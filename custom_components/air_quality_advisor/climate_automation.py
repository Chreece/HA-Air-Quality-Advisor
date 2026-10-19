"""Independent opt-in per-room automatic climate control runtime.

Safe by construction:
* no implicit device targets; Home Assistant entity_id only;
* device strategy never stacks a PID on a device thermostat;
* switch/PWM modes require explicit equipment confirmation;
* open/unknown window and stale temperature data stop heating/cooling;
* no guessed occupancy/away from unavailable sensors;
* manual target/mode/relay changes pause until explicit user resume;
* persistent cycling state and manual latches, conservative startup warmup;
* no PWM on climate/heat-pump compressor entities.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
import logging
import math
import time
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .discovery import entity_area, is_stale, temperature_sensor_c
from .climate_policy import (
    DEFAULT_CLIMATE, merge_config, safe_num, choose_occupancy, choose_home,
    choose_profile, stable_absence, in_sleep_window, targets_for_profile,
    select_mode, hysteresis_demand, onoff_decision, pwm_decision,
    validate_climate_config,
)
from .pid_math import Memory, step, setpoint_c, bounded_command, target_from_unit, target_to_unit

_LOGGER = logging.getLogger(__name__)
TEMP_MAX_AGE_MINUTES = 10
DEFAULT_PRESENCE_AGE_MINUTES = 60
WRITE_TIMEOUT_SECONDS = 20
MANUAL_ACK_SECONDS = 120
SENSOR_COOLDOWN_SECONDS = 60


@dataclass
class ZoneRuntime:
    pid: Memory = field(default_factory=Memory)
    last_checked: float | None = None
    last_profile: str = "home"
    last_strategy: str | None = None
    last_mode: str = "idle"
    last_driven_mode: str = "idle"
    last_mode_transition: float | None = None
    vacancy_since: float | None = None
    away_since: float | None = None
    profile_override: str = "auto"
    last_demand_percent: float | None = None


class ClimateAutomationCoordinator:
    def __init__(self, hass: Any, entry_id: str, *, changed: Callable[[], None],
                 clock: Callable[[], float] | None = None) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self._changed = changed
        self._clock = clock or time.time
        self._started: float | None = None
        self._active = False
        self._store: Any | None = None
        self._storage_ready = False
        self._zones: dict[str, ZoneRuntime] = {}
        self._paused: dict[str, str] = {}
        self._expected: dict[str, dict[str, dict]] = {}
        self._output: dict[str, dict[str, dict]] = {}
        self.statuses: dict[str, dict] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def _snapshot(self) -> dict:
        states = {}
        for area, zone in self._zones.items():
            states[area] = {
                "last_mode": zone.last_mode,
                "last_driven_mode": zone.last_driven_mode,
                "last_mode_transition": zone.last_mode_transition,
                "last_profile": zone.last_profile,
                "profile_override": zone.profile_override,
            }
        return {
            "version": 1, "paused": self._paused,
            "expected": self._expected, "outputs": self._output, "zones": states,
        }

    async def async_start(self) -> None:
        self._active = True
        self._started = self._clock()
        try:
            from homeassistant.helpers.storage import Store
            self._store = Store(self.hass, 1, f"air_quality_advisor.climate_{self.entry_id}")
            data = await self._store.async_load()
        except Exception:
            _LOGGER.exception("Climate automation storage unavailable; automation remains disabled")
            return
        if isinstance(data, dict) and data.get("version") == 1:
            paused = data.get("paused", {})
            if isinstance(paused, dict):
                self._paused = {a:r for a,r in paused.items() if isinstance(a,str) and isinstance(r,str)}
            for attr, key in (("_expected","expected"),("_output","outputs")):
                candidate = data.get(key,{})
                if isinstance(candidate,dict):
                    clean={}
                    for a, entries in list(candidate.items())[:100]:
                        if not isinstance(a,str) or not isinstance(entries,dict):
                            continue
                        clean[a] = {entity:details for entity,details in entries.items()
                                    if isinstance(entity,str) and isinstance(details,dict)
                                    and (entity.startswith(("climate.","switch.","input_boolean.","number.","fan.","valve.")))}
                    setattr(self,attr,clean)
            zones = data.get("zones",{})
            if isinstance(zones,dict):
                for area, item in zones.items():
                    if not isinstance(area,str) or not isinstance(item,dict):
                        continue
                    runtime=ZoneRuntime()
                    runtime.last_mode = item.get("last_mode") if item.get("last_mode") in ("heat","cool","idle") else "idle"
                    runtime.last_driven_mode = item.get("last_driven_mode") if item.get("last_driven_mode") in ("heat","cool","idle") else "idle"
                    runtime.last_mode_transition = safe_num(item.get("last_mode_transition"),0,1e13)
                    runtime.last_profile = item.get("last_profile") if item.get("last_profile") in ("home","occupied","unoccupied","away","sleep") else "home"
                    runtime.profile_override = item.get("profile_override") if item.get("profile_override") in ("auto","home","occupied","unoccupied","away","sleep") else "auto"
                    self._zones[area]=runtime
        self._storage_ready=True

    async def async_stop(self) -> None:
        self._active=False
        tasks=tuple(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks,return_exceptions=True)
        self._tasks.clear()
        if self._storage_ready and self._store:
            try:
                await self._store.async_save(self._snapshot())
            except Exception:
                _LOGGER.exception("Climate automation state could not be saved")

    def _save(self) -> None:
        if self._storage_ready and self._store:
            self._store.async_delay_save(self._snapshot,2)

    def _status(self, area: str, status: str, **kw: Any) -> None:
        latest={"status":status,**kw}
        if self.statuses.get(area)==latest:
            return
        self.statuses[area]=latest
        if self._active:
            self._changed()

    def configured_statuses(self, configs: Any) -> dict[str,dict]:
        if not isinstance(configs,dict):
            return {}
        return {area:(self.statuses.get(area,{"status":"warming_up","mode":raw.get("operation")})
                      if isinstance(raw,dict) and raw.get("enabled")
                      else {"status":"disabled"})
                for area,raw in configs.items()}

    @staticmethod
    def explicit_targets(config: dict) -> tuple[str,...]:
        return tuple(dict.fromkeys(e for e in (
            config.get("climate_entity"),config.get("heat_entity"),config.get("cool_entity")
        ) if isinstance(e,str) and e))

    def selected_sources(self, settings: dict) -> set[str]:
        entities=set()
        for cfg in settings.values():
            if not isinstance(cfg,dict) or not cfg.get("enabled"):
                continue
            for ent in self.explicit_targets(cfg):
                entities.add(ent)
            if isinstance(cfg.get("temperature_entity"),str):
                entities.add(cfg["temperature_entity"])
            entities.update(x for x in cfg.get("occupancy_entities",[])
                            if isinstance(x,str))
            entities.update(x for x in cfg.get("home_entities",[])
                            if isinstance(x,str))
        return entities

    def _duplicates(self, settings: dict, legacy_pid: dict | None) -> set[str]:
        seen, duplicates=set(),set()
        for config in settings.values():
            if not isinstance(config,dict) or not config.get("enabled"):
                continue
            for entity in self.explicit_targets(config):
                if entity in seen:
                    duplicates.add(entity)
                seen.add(entity)
        if isinstance(legacy_pid,dict):
            for cfg in legacy_pid.values():
                if not isinstance(cfg,dict) or not cfg.get("enabled"):
                    continue
                targets=cfg.get("climate_entities") or ([cfg.get("climate_entity")] if cfg.get("climate_entity") else [])
                for entity in targets:
                    if entity in seen:
                        duplicates.add(entity)
        return duplicates

    def schedule(self, rooms: tuple, settings: dict,
                 *, legacy_pid: dict | None = None, initial: bool=False) -> None:
        if not self._active or not isinstance(settings,dict):
            return
        room_by_id={r.area_id:r for r in rooms}
        duplicates=self._duplicates(settings,legacy_pid)
        for area, raw in settings.items():
            if not isinstance(raw,dict) or not raw.get("enabled"):
                self._status(area,"disabled")
                continue
            if not self._storage_ready:
                self._status(area,"storage_unavailable")
                continue
            if area not in room_by_id:
                self._status(area,"room_missing")
                continue
            if any(entity in duplicates for entity in self.explicit_targets(raw)):
                self._status(area,"target_conflict")
                continue
            if area in self._paused:
                self._status(area,"paused",reason=self._paused[area])
                continue
            if initial:
                self._status(area,"startup_warmup")
                continue
            existing=self._tasks.get(area)
            if existing and not existing.done():
                continue
            now=self._clock()
            cfg=merge_config(raw)
            zone=self._zones.setdefault(area,ZoneRuntime())
            interval=60 if cfg["strategy"] in ("pwm","on_off") else cfg["sample_seconds"]
            if zone.last_checked is not None and now-zone.last_checked < interval*.85:
                continue
            task=self.hass.async_create_task(self._tick(area,room_by_id[area],cfg,now))
            self._tasks[area]=task
            def cleanup(t: asyncio.Task,area_id: str=area) -> None:
                if self._tasks.get(area_id) is t:
                    self._tasks.pop(area_id,None)
                if not t.cancelled():
                    try:
                        t.result()
                    except Exception:
                        _LOGGER.exception("Climate control task failed for %s",area_id)
                        self._status(area_id,"controller_exception")
            task.add_done_callback(cleanup)

    async def async_action(self, area: str, action: str, config: Any,
                           *, profile: str | None = None) -> dict:
        if not isinstance(config,dict) or not isinstance(config.get(area),dict) or not config[area].get("enabled"):
            return {"accepted":False,"reason":"room_not_enabled"}
        if not self._storage_ready:
            return {"accepted":False,"reason":"storage_unavailable"}
        if action not in ("pause","resume","reset","profile"):
            return {"accepted":False,"reason":"unsupported_action"}
        if action=="profile" and profile not in ("auto","home","occupied","unoccupied","away","sleep"):
            return {"accepted":False,"reason":"invalid_profile"}
        task=self._tasks.get(area)
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
        zone=self._zones.setdefault(area,ZoneRuntime())
        if action=="pause":
            self._paused[area]="explicit_manual_pause"
        elif action=="resume":
            self._paused.pop(area,None)
            self._expected.pop(area,None)
            zone.pid=Memory()
            zone.last_checked=None
            self._started=self._clock()
        elif action=="reset":
            self._paused[area]="reset_requires_resume"
            self._expected.pop(area,None)
            self._output.pop(area,None)
            self._zones[area]=ZoneRuntime()
        elif action=="profile":
            zone.profile_override=profile
            zone.pid=Memory()
        self._save()
        self._status(area,"paused" if area in self._paused else "warming_up",
                     reason=self._paused.get(area),profile_override=zone.profile_override)
        return {"accepted":True,"area":area,"action":action,"profile":profile}

    async def _pause(self,area: str,reason: str) -> None:
        self._paused[area]=reason
        self._save()
        self._status(area,"paused",reason=reason)

    def _states_for_occupancy(self,area: str, cfg: dict) -> list[bool|None]:
        ids=cfg.get("occupancy_entities") or []
        if not ids and cfg.get("auto_discover_occupancy"):
            ids=[s.entity_id for s in self.hass.states.async_all("binary_sensor")
                 if entity_area(self.hass,s.entity_id)==area
                 and str(s.attributes.get("device_class","")).lower() in ("occupancy","presence")]
        states=[]
        for entity in ids:
            state=self.hass.states.get(entity)
            if state is None or is_stale(state,DEFAULT_PRESENCE_AGE_MINUTES):
                states.append(None)
            elif str(state.state).lower()=="on":
                states.append(True)
            elif str(state.state).lower()=="off":
                states.append(False)
            else:
                states.append(None)
        return states

    def _states_for_home(self,cfg: dict) -> list[bool|None]:
        states=[]
        for entity in cfg.get("home_entities") or []:
            s=self.hass.states.get(entity)
            if s is None or str(s.state).lower() in ("unknown","unavailable",""):
                states.append(None)
            elif entity.startswith(("person.","device_tracker.")):
                # Person in another zone is not at home.
                states.append(str(s.state).lower()=="home" if str(s.state).lower()!="unknown" else None)
            elif entity.startswith("binary_sensor."):
                states.append(True if s.state=="on" else False if s.state=="off" else None)
            else:
                states.append(None)
        return states

    def _profile(self,area: str,cfg: dict,now: float) -> tuple[str,str,str]:
        zone=self._zones.setdefault(area,ZoneRuntime())
        if zone.profile_override!="auto":
            return zone.profile_override,"manual_override","manual_override"
        room=choose_occupancy(self._states_for_occupancy(area,cfg))
        home=choose_home(self._states_for_home(cfg))
        if room!="unoccupied":
            zone.vacancy_since=None
        elif zone.vacancy_since is None:
            zone.vacancy_since=now
        if home!="away":
            zone.away_since=None
        elif zone.away_since is None:
            zone.away_since=now
        if room=="unoccupied":
            room=stable_absence(room,zone.vacancy_since,now,cfg["vacancy_delay_seconds"])
        if home=="away":
            home=stable_absence(home,zone.away_since,now,cfg["away_delay_seconds"])
        tz_name=getattr(getattr(self.hass,"config",None),"time_zone",None) or "UTC"
        try:
            local=datetime.fromtimestamp(now,ZoneInfo(tz_name))
        except (ZoneInfoNotFoundError,ValueError):
            local=datetime.fromtimestamp(now)
        sleep=bool(cfg.get("sleep_enabled")) and in_sleep_window(
            local.strftime("%H:%M"),cfg["sleep_start"],cfg["sleep_end"],
        )
        return choose_profile(room,home,sleeping=sleep),room,home

    async def _service(self,area: str, domain: str,action: str,entity: str,payload: dict) -> bool:
        if not self._active or area in self._paused:
            return False
        if entity_area(self.hass,entity) not in (None,area):
            await self._pause(area,"device_moved_outside_room")
            return False
        if not self.hass.services.has_service(domain,action):
            await self._pause(area,"service_unavailable")
            return False
        try:
            await asyncio.wait_for(
                self.hass.services.async_call(
                    domain,action,payload,target={"entity_id":entity},blocking=True,
                ),timeout=WRITE_TIMEOUT_SECONDS,
            )
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.exception("Climate command failure %s.%s %s",domain,action,entity)
            await self._pause(area,"climate_service_failure")
            return False

    def _current(self,area: str,entity: str) -> tuple[Any,str]:
        if not isinstance(entity,str):
            return None,"not_configured"
        state=self.hass.states.get(entity)
        if state is None or str(state.state).lower() in ("unknown","unavailable",""):
            return None,"unavailable"
        if entity_area(self.hass,entity) not in (None,area):
            return None,"wrong_room"
        return state,"ready"

    def _check_expected(self,area: str,entity: str,state: Any,now: float) -> str:
        expected=self._expected.get(area,{}).get(entity)
        if not expected:
            return "no_expected_write"
        last=expected.get("when",0)
        field=expected.get("field")
        recorded=expected.get("value")
        if field=="temperature":
            observed=safe_num(state.attributes.get("temperature"),-30,150)
            step_size=safe_num(state.attributes.get("target_temp_step"),0.1,10) or .5
            match=observed is not None and abs(observed-recorded)<=max(.1,step_size*.52)
        elif field=="mode":
            match=str(state.state).lower()==recorded
        elif field=="relay":
            match=str(state.state).lower()==("on" if recorded else "off")
        elif field=="percent":
            observed=safe_num(state.state if entity.startswith("number.") else state.attributes.get("percentage"),0,100)
            match=observed is not None and abs(observed-recorded)<=2
        else:
            match=False
        if match:
            return "acknowledged"
        return "pending_ack" if now-last<MANUAL_ACK_SECONDS else "manual_override"

    def _record(self,area: str,entity: str,field: str,value: Any,now: float) -> None:
        self._expected.setdefault(area,{})[entity]={"field":field,"value":value,"when":now}
        self._save()

    async def _relay_command(self,area: str,entity: str,wanted: bool,now: float,
                             *, force_off: bool=False) -> bool:
        state,status=self._current(area,entity)
        if status!="ready":
            self._status(area,"actuator_unavailable",entity=entity)
            return False
        domain=entity.split(".",1)[0]
        if domain not in ("switch","input_boolean"):
            self._status(area,"unsupported_relay_type",entity=entity)
            return False
        actual=str(state.state).lower()
        if actual not in ("on","off"):
            self._status(area,"actuator_state_unknown",entity=entity)
            return False
        if actual==("on" if wanted else "off"):
            return True
        # Do not override a manually energized relay at first startup.
        owned=self._output.get(area,{}).get(entity,{})
        if actual=="on" and not owned.get("on") and not force_off:
            await self._pause(area,"external_actuator_on")
            return False
        if not self._active:
            return False
        if await self._service(area,domain,"turn_on" if wanted else "turn_off",entity,{}):
            self._output.setdefault(area,{})[entity]={"on":wanted,"when":now}
            self._record(area,entity,"relay",wanted,now)
            return True
        return False

    async def _safe_off(self,area: str,cfg: dict,now: float,reason: str) -> None:
        if cfg["strategy"] not in ("pwm","on_off"):
            self._status(area,reason)
            return
        # Only de-energize switch outputs that this integration last turned on.
        for entity in self.explicit_targets(cfg):
            recorded=self._output.get(area,{}).get(entity)
            if recorded and recorded.get("on") and entity.startswith(("switch.","input_boolean.")):
                await self._relay_command(area,entity,False,now,force_off=True)
        if area not in self._paused:
            self._status(area,reason)

    async def _climate_mode(self,area: str,entity: str,mode: str,cfg: dict,now: float) -> bool:
        state,status=self._current(area,entity)
        if status!="ready":
            self._status(area,"climate_unavailable")
            return False
        if state.state==mode:
            return True
        if not cfg.get("allow_hvac_mode_change"):
            self._status(area,"manual_hvac_mode_required",requested_mode=mode)
            return False
        modes=state.attributes.get("hvac_modes") or []
        if mode not in modes:
            self._status(area,"hvac_mode_not_supported",requested_mode=mode)
            return False
        if await self._service(area,"climate","set_hvac_mode",entity,{"hvac_mode":mode}):
            self._record(area,entity,"mode",mode,now)
            return False  # Wait until mode is acknowledged before setting target.
        return False

    async def _device_control(self,area: str,cfg: dict,mode: str,target: float,
                              heat: float,cool: float,now: float,
                              *, pid_demand: float|None=None,
                              measured: float, profile: str) -> None:
        entity=cfg.get("climate_entity")
        state,status=self._current(area,entity)
        if status!="ready" or not entity.startswith("climate."):
            self._status(area,"climate_unavailable")
            return
        match=self._check_expected(area,entity,state,now)
        if match=="manual_override":
            await self._pause(area,"manual_thermostat_override")
            return
        if match=="pending_ack":
            self._status(area,"waiting_device_ack")
            return
        if mode=="idle":
            if cfg.get("allow_turn_off") and cfg.get("allow_hvac_mode_change"):
                await self._climate_mode(area,entity,"off",cfg,now)
            self._status(area,"deadband_idle")
            return
        if not await self._climate_mode(area,entity,mode,cfg,now):
            return
        attrs=state.attributes
        if not int(attrs.get("supported_features",0) or 0)&1:
            self._status(area,"target_temperature_unsupported")
            return
        if str(attrs.get("preset_mode") or "").lower() not in ("","none","manual"):
            self._status(area,"external_thermostat_preset")
            return
        unit=attrs.get("temperature_unit")
        device=attrs.get("temperature")
        actual=target_from_unit(device,unit)
        min_native=safe_num(attrs.get("min_temp"),-40,140)
        max_native=safe_num(attrs.get("max_temp"),-40,140)
        quant=safe_num(attrs.get("target_temp_step"),.1,10)
        if None in (actual,min_native,max_native) or unit not in ("°C","C","°F","F"):
            self._status(area,"device_temperature_capability_unknown")
            return
        device_step=quant or (.5 if unit in ("°C","C") else 1)
        if pid_demand is None:
            destination=target
        else:
            destination=setpoint_c(target,pid_demand,mode,cfg["offset_c"],cfg["min_setpoint_c"],cfg["max_setpoint_c"])
        if destination is None:
            self._status(area,"invalid_setpoint")
            return
        state_action, native=bounded_command(destination,actual,
                                             max_change_c=cfg["max_change_c"],
                                             min_change_c=cfg["min_change_c"],
                                             unit=unit,device_min=min_native,
                                             device_max=max_native,device_step=device_step)
        if state_action=="no_meaningful_change":
            self._status(area,"at_target",mode=mode,target_c=round(target,2),
                         measured_c=round(measured,2),profile=profile)
            return
        if state_action!="command":
            self._status(area,state_action)
            return
        if await self._service(area,"climate","set_temperature",entity,{"temperature":native}):
            self._record(area,entity,"temperature",native,now)
            self._status(area,"controlling",mode=mode,profile=profile,
                         target_c=round(target,2),measured_c=round(measured,2),
                         requested_setpoint=native,demand_percent=pid_demand)

    async def _power_control(self,area: str,cfg: dict,mode: str,target: float,
                             now: float,zone: ZoneRuntime,
                             demand_percent: float|None, measured: float,
                             profile: str) -> None:
        strategy=cfg["strategy"]
        heat,cool=cfg.get("heat_entity"),cfg.get("cool_entity")
        active=heat if mode=="heat" else cool if mode=="cool" else None
        inactive=cool if mode=="heat" else heat
        # Ensure the opposite relay is off before activating a new channel.
        if inactive and inactive!=active:
            state,status=self._current(area,inactive)
            if status=="ready" and state.state=="on":
                if not await self._relay_command(area,inactive,False,now,force_off=True):
                    self._status(area,"opposing_actuator_not_off")
                    return
                self._status(area,"cooldown_after_opposite_off")
                return
        if mode=="idle" or not active:
            if active is None and mode in ("heat","cool"):
                self._status(area,"missing_mode_actuator",mode=mode)
                return
            await self._safe_off(area,cfg,now,"idle_or_no_actuator")
            return
        state,status=self._current(area,active)
        if status!="ready":
            self._status(area,"actuator_unavailable",entity=active)
            return
        domain=active.split(".",1)[0]
        if strategy=="proportional":
            if domain not in ("number","fan"):
                self._status(area,"unsupported_proportional_actuator")
                return
            if demand_percent is None:
                self._status(area,"demand_not_ready")
                return
            wanted=max(cfg["output_min"],min(cfg["output_max"],demand_percent))
            if domain=="number":
                lo=safe_num(state.attributes.get("min"),0,100)
                hi=safe_num(state.attributes.get("max"),0,100)
                if lo is None or hi is None or hi<=lo:
                    self._status(area,"number_range_unavailable")
                    return
                current=safe_num(state.state,lo,hi)
                target_native=min(hi,max(lo,lo+(hi-lo)*wanted/100))
                svc="set_value";payload={"value":round(target_native,2)}
            else:
                current=safe_num(state.attributes.get("percentage"),0,100)
                svc="set_percentage";payload={"percentage":round(wanted)}
                target_native=payload["percentage"]
            if current is None:
                self._status(area,"current_output_unknown")
                return
            check=self._check_expected(area,active,state,now)
            if check=="manual_override":
                await self._pause(area,"manual_output_change")
                return
            if check=="pending_ack":
                return
            # Bounded percentage change per update.
            target_native=max(current-20,min(current+20,target_native))
            payload[next(iter(payload))]=round(target_native,2)
            if abs(target_native-current)<2:
                self._status(area,"proportional_at_target",target=round(target_native,1))
                return
            if await self._service(area,domain,svc,active,payload):
                self._record(area,active,"percent",target_native,now)
                self._status(area,"controlling",mode=mode,profile=profile,
                             demand_percent=round(wanted,1),actuator=active)
            return
        if strategy=="pwm" and domain not in ("switch","input_boolean"):
            self._status(area,"pwm_requires_confirmed_switch")
            return
        if strategy=="on_off" and domain not in ("switch","input_boolean","climate"):
            self._status(area,"unsupported_onoff_actuator")
            return
        if domain=="climate":
            # On/off climate support only through built-in HVAC mode machinery,
            # with explicit permission, never PWM over a compressor interface.
            if not cfg.get("allow_hvac_mode_change"):
                self._status(area,"climate_mode_switch_permission_required")
                return
            actual=state.state
            if actual not in ("off","heat","cool"):
                self._status(area,"unsupported_climate_state")
                return
            desired_on=hysteresis_demand(round(measured,2),target,mode,
                                         was_on=(actual==mode),hysteresis_c=cfg["hysteresis_c"])
            recorded=self._output.setdefault(area,{}).get(active)
            if recorded is None:
                if actual!="off":
                    await self._pause(area,"external_climate_already_running")
                    return
                self._output[area][active]={"on":False,"when":now}
                self._save()
                self._status(area,"initial_off_lockout",entity=active)
                return
            elapsed=now-recorded["when"]
            decision=onoff_decision(desired_on,actual==mode,
                                    seconds_since_switch=elapsed,
                                    min_on_seconds=cfg["min_on_seconds"],
                                    min_off_seconds=cfg["min_off_seconds"],
                                    max_on_seconds=cfg["max_on_seconds"])
            if decision.status=="change" or decision.status=="max_on_cutoff":
                new_mode=mode if decision.desired_on else "off"
                if state.state!=new_mode and (
                    cfg["allow_hvac_mode_change"] and
                    new_mode in (state.attributes.get("hvac_modes") or [])
                ):
                    if await self._service(area,"climate","set_hvac_mode",active,{"hvac_mode":new_mode}):
                        self._record(area,active,"mode",new_mode,now)
                        self._output.setdefault(area,{})[active]={"on":decision.desired_on,"when":now}
                        self._save()
                else:
                    self._status(area,"climate_hvac_mode_unavailable")
                    return
            self._status(area,decision.status,mode=mode,profile=profile)
            return
        actual=str(state.state).lower()
        if actual not in ("on","off"):
            self._status(area,"unknown_relay_state")
            return
        match=self._check_expected(area,active,state,now)
        if match=="manual_override":
            await self._pause(area,"manual_actuator_change")
            return
        if match=="pending_ack":
            self._status(area,"waiting_actuator_ack")
            return
        if strategy=="on_off":
            desired=hysteresis_demand(round(measured,2),target,mode,was_on=(actual=="on"),
                                      hysteresis_c=cfg["hysteresis_c"])
        else:
            if demand_percent is None:
                self._status(area,"pwm_waiting_pid")
                return
            cycle_start=zone.last_mode_transition if zone.last_mode_transition is not None else now
            pwm=pwm_decision(demand_percent,now,cycle_start,
                             period_seconds=cfg["pwm_period_seconds"],
                             min_pulse_seconds=cfg["pwm_min_pulse_seconds"])
            if pwm["status"]!="ready":
                self._status(area,"invalid_pwm_cycle")
                return
            desired=pwm["desired_on"]
        last=self._output.get(area,{}).get(active)
        if last is None:
            if actual=="on":
                await self._pause(area,"external_actuator_already_on")
                return
            self._output.setdefault(area,{})[active]={"on":False,"when":now}
            self._save()
            self._status(area,"initial_off_lockout",entity=active)
            return
        elapsed=now-last["when"]
        edge=onoff_decision(desired,actual=="on",seconds_since_switch=elapsed,
                            min_on_seconds=cfg["min_on_seconds"],
                            min_off_seconds=cfg["min_off_seconds"],
                            max_on_seconds=cfg["max_on_seconds"])
        if edge.status=="change" or edge.status=="max_on_cutoff":
            await self._relay_command(area,active,edge.desired_on,now)
        self._status(area,edge.status,mode=mode,profile=profile,
                     measured_c=round(measured,2),target_c=round(target,2),
                     demand_percent=demand_percent,actuator=active)

    async def _tick(self,area: str,room: Any,cfg: dict,now: float) -> None:
        if not self._active or not self._storage_ready or area in self._paused:
            return
        ok,why=validate_climate_config(cfg)
        if not ok:
            self._status(area,"invalid_configuration",reason=why)
            return
        zone=self._zones.setdefault(area,ZoneRuntime())
        if zone.last_strategy!=cfg["strategy"]:
            zone.pid=Memory()
            zone.last_strategy=cfg["strategy"]
        zone.last_checked=now
        if self._started is None or now-self._started < max(120,cfg["sample_seconds"]):
            await self._safe_off(area,cfg,now,"startup_warmup")
            return
        if cfg.get("pause_on_window_open",True) and (
            not room.windows or any(w.opened is not False for w in room.windows)
        ):
            await self._safe_off(area,cfg,now,"window_open_or_unknown")
            return
        sensor=cfg.get("temperature_entity")
        if not isinstance(sensor,str) or not sensor.startswith("sensor."):
            self._status(area,"temperature_sensor_required")
            return
        if entity_area(self.hass,sensor) not in (None,area):
            self._status(area,"temperature_sensor_wrong_room")
            return
        measured=temperature_sensor_c(self.hass,sensor,TEMP_MAX_AGE_MINUTES)
        if measured is None or not math.isfinite(measured) or measured < -10 or measured > 50:
            await self._safe_off(area,cfg,now,"temperature_missing_or_stale")
            return
        # Room temperatures stay local to each concurrent controller task.
        profile,room_presence,home_presence=self._profile(area,cfg,now)
        try:
            heat,cool=targets_for_profile(cfg,profile)
        except (ValueError,TypeError):
            self._status(area,"invalid_profile_targets")
            return
        if zone.last_profile!=profile:
            zone.pid=Memory()
            zone.last_profile=profile
        previous=zone.last_mode
        elapsed=now-zone.last_mode_transition if zone.last_mode_transition is not None else None
        decision=select_mode(measured,heat,cool,cfg["operation"],
                             hysteresis_c=cfg["hysteresis_c"],
                             previous_mode=previous,
                             seconds_since_mode_change=elapsed,
                             min_mode_seconds=cfg["min_mode_seconds"])
        if decision.status=="invalid":
            self._status(area,"invalid_mode_target")
            return
        mode=decision.mode
        # Off dwell required between heating and cooling, even after going idle.
        if (mode in ("heat","cool") and zone.last_driven_mode not in ("idle",mode)
                and (zone.last_mode_transition is None or now-zone.last_mode_transition < cfg["min_mode_seconds"])):
            mode="idle"
        if mode!=zone.last_mode:
            zone.last_mode=mode
            zone.last_mode_transition=now
            zone.pid=Memory()
            self._save()
        if mode in ("heat","cool"):
            zone.last_driven_mode=mode
        if cfg["strategy"] in ("device","setpoint_pid"):
            target=heat if mode=="heat" else cool
            demand=None
            if cfg["strategy"]=="setpoint_pid" and mode!="idle":
                pid=step(measured,target,now,mode,cfg["kp"],cfg["ki"],cfg["kd"],
                         cfg["sample_seconds"],zone.pid)
                zone.pid=pid.memory
                if pid.status!="ready":
                    self._status(area,"pid_"+pid.status,mode=mode,profile=profile,
                                 measured_c=round(measured,2),target_c=target)
                    return
                demand=pid.demand_percent
            await self._device_control(area,cfg,mode,target,heat,cool,now,
                                       pid_demand=demand,measured=measured,profile=profile)
        else:
            target=heat if mode=="heat" else cool
            demand=None
            if cfg["strategy"] in ("pwm","proportional") and mode!="idle":
                pid=step(measured,target,now,mode,cfg["kp"],cfg["ki"],cfg["kd"],
                         cfg["sample_seconds"],zone.pid)
                zone.pid=pid.memory
                if pid.status not in ("ready","waiting_sample"):
                    self._status(area,"pid_"+pid.status,profile=profile)
                if pid.status=="ready":
                    demand=pid.demand_percent
                    zone.last_demand_percent=demand
                elif pid.status=="waiting_sample":
                    demand=zone.last_demand_percent
            await self._power_control(area,cfg,mode,target,now,zone,demand,
                                      measured=measured,profile=profile)
        if self.statuses.get(area,{}).get("status")!="paused":
            self.statuses[area].update({
                "profile":profile,"room_occupancy":room_presence,"home_presence":home_presence,
                "heat_target_c":heat,"cool_target_c":cool,"operation":cfg["operation"],
                "strategy":cfg["strategy"],
            })
            self._changed()
