"""Conservative humidity setpoint supervision for an ALREADY-ON HA humidifier.

Never sends turn_on, turn_off, set_mode, or climate.set_hvac_mode.
This is a target-only helper, not a compressor/heater safety controller.
Users explicitly opt in PER ROOM after selecting one fresh humidity sensor.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable

from .climate_coordination import duplicate_owners, device_inventory
from .climate_equipment import humidity_advice
from .climate_arbitration import new_command_gate
from .discovery import entity_area, reading
from .pid_math import finite
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
STARTUP_SETTLING_SECONDS = 300
MIN_WRITE_INTERVAL_SECONDS = 600
ACK_GRACE_SECONDS = 120
WRITE_TIMEOUT_SECONDS = 20
MAX_TARGET_CHANGE_RH = 5.0


def _target(attrs: dict) -> float | None:
    """Require a known observed setpoint, rejecting contradictory attributes."""
    values = [finite(attrs[k], 0, 100)
              for k in ("humidity", "target_humidity") if k in attrs]
    if not values or any(v is None for v in values):
        return None
    if max(values) - min(values) > 0.1:
        return None
    return values[0]


def _bounded_setpoint(attrs: dict, observed: float,
                      desired: float) -> tuple[str, int | None]:
    """No guessed limits or resolution; cap each change to five RH points."""
    lower = finite(attrs.get("min_humidity"), 0, 100)
    upper = finite(attrs.get("max_humidity"), 0, 100)
    step = finite(attrs.get("target_humidity_step"), 0.5, 10)
    if (lower is None or upper is None or step is None or
            upper <= lower or desired < lower or desired > upper or
            observed < lower or observed > upper):
        return "device_limits_or_resolution_unknown", None
    # HA humidifier.set_humidity accepts integer humidity target values.
    if step % 1 != 0 or lower % 1 != 0:
        return "unsupported_fractional_humidity_steps", None
    candidate = max(observed - MAX_TARGET_CHANGE_RH,
                    min(observed + MAX_TARGET_CHANGE_RH, desired))
    position = round((candidate - lower) / step)
    requested = round(lower + position * step)
    if requested < lower or requested > upper:
        return "out_of_device_range", None
    if abs(requested - observed) < max(0.5, step * 0.5):
        return "at_setpoint", None
    return "command", requested


class HumiditySetpointControl:
    """Explicitly selected and owned native device setpoint only."""

    def __init__(self, hass: Any, entry_id: str, *,
                 clock: Callable[[], float] | None = None,
                 changed: Callable[[], None] | None = None):
        self.hass, self.entry_id = hass, entry_id
        self.clock = clock or time.time
        self.changed = changed or (lambda: None)
        self.statuses: dict[str, dict] = {}
        self.paused: dict[str, str] = {}
        self.expected: dict[str, dict] = {}
        self.last_write: dict[str, float] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._store = None
        self._ready = False
        self._active = False
        self._started: float | None = None

    def _snapshot(self) -> dict:
        return {"version": 1, "paused": self.paused,
                "expected": self.expected, "last_write": self.last_write}

    def _persist(self) -> None:
        if self._store is not None:
            self._store.async_delay_save(self._snapshot, 3)

    def _status(self, area: str, name: str, **details: Any) -> None:
        value = {"status": name, **details}
        if self.statuses.get(area) != value:
            self.statuses[area] = value
            if self._active:
                self.changed()

    def _pause(self, area: str, reason: str) -> None:
        self.paused[area] = reason
        self._persist()
        self._status(area, "paused", reason=reason)

    async def async_start(self) -> None:
        self._active = True
        self._started = self.clock()
        try:
            from homeassistant.helpers.storage import Store
            self._store = Store(self.hass, 1,
                f"{DOMAIN}.humidity_native_{self.entry_id}")
            saved = await self._store.async_load()
        except Exception:
            _LOGGER.exception("Humidity setpoint safety storage unavailable")
            return
        if isinstance(saved, dict) and saved.get("version") == 1:
            self.paused = {a:v for a,v in saved.get("paused",{}).items()
                           if isinstance(a,str) and isinstance(v,str)} if isinstance(
                               saved.get("paused"), dict) else {}
            self.expected = {a:v for a,v in saved.get("expected",{}).items()
                             if isinstance(a,str) and isinstance(v,dict)} if isinstance(
                                 saved.get("expected"), dict) else {}
            self.last_write = {a:float(v) for a,v in
                               saved.get("last_write",{}).items()
                               if isinstance(a,str) and finite(v,0,1e13) is not None
                               } if isinstance(saved.get("last_write"),dict) else {}
        self._ready = True

    async def async_stop(self) -> None:
        self._active = False
        tasks = tuple(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        if self._ready and self._store is not None:
            await self._store.async_save(self._snapshot())

    async def command(self, area: str, action: str) -> dict:
        if action not in ("pause", "resume") or not self._ready:
            return {"accepted": False, "reason": "unsupported_action_or_unready"}
        task = self._tasks.get(area)
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if action == "pause":
            self._pause(area, "user_paused")
        else:
            self.paused.pop(area, None)
            self.expected.pop(area, None)
            self.last_write.pop(area, None)
            self._started = self.clock()
            self._persist()
            self._status(area, "startup_warmup")
        return {"accepted": True, "area": area, "action": action}

    def schedule(self, configs: dict, plans: dict) -> None:
        if not self._active or not self._ready or not isinstance(configs,dict):
            return
        duplicates = duplicate_owners(configs)
        now = self.clock()
        for area, cfg in configs.items():
            if not isinstance(cfg,dict) or not cfg.get("enabled"):
                continue
            if cfg.get("humidity_power_auto") is True:
                self._status(area, "conflicting_humidity_power_owner")
                continue
            if not (cfg.get("allow_actuation") is True and
                    cfg.get("humidity_setpoint_auto") is True):
                self._status(area, "advisory_only")
                continue
            if area in self.paused:
                self._status(area, "paused", reason=self.paused[area])
                continue
            if set((cfg.get("humidifier_entity"),
                    cfg.get("dehumidifier_entity"))).intersection(duplicates):
                self._status(area, "duplicate_equipment_owner")
                continue
            plan = plans.get(area, {})
            if not isinstance(plan,dict) or plan.get("window_safe") is not True:
                self._status(area, "window_interlock_or_missing_plan")
                continue
            equipment = plan.get("equipment_plan", {})
            if equipment.get("status")!="ready":
                self._status(area, "unverified_equipment_plan")
                continue
            choice = equipment.get("moisture",{})
            if (choice.get("status")!="selected" or
                choice.get("role") not in ("humidifier_entity","dehumidifier_entity")):
                self._status(area, "no_selected_native_humidity_device")
                continue
            if now - (self._started if self._started is not None else now) < STARTUP_SETTLING_SECONDS:
                self._status(area, "startup_warmup")
                continue
            if now - self.last_write.get(area,0) < MIN_WRITE_INTERVAL_SECONDS:
                continue
            task = self._tasks.get(area)
            if task and not task.done():
                continue
            task = self.hass.async_create_task(self._apply(area,cfg,plan,now))
            self._tasks[area] = task
            def done(future:asyncio.Task, key:str=area)->None:
                if self._tasks.get(key) is future:
                    self._tasks.pop(key,None)
                if not future.cancelled():
                    try:
                        future.result()
                    except Exception:
                        _LOGGER.exception("Unexpected humidity control failure in %s",key)
                        self._pause(key,"unexpected_task_exception")
            task.add_done_callback(done)

    async def _apply(self, area: str, cfg: dict, plan: dict, now: float) -> None:
        if not self._active or not self._ready or area in self.paused:
            return
        if cfg.get("humidity_power_auto") is True:
            self._status(area, "conflicting_humidity_power_owner")
            return
        choice = plan.get("equipment_plan",{}).get("moisture",{})
        role = choice.get("role")
        action = choice.get("action")
        if (role not in ("humidifier_entity","dehumidifier_entity") or
                action not in ("humidify","dry") or
                (role == "humidifier_entity") != (action == "humidify")):
            self._status(area, "invalid_moisture_intent")
            return
        entity = cfg.get(role)
        if (not isinstance(entity,str) or choice.get("entity_id")!=entity or
                entity_area(self.hass,entity)!=area):
            self._status(area, "unverified_humidity_device_or_area")
            return
        sensor = cfg.get("humidity_entity")
        if not isinstance(sensor,str) or entity_area(self.hass,sensor)!=area:
            self._status(area, "explicit_fresh_humidity_sensor_required")
            return
        live = reading(self.hass,sensor,10,outdoor=False)
        if live.metric!="humidity" or live.value is None:
            self._status(area, "humidity_measurement_stale_or_invalid")
            return
        reading_advice = humidity_advice(
            live.value, low_rh=cfg.get("humidity_low_rh",40),
            high_rh=cfg.get("humidity_high_rh",60),
            hysteresis=cfg.get("humidity_hysteresis_rh",3),
        )
        if reading_advice.get("status")!="advisory" or reading_advice.get("action")!=action:
            self._status(area, "humidity_intent_changed")
            return
        if plan.get("window_safe") is not True:
            self._status(area, "window_interlock")
            return
        inventory=device_inventory(self.hass,area,cfg)
        item=inventory.get(role,{})
        if (item.get("status")!="ready" or item.get("entity_id")!=entity):
            self._status(area, "device_unavailable_or_not_verified")
            return
        state=self.hass.states.get(entity)
        if state is None or state.state!="on":
            self._status(area, "device_off_no_automatic_start")
            return
        attrs=state.attributes
        observed=_target(attrs)
        if observed is None:
            self._status(area, "native_target_unavailable_or_ambiguous")
            return
        expected=self.expected.get(area)
        if expected:
            if expected.get("entity_id")!=entity:
                self._pause(area,"configured_device_changed_since_last_command")
                return
            prior=finite(expected.get("target"),0,100)
            written=finite(expected.get("when"),0,1e13)
            if prior is None or written is None or written>now:
                self._pause(area,"invalid_persistent_ack_state")
                return
            if abs(observed-prior)>0.51:
                if now-written<ACK_GRACE_SECONDS:
                    self._status(area,"waiting_for_target_ack")
                else:
                    self._pause(area,"manual_setpoint_change_or_unacknowledged_write")
                return
        desired=reading_advice["target_band_rh"][0 if action=="humidify" else 1]
        # A user may choose independent device setpoints during normal hours
        # and sleep; this never switches the device ON or bypasses native
        # humidity demand, bounds, write-rate or reconciliation guards.
        chosen=(cfg.get("device_settings",{}).get(entity,{})
                if isinstance(cfg.get("device_settings"),dict) else {})
        if isinstance(chosen,dict) and chosen.get("auto_control") is True:
            sleeping=(plan.get("sleeping") is True and
                      chosen.get("sleep_behavior")=="sleep_targets")
            value=finite(chosen.get(
                "sleep_humidity_target" if sleeping else "humidity_target"),20,80)
            if value is not None:
                desired=value
        status,target=_bounded_setpoint(attrs,observed,desired)
        if status!="command":
            self._status(area,status,entity_id=entity)
            return
        conflict=new_command_gate(
            self.hass,area,cfg,plan,"humidity",entity,now=now,entry_id=self.entry_id,
        )
        if conflict is not None:
            self._status(area,"coordination_hold",reason=conflict)
            return
        if not self.hass.services.has_service("humidifier","set_humidity"):
            self._status(area, "set_humidity_service_missing")
            return
        try:
            await asyncio.wait_for(self.hass.services.async_call(
                "humidifier","set_humidity",{"humidity":target},
                target={"entity_id":entity},blocking=True),
                WRITE_TIMEOUT_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.exception("Failed to set native humidifier target: %s",entity)
            self._pause(area,"humidity_service_failure")
            return
        self.expected[area]={"entity_id":entity,"target":target,"when":now}
        self.last_write[area]=now
        self._persist()
        self._status(area,"target_commanded",entity_id=entity,target_rh=target)
