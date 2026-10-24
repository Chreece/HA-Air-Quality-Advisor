"""Measured, capacity-aware PID allocation for ON/OFF equipment with a fan.

This is a pure deterministic transformation. Fan airflow or RPM is NOT assumed
to equal delivered heating, cooling or dehumidification capacity. A user must
supply measured relative output for each available stage / permitted
percentage response. The fastest physical fan is defined as the 100% OUTPUT
reference by normalization; that does not claim a manufacturer capacity.

Never infer capacities from device names, native fan modes or live PID gains.
No Home Assistant services, network requests, hardware probes or timers.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import math
from typing import Any, Mapping

from .pid_output_allocator import ordered_fan_stages

STAGE_FIELDS = tuple(f"pid_capacity_stage_{i}" for i in range(1, 5))
PERCENT_POINT_FIELDS = tuple(
    (f"pid_capacity_speed_{i}", f"pid_capacity_output_{i}") for i in range(1, 4)
)
CAPACITY_FIELDS = {
    **{key: (0., 99., 1., "%") for key in STAGE_FIELDS},
    **{key: (0., 99., 1., "%") for pair in PERCENT_POINT_FIELDS for key in pair},
}
CAPACITY_METHODS = ("legacy", "measured")
CALIBRATION_DIRECTIONS = ("heat", "cool", "dry", "fan_only")


@dataclass(frozen=True, slots=True)
class CapacityAllocation:
    speed: str | int
    demand_percent: float
    stage_capacity_percent: float
    compensated_duty_percent: float
    expected_delivered_percent: float
    unmet_demand_percent: float
    quiet_limited: bool

    def snapshot(self) -> dict:
        return asdict(self)


def _number(value: Any) -> float | None:
    return float(value) if type(value) in (int, float) and math.isfinite(value) else None


def build_model(
    *,
    percentage: bool,
    advertised_modes: tuple[str, ...],
    measured: Mapping[str, Any],
    min_speed: float = 1,
) -> dict:
    """Validate complete evidence; zero input means not measured, not 0% capacity.

    Discrete mode: provide every stage except the fastest (defined as 100%
    reference). Supports any 2-5 genuine ordered native stages.
    Percentage mode: at least two measured capacity anchors at attainable
    native 25/50/75 settings plus the 100% output reference. Predictions at
    lower unmeasured speeds are prohibited (no extrapolation).
    """
    if percentage:
        supported = sorted({
            int(mode) for mode in advertised_modes
            if isinstance(mode, str) and mode.isdecimal() and 1 <= int(mode) <= 100
        })
        if not supported or 100 not in supported:
            raise ValueError("native_full_fan_speed_not_available")
        observed = []
        for speed_key, capacity_key in PERCENT_POINT_FIELDS:
            speed, value = _number(measured.get(speed_key, 0)), _number(measured.get(capacity_key, 0))
            if speed is None or value is None or not 0 <= speed <= 99 or not 0 <= value <= 99:
                raise ValueError("invalid_measured_percentage_capacity")
            if speed == value == 0:
                continue  # unused sample slot, not an invented response
            if speed == 0 or value == 0:
                raise ValueError("incomplete_measured_percentage_pair")
            if int(speed) != speed or int(speed) not in supported or speed < min_speed:
                raise ValueError("calibrated_percentage_speed_not_supported")
            observed.append((int(speed), value))
        if len(observed) < 2:
            raise ValueError("two_measured_percentage_capacity_points_required")
        observed.sort(key=lambda item: item[0])
        points = (*observed, (100, 100.0))
        name = "percentage"
        stages: tuple[str, ...] = ()
    else:
        stages = ordered_fan_stages(advertised_modes)
        if len(stages) < 2 or len(stages) > 5:
            raise ValueError("two_to_five_ordered_native_fan_stages_required")
        measured_capacities = []
        for key in STAGE_FIELDS[:len(stages)-1]:
            value = _number(measured.get(key))
            if value is None or not 0 < value < 100:
                raise ValueError("complete_measured_stage_capacities_required")
            measured_capacities.append(value)
        points = tuple((*enumerate(measured_capacities, 1), (len(stages), 100.0)))
        name = "discrete"

    values = [capacity for _, capacity in points]
    if any(right <= left for left, right in zip(values, values[1:])):
        raise ValueError("measured_fan_capacities_must_increase_monotonically")
    return {
        "type": name, "modes": list(advertised_modes),
        "stages": list(stages),
        "points": [[x, float(y)] for x, y in points],
    }


def model_is_valid(
    stored: Mapping[str, Any] | None, *,
    mode: str, physical_entity: str, fan_entity: str,
    percentage: bool, advertised_modes: tuple[str, ...],
) -> bool:
    """Refuse a model from a different operating direction or source."""
    if not isinstance(stored, dict):
        return False
    if (stored.get("direction") != mode or
        stored.get("physical_entity") != physical_entity or
        stored.get("fan_entity") != fan_entity or
        stored.get("type") != ("percentage" if percentage else "discrete") or
        stored.get("modes") != list(advertised_modes)):
        return False
    try:
        points = stored["points"]
        return (isinstance(points, list) and len(points) >= 2 and
                all(isinstance(p, list) and len(p) == 2 and
                    _number(p[0]) is not None and _number(p[1]) is not None
                    for p in points) and
                points[-1][1] == 100 and
                all(0 < p[1] <= 100 for p in points) and
                all(b[0] > a[0] and b[1] > a[1]
                    for a, b in zip(points, points[1:])))
    except (KeyError, IndexError, TypeError, ValueError):
        return False


def _percent_capacity(speed: int, points: list[list[float]]) -> float | None:
    if speed < points[0][0] or speed > points[-1][0]:
        return None
    for (left_speed, left_cap), (right_speed, right_cap) in zip(points, points[1:]):
        if left_speed <= speed <= right_speed:
            fraction = (speed - left_speed) / (right_speed - left_speed)
            return float(left_cap + fraction * (right_cap - left_cap))
    return None


def allocate(
    demand: float, model: Mapping[str, Any], *,
    quiet: bool, quiet_mode: str | None,
    quiet_percentage: float,
    fan_min_percentage: float, fan_max_percentage: float,
) -> CapacityAllocation | None:
    """Allocate PID output from measured capacity, then account for duty.

    Choose the lowest *allowed* fan speed capable of meeting the output where
    possible. If quiet / device maximum limits capacity, run at the capped
    speed with compensated duty at most 100%, and report unmet demand.
    The hardware minimum runtime and minimum off period are applied later.
    """
    demand = _number(demand)
    if demand is None or not 0 < demand <= 100:
        return None
    if model.get("type") == "discrete":
        stages = model["stages"]
        points = model["points"]
        if not stages or len(points) != len(stages):
            return None
        max_index = len(stages)-1
        if quiet:
            cap = quiet_mode or ("low" if "low" in stages else None)
            if cap not in stages:
                return None
            max_index = min(max_index, stages.index(cap))
        choices = [(stages[index], points[index][1])
                   for index in range(max_index+1)]
    elif model.get("type") == "percentage":
        native_modes = model.get("modes", [])
        allowed = sorted({
            int(p) for p in native_modes
            if isinstance(p, str) and p.isdecimal()
            and fan_min_percentage <= int(p) <= fan_max_percentage
            and (not quiet or int(p) <= max(fan_min_percentage, quiet_percentage))
        })
        choices = [(speed, capacity)
                   for speed in allowed
                   if (capacity := _percent_capacity(speed, model["points"])) is not None]
    else:
        return None
    if not choices:
        return None
    speed, capacity = next(
        ((speed, capacity) for speed, capacity in choices if capacity >= demand),
        choices[-1],
    )
    duty = min(100.0, 100.0 * demand / capacity)
    delivered = min(demand, capacity)
    return CapacityAllocation(
        speed, demand, float(capacity), duty, delivered,
        max(0., demand - capacity),
        bool(quiet and (capacity < demand or speed != choices[-1][0])),
    )
