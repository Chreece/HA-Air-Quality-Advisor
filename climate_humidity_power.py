"""Draft guarded humidifier/dehumidifier power owner.

Only explicitly attested HA humidifier.* entities may be powered; never operate
generic switches, compressors exposed as climate.*, fan.*, or other actuators.
Manual/unknown output states, failed acknowledgements, unexpected restarts and
uncertain moisture evidence all fail closed. A device's independent compressor,
frost, tank-full and electrical protections remain mandatory.

This is not production commissioning approval.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Callable

from .climate_coordination import device_inventory, duplicate_owners
from .const import DOMAIN
from .climate_equipment import humidity_advice
from .climate_arbitration import new_command_gate
from .climate_humidity_native import _target as native_humidity_target
from .discovery import entity_area, reading
from .pid_math import finite

_LOGGER = logging.getLogger(__name__)
WARMUP_S = 300
ACK_S = 120
WRITE_TIMEOUT_S = 20
ROLES = {"dry": "dehumidifier_entity", "humidify": "humidifier_entity"}


def timings(config: dict) -> tuple[float, float, float] | None:
    """Require realistic compressor dwell and a finite watchdog limit."""
    low = finite(config.get("humidity_power_min_on_s", 600), 300, 7200)
    high = finite(config.get("humidity_power_min_off_s", 600), 600, 14400)
    maximum = finite(config.get("humidity_power_max_on_s", 7200), 900, 28800)
    if None in (low, high, maximum) or maximum <= low:
        return None
    return low, high, maximum


class HumidityPowerControl:
    """Persistent single-room output ownership; fail closed on restart."""

    def __init__(
        self, hass: Any, entry_id: str, *, clock: Callable[[], float] | None = None,
        changed: Callable[[], None] | None = None,
    ) -> None:
        self.hass, self.entry_id = hass, entry_id
        self.clock = clock or time.time
        self.changed = changed or (lambda: None)
        self.statuses: dict[str, dict] = {}
        self.paused: dict[str, str] = {}
        # Each record contains one exact owned entity and expected on/off state.
        self.records: dict[str, dict] = {}
        self.last_off: dict[str, float] = {}
        self.off_seen: dict[str, float] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._configured: dict = {}
        self._store = None
        self._active = False
        self._ready = False
        self._started: float | None = None

    def _snapshot(self) -> dict:
        return {"version": 1, "paused": dict(self.paused),
                "records": {key: dict(value) for key, value in self.records.items()},
                "last_off": dict(self.last_off)}

    def _save(self) -> None:
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
        self._save()
        self._status(area, "paused", reason=reason)

    async def async_start(self) -> None:
        self._active = True
        self._started = self.clock()
        try:
            from homeassistant.helpers.storage import Store
            self._store = Store(
                self.hass, 1, f"{DOMAIN}.humidity_power_{self.entry_id}"
            )
            loaded = await self._store.async_load()
        except Exception:
            _LOGGER.exception("Humidity power safety history unavailable")
            return
        if isinstance(loaded, dict) and loaded.get("version") == 1:
            self.paused = {k: v for k, v in loaded.get("paused", {}).items()
                           if isinstance(k, str) and isinstance(v, str)} if isinstance(
                               loaded.get("paused"), dict) else {}
            self.last_off = {
                k: float(v) for k, v in loaded.get("last_off", {}).items()
                if isinstance(k, str) and k.startswith("humidifier.")
                and finite(v, 0, 1e13) is not None
            } if isinstance(loaded.get("last_off"), dict) else {}
            saved = loaded.get("records", {})
            if isinstance(saved, dict):
                for area, record in saved.items():
                    if not isinstance(area, str) or not isinstance(record, dict):
                        continue
                    entity = record.get("entity_id")
                    if isinstance(entity, str) and entity.startswith("humidifier."):
                        self.records[area] = dict(record)
                        # A running appliance after HA was stopped is not
                        # automatically re-owned, regardless of persisted state.
                        self.paused[area] = "restart_requires_manual_output_reconciliation"
        self._ready = True
        self._save()

    async def async_stop(self) -> None:
        self._active = False
        tasks = tuple(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        # Do not issue sudden compressor power changes on HA shutdown.
        # Persist ownership and require manual reconciliation on restart.
        if self._ready and self._store is not None:
            await self._store.async_save(self._snapshot())

    async def command(self, area: str, action: str) -> dict:
        if action not in ("pause", "resume") or not self._ready:
            return {"accepted": False, "reason": "unsupported_action_or_storage"}
        task = self._tasks.get(area)
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if action == "pause":
            self._pause(area, "user_paused")
            # _tick still schedules OWNED equipment for a safe delayed OFF.
            return {"accepted": True, "area": area, "action": action}
        record = self.records.get(area)
        if record is not None:
            state = self.hass.states.get(record.get("entity_id"))
            if state is None or state.state != "off":
                return {"accepted": False, "reason": "manual_off_reconciliation_required"}
            # The physical device is now OFF. Require a full observed off dwell
            # and warmup before another automatic ON.
            self.last_off[record["entity_id"]] = self.clock()
            self.off_seen[record["entity_id"]] = self.clock()
            self.records.pop(area, None)
        self.paused.pop(area, None)
        self._started = self.clock()
        self._save()
        self._status(area, "startup_warmup")
        return {"accepted": True, "area": area, "action": action}

    def schedule(self, configs: dict, plans: dict) -> None:
        if not self._active or not self._ready or not isinstance(configs, dict):
            return
        self._configured = configs
        now = self.clock()
        # Config entry/room removal must NOT abandon a previously powered
        # humidifier: continue its independent bounded OFF/reconciliation
        # handling even when the room is no longer configured.
        for area in set(configs) | set(self.records):
            if not isinstance(area, str):
                continue
            config=configs.get(area,{})
            if not isinstance(config,dict):
                config={}
            active_record = self.records.get(area)
            if (not active_record and not (
                config.get("enabled") is True and
                config.get("allow_actuation") is True and
                config.get("humidity_power_auto") is True and
                config.get("humidity_power_hardware_confirmed") is True
            )):
                self._status(area, "advisory_only")
                continue
            task = self._tasks.get(area)
            if task is not None and not task.done():
                continue
            plan = plans.get(area, {})
            task = self.hass.async_create_task(self._tick(area, config, plan, now))
            self._tasks[area] = task
            def done(future: asyncio.Task, key: str = area) -> None:
                if self._tasks.get(key) is future:
                    self._tasks.pop(key, None)
                if not future.cancelled():
                    try:
                        future.result()
                    except Exception:
                        _LOGGER.exception("Uncaught humidity power error for %s", key)
                        self._pause(key, "controller_exception")
            task.add_done_callback(done)

    async def _send(self, area: str, record: dict, power: str,
                    now: float) -> bool:
        entity = record["entity_id"]
        action = "turn_on" if power == "on" else "turn_off"
        try:
            if not self.hass.services.has_service("humidifier", action):
                self._status(area, "humidifier_service_missing", action=action)
                return False
            await asyncio.wait_for(self.hass.services.async_call(
                "humidifier", action, {}, target={"entity_id": entity},
                blocking=True,
            ), WRITE_TIMEOUT_S)
        except asyncio.CancelledError:
            raise
        except Exception:
            self._pause(area, "output_service_failure_or_timeout")
            return False
        record.update({"power": power, "when": now, "acknowledged": False})
        self.records[area] = record
        self._save()
        self._status(area, "power_command_sent", action=action, entity_id=entity)
        return True

    def _evidence(self, area: str, cfg: dict, plan: dict) -> tuple[str, str | None]:
        """Recheck the live sensor and each configured window every cycle."""
        if not isinstance(plan, dict):
            return "missing_room_plan", None
        if plan.get("window_safe") is not True:
            return "window_plan_blocked", None
        contacts = plan.get("window_contacts")
        if not isinstance(contacts, list):
            return "window_evidence_missing", None
        if not contacts and cfg.get("humidity_power_windowless_confirmed") is not True:
            return "window_contact_or_explicit_exception_required", None
        for contact in contacts:
            if (not isinstance(contact, str) or entity_area(self.hass, contact) != area):
                return "wrong_room_window_contact", None
            current = self.hass.states.get(contact)
            if (current is None or current.domain != "binary_sensor" or
                    current.attributes.get("device_class") != "window" or
                    current.state != "off"):
                return "window_open_or_unavailable", None
        sensor = cfg.get("humidity_entity")
        if not isinstance(sensor, str) or entity_area(self.hass, sensor) != area:
            return "humidity_sensor_unverified", None
        measured = reading(self.hass, sensor, 10, outdoor=False)
        if measured.metric != "humidity" or measured.value is None:
            return "humidity_sensor_stale", None
        return "ready", sensor

    @staticmethod
    def _internal_target_suitable(state: Any, demand: str, config: dict) -> bool:
        target = native_humidity_target(state.attributes)
        band = config.get("humidity_low_rh", 40) if demand == "humidify" else config.get("humidity_high_rh", 60)
        desired = finite(band, 20, 80)
        # Require a compatible pre-programmed native controller, NOT an
        # arbitrary 30% drying target left from a prior manual session.
        minimum = finite(state.attributes.get("min_humidity"), 0, 100)
        maximum = finite(state.attributes.get("max_humidity"), 0, 100)
        step = finite(state.attributes.get("target_humidity_step"), 0.5, 10)
        return (target is not None and desired is not None and
                minimum is not None and maximum is not None and
                step is not None and minimum < maximum and
                minimum <= target <= maximum and
                abs(target-desired) <= 2 and
                abs((target-minimum)/step-round((target-minimum)/step)) < 0.01)

    async def _tick(self, area: str, cfg: dict, plan: dict, now: float) -> None:
        if not self._ready or not self._active:
            return
        record = self.records.get(area)
        if record is not None:
            # Freeze compressor minimum-ON and maximum-ON protections at
            # initial power-on. An options edit must not retroactively alter
            # the operating envelope of equipment that is already running.
            min_on=finite(record.get("min_on_s"),300,7200)
            max_on=finite(record.get("max_on_s"),900,28800)
            if min_on is None or max_on is None or max_on<=min_on:
                previous=timings(cfg) if cfg else None
                if previous is None:
                    self._pause(area,"original_power_dwell_unknown_reconcile_manually")
                    return
                min_on,_,max_on=previous
            await self._owned_tick(area,cfg,plan,now,record,min_on,max_on)
            return
        dwell = timings(cfg)
        if dwell is None:
            self._status(area, "invalid_hardware_dwell_config")
            return
        min_on, min_off, max_on = dwell
        if area in self.paused:
            self._status(area, "paused", reason=self.paused[area])
            return
        if not (cfg.get("enabled") is True and cfg.get("allow_actuation") is True
                and cfg.get("humidity_power_auto") is True
                and cfg.get("humidity_power_hardware_confirmed") is True
                and cfg.get("humidity_setpoint_auto") is not True):
            self._status(area, "advisory_only_or_conflicting_humidity_driver")
            return
        if now - (self._started if self._started is not None else now) < WARMUP_S:
            self._status(area, "startup_warmup")
            return
        if not isinstance(plan, dict) or plan.get("equipment_plan",{}).get("status") != "ready":
            self._status(area, "equipment_plan_unknown")
            return
        if any(x in duplicate_owners(self._configured)
               for x in (cfg.get("humidifier_entity"), cfg.get("dehumidifier_entity"))
               if isinstance(x, str)):
            self._status(area, "duplicate_humidity_device_owner")
            return
        quality, sensor = self._evidence(area, cfg, plan)
        if quality != "ready":
            self._status(area, quality)
            return
        humidity = reading(self.hass, sensor, 10, outdoor=False).value
        intent = humidity_advice(
            humidity, low_rh=cfg.get("humidity_low_rh",40),
            high_rh=cfg.get("humidity_high_rh",60),
            hysteresis=cfg.get("humidity_hysteresis_rh",3),
        )
        if intent.get("status") != "advisory" or intent["action"] not in ROLES:
            self._status(area, "no_humidity_power_demand")
            return
        desired = intent["action"]
        role = ROLES[desired]
        selection = plan["equipment_plan"].get("moisture", {})
        entity = cfg.get(role)
        if (selection.get("status")!="selected" or selection.get("role")!=role
            or selection.get("entity_id") != entity or
            not isinstance(entity,str) or not entity.startswith("humidifier.")):
            self._status(area, "no_verified_selected_device")
            return
        inventory = device_inventory(self.hass,area,cfg)
        if inventory.get(role,{}).get("status") != "ready":
            self._status(area, "native_humidity_device_unavailable")
            return
        opposite_role = "humidifier_entity" if role=="dehumidifier_entity" else "dehumidifier_entity"
        opposite = inventory.get(opposite_role,{})
        if opposite.get("active") is True or (
            opposite and opposite.get("status") != "ready"):
            self._status(area, "opposing_humidity_output_on_or_unknown")
            return
        for other in inventory.values():
            if (other.get("domain") == "climate" and
                    other.get("status")=="ready" and
                    (other.get("hvac_action")=="drying" or
                     other.get("capabilities",{}).get("current")=="dry")):
                self._status(area, "native_ac_drying_already_active")
                return
        native = self.hass.states.get(entity)
        if native is None:
            self._status(area, "device_unavailable")
            return
        if native.state == "on":
            self._pause(area, "external_power_on_not_owned")
            return
        if native.state != "off":
            self._status(area, "unknown_native_power")
            return
        self.off_seen.setdefault(entity, now)
        last_observed = self.off_seen[entity]
        last_off = self.last_off.get(entity, last_observed)
        # HA's last_changed catches brief manual ON/OFF events between
        # supervisor polls. Only an aware timestamp is trusted; otherwise
        # rely on the conservative in-process continuous OFF observation.
        changed = getattr(native, "last_changed", None)
        if isinstance(changed, datetime) and changed.tzinfo is not None:
            observed_change = changed.timestamp()
            if observed_change > now or now-observed_change < min_off:
                self._status(area, "minimum_native_device_off_hold")
                return
        if now < last_off or now - max(last_observed,last_off) < min_off:
            self._status(area, "minimum_off_hold")
            return
        if not self._internal_target_suitable(native, desired, cfg):
            self._status(area, "native_target_must_be_commissioned")
            return
        conflict=new_command_gate(
            self.hass,area,cfg,plan,"humidity",entity,now=now,entry_id=self.entry_id,
        )
        if conflict is not None:
            self._status(area,"coordination_hold",reason=conflict)
            return
        record = {"entity_id":entity,"role":role,"area":area,
                  "power":"off","when":now,"acknowledged":True,
                  "target":native_humidity_target(native.attributes),
                  "min_on_s":min_on,"max_on_s":max_on}
        await self._send(area,record,"on",now)

    async def _owned_tick(self, area: str, cfg: dict, plan: dict, now: float,
                          record: dict, min_on: float, max_on: float) -> None:
        entity = record.get("entity_id")
        role = record.get("role")
        if (not isinstance(entity,str) or not entity.startswith("humidifier.")
                or role not in ROLES.values() or record.get("area")!=area):
            self._pause(area,"damaged_ownership_record")
            return
        state = self.hass.states.get(entity)
        if (state is None or entity_area(self.hass,entity)!=area or
                state.state not in ("on","off") or
                state.attributes.get("device_class") != (
                    "humidifier" if role=="humidifier_entity" else "dehumidifier")):
            self._pause(area,"owned_output_unverifiable")
            return
        expected = record.get("power")
        commanded_at = finite(record.get("when"),0,1e13)
        if expected not in ("on","off") or commanded_at is None or commanded_at>now:
            self._pause(area,"damaged_ack_history")
            return
        if state.state != expected:
            if now - commanded_at < ACK_S:
                self._status(area,"waiting_for_power_ack",entity_id=entity)
                return
            self._pause(area,"manual_power_or_failed_ack")
            return
        if record.get("acknowledged") is not True:
            record["acknowledged"] = True
            self._save()
        if expected == "off":
            self.last_off[entity] = commanded_at
            self.off_seen[entity] = now
            self.records.pop(area,None)
            self._save()
            self._status(area,"power_off_acknowledged",entity_id=entity)
            return
        # Persisted active device remains paused across restart. No automatic
        # OFF command is sent after HA lost control of the device.
        if area in self.paused and self.paused[area] != "user_paused":
            # Manual mode/target change, service failure, and restart all
            # transfer authority away from this controller. Never keep
            # retrying power writes after a fault.
            self._status(area, "paused", reason=self.paused[area])
            return
        target = native_humidity_target(state.attributes)
        if target is None or abs(target-float(record.get("target",-999)))>0.51:
            self._pause(area,"manual_native_humidity_target_change")
            return
        on_since = commanded_at
        if now < on_since:
            self._pause(area,"clock_regression")
            return
        if now - on_since >= max_on:
            if await self._send(area,record,"off",now):
                self._pause(area,"maximum_owned_runtime_exceeded")
            return
        evidence, sensor = self._evidence(area,cfg,plan)
        power_enabled = (
            cfg.get("enabled") is True and cfg.get("allow_actuation") is True
            and cfg.get("humidity_power_auto") is True
            and cfg.get("humidity_power_hardware_confirmed") is True
            and cfg.get("humidity_setpoint_auto") is not True
        )
        if area in self.paused or evidence!="ready" or not power_enabled:
            stop = True
        else:
            latest = reading(self.hass,sensor,10,outdoor=False)
            action = "humidify" if role=="humidifier_entity" else "dry"
            persisted = humidity_advice(
                latest.value, low_rh=cfg.get("humidity_low_rh",40),
                high_rh=cfg.get("humidity_high_rh",60),
                hysteresis=cfg.get("humidity_hysteresis_rh",3),
                previous=action,
            )
            stop = (persisted.get("status")!="advisory" or
                    persisted.get("action")!=action)
        if not stop:
            inventory = device_inventory(self.hass, area, cfg)
            other_role = ("humidifier_entity" if role=="dehumidifier_entity"
                          else "dehumidifier_entity")
            opposite = inventory.get(other_role, {})
            if opposite.get("active") is True or (
                opposite and opposite.get("status") != "ready"
            ):
                stop = True
        if not stop:
            # A newly armed cooling/drying device may change the room
            # priority during the minimum-on period. Never abandon owned
            # hardware; request an acknowledged, bounded OFF after dwell.
            conflict=new_command_gate(
                self.hass,area,cfg,plan,"humidity",entity,now=now,entry_id=self.entry_id,
            )
            if conflict is not None:
                stop=True
        if not stop:
            self._status(area,"owned_running",entity_id=entity,
                         elapsed_s=int(now-on_since))
            return
        if now - on_since < min_on:
            self._status(area,"minimum_on_hold_before_safe_off",
                         remaining_s=round(min_on-(now-on_since)))
            return
        await self._send(area,record,"off",now)
