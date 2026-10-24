"""Conservative climate-native target controller; no relay/PWM writes.

Only explicit opted-in same-room climate.* with native single-setpoint support.
A native thermostat retains compressor protection. No power-off command is sent
just because the room enters the heating/cooling comfort deadband.
"""
from __future__ import annotations
import asyncio
import logging
import time
from datetime import datetime
from typing import Any

from .pid_math import bounded_command, target_from_unit, finite
from .climate_arbitration import new_command_gate
from .discovery import entity_area, temperature_sensor_c
from .const import DOMAIN

_LOGGER=logging.getLogger(__name__)
MODE_DWELL_SECONDS=1800
STARTUP_WARMUP_SECONDS=300
WRITE_TIMEOUT_SECONDS=20
MANUAL_GRACE_SECONDS=120


class NativeClimateControl:
    def __init__(self,hass:Any,entry_id:str,*,clock=None):
        self.hass=hass
        self.entry_id=entry_id
        self.clock=clock or time.time
        self.statuses={}
        self.paused={}
        self.expected={}
        self.expected_hvac={}
        self.off_intent={}
        self._configured={}
        self._planned={}
        self.last_mode={}
        self.last_write={}
        self._store=None
        self.ready=False
        self.started=None
        self._tasks={}
        self._active=False

    async def async_start(self):
        self._active=True
        self.started=self.clock()
        try:
            from homeassistant.helpers.storage import Store
            self._store=Store(self.hass,1,f"{DOMAIN}.climate_native_{self.entry_id}")
            loaded=await self._store.async_load()
        except Exception:
            _LOGGER.exception("Climate mode safety state unavailable; native actuation blocked")
            return
        if isinstance(loaded,dict) and loaded.get("version")==1:
            p=loaded.get("paused",{})
            if isinstance(p,dict):
                self.paused={k:v for k,v in p.items() if isinstance(k,str) and isinstance(v,str)}
            lm=loaded.get("last_mode",{})
            if isinstance(lm,dict):
                self.last_mode={k:float(v) for k,v in lm.items() if isinstance(v,(float,int))}
            ew=loaded.get("expected",{})
            if isinstance(ew,dict):
                self.expected={k:v for k,v in ew.items() if isinstance(k,str) and isinstance(v,dict)}
            expected_mode=loaded.get("expected_hvac",{})
            if isinstance(expected_mode,dict):
                self.expected_hvac={k:v for k,v in expected_mode.items() if isinstance(k,str) and v in ("heat","cool")}
            lw=loaded.get("last_write",{})
            if isinstance(lw,dict):
                self.last_write={k:float(v) for k,v in lw.items() if isinstance(v,(float,int))}
            previous=loaded.get("off_intent",{})
            if not isinstance(previous,dict) or any(
                not isinstance(area,str) or not isinstance(value,dict)
                or value.get("phase") not in ("intent","commanded")
                for area,value in previous.items()
            ):
                _LOGGER.error("Unrecognized native OFF history; output commands disabled")
                self._active=False
                return
            self.off_intent={k:dict(v) for k,v in previous.items()}
            for area in self.off_intent:
                self.paused[area]="native_off_requires_manual_reconciliation"
        self.ready=True

    def _snapshot(self):
        return {"version":1,"paused":dict(self.paused),"last_mode":dict(self.last_mode),
                "expected":{k:dict(v) for k,v in self.expected.items()},
                "expected_hvac":dict(self.expected_hvac),
                "off_intent":{k:dict(v) for k,v in self.off_intent.items()},
                "last_write":dict(self.last_write)}

    def _save(self):
        if self._store is not None:
            self._store.async_delay_save(self._snapshot,3)

    async def async_stop(self):
        self._active=False
        tasks=list(self._tasks.values())
        for task in tasks:task.cancel()
        if tasks:await asyncio.gather(*tasks,return_exceptions=True)
        self._tasks.clear()
        if self.ready and self._store is not None:
            await self._store.async_save(self._snapshot())

    async def command(self,area:str,action:str)->dict:
        if action not in ("pause","resume"):
            return {"accepted":False,"reason":"unsupported_action"}
        task=self._tasks.get(area)
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
        if action=="pause":
            self.paused[area]="user_paused"
        else:
            old=self.off_intent.get(area)
            if isinstance(old,dict):
                entity=old.get("entity_id")
                current=self.hass.states.get(entity) if isinstance(entity,str) else None
                changed=getattr(current,"last_changed",None)
                now=self.clock()
                if not (current is not None and current.state=="off" and
                        isinstance(changed,datetime) and changed.tzinfo is not None and
                        0<=now-changed.timestamp() and now-changed.timestamp()>=1800):
                    return {"accepted":False,"reason":"native_output_must_be_verified_off_30_minutes"}
                self.off_intent.pop(area,None)
            self.paused.pop(area,None)
            self.expected.pop(area,None)
            self.expected_hvac.pop(area,None)
            self.last_write.pop(area,None)
            # Resume always warms up before any new command.
            self.started=self.clock()
        self._save()
        return {"accepted":True,"area":area,"action":action}

    def schedule(self,config:dict,plans:dict,*,pid_rooms:dict|None=None):
        if not self._active or not self.ready or not isinstance(config,dict):
            return
        now=self.clock()
        self._configured=config
        self._planned=plans
        owners={}
        pid_owners=set()
        for pid in (pid_rooms or {}).values():
            if not isinstance(pid,dict) or not pid.get("enabled"):continue
            values=pid.get("climate_entities",[])
            if isinstance(values,list):
                pid_owners.update(x for x in values if isinstance(x,str))
        for area,room in config.items():
            if isinstance(room,dict) and room.get("allow_actuation") is True:
                entity=room.get("climate_entity")
                owners[entity]=owners.get(entity,0)+1
        for area,settings in config.items():
            if not isinstance(settings,dict) or settings.get("allow_actuation") is not True:
                self.statuses[area]={"status":"advisory_only"}
                continue
            report=plans.get(area,{})
            if not settings.get("enabled"):
                self.statuses[area]={"status":"disabled"}
                continue
            if area in self.paused:
                self.statuses[area]={"status":"paused","reason":self.paused[area]}
                continue
            entity=settings.get("climate_entity")
            if (not isinstance(entity,str) or owners.get(entity)!=1 or
                entity in pid_owners or
                (pid_rooms or {}).get(area,{}).get("enabled")):
                self.statuses[area]={"status":"conflicting_controller"}
                continue
            if settings.get("controller")=="environment":
                # Environmental-only rooms use independent humidity/fan
                # drivers; no primary thermostat exists or should be commanded.
                self.statuses[area]={"status":"advisory_only"}
                continue
            if settings.get("controller")!="device":
                self.statuses[area]={"status":"unsupported_control_method"}
                continue
            if now-(self.started or now)<STARTUP_WARMUP_SECONDS:
                self.statuses[area]={"status":"startup_warmup"}
                continue
            if now-self.last_write.get(area,0)<300:
                continue
            t=self._tasks.get(area)
            if t and not t.done():continue
            task=self.hass.async_create_task(self._apply(area,settings,report,now))
            self._tasks[area]=task
            def done(t,area=area):
                if self._tasks.get(area) is t:self._tasks.pop(area,None)
                if not t.cancelled():
                    try:t.result()
                    except Exception:
                        _LOGGER.exception("Native climate controller exception in %s",area)
                        self.paused[area]="unexpected_task_exception"
                        self._save()
            task.add_done_callback(done)

    async def _absence_off(self,area:str,settings:dict,report:dict,now:float)->bool:
        """Physically OFF only a specific, explicitly commissioned native HVAC.

        Never switches equipment back on; it remains OFF until a user restarts
        it manually. A durable intent is saved before a compressor-affecting
        OFF request, so interruption cannot cause an unsafe automatic retry.
        """
        entity=settings.get("climate_entity")
        # Absence OFF deliberately bypasses the normal setpoint command gate.
        # Therefore it must independently enforce the *current* selection:
        # an old commissioned device may never be switched OFF after removal.
        selected=settings.get("selected_devices")
        if isinstance(selected,list) and entity not in selected:
            self.statuses[area]={"status":"device_not_selected"}
            return True
        devices=settings.get("device_settings",{})
        device=devices.get(entity,{}) if isinstance(devices,dict) else {}
        if not isinstance(device,dict) or device.get("auto_control") is not True:
            return False
        from .occupancy_policy import device_permission, live_device_permission
        decision,reason=device_permission(
            device,report.get("occupancy","unknown"),
            report.get("away","home"),report.get("sleeping"),
        )
        if decision!="absent":
            return False
        live_decision,_=live_device_permission(
            self.hass,area,settings,report,device,
        )
        if live_decision!="absent":
            self.statuses[area]={"status":"presence_changed_before_off"}
            return True
        self.statuses[area]={"status":"presence_hold","reason":reason}
        if device.get("absence_action")!="off":
            return True
        if not (
            settings.get("allow_actuation") is True and
            settings.get("enabled") is True and
            device.get("hardware_confirmed") is True and
            device.get("presence_requirement") in ("home","room") and
            isinstance(entity,str) and entity.startswith("climate.") and
            entity_area(self.hass,entity)==area and self._store is not None
        ):
            self.statuses[area]={"status":"uncommissioned_absence_off"}
            return True
        from .climate_entry_ownership import foreign_owner_hold
        if foreign_owner_hold(self.hass,self.entry_id,entity) is not None:
            self.statuses[area]={"status":"foreign_equipment_owner"}
            return True
        state=self.hass.states.get(entity)
        if state is None or state.state in ("unknown","unavailable"):
            return True
        if state.state=="off":
            self.statuses[area]={"status":"native_already_off"}
            return True
        modes=state.attributes.get("hvac_modes")
        # DRY/defrost/heating+cooling sharing require actual device safety
        # verification, and are NOT automatically powered down here.
        if (state.state not in ("heat","cool") or not isinstance(modes,list)
                or "off" not in modes or
                state.attributes.get("hvac_action") in ("defrosting","drying")):
            self.statuses[area]={"status":"native_absence_off_mode_unsupported"}
            return True
        last=getattr(state,"last_changed",None)
        if (not isinstance(last,datetime) or last.tzinfo is None or
                now-last.timestamp()<MODE_DWELL_SECONDS or
                now-last.timestamp()<0 or
                now-self.last_mode.get(area,self.started or now)<MODE_DWELL_SECONDS):
            self.statuses[area]={"status":"native_absence_off_wait_dwell"}
            return True
        # One exact room/device. Persist intent before any HA physical call.
        self.off_intent[area]={"entity_id":entity,"phase":"intent","when":now}
        try:
            await self._store.async_save(self._snapshot())
        except asyncio.CancelledError:
            raise
        except Exception:
            self.paused[area]="native_off_intent_storage_failed"
            self._save()
            return True
        # A new options flow/room plan may revoke the stale command while
        # Store.save awaits I/O. Keep the saved intent for human reconciliation.
        if (not self._active or settings!=self._configured.get(area) or
                self._planned.get(area) is not report or area in self.paused or
                entity_area(self.hass,entity)!=area or
                foreign_owner_hold(self.hass,self.entry_id,entity) is not None or
                live_device_permission(self.hass,area,settings,report,device)[0]!="absent"):
            self.paused[area]="native_off_permission_revoked_after_intent"
            self._save()
            return True
        latest=self.hass.states.get(entity)
        changed=getattr(latest,"last_changed",None)
        if (latest is None or latest.state!=state.state or
                not isinstance(changed,datetime) or changed.tzinfo is None or
                now-changed.timestamp()<MODE_DWELL_SECONDS):
            self.paused[area]="native_off_state_changed_after_intent"
            self._save()
            return True
        try:
            if not self.hass.services.has_service("climate","set_hvac_mode"):
                raise RuntimeError("Native HVAC OFF service unavailable")
            await asyncio.wait_for(
                self.hass.services.async_call("climate","set_hvac_mode",
                    {"hvac_mode":"off"},target={"entity_id":entity},
                    blocking=True),WRITE_TIMEOUT_SECONDS
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.exception("Failed commissioned native absence OFF for %s",entity)
            self.paused[area]="native_off_service_unacknowledged"
            self._save()
            return True
        self.off_intent[area]["phase"]="commanded"
        self.last_mode[area]=now
        self.last_write[area]=now
        self.paused[area]="native_off_requires_manual_reconciliation"
        try:
            await self._store.async_save(self._snapshot())
        except asyncio.CancelledError:
            raise
        except Exception:
            self.off_intent[area]["phase"]="intent"
            self.paused[area]="native_off_ack_storage_failed"
            self._save()
        self.statuses[area]={"status":"native_off_requested_for_absence"}
        return True

    async def _apply(self,area:str,settings:dict,report:dict,now:float):
        if not self._active or area in self.paused:return
        if await self._absence_off(area,settings,report,now):
            return
        if report.get("status")!="ready" or report.get("window_safe") is not True:
            self.statuses[area]={"status":"hold","reason":report.get("reason","no_valid_plan")}
            return
        # Revalidate the live room-temperature source, not just the cached
        # recommendation. An explicitly chosen heat mode cannot skip this gate.
        source=settings.get("temperature_entity")
        if (not isinstance(source,str) or entity_area(self.hass,source)!=area or
                temperature_sensor_c(self.hass,source,10) is None):
            self.statuses[area]={"status":"temperature_stale_or_wrong_room"}
            return
        mode=report.get("mode")
        entity=settings.get("climate_entity")
        # Device-specific profile targets override shared room bands, but
        # cannot change the controller's native safety or capability checks.
        device=(settings.get("device_settings",{}).get(entity,{})
                if isinstance(settings.get("device_settings"),dict) else {})
        if isinstance(device,dict) and device.get("auto_control") is True:
            profile=report.get("profile")
            if profile not in ("home","unoccupied","away","sleep"):
                profile="home"
            if profile=="sleep" and device.get("sleep_behavior")!="sleep_targets":
                profile="home"
            if mode in ("heat","cool"):
                desired=finite(device.get(f"{profile}_{mode}_c"),5,40)
                if desired is not None:
                    report={**report,"temperature_target_c":desired}
            elif mode=="heat_cool":
                low=finite(device.get(f"{profile}_heat_c"),5,35)
                high=finite(device.get(f"{profile}_cool_c"),6,40)
                if low is not None and high is not None and high-low>=1:
                    report={**report,"low_target_c":low,"high_target_c":high}
        if mode in ("heat","cool","heat_cool"):
            conflict=new_command_gate(
                self.hass,area,settings,report,"thermal",entity,now=now,entry_id=self.entry_id,
            )
            if conflict is not None:
                self.statuses[area]={"status":"coordination_hold","reason":conflict}
                return
        # Recheck live ownership and contacts immediately before every write.
        # The advisory plan can be older than the last entity/area change.
        if (not isinstance(entity,str) or not entity.startswith("climate.") or
                entity_area(self.hass,entity)!=area):
            self.statuses[area]={"status":"climate_target_wrong_room"}
            return
        contacts=report.get("window_contacts")
        if contacts is not None:
            if not isinstance(contacts,list):
                self.statuses[area]={"status":"window_contacts_invalid"}
                return
            for contact in contacts:
                current=self.hass.states.get(contact)
                if (not isinstance(contact,str) or current is None or
                        current.domain!="binary_sensor" or
                        current.attributes.get("device_class")!="window" or
                        current.state!="off" or entity_area(self.hass,contact)!=area):
                    self.statuses[area]={"status":"window_changed_since_plan"}
                    return
        # Explicit extra native equipment must not silently oppose this
        # thermostat. Its state can change between capture and command.
        for key in ("heat_climate_entity","cool_climate_entity",
                    "dry_climate_entity","fan_climate_entity"):
            other=settings.get(key)
            if not other or other==entity:
                continue
            if (not isinstance(other,str) or not other.startswith("climate.") or
                    entity_area(self.hass,other)!=area):
                self.statuses[area]={"status":"competing_climate_wrong_room"}
                return
            observed=self.hass.states.get(other)
            if observed is None or observed.state in ("unknown","unavailable"):
                self.statuses[area]={"status":"competing_climate_unavailable"}
                return
            other_mode=observed.state
            action=observed.attributes.get("hvac_action")
            # Heat/cool/auto/DRY can self-restart even while currently idle.
            if ((mode=="heat" and other_mode in ("cool","heat_cool","auto","dry")) or
                (mode=="cool" and other_mode in ("heat","heat_cool","auto")) or
                (mode=="heat_cool" and other_mode not in ("off","fan_only")) or
                action in ("heating","cooling","drying","preheating") or
                (other_mode!="off" and action is None)):
                self.statuses[area]={"status":"competing_climate_active_or_armed"}
                return
        if mode=="heat_cool":
            from .climate_range import async_apply_native_range
            await async_apply_native_range(self,area,settings,report,now)
            return
        target=finite(report.get("temperature_target_c"),5,36)
        if mode=="off" or target is None:
            self.statuses[area]={"status":"comfort_deadband_no_command"}
            return
        state=self.hass.states.get(entity)
        if state is None or state.state in ("unknown","unavailable"):
            self.statuses[area]={"status":"unavailable"}
            return
        attrs=state.attributes
        prior_commanded_mode=self.expected_hvac.get(area)
        if prior_commanded_mode and state.state!=prior_commanded_mode:
            self.paused[area]="manual_hvac_mode_change_or_unacknowledged_write"
            self._save()
            self.statuses[area]={"status":"paused","reason":self.paused[area]}
            return
        modes=attrs.get("hvac_modes",[])
        if not isinstance(modes,list) or mode not in modes:
            self.statuses[area]={"status":"unsupported_mode"}
            return
        try:features=int(attrs.get("supported_features",0))
        except (TypeError,ValueError):features=0
        if features&1==0:
            self.statuses[area]={"status":"no_single_setpoint"}
            return
        preset=str(attrs.get("preset_mode") or "").casefold()
        if preset not in ("","none","manual"):
            self.statuses[area]={"status":"native_preset_active","preset":preset}
            return
        if state.state not in ("heat","cool","off",mode):
            self.paused[area]="unexpected_mode"
            self._save()
            return
        expected=self.expected.get(area)
        observed=finite(attrs.get("temperature"),-30,150)
        if observed is None:
            self.statuses[area]={"status":"target_unavailable"}
            return
        unit=str(attrs.get("temperature_unit") or "")
        if unit not in ("°C","C","°F","F"):
            self.statuses[area]={"status":"unsupported_unit"}
            return
        if expected:
            last=finite(expected.get("when"),0,1e13)
            desired=finite(expected.get("temperature"),-30,150)
            if last is None or desired is None:
                self.paused[area]="invalid_ack_state"
            elif (step_size:=finite(attrs.get("target_temp_step"),0.1,10)) is None:
                self.statuses[area]={"status":"device_step_unknown"}
                return
            elif abs(observed-desired)>max(.05,step_size*.51):
                if now-last<MANUAL_GRACE_SECONDS:
                    self.statuses[area]={"status":"waiting_for_ack"}
                    return
                self.paused[area]="manual_setpoint_or_unacknowledged_write"
            if area in self.paused:
                self._save()
                return
        # Explicitly opted in to automatic HVAC mode switching; do not turn
        # hardware off within the deadband. Enforce full dwell period.
        if state.state!=mode:
            # An OFF thermostat is a user/hardware stop. Never autonomously
            # restart it even when automatic heat/cool mode selection is opted in.
            if state.state=="off":
                self.paused[area]="thermostat_turned_off"
                self._save()
                return
            if settings.get("auto_switch_hvac") is not True:
                self.statuses[area]={"status":"mode_mismatch_auto_switch_disabled"}
                return
            if now-self.last_mode.get(area,self.started or now)<MODE_DWELL_SECONDS:
                self.statuses[area]={"status":"mode_dwell"}
                return
            if not self.hass.services.has_service("climate","set_hvac_mode"):
                self.statuses[area]={"status":"mode_service_missing"}
                return
            try:
                await asyncio.wait_for(
                    self.hass.services.async_call("climate","set_hvac_mode",
                        {"hvac_mode":mode},target={"entity_id":entity},blocking=True),
                    WRITE_TIMEOUT_SECONDS)
            except asyncio.CancelledError: raise
            except Exception:
                _LOGGER.exception("Climate mode command failed for %s",entity)
                self.paused[area]="mode_service_failure"
                self._save()
                return
            self.last_mode[area]=now
            self.expected_hvac[area]=mode
            self.last_write[area]=now
            self._save()
            self.statuses[area]={"status":"mode_commanded","mode":mode,
                                 "note":"wait_for_device_ack_before_target"}
            return
        if not self.hass.services.has_service("climate","set_temperature"):
            self.statuses[area]={"status":"temperature_service_unavailable"}
            return
        observed_c=target_from_unit(observed,unit)
        if observed_c is None:return
        device_min=finite(attrs.get("min_temp"),-30,140)
        device_max=finite(attrs.get("max_temp"),-29,150)
        device_step=finite(attrs.get("target_temp_step"),0.1,10)
        if None in (device_min,device_max,device_step):
            self.statuses[area]={"status":"device_limits_unknown"}
            return
        status,native=bounded_command(target,observed_c,max_change_c=.5,
            min_change_c=.15,unit=unit,
            device_min=device_min,device_max=device_max,
            device_step=device_step)
        if status=="no_meaningful_change":
            self.statuses[area]={"status":"at_setpoint","mode":mode,"target_c":target}
            return
        if status!="command" or native is None:
            self.statuses[area]={"status":status}
            return
        try:
            await asyncio.wait_for(
                self.hass.services.async_call("climate","set_temperature",
                    {"temperature":native},target={"entity_id":entity},blocking=True),
                WRITE_TIMEOUT_SECONDS)
        except asyncio.CancelledError:raise
        except Exception:
            _LOGGER.exception("Native climate setpoint failed for %s",entity)
            self.paused[area]="setpoint_service_failure"
            self._save()
            return
        self.expected[area]={"temperature":native,"when":now}
        self.last_write[area]=now
        self._save()
        self.statuses[area]={"status":"setpoint_commanded","mode":mode,
            "target_c":target,"device_setpoint":native}
