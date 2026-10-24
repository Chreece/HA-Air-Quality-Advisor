"""Commissioning-gated native DRY <-> FAN_ONLY HVAC mode controller.

This module never controls compressor electrical power, calls turn_on/off,
targets an area/device, or changes HEAT/COOL/AUTO modes. Automatic transitions
require explicit per-room consent AND independently protected, commissioned
equipment exposing BOTH DRY and FAN_ONLY. An HVAC entity exposing only DRY
is fully supported for monitoring/manual advice, never auto mode switching.

No software can certify a real compressor's defrost, cycle, refrigerant,
outdoor-unit, electrical or motor safety. The entire feature defaults off.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Callable

from .climate_coordination import device_inventory, duplicate_owners, room_equipment_plan
from .climate_entry_ownership import foreign_owner_hold
from .climate_equipment import humidity_advice
from .climate_hvac_modes import native_air_mode_advice
from .discovery import entity_area, reading
from .logic import Reading
from .pid_math import finite
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
STARTUP_WARMUP_S=300
MIN_MODE_DWELL_S=1800
# Confirm sustained native idle before leaving DRY. A single instant of
# hvac_action=idle is not evidence that the compressor is safe to cycle.
MIN_DRY_IDLE_CONFIRM_S=300
ACK_GRACE_S=120
SERVICE_TIMEOUT_S=20
VALID_MODES=frozenset(("dry","fan_only"))


def allowed_dwell(config: dict) -> float | None:
    """Never permit less than 30 minutes between native HVAC mode changes."""
    return finite(config.get("dry_fan_mode_dwell_s",1800),1800,14400)


class NativeAirModeControl:
    """One explicitly chosen native AC, with persistent manual override latch."""

    def __init__(self,hass: Any,entry_id: str, *,
                 clock: Callable[[],float] | None=None,
                 changed: Callable[[],None] | None=None):
        self.hass,self.entry_id=hass,entry_id
        self.clock=clock or time.time
        self.changed=changed or (lambda:None)
        self.statuses:dict[str,dict]={}
        self.paused:dict[str,str]={}
        self.expected:dict[str,dict]={}
        self.last_write:dict[str,float]={}
        # In-process observations deliberately reset on HA restart. They
        # cannot stand in for manufacturer-proven compressor protections.
        self._dry_idle_since:dict[str,float]={}
        self._configured:dict={}
        self._planned:dict={}
        self._tasks:dict[str,asyncio.Task]={}
        self._store=None
        self._started:float|None=None
        self._active=False
        self._ready=False

    def _snapshot(self)->dict:
        # Capture value copies: a returned Store snapshot must NOT silently
        # change its previously persisted "intent" phase if our in-memory
        # record is later advanced to "commanded" but that second save fails.
        return {"version":1,"paused":dict(self.paused),
                "expected":{area:dict(value) for area,value in self.expected.items()},
                "last_write":dict(self.last_write)}

    def _save(self)->None:
        if self._store is not None:
            self._store.async_delay_save(self._snapshot,3)

    def _status(self,area:str,status:str,**details:Any)->None:
        current={"status":status,**details}
        if self.statuses.get(area)!=current:
            self.statuses[area]=current
            if self._active:
                self.changed()

    def _pause(self,area:str,reason:str)->None:
        self.paused[area]=reason
        self._save()
        self._status(area,"paused",reason=reason)

    async def async_start(self)->None:
        self._active=True
        self._started=self.clock()
        try:
            from homeassistant.helpers.storage import Store
            self._store=Store(
                self.hass,1,
                f"{DOMAIN}.native_dry_fan_{self.entry_id}",
            )
            loaded=await self._store.async_load()
        except Exception:
            _LOGGER.exception("Native DRY/FAN mode control safety storage unavailable")
            return
        if loaded is not None and (
            not isinstance(loaded,dict) or loaded.get("version")!=1 or
            not isinstance(loaded.get("expected",{}),dict) or
            not isinstance(loaded.get("paused",{}),dict) or
            not isinstance(loaded.get("last_write",{}),dict)
        ):
            # Never reinterpret future/incompatible or corrupt safety records
            # as a fresh, first-time installation. Fail closed, keeping the
            # original on-disk record available for diagnosis.
            _LOGGER.error("Unsupported or damaged DRY/FAN mode safety history")
            self._active=False
            self._status("*","safety_history_unsupported")
            return
        if isinstance(loaded,dict) and loaded.get("version")==1:
            paused=loaded.get("paused",{})
            if isinstance(paused,dict):
                self.paused={a:v for a,v in paused.items()
                             if isinstance(a,str) and isinstance(v,str)}
            expected=loaded.get("expected",{})
            if isinstance(expected,dict):
                if any(not isinstance(area,str) or not isinstance(item,dict)
                       for area,item in expected.items()):
                    _LOGGER.error("Corrupt DRY/FAN pending write history")
                    self._active=False
                    self._status("*","safety_history_unsupported")
                    return
                self.expected={
                    area:dict(item) for area,item in expected.items()
                }
            written=loaded.get("last_write",{})
            if isinstance(written,dict):
                if any(not isinstance(area,str) or finite(v,0,1e13) is None
                       for area,v in written.items()):
                    _LOGGER.error("Corrupt native mode last-write history")
                    self._active=False
                    self._status("*","safety_history_unsupported")
                    return
                self.last_write={area:float(v) for area,v in written.items()}
            for area,record in self.expected.items():
                phase=record.get("phase","commanded")
                if phase=="intent":
                    # Surface interrupted physical commands as an immediate
                    # persisted safety pause rather than showing warmup for
                    # several minutes and discovering the issue only later.
                    self.paused[area]=(
                        "interrupted_mode_write_requires_manual_reconciliation"
                    )
                    self._status(area,"paused",reason=self.paused[area])
                elif phase!="commanded":
                    self.paused[area]="persistent_mode_ack_history_invalid"
                    self._status(area,"paused",reason=self.paused[area])
            if self.paused:
                self._save()
        self._ready=True

    async def async_stop(self)->None:
        self._active=False
        tasks=tuple(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks,return_exceptions=True)
        self._tasks.clear()
        self._dry_idle_since.clear()
        if self._ready and self._store is not None:
            try:
                await self._store.async_save(self._snapshot())
            except Exception:
                # A broken Store cannot justify new commands, but must not
                # prevent other HA controllers from unloading cleanly.
                _LOGGER.exception("Could not persist native DRY/FAN shutdown history")

    async def command(self,area:str,action:str)->dict:
        if action not in ("pause","resume") or not self._ready:
            return {"accepted":False,"reason":"unavailable_or_unsupported_action"}
        task=self._tasks.get(area)
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
        if action=="pause":
            self._pause(area,"user_paused")
        else:
            # A previous DRY command may have reached the compressor even if
            # Home Assistant did not acknowledge it. Never discard physical
            # mode history merely because the user pressed Resume.
            config=self._configured.get(area,{})
            entity=config.get("dry_climate_entity") if isinstance(config,dict) else None
            dwell=allowed_dwell(config) if isinstance(config,dict) else None
            state=self.hass.states.get(entity) if isinstance(entity,str) else None
            changed=getattr(state,"last_changed",None)
            now=self.clock()
            latest=self.last_write.get(area,0)
            if not (dwell is not None and
                    isinstance(entity,str) and entity_area(self.hass,entity)==area and
                    state is not None and state.state=="fan_only" and
                    state.attributes.get("hvac_action") in ("fan","idle") and
                    isinstance(changed,datetime) and changed.tzinfo is not None and
                    0<=now-changed.timestamp() and now-changed.timestamp()>=dwell and
                    0<=now-latest and now-latest>=dwell):
                return {
                    "accepted":False,"reason":"manual_fan_only_reconciliation_and_full_dwell_required",
                }
            # Only a physically confirmed, stable FAN_ONLY state can retire
            # an unacknowledged/failed previous intent. Preserve last_write:
            # it remains an additional anti-short-cycle bound after resume.
            self.paused.pop(area,None)
            self.expected.pop(area,None)
            self._dry_idle_since.pop(area,None)
            self._started=now
            self._save()
            self._status(area,"startup_warmup")
        return {"accepted":True,"area":area,"action":action}

    def schedule(self,configs:dict,plans:dict)->None:
        if not self._active or not self._ready or not isinstance(configs,dict):
            return
        self._configured=configs
        self._planned=plans if isinstance(plans,dict) else {}
        now=self.clock()
        for area,config in configs.items():
            if not isinstance(area,str) or not isinstance(config,dict):
                continue
            if not (config.get("enabled") is True and
                    config.get("allow_actuation") is True and
                    config.get("dry_fan_mode_auto") is True and
                    config.get("dry_fan_hardware_confirmed") is True):
                self._status(area,"advisory_only")
                continue
            task=self._tasks.get(area)
            if task is not None and not task.done():
                continue
            # Pass an immutable-at-dispatch snapshot of the room's options.
            # If an options reload or new plan arrives during storage I/O,
            # the live pre-service gate detects that change and aborts.
            task=self.hass.async_create_task(
                self._apply(area,dict(config),self._planned.get(area,{}),now)
            )
            self._tasks[area]=task
            def done(future:asyncio.Task,key:str=area)->None:
                if self._tasks.get(key) is future:
                    self._tasks.pop(key,None)
                if not future.cancelled():
                    try:
                        future.result()
                    except Exception:
                        _LOGGER.exception("Unexpected native DRY/FAN mode failure for %s",key)
                        self._pause(key,"controller_exception")
            task.add_done_callback(done)

    def _current_evidence(self,area:str,cfg:dict,plan:dict,now:float)->tuple[str,dict|None]:
        """Rebuild current RH evidence and device inventory, never trust old plan."""
        if not self._active or not self._ready or area in self.paused:
            return "controller_not_active_or_paused",None
        if not isinstance(cfg,dict) or self._configured.get(area)!=cfg:
            return "room_permissions_or_equipment_changed",None
        if not isinstance(self._planned,dict) or self._planned.get(area) is not plan:
            return "room_plan_superseded",None
        if not (
            cfg.get("enabled") is True and
            cfg.get("allow_actuation") is True and
            cfg.get("dry_fan_mode_auto") is True and
            cfg.get("dry_fan_hardware_confirmed") is True
        ):
            return "native_mode_permission_revoked",None
        if allowed_dwell(cfg) is None:
            return "native_mode_dwell_policy_changed",None
        if not isinstance(plan,dict):
            return "plan_missing",None
        if plan.get("equipment_plan",{}).get("status")!="ready":
            return "equipment_plan_unverified",None
        if plan.get("window_safe") is not True:
            return "window_plan_unsafe",None
        windows=plan.get("window_contacts")
        if not isinstance(windows,list):
            return "window_contacts_missing",None
        if not windows and cfg.get("dry_fan_windowless_confirmed") is not True:
            return "window_contact_or_explicit_exception_required",None
        for entity in windows:
            if not isinstance(entity,str) or entity_area(self.hass,entity)!=area:
                return "window_wrong_room",None
            observed=self.hass.states.get(entity)
            if (observed is None or observed.domain!="binary_sensor" or
                    observed.attributes.get("device_class")!="window" or
                    observed.state!="off"):
                return "window_open_or_unknown",None
        sensor=cfg.get("humidity_entity")
        if not isinstance(sensor,str) or entity_area(self.hass,sensor)!=area:
            return "explicit_room_humidity_sensor_required",None
        latest=reading(self.hass,sensor,10,outdoor=False)
        if latest.metric!="humidity" or latest.value is None:
            return "humidity_sensor_invalid_or_stale",None
        entity=cfg.get("dry_climate_entity")
        if not isinstance(entity,str) or not entity.startswith("climate.") or (
                entity_area(self.hass,entity)!=area):
            return "dedicated_dry_climate_required",None
        state=self.hass.states.get(entity)
        if state is None or state.state not in VALID_MODES:
            return "unit_must_be_running_dry_or_fan_only",None
        inv=device_inventory(self.hass,area,cfg)
        role=inv.get("dry_climate_entity",{})
        caps=role.get("capabilities",{})
        if role.get("status")!="ready" or not (
            caps.get("drying") is True and caps.get("fan_only") is True):
            return "both_dry_and_fan_only_required",None
        if entity in duplicate_owners(self._configured):
            return "duplicate_device_owner",None
        other_entry=foreign_owner_hold(self.hass,self.entry_id,entity)
        if other_entry is not None:
            return other_entry,None
        # Never switch a climate entity while another room controller
        # could simultaneously set its HEAT/COOL target.
        if cfg.get("climate_entity")==entity and not (
            cfg.get("controller")=="environment" or
            (cfg.get("controller")=="device" and cfg.get("mode")=="dry")
        ):
            return "temperature_controller_owns_same_device",None
        for other_role in (
            "heat_climate_entity","cool_climate_entity",
            "climate_entity","fan_climate_entity",
        ):
            other=cfg.get(other_role)
            if other is None or other==entity:
                continue
            observed=self.hass.states.get(other)
            if (not isinstance(other,str) or entity_area(self.hass,other)!=area
                    or observed is None or observed.state in ("unknown","unavailable")):
                return "competing_hvac_unverified",None
            # HEAT/COOL/AUTO/DRY modes can spontaneously engage the
            # compressor while current hvac_action is idle.
            if observed.state not in ("off","fan_only"):
                return "other_hvac_armed",None
            if observed.attributes.get("hvac_action") in (
                "heating","preheating","cooling","drying","defrosting"):
                return "other_hvac_active",None
        for moisture_role in ("humidifier_entity","dehumidifier_entity"):
            other=inv.get(moisture_role,{})
            if other and (other.get("status")!="ready" or other.get("active")):
                return "other_humidity_device_active_or_unverified",None
        if cfg.get("humidity_power_auto") is True or cfg.get("humidity_setpoint_auto") is True:
            return "conflicting_native_humidity_controller",None
        if cfg.get("secondary_climate_setpoint_auto") is True and entity in (
            cfg.get("heat_climate_entity"),cfg.get("cool_climate_entity")
        ):
            return "secondary_setpoint_conflict",None
        # Any previously approved room safety hold still applies.
        coordinator=plan.get("coordination",{})
        thermal=(coordinator.get("channels",{}).get("thermal",{})
                 if isinstance(coordinator,dict) else {})
        if thermal.get("status")=="eligible":
            return "thermal_temperature_control_has_priority",None
        # Strict native fan-only -> compressor entry demands a declared,
        # physical FAN/IDLE state and separately commissioned hardware.
        # Stopping an ACTIVE DRY compressor would be unsafe, so exit only
        # after its native action has already become IDLE.
        action=state.attributes.get("hvac_action")
        if state.state=="fan_only" and action not in ("fan","idle"):
            return "fan_state_or_compressor_unknown",None
        fresh=room_equipment_plan(
            self.hass,area,cfg,
            {"status":plan.get("status"),"mode":plan.get("mode"),
             "window_safe":True},
            (Reading(sensor,"Room humidity","humidity",latest.value),),
            duplicates=duplicate_owners(self._configured),
        )
        humidity=humidity_advice(
            latest.value,
            low_rh=cfg.get("humidity_low_rh",40),
            high_rh=cfg.get("humidity_high_rh",60),
            hysteresis=cfg.get("humidity_hysteresis_rh",3),
            drying_available=True,
            previous="dry" if state.state=="dry" else "idle",
        )
        if humidity.get("status")!="advisory":
            return "humidity_parameters_invalid",None
        fresh["humidity"]=humidity
        # Use the proven advisory policy as one reusable source for
        # deciding the desired mode, then add hardware-specific guards.
        suggestion=native_air_mode_advice(self.hass,area,cfg,fresh,now)
        # A fresh native report of active compressor work invalidates
        # every previous sustained-idle observation, even while RH remains
        # high enough that no transition is currently requested.
        if state.state=="dry" and action not in ("idle","fan"):
            self._dry_idle_since.pop(area,None)
        if suggestion.get("status")=="already_in_suitable_mode":
            return "already_in_suitable_mode",None
        # DRY -> FAN_ONLY may interrupt a compressor. Require the unit's
        # reported compressor state to remain idle over multiple polls.
        # This is an extra protective software gate, never proof that
        # the manufacturer's own minimum-off/defrost requirements are met.
        if state.state=="dry":
            if action not in ("idle","fan"):
                return "active_compressor_wait_for_idle",None
            since=self._dry_idle_since.get(area)
            if since is None or since>now:
                self._dry_idle_since[area]=now
                return "compressor_idle_confirmation_pending",None
            if now-since<MIN_DRY_IDLE_CONFIRM_S:
                return "compressor_idle_confirmation_pending",None
        if suggestion.get("status")!="manual_mode_transition_suggested":
            return suggestion.get("status","advice_unavailable"),None
        selected=suggestion.get("recommended_mode")
        if selected not in VALID_MODES:
            return "unsafe_or_unsupported_mode_change",None
        return "ready",{"entity_id":entity,"mode":selected,
                        "current":state.state,"source":sensor}

    async def _apply(self,area:str,cfg:dict,plan:dict,now:float)->None:
        if not self._active or not self._ready or area in self.paused:
            return
        dwell=allowed_dwell(cfg)
        if dwell is None:
            self._status(area,"invalid_mode_dwell")
            return
        if now-(self._started if self._started is not None else now)<STARTUP_WARMUP_S:
            self._status(area,"startup_warmup")
            return
        entity=cfg.get("dry_climate_entity")
        if not isinstance(entity,str):
            self._status(area,"dedicated_dry_climate_required")
            return
        state=self.hass.states.get(entity)
        expected=self.expected.get(area)
        if expected is not None:
            written=finite(expected.get("when"),0,1e13)
            target=expected.get("mode")
            phase=expected.get("phase","commanded")
            if (written is None or written>now or
                expected.get("entity_id")!=entity or target not in VALID_MODES or
                phase not in ("intent","commanded")):
                self._pause(area,"persistent_mode_ack_history_invalid")
                return
            # A durable pre-write intent may have reached the physical AC
            # before the process died. Never guess whether it took effect,
            # even when Home Assistant currently reports the target state.
            if phase=="intent":
                self._pause(area,"interrupted_mode_write_requires_manual_reconciliation")
                return
            if state is None or state.state!=target:
                if now-written<ACK_GRACE_S:
                    self._status(area,"waiting_for_native_mode_ack")
                else:
                    self._pause(area,"manual_mode_or_unacknowledged_write")
                return
        if now-self.last_write.get(area,0)<dwell:
            self._status(area,"mode_transition_dwell")
            return
        ready,item=self._current_evidence(area,cfg,plan,now)
        if ready!="ready" or item is None:
            self._status(area,ready)
            return
        state=self.hass.states.get(item["entity_id"])
        if state is None:
            self._status(area,"device_unavailable")
            return
        last=getattr(state,"last_changed",None)
        if not isinstance(last,datetime) or last.tzinfo is None:
            self._status(area,"mode_history_unavailable")
            return
        elapsed=now-last.timestamp()
        if elapsed<dwell or elapsed<0:
            self._status(area,"native_mode_dwell_not_met")
            return
        # No power controls and no implicit OFF/HEAT/COOL/AUTO request.
        if item["mode"] not in VALID_MODES or state.state not in VALID_MODES:
            self._status(area,"unsafe_mode_selection")
            return
        if not self.hass.services.has_service("climate","set_hvac_mode"):
            self._status(area,"native_mode_service_missing")
            return
        # Durable write-ahead: a successful service may reach the actual
        # HVAC unit just before Home Assistant or the integration crashes.
        # Persist the intent *before* the first physical mode command.
        # On an interrupted write this record forces human reconciliation
        # instead of automatically retrying a potentially running compressor.
        self.expected[area]={
            "entity_id":item["entity_id"],"mode":item["mode"],
            "when":now,"phase":"intent",
        }
        self.last_write[area]=now
        try:
            if self._store is None:
                raise RuntimeError("Persistent mode history unavailable")
            await self._store.async_save(self._snapshot())
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.exception("Cannot persist native DRY/FAN mode intent in %s",area)
            self._pause(area,"mode_intent_storage_failed")
            return
        # Storage I/O may suspend this coroutine while a room window
        # opens, another compressor engages, or the humidity evidence
        # changes. The durable intent is already saved: re-verify the
        # specific mode/target immediately before the physical service call.
        # If evidence changed, preserve the intent as a fail-closed
        # reconciliation record rather than sending an obsolete command.
        rechecked_at=self.clock()
        verified_again,latest=self._current_evidence(
            area,cfg,plan,rechecked_at,
        )
        # Between the durable intent and this service call, HA can receive
        # a new device event that resets its physical mode-change timer.
        # Honor the room's ORIGINAL configured dwell, not merely the
        # generic 30-minute advisor threshold checked above.
        physical=self.hass.states.get(item["entity_id"])
        final_changed=getattr(physical,"last_changed",None)
        dwell_still_valid=(
            isinstance(final_changed,datetime) and
            final_changed.tzinfo is not None and
            0<=rechecked_at-final_changed.timestamp() and
            rechecked_at-final_changed.timestamp()>=dwell
        )
        if (verified_again!="ready" or not isinstance(latest,dict) or
                latest.get("entity_id")!=item["entity_id"] or
                latest.get("mode")!=item["mode"] or
                not dwell_still_valid or
                self.last_write.get(area)!=now):
            self._pause(area,"mode_intent_aborted_by_live_interlock")
            return
        try:
            await asyncio.wait_for(
                self.hass.services.async_call(
                    "climate","set_hvac_mode",
                    {"hvac_mode":item["mode"]},
                    target={"entity_id":item["entity_id"]},blocking=True,
                ),SERVICE_TIMEOUT_S,
            )
        except asyncio.CancelledError:
            # The durable 'intent' is deliberately left in place; it may
            # already have reached the device.
            raise
        except Exception:
            _LOGGER.exception("Native DRY/FAN mode command failure in %s",area)
            self._pause(area,"native_mode_service_failure")
            return
        self.expected[area]["phase"]="commanded"
        try:
            await self._store.async_save(self._snapshot())
        except asyncio.CancelledError:
            raise
        except Exception:
            # A service may have reached the real unit while the later
            # completion record could not be committed. Restore the durable
            # INTENT phase in memory, so any shutdown/restart reconciliation
            # still fails closed rather than treating the write as complete.
            _LOGGER.exception("Native DRY/FAN mode acknowledgement history not saved")
            self.expected[area]["phase"]="intent"
            self._pause(area,"mode_command_history_persist_failed")
            return
        self._dry_idle_since.pop(area,None)
        self._status(area,"native_mode_commanded",
                     entity_id=item["entity_id"],mode=item["mode"])
