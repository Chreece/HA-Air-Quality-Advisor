"""Capability-verified slow-load relay/PWM and proportional room climate drivers.

A switch is NOT inherently an HVAC-safe actuator. Explicit user attestation
that these are non-compressor, independently protected thermal actuators is
required before any switching. This module never issues climate.set_hvac_mode.
It never energizes an unknown, stale, wrongly assigned or unacknowledged output.
"""
from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from .climate_strategy import guarded_transition, pwm_slot, relay_demand
from .discovery import entity_area, temperature_sensor_c
from .pid_math import Memory, finite, step

_LOGGER = logging.getLogger(__name__)
MAX_SENSOR_AGE_MINUTES = 10
STARTUP_SETTLING_SECONDS = 300
WRITE_TIMEOUT_SECONDS = 15
ACK_GRACE_SECONDS = 90
MAX_DIRECT_OUTPUTS = 2


@dataclass
class RoomCycle:
    pid: Memory = field(default_factory=Memory)
    pid_percent: float | None = None
    mode: str | None = None
    last_sample: float | None = None


class DirectClimateControl:
    """Fail-closed actuator ownership, bounded writes and persistent pauses."""

    def __init__(self, hass: Any, entry_id: str, *,
                 clock: Callable[[], float] | None = None,
                 changed: Callable[[], None] | None = None):
        self.hass, self.entry_id = hass, entry_id
        self.clock = clock or time.time
        self.changed = changed or (lambda: None)
        self.statuses: dict[str, dict] = {}
        self.paused: dict[str, str] = {}
        self.expected: dict[str, dict] = {}
        self.transitions: dict[str, dict] = {}
        self.mode_changed: dict[str, float] = {}
        self._rooms: dict[str, RoomCycle] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._store = None
        self._ready = False
        self._active = False
        self._started: float | None = None

    def _snapshot(self) -> dict:
        return {"version": 1, "paused": self.paused,
                "expected": self.expected, "transitions": self.transitions,
                "mode_changed": self.mode_changed}

    def _persist(self) -> None:
        if self._store is not None:
            self._store.async_delay_save(self._snapshot, 2)

    def _status(self, area: str, state: str, **details: Any) -> None:
        current = {"status": state, **details}
        if self.statuses.get(area) != current:
            self.statuses[area] = current
            if self._active:
                self.changed()

    async def async_start(self) -> None:
        self._active = True
        self._started = self.clock()
        try:
            from homeassistant.helpers.storage import Store
            self._store = Store(self.hass, 1, f"air_quality_advisor.direct_{self.entry_id}")
            saved = await self._store.async_load()
        except Exception:
            _LOGGER.exception("Direct actuator storage unavailable; output writes disabled")
            return
        if isinstance(saved, dict) and saved.get("version") == 1:
            pauses = saved.get("paused", {})
            self.paused = {k: v for k, v in pauses.items()
                           if isinstance(k, str) and isinstance(v, str)} if isinstance(pauses, dict) else {}
            for name in ("expected", "transitions"):
                incoming = saved.get(name, {})
                if isinstance(incoming, dict):
                    setattr(self, name, {k: v for k, v in incoming.items()
                                          if isinstance(k, str) and isinstance(v, dict)})
            changes = saved.get("mode_changed", {})
            if isinstance(changes, dict):
                self.mode_changed = {k:float(v) for k,v in changes.items()
                                     if isinstance(k,str) and finite(v,0,1e13) is not None}
        self._ready = True

    async def async_stop(self) -> None:
        self._active = False
        running = tuple(self._tasks.values())
        for task in running:
            task.cancel()
        if running:
            await asyncio.gather(*running, return_exceptions=True)
        self._tasks.clear()
        if self._ready and self._store is not None:
            try:
                await self._store.async_save(self._snapshot())
            except Exception:
                _LOGGER.exception("Unable to save direct actuator state")

    def _pause(self, area: str, reason: str) -> None:
        self.paused[area] = reason
        self._rooms.pop(area, None)
        self._persist()
        self._status(area, "paused", reason=reason)

    async def command(self, area: str, action: str, configurations: dict) -> dict:
        if action not in ("pause", "resume"):
            return {"accepted":False, "reason":"unknown_action"}
        settings = configurations.get(area) if isinstance(configurations,dict) else None
        if not isinstance(settings,dict) or settings.get("enabled") is not True:
            return {"accepted":False,"reason":"room_not_enabled"}
        if not self._ready:
            return {"accepted":False,"reason":"storage_not_ready"}
        task = self._tasks.get(area)
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
        if action=="pause":
            self._pause(area,"user_paused")
        else:
            self.paused.pop(area,None)
            self._rooms.pop(area,None)
            self.expected.pop(area,None)
            self._started=self.clock()
            self._persist()
            self._status(area,"startup_warmup")
        return {"accepted":True,"area":area,"action":action}

    @staticmethod
    def _entities(settings: dict) -> list[str]:
        heat=settings.get("heat_actuator")
        cool=settings.get("cool_actuator")
        return list(dict.fromkeys(v for v in (heat,cool)
                                  if isinstance(v,str) and v))

    def schedule(self, config: dict, plans: dict, *,
                 pid_rooms: dict | None = None,
                 native_rooms: dict | None = None) -> None:
        if not self._active or not isinstance(config, dict):
            return
        owner_counts: dict[str,int] = {}
        for settings in config.values():
            if isinstance(settings,dict) and settings.get("enabled") and settings.get("allow_actuation"):
                for entity in self._entities(settings):
                    owner_counts[entity]=owner_counts.get(entity,0)+1
        # An external PID/native thermostat cannot own the same selected output.
        native_targets = {v.get("climate_entity") for v in (native_rooms or {}).values()
                          if isinstance(v,dict) and v.get("enabled")}
        active_pid_targets = {t for v in (pid_rooms or {}).values()
                              if isinstance(v,dict) and v.get("enabled")
                              for t in v.get("climate_entities",[]) if isinstance(t,str)}
        now = self.clock()
        for area, raw in config.items():
            if not isinstance(raw,dict) or not raw.get("enabled"):
                continue
            if raw.get("controller") not in ("on_off","pwm","proportional"):
                self._status(area,"not_direct_strategy")
                continue
            if not raw.get("allow_actuation") or not raw.get("direct_hardware_confirmed"):
                self._status(area,"advisory_only",reason="actuator_attestation_required")
                continue
            if not self._ready:
                self._status(area,"storage_unavailable")
                continue
            if area in self.paused:
                self._status(area,"paused",reason=self.paused[area])
                continue
            entities=self._entities(raw)
            if not entities or len(entities)>MAX_DIRECT_OUTPUTS or any(
                owner_counts.get(x)!=1 or x in native_targets or x in active_pid_targets
                for x in entities
            ):
                self._status(area,"conflicting_or_missing_actuator")
                continue
            if not isinstance(plans.get(area),dict):
                self._status(area,"no_room_plan")
                continue
            if now-(self._started if self._started is not None else now)<STARTUP_SETTLING_SECONDS:
                self._status(area,"startup_warmup")
                continue
            running=self._tasks.get(area)
            if running is not None and not running.done():
                continue
            task=self.hass.async_create_task(self._tick(area,raw,plans[area],now))
            self._tasks[area]=task
            def done(future: asyncio.Task, key: str=area)->None:
                if self._tasks.get(key) is future:
                    self._tasks.pop(key,None)
                if not future.cancelled():
                    try:
                        future.result()
                    except Exception:
                        _LOGGER.exception("Unhandled direct climate error in %s",key)
                        self._pause(key,"controller_exception")
            task.add_done_callback(done)

    async def _send(self, area: str, entity: str, state: bool | float,
                    *, percentage: bool=False, now:float)->bool:
        domain,service=(("number","set_value") if percentage else
                        ("switch","turn_on" if state is True else "turn_off"))
        value={"value":float(state)} if percentage else {}
        try:
            if not self.hass.services.has_service(domain,service):
                raise RuntimeError(f"{domain}.{service} not available")
            await asyncio.wait_for(self.hass.services.async_call(
                domain,service,value,target={"entity_id":entity},blocking=True
            ),timeout=WRITE_TIMEOUT_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.exception("Direct actuator command failed: %s",entity)
            self._pause(area,"service_failed_or_timeout")
            return False
        self.expected[entity]={"state":state,"when":now}
        if not percentage:
            self.transitions[entity]={"state":state,"when":now}
        self._persist()
        return True

    async def _tick(self, area: str, cfg: dict, report: dict, now: float) -> None:
        if not self._active or area in self.paused:
            return
        strategy=cfg.get("controller")
        if strategy not in ("on_off","pwm","proportional"):
            self._status(area,"unsupported_strategy")
            return
        mode=report.get("mode")
        # A held or failed plan never issues an ON command.
        can_run=(report.get("status")=="ready" and report.get("window_safe") is True
                 and mode in ("heat","cool"))
        source=cfg.get("temperature_entity")
        if not isinstance(source,str) or entity_area(self.hass,source) != area:
            self._status(area,"temperature_source_missing_or_wrong_area")
            return
        temp=temperature_sensor_c(self.hass,source,MAX_SENSOR_AGE_MINUTES)
        if temp is None:
            can_run=False
            self._status(area,"stale_temperature")
        heat=cfg.get("heat_actuator")
        cool=cfg.get("cool_actuator")
        active=heat if mode=="heat" else cool if mode=="cool" else None
        all_entities=self._entities(cfg)
        if not all_entities:
            self._status(area,"no_actuator")
            return
        suffix="number." if strategy=="proportional" else "switch."
        if any(not e.startswith(suffix) or entity_area(self.hass,e)!=area for e in all_entities):
            self._status(area,"actuator_wrong_domain_or_area")
            return
        if can_run and active not in all_entities:
            self._status(area,"mode_has_no_verified_actuator")
            return
        measured:dict[str,bool|float]={}
        for e in all_entities:
            state=self.hass.states.get(e)
            if state is None or str(state.state).lower() in ("unknown","unavailable"):
                self._status(area,"actuator_unknown_or_unavailable",entity=e)
                return
            if strategy=="proportional":
                value=finite(state.state,0,100)
                attrs=state.attributes
                if (value is None or str(attrs.get("unit_of_measurement"))!="%"
                    or finite(attrs.get("min"),0,100)!=0.0
                    or finite(attrs.get("max"),0,100)!=100.0
                    or finite(attrs.get("step"),0.1,10) is None):
                    self._status(area,"unverified_proportional_range",entity=e)
                    return
                observed=value
            else:
                if state.state not in ("on","off"):
                    self._status(area,"actuator_not_binary",entity=e)
                    return
                observed=state.state=="on"
            measured[e]=observed
            acknowledgement=self.expected.get(e)
            if acknowledgement is not None and acknowledgement.get("state") != observed:
                sent=finite(acknowledgement.get("when"),0,1e13)
                if sent is not None and 0 <= now-sent < ACK_GRACE_SECONDS:
                    self._status(area,"waiting_for_output_ack",entity=e)
                    return
                self._pause(area,"manual_override_or_unacknowledged_output")
                return
            if acknowledgement is None and (observed is True or
                    (strategy=="proportional" and observed>0)):
                self._pause(area,"unowned_active_output")
                return
        if not can_run:
            # Fail-safe OFF is allowed for expressly attested non-compressor
            # actuators only; never try to turn equipment on with missing data.
            for e,observed in measured.items():
                if (observed is True or
                    (strategy=="proportional" and observed>0)):
                    if not await self._send(area,e,0.0 if strategy=="proportional" else False,
                                            percentage=strategy=="proportional",now=now):
                        return
            self._status(area,"safe_off",reason=report.get("reason","no_heat_cool_demand"))
            return
        last_mode=self._rooms.get(area,RoomCycle()).mode
        if last_mode not in (None,mode):
            self._rooms.pop(area,None)
            self.mode_changed[area]=now
            self._persist()
        mode_dwell=finite(cfg.get("mode_dwell_s",900),300,7200)
        if mode_dwell is None:
            self._status(area,"invalid_mode_dwell")
            return
        if now-self.mode_changed.get(area,self._started if self._started is not None else now)<mode_dwell:
            self._status(area,"mode_transfer_dwell")
            return
        # Exclusivity: opposing output is stopped and confirmed OFF
        # before another side may turn ON, never both simultaneously.
        opposite=cool if mode=="heat" else heat
        if opposite and (measured.get(opposite) is True or
                         (strategy=="proportional" and measured.get(opposite,0)>0)):
            if not await self._send(area,opposite,0.0 if strategy=="proportional" else False,
                                    percentage=strategy=="proportional",now=now):
                return
            self.mode_changed[area]=now
            self._persist()
            self._status(area,"interlock_wait_opposite_off")
            return
        if opposite and opposite in self.expected and (
                self.expected[opposite].get("state") is True or
                (strategy=="proportional" and self.expected[opposite].get("state",0)>0)):
            self._status(area,"interlock_unconfirmed")
            return
        cycle=self._rooms.setdefault(area,RoomCycle(mode=mode))
        if cycle.mode!=mode:
            cycle=RoomCycle(mode=mode)
            self._rooms[area]=cycle
        target=finite(report.get("temperature_target_c"),5,36)
        if target is None:
            self._status(area,"no_target")
            return
        if strategy=="on_off":
            desired=relay_demand(temp,target,mode,
                cold_tolerance_c=float(cfg.get("cold_tolerance_c",.3)),
                hot_tolerance_c=float(cfg.get("hot_tolerance_c",.3)),
                previous_on=measured[active])
            if desired is None:
                self._status(area,"invalid_hysteresis")
                return
        else:
            sample=float(cfg.get("sample_seconds",300))
            if not 120<=sample<=3600:
                self._status(area,"invalid_pid_sample")
                return
            calc=step(temp,target,now,mode,
                float(cfg.get("kp",18)),float(cfg.get("ki",.12)),
                float(cfg.get("kd",0)),sample,cycle.pid)
            if calc.status in ("initializing","gap_reset"):
                cycle.pid=calc.memory
                self._status(area,"waiting_for_pid_samples")
                return
            if calc.status not in ("ready","waiting_sample"):
                self._status(area,"pid_not_ready",reason=calc.status)
                return
            if calc.status=="ready":
                cycle.pid=calc.memory
                cycle.pid_percent=calc.demand_percent
            demand=cycle.pid_percent
            if demand is None:
                self._status(area,"insufficient_pid_history")
                return
            if strategy=="pwm":
                period=float(cfg.get("pwm_period_s",900))
                if not 300<=period<=7200:
                    self._status(area,"invalid_pwm_period")
                    return
                # A deterministic common anchor avoids an arbitrary restart
                # pulse phase, while still requiring startup settling.
                phase_anchor=math.floor(now/period)*period
                pwm_state,desired=pwm_slot(
                    demand,period_s=period,now_s=now,anchor_s=phase_anchor,
                    min_on_s=float(cfg.get("min_on_s",120)),
                    min_off_s=float(cfg.get("min_off_s",180)))
                if pwm_state=="pulse_too_short":
                    desired=False
                elif pwm_state=="invalid":
                    self._status(area,"invalid_pwm")
                    return
                if desired and not measured[active]:
                    # Do not begin a pulse with insufficient remaining ON time.
                    if period*demand/100-(now-phase_anchor)<float(cfg.get("min_on_s",120)):
                        desired=False
            else:
                observed=measured[active]
                if not isinstance(observed,(int,float)):
                    self._status(area,"invalid_proportional_input")
                    return
                change=max(-float(cfg.get("max_demand_change",10)),
                           min(float(cfg.get("max_demand_change",10)),demand-observed))
                desired=round(observed+change,1)
                if abs(desired-observed)<float(cfg.get("min_demand_change",2)):
                    self._status(area,"demand_within_tolerance",demand_percent=demand)
                    return
                now_last=self.transitions.get(active,{}).get("when")
                if now_last is not None and now-now_last < sample:
                    self._status(area,"proportional_rate_limit")
                    return
                if await self._send(area,active,desired,percentage=True,now=now):
                    self._status(area,"modulating",demand_percent=demand,
                                 commanded_percent=desired)
                return
        last=self.transitions.get(active)
        max_on=finite(cfg.get("max_on_s",7200),300,86400)
        if max_on is None:
            self._status(area,"invalid_maximum_runtime")
            return
        # Enforce the maximum continuously-ON interval even when the PID keeps
        # requesting ON; never bypass the watchdog through an early return.
        if measured[active] is True and last is not None:
            on_since=finite(last.get("when"),0,1e13)
            if on_since is None or now<on_since:
                self._pause(area,"invalid_on_duration")
                return
            if now-on_since>=max_on:
                if await self._send(area,active,False,now=now):
                    self._pause(area,"maximum_on_runtime_exceeded")
                return
        if desired == measured[active]:
            self._status(area,"holding",mode=mode,
                         demand_percent=cycle.pid_percent)
            return
        if last is None:
            # On first observation from an already-OFF actuator, honor a
            # complete OFF minimum interval after startup before energizing.
            last={"state":False,"when":self._started or now}
        change_status,next_state=guarded_transition(
            demand_on=desired,current_on=measured[active],now=now,
            last_changed=float(last["when"]),
            min_on_s=float(cfg.get("min_on_s",120)),
            min_off_s=float(cfg.get("min_off_s",180)),
            maximum_on_s=max_on)
        if change_status=="maximum_runtime_exceeded":
            # A verified direct heating relay overrun is an emergency OFF
            # and a latched pause; never automatically energize it again.
            if await self._send(area,active,False,now=now):
                self._pause(area,"maximum_on_runtime_exceeded")
            return
        if change_status!="transition":
            self._status(area,change_status,mode=mode)
            return
        if await self._send(area,active,next_state,now=now):
            self._status(area,"commanded",mode=mode,
                         output_on=next_state,demand_percent=cycle.pid_percent)
