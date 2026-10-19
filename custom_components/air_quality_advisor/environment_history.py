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
))
MAX_AGE = 8 * DAY_S
MAX_POINTS_PER_AREA = 2600


class EnvironmentHistory:
    def __init__(self, areas: dict[str, list[dict]] | None = None):
        self.areas: dict[str, list[dict]] = areas if areas is not None else {}

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
                    if key in ("occupied", "window_open"):
                        if type(val) is bool:
                            clean[key] = val
                    elif isinstance(val, (int, float)) and math.isfinite(val):
                        clean[key] = float(val)
                valid.append(clean)
            valid.sort(key=lambda p: p["t"])
            if valid:
                areas[area] = valid
        return cls(areas)

    def snapshot(self) -> dict:
        return {"version": 1, "areas": self.areas}

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
            if key in ("occupied", "window_open"):
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
