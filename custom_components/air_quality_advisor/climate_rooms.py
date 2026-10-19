"""Room-aware occupancy and climate diagnostics, independent of actuator writes."""
from __future__ import annotations
from typing import Any

from .climate_strategy import (capabilities,home_away_evidence,occupied_evidence,
                               policy)
from .discovery import entity_area, temperature_sensor_c, is_stale


def _bool_state(hass:Any,entity_id:str,*,max_age_minutes:float=15) -> bool|None:
    s=hass.states.get(entity_id)
    if s is None or s.state in ("unknown","unavailable","none"): return None
    if s.domain=="binary_sensor":
        if is_stale(s,max_age_minutes): return None
        return True if s.state=="on" else False if s.state=="off" else None
    if s.domain=="person":
        return s.state!="not_home" if s.state not in ("unknown","unavailable") else None
    if s.domain=="device_tracker":
        return s.state!="not_home" if s.state not in ("unknown","unavailable") else None
    return None


def _presence_ids(hass:Any,area:str,config:dict) -> list[str]:
    selected=config.get("occupancy_sensors")
    if isinstance(selected,list) and selected:
        return [x for x in selected if isinstance(x,str) and x.startswith("binary_sensor.")
                and entity_area(hass,x)==area]
    # Auto-discover only real presence/occupancy device_class in HA registry.
    result=[]
    for s in hass.states.async_all("binary_sensor"):
        if (entity_area(hass,s.entity_id)==area and
            str(s.attributes.get("device_class","")).casefold() in ("occupancy","presence")):
            result.append(s.entity_id)
    return sorted(result)


def gather(hass:Any,room:Any,settings:dict,*,prior_mode:str|None=None)->tuple[dict,set[str]]:
    """Expose what should happen, with provenance, without operating devices."""
    if not isinstance(settings,dict) or not settings.get("enabled"):
        return {"status":"disabled"},set()
    area=room.area_id
    sensors=_presence_ids(hass,area,settings)
    occupants=[_bool_state(hass,s) for s in sensors]
    occupied,occ_reason=occupied_evidence(occupants,unknown_policy=settings.get("unknown_occupancy","occupied"))
    tracker_ids=settings.get("away_entities",[])
    if not isinstance(tracker_ids,list): tracker_ids=[]
    trackers=[e for e in tracker_ids if isinstance(e,str) and e.startswith(("person.","device_tracker.","binary_sensor."))]
    at_home,home_reason=home_away_evidence([_bool_state(hass,x) for x in trackers],
                                           mode=settings.get("away_policy","any_home"))
    temperature_id=settings.get("temperature_entity")
    temp=temperature_sensor_c(hass,temperature_id,10) if isinstance(temperature_id,str) else None
    climate_id=settings.get("climate_entity")
    state=hass.states.get(climate_id) if isinstance(climate_id,str) and climate_id.startswith("climate.") else None
    cap=capabilities(state.attributes,state.state) if state else {"kind":"unavailable"}
    window_safe=bool(room.windows) and all(win.opened is False for win in room.windows)
    result=policy(settings,temp_c=temp,capability=cap,at_home=at_home,
                  occupied=occupied,sleeping=settings.get("sleep_active") is True,
                  manual_profile=settings.get("manual_profile"),prior_mode=prior_mode,
                  window_safe=window_safe)
    return {
        "status":result.state,
        "profile":result.profile,"mode":result.desired_hvac_mode,
        "temperature_target_c":result.temperature_c,
        "reason":result.reason,"controller":result.controller,
        "occupancy":occupied,"occupancy_evidence":occ_reason,
        "presence_entities":sensors,"away":at_home,"away_evidence":home_reason,
        "tracker_entities":trackers,
        "climate_entity":climate_id,"climate_capabilities":cap,
        "temperature_entity":temperature_id,"temperature_c":temp,
        "window_safe":window_safe,
        "automatic_actuation_enabled":False,
        "note":"advisory planner only: direct mode/PWM/relay commands require separate validated driver",
    },set(sensors+trackers+[x for x in (temperature_id,climate_id) if isinstance(x,str)])
