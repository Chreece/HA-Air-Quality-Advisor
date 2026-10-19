"""Deterministic indoor-environment calculations with explicit evidence limits.

References:
- ASHRAE Standard 55 adaptive thermal comfort: applicable only to naturally
  conditioned, occupant-controlled spaces with suitable operative temperature.
- ISO 13788: surface humidity and condensation risk (NOT mold probability).
- WHO 2021 particulate guidelines: 24-hour averages, NOT instantaneous limits.
- ISO 12569: decay estimates require no source, well-mixed air and stable air flow.
- SI psychrometrics: Magnus vapor pressure and ideal-gas humidity ratio.

None of these calculations certify health, thermal comfort or air exchange.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

PRESSURE_PA = 101325.0
R_VAPOR = 461.5
MAX_GAP_S = 15 * 60
DAY_S = 24 * 60 * 60
WEEK_S = 7 * DAY_S


def _valid(value: Any, low: float, high: float) -> float | None:
    try:
        v = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return v if math.isfinite(v) and low <= v <= high else None


def saturation_vapor_pressure_pa(temp_c: float) -> float | None:
    """Magnus approximation valid for ordinary inhabited/outdoor temperatures."""
    t = _valid(temp_c, -45, 65)
    return 610.94 * math.exp(17.625 * t / (t + 243.04)) if t is not None else None


def humidity_ratio_g_kg(temp_c: float, rh_percent: float, pressure_pa: float = PRESSURE_PA) -> float | None:
    """Mass of water vapor per kilogram of DRY air (pressure dependent)."""
    sat = saturation_vapor_pressure_pa(temp_c)
    rh = _valid(rh_percent, 0.1, 100)
    p = _valid(pressure_pa, 60000, 110000)
    if sat is None or rh is None or p is None:
        return None
    vap = rh / 100 * sat
    if vap >= p:
        return None
    return 1000 * 0.621945 * vap / (p - vap)


def absolute_humidity_g_m3(temp_c: float, rh_percent: float) -> float | None:
    """Mass of water vapor per cubic meter at the specified air temperature."""
    sat = saturation_vapor_pressure_pa(temp_c)
    rh = _valid(rh_percent, 0.1, 100)
    if sat is None or rh is None:
        return None
    return (sat * rh / 100) / (R_VAPOR * (float(temp_c) + 273.15)) * 1000


def dew_point_c(temp_c: float, rh_percent: float) -> float | None:
    t = _valid(temp_c, -45, 65)
    rh = _valid(rh_percent, 0.1, 100)
    if t is None or rh is None:
        return None
    gamma = math.log(rh / 100) + 17.625 * t / (243.04 + t)
    return 243.04 * gamma / (17.625 - gamma)


def rh_at_temperature_from_ratio(ratio_g_kg: float, target_c: float, pressure_pa: float = PRESSURE_PA) -> float | None:
    w = _valid(ratio_g_kg, 0, 70)
    sat = saturation_vapor_pressure_pa(target_c)
    p = _valid(pressure_pa, 60000, 110000)
    if w is None or sat is None or p is None:
        return None
    vap = p * (w / 1000) / (0.621945 + w / 1000)
    return 100 * vap / sat


def moisture_potential(indoor_c: float | None, indoor_rh: float | None,
                       outdoor_c: float | None, outdoor_rh: float | None,
                       *, pressure_pa: float = PRESSURE_PA) -> dict[str, Any]:
    """Compare moisture mass; cold air with high RH may have strong drying potential.

    Positive drying_potential_g_kg means outside air has LESS water vapor per
    kilogram of dry air. Heating outside air to indoor temperature is an
    equilibrium illustration, NOT a forecast of room RH or mixing time.
    """
    inside = humidity_ratio_g_kg(indoor_c, indoor_rh, pressure_pa)
    outside = humidity_ratio_g_kg(outdoor_c, outdoor_rh, pressure_pa)
    if inside is None or outside is None:
        return {"status": "unavailable", "reason": "temperature_or_relative_humidity_missing"}
    diff = inside - outside
    status = "drying" if diff >= 1.0 else "humidifying" if diff <= -1.0 else "neutral"
    predicted = rh_at_temperature_from_ratio(outside, indoor_c, pressure_pa)
    return {
        "status": status,
        "drying_potential_g_kg": round(diff, 2),
        "indoor_humidity_ratio_g_kg": round(inside, 2),
        "outdoor_humidity_ratio_g_kg": round(outside, 2),
        "indoor_absolute_humidity_g_m3": round(absolute_humidity_g_m3(indoor_c, indoor_rh), 2),
        "outdoor_absolute_humidity_g_m3": round(absolute_humidity_g_m3(outdoor_c, outdoor_rh), 2),
        "outside_air_rh_when_warmed_percent": round(predicted, 1) if predicted is not None else None,
        "indoor_dew_point_c": round(dew_point_c(indoor_c, indoor_rh), 2),
        "method": "humidity_ratio_ideal_gas_magnus",
    }


def adaptive_comfort(indoor_air_c: float | None, prevailing_outdoor_c: float | None) -> dict[str, Any]:
    """ASHRAE 55 80% acceptability adaptive band, with air-temp proxy warning.

    This is an informative APPROXIMATION, not a full standard compliance test:
    operative temperature, occupant control, clothing, activity and inactive
    mechanical conditioning cannot be verified by ordinary HA temperature data.
    """
    indoor = _valid(indoor_air_c, -10, 55)
    outdoor = _valid(prevailing_outdoor_c, -45, 55)
    if indoor is None or outdoor is None:
        return {"status": "unavailable", "method": "ashrae55_adaptive_80_proxy"}
    if not 10 <= outdoor <= 33.5:
        return {"status": "outside_applicability", "prevailing_outdoor_c": round(outdoor, 2),
                "method": "ashrae55_adaptive_80_proxy"}
    center = 0.31 * outdoor + 17.8
    lower, upper = center - 3.5, center + 3.5
    status = "below_band" if indoor < lower else "above_band" if indoor > upper else "within_band"
    return {
        "status": status, "temperature_proxy_c": round(indoor, 2),
        "prevailing_outdoor_c": round(outdoor, 2),
        "comfort_center_c": round(center, 2),
        "lower_80_c": round(lower, 2), "upper_80_c": round(upper, 2),
        "method": "ashrae55_adaptive_80_proxy",
        "requires_naturally_conditioned_space": True,
        "air_temperature_is_not_operative_temperature": True,
    }


def passive_cooling(indoor_c: float | None, outdoor_c: float | None,
                    comfort_upper_c: float | None, outdoor_safe: bool) -> dict[str, Any]:
    """Physical cooling opportunity, not evidence of sufficient air flow."""
    indoor = _valid(indoor_c, -10, 55)
    outdoor = _valid(outdoor_c, -45, 55)
    upper = _valid(comfort_upper_c, 15, 45) if comfort_upper_c is not None else None
    if indoor is None or outdoor is None:
        return {"status": "unavailable"}
    delta = indoor - outdoor
    # Without an applicable comfort model, report only the thermal delta;
    # never assert that a room is too hot.
    if upper is None:
        return {"status": "comfort_model_unavailable", "cooling_delta_c": round(delta, 2)}
    if not outdoor_safe:
        status = "outdoors_blocked"
    elif indoor <= upper:
        status = "not_needed"
    elif delta < 2:
        status = "insufficient_temperature_difference"
    else:
        status = "cooling_opportunity"
    return {"status": status, "cooling_delta_c": round(delta, 2)}


def heat_per_air_exchange_wh_m3(indoor_c: float | None, outdoor_c: float | None) -> float | None:
    """Approx sensible thermal energy PER m3 of exchanged air (NOT actual use)."""
    indoor = _valid(indoor_c, -10, 55)
    outdoor = _valid(outdoor_c, -45, 55)
    return round(0.335 * abs(indoor - outdoor), 2) if indoor is not None and outdoor is not None else None


def surface_condensation(indoor_c: float | None, indoor_rh: float | None,
                         surface_c: float | None) -> dict[str, Any]:
    """Surface RH and dew point gap; no mold probability is inferred."""
    dp = dew_point_c(indoor_c, indoor_rh)
    surface = _valid(surface_c, -45, 65)
    if dp is None or surface is None:
        return {"status": "unavailable"}
    p = saturation_vapor_pressure_pa(dp)
    sat = saturation_vapor_pressure_pa(surface)
    surface_rh = min(100, 100 * p / sat)
    margin = surface - dp
    return {
        "status": "condensation_possible" if margin <= 0 else
                  "high_surface_humidity" if surface_rh >= 80 else "lower_surface_humidity",
        "surface_relative_humidity_percent": round(surface_rh, 1),
        "dew_point_c": round(dp, 2),
        "condensation_margin_c": round(margin, 2),
        "surface_temperature_c": round(surface, 2),
        "method": "surface_vapor_pressure_iso13788_context",
    }


def weighted_window(samples: Sequence[dict], key: str, now: float, seconds: float,
                    *, max_gap_s: float = MAX_GAP_S,
                    min_coverage: float = 0.8) -> dict[str, Any]:
    """Time-weighted trapezoidal average over valid contiguous observations.

    Unlike an arithmetic sample mean, gaps beyond max_gap_s are excluded.
    A complete-window result is withheld until the coverage requirement is met.
    """
    end = _valid(now, 0, 9e12)
    if end is None or seconds <= 0:
        return {"status": "unavailable", "coverage_percent": 0}
    start, total, covered = end - seconds, 0.0, 0.0
    ordered = sorted((s for s in samples if isinstance(s, dict)), key=lambda s: s.get("t", -1))
    for a, b in zip(ordered, ordered[1:]):
        try:
            t1, t2 = float(a["t"]), float(b["t"])
        except (TypeError, ValueError, KeyError, OverflowError):
            continue
        if not (math.isfinite(t1) and math.isfinite(t2)) or not 0 < t2 - t1 <= max_gap_s:
            continue
        va, vb = _valid(a.get(key), -100, 200000), _valid(b.get(key), -100, 200000)
        if va is None or vb is None:
            continue
        left, right = max(start, t1), min(end, t2)
        if right <= left:
            continue
        vleft = va + (vb - va) * (left - t1) / (t2 - t1)
        vright = va + (vb - va) * (right - t1) / (t2 - t1)
        total += (vleft + vright) / 2 * (right - left)
        covered += right - left
    coverage = 100 * covered / seconds
    result = {"status": "ready" if covered >= min_coverage * seconds else "insufficient_coverage",
              "coverage_percent": round(coverage, 1)}
    if result["status"] == "ready":
        result["mean"] = round(total / covered, 2)
    return result


def threshold_exposure_hours(samples: Sequence[dict], key: str, threshold: float,
                             now: float, seconds: float = DAY_S) -> dict[str, Any]:
    """Observed duration above a threshold, without filling unknown time gaps."""
    start, duration, observed = now - seconds, 0.0, 0.0
    ordered = sorted((s for s in samples if isinstance(s, dict)), key=lambda s: s.get("t", -1))
    for a, b in zip(ordered, ordered[1:]):
        try:
            t1, t2 = float(a["t"]), float(b["t"])
        except (TypeError, ValueError, KeyError, OverflowError):
            continue
        if not 0 < t2 - t1 <= MAX_GAP_S:
            continue
        va, vb = _valid(a.get(key), 0, 100), _valid(b.get(key), 0, 100)
        if va is None or vb is None:
            continue
        left, right = max(start, t1), min(now, t2)
        if right <= left:
            continue
        x = va + (vb - va) * (left - t1) / (t2 - t1)
        y = va + (vb - va) * (right - t1) / (t2 - t1)
        fraction = 1.0 if x >= threshold and y >= threshold else (
            0.0 if x < threshold and y < threshold else
            max(0.0, min(1.0, (max(x, y) - threshold) / abs(y - x)))
        )
        observed += right - left
        duration += fraction * (right - left)
    return {"observed_hours": round(observed / 3600, 2),
            "above_threshold_hours": round(duration / 3600, 2),
            "coverage_percent": round(100 * observed / seconds, 1),
            "threshold_percent": threshold,
            "status": "ready" if observed >= seconds * 0.8 else "insufficient_coverage"}


def co2_trend(samples: Sequence[dict], now: float) -> dict[str, Any]:
    """Linear first/last trend only when at least 3 valid recent observations."""
    ordered = [s for s in samples if now - 30 * 60 <= s.get("t", -1) <= now
               and _valid(s.get("co2"), 250, 20000) is not None]
    if len(ordered) < 3:
        return {"status": "insufficient_data"}
    ordered.sort(key=lambda s: s["t"])
    duration = ordered[-1]["t"] - ordered[0]["t"]
    if duration < 10 * 60:
        return {"status": "insufficient_data"}
    # A simple descriptive slope is not an inferred air exchange rate.
    rate = (ordered[-1]["co2"] - ordered[0]["co2"]) / duration * 3600
    return {"status": "ready", "trend_ppm_per_hour": round(rate, 1),
            "observation_minutes": round(duration / 60, 1)}


def co2_decay_ach(samples: Sequence[dict], now: float, outdoor_co2: float | None) -> dict[str, Any]:
    """Conditional tracer-gas decay estimate: vacancy and open windows REQUIRED.

    A passive CO2 time series cannot establish well-mixed air or steady flow,
    so this remains a tentative engineering estimate, never a safety assertion.
    """
    base = _valid(outdoor_co2, 250, 1500)
    if base is None:
        return {"status": "outdoor_co2_required"}
    data = [s for s in samples if now - 40 * 60 <= s.get("t", -1) <= now]
    data.sort(key=lambda s: s["t"])
    if len(data) < 4 or data[-1]["t"] - data[0]["t"] < 15 * 60:
        return {"status": "insufficient_data"}
    if any(s.get("occupied") is not False or s.get("window_open") is not True
           for s in data):
        return {"status": "vacant_open_window_required"}
    values = [_valid(s.get("co2"), 250, 20000) for s in data]
    if any(v is None for v in values):
        return {"status": "invalid_co2"}
    if any(b["t"] - a["t"] > MAX_GAP_S for a, b in zip(data, data[1:])):
        return {"status": "insufficient_data"}
    first, last = values[0] - base, values[-1] - base
    if first < 150 or last < 75 or last >= first:
        return {"status": "insufficient_decay"}
    # Reject readings with large spikes during the supposed unoccupied decay.
    if any(b > a + 35 for a, b in zip(values, values[1:])):
        return {"status": "unstable_decay"}
    ach = math.log(first / last) / ((data[-1]["t"] - data[0]["t"]) / 3600)
    if not 0 < ach < 20:
        return {"status": "implausible_rate"}
    return {"status": "estimate", "ach_per_hour": round(ach, 2),
            "assumptions": "vacant_well_mixed_stable_flow",
            "duration_minutes": round((data[-1]["t"] - data[0]["t"]) / 60, 1)}


def nighttime_overheating_exposure(samples: Sequence[dict], now: float,
                                  local_timezone: str = "UTC",
                                  *, threshold_c: float = 26.0) -> dict[str, Any]:
    """Observed hot sleeping hours (22:00–07:00), NOT TM59 compliance.

    The CIBSE TM59 design method requires dynamic simulation and occupancy
    assumptions. This is only an observed air-temperature duration indicator.
    """
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        zone = ZoneInfo(local_timezone)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        zone = timezone.utc
    since = now - WEEK_S
    observed, above = 0.0, 0.0
    valid = [s for s in samples if isinstance(s, dict) and
             isinstance(s.get("t"), (float, int))]
    valid.sort(key=lambda s: s["t"])
    for a, b in zip(valid, valid[1:]):
        try:
            t1, t2 = float(a["t"]), float(b["t"])
        except (TypeError, ValueError, OverflowError):
            continue
        if not 0 < t2 - t1 <= MAX_GAP_S:
            continue
        va, vb = _valid(a.get("temperature_c"), -10, 55), _valid(b.get("temperature_c"), -10, 55)
        if va is None or vb is None:
            continue
        left, right = max(since, t1), min(now, t2)
        if right <= left:
            continue
        mid = datetime.fromtimestamp((left + right) / 2, zone)
        if not (mid.hour >= 22 or mid.hour < 7):
            continue
        x = va + (vb - va) * (left - t1) / (t2 - t1)
        y = va + (vb - va) * (right - t1) / (t2 - t1)
        fraction = (1 if x >= threshold_c and y >= threshold_c else
                    0 if x < threshold_c and y < threshold_c else
                    max(0.0, min(1.0, (max(x, y) - threshold_c) / abs(y - x))))
        observed += right - left
        above += fraction * (right - left)
    # Seven nights at nominal nine hours; DST may vary, so only an estimate.
    nominal_s = 7 * 9 * 3600
    return {"status": "ready" if observed >= 0.8 * nominal_s else "insufficient_coverage",
            "above_threshold_hours": round(above / 3600, 2),
            "observed_hours": round(observed / 3600, 2),
            "threshold_c": threshold_c,
            "timezone": local_timezone,
            "method": "observed_22_to_07_not_tm59_compliance"}


