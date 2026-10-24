"""One deterministic, safety-first arbitration for ALL devices in a room.

A room has four independently qualified *purposes*: temperature regulation,
humidity management, safe outdoor-air extraction and particulate filtration.
This module grants no power or mode-switch permissions by itself. Existing
native device drivers keep their own independent entitlements, minimum dwell,
sensor validation, manual pause and service acknowledgement safeguards.

The same pure decisions are used during planning and immediately before each
new device command. They cannot operate equipment or automatically shut down
a manually controlled device.
"""
from __future__ import annotations

from typing import Any

from .climate_coordination import device_inventory
from .discovery import entity_area
from .pid_math import finite

CHANNELS = ("thermal", "humidity", "extraction", "filtration")
ACTIVE_ACTIONS = frozenset(("heating", "preheating", "cooling", "drying"))
OPPOSING_MODES = {
    "heat": frozenset(("cool", "heat_cool", "auto", "dry")),
    "cool": frozenset(("heat", "heat_cool", "auto", "dry")),
    "heat_cool": frozenset(("heat", "cool", "heat_cool", "auto", "dry")),
}
# Conservative heuristic for deferring a separate dehumidifier while a
# cooling system may already remove moisture. This is a control preference,
# NOT evidence that a particular AC actually dehumidifies.
COOLING_DRY_DEFERRAL_RH_POINTS = 10.0


def _decision(status: str, *, entity: str | None = None,
              reason: str | None = None, **details: Any) -> dict:
    result: dict[str, Any] = {"status": status}
    if entity is not None:
        result["entity_id"] = entity
    if reason is not None:
        result["reason"] = reason
    result.update(details)
    return result


def _selected_thermal(config: dict, plan: dict, inventory: dict) -> tuple[str | None,str | None,str]:
    """Native thermostat selection and direct slow-load actuator are distinct."""
    mode = plan.get("mode")
    if plan.get("status") not in ("ready", "hold") or mode not in ("heat", "cool", "heat_cool"):
        return None, mode, "no_active_thermal_plan"
    strategy = config.get("controller", "device")
    if strategy in ("on_off", "pwm", "proportional"):
        if plan.get("status") != "ready" or mode not in ("heat", "cool"):
            return None, mode, "no_direct_thermal_plan"
        entity = config.get("heat_actuator" if mode == "heat" else "cool_actuator")
        if not isinstance(entity,str):
            return None,mode,"direct_actuator_not_selected"
        return entity, mode, "direct"
    thermal = plan.get("equipment_plan",{}).get("thermal",{})
    if not isinstance(thermal,dict) or thermal.get("status") != "selected":
        return None, mode, "verified_thermal_selection_missing"
    entity = thermal.get("entity_id")
    if not isinstance(entity,str):
        return None,mode,"verified_thermal_entity_missing"
    return entity, mode, "climate"


def _physical_climate_conflict(hass: Any, area: str, config: dict,
                               owner: str, mode: str) -> str | None:
    """Avoid trying to command against OTHER armed/active HVAC units.

    A climate unit armed in an opposing mode can restart its compressor at
    any moment, even if hvac_action currently says 'idle'.
    """
    others = set()
    for role in ("climate_entity","heat_climate_entity","cool_climate_entity",
                 "dry_climate_entity","fan_climate_entity"):
        entity=config.get(role)
        if isinstance(entity,str) and entity != owner:
            others.add(entity)
    for entity in sorted(others):
        if entity_area(hass,entity)!=area:
            return "other_climate_wrong_room"
        state=hass.states.get(entity)
        if state is None or str(state.state).lower() in ("unknown","unavailable"):
            return "other_climate_unavailable"
        observed_mode = str(state.state)
        action=state.attributes.get("hvac_action")
        if observed_mode in OPPOSING_MODES.get(mode,()):
            return "opposing_native_mode_armed"
        if action in ACTIVE_ACTIONS:
            return "other_climate_active"
        if observed_mode not in ("off","fan_only") and action is None:
            return "other_climate_activity_unknown"
    return None


def _contact_interlock(hass: Any, area: str, plan: dict) -> bool:
    """An old 'closed' plan cannot mask a window opened before a service call."""
    if plan.get("window_safe") is not True:
        return False
    contacts=plan.get("window_contacts")
    if contacts is None:
        # Existing direct unit tests build only minimal plans; real manager
        # reports always contain a contact list.
        return True
    if not isinstance(contacts,list):
        return False
    for entity in contacts:
        if not isinstance(entity,str) or entity_area(hass,entity)!=area:
            return False
        state=hass.states.get(entity)
        if (state is None or state.domain!="binary_sensor"
                or state.attributes.get("device_class")!="window"
                or state.state!="off"):
            return False
    return True


def room_coordination(hass: Any, area: str, config: dict, plan: dict,
                      *, now: float | None = None) -> dict:
    """Explain grants and blocks, not issue device actions.

    A single-room HVAC or humidity plan can still be advisory, and
    'eligible' is *not* permission to actuate absent a driver-specific opt-in.
    """
    decisions={key:_decision("idle",reason="no_qualified_demand")
               for key in CHANNELS}
    if not isinstance(config,dict) or config.get("enabled") is not True:
        return {"status":"disabled","channels":decisions,
                "priority":"none","method":"live_room_exclusive_purpose_arbitration"}
    if not isinstance(plan,dict):
        return {"status":"unavailable","channels":decisions,"priority":"none",
                "method":"live_room_exclusive_purpose_arbitration"}
    inventory=device_inventory(hass,area,config)
    equipment=plan.get("equipment_plan",{})
    if not isinstance(equipment,dict):
        equipment={}
    if equipment.get("status")=="duplicate_equipment_owner":
        for key in decisions:
            decisions[key]=_decision("held",reason="duplicate_equipment_owner")
        return {"status":"held","channels":decisions,"priority":"safety",
                "method":"live_room_exclusive_purpose_arbitration"}
    contact_safe=_contact_interlock(hass,area,plan)

    # 1. THERMAL: one verified room actuator, no actively competing native
    # climate. Ordinary non-temperature systems do not get thermal grants.
    selected,mode,kind=_selected_thermal(config,plan,inventory)
    if kind in ("climate","direct") and isinstance(selected,str):
        if not contact_safe:
            decisions["thermal"]=_decision("held",entity=selected,reason="open_or_unknown_window")
        elif entity_area(hass,selected)!=area:
            decisions["thermal"]=_decision("held",entity=selected,reason="thermal_wrong_room")
        elif kind=="climate" and inventory.get(
            next((role for role in ("heat_climate_entity","cool_climate_entity","climate_entity")
                  if config.get(role)==selected),"climate_entity"),{}
        ).get("status")!="ready":
            decisions["thermal"]=_decision("held",entity=selected,reason="thermal_device_unverified")
        elif conflict:=_physical_climate_conflict(hass,area,config,selected,mode):
            decisions["thermal"]=_decision("held",entity=selected,reason=conflict)
        else:
            decisions["thermal"]=_decision("eligible",entity=selected,
                                            purpose=mode,controller=kind)
    else:
        decisions["thermal"]=_decision("idle",reason=kind)

    # 2. HUMIDITY: no humidifier/dehumidifier competition. Active native AC
    # cooling may be preferred to a *separate* compressor below a cautious
    # configurable relative-humidity margin. An actually critical wet room
    # is never automatically dismissed as successfully dehumidified by AC.
    moisture=equipment.get("moisture",{})
    advice=equipment.get("humidity",{})
    if isinstance(moisture,dict) and moisture.get("status")=="selected":
        wanted=moisture.get("action")
        role=moisture.get("role")
        entity=moisture.get("entity_id")
        if role in ("humidifier_entity","dehumidifier_entity") and isinstance(entity,str):
            twin="dehumidifier_entity" if wanted=="humidify" else "humidifier_entity"
            other=inventory.get(twin,{})
            if not contact_safe:
                decisions["humidity"]=_decision("held",entity=entity,reason="open_or_unknown_window")
            elif entity_area(hass,entity)!=area or inventory.get(role,{}).get("status")!="ready":
                decisions["humidity"]=_decision("held",entity=entity,reason="humidity_entity_not_verified")
            elif other.get("active") is True or (
                other and other.get("status")!="ready"):
                decisions["humidity"]=_decision("held",entity=entity,reason="opposing_humidity_device")
            elif advice.get("status")!="advisory" or advice.get("action")!=wanted:
                decisions["humidity"]=_decision("held",entity=entity,reason="humidity_measurement_not_qualified")
            elif any(item.get("status")=="ready" and
                     item.get("domain")=="climate" and
                     item.get("capabilities",{}).get("current")=="dry"
                     for item in inventory.values()) and wanted=="dry":
                decisions["humidity"]=_decision("held",entity=entity,reason="native_ac_drying_armed")
            else:
                observed=finite(advice.get("measured_rh"),0,100)
                high=finite(config.get("humidity_high_rh",60),30,80)
                margin=finite(config.get("cooling_dry_deferral_rh_points",
                                         COOLING_DRY_DEFERRAL_RH_POINTS),0,20)
                cooling_armed=any(
                    item.get("status")=="ready" and
                    item.get("domain")=="climate" and
                    item.get("capabilities",{}).get("current") in ("cool","heat_cool")
                    for item in inventory.values()
                )
                if margin is None:
                    decisions["humidity"]=_decision("held",entity=entity,
                                                   reason="invalid_cooling_dry_margin")
                elif wanted=="humidify" and cooling_armed:
                    decisions["humidity"]=_decision("held",entity=entity,
                                                   reason="cooling_conflicts_with_humidification")
                elif (wanted=="dry" and cooling_armed and
                      observed is not None and high is not None and
                      observed < high + margin):
                    decisions["humidity"]=_decision(
                        "held",entity=entity,reason="cooling_priority_observe_rh",
                        measured_rh=observed,
                    )
                elif wanted in ("humidify","dry"):
                    decisions["humidity"]=_decision("eligible",entity=entity,
                                                    purpose=wanted)
        elif role in ("dry_climate_entity","climate_entity"):
            decisions["humidity"]=_decision("advisory_only",
                reason="native_compressor_dry_mode_not_auto_controlled")
    # 3. AIR TREATMENT: extraction needs verified safe outdoor AND current
    # measured CO2. PM filtration is distinct and may run with bad outdoor AQ.
    air=plan.get("air_actions",{})
    if isinstance(air,dict) and air.get("status")=="advisory":
        for channel,policy,role in (
            ("extraction","extraction","extraction_fan_entity"),
            ("filtration","filtration","purifier_fan_entity"),
        ):
            item=air.get(policy,{})
            entity=config.get(role)
            if not isinstance(item,dict) or item.get("status")!="recommended":
                continue
            if not isinstance(entity,str) or item.get("entity_id")!=entity:
                decisions[channel]=_decision("held",reason="air_device_selection_mismatch")
            elif inventory.get(role,{}).get("status")!="ready":
                decisions[channel]=_decision("held",entity=entity,reason="air_device_unavailable")
            elif channel=="extraction" and not contact_safe:
                decisions[channel]=_decision("held",entity=entity,reason="window_open_or_unknown")
            elif channel=="extraction" and air.get("outdoor_air_verified") is not True:
                decisions[channel]=_decision("held",entity=entity,reason="outdoor_air_not_verified")
            elif item.get("speed_control_eligible") is not True:
                decisions[channel]=_decision("held",entity=entity,reason="sensor_not_verified")
            else:
                stamp=plan.get("air_evidence_at")
                stamp_value=finite(stamp,0,1e13)
                if (now is not None and stamp is not None and
                    (stamp_value is None or not 0<=now-stamp_value<=120)):
                    decisions[channel]=_decision("held",entity=entity,reason="air_policy_expired")
                else:
                    decisions[channel]=_decision("eligible",entity=entity,
                                                purpose=policy)

    # If ventilation is justified by qualified CO2, it takes priority over
    # energy convenience. This is a ranking for user explanation; a running
    # thermostat is NOT powered off to honor the priority.
    if decisions["extraction"]["status"]=="eligible":
        priority="measured_co2_ventilation"
    elif decisions["filtration"]["status"]=="eligible":
        priority="measured_particle_filtration"
    elif decisions["thermal"]["status"]=="eligible":
        priority="temperature_comfort"
    elif decisions["humidity"]["status"]=="eligible":
        priority="humidity_management"
    else:
        priority="hold_or_no_demand"
    status=("ready" if any(d["status"]=="eligible" for d in decisions.values())
            else "hold" if any(d["status"]=="held" for d in decisions.values())
            else "idle")
    return {
        "status":status,"priority":priority,"channels":decisions,
        "window_efficiency":(plan.get("window_efficiency",{}).get("status")
                              if isinstance(plan.get("window_efficiency"),dict)
                              else "unknown"),
        "mechanical_mode_changes_allowed":False,
        "method":"live_room_exclusive_purpose_arbitration",
    }


def new_command_gate(hass: Any, area: str, config: dict,
                     plan: dict, purpose: str, entity: str,
                     *, now: float | None = None,
                     entry_id: str | None = None) -> str | None:
    """Require both planned AND fresh live authority for any new command.

    None permits a command to progress to the independent device driver.
    Non-None is a stable reason to hold. This helper NEVER authorizes a
    reverse/off command; previously-owned output shutdown uses its own
    independent fail-safe acknowledgement and minimum-on policy.

    The legacy no-arbitration test interface is preserved for direct device
    fixtures; plans produced by the room manager always include coordination.
    """
    from .equipment_model import legacy_hold
    if hold := legacy_hold(hass, entry_id, entity):
        return hold
    if purpose not in CHANNELS or not isinstance(plan,dict):
        return "invalid_coordination_request"
    selected=config.get("selected_devices") if isinstance(config,dict) else None
    if isinstance(selected,list) and entity not in selected:
        # A deselected device cannot remain live via an old room role.
        if entity.startswith(("climate.","humidifier.","fan.")):
            return "device_not_selected"
    profiles=config.get("device_settings",{}) if isinstance(config,dict) else {}
    if isinstance(profiles,dict) and isinstance(profiles.get(entity),dict):
        from .occupancy_policy import device_permission, live_device_permission
        action,reason=device_permission(
            profiles[entity],plan.get("occupancy","unknown"),
            plan.get("away","home"),plan.get("sleeping"),
        )
        if action=="eligible":
            action,reason=live_device_permission(
                hass,area,config,plan,profiles[entity],
            )
        if action!="eligible":
            return reason
    # A separate HA config entry may choose the same climate/fan/humidity
    # output *after* this room was planned. The live foreign-owner gate must
    # apply even to the legacy minimal-plan interface.
    if entry_id is not None:
        from .climate_entry_ownership import foreign_owner_hold
        other_owner=foreign_owner_hold(hass,entry_id,entity)
        if other_owner is not None:
            return other_owner
    cached=plan.get("coordination")
    if cached is None:
        return None
    planned=(cached.get("channels",{}).get(purpose,{})
             if isinstance(cached,dict) else {})
    if (planned.get("status")!="eligible" or
        planned.get("entity_id")!=entity):
        return "coordination_plan_not_authorized"
    current=room_coordination(hass,area,config,plan,now=now)
    live=current["channels"][purpose]
    if live.get("status")!="eligible" or live.get("entity_id")!=entity:
        return live.get("reason") or "coordination_live_conflict"
    return None
