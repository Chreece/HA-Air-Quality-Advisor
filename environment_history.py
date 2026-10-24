"""Small bounded history for evidence-qualified environmental indicators.

Persisted through Home Assistant Store by the manager; no cloud, no Recorder
database queries, no raw occupancy log. Snapshot sampling is capped at 5 min.
"""
from __future__ import annotations

import math
import time
from typing import Any

from .building_physics import WEEK_S, DAY_S


FIELDS = frozenset((
    "temperature_c", "humidity", "pm25", "pm10", "co2", "surface_rh",
    "outdoor_temperature_c", "window_open", "occupied",
    "radon", "noise_dba", "hcho", "lux", "melanopic_edi",
    "outdoor_pm25", "outdoor_pm10",
    "radon_source",
))
MAX_AGE = 8 * DAY_S
MAX_POINTS_PER_AREA = 2600


class EnvironmentHistory:
    def __init__(self, areas: dict[str, list[dict]] | None = None,
                 daily: dict[str, list[dict]] | None = None):
        self.areas: dict[str, list[dict]] = areas if areas is not None else {}
        self.daily: dict[str, list[dict]] = daily if daily is not None else {}

    @classmethod
    def restore(cls, data: Any, *, now: float | None = None) -> "EnvironmentHistory":
        current = time.time() if now is None else now
        if not isinstance(data, dict) or data.get("version") != 1:
            return cls()
        areas: dict[str, list[dict]] = {}
        source = data.get("areas")
        if not isinstance(source, dict):
            return cls()
        for area, points in list(source.items())[:150]:
            if not isinstance(area, str) or not isinstance(points, list):
                continue
            valid = []
            for point in points[-MAX_POINTS_PER_AREA:]:
                if not isinstance(point, dict):
                    continue
                try:
                    stamp = float(point["t"])
                except (TypeError, ValueError, KeyError, OverflowError):
                    continue
                if not math.isfinite(stamp) or not current - MAX_AGE <= stamp <= current + 60:
                    continue
                clean = {"t": stamp}
                for key in FIELDS:
                    val = point.get(key)
                    if key == "radon_source":
                        if isinstance(val, str) and val.startswith("sensor.") and len(val) <= 255:
                            clean[key] = val
                    elif key in ("occupied", "window_open"):
                        if type(val) is bool:
                            clean[key] = val
                    elif isinstance(val, (int, float)) and math.isfinite(val):
                        clean[key] = float(val)
                valid.append(clean)
            valid.sort(key=lambda p: p["t"])
            if valid:
                areas[area] = valid
        daily = {}
        raw_daily = data.get("daily")
        if isinstance(raw_daily, dict):
            for key, rows in list(raw_daily.items())[:150]:
                if not isinstance(key, str) or not isinstance(rows, list) or len(key) > 512:
                    continue
                valid_rows = []
                for item in rows[-370:]:
                    if not isinstance(item, dict):
                        continue
                    day, mean, coverage = item.get("day"), item.get("mean_bq_m3"), item.get("coverage_percent")
                    if (type(day) is int and current / DAY_S - 370 <= day <= current / DAY_S
                            and isinstance(mean, (float, int)) and math.isfinite(mean) and 0 <= mean <= 10000
                            and isinstance(coverage, (float, int)) and math.isfinite(coverage) and 80 <= coverage <= 100):
                        valid_rows.append({"day": day, "mean_bq_m3": float(mean),
                                           "coverage_percent": float(coverage)})
                if valid_rows:
                    daily[key] = sorted(valid_rows, key=lambda r: r["day"])
        return cls(areas, daily)

    def snapshot(self) -> dict:
        return {"version": 1, "areas": self.areas, "daily": self.daily}

    def add(self, area: str, observation: dict[str, Any], *, now: float | None = None) -> bool:
        current = time.time() if now is None else now
        if not isinstance(area, str) or not area or not math.isfinite(current):
            return False
        points = self.areas.setdefault(area, [])
        min_stamp = current - MAX_AGE
        if points and points[-1]["t"] > current:
            return False
        data = {"t": round(current, 3)}
        for key in FIELDS:
            val = observation.get(key)
            if key == "radon_source":
                if isinstance(val, str) and val.startswith("sensor.") and len(val) <= 255:
                    data[key] = val
            elif key in ("occupied", "window_open"):
                if type(val) is bool:
                    data[key] = val
            elif isinstance(val, (int, float)) and math.isfinite(val):
                data[key] = float(val)
        if points and current - points[-1]["t"] < 300:
            # Record window/occupancy transitions immediately to segment ACH.
            if all(points[-1].get(key) == data.get(key) for key in ("occupied", "window_open")):
                return False
        points.append(data)
        points[:] = [s for s in points if s["t"] >= min_stamp][-MAX_POINTS_PER_AREA:]
        return True

    def samples(self, area: str) -> list[dict]:
        return self.areas.get(area, [])

    def record_qualified_radon_days(self, area: str, source: str, *, now: float) -> bool:
        """Accumulate up to 370 confirmed UTC 24h radon means, source-specific.

        No guesswork for unmeasured historical days and no merging sensors
        that could have different calibration/placement.
        """
        from .building_physics import weighted_window
        if not area or not source or not math.isfinite(now):
            return False
        key = area + "|" + source
        history = self.daily.setdefault(key, [])
        existing = {item["day"] for item in history}
        last_complete_day = int(now // DAY_S) - 1
        newly = False
        # Only the last seven days can have enough raw source observations.
        for day in range(max(0,last_complete_day - 7), last_complete_day + 1):
            if day in existing:
                continue
            end = (day + 1) * DAY_S
            scoped = [row for row in self.samples(area)
                      if row.get("radon_source") == source]
            window = weighted_window(scoped, "radon", end, DAY_S, min_coverage=0.8)
            if window.get("status") == "ready":
                history.append({"day": day, "mean_bq_m3": window["mean"],
                                "coverage_percent": window["coverage_percent"]})
                newly = True
        history.sort(key=lambda x: x["day"])
        history[:] = [d for d in history if d["day"] >= now // DAY_S - 370][-370:]
        return newly

    def radon_days(self, area: str, source: str) -> list[dict]:
        return self.daily.get(area + "|" + source, [])
