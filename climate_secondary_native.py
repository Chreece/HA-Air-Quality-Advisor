"""Secondary native HVAC setpoint supervision; never changes HVAC operating modes.

Only an explicitly opted-in, already-running room-assigned climate device
with current HEAT/COOL mode and native internal regulation receives bounded
climate.set_temperature commands. Missing or conflicting evidence holds.
Compressors, relays, power and mode transitions are never commanded here.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable

from .climate_coordination import assigned_entities, duplicate_owners, device_inventory
from .climate_arbitration import new_command_gate
from .discovery import entity_area, temperature_sensor_c
from .pid_math import bounded_command, finite, target_from_unit
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
STARTUP_WARMUP_S = 300
WRITE_INTERVAL_S = 300
ACK_GRACE_S = 120
WRITE_TIMEOUT_S = 20
ROLES = {"heat": "heat_climate_entity", "cool": "cool_climate_entity"}
OPPOSING_MODES = {
    "heat": frozenset(("cool", "heat_cool", "auto", "dry")),
    "cool": frozenset(("heat", "heat_cool", "auto")),
}


class SecondaryClimateSetpoint:
    """Separate, persistent ownership for an optional second HVAC device."""

    def __init__(self, hass: Any, entry_id: str, *, clock: Callable | None = None,
                 changed: Callable | None = None):
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
        self._configured: dict = {}
        self._pid_rooms: dict = {}

    def _snapshot(self) -> dict:
        return {"version": 1, "paused": self.paused, "expected": self.expected,
                "last_write": self.last_write}

    def _save(self) -> None:
        if self._store is not None:
            self._store.async_delay_save(self._snapshot, 3)

    def _status(self, area: str, value: str, **details: Any) -> None:
        status = {"status": value, **details}
        if self.statuses.get(area) != status:
            self.statuses[area] = status
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
            self._store = Store(self.hass, 1,
                f"{DOMAIN}.secondary_native_{self.entry_id}")
            saved = await self._store.async_load()
        except Exception:
            _LOGGER.exception("Secondary native thermostat safety storage unavailable")
            return
        if isinstance(saved, dict) and saved.get("version") == 1:
            if isinstance(saved.get("paused"), dict):
                self.paused = {
                    k:v for k,v in saved["paused"].items()
                    if isinstance(k,str) and isinstance(v,str)
                }
            if isinstance(saved.get("expected"), dict):
                self.expected = {
                    k:v for k,v in saved["expected"].items()
                    if isinstance(k,str) and isinstance(v,dict)
                }
            if isinstance(saved.get("last_write"), dict):
                self.last_write = {
                    k:float(v) for k,v in saved["last_write"].items()
                    if isinstance(k,str) and finite(v,0,1e13) is not None
                }
        self._ready = True

    async def async_stop(self) -> None:
        self._active = False
        pending = tuple(self._tasks.values())
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self._tasks.clear()
        if self._ready and self._store is not None:
            await self._store.async_save(self._snapshot())

    async def command(self, area: str, action: str) -> dict:
        if action not in ("pause", "resume") or not self._ready:
            return {"accepted": False, "reason": "unsupported_action_or_not_ready"}
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
            self._save()
            self._status(area, "startup_warmup")
        return {"accepted": True, "area": area, "action": action}

    @staticmethod
    def _requested(area: str, cfg: dict, plan: dict) -> tuple[str, str, str] | None:
        if (not isinstance(cfg, dict) or cfg.get("enabled") is not True or
                cfg.get("controller") != "device" or
                cfg.get("allow_actuation") is not True or
                cfg.get("secondary_climate_setpoint_auto") is not True):
            return None
        if (not isinstance(plan, dict) or
                plan.get("status") != "hold" or
                plan.get("reason") != "secondary_thermal_driver_pending" or
                plan.get("window_safe") is not True):
            return None
        equipment = plan.get("equipment_plan", {})
        thermal = equipment.get("thermal", {})
        mode = plan.get("mode")
        if (equipment.get("status") != "ready" or
                thermal.get("status") != "selected" or
                mode not in ROLES or
                thermal.get("mode") != mode or
                thermal.get("role") != ROLES[mode]):
            return None
        entity = cfg.get(ROLES[mode])
        primary = cfg.get("climate_entity")
        if (not isinstance(entity, str) or not entity.startswith("climate.") or
                entity == primary or thermal.get("entity_id") != entity):
            return None
        return entity, mode, ROLES[mode]

    def schedule(self, configs: dict, plans: dict, *,
                 pid_rooms: dict | None = None) -> None:
        if not self._active or not self._ready or not isinstance(configs, dict):
            return
        self._configured = configs
        self._pid_rooms = pid_rooms if isinstance(pid_rooms,dict) else {}
        duplicated = duplicate_owners(configs)
        pid_targets = {
            target for config in self._pid_rooms.values()
            if isinstance(config,dict) and config.get("enabled")
            for target in config.get("climate_entities",[])
            if isinstance(target,str)
        }
        now = self.clock()
        for area,cfg in configs.items():
            if not isinstance(area,str) or not isinstance(cfg,dict):
                continue
            if (cfg.get("controller")!="device" or
                    cfg.get("secondary_climate_setpoint_auto") is not True or
                    cfg.get("allow_actuation") is not True):
                self._status(area, "advisory_only")
                continue
            if area in self.paused:
                self._status(area,"paused",reason=self.paused[area])
                continue
            if self._requested(area,cfg,plans.get(area,{})) is None:
                self._status(area,"no_verified_secondary_demand")
                continue
            entity, mode, _ = self._requested(area,cfg,plans[area])
            if entity in duplicated or entity in pid_targets or (
                self._pid_rooms.get(area,{}).get("enabled")
            ):
                self._status(area,"conflicting_controller_or_equipment_owner")
                continue
            if now - (self._started or now) < STARTUP_WARMUP_S:
                self._status(area,"startup_warmup")
                continue
            if now - self.last_write.get(area,0) < WRITE_INTERVAL_S:
                continue
            task=self._tasks.get(area)
            if task and not task.done():
                continue
            task=self.hass.async_create_task(self._apply(area,cfg,plans[area],now))
            self._tasks[area]=task
            def done(future: asyncio.Task, key:str=area) -> None:
                if self._tasks.get(key) is future:
                    self._tasks.pop(key,None)
                if not future.cancelled():
                    try:
                        future.result()
                    except Exception:
                        _LOGGER.exception("Secondary climate error for %s",key)
                        self._pause(key,"unexpected_task_exception")
            task.add_done_callback(done)

    def _interlock_others(self, area: str, selected: str, mode: str,
                          cfg: dict) -> str | None:
        """Never energize against active/unknown heating or cooling appliances.

        A second native thermostat's own PID can restart without our command.
        If it is armed in the opposing mode, even a currently-idle device
        blocks the secondary target write. This can be relaxed only after
        deliberate end-to-end heat/cool arbitration and commissioning.
        """
        for entity in assigned_entities(cfg):
            if not entity.startswith("climate.") or entity == selected:
                continue
            if entity_area(self.hass,entity) != area:
                return "other_climate_wrong_room"
            state = self.hass.states.get(entity)
            if state is None or state.state in ("unavailable","unknown"):
                return "other_climate_unavailable"
            if state.state in OPPOSING_MODES[mode]:
                return "other_thermostat_opposing_mode_armed"
            action = state.attributes.get("hvac_action")
            if action is None and state.state != "off":
                return "other_thermostat_action_unknown"
            if action in ("heating","cooling","drying","preheating"):
                return "other_thermostat_active"
        return None

    async def _apply(self, area: str, cfg: dict, plan: dict, now: float) -> None:
        if not self._active or not self._ready or area in self.paused:
            return
        if now - (self._started or now) < STARTUP_WARMUP_S:
            self._status(area,"startup_warmup")
            return
        if now - self.last_write.get(area,0) < WRITE_INTERVAL_S:
            return
        selected=self._requested(area,cfg,plan)
        if selected is None:
            self._status(area,"plan_or_permission_changed")
            return
        entity, mode, role = selected
        conflict=new_command_gate(
            self.hass,area,cfg,plan,"thermal",entity,now=now,entry_id=self.entry_id,
        )
        if conflict is not None:
            self._status(area,"coordination_hold",reason=conflict)
            return
        if entity in duplicate_owners(self._configured):
            self._status(area,"duplicate_equipment_owner")
            return
        if any(entity in conf.get("climate_entities",[])
               for conf in self._pid_rooms.values()
               if isinstance(conf,dict) and conf.get("enabled")):
            self._status(area,"pid_already_owns_device")
            return
        if self._pid_rooms.get(area,{}).get("enabled"):
            self._status(area,"room_pid_conflict")
            return
        source=cfg.get("temperature_entity")
        if (not isinstance(source,str) or entity_area(self.hass,source)!=area or
                temperature_sensor_c(self.hass,source,10) is None):
            self._status(area,"temperature_stale_or_wrong_room")
            return
        windows=plan.get("window_contacts",[])
        if not isinstance(windows,list):
            self._status(area,"unknown_window_contacts")
            return
        for window in windows:
            current=self.hass.states.get(window)
            if (current is None or current.domain!="binary_sensor" or
                    current.attributes.get("device_class")!="window" or
                    current.state!="off"):
                self._status(area,"window_open_or_unavailable")
                return
        inventory=device_inventory(self.hass,area,cfg)
        selected_item=inventory.get(role,{})
        features=selected_item.get("capabilities",{})
        if (selected_item.get("status")!="ready" or
                selected_item.get("entity_id")!=entity or
                features.get("temperature_setpoint") is not True or
                features.get("heating" if mode=="heat" else "cooling") is not True):
            self._status(area,"secondary_device_unavailable_or_unsupported")
            return
        status=self._interlock_others(area,entity,mode,cfg)
        if status:
            self._status(area,status)
            return
        state=self.hass.states.get(entity)
        if state.state=="off":
            self._pause(area,"thermostat_switched_off")
            return
        expected=self.expected.get(area)
        if expected and (expected.get("entity")!=entity or
                         expected.get("mode")!=mode):
            self._pause(area,"configuration_or_mode_changed_since_last_command")
            return
        if state.state!=mode:
            if expected:
                self._pause(area,"manual_mode_override")
            else:
                self._status(area,"native_mode_mismatch_no_mode_switch")
            return
        attrs=state.attributes
        preset=str(attrs.get("preset_mode") or "").casefold()
        if preset not in ("","none","manual"):
            self._status(area,"native_preset_active",preset=preset)
            return
        observed=finite(attrs.get("temperature"),-30,150)
        unit=attrs.get("temperature_unit")
        low=finite(attrs.get("min_temp"),-30,140)
        high=finite(attrs.get("max_temp"),-29,150)
        step=finite(attrs.get("target_temp_step"),0.1,10)
        if (None in (observed,low,high,step) or
                unit not in ("°C","C","°F","F") or low>=high):
            self._status(area,"native_setpoint_limits_unknown")
            return
        if expected:
            sent=finite(expected.get("when"),0,1e13)
            previous=finite(expected.get("target"),-30,150)
            if sent is None or previous is None or sent>now:
                self._pause(area,"persistent_ack_history_invalid")
                return
            if abs(observed-previous)>max(0.05,step*.51):
                if now-sent<ACK_GRACE_S:
                    self._status(area,"waiting_for_native_ack")
                else:
                    self._pause(area,"manual_setpoint_or_missing_ack")
                return
        desired=finite(plan.get("temperature_target_c"),5,36)
        profiles=(cfg.get("device_settings",{}) if isinstance(cfg.get("device_settings"),dict)
                  else {})
        override=profiles.get(entity,{})
        if isinstance(override,dict) and override.get("auto_control") is True:
            profile=plan.get("profile","home")
            if profile not in ("home","unoccupied","away","sleep"):
                profile="home"
            if profile=="sleep" and override.get("sleep_behavior")!="sleep_targets":
                profile="home"
            proposed=finite(override.get(f"{profile}_{mode}_c"),5,36)
            if proposed is not None:
                desired=proposed
        current_c=target_from_unit(observed,unit)
        if desired is None or current_c is None:
            self._status(area,"invalid_temperature_target")
            return
        recommendation, native=bounded_command(
            desired,current_c,max_change_c=0.5,min_change_c=0.15,
            unit=unit,device_min=low,device_max=high,device_step=step,
        )
        if recommendation=="no_meaningful_change":
            self._status(area,"at_setpoint",entity_id=entity,mode=mode)
            return
        if recommendation!="command" or native is None:
            self._status(area,recommendation)
            return
        if not self.hass.services.has_service("climate","set_temperature"):
            self._status(area,"temperature_service_unavailable")
            return
        try:
            await asyncio.wait_for(
                self.hass.services.async_call("climate","set_temperature",
                    {"temperature":native},target={"entity_id":entity},
                    blocking=True),WRITE_TIMEOUT_S,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.exception("Secondary climate setpoint failed for %s",entity)
            self._pause(area,"climate_setpoint_write_failed")
            return
        self.expected[area]={"entity":entity,"mode":mode,"target":native,"when":now}
        self.last_write[area]=now
        self._save()
        self._status(area,"setpoint_commanded",entity_id=entity,
                     requested_c=desired,device_target=native)
