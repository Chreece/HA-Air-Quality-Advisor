"""Explicit opt-in international sensor adapters and environmental alternatives.

Uses Home Assistant entities supplied by the user. No hardcoded country, API,
location or vendor-specific device assumptions. Missing evidence is visible.
"""
from __future__ import annotations

import math
from typing import Any

from .building_physics import DAY_S, weighted_window
from .comfort_targets import solve_pmv_air_temperature
from .environment_science import (
    aqi_category, daylight_exposure, eea_hourly_category, hcho_30min,
    laeq_db_a, moisture_event, overheating_degree_hours, particle_filtration,
    pmv_iso7730, pollen_reading, radon_long_term, ventilation_learning, nighttime_laeq,
)
from .discovery import entity_area, is_stale, temperature_sensor_c


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return n if math.isfinite(n) else None


def measurement(hass: Any, entity_id: str | None, max_age_minutes: float,
                metric: str, *, area_id: str | None = None) -> tuple[float | None, str]:
    """Strict units, domain and assigned-room match; calibrated hardware is opt-in."""
    if not isinstance(entity_id, str) or not entity_id.startswith("sensor."):
        return None, "not_selected"
    if area_id is not None and (area := entity_area(hass, entity_id)) is not None and area != area_id:
        return None, "wrong_room"
    state = hass.states.get(entity_id)
    if state is None or is_stale(state, max_age_minutes):
        return None, "unavailable"
    value = _num(state.state)
    if value is None:
        return None, "not_numeric"
    unit = str(state.attributes.get("unit_of_measurement", "")).replace("μ", "µ").replace("³","3").replace(" ","").lower()
    if metric == "hcho":
        if unit in ("µg/m3", "ug/m3"):
            return (value, "measured") if 0 <= value <= 100000 else (None, "invalid_range")
        if unit == "mg/m3":
            return (value*1000, "measured") if 0 <= value <= 100 else (None, "invalid_range")
        return None, "invalid_unit"
    if metric == "radon":
        if unit in ("bq/m3", "bq/m^3"):
            return (value, "measured") if 0 <= value <= 20000 else (None, "invalid_range")
        if unit in ("pci/l",):
            return (value*37.0, "measured") if 0 <= value <= 550 else (None, "invalid_range")
        return None, "invalid_unit"
    if metric == "noise_dba":
        return (value, "measured") if unit in ("db(a)", "dba") and 0 <= value <= 150 else (None, "invalid_unit_or_range")
    if metric in ("lux", "melanopic_edi"):
        return (value, "measured") if unit in ("lx", "lux") and 0 <= value <= 300000 else (None, "invalid_unit_or_range")
    if metric == "air_speed":
        return (value, "measured") if unit in ("m/s","mps") and 0 <= value <= 5 else (None, "invalid_unit_or_range")
    return None, "unknown_metric"


def entity_on(hass: Any, entity_id: str | None) -> bool | None:
    if not isinstance(entity_id, str) or not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None:
        return None
    v = str(state.state).casefold()
    # State of a switch/fan does not get stale just because it remains on/off.
    if v in ("on", "off"):
        return v == "on"
    return None


def extend_room_inputs(hass: Any, area_id: str, profile: dict,
                       *, max_age: float) -> tuple[dict, dict, set[str]]:
    """Return bounded measurement sample, per-source diagnostics and track IDs."""
    keys = {
        "radon": ("radon_entity", "radon"),
        "hcho": ("formaldehyde_entity", "hcho"),
        "noise_dba": ("noise_entity", "noise_dba"),
        "lux": ("illuminance_entity", "lux"),
        "melanopic_edi": ("melanopic_edi_entity", "melanopic_edi"),
    }
    sample: dict = {}
    sources: dict = {}
    tracked: set[str] = set()
    for dest, (field, name) in keys.items():
        entity = profile.get(field)
        if not entity:
            continue
        value, status = measurement(hass, entity, max_age, name, area_id=area_id)
        sources[field] = {"entity": entity, "status": status}
        tracked.add(entity)
        if value is not None:
            sample[dest] = value
            if dest == "radon":
                sample["radon_source"] = entity
    for field in ("purifier_entity", "extractor_entity", "radiant_temperature_entity",
                  "air_speed_entity", "temperature_entity"):
        entity = profile.get(field)
        if isinstance(entity, str) and entity:
            tracked.add(entity)
    return sample, sources, tracked


def room_science(hass: Any, area_id: str, profile: dict, samples: list[dict],
                 now: float, *, history: Any, outside_safe: bool,
                 existing: dict) -> tuple[dict, bool]:
    """New features remain informational unless a configured policy opts in."""
    if not profile:
        return {"status": "not_configured"}, False
    volume = profile.get("room_volume_m3")
    cadr = profile.get("particle_cadr_m3h")
    purification = particle_filtration(
        volume, cadr, entity_on(hass, profile.get("purifier_entity")), samples, now,
    ) if volume is not None or cadr is not None else {"status": "not_configured"}
    extractor = entity_on(hass, profile.get("extractor_entity"))
    moisture = moisture_event(samples, now, extractor_on=extractor)
    ventilation = (ventilation_learning(samples, now, target_co2=float(
        profile.get("co2_target_ppm", 1000))) if profile.get("co2_ndir_verified")
        else {"status":"co2_sensor_verification_required"})
    qualified = bool(profile.get("formaldehyde_sensor_verified"))
    hcho = hcho_30min(samples, now, verified=qualified) if profile.get("formaldehyde_entity") else {"status": "not_configured"}
    calibrated_noise = bool(profile.get("noise_sensor_calibrated"))
    sound = laeq_db_a(samples, now, DAY_S) if calibrated_noise and profile.get("noise_entity") else {
        "status": "sensor_calibration_required" if profile.get("noise_entity") else "not_configured"}
    night_sound = nighttime_laeq(samples, now, getattr(getattr(hass,"config",None),"time_zone",None) or "UTC") if calibrated_noise and profile.get("noise_entity") and profile.get("sleep_room") else {"status":"not_configured"}
    light = daylight_exposure(samples, now) if profile.get("illuminance_entity") else {"status": "not_configured"}
    mel = [s.get("melanopic_edi") for s in samples[-1:] if isinstance(s.get("melanopic_edi"), (float,int))]
    if mel and profile.get("melanopic_spectral_verified"):
        light["melanopic_edi_lux"] = round(mel[0],1)
        light["melanopic_edi_status"] = "sensor_reported_not_from_photopic_lux"
    radon_id = profile.get("radon_entity")
    committed = False
    if radon_id and profile.get("radon_sensor_verified"):
        committed = history.record_qualified_radon_days(area_id, radon_id, now=now)
        radon = radon_long_term(history.radon_days(area_id, radon_id), now,
                                recommended_bq_m3=float(profile.get("radon_reference_bq_m3",100)))
        radon["current_bq_m3"] = next((s["radon"] for s in reversed(samples)
                                     if s.get("radon_source") == radon_id and isinstance(s.get("radon"), (int,float))), None)
    else:
        radon = {"status": "sensor_verification_required" if radon_id else "not_configured"}
    pmv = {"status": "not_configured"}
    comfort_target = {"status":"not_configured"}
    if profile.get("enable_pmv"):
        radiant = None
        if profile.get("radiant_temperature_entity") and entity_area(
            hass, profile["radiant_temperature_entity"]
        ) in (None, area_id):
            radiant = temperature_sensor_c(
                hass, profile["radiant_temperature_entity"], 10,
            )
        air_speed = profile.get("air_speed_m_s")
        if profile.get("air_speed_entity"):
            air_speed, _ = measurement(hass, profile["air_speed_entity"], 10, "air_speed", area_id=area_id)
        # No reuse of old PMV inputs from the persisted room history.
        # Newest sample must itself be recent and carry all required fields.
        sample=samples[-1] if samples and now-samples[-1].get("t",-1)>-1 and (
            now-samples[-1].get("t",-1)<=600) else {}
        indoor_temperature=sample.get("temperature_c")
        humidity=sample.get("humidity")
        pmv = pmv_iso7730(indoor_temperature, radiant, humidity, air_speed,
                           profile.get("met"), profile.get("clo"))
        pmv["radiant_sensor_status"] = "measured" if radiant is not None else "unavailable"
        if pmv.get("status")=="estimate":
            comfort_target=solve_pmv_air_temperature(
                radiant,humidity,air_speed,profile.get("met"),profile.get("clo"),
            )
        else:
            comfort_target={"status":"insufficient_fresh_pmv_inputs"}
    overheating = overheating_degree_hours(samples,now,reference_c=float(
        profile.get("overheating_reference_c",26)))
    recommendation = {"status": "no_additional_action"}
    if hcho.get("status") == "ready" and hcho.get("above_who_100ug_m3"):
        recommendation = {"status": "investigate_source_and_ventilation", "reason": "verified_30_min_formaldehyde"}
    elif purification.get("status") == "running" and existing.get("pm25_24h",{}).get("status") == "ready":
        recommendation = {"status": "filtration_running", "reason": "particle_clean_air"}
    elif moisture.get("status") == "relative_humidity_rise":
        recommendation = {"status": "check_extraction" if extractor is not True else "extraction_active",
                          "reason": "rapid_relative_humidity_rise"}
    elif existing.get("passive_cooling",{}).get("status") == "cooling_opportunity" and outside_safe:
        recommendation = {"status": "passive_cooling_option", "reason": "cooler_safe_outdoor_air"}
    return {
        "air_purification": purification, "moisture_event": moisture,
        "ventilation_learning": ventilation, "formaldehyde_30min": hcho,
        "radon": radon, "sound_24h": sound, "sound_last_night": night_sound,
        "daylight": light, "pmv_ppd": pmv,
        "pmv_air_target": comfort_target,
        "overheating_degree_hours": overheating,
        "additional_advice": recommendation,
        "method": "deterministic_opt_in_environmental_observations",
    }, committed


def global_pollen(hass: Any, profile: dict, max_age: float) -> tuple[dict, set[str]]:
    """Combine explicitly selected provider-specific pollen indices conservatively."""
    configured = profile.get("pollen_entities")
    if not isinstance(configured, list):
        legacy = profile.get("pollen_entity")
        configured = [legacy] if isinstance(legacy, str) and legacy else []
    entities = list(dict.fromkeys(e for e in configured if isinstance(e, str) and e))
    if not entities:
        return {"status": "not_configured"}, set()
    readings = []
    for entity_id in entities:
        state = hass.states.get(entity_id)
        if state is None or is_stale(state, max_age):
            readings.append({"status": "unavailable", "provider_entity": entity_id})
            continue
        item = pollen_reading(
            state.state, high_from=profile.get("pollen_high_from", 3),
            max_scale=profile.get("pollen_max_scale", 5),
            prevent_ventilation=bool(profile.get("pollen_avoid_ventilation", False)),
        )
        item["provider_entity"] = entity_id
        readings.append(item)
    valid = [item for item in readings if item.get("status") == "provider_defined"]
    if not valid:
        return {"status": "unavailable", "providers": readings}, set(entities)
    worst = max(valid, key=lambda item: float(item.get("value", 0)) /
                max(float(item.get("max_scale", 1)), 1))
    result = dict(worst)
    result["provider_entities"] = entities
    result["providers"] = readings
    result["high"] = any(bool(item.get("high")) for item in valid)
    result["avoid_ventilation"] = any(bool(item.get("avoid_ventilation")) for item in valid)
    return result, set(entities)


def global_aqi(reading: Any, profile: dict) -> dict:
    selectors = profile.get("aqi_scales", {})
    entry = selectors.get(reading.entity_id, {}) if isinstance(selectors, dict) else {}
    scale = entry.get("scale") if isinstance(entry, dict) else entry
    limit = entry.get("custom_limit") if isinstance(entry, dict) else None
    return aqi_category(reading.value, scale, custom_limit=limit)
