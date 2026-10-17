"""Compact, presentation-neutral snapshot for the Lovelace dashboard card.

The backend owns the safety decision and measurement normalisation; the card
only presents the result in the Home Assistant user's interface language.
"""

from __future__ import annotations

from typing import Any

from .const import UNIT_LABEL
from .logic import Plan, Reading, Reason, Room, Weather, Warning

_MISSING_OUTSIDE = frozenset({
    "no_outdoor_data", "no_weather_data", "unavailable_weather", "unavailable_warning"
})


def _reason(reason: Reason) -> dict[str, str]:
    return {"code": reason.code, "label": reason.label, "value": reason.value}


def _reading(reading: Reading, threshold: float | None, *, indoor: bool) -> dict[str, Any]:
    value = reading.value
    return {
        "entity_id": reading.entity_id,
        "name": reading.name,
        "metric": reading.metric,
        "unit": UNIT_LABEL.get(reading.metric, ""),
        "value": value,
        "threshold": threshold,
        "available": value is not None,
        **({"details": reading.details} if reading.details else {}),
        "exceeded": (
            value is not None and threshold is not None
            and (value >= threshold if indoor else value > threshold)
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


def _room(room: Room, plan: Plan, limits: dict[str, float]) -> dict[str, Any]:
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
    if high or (recommended and recommended.action == "close"):
        status = "attention"
    elif not known or incomplete_air or incomplete_windows:
        status = "unknown"
    else:
        status = "safe"

    missing_mold = next(
        (item for item in readings if item["metric"] == "mold" and not item["available"]),
        None,
    )
    mold_data_status = (missing_mold or {}).get("details", {}).get("status")
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
        "status": status,
        "status_detail": status_detail,
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
        "rooms": room_data,
        "outdoor": {
            "status": outside_status,
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
