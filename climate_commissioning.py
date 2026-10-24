"""Read-only, privacy-minimal Home Assistant climate commissioning report.

Reports only explicitly selected room entities and their relevant native
capabilities/safety evidence; never reads registry serial numbers, device
identifiers, network addresses, credentials, automation secrets or tokens.
Never calls hass.services and never infers physical equipment certification.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any

from .climate_coordination import ROLE_KINDS, device_inventory, duplicate_owners
from .climate_entry_ownership import cross_entry_collisions
from .climate_air_mode_native import allowed_dwell
from .discovery import entity_area, reading, temperature_sensor_c

SENSORS = {
    "temperature_entity": "temperature",
    "humidity_entity": "humidity",
    "co2_entity": "co2",
    "pm25_entity": "pm25",
}


def _age_seconds(state: Any, now: float, attribute: str) -> int | None:
    value=getattr(state,attribute,None)
    if not isinstance(value,datetime) or value.tzinfo is None:
        return None
    age=now-value.timestamp()
    return round(age) if isfinite(age) and age>=0 else None


def room_commissioning(hass: Any, area: str, config: dict,
                       plan: dict | None = None, *,
                       now: float | None = None,
                       collisions: dict | None = None) -> dict:
    """Inspect one configured room without any device writes."""
    if now is None:
        now=datetime.now(timezone.utc).timestamp()
    plan=plan if isinstance(plan,dict) else {}
    config=config if isinstance(config,dict) else {}
    inventory=device_inventory(hass,area,config)
    devices=[]
    for role in ROLE_KINDS:
        item=inventory.get(role)
        if item is None:
            continue
        entity=item.get("entity_id")
        state=hass.states.get(entity) if isinstance(entity,str) else None
        modes=state.attributes.get("hvac_modes") if state else None
        devices.append({
            "role":role,
            "entity_id":entity,
            "status":item.get("status","unknown"),
            "state":str(state.state) if state else "missing",
            "area_verified":entity_area(hass,entity)==area if isinstance(entity,str) else False,
            "reported_modes":sorted({
                m for m in (modes if isinstance(modes,(tuple,list)) else [])
                if isinstance(m,str) and m in (
                    "off","heat","cool","heat_cool","auto","dry","fan_only"
                )
            }),
            "hvac_action":str(state.attributes.get("hvac_action") or "unknown") if state else "unknown",
            "device_class":str(state.attributes.get("device_class") or "unknown") if state else "unknown",
            "supported_features":(
                state.attributes.get("supported_features")
                if state and isinstance(state.attributes.get("supported_features"),int)
                and not isinstance(state.attributes["supported_features"],bool)
                else None
            ),
            "state_changed_age_seconds":_age_seconds(state,now,"last_changed"),
        })
    sensors=[]
    for role,metric in SENSORS.items():
        entity=config.get(role)
        if not isinstance(entity,str) or not entity:
            continue
        state=hass.states.get(entity)
        selected=reading(hass,entity,10,outdoor=False)
        value=(temperature_sensor_c(hass,entity,10)
               if metric=="temperature" else
               selected.value if selected.metric==metric else None)
        sensors.append({
            "role":role,"entity_id":entity,
            "status":("ready" if value is not None and
                      entity_area(hass,entity)==area else "unavailable_or_unverified"),
            "value":value if isinstance(value,(int,float)) and isfinite(value) else None,
            "unit":"°C" if metric=="temperature"
                   else "%" if metric=="humidity"
                   else "ppm" if metric=="co2" else "µg/m³",
            "last_report_age_seconds":_age_seconds(state,now,"last_reported")
               if _age_seconds(state,now,"last_reported") is not None
               else _age_seconds(state,now,"last_updated"),
        })
    windows=[]
    for state in hass.states.async_all("binary_sensor"):
        if (entity_area(hass,state.entity_id)==area and
                state.attributes.get("device_class")=="window"):
            windows.append({
                "entity_id":state.entity_id,
                "state":str(state.state),
                "closed_verified":state.state=="off",
            })
    windows.sort(key=lambda item:item["entity_id"])
    by_role={item["role"]:item for item in devices}
    target=by_role.get("dry_climate_entity",{})
    live_modes=target.get("reported_modes",[])
    dry_qualified=all((
        config.get("enabled") is True,
        config.get("allow_actuation") is True,
        config.get("dry_fan_mode_auto") is True,
        config.get("dry_fan_hardware_confirmed") is True,
        isinstance(config.get("humidity_entity"),str),
        "dry" in live_modes,
        "fan_only" in live_modes,
        target.get("status")=="ready",
        allowed_dwell(config) is not None,
        not (config.get("humidity_setpoint_auto") is True or
             config.get("humidity_power_auto") is True),
    ))
    blockers=[]
    if config.get("dry_fan_mode_auto") is True:
        if not dry_qualified:
            blockers.append("configuration_or_device_not_verified")
        if not windows and config.get("dry_fan_windowless_confirmed") is not True:
            blockers.append("no_verified_window_contact")
        if any(not window["closed_verified"] for window in windows):
            blockers.append("window_open_or_unknown")
        if any(sensor["role"]=="humidity_entity" and sensor["status"]!="ready"
               for sensor in sensors):
            blockers.append("humidity_sensor_invalid")
    roles_in_use={item["entity_id"] for item in devices}
    cross_room=sorted(roles_in_use.intersection(collisions or {}))
    if cross_room:
        blockers.append("equipment_assigned_to_multiple_rooms")
    return {
        "area_id":area,"enabled":config.get("enabled") is True,
        "controller":str(config.get("controller","device")),
        "mode":str(config.get("mode","auto")),
        "actuation_opted_in":config.get("allow_actuation") is True,
        "devices":devices,"sensors":sensors,"windows":windows,
        "native_dry_fan":{
            "requested":config.get("dry_fan_mode_auto") is True,
            "hardware_confirmed_by_user":config.get("dry_fan_hardware_confirmed") is True,
            "software_preflight_ready":dry_qualified and not blockers,
            "configured_mode_dwell_seconds":allowed_dwell(config),
            "blockers":blockers,
            "real_hardware_commissioned_by_integration":False,
        },
        "coordination":plan.get("coordination") if isinstance(
            plan.get("coordination"),dict) else {"status":"not_available"},
        "mode_advice":plan.get("native_air_mode_advice") if isinstance(
            plan.get("native_air_mode_advice"),dict) else {"status":"not_available"},
        "mode_actuation":plan.get("native_air_mode_actuation") if isinstance(
            plan.get("native_air_mode_actuation"),dict) else {"status":"not_available"},
    }


def report(hass: Any, configs: dict, plans: dict | None = None,
           *, area: str | None = None, now: float | None = None,
           entry_id: str | None = None) -> dict:
    """Return an explicitly requested, safe-to-share overview."""
    configs=configs if isinstance(configs,dict) else {}
    plans=plans if isinstance(plans,dict) else {}
    selected=sorted(key for key in configs if isinstance(key,str))
    if area is not None:
        if area not in configs:
            return {"status":"area_not_configured","read_only":True,
                    "requested_area":area,"rooms":[]}
        selected=[area]
    duplicates=duplicate_owners(configs)
    if entry_id is not None:
        duplicates.update(cross_entry_collisions(hass,entry_id,configs))
    rooms=[room_commissioning(hass,key,configs[key],plans.get(key),now=now,
                             collisions=duplicates)
           for key in selected if isinstance(configs.get(key),dict)]
    return {"schema_version":1,"status":"ok","read_only":True,
            "no_commands_sent":True,
            "physical_hardware_safety_verified":False,
            "rooms":rooms}
