"""Draft-only native HVAC DRY/FAN_ONLY transition advice.

No Home Assistant service calls. A DRY transition may start a compressor:
unit tests cannot establish an equipment's minimum off/on intervals, internal
defrost, electrical protection, shared outdoor-unit constraints, or manual
operating preferences. This policy NEVER grants actuation authority.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .climate_coordination import device_inventory
from .discovery import entity_area

MODE_DWELL_SECONDS=1800


def native_air_mode_advice(hass:Any, area:str, settings:dict,
                           equipment:dict, now:float) -> dict:
    """Propose a compressor-affecting mode change only with reliable evidence.

    Return descriptive instructions; no actuation option exists. Only modes
    actually published in a climate device's hvac_modes are considered.
    """
    advisory={"automatic_control":False,
              "method":"capability_gated_dry_fan_only_advisory"}
    if not isinstance(settings,dict) or settings.get("enabled") is not True:
        return {**advisory,"status":"disabled"}
    climate=settings.get("dry_climate_entity") or settings.get("climate_entity")
    if not isinstance(climate,str) or not climate.startswith("climate."):
        return {**advisory,"status":"no_dry_climate_selected"}
    if entity_area(hass,climate)!=area:
        return {**advisory,"status":"device_wrong_room"}
    inventory=device_inventory(hass,area,settings)
    role="dry_climate_entity" if settings.get("dry_climate_entity") else "climate_entity"
    candidate=inventory.get(role,{})
    if (candidate.get("status")!="ready" or
        candidate.get("entity_id")!=climate):
        return {**advisory,"status":"device_unavailable_or_unverified"}
    caps=candidate.get("capabilities",{})
    if not caps.get("drying"):
        return {**advisory,"status":"native_dry_mode_required"}
    # FAN_ONLY is optional. A DRY-only device may still provide humidity
    # control; never recommend a mode the actual entity does not expose.
    if equipment.get("status")!="ready":
        return {**advisory,"status":"incomplete_equipment_plan"}
    thermal=equipment.get("thermal",{})
    if (thermal.get("status")=="selected" and
        thermal.get("mode") in ("heat","cool","heat_cool")):
        return {**advisory,"status":"thermal_regulation_has_priority"}
    moisture=equipment.get("moisture",{})
    if moisture.get("status") in ("opposing_moisture_device_running",
                                  "window_interlock"):
        return {**advisory,"status":"moisture_interlock"}
    if (moisture.get("status")=="selected" and
        moisture.get("entity_id")!=climate):
        return {**advisory,"status":"separate_dehumidifier_selected"}
    humidity=equipment.get("humidity",{})
    if humidity.get("status")!="advisory":
        return {**advisory,"status":"humidity_evidence_insufficient"}
    action=humidity.get("action")
    if action not in ("dry","idle"):
        return {**advisory,"status":"drying_not_appropriate", "action":action}
    state=hass.states.get(climate)
    if state is None or state.state in ("off","unknown","unavailable"):
        return {**advisory,"status":"air_conditioner_off_or_unavailable"}
    if state.state not in ("dry","fan_only"):
        return {**advisory,"status":"another_native_mode_active",
                "current_mode":state.state}
    # No unacknowledged or contradictory device self-report.
    hvac_action=state.attributes.get("hvac_action")
    if hvac_action in ("heating","cooling","preheating") and state.state=="fan_only":
        return {**advisory,"status":"unexpected_compressor_activity"}
    target=("dry" if action=="dry" else
            "fan_only" if caps.get("fan_only") else "off")
    if state.state==target:
        return {**advisory,"status":"already_in_suitable_mode",
                "current_mode":state.state, "recommended_mode":target}
    changed=getattr(state,"last_changed",None)
    if not isinstance(changed,datetime) or changed.tzinfo is None:
        return {**advisory,"status":"mode_dwell_history_unavailable"}
    interval=now-changed.timestamp()
    if not 0<=interval:
        return {**advisory,"status":"invalid_mode_timestamp"}
    if interval<MODE_DWELL_SECONDS:
        return {**advisory,"status":"mode_dwell_not_met",
                "dwell_remaining_minutes":round((MODE_DWELL_SECONDS-interval)/60,1)}
    return {**advisory,"status":("manual_stop_dry_suggested" if target=="off"
                                       else "manual_mode_transition_suggested"),
            "current_mode":state.state,"recommended_mode":target,
            "climate_entity":climate,
            "requires_device_commissioning":True,
            "reason":("high_measured_rh" if action=="dry"
                      else "humidity_recovered"),
            "note":"Native DRY may start the compressor. No automatic mode change is issued."}
