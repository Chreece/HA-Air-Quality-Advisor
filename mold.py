"""Pure calibrated mold-indication calculations; no Home Assistant dependencies.

The predicted relative humidity at a room's coldest surface follows
Home Assistant's Mold Indicator (Magnus approximation). Calibration requires
simultaneous room, outdoor and cold-surface measurements.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from .logic import Reading, Room, Weather

MAGNUS_A = 17.62
MAGNUS_B = 243.12


def _temperature(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) and -60 <= number <= 85 else None
    except (TypeError, ValueError, OverflowError):
        return None


def calibration_factor(indoor_c: float, outdoor_c: float, surface_c: float) -> float | None:
    """Calculate HA-compatible factor from three simultaneous temperatures.

    A difference of at least 3°C makes the estimate less unstable. A very
    small surface/outdoor denominator, or extreme factor, is not usable.
    Negative factors are valid for unusual thermal conditions (as in HA).
    """
    inside, outside, surface = (_temperature(v) for v in (indoor_c, outdoor_c, surface_c))
    if any(value is None for value in (inside, outside, surface)):
        return None
    if abs(inside - outside) < 3 or abs(surface - outside) < 0.5:
        return None
    factor = (inside - outside) / (surface - outside)
    return factor if math.isfinite(factor) and 0.5 <= abs(factor) <= 20 else None


def mean_valid_humidity(readings: tuple[Reading, ...]) -> tuple[float | None, int]:
    """Ignore zero, negative, out-of-range, NaN, unknown and missing RH."""
    valid = [
        item.value for item in readings
        if item.metric == "humidity" and item.value is not None
        and isinstance(item.value, (int, float))
        and math.isfinite(item.value) and 0 < item.value <= 100
    ]
    return (sum(valid) / len(valid), len(valid)) if valid else (None, 0)


@dataclass(frozen=True)
class MoldEstimate:
    surface_humidity: float
    indoor_humidity: float
    dewpoint_c: float
    estimated_surface_c: float


def estimate_mold(
    indoor_c: float | None, outdoor_c: float | None,
    humidity: float | None, factor: float | None,
) -> MoldEstimate | None:
    """Estimate surface RH, clamped to 0–100% (not percent probability)."""
    inside, outside = _temperature(indoor_c), _temperature(outdoor_c)
    try:
        rh, f = float(humidity), float(factor)
    except (TypeError, ValueError, OverflowError):
        return None
    if (inside is None or outside is None or not math.isfinite(rh)
            or not 0 < rh <= 100 or not math.isfinite(f)
            or not 0.5 <= abs(f) <= 20):
        return None

    gamma = math.log(rh / 100.0) + MAGNUS_A * inside / (MAGNUS_B + inside)
    dewpoint = MAGNUS_B * gamma / (MAGNUS_A - gamma)
    surface = outside + (inside - outside) / f
    try:
        saturation_ratio = math.exp(
            MAGNUS_A * dewpoint / (MAGNUS_B + dewpoint)
            - MAGNUS_A * surface / (MAGNUS_B + surface)
        )
    except (ValueError, OverflowError, ZeroDivisionError):
        return None
    if not math.isfinite(saturation_ratio):
        return None
    return MoldEstimate(
        surface_humidity=round(min(100.0, max(0.0, 100.0 * saturation_ratio)), 1),
        indoor_humidity=round(rh, 1),
        dewpoint_c=round(dewpoint, 2),
        estimated_surface_c=round(surface, 2),
    )


def estimate_mold_for_room(
    room: Room, indoor_c: float | None,
    weather: tuple[Weather, ...], calibration: dict[str, Any],
) -> Reading:
    """Add one derived mold reading per room, never treating missing data as safe."""
    label = "Mold indication"
    entity = f"derived.mold_{room.area_id}"
    factor = calibration.get("calibration_factor")
    outdoor_id = calibration.get("outdoor_weather_entity")
    outdoor_c = next(
        (item.temperature_c for item in weather if item.entity_id == outdoor_id),
        None,
    )
    if not outdoor_id:
        # A not-yet-calibrated room can still show whether any selected
        # weather provider supplies the outdoor temperature needed for setup.
        # Once calibrated, the original provider is pinned, never silently
        # replaced with another weather source.
        outdoor_c = next(
            (item.temperature_c for item in weather if item.temperature_c is not None),
            None,
        )
    avg, count = mean_valid_humidity(room.readings)
    result = estimate_mold(indoor_c, outdoor_c, avg, factor)

    # Distinguish a calibration that has not been supplied from a calibrated
    # room whose live sensors are temporarily unavailable. The presentation
    # must never mistake either case for "no indoor measurements".
    try:
        factor_number = float(factor)
    except (ValueError, TypeError, OverflowError):
        factor_number = float("nan")
    calibrated = (
        isinstance(outdoor_id, str) and bool(outdoor_id)
        and math.isfinite(factor_number) and 0.5 <= abs(factor_number) <= 20
    )
    data_status = (
        "needs_calibration" if not calibrated else
        "inputs_unavailable" if result is None else "ready"
    )

    # Report *every* unavailable input, not only the first one encountered.
    # These are presentation/diagnostic warnings, never TTS events or
    # additional conditions for triggering open/close window announcements.
    missing_inputs: list[str] = []
    if not calibrated:
        missing_inputs.append("calibration")
    if _temperature(indoor_c) is None:
        missing_inputs.append("indoor_temperature")
    if _temperature(outdoor_c) is None:
        missing_inputs.append("outdoor_temperature")
    if avg is None:
        missing_inputs.append("humidity")
    if result is None and not missing_inputs:
        missing_inputs.append("calculation")

    details: dict[str, float | int | str | list[str]] = {
        "humidity_sensor_count": count,
        "status": data_status,
        "missing_inputs": missing_inputs,
    }
    if calibrated:
        # Preserve the exact saved floating-point factor; rounding is a
        # presentation concern only and must not alter mold calculations.
        details["calibration_factor"] = factor_number
    if isinstance(outdoor_id, str):
        details["outdoor_weather_entity"] = outdoor_id
    indoor_sensor = calibration.get("indoor_temperature_entity")
    if isinstance(indoor_sensor, str):
        details["indoor_temperature_entity"] = indoor_sensor
    if avg is not None:
        details["average_indoor_humidity"] = round(avg, 1)
    if result:
        details.update({
            "dewpoint_c": result.dewpoint_c,
            "estimated_surface_c": result.estimated_surface_c,
            "indoor_temperature_c": round(float(indoor_c), 2),
            "outdoor_temperature_c": round(float(outdoor_c), 2),
        })
    return Reading(entity, label, "mold", result.surface_humidity if result else None, details)


def rh_fallback_for_room(room: Room, mold_reading: Reading) -> Reading | None:
    """Use averaged *valid included* room RH only while mold is unavailable.

    Fallback is the same 65% legacy indoor humidity metric, never a mold
    percentage and never a separate sensor or calibration factor. Once a
    valid mold estimate exists, it takes priority over any room RH.
    """
    if mold_reading.value is not None:
        return None
    mean, count = mean_valid_humidity(room.readings)
    if mean is None:
        return None
    return Reading(
        f"derived.rh_fallback_{room.area_id}",
        "Average room relative humidity (fallback)",
        "humidity",
        mean,  # Compare with threshold at full precision; formatting is UI-only.
        {
            "fallback_for_mold": True,
            "humidity_sensor_count": count,
        },
    )
