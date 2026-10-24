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
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, Callable

from .climate_strategy import guarded_transition, pwm_slot, relay_demand
from .climate_arbitration import new_command_gate
from .discovery import entity_area, temperature_sensor_c
from .pid_math import Memory, finite, step
from .const import DOMAIN

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
        # Continuous energized duration is distinct from command timestamps.
        # Proportional modulation must never reset this watchdog.
        self.energized_since: dict[str, float] = {}
        self.mode_changed: dict[str, float] = {}
        self._rooms: dict[str, RoomCycle] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._store = None
        self._ready = False
        self._active = False
        self._started: float | None = None
        self._last_config: dict[str,dict] = {}
        self._last_plans: dict[str,dict] = {}
        self._retired_config: dict[str,dict] = {}
        self._retiring: dict[str,asyncio.Task] = {}
        self._write_lock = asyncio.Lock()

    def _snapshot(self) -> dict:
        return {"version": 1, "paused": dict(self.paused),
                "expected": {k: dict(v) for k,v in self.expected.items()},
                "transitions": {k: dict(v) for k,v in self.transitions.items()},
                "energized_since": dict(self.energized_since),
                "mode_changed": dict(self.mode_changed)}

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
            self._store = Store(self.hass, 1, f"{DOMAIN}.direct_{self.entry_id}")
            saved = await self._store.async_load()
        except Exception:
            _LOGGER.exception("Direct actuator storage unavailable; output writes disabled")
            return
        if saved is not None and (
            not isinstance(saved, dict) or saved.get("version") != 1 or
            any(not isinstance(saved.get(key, {}), dict) for key in (
                "paused", "expected", "transitions", "energized_since",
                "mode_changed"
            ))
        ):
            self._active = False
            self._status("*", "safety_history_unsupported")
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
            active_since = saved.get("energized_since", {})
            if isinstance(active_since, dict):
                self.energized_since = {
                    entity: float(stamp) for entity, stamp in active_since.items()
                    if isinstance(entity,str) and
                    entity.startswith(("switch.","number.")) and
                    finite(stamp,0,1e13) is not None
                }
            changes = saved.get("mode_changed", {})
            if isinstance(changes, dict):
                self.mode_changed = {k:float(v) for k,v in changes.items()
                                     if isinstance(k,str) and finite(v,0,1e13) is not None}
            for entity, record in self.expected.items():
                if (not entity.startswith(("switch.", "number.")) or
                        record.get("phase", "commanded") not in ("intent", "commanded")):
                    self._active = False
                    self._status("*", "safety_history_unsupported")
                    return
                if record.get("phase") == "intent":
                    area = record.get("area")
                    if not isinstance(area, str) or not area:
                        self._active = False
                        self._status("*", "unattributed_direct_write_intent")
                        return
                    self.paused[area] = "interrupted_direct_write_requires_manual_reconciliation"
                    self._status(area, "paused", reason=self.paused[area])
        self._ready = True
        if any(rec.get("phase") == "intent" for rec in self.expected.values()):
            self._persist()

    async def async_stop(self) -> None:
        # On Home Assistant reload, deenergize outputs owned by this direct
        # non-compressor controller BEFORE leaving the feedback loop.
        self._active = False
        running = tuple(self._tasks.values())
        for task in running:
            task.cancel()
        if running:
            await asyncio.gather(*running, return_exceptions=True)
        self._tasks.clear()
        # Do not abandon a scheduled safe-off when Home Assistant unloads
        # during an options change or room removal.
        if self._retiring:
            await asyncio.gather(*tuple(self._retiring.values()),
                                 return_exceptions=True)
        self._retiring.clear()
        if self._ready:
            # A reconfigured area may have BOTH an old, not-yet-reconciled
            # output and a newly commissioned output. Check both separately.
            for profiles in (self._retired_config, self._last_config):
                for area,settings in profiles.items():
                    if (not isinstance(settings,dict) or
                            not settings.get("direct_hardware_confirmed") or
                            not settings.get("allow_actuation")):
                        continue
                    await self._safe_off_owned(area,settings,now=self.clock())
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

    async def _safe_off_owned(self, area:str,settings:dict,*,now:float)->bool:
        """Deenergize only outputs this controller is known to own."""
        percentage=settings.get("controller")=="proportional"
        for entity in self._entities(settings):
            from .climate_entry_ownership import foreign_owner_hold
            # The old room's recorded ownership is not permission to change
            # an output moved to another HA area or claimed by another entry.
            if (entity_area(self.hass,entity)!=area or
                    foreign_owner_hold(self.hass,self.entry_id,entity) is not None):
                _LOGGER.warning("Retired output %s changed HA ownership; manual reconciliation required",entity)
                return False
            state=self.hass.states.get(entity)
            if state is None or str(state.state).lower() in ("unknown","unavailable"):
                _LOGGER.warning("Could not confirm output OFF: %s state unavailable",entity)
                return False
            observed=finite(state.state,0,100) if percentage else (
                True if state.state=="on" else False if state.state=="off" else None
            )
            if observed is None:
                return False
            if observed is True or (percentage and observed>0):
                known=self.expected.get(entity)
                if (not isinstance(known,dict) or
                        known.get("phase", "commanded") != "commanded" or
                        known.get("state") != observed):
                    _LOGGER.warning("Output %s active but not confirmed owned; refusing to overwrite", entity)
                    return False
                if not await self._send(
                    area,entity,0.0 if percentage else False,
                    percentage=percentage,now=now,
                ):
                    return False
        return True

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
            if (settings.get("controller") in ("on_off","pwm","proportional")
                    and settings.get("allow_actuation") and
                    settings.get("direct_hardware_confirmed")):
                if not await self._safe_off_owned(area,settings,now=self.clock()):
                    self._pause(area,"pause_output_unconfirmed")
                    return {"accepted":False,"reason":"unable_to_confirm_output_safe_off"}
            self._pause(area,"user_paused")
        else:
            # Uncertain ON history must be physically reconciled, not merely
            # cleared with Resume. Require OFF for the entire original dwell.
            pending = [entity for entity in self._entities(settings)
                       if self.expected.get(entity, {}).get("phase") == "intent"]
            now = self.clock()
            minimum = finite(settings.get("min_off_s", 180), 60, 7200)
            for entity in pending:
                observed = self.hass.states.get(entity)
                changed = getattr(observed, "last_changed", None)
                is_off = (finite(observed.state, 0, 100) == 0
                          if entity.startswith("number.") else
                          observed.state == "off") if observed is not None else False
                if (minimum is None or entity_area(self.hass, entity) != area or
                        not is_off or not isinstance(changed, datetime) or
                        changed.tzinfo is None or
                        not 0 <= now - changed.timestamp() or
                        now - changed.timestamp() < minimum):
                    return {"accepted": False,
                            "reason": "verified_output_off_and_full_dwell_required"}
            for entity in pending:
                self.expected.pop(entity, None)
                self.energized_since.pop(entity, None)
                self.transitions[entity] = {"state": False, "when": now}
            self.paused.pop(area,None)
            self._rooms.pop(area,None)
            self._started=now
            self._persist()
            self._status(area,"startup_warmup")
        return {"accepted":True,"area":area,"action":action}

    @staticmethod
    def _hardware_signature(settings: dict) -> tuple:
        """A live room edit cannot relax the original safety policy."""
        return tuple(settings.get(key) for key in (
            "enabled", "allow_actuation", "direct_hardware_confirmed",
            "controller", "heat_actuator", "cool_actuator",
            "temperature_entity", "min_on_s", "min_off_s", "max_on_s",
            "mode_dwell_s", "pwm_period_s",
        ))

    def _retire_room(self, area: str, previous: dict) -> None:
        if area in self._retiring and not self._retiring[area].done():
            return
        # Cancel any in-flight ON task first. A write that was already
        # dispatched leaves a durable intent and will NOT be treated as
        # confirmed ownership merely because the desired state matches.
        running = self._tasks.pop(area, None)
        if running is not None and not running.done():
            running.cancel()
        self._retired_config[area] = dict(previous)

        async def retire() -> None:
            if running is not None:
                await asyncio.gather(running, return_exceptions=True)
            if not self._ready:
                self._pause(area, "retired_output_storage_unavailable")
                return
            safe = await self._safe_off_owned(area, previous, now=self.clock())
            self._pause(area, "room_output_configuration_removed_or_changed"
                        if safe else "retired_output_safe_off_unconfirmed")

        task = self.hass.async_create_task(retire())
        self._retiring[area] = task
        def done(future: asyncio.Task) -> None:
            if self._retiring.get(area) is future:
                self._retiring.pop(area,None)
            if not future.cancelled():
                try:
                    future.result()
                except Exception:
                    _LOGGER.exception("Unable to retire owned output in %s",area)
                    self._pause(area,"retirement_controller_exception")
        task.add_done_callback(done)

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
        self._last_plans = plans if isinstance(plans,dict) else {}
        previous_config = self._last_config
        self._last_config={
            area:dict(settings) for area,settings in config.items()
            if isinstance(area,str) and isinstance(settings,dict)
            and settings.get("enabled")
            and settings.get("controller") in ("on_off","pwm","proportional")
        }
        for area, previous in previous_config.items():
            current = self._last_config.get(area)
            if (self._hardware_signature(previous) !=
                    self._hardware_signature(current or {})):
                self._retire_room(area,previous)
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
            if area in self._retiring and not self._retiring[area].done():
                self._status(area,"retiring_previous_output")
                continue
            entities=self._entities(raw)
            if (pid_rooms or {}).get(area,{}).get("enabled"):
                self._status(area,"conflicting_pid_room")
                continue
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
                    *, percentage: bool=False, now:float,
                    cfg:dict|None=None, report:dict|None=None)->bool:
        """Durably record ON intent before the first physical command."""
        domain, service = (("number", "set_value") if percentage else
                           ("switch", "turn_on" if state is True else "turn_off"))
        data = {"value": float(state)} if percentage else {}
        new_active = state is True or (percentage and float(state) > 0)
        async with self._write_lock:
            if new_active and (not self._active or not self._ready or
                               area in self.paused or self._store is None):
                self._pause(area, "direct_write_not_authorized")
                return False
            prior = self.expected.get(entity, {})
            previous = prior.get("state")
            old_active = previous is True or (
                percentage and isinstance(previous, (int,float))
                and not isinstance(previous, bool) and previous > 0
            )
            if new_active:
                # Without this durable intent an interrupted turn_on can
                # leave an energized actuator with NO ownership/watchdog
                # history. Capture a deep snapshot before dispatch.
                self.expected[entity] = {
                    "state": state, "when": now, "phase": "intent", "area": area}
                self.transitions[entity] = {"state": state, "when": now}
                if not old_active:
                    self.energized_since[entity] = now
                try:
                    await self._store.async_save(self._snapshot())
                except asyncio.CancelledError:
                    raise
                except Exception:
                    _LOGGER.exception("Cannot store direct ON intent for %s", entity)
                    self._pause(area, "direct_intent_storage_failed")
                    return False
                latest = self._last_config.get(area)
                if (not self._active or area in self.paused or
                        not isinstance(latest,dict) or
                        latest.get("enabled") is not True or
                        latest.get("allow_actuation") is not True or
                        latest.get("direct_hardware_confirmed") is not True or
                        entity not in self._entities(latest) or
                        entity_area(self.hass,entity)!=area or
                        cfg is None or latest != cfg or
                        report is None or self._last_plans.get(area) is not report or
                        temperature_sensor_c(self.hass, cfg.get("temperature_entity"),
                                             MAX_SENSOR_AGE_MINUTES) is None or
                        new_command_gate(self.hass,area,cfg,report,"thermal",entity,
                                         now=self.clock(),entry_id=self.entry_id) is not None):
                    self._pause(area, "direct_intent_revoked_before_dispatch")
                    return False
            try:
                if not self.hass.services.has_service(domain,service):
                    raise RuntimeError(f"{domain}.{service} not available")
                await asyncio.wait_for(self.hass.services.async_call(
                    domain,service,data,target={"entity_id":entity},blocking=True
                ),timeout=WRITE_TIMEOUT_SECONDS)
            except asyncio.CancelledError:
                # Persistent intent may have reached equipment; never retry.
                raise
            except Exception:
                _LOGGER.exception("Direct actuator command failed: %s",entity)
                self._pause(area,"service_failed_or_timeout")
                return False
            self.expected[entity] = {
                "state":state, "when":now, "phase":"commanded", "area":area}
            if not new_active:
                self.energized_since.pop(entity,None)
            elif not old_active:
                self.energized_since[entity]=now
            self.transitions[entity]={"state":state,"when":now}
            try:
                await self._store.async_save(self._snapshot())
            except asyncio.CancelledError:
                raise
            except Exception:
                if new_active:
                    self.expected[entity]["phase"]="intent"
                self._pause(area, "direct_command_history_persist_failed")
                return False
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
        coordination_reason=None
        if can_run and isinstance(active,str):
            coordination_reason=new_command_gate(
                self.hass,area,cfg,report,"thermal",active,now=now,entry_id=self.entry_id,
            )
            if coordination_reason is not None:
                can_run=False
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
        max_on=finite(cfg.get("max_on_s",7200),300,86400)
        if max_on is None:
            self._status(area,"invalid_maximum_runtime")
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
            if (acknowledgement is not None and
                    acknowledgement.get("phase", "commanded") != "commanded"):
                self._pause(area, "interrupted_direct_write_requires_manual_reconciliation")
                return
            if acknowledgement is not None and acknowledgement.get("state") != observed:
                sent=finite(acknowledgement.get("when"),0,1e13)
                if sent is not None and 0 <= now-sent < ACK_GRACE_SECONDS:
                    self._status(area,"waiting_for_output_ack",entity=e)
                    return
                self._pause(area,"manual_override_or_unacknowledged_output")
                return
            observed_on=(observed is True or
                         (strategy=="proportional" and observed>0))
            if acknowledgement is None and observed_on:
                self._pause(area,"unowned_active_output")
                return
            if observed_on and acknowledgement is not None:
                begun=finite(self.energized_since.get(e),0,1e13)
                if begun is None or now<begun:
                    # Historical runtime is unknown after a damaged cache or
                    # upgrade: stop only an explicitly owned active load.
                    if not await self._send(area,e,
                            0.0 if strategy=="proportional" else False,
                            percentage=strategy=="proportional",now=now):
                        return
                    self._pause(area,"continuous_runtime_history_missing")
                    return
                if now-begun>=max_on:
                    if not await self._send(area,e,
                            0.0 if strategy=="proportional" else False,
                            percentage=strategy=="proportional",now=now):
                        return
                    self._pause(area,"maximum_on_runtime_exceeded")
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
            self._status(area,"safe_off",reason=coordination_reason or
                         report.get("reason","no_heat_cool_demand"))
            return
        last_mode=self._rooms.get(area,RoomCycle()).mode
        if last_mode not in (None,mode):
            self._rooms.pop(area,None)
            self.mode_changed[area]=now
            self._persist()
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
        mode_dwell=finite(cfg.get("mode_dwell_s",900),300,7200)
        if mode_dwell is None:
            self._status(area,"invalid_mode_dwell")
            return
        if now-self.mode_changed.get(area,self._started if self._started is not None else now)<mode_dwell:
            self._status(area,"mode_transfer_dwell")
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
                max_delta=finite(cfg.get("max_demand_change",10),1,50)
                min_delta=finite(cfg.get("min_demand_change",2),0.1,20)
                number_state=self.hass.states.get(active)
                spacing=finite(number_state.attributes.get("step") if number_state else None,0.1,10)
                if None in (max_delta,min_delta,spacing):
                    self._status(area,"invalid_percentage_step_or_rate")
                    return
                change=max(-max_delta,min(max_delta,demand-observed))
                proposed=max(0.0,min(100.0,observed+change))
                # Quantize inward, never allowing device rounding to violate
                # the maximum allowed output change per sampling interval.
                if change>=0:
                    desired=math.floor(proposed/spacing+1e-9)*spacing
                else:
                    desired=math.ceil(proposed/spacing-1e-9)*spacing
                desired=round(max(0.0,min(100.0,desired)),5)
                if abs(desired-observed)<min_delta:
                    self._status(area,"demand_within_tolerance",demand_percent=demand)
                    return
                now_last=self.transitions.get(active,{}).get("when")
                if now_last is not None and now-now_last < sample:
                    self._status(area,"proportional_rate_limit")
                    return
                if await self._send(area,active,desired,percentage=True,now=now,
                                    cfg=cfg,report=report):
                    self._status(area,"modulating",demand_percent=demand,
                                 commanded_percent=desired)
                return
        last=self.transitions.get(active)
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
        if await self._send(area,active,next_state,now=now,
                            cfg=cfg,report=report):
            self._status(area,"commanded",mode=mode,
                         output_on=next_state,demand_percent=cycle.pid_percent)
