"""Internationally applicable indoor-environment science with explicit evidence gates.

Units, averaging intervals and sensor verification are never inferred from an
entity name. All calculations are deterministic, local and optional.
References: WHO 2021/2010, EEA 2026 AQI, US EPA AQI, ASHRAE 55, ISO 7730,
CIBSE TM52 and TM59 (observed data cannot certify simulation compliance).
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from collections.abc import Sequence
from typing import Any

from .building_physics import DAY_S, WEEK_S, MAX_GAP_S, weighted_window

US_BANDS = ((50, "good"), (100, "moderate"), (150, "unhealthy_for_sensitive"),
            (200, "unhealthy"), (300, "very_unhealthy"), (500, "hazardous"))
EU_BANDS = ("good", "fair", "moderate", "poor", "very_poor", "extremely_poor")
# Current EEA *hourly* air quality categories by measured µg/m³.
# EEA categories are not themselves a universal numeric AQI unit.
EU_HOURLY_UG_M3 = {
    "pm25": (5, 15, 50, 90, 140),
    "pm10": (15, 45, 120, 195, 270),
    "no2": (10, 25, 60, 100, 150),
    "o3": (60, 100, 120, 160, 180),
    "so2": (20, 40, 125, 190, 275),
}


def finite(value: Any, lower: float = 0, upper: float = 1e8) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        v = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return v if math.isfinite(v) and lower <= v <= upper else None


def aqi_category(value: Any, scale: str | None, *, custom_limit: float | None = None) -> dict:
    """Never guess an AQI scale from a geographic location or device name."""
    x = finite(value, 0, 10000)
    if x is None:
        return {"status": "unavailable"}
    if scale == "us_epa":
        if x > 500:
            return {"status": "invalid", "reason": "aqi_out_of_range"}
        category = next((label for top, label in US_BANDS if x <= top), "hazardous")
        return {"status": "ready", "category": category, "scale": scale,
                "operational_unsafe": x > 100, "value": x}
    if scale == "eea_category":
        if not 1 <= x <= 6 or int(x) != x:
            return {"status": "invalid", "reason": "eea_requires_integer_category_1_to_6"}
        return {"status": "ready", "category": EU_BANDS[int(x) - 1],
                "scale": scale, "operational_unsafe": x >= 4, "value": x}
    if scale == "custom":
        limit = finite(custom_limit, 0, 10000)
        if limit is None:
            return {"status": "configuration_required", "reason": "custom_limit_required"}
        return {"status": "ready", "category": "above_limit" if x > limit else "within_limit",
                "scale": scale, "operational_unsafe": x > limit,
                "custom_limit": limit, "value": x}
    return {"status": "configuration_required", "reason": "aqi_scale_not_selected"}


def eea_hourly_category(metric: str, value_ug_m3: Any) -> dict:
    bounds = EU_HOURLY_UG_M3.get(metric)
    value = finite(value_ug_m3, 0, 10000)
    if not bounds or value is None:
        return {"status": "unavailable"}
    index = next((i for i, limit in enumerate(bounds) if value <= limit), 5)
    return {"status": "reference", "category": EU_BANDS[index], "category_number": index + 1,
            "measurement_period": "hourly", "region": "eea_guidance_reference_only"}


def _recent(samples: Sequence[dict], key: str, now: float, minutes: int) -> list[dict]:
    result = []
    for row in samples:
        if not isinstance(row, dict):
            continue
        t = finite(row.get("t"), 0, 1e12)
        v = finite(row.get(key), 0, 1e7)
        if t is not None and v is not None and now - minutes * 60 <= t <= now:
            result.append({"t": t, key: v, "occupied": row.get("occupied"),
                           "window_open": row.get("window_open")})
    return sorted(result, key=lambda r: r["t"])


def ventilation_learning(samples: Sequence[dict], now: float,
                         *, target_co2: float = 1000) -> dict:
    """Measured CO2 decline only; never an epidemiological or health guarantee."""
    data = _recent(samples, "co2", now, 35)
    if len(data) < 4 or data[-1]["t"] - data[0]["t"] < 12 * 60:
        return {"status": "insufficient_data"}
    if any(row.get("window_open") is not True for row in data):
        return {"status": "window_not_continuously_open"}
    if any(b["t"] - a["t"] > MAX_GAP_S for a, b in zip(data, data[1:])):
        return {"status": "missing_interval"}
    target = finite(target_co2, 400, 3000)
    if target is None:
        return {"status": "invalid_target"}
    initial, current = data[0]["co2"], data[-1]["co2"]
    seconds = data[-1]["t"] - data[0]["t"]
    delta = current - initial
    if delta >= -50:
        return {"status": "not_demonstrably_decreasing", "co2_change_ppm": round(delta)}
    rate = -delta / seconds * 60
    if current <= target:
        return {"status": "target_reached", "co2_change_ppm": round(delta),
                "elapsed_minutes": round(seconds / 60, 1)}
    if rate < 1 or rate > 100:
        return {"status": "unstable_decline"}
    # Two halves must show same trend, rejecting strong occupancy/source effects.
    mid = data[len(data)//2]
    early = (initial - mid["co2"]) / max(1, mid["t"] - data[0]["t"])
    late = (mid["co2"] - current) / max(1, data[-1]["t"] - mid["t"])
    if early <= 0 or late <= 0 or not 0.4 <= late / early <= 2.5:
        return {"status": "inconsistent_trend"}
    minutes = (current - target) / rate
    if minutes > 45:
        return {"status": "declining_but_target_distant",
                "co2_change_ppm": round(delta),
                "estimated_time_exceeds_minutes": 45}
    return {"status": "indicative", "estimated_minutes_to_target": round(minutes),
            "observed_ppm_change": round(delta), "target_ppm": target,
            "method": "linear_recent_decay_extrapolation_not_ach"}


def particle_filtration(volume_m3: Any, cadr_m3h: Any, purifier_on: bool | None,
                        samples: Sequence[dict], now: float) -> dict:
    volume, cadr = finite(volume_m3, 1, 30000), finite(cadr_m3h, 0.1, 100000)
    if volume is None or cadr is None:
        return {"status": "configuration_required", "required": ["volume_m3", "particle_cadr_m3h"]}
    theoretical = cadr / volume
    if purifier_on is None:
        status = "operation_state_unknown"
    else:
        status = "running" if purifier_on else "off"
    window = _recent(samples, "pm25", now, 30)
    change = (round(window[-1]["pm25"] - window[0]["pm25"], 1)
              if len(window) >= 3 and window[-1]["t"] - window[0]["t"] >= 600 else None)
    return {"status": status, "nominal_particle_clean_air_changes_h": round(theoretical, 2),
            "pm25_observed_change_ug_m3": change,
            "particle_only": True, "note": "CADR is rated at particular test conditions and fan speed; observed changes are not causally attributable."}


def moisture_event(samples: Sequence[dict], now: float, *, extractor_on: bool | None) -> dict:
    data = _recent(samples, "humidity", now, 35)
    if len(data) < 3 or data[-1]["t"] - data[0]["t"] < 10 * 60:
        return {"status": "insufficient_data"}
    net = data[-1]["humidity"] - data[0]["humidity"]
    if net < 8:
        return {"status": "no_large_rise", "rh_change_percent_points": round(net, 1)}
    return {"status": "relative_humidity_rise",
            "rh_change_percent_points": round(net, 1),
            "extractor_on": extractor_on,
            "source": "undetermined_not_cooking_or_showering_proven",
            "note": "Temperature changes alone can raise relative humidity; compare moisture ratio before inferring a source."}


def pollen_reading(value: Any, *, high_from: float = 3.0,
                   max_scale: float = 5.0, prevent_ventilation: bool = False) -> dict:
    x, threshold, maximum = finite(value, 0, 10000), finite(high_from, 0, 10000), finite(max_scale, 1, 10000)
    if x is None:
        return {"status": "unavailable"}
    if maximum is None or threshold is None or x > maximum or threshold > maximum:
        return {"status": "invalid_provider_scale"}
    return {"status": "provider_defined", "value": x,
            "high": x >= threshold, "high_from": threshold, "max_scale": maximum,
            "avoid_ventilation": bool(prevent_ventilation and x >= threshold),
            "note": "Pollen scales and coverage vary by provider and region; do not compare across providers."}


def radon_long_term(days: Sequence[dict], now: float,
                    *, recommended_bq_m3: float = 100.0) -> dict:
    """Requires near-year-long *qualified* daily means, never eight-day proxy."""
    threshold = finite(recommended_bq_m3, 25, 1000)
    if threshold is None:
        return {"status": "invalid_reference"}
    first = int((now - 365 * DAY_S) // DAY_S)
    unique = {}
    for record in days:
        if not isinstance(record, dict):
            continue
        date = record.get("day")
        value = finite(record.get("mean_bq_m3"), 0, 10000)
        coverage = finite(record.get("coverage_percent"), 0, 100)
        if type(date) is int and date >= first and value is not None and coverage is not None and coverage >= 80:
            unique[date] = value
    if len(unique) < 340:
        return {"status": "insufficient_yearly_coverage", "qualified_days": len(unique),
                "reference_bq_m3": threshold}
    average = sum(unique.values()) / len(unique)
    return {"status": "annual_screening", "qualified_days": len(unique),
            "mean_bq_m3": round(average, 1),
            "above_reference": average > threshold, "reference_bq_m3": threshold,
            "note": "Not a calibrated regulatory radon assessment; reference levels vary by country."}


def laeq_db_a(samples: Sequence[dict], now: float, window_seconds: float) -> dict:
    """Physically valid dBA average: logarithmic sound energy, not dB arithmetic."""
    since = now - window_seconds
    total_energy, covered = 0.0, 0.0
    data = [s for s in _recent(samples, "noise_dba", now, int(window_seconds / 60) + 1) if 0 <= s["noise_dba"] <= 150]
    for a, b in zip(data, data[1:]):
        elapsed = b["t"] - a["t"]
        if not 0 < elapsed <= MAX_GAP_S:
            continue
        left, right = max(since, a["t"]), min(now, b["t"])
        if left >= right:
            continue
        energy = (10 ** (a["noise_dba"] / 10) + 10 ** (b["noise_dba"] / 10)) / 2
        total_energy += energy * (right - left)
        covered += right - left
    coverage = 100 * covered / window_seconds
    if covered < window_seconds * 0.8:
        return {"status": "insufficient_coverage", "coverage_percent": round(coverage, 1)}
    return {"status": "indicative_laeq", "db_a": round(10 * math.log10(total_energy / covered), 1),
            "coverage_percent": round(coverage, 1),
            "note": "Requires a calibrated time-equivalent A-weighted sound level sensor; samples of peak sound levels cannot estimate LAeq."}


def hcho_30min(samples: Sequence[dict], now: float, *, verified: bool) -> dict:
    if not verified:
        return {"status": "sensor_verification_required"}
    res = weighted_window(samples, "hcho", now, 1800, max_gap_s=600, min_coverage=0.85)
    if res.get("status") != "ready":
        return res
    return {**res, "above_who_100ug_m3": res["mean"] > 100,
            "who_reference_ug_m3": 100, "duration_minutes": 30}


def daylight_exposure(samples: Sequence[dict], now: float,
                      *, threshold_lux: float = 300.0) -> dict:
    threshold = finite(threshold_lux, 1, 100000)
    if threshold is None:
        return {"status": "invalid_threshold"}
    # Reporting only. A lux meter cannot determine CIE melanopic EDI.
    count = 0.0
    covered = 0.0
    data = _recent(samples, "lux", now, 24 * 60)
    for a, b in zip(data, data[1:]):
        gap = b["t"] - a["t"]
        if 0 < gap <= MAX_GAP_S:
            covered += gap
            if (a["lux"] + b["lux"]) / 2 >= threshold:
                count += gap
    return {"status": "descriptive" if covered >= 0.8 * DAY_S else "insufficient_coverage",
            "observed_hours_above_threshold": round(count/3600, 2),
            "threshold_lux": threshold,
            "coverage_percent": round(100*covered/DAY_S, 1),
            "note": "Photopic lux is not melanopic equivalent daylight illuminance."}


def overheating_degree_hours(samples: Sequence[dict], now: float,
                             *, reference_c: float = 26.0) -> dict:
    """Integral of observed degrees above reference; NOT TM52/TM59 compliance."""
    extra_degree_hours, covered = 0.0, 0.0
    data = _recent(samples, "temperature_c", now, 24*60)
    for a, b in zip(data, data[1:]):
        seconds = b["t"] - a["t"]
        if not 0 < seconds <= MAX_GAP_S:
            continue
        v = (max(0.0, a["temperature_c"] - reference_c) +
             max(0.0, b["temperature_c"] - reference_c))/2
        extra_degree_hours += v * seconds / 3600
        covered += seconds
    return {"status": "ready" if covered >= 0.8 * DAY_S else "insufficient_coverage",
            "degree_hours_over_reference": round(extra_degree_hours, 2),
            "reference_c": reference_c, "coverage_percent": round(100*covered/DAY_S, 1),
            "method": "observed_degree_hours_not_tm52_tm59"}


def pmv_iso7730(air_c: Any, mean_radiant_c: Any, rh: Any,
                air_speed_m_s: Any, met: Any, clo: Any) -> dict:
    """Optional validated library, never silently invent MRT, activity or clothing."""
    inputs = [finite(air_c, 10, 30), finite(mean_radiant_c, 10, 40),
              finite(rh, 0.1, 100), finite(air_speed_m_s, 0.01, 0.99),
              finite(met, 0.81, 3.99), finite(clo, 0.01, 1.99)]
    if any(x is None for x in inputs):
        return {"status": "missing_or_outside_iso7730_inputs"}
    from .pmv_core import pmv_ppd_iso
    try:
        response = pmv_ppd_iso(tdb=inputs[0], tr=inputs[1], rh=inputs[2],
                               vr=inputs[3], met=inputs[4], clo=inputs[5],
                               model="7730-2025", limit_inputs=True)
        pmv, ppd = float(response.pmv), float(response.ppd)
    except (TypeError, ValueError, OverflowError):
        return {"status": "outside_model_applicability"}
    if not math.isfinite(pmv) or not math.isfinite(ppd):
        return {"status": "outside_model_applicability"}
    return {"status": "estimate", "pmv": round(pmv, 2), "ppd_percent": round(ppd, 1),
            "standard": "ISO7730:2025", "inputs_user_supplied": ["met", "clo", "air_speed"],
            "note": "PMV/PPD estimates are model-based; not individual comfort predictions."}

def nighttime_laeq(samples: Sequence[dict], now: float, tz_name: str) -> dict:
    """Energy-averaged dB(A) over the last completed local 22:00–07:00 window."""
    from datetime import timedelta
    try:
        zone = ZoneInfo(tz_name)
    except (TypeError, ValueError, ZoneInfoNotFoundError):
        zone = timezone.utc
    local = datetime.fromtimestamp(now, zone)
    end_day = local.date() if local.hour >= 7 else local.date()-timedelta(days=1)
    end = datetime.combine(end_day, datetime.min.time(), zone).replace(hour=7)
    start = end-timedelta(hours=9)
    begin_s, end_s = start.timestamp(), end.timestamp()
    data = [r for r in _recent(samples,"noise_dba",end_s,12*60) if 0 <= r["noise_dba"] <= 150]
    energy = covered = 0.0
    for a,b in zip(data,data[1:]):
        if not 0 < b["t"]-a["t"] <= MAX_GAP_S:
            continue
        left,right=max(a["t"],begin_s),min(b["t"],end_s)
        if right <= left:
            continue
        energy += (10**(a["noise_dba"]/10)+10**(b["noise_dba"]/10))/2*(right-left)
        covered += right-left
    expected = end_s - begin_s
    if covered < 0.8*expected or energy <= 0:
        return {"status":"insufficient_coverage", "coverage_percent":round(100*covered/expected,1)}
    level = 10*math.log10(energy/covered)
    return {"status":"indicative_night_laeq", "db_a":round(level,1),
            "above_who_bedroom_30_dba":level>30, "reference_db_a":30,
            "coverage_percent":round(100*covered/expected,1),
            "local_window":"22:00_to_07:00","method":"measured_laeq_not_peak_dba"}
