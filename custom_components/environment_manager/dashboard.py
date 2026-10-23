"""Compact, presentation-neutral snapshot for the Lovelace dashboard card.

The backend owns the safety decision and measurement normalisation; the card
only presents the result in the Home Assistant user's interface language.
"""

from __future__ import annotations

from typing import Any

from .const import UNIT_LABEL
from .logic import Plan, Reading, Reason, Room, Weather, Warning

_MISSING_OUTSIDE = frozenset({
    "no_outdoor_data", "no_weather_data", "unavailable_weather", "unavailable_warning",
    "aqi_scale_unconfigured"
})


def _reason(reason: Reason) -> dict[str, str]:
    return {"code": reason.code, "label": reason.label, "value": reason.value}


def _reading(reading: Reading, threshold: float | None, *, indoor: bool) -> dict[str, Any]:
    value = reading.value
    aqi = (reading.details or {}).get("aqi", {}) if reading.metric == "aqi" else {}
    if aqi:
        threshold = aqi.get("custom_limit") if aqi.get("scale") == "custom" else (
            100 if aqi.get("scale") == "us_epa" else
            3 if aqi.get("scale") == "eea_category" else None
        )
    return {
        "entity_id": reading.entity_id,
        "name": reading.name,
        "metric": reading.metric,
        "unit": ("US AQI" if aqi.get("scale") == "us_epa"
                 else "EEA category" if aqi.get("scale") == "eea_category"
                 else UNIT_LABEL.get(reading.metric, "")),
        "value": value,
        "threshold": threshold,
        "available": value is not None,
        **({"details": reading.details} if reading.details else {}),
        "exceeded": (
            bool(aqi.get("operational_unsafe"))
            if aqi else
            (value is not None and threshold is not None
             and (value >= threshold if indoor else value > threshold))
        ),
    }


def _window(window: Any) -> dict[str, Any]:
    return {"entity_id": window.entity_id, "name": window.name, "opened": window.opened}


def _weather(item: Weather) -> dict[str, Any]:
    return {
        "entity_id": item.entity_id,
        "condition": item.condition,
        "temperature_c": item.temperature_c,
        "humidity": item.humidity,
        "wind_kmh": item.wind_kmh,
    }


def _warning(item: Warning) -> dict[str, Any]:
    return {"entity_id": item.entity_id, "name": item.name, "active": item.active}


def _room(room: Room, plan: Plan, limits: dict[str, float], *,
          climate_only: bool = False) -> dict[str, Any]:
    readings = [
        _reading(item, limits.get(f"indoor_{item.metric}"), indoor=True)
        for item in room.readings
    ]
    high = [item for item in readings if item["exceeded"]]
    known = any(item["available"] for item in readings)
    incomplete_air = any(not item["available"] for item in readings)
    opened = [item for item in room.windows if item.opened is True]
    incomplete_windows = not room.windows or any(item.opened is None for item in room.windows)
    recommended = next((rec for rec in plan.recommendations if rec.area_id == room.area_id), None)

    # Urgent closure always needs attention, even if indoor sensors are missing.
    # Indoor values over a threshold remain important while already ventilating
    # or when opening is prevented by outdoor hazards.
    extended = plan.environment.get(room.area_id, {}).get("international", {})
    hcho = extended.get("formaldehyde_30min", {})
    radon = extended.get("radon", {})
    evidence_high = ((hcho.get("status") == "ready" and hcho.get("above_who_100ug_m3"))
                     or (radon.get("status") == "annual_screening" and radon.get("above_reference")))
    if climate_only:
        # A room enabled only for HVAC must never appear as air-quality safe.
        status = "unknown"
    elif high or evidence_high or (recommended and recommended.action == "close"):
        status = "attention"
    elif not known or incomplete_air or incomplete_windows:
        status = "unknown"
    else:
        status = "safe"

    missing_mold = next(
        (item for item in readings if item["metric"] == "mold" and not item["available"]),
        None,
    )
    mold_details = (missing_mold or {}).get("details", {}) or {}
    mold_data_status = mold_details.get("status")
    mold_warnings = [
        code for code in mold_details.get("missing_inputs", [])
        if code in {
            "calibration", "indoor_temperature",
            "outdoor_temperature", "humidity", "calculation",
        }
    ]
    # The fallback is a measured room RH average, not a calculated surface
    # RH reading. The dashboard must label the substitution explicitly and
    # retain mold diagnostics even if the fallback itself is healthy.
    fallback = next(
        (item for item in readings
         if item["metric"] == "humidity"
         and (item.get("details") or {}).get("fallback_for_mold")
         and item["available"]),
        None,
    )
    if status == "unknown":
        if mold_data_status == "needs_calibration":
            status_detail = "mold_not_calibrated"
        elif mold_data_status == "inputs_unavailable":
            status_detail = "mold_inputs_unavailable"
        elif known:
            status_detail = "partial_indoor_data"
        else:
            status_detail = "no_indoor_data"
    else:
        status_detail = None

    return {
        "area_id": room.area_id,
        "name": room.name,
        "climate_only": climate_only,
        "status": status,
        "status_detail": status_detail,
        "mold_warnings": mold_warnings,
        "environment": plan.environment.get(room.area_id, {}),
        "rh_fallback": (
            {
                "active": True,
                "value": fallback["value"],
                "threshold": fallback["threshold"],
                "humidity_sensor_count": fallback["details"]["humidity_sensor_count"],
            }
            if fallback else {"active": False}
        ),
        "action": recommended.action if recommended else None,
        "action_window_ids": [w.entity_id for w in recommended.windows] if recommended else [],
        "open_count": len(opened),
        "window_count": len(room.windows),
        "windows": [_window(item) for item in room.windows],
        "readings": readings,
        "high_count": len(high),
        "available_count": sum(item["available"] for item in readings),
        "ventilating": bool(opened) and plan.outdoor_safe,
        "reasons": [_reason(reason) for reason in recommended.reasons] if recommended else [],
    }


def dashboard_snapshot(plan: Plan, limits: dict[str, float]) -> dict[str, Any]:
    """Describe *all* monitored rooms, not only actionable recommendations.

    Missing sensors are explicitly marked unknown, never optimistically green.
    Incomplete outside air readings are not a known hazard and must not trigger
    closing a window, but the UI must not imply complete verification either.
    """
    room_data = [_room(room, plan, limits) for room in plan.rooms]
    # Distinct from monitored rooms: show explicitly configured climate-only
    # rooms without making up window advice or inflating AQ summary totals.
    already={room.area_id for room in plan.rooms}
    extra=[_room(room,plan,limits,climate_only=True)
           for room in plan.climate_rooms if room.area_id not in already]
    summary = {
        "total": len(room_data),
        "safe": sum(room["status"] == "safe" for room in room_data),
        "attention": sum(room["status"] == "attention" for room in room_data),
        "unknown": sum(room["status"] == "unknown" for room in room_data),
    }
    missing_conditions = bool(plan.unavailable_outdoor) or any(
        reason.code in _MISSING_OUTSIDE for reason in plan.outside_reasons
    )
    known_hazards = any(
        reason.code not in _MISSING_OUTSIDE for reason in plan.outside_reasons
    )
    outside_status = (
        "unsafe" if known_hazards else
        "unknown" if not plan.outdoor_safe else
        "partial" if missing_conditions else "safe"
    )

    return {
        "version": 1,
        "summary": summary,
        "rooms": room_data+extra,
        "climate_only_count":len(extra),
        "outdoor": {
            "status": outside_status,
            "pollen": plan.environment.get("__outside__", {}).get("pollen", {"status":"not_configured"}),
            "safe_to_ventilate": plan.outdoor_safe,
            "data_complete": not missing_conditions,
            "readings": [
                _reading(item, limits.get(f"outdoor_{item.metric}"), indoor=False)
                for item in plan.outdoor_readings
            ],
            "weather": [_weather(item) for item in plan.weather],
            "warnings": [_warning(item) for item in plan.warnings],
            "blockers": [_reason(reason) for reason in plan.outside_reasons],
            "unavailable_sensors": list(plan.unavailable_outdoor),
        },
    }
