"""Collect available HA room/weather inputs and build transparent physics metrics.

This module intentionally never invents unknown sensors or occupant activity.
With multiple eligible temperature sensors and no chosen mold calibration sensor,
it withholds thermal assessments instead of selecting a random sensor.
"""
from __future__ import annotations

import math
import time
from typing import Any

from .building_physics import (
    DAY_S, WEEK_S, adaptive_comfort, co2_decay_ach, co2_trend,
    heat_per_air_exchange_wh_m3, moisture_potential, passive_cooling,
    nighttime_overheating_exposure,
    surface_condensation, threshold_exposure_hours, weighted_window,
)
from .discovery import entity_area, indoor_temperature_choices, is_stale, temperature_sensor_c
from .environment_history import EnvironmentHistory
from .environment_extended import extend_room_inputs, room_science


def _single_value(readings: Any, metric: str) -> float | None:
    """Require compatible colocated values; reject disagreeing sensors."""
    values = [float(s.value) for s in readings
              if s.metric == metric and s.value is not None
              and isinstance(s.value, (float, int)) and math.isfinite(s.value)]
    if not values:
        return None
    if metric == "humidity":
        return sum(v for v in values if 0 < v <= 100) / len(values) if all(
            0 < v <= 100 for v in values) else None
    spread_limit = max(5, 0.15 * max(values))
    if max(values) - min(values) > spread_limit:
        return None
    return round(sum(values) / len(values), 3)


def _room_temperature(hass: Any, area_id: str, calibration: dict, max_age: float,
                      explicit: str | None = None, selected_entities=None) -> tuple[float | None, str | None, str]:
    if selected_entities is not None:
        from .room_sources import aggregate
        value, status = aggregate(hass, selected_entities, area_id, "temperature", max_age)
        return value, selected_entities[0] if len(selected_entities) == 1 else None, status
    configured = explicit or calibration.get("indoor_temperature_entity")
    if isinstance(configured, str) and configured:
        assigned = entity_area(hass, configured)
        if assigned is not None and assigned != area_id:
            return None, configured, "sensor_assigned_to_another_room"
        return temperature_sensor_c(hass, configured, max_age), configured, "configured"
    choices = indoor_temperature_choices(hass, area_id)
    active = [(item["value"], temperature_sensor_c(hass, item["value"], max_age))
              for item in choices]
    active = [(ent, value) for ent, value in active if value is not None]
    if len(active) == 1:
        return active[0][1], active[0][0], "unique_sensor"
    return None, None, "ambiguous_sensors" if len(active) > 1 else "missing_sensor"


def _occupancy_state(hass: Any, area_id: str, max_age: float) -> bool | None:
    # Motion sensors cannot prove absence. Occupancy/presence sensors remain
    # provisional indicators and are never treated as certified detectors.
    candidates = []
    for state in hass.states.async_all("binary_sensor"):
        if entity_area(hass, state.entity_id) != area_id:
            continue
        klass = str(state.attributes.get("device_class", "")).casefold()
        if klass not in ("occupancy", "presence"):
            continue
        if is_stale(state, max_age):
            continue
        raw = str(state.state).casefold()
        if raw in ("on", "off"):
            candidates.append(raw == "on")
    if candidates and all(v == candidates[0] for v in candidates):
        return candidates[0]
    return None


def build_environment(
    hass: Any, raw_rooms: tuple, rooms_with_mold: tuple, weather: tuple,
    outdoor_readings: tuple, *,
    history: EnvironmentHistory, max_age_minutes: float,
    mold_calibrations: dict[str, Any] | None = None,
    room_profiles: dict[str, Any] | None = None,
    source_selections: dict[str, Any] | None = None,
    outside_safe: bool = False, now: float | None = None,
) -> tuple[dict[str, dict], bool]:
    """Return scientific diagnostics for dashboard and whether history changed."""
    stamp = time.time() if now is None else now
    selected_weather = [w for w in weather if w.temperature_c is not None]
    # Do not silently mix two different weather stations.
    wx = selected_weather[0] if len(selected_weather) == 1 else None
    outdoor_t = wx.temperature_c if wx else None
    outdoor_rh = wx.humidity if wx and wx.humidity is not None and 0 < wx.humidity <= 100 else None
    outdoor_co2 = _single_value(outdoor_readings, "co2")
    changed = history.add("__outside__", {
        "outdoor_temperature_c": outdoor_t,
        "outdoor_pm25": _single_value(outdoor_readings, "pm25"),
        "outdoor_pm10": _single_value(outdoor_readings, "pm10"),
    }, now=stamp)
    prevailing = weighted_window(
        history.samples("__outside__"), "outdoor_temperature_c",
        stamp, WEEK_S, min_coverage=0.8,
    )
    mean_outdoor = prevailing.get("mean") if prevailing["status"] == "ready" else None
    timezone_name = getattr(getattr(hass, "config", None), "time_zone", None) or "UTC"
    readings_after_mold = {room.area_id: room for room in rooms_with_mold}
    settings = mold_calibrations if isinstance(mold_calibrations, dict) else {}
    profiles = room_profiles if isinstance(room_profiles, dict) else {}
    result: dict[str, dict] = {}
    for room in raw_rooms:
        raw_mold = readings_after_mold.get(room.area_id)
        calibrated = settings.get(room.area_id, {})
        if not isinstance(calibrated, dict):
            calibrated = {}
        profile = profiles.get(room.area_id, {})
        if not isinstance(profile, dict):
            profile = {}
        from .room_sources import selected
        temperature_inputs = selected({"room_sources": source_selections or {}}, room.area_id, "temperature")
        indoor_t, temp_source, temp_source_status = _room_temperature(
            hass, room.area_id, calibrated, max_age_minutes, profile.get("temperature_entity"),
            selected_entities=temperature_inputs,
        )
        optional_data, optional_sources, _optional_tracked = extend_room_inputs(
            hass, room.area_id, profile, max_age=max_age_minutes,
        )
        indoor_rh = _single_value(room.readings, "humidity")
        pm25 = _single_value(room.readings, "pm25")
        pm10 = _single_value(room.readings, "pm10")
        co2 = _single_value(room.readings, "co2")
        mold = next((
            r for r in (raw_mold.readings if raw_mold else ())
            if r.metric == "mold" and r.value is not None
        ), None)
        surface_c = (mold.details or {}).get("estimated_surface_c") if mold else None
        surface_rh = mold.value if mold else None
        win_values = [w.opened for w in room.windows]
        # A window is definitely open if any contact reads open; unknown if all
        # readings are unknown or a missing contact could be open.
        window_open = (True if True in win_values else
                       False if win_values and all(v is False for v in win_values) else None)
        occupied = _occupancy_state(hass, room.area_id, max_age_minutes)
        changed = history.add(room.area_id, {
            "temperature_c": indoor_t, "humidity": indoor_rh,
            "pm25": pm25, "pm10": pm10, "co2": co2,
            "surface_rh": surface_rh,
            "window_open": window_open, "occupied": occupied,
            **optional_data,
        }, now=stamp) or changed
        samples = history.samples(room.area_id)
        moisture = moisture_potential(indoor_t, indoor_rh, outdoor_t, outdoor_rh)
        comfort = adaptive_comfort(indoor_t, mean_outdoor)
        cooling = passive_cooling(indoor_t, outdoor_t, comfort.get("upper_80_c"), outside_safe)
        condensation = surface_condensation(indoor_t, indoor_rh, surface_c)
        exposure = threshold_exposure_hours(samples, "surface_rh", 80.0, stamp)
        pm25_24h = weighted_window(samples, "pm25", stamp, DAY_S)
        pm10_24h = weighted_window(samples, "pm10", stamp, DAY_S)
        co2_data = co2_trend(samples, stamp)
        ach = co2_decay_ach(samples, stamp, outdoor_co2)
        base_report = {
            "moisture": moisture,
            "thermal_comfort": comfort,
            "passive_cooling": cooling,
            "condensation": condensation,
            "surface_rh_exposure_24h": exposure,
            "pm25_24h": {**pm25_24h, "who_2021_24h_guideline_ug_m3": 15},
            "pm10_24h": {**pm10_24h, "who_2021_24h_guideline_ug_m3": 45},
            "co2_trend": co2_data,
            "nighttime_overheating": nighttime_overheating_exposure(samples, stamp, timezone_name),
            "co2_decay_ach": ach,
            "heat_per_full_air_exchange_wh_m3": heat_per_air_exchange_wh_m3(indoor_t, outdoor_t),
            "sources": {
                "indoor_temperature_entity": temp_source,
                "selected_temperature_entities": list(temperature_inputs) if temperature_inputs is not None else None,
                "indoor_temperature_status": temp_source_status,
                "outdoor_weather_entity": wx.entity_id if wx else None,
                "outdoor_weather_status": "one_source" if wx else
                     "multiple_sources" if len(selected_weather) > 1 else "unavailable",
                "humidity_sensors": sum(r.metric == "humidity" and r.value is not None for r in room.readings),
                "occupancy_known": occupied is not None,
                "outdoor_co2_measured": outdoor_co2 is not None,
                "co2_sensor_technology_verified": False,
                "co2_sensor_note": "Verify NDIR technology manually; eCO2 is not true CO2",
                "pm_high_humidity_interference_caution": indoor_rh is not None and indoor_rh >= 85,
                "optional_entity_sources": optional_sources,
            },
        }
        extra, daily_saved = room_science(
            hass, room.area_id, profile, samples, stamp,
            history=history, outside_safe=outside_safe, existing=base_report,
        )
        outdoor_mean = weighted_window(history.samples("__outside__"), "outdoor_pm25", stamp, DAY_S)
        indoor_mean = base_report["pm25_24h"]
        if (outdoor_mean.get("status") == "ready"
                and indoor_mean.get("status") == "ready" and outdoor_mean["mean"] > 0.1):
            extra["particle_indoor_outdoor_ratio"] = {
                "status":"descriptive_only", "ratio":round(indoor_mean["mean"]/outdoor_mean["mean"],2),
                "indoor_pm25_24h":indoor_mean["mean"], "outdoor_pm25_24h":outdoor_mean["mean"],
                "is_infiltration_fraction":False,
                "note":"Cannot infer infiltration: indoor sources, deposition and airflow are unmeasured."
            }
        else:
            extra["particle_indoor_outdoor_ratio"] = {"status":"insufficient_coverage"}
        base_report["international"] = extra
        changed = daily_saved or changed
        result[room.area_id] = base_report
    return result, changed
