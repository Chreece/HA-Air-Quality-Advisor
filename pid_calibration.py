"""Deterministic, non-actuating PID calibration from identified FOPDT models.

The operator must supply an observed process response: process gain per 100%
actuator change, first-order time constant, and apparent dead time. No relay
test, live probing, oscillation, hardware service, or guessed response is made.

Engineering sources:
- Skogestad (2003) SIMC/Lambda PI tuning (first-order plus dead time)
- Cohen & Coon (1953) process-reaction-curve PID tuning
The integration uses PARALLEL kp,ki,kd. Time is in MINUTES because its
discrete integrator and filtered derivative use dt / 60.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

METHODS = ("manual", "imc_lambda", "cohen_coon")

# The inputs are measured independently for each physical controller and
# each selected feedback metric. Gain = ABS(ΔPV / Δactuator fraction);
# for an ON/OFF source the full actuator step is 0->1, not 0->100.
MODEL_FIELDS = {
    "pid_process_gain": (0.001, 10000.0, 0.001, None),
    "pid_time_constant_minutes": (1.0, 1440.0, 0.5, "min"),
    "pid_dead_time_minutes": (0.1, 360.0, 0.1, "min"),
    "pid_lambda_minutes": (1.0, 1440.0, 0.5, "min"),
}


@dataclass(frozen=True)
class Calibration:
    kp: float
    ki: float
    kd: float
    method: str
    process_gain: float
    time_constant_minutes: float
    dead_time_minutes: float
    lambda_minutes: float | None


def tune(method: str, data: Mapping, *, sample_seconds: float,
         constraints: Mapping[str, tuple] | None = None) -> Calibration:
    """Return physically bounded parallel-form tuning without any IO.

    The reaction-curve model is meaningful only for a self-regulating plant
    with a measured step response (not guessed from an entity's name).
    Reject processes faster than our selected sample interval and any
    resulting gains that exceed the Manager's existing UI safety bounds.
    """
    if method not in METHODS or method == "manual":
        raise ValueError("select_imc_lambda_or_cohen_coon")
    values = {}
    for key in ("pid_process_gain", "pid_time_constant_minutes", "pid_dead_time_minutes"):
        value = data.get(key)
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("calibration_model_missing_or_invalid")
        low, high, _, _ = MODEL_FIELDS[key]
        if not low <= value <= high:
            raise ValueError("calibration_model_outside_bounds")
        values[key] = float(value)
    gain = values["pid_process_gain"]
    tau = values["pid_time_constant_minutes"]
    dead = values["pid_dead_time_minutes"]
    if type(sample_seconds) not in (float, int) or not math.isfinite(sample_seconds):
        raise ValueError("invalid_pid_sample_time")
    if tau * 60 < sample_seconds:
        raise ValueError("process_faster_than_pid_sampling")
    lam = data.get("pid_lambda_minutes")
    if method == "imc_lambda":
        if type(lam) not in (float, int) or not math.isfinite(lam):
            raise ValueError("imc_lambda_required")
        if not MODEL_FIELDS["pid_lambda_minutes"][0] <= lam <= MODEL_FIELDS["pid_lambda_minutes"][1]:
            raise ValueError("imc_lambda_outside_bounds")
        # Conservative default: avoid requesting a closed-loop response
        # faster than both delay and the existing sample interval.
        if lam < max(dead, sample_seconds / 60):
            raise ValueError("imc_lambda_too_aggressive")
        # SIMC/Skogestad PI: Kc=tau/(k*(lambda+dead)),
        # Ti=min(tau, 4*(lambda+dead)). Our output is percent 0..100.
        kp = 100.0 * tau / (gain * (float(lam) + dead))
        ti = min(tau, 4.0 * (float(lam) + dead))
        td = 0.0
    else:
        # Original Cohen-Coon PID reaction-curve rule (K normalized to 100%
        # output), substantially less forgiving of uncertain dead time.
        ratio = dead / tau
        kp = 100.0 * tau / (gain * dead) * (4.0 / 3.0 + ratio / 4.0)
        ti = dead * (32.0 + 6.0 * ratio) / (13.0 + 8.0 * ratio)
        td = 4.0 * dead / (11.0 + 2.0 * ratio)

    values = {"kp": kp, "ki": kp / ti, "kd": kp * td}
    for key, value in values.items():
        if not math.isfinite(value):
            raise ValueError("invalid_calculated_pid_gain")
        if constraints is not None:
            low, high = constraints[key][:2]
            if not low <= value <= high:
                raise ValueError(f"calculated_{key}_outside_safe_bounds")
    return Calibration(kp, values["ki"], values["kd"], method, gain, tau, dead,
                       float(lam) if method == "imc_lambda" else None)
