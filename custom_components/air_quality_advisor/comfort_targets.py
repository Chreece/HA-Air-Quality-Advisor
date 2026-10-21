"""Optional ISO 7730 PMV zero-crossing comfort target, with input-quality gates.

Numerically invert the standardized PMV function for air temperature while
holding *measured* current mean radiant temperature, RH and air movement, plus
explicitly configured metabolic rate and clothing constant. This is an
informational local steady-state air-temperature solution, not a prediction of
future conditions or a guarantee of individual comfort.
"""
from __future__ import annotations
from collections.abc import Callable
import math
from typing import Any

from .pid_math import finite


def solve_pmv_air_temperature(
    radiant_c: Any, relative_humidity: Any, air_speed_m_s: Any,
    met: Any, clo: Any, *, evaluator: Callable | None = None,
    target_pmv: float = 0.0,
) -> dict:
    inputs=[
        finite(radiant_c,10,40),finite(relative_humidity,1,100),
        finite(air_speed_m_s,0.01,0.99),finite(met,0.81,3.99),
        finite(clo,0.01,1.99),
    ]
    desired=finite(target_pmv,-0.5,0.5)
    if any(x is None for x in inputs) or desired is None:
        return {"status":"insufficient_physical_inputs"}
    if evaluator is None:
        from .pmv_core import pmv_ppd_iso
        evaluator=pmv_ppd_iso

    def calculate(temperature:float) -> float | None:
        try:
            result=evaluator(
                tdb=temperature, tr=inputs[0], rh=inputs[1],
                vr=inputs[2], met=inputs[3], clo=inputs[4],
                model="7730-2025",limit_inputs=True,round_output=False,
            )
            pmv=float(result.pmv)
        except (AttributeError,TypeError,ValueError,OverflowError):
            return None
        return pmv if math.isfinite(pmv) else None

    # ISO 7730 excludes exact 30°C and PMV values outside [-2,2].
    # Scan for a finite sign-changing bracket rather than rejecting a valid
    # neutral target just because one extreme endpoint is outside its domain.
    bracket=None
    previous=None
    for i in range(29):
        t=16.0+i*0.5
        value=calculate(t)
        if value is None:
            continue
        if previous is not None and previous[1]<=desired<=value and previous[1]<value:
            bracket=(previous[0],t)
            break
        previous=(t,value)
    if bracket is None:
        return {"status":"target_not_bracketed"}
    low,high=bracket
    for _ in range(20):
        mid=(low+high)/2
        value=calculate(mid)
        if value is None:
            return {"status":"model_unavailable_within_band"}
        if value<desired:
            low=mid
        else:
            high=mid
    target=(low+high)/2
    # Clamp only output, never invent comfort estimates outside a valid model.
    return {"status":"estimate",
            "air_temperature_target_c":round(target,2),
            "target_pmv":desired,
            "method":"iso7730_fixed_radiant_and_airflow_bisection",
            "caveat":"Radiant temperature/airflow may change as equipment runs; verify actual comfort."}
