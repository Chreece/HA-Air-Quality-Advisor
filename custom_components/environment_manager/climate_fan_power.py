"""Opt-in guarded power for dedicated native Home Assistant fan.* entities.

This driver never writes climate modes, generic switches, speed, direction or
presets. Only fan.turn_on / fan.turn_off with a single exact target is allowed.
No automatic ownership of an already-running fan, and any persisted owned
output must be manually reconciled OFF after restart.

Real ventilation/extraction fans may have fire, backdraft, pressure and air
exchange requirements beyond Home Assistant; independent hardware protection
and physical commissioning are mandatory before publishing this draft driver.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Callable

from .climate_coordination import duplicate_owners, device_inventory
from .const import DOMAIN
from .climate_arbitration import new_command_gate
from .climate_fan_native import FAN_ROLES
from .discovery import entity_area, reading
from .pid_math import finite

_LOGGER = logging.getLogger(__name__)
STARTUP_WARMUP_S = 300
WRITE_TIMEOUT_S = 20
ACK_TIMEOUT_S = 120


def dwell_settings(config: dict) -> tuple[float, float, float] | None:
    on = finite(config.get("fan_power_min_on_s", 300), 120, 3600)
    off = finite(config.get("fan_power_min_off_s", 300), 120, 7200)
    maximum = finite(config.get("fan_power_max_on_s", 14400), 900, 86400)
    if None in (on, off, maximum) or maximum <= on:
        return None
    return on, off, maximum


class FanPowerControl:
    """Persist entity-specific fan output ownership, acknowledgements and dwell."""

    def __init__(self, hass: Any, entry_id: str, *,
                 clock: Callable[[], float] | None = None,
                 changed: Callable[[], None] | None = None) -> None:
        self.hass, self.entry_id = hass, entry_id
        self.clock = clock or time.time
        self.changed = changed or (lambda: None)
        self.statuses: dict[str, dict] = {}
        self.paused: dict[str, str] = {}
        self.owned: dict[str, dict] = {}
        self.last_off: dict[str, float] = {}
        self.off_seen: dict[str, float] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._store = None
        self._active = False
        self._ready = False
        self._started: float | None = None
        self._configured: dict = {}

    def _snapshot(self) -> dict:
        return {"version": 1, "paused": self.paused,
                "owned": self.owned, "last_off": self.last_off}

    def _save(self) -> None:
        if self._store is not None:
            self._store.async_delay_save(self._snapshot, 3)

    def _status(self, area: str, status: str, **info: Any) -> None:
        item = {"status": status, **info}
        if self.statuses.get(area) != item:
            self.statuses[area] = item
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
                self.hass, 1, f"{DOMAIN}.fan_power_{self.entry_id}"
            )
            saved = await self._store.async_load()
        except Exception:
            _LOGGER.exception("Native fan power storage unavailable")
            return
        if isinstance(saved, dict) and saved.get("version") == 1:
            data = saved.get("paused", {})
            if isinstance(data, dict):
                self.paused = {a:r for a,r in data.items()
                               if isinstance(a,str) and isinstance(r,str)}
            data = saved.get("last_off", {})
            if isinstance(data, dict):
                self.last_off = {e:float(v) for e,v in data.items()
                                 if isinstance(e,str) and e.startswith("fan.")
                                 and finite(v,0,1e13) is not None}
            data = saved.get("owned", {})
            if isinstance(data, dict):
                for entity,record in data.items():
                    if (isinstance(entity,str) and entity.startswith("fan.")
                            and isinstance(record,dict)
                            and isinstance(record.get("area"),str)):
                        self.owned[entity]=dict(record)
                        self.paused[record["area"]]=(
                            "restart_requires_manual_fan_off_reconciliation"
                        )
        self._ready = True
        self._save()

    async def async_stop(self) -> None:
        self._active = False
        pending=tuple(self._tasks.values())
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending,return_exceptions=True)
        self._tasks.clear()
        if self._ready and self._store is not None:
            await self._store.async_save(self._snapshot())

    async def command(self, area: str, action: str) -> dict:
        if action not in ("pause","resume") or not self._ready:
            return {"accepted":False,"reason":"unsupported_action_or_unready"}
        job=self._tasks.get(area)
        if job is not None and not job.done():
            job.cancel()
            await asyncio.gather(job,return_exceptions=True)
        if action=="pause":
            self._pause(area,"user_paused")
            return {"accepted":True,"area":area,"action":action}
        for entity,record in list(self.owned.items()):
            if record.get("area")!=area:
                continue
            state=self.hass.states.get(entity)
            if state is None or state.state!="off":
                return {"accepted":False,"reason":"manual_fan_off_reconciliation_required"}
            self.owned.pop(entity,None)
            self.last_off[entity]=self.clock()
            self.off_seen[entity]=self.clock()
        self.paused.pop(area,None)
        self._started=self.clock()
        self._save()
        self._status(area,"startup_warmup")
        return {"accepted":True,"area":area,"action":action}

    def schedule(self, configs: dict, plans: dict) -> None:
        if not self._active or not self._ready or not isinstance(configs,dict):
            return
        self._configured=configs
        now=self.clock()
        selected=set(configs) | {v.get("area") for v in self.owned.values()}
        for area in selected:
            if not isinstance(area,str):
                continue
            cfg=configs.get(area, {})
            if not isinstance(cfg,dict):
                cfg={}
            has_owned=any(v.get("area")==area for v in self.owned.values())
            if not has_owned and not (
                cfg.get("enabled") is True and
                cfg.get("allow_actuation") is True and
                cfg.get("fan_power_auto") is True and
                cfg.get("fan_power_hardware_confirmed") is True
            ):
                self._status(area,"advisory_only")
                continue
            job=self._tasks.get(area)
            if job is not None and not job.done():
                continue
            job=self.hass.async_create_task(
                self._tick(area,cfg,plans.get(area,{}),now)
            )
            self._tasks[area]=job
            def done(task:asyncio.Task,key:str=area)->None:
                if self._tasks.get(key) is task:
                    self._tasks.pop(key,None)
                if not task.cancelled():
                    try:
                        task.result()
                    except Exception:
                        _LOGGER.exception("Unhandled fan power error for %s",key)
                        self._pause(key,"controller_exception")
            job.add_done_callback(done)

    def _need(self, area: str, cfg: dict, plan: dict,
              role: str, now: float) -> tuple[bool, str]:
        """Confirm both fresh planned outdoor/indoor policy and live source."""
        if not isinstance(plan,dict):
            return False,"missing_room_plan"
        evidence=finite(plan.get("air_evidence_at"),0,1e13)
        if evidence is None or not 0 <= now-evidence <= 120:
            return False,"air_quality_decision_expired"
        air=plan.get("air_actions",{})
        if not isinstance(air,dict) or air.get("status")!="advisory":
            return False,"unverified_air_policy"
        if role not in FAN_ROLES:
            return False,"unverified_role"
        purpose,metric,source_key,_ = FAN_ROLES[role]
        item=air.get(purpose,{})
        if not isinstance(item,dict) or (
            item.get("status")!="recommended" or
            item.get("speed_control_eligible") is not True or
            item.get("entity_id")!=cfg.get(role)
        ):
            return False,"no_valid_fan_demand"
        source=cfg.get(source_key)
        if not isinstance(source,str) or entity_area(self.hass,source)!=area:
            return False,"wrong_room_or_missing_source"
        live=reading(self.hass,source,10,outdoor=False)
        bound=finite(air.get("thresholds",{}).get(
            "co2_operational_ppm" if metric=="co2" else
            "pm25_short_term_action_ug_m3"
        ),0,20000)
        if live.metric!=metric or live.value is None or bound is None:
            return False,"measurement_missing_or_stale"
        if live.value < bound:
            return False,"measured_need_resolved"
        if role=="extraction_fan_entity":
            if air.get("outdoor_air_verified") is not True:
                return False,"outdoor_pollutant_data_unverified"
            if plan.get("window_safe") is not True:
                return False,"window_already_open_or_unknown"
        if role=="purifier_fan_entity" and cfg.get("pm25_sensor_verified") is not True:
            return False,"pm25_sensor_not_attested"
        return True,"measured_fan_demand"

    async def _send(self, area: str, entity: str,
                    record: dict, power: str, now: float) -> bool:
        service="turn_on" if power=="on" else "turn_off"
        try:
            if not self.hass.services.has_service("fan",service):
                self._status(area,"fan_power_service_missing",service=service)
                return False
            await asyncio.wait_for(self.hass.services.async_call(
                "fan",service,{},target={"entity_id":entity},blocking=True
            ),WRITE_TIMEOUT_S)
        except asyncio.CancelledError:
            raise
        except Exception:
            self._pause(area,"fan_power_command_failed")
            return False
        record.update({"power":power,"when":now,"acknowledged":False})
        self.owned[entity]=record
        self._save()
        self._status(area,"fan_power_commanded",entity_id=entity,action=service)
        return True

    async def _tick(self, area: str, cfg: dict, plan: dict, now: float) -> None:
        if not self._active or not self._ready:
            return
        interval=dwell_settings(cfg)
        # Incorrect new settings may block NEW starts, but cannot strand a
        # previously owned output whose original safe dwell was persisted.
        on_min,off_min,max_on=(interval if interval is not None
                              else (None,None,None))
        roles=[role for role in FAN_ROLES if isinstance(cfg.get(role),str)]
        devices=[cfg[role] for role in roles]
        duplicates=duplicate_owners(self._configured)
        # Reconcile equipment we actually own before any new-ownership
        # checks. A duplicate configuration must not bypass the bounded
        # OFF/reconciliation path for a previously commanded output.
        active_owned=[(e,r) for e,r in self.owned.items() if r.get("area")==area]
        for entity,record in active_owned:
            original_on=finite(record.get("min_on_s"),120,3600)
            original_max=finite(record.get("max_on_s"),900,86400)
            if (original_on is None or original_max is None or
                    original_max<=original_on):
                if interval is None or not cfg:
                    self._pause(area,"original_fan_dwell_unknown_reconcile_manually")
                    continue
                original_on,_,original_max=interval
            await self._owned_tick(area,cfg,plan,entity,record,now,
                                   original_on,original_max)
        if active_owned:
            # Never override owned-device safety status with "advisory only",
            # nor start a new fan while a prior ON/OFF is still reconciling.
            return
        if area in self.paused:
            self._status(area,"paused",reason=self.paused[area])
            return
        if interval is None:
            self._status(area,"invalid_fan_power_timing")
            return
        if len(devices)!=len(set(devices)) or any(e in duplicates for e in devices):
            self._status(area,"duplicate_fan_owner")
            return
        if not (cfg.get("enabled") is True and cfg.get("allow_actuation") is True
                and cfg.get("fan_power_auto") is True
                and cfg.get("fan_power_hardware_confirmed") is True
                and cfg.get("fan_speed_auto") is not True):
            self._status(area,"advisory_only_or_conflicting_driver")
            return
        if now-(self._started if self._started is not None else now)<STARTUP_WARMUP_S:
            self._status(area,"startup_warmup")
            return
        live=device_inventory(self.hass,area,cfg)
        for role in roles:
            entity=cfg[role]
            if entity in self.owned:
                continue
            if live.get(role,{}).get("status")!="ready":
                self._status(area,"fan_unavailable_or_wrong_room",entity_id=entity)
                continue
            needed,reason=self._need(area,cfg,plan,role,now)
            if not needed:
                self._status(area,reason,entity_id=entity)
                continue
            state=self.hass.states.get(entity)
            if state is None or state.state not in ("on","off"):
                self._status(area,"fan_power_unknown",entity_id=entity)
                continue
            if state.state=="on":
                self._pause(area,"already_running_fan_is_manual")
                return
            if state.attributes.get("preset_mode") not in (None,"","none","manual"):
                self._status(area,"native_fan_preset_active",entity_id=entity)
                continue
            self.off_seen.setdefault(entity,now)
            last_off=self.last_off.get(entity,self.off_seen[entity])
            changed=getattr(state,"last_changed",None)
            if isinstance(changed,datetime) and changed.tzinfo is not None:
                stamp=changed.timestamp()
                if stamp>now or now-stamp<off_min:
                    self._status(area,"recent_fan_state_change",entity_id=entity)
                    continue
            if now<last_off or now-max(last_off,self.off_seen[entity])<off_min:
                self._status(area,"minimum_fan_off_hold",entity_id=entity)
                continue
            purpose=("extraction" if role=="extraction_fan_entity"
                     else "filtration")
            conflict=new_command_gate(
                self.hass,area,cfg,plan,purpose,entity,now=now,entry_id=self.entry_id,
            )
            if conflict is not None:
                self._status(area,"coordination_hold",entity_id=entity,
                             reason=conflict)
                continue
            record={"entity_id":entity,"area":area,"role":role,
                    "power":"off","when":now,"acknowledged":True,
                    "min_on_s":on_min,"max_on_s":max_on}
            if not await self._send(area,entity,record,"on",now):
                return

    async def _owned_tick(self, area: str, cfg: dict, plan: dict,
                          entity: str, record: dict,
                          now: float, min_on: float, max_on: float) -> None:
        role=record.get("role")
        state=self.hass.states.get(entity)
        if (not entity.startswith("fan.") or role not in FAN_ROLES or
                record.get("area")!=area or
                state is None or entity_area(self.hass,entity)!=area or
                state.state not in ("on","off")):
            self._pause(area,"owned_fan_state_unverifiable")
            return
        expected=record.get("power")
        stamp=finite(record.get("when"),0,1e13)
        if expected not in ("on","off") or stamp is None or stamp>now:
            self._pause(area,"fan_command_history_invalid")
            return
        if state.state!=expected:
            if now-stamp<ACK_TIMEOUT_S:
                self._status(area,"waiting_for_fan_power_ack",entity_id=entity)
            else:
                self._pause(area,"manual_fan_power_or_unacknowledged_write")
            return
        if not record.get("acknowledged"):
            record["acknowledged"]=True
            self._save()
        if expected=="off":
            self.owned.pop(entity,None)
            self.last_off[entity]=stamp
            self.off_seen[entity]=now
            self._save()
            self._status(area,"fan_power_off_acknowledged",entity_id=entity)
            return
        if area in self.paused and self.paused[area]!="user_paused":
            self._status(area,"paused",reason=self.paused[area])
            return
        if now-stamp>=max_on:
            if await self._send(area,entity,record,"off",now):
                self._pause(area,"maximum_owned_fan_runtime_exceeded")
            return
        active=(cfg.get("enabled") is True and
                cfg.get("allow_actuation") is True and
                cfg.get("fan_power_auto") is True and
                cfg.get("fan_power_hardware_confirmed") is True and
                cfg.get("fan_speed_auto") is not True)
        needed,why=self._need(area,cfg,plan,role,now) if active else (False,"disabled")
        if needed:
            purpose=("extraction" if role=="extraction_fan_entity"
                     else "filtration")
            conflict=new_command_gate(
                self.hass,area,cfg,plan,purpose,entity,now=now,entry_id=self.entry_id,
            )
            if conflict is not None:
                needed=False
                why=conflict
        if needed and area not in self.paused:
            self._status(area,"owned_fan_running",entity_id=entity)
            return
        if now-stamp<min_on:
            self._status(area,"minimum_fan_on_hold",entity_id=entity,
                         remaining_s=round(min_on-(now-stamp)))
            return
        await self._send(area,entity,record,"off",now)
