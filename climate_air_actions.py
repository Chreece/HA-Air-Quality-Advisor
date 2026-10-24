"""Deterministic evidence-first ventilation, dehumidification and filtration.

This is advisory arbitration only. It does not switch or ramp real equipment.
No WHO 24-hour guideline is interpreted as an instantaneous action threshold.
For future fan setpoint supervision, source verification and live checks remain
mandatory and independent of these recommendations.
"""
from __future__ import annotations

from typing import Any
from math import isfinite


def _number(v: Any, low: float, high: float) -> float | None:
    if isinstance(v, bool):
        return None
    try:
        n = float(v)
    except (TypeError, ValueError, OverflowError):
        return None
    return n if isfinite(n) and low <= n <= high else None


def unique_measurement(readings: tuple | list, metric: str,
                       selected_entity: str | None = None) -> tuple[float | None, str]:
    """Do not blend disagreeing sensors or use stale/unknown readings."""
    rows = [
        (getattr(r,"entity_id",None), getattr(r,"value",None))
        for r in readings if getattr(r,"metric",None)==metric
    ]
    if selected_entity:
        rows = [row for row in rows if row[0]==selected_entity]
    if len(rows)!=1:
        return None, "ambiguous_sensor" if len(rows)>1 else "sensor_not_available"
    lo,hi={"co2":(250,20000),"pm25":(0,10000),
           "humidity":(0,100)}.get(metric,(-1e9,1e9))
    val=_number(rows[0][1],lo,hi)
    return (val, "measured") if val is not None else (None,"invalid_or_stale_reading")


def air_treatment_plan(
    readings: tuple | list, climate_report: dict, equipment: dict,
    moisture: dict, *, outside_safe: bool | None,
    science_profile: dict | None = None, settings: dict | None = None,
) -> dict:
    """Give independent extraction/purification priorities and data-quality.

    NDIR verification is explicit for CO2 fan control. PM sensor suitability
    must also be explicitly attested to before fan-control eligibility.
    Only actual room and weather measurements can support moisture extraction.
    """
    science = science_profile if isinstance(science_profile,dict) else {}
    config = settings if isinstance(settings,dict) else {}
    devices = equipment.get("inventory",{}) if isinstance(equipment,dict) else {}
    target_co2=_number(science.get("co2_target_ppm",1000),400,3000)
    pm_limit=_number(config.get("pm25_action_ug_m3",35),5,250)
    if target_co2 is None or pm_limit is None:
        return {"status":"invalid_settings","control_eligible":False}
    co2,co2_status=unique_measurement(readings,"co2",config.get("co2_entity"))
    particle,pm_status=unique_measurement(readings,"pm25",config.get("pm25_entity"))
    humidity_plan=climate_report.get("humidity_management",{})
    humidity=_number(humidity_plan.get("measured_rh"),0,100)
    high=_number(config.get("humidity_high_rh",60),30,80)
    hyst=_number(config.get("humidity_hysteresis_rh",3),0.5,10)
    wet=bool(humidity is not None and high is not None and hyst is not None
             and humidity>=high+hyst)
    moisture_status=moisture.get("status") if isinstance(moisture,dict) else "unavailable"
    drier=bool(moisture_status=="drying" and
               _number(moisture.get("drying_potential_g_kg"),1,100) is not None)
    high_co2=bool(co2 is not None and co2>=target_co2+200)
    high_particles=bool(particle is not None and particle>=pm_limit)
    extraction=devices.get("extraction_fan_entity",{})
    purifier=devices.get("purifier_fan_entity",{})
    external_safe=outside_safe is True
    reasons=[]
    if high_co2:
        reasons.append("elevated_measured_co2")
    if wet and drier:
        reasons.append("high_rh_and_measured_outdoor_drying")
    extract_demand=bool(reasons and external_safe)
    filter_demand=high_particles
    extracted={
        "status": ("recommended" if extract_demand else
                   "blocked_outdoor_evidence" if reasons and not external_safe
                   else "no_drying_advantage" if wet and not drier else
                   "no_ventilation_demand"),
        "reasons":reasons if extract_demand else [],
        "entity_id":extraction.get("entity_id"),
        "device_status":extraction.get("status","not_configured"),
        "speed_control_eligible":bool(
            extract_demand and extraction.get("status")=="ready" and
            "elevated_measured_co2" in reasons and
            science.get("co2_ndir_verified") is True and
            isinstance(config.get("co2_entity"),str)
        ),
    }
    filtered={
        "status":"recommended" if filter_demand else "no_particle_demand",
        "reasons":["measured_short_term_pm25_trigger"] if filter_demand else [],
        "entity_id":purifier.get("entity_id"),
        "device_status":purifier.get("status","not_configured"),
        "speed_control_eligible":bool(
            filter_demand and purifier.get("status")=="ready" and
            config.get("pm25_sensor_verified") is True and
            isinstance(config.get("pm25_entity"),str)),
    }
    return {
        "status":"advisory",
        "extraction":extracted,
        "filtration":filtered,
        "moisture_evidence":moisture_status,
        "measurements":{
            "co2_ppm":co2,"co2_quality":co2_status,
            "pm25_ug_m3":particle,"pm25_quality":pm_status,
            "humidity_percent":humidity,
        },
        "thresholds":{"co2_operational_ppm":target_co2+200,
                      "pm25_short_term_action_ug_m3":pm_limit},
        "control_eligible":False,
        "method":"measured_room_air_advice_not_exposure_or_air_change_proof",
    }
