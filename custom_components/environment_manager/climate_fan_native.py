"""Opt-in fan speed-only control for already-running HA fan.* equipment.

This controller never calls fan.turn_on, fan.turn_off or fan.set_preset_mode.
It can ONLY raise a verified existing speed for an evidence-qualified
CO2 extraction or PM2.5 filtration need. No command is sent for uncertain
sensor, area, fan capability, outdoor conditions, or manual override.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable

from .climate_coordination import duplicate_owners, device_inventory
from .climate_arbitration import new_command_gate
from .discovery import entity_area, reading
from .pid_math import finite
from .const import DOMAIN

_LOGGER=logging.getLogger(__name__)
STARTUP_WARMUP_S=300
MIN_WRITE_INTERVAL_S=300
ACK_GRACE_S=90
WRITE_TIMEOUT_S=20
MAX_STEP_PERCENT=10
FAN_SET_SPEED_FEATURE=1  # Home Assistant FanEntityFeature.SET_SPEED

FAN_ROLES={
    "extraction_fan_entity":("extraction","co2","co2_entity",
                             "extraction_speed_percent"),
    "purifier_fan_entity":("filtration","pm25","pm25_entity",
                           "purifier_speed_percent"),
}


def next_fan_speed(observed: Any, desired: Any, step: Any) -> tuple[str,int|None]:
    """Only upward changes, no zero-speed command or unverified large step."""
    current=finite(observed,1,100)
    target=finite(desired,30,100)
    size=finite(step,1,100)
    if None in (current,target,size):
        return "missing_percent_or_native_step",None
    if size>MAX_STEP_PERCENT:
        return "native_step_exceeds_safe_ramp",None
    if current>=target-0.1:
        return "already_sufficient_speed",None
    # Quantize to the next supported positive percentage; never overshoot the
    # user-permitted target or exceed one ten-point change per cycle.
    ceiling=min(target,current+MAX_STEP_PERCENT)
    index=int((ceiling+1e-8)//size)
    candidate=round(index*size)
    if candidate<=current or candidate-current>MAX_STEP_PERCENT or candidate>target:
        return "incompatible_speed_quantization",None
    return "command",candidate


class RunningFanSpeedControl:
    def __init__(self,hass:Any,entry_id:str,*,clock:Callable|None=None,
                 changed:Callable|None=None):
        self.hass,self.entry_id=hass,entry_id
        self.clock=clock or time.time
        self.changed=changed or (lambda:None)
        self.statuses:dict[str,dict]={}
        self.paused:dict[str,str]={}
        self.expected:dict[str,dict]={}
        self.last_write:dict[str,float]={}
        self._tasks:dict[str,asyncio.Task]={}
        self._store=None
        self._active=False
        self._ready=False
        self._started:float|None=None
        self._configured:dict={}

    def _snapshot(self)->dict:
        return {"version":1,"paused":self.paused,
                "expected":self.expected,"last_write":self.last_write}

    def _save(self)->None:
        if self._store is not None:
            self._store.async_delay_save(self._snapshot,3)

    def _status(self,area:str,value:str,**details:Any)->None:
        state={"status":value,**details}
        if self.statuses.get(area)!=state:
            self.statuses[area]=state
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
            self._store=Store(self.hass,1,
                f"{DOMAIN}.running_fan_{self.entry_id}")
            saved=await self._store.async_load()
        except Exception:
            _LOGGER.exception("Native fan speed safety storage unavailable")
            return
        if isinstance(saved,dict) and saved.get("version")==1:
            for key in ("paused","expected","last_write"):
                values=saved.get(key)
                if not isinstance(values,dict):
                    continue
                if key=="paused":
                    self.paused={k:v for k,v in values.items()
                                 if isinstance(k,str) and isinstance(v,str)}
                elif key=="expected":
                    self.expected={k:v for k,v in values.items()
                                   if isinstance(k,str) and isinstance(v,dict)}
                else:
                    self.last_write={k:float(v) for k,v in values.items()
                                     if isinstance(k,str) and finite(v,0,1e13) is not None}
        self._ready=True

    async def async_stop(self)->None:
        self._active=False
        tasks=tuple(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks,return_exceptions=True)
        self._tasks.clear()
        if self._ready and self._store is not None:
            await self._store.async_save(self._snapshot())

    async def command(self,area:str,action:str)->dict:
        if action not in ("pause","resume") or not self._ready:
            return {"accepted":False,"reason":"unknown_action_or_storage_unavailable"}
        task=self._tasks.get(area)
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
        if action=="pause":
            self._pause(area,"user_paused")
        else:
            self.paused.pop(area,None)
            for device in list(self.expected):
                if device in [self._configured.get(area,{}).get(k) for k in FAN_ROLES]:
                    self.expected.pop(device,None)
                    self.last_write.pop(device,None)
            self._started=self.clock()
            self._save()
            self._status(area,"startup_warmup")
        return {"accepted":True,"area":area,"action":action}

    def schedule(self,configs:dict,plans:dict)->None:
        if not self._active or not self._ready or not isinstance(configs,dict):
            return
        self._configured=configs
        shared=duplicate_owners(configs)
        now=self.clock()
        for area,cfg in configs.items():
            if not isinstance(cfg,dict) or not isinstance(area,str):
                continue
            if cfg.get("fan_power_auto") is True:
                self._status(area,"conflicting_fan_power_owner")
                continue
            if not (cfg.get("enabled") is True and
                    cfg.get("allow_actuation") is True and
                    cfg.get("fan_speed_auto") is True):
                self._status(area,"advisory_only")
                continue
            if area in self.paused:
                self._status(area,"paused",reason=self.paused[area])
                continue
            fans=[e for r in FAN_ROLES
                  if isinstance((e:=cfg.get(r)),str)]
            if len(fans)!=len(set(fans)) or any(e in shared for e in fans):
                self._status(area,"duplicate_or_ambiguous_fan_assignment")
                continue
            plan=plans.get(area,{})
            if not isinstance(plan,dict) or plan.get("air_actions",{}).get("status")!="advisory":
                self._status(area,"no_fresh_air_policy")
                continue
            if now - (self._started or now) < STARTUP_WARMUP_S:
                self._status(area,"startup_warmup")
                continue
            task=self._tasks.get(area)
            if task and not task.done():
                continue
            task=self.hass.async_create_task(self._apply(area,cfg,plan,now))
            self._tasks[area]=task
            def done(future:asyncio.Task,key:str=area)->None:
                if self._tasks.get(key) is future:
                    self._tasks.pop(key,None)
                if not future.cancelled():
                    try:
                        future.result()
                    except Exception:
                        _LOGGER.exception("Unexpected fan speed control error: %s",key)
                        self._pause(key,"unexpected_task_exception")
            task.add_done_callback(done)

    async def _apply(self,area:str,cfg:dict,plan:dict,now:float)->None:
        if (not self._active or not self._ready or area in self.paused or
                cfg.get("enabled") is not True or
                cfg.get("allow_actuation") is not True or
                cfg.get("fan_speed_auto") is not True or
                cfg.get("fan_power_auto") is True):
            return
        if now - (self._started or now) < STARTUP_WARMUP_S:
            self._status(area,"startup_warmup")
            return
        stamp=plan.get("air_evidence_at")
        if stamp is not None:
            seen=finite(stamp,0,1e13)
            if seen is None or not 0 <= now-seen <= 120:
                self._status(area,"air_quality_decision_expired")
                return
        air=plan.get("air_actions",{})
        if air.get("status")!="advisory":
            self._status(area,"air_quality_policy_missing")
            return
        if (len([e for k in FAN_ROLES if isinstance((e:=cfg.get(k)),str)])!=
            len({e for k in FAN_ROLES if isinstance((e:=cfg.get(k)),str)})):
            self._status(area,"ambiguous_fan_roles")
            return
        if any(cfg.get(k) in duplicate_owners(self._configured) for k in FAN_ROLES):
            self._status(area,"duplicate_fan_owner")
            return
        live=device_inventory(self.hass,area,cfg)
        did_any=False
        attempted=False
        for role,(choice,metric,source_key,target_key) in FAN_ROLES.items():
            proposal=air.get(choice,{})
            if not isinstance(cfg.get(role),str):
                continue
            if (proposal.get("status")!="recommended" or
                    proposal.get("speed_control_eligible") is not True):
                continue
            attempted=True
            fan=cfg.get(role)
            source=cfg.get(source_key)
            if (not isinstance(fan,str) or not isinstance(source,str) or
                    entity_area(self.hass,fan)!=area or
                    entity_area(self.hass,source)!=area or
                    live.get(role,{}).get("status")!="ready" or
                    proposal.get("entity_id")!=fan):
                self._status(area,"invalid_fan_or_sensor_assignment")
                return
            if role=="extraction_fan_entity" and (
                    air.get("extraction",{}).get("status")!="recommended" or
                    "elevated_measured_co2" not in proposal.get("reasons",[]) or
                    proposal.get("speed_control_eligible") is not True):
                continue
            if role=="purifier_fan_entity" and cfg.get("pm25_sensor_verified") is not True:
                self._status(area,"particle_sensor_verification_required")
                return
            current=reading(self.hass,source,10,outdoor=False)
            threshold=finite(air.get("thresholds",{}).get(
                "co2_operational_ppm" if metric=="co2" else
                "pm25_short_term_action_ug_m3"),0,20000)
            if current.metric!=metric or current.value is None or threshold is None:
                self._status(area,"sensor_unknown_or_stale")
                return
            if current.value<threshold:
                self._status(area,"measured_need_resolved")
                continue
            state=self.hass.states.get(fan)
            if state is None or state.state!="on":
                self._status(area,"fan_off_no_automatic_power_on",entity_id=fan)
                continue
            attrs=state.attributes
            try:
                features=int(attrs.get("supported_features",0))
            except (TypeError,ValueError,OverflowError):
                features=0
            if features&FAN_SET_SPEED_FEATURE==0:
                self._status(area,"fan_speed_not_supported",entity_id=fan)
                continue
            if attrs.get("preset_mode") not in (None,"","none","manual"):
                self._status(area,"manual_fan_preset_active",entity_id=fan)
                continue
            observed=finite(attrs.get("percentage"),1,100)
            increment=finite(attrs.get("percentage_step"),1,100)
            if None in (observed,increment):
                self._status(area,"fan_percentage_or_step_unknown",entity_id=fan)
                continue
            expected=self.expected.get(fan)
            if expected:
                saved=finite(expected.get("when"),0,1e13)
                desired=finite(expected.get("percentage"),1,100)
                if expected.get("area")!=area or saved is None or desired is None or saved>now:
                    self._pause(area,"persistent_fan_ack_history_invalid")
                    return
                if abs(observed-desired)>max(0.5,increment*.51):
                    if now-saved<ACK_GRACE_S:
                        self._status(area,"waiting_for_fan_speed_ack",entity_id=fan)
                    else:
                        self._pause(area,"manual_speed_or_unacknowledged_fan")
                    return
            if now - self.last_write.get(fan,0)<MIN_WRITE_INTERVAL_S:
                continue
            value,percentage=next_fan_speed(
                observed,cfg.get(target_key,65),increment)
            if value=="already_sufficient_speed":
                self._status(area,"at_target_speed",entity_id=fan,
                             current_percent=observed)
                continue
            if value!="command" or percentage is None:
                self._status(area,value,entity_id=fan)
                continue
            channel=("extraction" if role=="extraction_fan_entity"
                     else "filtration")
            conflict=new_command_gate(
                self.hass,area,cfg,plan,channel,fan,now=now,entry_id=self.entry_id,
            )
            if conflict is not None:
                self._status(area,"coordination_hold",entity_id=fan,
                             reason=conflict)
                continue
            if not self.hass.services.has_service("fan","set_percentage"):
                self._status(area,"fan_speed_service_unavailable")
                return
            try:
                await asyncio.wait_for(self.hass.services.async_call(
                    "fan","set_percentage",{"percentage":percentage},
                    target={"entity_id":fan},blocking=True),WRITE_TIMEOUT_S)
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.exception("Fan speed command failed for %s",fan)
                self._pause(area,"fan_speed_service_failure")
                return
            self.expected[fan]={"area":area,"when":now,"percentage":percentage}
            self.last_write[fan]=now
            self._save()
            did_any=True
            self._status(area,"fan_speed_increased",entity_id=fan,
                         new_percent=percentage)
        if not did_any and not attempted:
            self._status(area,"no_verified_fan_speed_demand")
