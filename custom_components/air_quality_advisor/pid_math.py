"""Deterministic, bounded supervisory PID control for Home Assistant climate devices.

All temperatures are Celsius here. Kp = %/°C, Ki = %/(°C minute),
Kd = %·minute/°C. Derivative is taken on the measurement to avoid setpoint
kick; anti-windup stops integration in the saturating error direction.

This PI/PID does not directly cycle compressors: it computes a *bounded
setpoint trim* for climate.set_temperature. Existing thermostats retain their
own compressor minimum-off protection and feedback loops.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


DEFAULT_PID = {
    "enabled": False, "mode": "heat", "target_c": 21.0,
    "kp": 22.0, "ki": 0.25, "kd": 0.0,
    "offset_c": 1.5, "min_setpoint_c": 16.0, "max_setpoint_c": 27.0,
    "sample_seconds": 300, "max_change_c": 0.5, "min_change_c": 0.15,
    "pause_on_window_open": True,
}


@dataclass(frozen=True)
class Memory:
    integral: float = 0.0
    last_c: float | None = None
    last_s: float | None = None
    derivative_c_per_min: float = 0.0


@dataclass(frozen=True)
class Result:
    status: str
    memory: Memory
    demand_percent: float | None = None
    proportional: float | None = None
    integral: float | None = None
    derivative: float | None = None


def finite(value: Any, minimum: float, maximum: float) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and minimum <= number <= maximum else None


def validate_settings(settings: dict) -> tuple[bool, str]:
    if not isinstance(settings, dict):
        return False, "invalid_settings"
    if settings.get("mode") not in ("heat", "cool"):
        return False, "unsupported_mode"
    bounds = {
        "target_c": (5, 36), "kp": (0.01, 100),
        "ki": (0, 10), "kd": (0, 50),
        "offset_c": (0.25, 5.0), "min_setpoint_c": (5, 35),
        "max_setpoint_c": (6, 40), "sample_seconds": (120, 3600),
        "max_change_c": (0.1, 2), "min_change_c": (0.05, 1),
    }
    for key, (low, high) in bounds.items():
        if finite(settings.get(key), low, high) is None:
            return False, f"invalid_{key}"
    lo, hi, goal = (float(settings[key]) for key in ("min_setpoint_c", "max_setpoint_c", "target_c"))
    if not lo < hi or not lo <= goal <= hi:
        return False, "target_outside_setpoint_limits"
    if float(settings["min_change_c"]) > float(settings["max_change_c"]):
        return False, "minimum_change_exceeds_rate_limit"
    return True, "ready"


def step(temp_c: float, target_c: float, now_s: float, mode: str,
         kp: float, ki: float, kd: float, sample_seconds: float,
         previous: Memory | None = None) -> Result:
    """Advance PID from a fresh measured temperature (never from a forecast)."""
    state = previous or Memory()
    measured = finite(temp_c, -10, 50)
    target = finite(target_c, 5, 36)
    clock = finite(now_s, 0, 1e13)
    gains = [finite(kp, 0, 100), finite(ki, 0, 10),
             finite(kd, 0, 50), finite(sample_seconds, 120, 3600)]
    if measured is None or target is None or clock is None or any(x is None for x in gains):
        return Result("invalid_input", Memory())
    if mode not in ("heat", "cool"):
        return Result("unsupported_mode", Memory())
    if state.last_s is None or state.last_c is None:
        return Result("initializing", Memory(last_c=measured, last_s=clock))
    dt = clock - state.last_s
    if dt <= 0:
        return Result("nonmonotonic_time", state)
    if dt > max(3 * sample_seconds, 1800):
        return Result("gap_reset", Memory(last_c=measured, last_s=clock))
    if dt < sample_seconds * 0.75:
        return Result("waiting_sample", state)
    direction = 1 if mode == "heat" else -1
    error = direction * (target - measured)
    delta_minutes = dt / 60
    # Filter measured derivative (large sensor quantization steps are common).
    derivative = 0.25 * ((measured - state.last_c) / delta_minutes) + (
        0.75 * state.derivative_c_per_min
    )
    d_term = -direction * kd * derivative
    p_term = kp * error
    trial_integral = min(100.0, max(-100.0, state.integral + ki * error * delta_minutes))
    raw = p_term + trial_integral + d_term
    # Anti-windup: do not accumulate more integral when output is saturated
    # and the current error would drive farther into that saturation.
    if (raw >= 100 and error > 0) or (raw <= 0 and error < 0):
        integral = state.integral
    else:
        integral = trial_integral
    demand = min(100.0, max(0.0, p_term + integral + d_term))
    next_state = Memory(integral, measured, clock, derivative)
    return Result("ready", next_state, round(demand, 3),
                  round(p_term, 3), round(integral, 3), round(d_term, 3))


def setpoint_c(target_c: float, demand_percent: float, mode: str,
               offset_c: float, min_c: float, max_c: float) -> float | None:
    """Map PID effort into a bounded single-setpoint trim, never HVAC cycling."""
    target = finite(target_c, 5, 36)
    demand = finite(demand_percent, 0, 100)
    offset = finite(offset_c, 0.25, 5)
    lo, hi = finite(min_c, 5, 35), finite(max_c, 6, 40)
    if None in (target, demand, offset, lo, hi) or not lo < hi or mode not in ("heat", "cool"):
        return None
    direction = 1 if mode == "heat" else -1
    return min(hi, max(lo, target + direction * offset * demand / 100))


def target_to_unit(value_c: float, unit: str) -> float | None:
    t = finite(value_c, -30, 60)
    if t is None:
        return None
    if unit in ("°C", "C"):
        return t
    if unit in ("°F", "F"):
        return 32 + t * 9 / 5
    return None


def target_from_unit(value: float, unit: str) -> float | None:
    t = finite(value, -30, 150)
    if t is None:
        return None
    if unit in ("°C", "C"):
        return t
    if unit in ("°F", "F"):
        return (t - 32) * 5 / 9
    return None


def quantize_target(value: float, step_size: float, minimum: float,
                    maximum: float) -> float | None:
    val = finite(value, -30, 150)
    spacing = finite(step_size, 0.1, 10)
    lo = finite(minimum, -30, 140)
    hi = finite(maximum, -29, 150)
    if None in (val, spacing, lo, hi) or lo >= hi:
        return None
    # Anchor on the device minimum to honor half-degree and full-degree steps.
    steps = math.floor((min(hi, max(lo, val)) - lo) / spacing + 0.5)
    return round(min(hi, lo + steps * spacing), 5)


def bounded_command(target_c: float, current_c: float, *,
                    max_change_c: float, min_change_c: float,
                    unit: str, device_min: float, device_max: float,
                    device_step: float) -> tuple[str, float | None]:
    """Hard rate limits in °C per PID cycle then quantize to HA device units."""
    target = finite(target_c, 5, 40)
    current = finite(current_c, 5, 40)
    movement = finite(max_change_c, 0.1, 2)
    minimum = finite(min_change_c, 0.05, 1)
    if None in (target, current, movement, minimum) or minimum > movement:
        return "invalid_command", None
    shift = max(-movement, min(movement, target - current))
    if abs(shift) < minimum:
        return "no_meaningful_change", None
    output = target_to_unit(current + shift, unit)
    if output is None:
        return "unsupported_temperature_unit", None
    rounded = quantize_target(output, device_step, device_min, device_max)
    if rounded is None:
        return "invalid_device_limits", None
    measured_units = target_from_unit(rounded, unit)
    if measured_units is None:
        return "unsupported_temperature_unit", None
    if abs(measured_units - current) < minimum - 1e-6:
        return "no_meaningful_change", None
    if abs(measured_units - current) > movement + 1e-6:
        return "device_step_exceeds_rate_limit", None
    return "command", rounded
