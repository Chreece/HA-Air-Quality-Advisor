"""Room-aware occupancy and climate diagnostics, independent of actuator writes."""
from __future__ import annotations
from typing import Any
from datetime import datetime, timezone
import time
from .climate_schedule import scheduled_sleep
from .climate_hvac_modes import native_air_mode_advice
from .climate_coordination import (assigned_entities, room_equipment_plan,
                                   device_inventory, planning_capabilities)

from .climate_strategy import (capabilities,home_away_evidence,occupied_evidence,
                               policy)
from .discovery import entity_area, temperature_sensor_c, is_stale


def _bool_state(hass:Any,entity_id:str,*,max_age_minutes:float=240) -> bool|None:
    s=hass.states.get(entity_id)
    if s is None or s.state in ("unknown","unavailable","none"): return None
    if s.domain=="binary_sensor":
        if is_stale(s,max_age_minutes): return None
        return True if s.state=="on" else False if s.state=="off" else None
    if s.domain in ("person","device_tracker"):
        # HA's non-home named zones are away (work, school, etc.).
        # Only the literal state 'home' counts as home presence.
        if s.state=="home": return True
        if s.state=="not_home" or (
            isinstance(s.state,str) and s.state
            not in ("home","unknown","unavailable","none")
        ): return False
        return None
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


def gather(hass:Any,room:Any,settings:dict,*,prior_mode:str|None=None,
           now:float|None=None,comfort_target_c:float|None=None,
           outdoor_safe:bool|None=None,duplicate_equipment:dict|None=None,
           require_window_contact:bool=False,
           global_presence:dict|None=None,
           known_areas:set[str]|None=None,
           selected_temperature_c:float|None=None,
           temperature_evidence:dict|None=None)->tuple[dict,set[str]]:
    """Expose what should happen, with provenance, without operating devices."""
    if not isinstance(settings,dict) or not settings.get("enabled"):
        return {"status":"disabled"},set()
    area=room.area_id
    sensors=_presence_ids(hass,area,settings)
    age_limit=settings.get("occupancy_stale_minutes",240)
    try: age_limit=float(age_limit)
    except (ValueError,TypeError,OverflowError): age_limit=240
    if not 10<=age_limit<=1440: age_limit=240
    occupants=[_bool_state(hass,s,max_age_minutes=age_limit) for s in sensors]
    occupied,occ_reason=occupied_evidence(
        occupants,unknown_policy=settings.get("unknown_occupancy","occupied")
    )
    # An instantaneous 'no motion' does not prove a vacant room. Wait until
    # EVERY selected presence sensor has remained OFF for the chosen interval.
    if occupied=="unoccupied":
        try: delay=float(settings.get("unoccupied_delay_minutes",10))
        except (ValueError,TypeError,OverflowError): delay=10
        if not 0<=delay<=240: delay=10
        if delay > 0:
            clock=time.time() if now is None else now
            for entity in sensors:
                state=hass.states.get(entity)
                changed=(getattr(state,"last_changed",None) or
                         getattr(state,"last_updated",None))
                if not isinstance(changed,datetime) or changed.tzinfo is None:
                    occupied,occ_reason="occupied","off_duration_unverified"
                    break
                seconds=clock-changed.timestamp()
                if seconds<0 or seconds<delay*60:
                    occupied,occ_reason="occupied","awaiting_stable_unoccupied_period"
                    break
    # The shared configuration may supply an authoritative occupied-rooms
    # list in an entity state/attribute, global area sensors and trackers.
    # Missing evidence never becomes a negative/off signal.
    if isinstance(global_presence,dict) and global_presence:
        from .occupancy_policy import room_presence, home_presence
        occupied,occ_reason,sensors=room_presence(
            hass,area,settings,global_presence,
            known_areas=known_areas or {area},
        )
        if occupied == "unoccupied":
            # A room-list entity can change while the last person leaves.
            # Require a stable empty indication over the same vacancy delay
            # used for individual room presence sensors.
            delay = settings.get("unoccupied_delay_minutes", 10)
            try:
                delay = float(delay)
            except (ValueError,TypeError,OverflowError):
                delay = 10.
            if not 0 <= delay <= 240:
                delay = 10.
            sources = list(sensors)
            if isinstance(global_presence.get("occupied_rooms_entity"),str):
                sources.append(global_presence["occupied_rooms_entity"])
            now_clock=time.time() if now is None else now
            for source in sources:
                state = hass.states.get(source)
                if source == global_presence.get("occupied_rooms_entity") and (
                    global_presence.get("occupied_rooms_attribute")
                ):
                    # Home Assistant updates attributes without changing the
                    # entity's state. Use the attribute update time for dwell.
                    changed = getattr(state, "last_updated", None)
                else:
                    changed = (getattr(state,"last_changed",None) or
                               getattr(state,"last_updated",None))
                if (not isinstance(changed,datetime) or changed.tzinfo is None
                        or not 0<=now_clock-changed.timestamp()
                        or now_clock-changed.timestamp()<delay*60):
                    occupied,occ_reason="unknown","awaiting_stable_unoccupied_period"
                    break
    tracker_ids=settings.get("away_entities",[])
    if not isinstance(tracker_ids,list): tracker_ids=[]
    trackers=[e for e in tracker_ids if isinstance(e,str) and e.startswith(("person.","device_tracker.","binary_sensor."))]
    at_home,home_reason=home_away_evidence([_bool_state(hass,x) for x in trackers],
                                           mode=settings.get("away_policy","any_home"))
    if isinstance(global_presence,dict) and global_presence:
        at_home,home_reason,trackers=home_presence(hass,global_presence,trackers)
    temperature_id=settings.get("temperature_entity")
    pinned=isinstance(temperature_id,str) and bool(temperature_id)
    # A Manager-supplied temperature is already source/area/freshness
    # validated, including any explicit pin. Do not re-read and accidentally
    # accept a pinned source rejected by the selected room inventory.
    temp=(selected_temperature_c if temperature_evidence is not None
          else temperature_sensor_c(hass,temperature_id,10) if pinned
          else None)
    if temp is not None and not -60 <= temp <= 85:
        temp=None
    climate_id=settings.get("climate_entity")
    state=hass.states.get(climate_id) if isinstance(climate_id,str) and climate_id.startswith("climate.") else None
    cap=capabilities(state.attributes,state.state) if state else {"kind":"unavailable"}
    strategy=settings.get("controller","device")
    primary_cap=cap
    if strategy=="device":
        cap=planning_capabilities(cap,device_inventory(hass,area,settings))
    if strategy in ("on_off","pwm","proportional"):
        kind="number" if strategy=="proportional" else "switch"
        capability={"kind":kind,"heat":False,"cool":False,"setpoint":False}
        for key,mode in (("heat_actuator","heat"),("cool_actuator","cool")):
            entity=settings.get(key)
            if not isinstance(entity,str) or not entity.startswith(kind+"."):
                continue
            if entity_area(hass,entity)!=area:
                continue
            candidate=hass.states.get(entity)
            if candidate is None or candidate.state in ("unavailable","unknown"):
                continue
            if kind=="switch":
                capability[mode]=candidate.state in ("on","off")
            else:
                attrs=candidate.attributes
                try: valid=0<=float(candidate.state)<=100
                except (ValueError,TypeError,OverflowError): valid=False
                capability[mode]=(valid and attrs.get("unit_of_measurement")=="%"
                    and attrs.get("min")==0 and attrs.get("max")==100)
        cap=capability
    window_safe=all(win.opened is False for win in room.windows) and (
        bool(room.windows) or not require_window_contact
    )
    window_evidence=("missing_required_contact" if not room.windows and require_window_contact
                     else "no_contact_configured" if not room.windows else
                     "all_contacts_closed" if window_safe else "open_or_unavailable_contact")
    time_zone=getattr(getattr(hass,"config",None),"time_zone",None) or "UTC"
    sleeping,sleep_evidence=scheduled_sleep(
        settings,time.time() if now is None else now,time_zone,
    )
    # Local schedule is trustworthy even when inactive. Only a CONFIGURED
    # but broken global sleep-room source makes sleep evidence unknown.
    sleep_verified=True
    if isinstance(global_presence,dict) and global_presence.get("sleep_rooms_entity"):
        from .occupancy_policy import sleep_presence
        global_sleep,global_reason=sleep_presence(
            hass,area,global_presence,known_areas or {area})
        if global_sleep is True:
            sleeping,sleep_evidence=True,global_reason
            sleep_verified=True
        elif global_sleep is None:
            sleep_verified=False
            sleep_evidence=global_reason
        else:
            sleep_verified=True
    # The legacy diagnostic occupancy helper may conservatively report
    # "occupied" when evidence is missing/partial. That is safe for hold logic,
    # but Comfort must mean VERIFIED room presence. Feed unknown into profile
    # selection for those conservative cases, so it resolves to Home, never Away.
    profile_occupied = (
        "unknown"
        if occ_reason in ("no_sensor_conservative", "unknown_sensor_conservative",
                          "off_duration_unverified", "awaiting_stable_unoccupied_period")
        and occupied == "occupied"
        else occupied
    )
    result=policy(settings,temp_c=temp,capability=cap,at_home=at_home,
                  occupied=profile_occupied,sleeping=sleeping,
                  manual_profile=settings.get("manual_profile"),prior_mode=prior_mode,
                  window_safe=window_safe,comfort_target_c=comfort_target_c)

    temperature_intent={"status":result.state,"mode":result.desired_hvac_mode,
                        "window_safe":window_safe}
    equipment=room_equipment_plan(
        hass,area,settings,temperature_intent,room.readings,
        outdoor_safe=outdoor_safe,duplicates=duplicate_equipment,
    )
    native_air=native_air_mode_advice(
        hass,area,settings,equipment,time.time() if now is None else now,
    )

    return {
        "humidity_management":equipment.get("humidity", {"status":"unavailable"}),
        "equipment_plan":equipment,
        "native_air_mode_advice":native_air,
        "status":result.state,
        "profile":result.profile,"mode":result.desired_hvac_mode,
        "temperature_target_c":result.temperature_c,
        "low_target_c":result.range_low_c,
        "high_target_c":result.range_high_c,
        "reason":result.reason,"controller":result.controller,
        "occupancy":occupied,"occupancy_evidence":occ_reason,
        "presence_entities":sensors,"away":at_home,"away_evidence":home_reason,
        "absence_delay_minutes":settings.get("unoccupied_delay_minutes",10),
        "sleep_schedule_active":sleeping,"sleep_schedule_evidence":sleep_evidence,
        "sleeping":sleeping if sleep_verified else None,
        "global_presence":global_presence if isinstance(global_presence,dict) else None,
        "known_presence_areas":sorted(known_areas or {area}),
        "tracker_entities":trackers,
        "climate_entity":climate_id,"climate_capabilities":primary_cap,
        "room_planning_capabilities":cap,
        "temperature_entity":temperature_id,"temperature_c":temp,
        "temperature_evidence":temperature_evidence or {
            "status": "ready" if temp is not None else "temperature_unavailable",
            "source": "pinned_sensor" if pinned else "not_configured",
            "entity_ids": [temperature_id] if pinned else [],
        },
        "window_safe":window_safe,
        "window_evidence":window_evidence,
        "window_contacts":[win.entity_id for win in room.windows],
        "automatic_actuation_enabled": bool(
            settings.get("allow_actuation") and
            (strategy in ("device","on_off","pwm","proportional")) and
            (strategy=="device" or settings.get("direct_hardware_confirmed"))
        ),
        "note":"Only explicitly authorized same-room actuators are controllable; equipment safety remains external",
    },(set(sensors+trackers+[x for x in (temperature_id,climate_id)
                           if isinstance(x,str)]) | assigned_entities(settings) |
          ({settings["humidity_entity"]} if isinstance(settings.get("humidity_entity"),str) else set()))
