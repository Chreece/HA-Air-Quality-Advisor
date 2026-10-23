"""Capability-aware HVAC classification and humidity advice.

No service calls: advisory data must never energize unknown equipment.
Home Assistant climate HVAC modes are not interchangeable with entity
capabilities such as target humidity or fan preset.
"""
from __future__ import annotations
from math import isfinite
from typing import Any

HVAC_MODES = frozenset(("off", "heat", "cool", "heat_cool", "auto",
                        "dry", "fan_only"))
TEMPERATURE_MODES = frozenset(("heat", "cool", "heat_cool", "auto"))
HUMIDITY_FEATURE = 1 << 2  # ClimateEntityFeature.TARGET_HUMIDITY
FAN_FEATURE = 1 << 3       # ClimateEntityFeature.FAN_MODE
SWING_FEATURE = 1 << 5     # ClimateEntityFeature.SWING_MODE


def classify_hvac(attributes: dict[str, Any], state: str) -> dict[str, Any]:
    """Report actual supported modes, not guessed equipment brands.

    A radiator, AC or heat pump is driven only by capabilities and explicit
    configuration. 'auto' alone does not imply both heat and cool.
    """
    if not isinstance(attributes, dict):
        return {"status": "invalid_attributes"}
    raw = attributes.get("hvac_modes")
    if not isinstance(raw, (list, tuple)):
        return {"status": "unknown_modes"}
    modes = sorted(set(m for m in raw if isinstance(m, str) and m in HVAC_MODES))
    try:
        flags = int(attributes.get("supported_features", 0))
    except (TypeError, ValueError, OverflowError):
        return {"status": "invalid_features"}
    if flags < 0:
        return {"status": "invalid_features"}
    return {
        "status": "ready", "modes": modes, "current": state,
        "heating": "heat" in modes or "heat_cool" in modes,
        "cooling": "cool" in modes or "heat_cool" in modes,
        "native_heat_cool": "heat_cool" in modes,
        "drying": "dry" in modes,
        "fan_only": "fan_only" in modes,
        "auto_unspecified": "auto" in modes,
        "temperature_setpoint": bool(flags & 1),
        "temperature_range": bool(flags & 2),
        "target_humidity": bool(flags & HUMIDITY_FEATURE),
        "fan_control": bool(flags & FAN_FEATURE),
        "swing_control": bool(flags & SWING_FEATURE),
    }


def humidity_advice(indoor_rh: Any, *, low_rh: float = 40.0,
                    high_rh: float = 60.0, hysteresis: float = 3.0,
                    previous: str = "idle",
                    drying_available: bool = False,
                    humidifying_available: bool = False) -> dict[str, Any]:
    """Recommend humidity action; does not switch HVAC modes.

    Sensor quality/freshness and competing moisture/ventilation policies must
    be checked by the caller before any future actuator implementation.
    """
    try:
        value = float(indoor_rh)
        low = float(low_rh)
        high = float(high_rh)
        band = float(hysteresis)
    except (TypeError, ValueError, OverflowError):
        return {"status": "insufficient_data"}
    if (not all(isfinite(v) for v in (value, low, high, band))
            or not 0 <= value <= 100 or not 20 <= low < high <= 80
            or not 0.5 <= band <= 10 or high-low < 2 * band):
        return {"status": "invalid_inputs"}
    if value >= high + band or (previous == "dry" and value > high - band):
        action = "dry"
    elif value <= low - band or (previous == "humidify" and value < low + band):
        action = "humidify"
    else:
        action = "idle"
    available = (action == "idle" or
                 (action == "dry" and drying_available) or
                 (action == "humidify" and humidifying_available))
    return {"status": "advisory", "action": action, "available": available,
            "measured_rh": value, "target_band_rh": [low, high],
            "reason": "humidity_hysteresis", "automatic_control": False}
