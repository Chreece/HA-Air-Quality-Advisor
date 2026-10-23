"""Dependency-free, scalar Fanger PMV/PPD calculation for ISO 7730:2025.

Fanger's heat-balance equations, with the clothing-surface iteration and
applicability checks verified against pythermalcomfort 4.6.2 (MIT, copyright
2019 Federico Tartarini). Its permission notice is bundled at
docs/licenses/pythermalcomfort-MIT.txt. No numpy, scipy, numba or LLVM.

Only finite, scalar SI units are accepted here. Relative air velocity (vr)
must represent air speed relative to the person, NOT automatically the
reading of an ambient anemometer. The model describes population comfort,
not guaranteed individual comfort or ISO-compliant building certification.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, isfinite, nan, sqrt
from typing import Any


MET_TO_W_M2 = 58.15


@dataclass(frozen=True)
class PmvPpd:
    pmv: float
    ppd: float


def _value(raw: Any) -> float | None:
    if isinstance(raw, bool):
        return None
    try:
        result = float(raw)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if isfinite(result) else None


def _unavailable() -> PmvPpd:
    return PmvPpd(nan, nan)


def pmv_ppd_iso(
    tdb: Any, tr: Any, vr: Any, rh: Any, met: Any, clo: Any,
    wme: Any = 0.0, model: str = "7730-2025", *,
    limit_inputs: bool = True, round_output: bool = True,
) -> PmvPpd:
    """Calculate ISO 7730 PMV/PPD for ONE set of SI-unit input values.

    Uses the original Fanger thermal balance and converges the clothing
    surface temperature, rather than a fitted approximation.

    Return NaN for invalid or non-convergent calculations, matching
    pythermalcomfort's invalid-value convention; callers MUST reject it.
    2005/2025 currently share the same PMV equations and applicability.
    """
    if model not in ("7730-2005", "7730-2025"):
        raise ValueError("Unsupported ISO 7730 edition")
    values = [_value(x) for x in (tdb, tr, vr, rh, met, clo, wme)]
    if any(x is None for x in values):
        return _unavailable()
    air, radiant, velocity, humidity, activity, clothing, work = values
    if velocity < 0 or not 0 <= humidity <= 100 or activity <= 0 or clothing < 0:
        return _unavailable()
    if not 0 <= work <= activity:
        return _unavailable()
    if limit_inputs and not (
        10 < air < 30 and 10 < radiant < 40 and 0 < velocity < 1
        and 0.8 < activity < 4 and 0 < clothing < 2
    ):
        return _unavailable()
    try:
        partial_vapor_pressure = humidity * 10 * exp(
            16.6536 - 4030.183 / (air + 235.0)
        )
        if limit_inputs and not 0 < partial_vapor_pressure < 2700:
            return _unavailable()

        insulation = 0.155 * clothing
        metabolic = activity * MET_TO_W_M2
        net_metabolic = metabolic - work * MET_TO_W_M2
        clothing_area = (1.0 + 1.29 * insulation if insulation <= 0.078
                         else 1.05 + 0.645 * insulation)
        forced_convective = 12.1 * sqrt(velocity)
        kelvin_air = air + 273.0
        kelvin_radiant = radiant + 273.0
        initial_clothing_kelvin = (
            kelvin_air + (35.5 - air) / (3.5 * (6.45 * insulation + 0.1))
        )
        coefficient = insulation * clothing_area
        radiative_coefficient = coefficient * 3.96
        convective_coefficient = coefficient * 100.0
        source = (
            308.7 - 0.028 * net_metabolic
            + radiative_coefficient * (kelvin_radiant / 100.0) ** 4
        )
        current = initial_clothing_kelvin / 100.0
        previous = initial_clothing_kelvin / 50.0
        convective = forced_convective
        for _ in range(150):
            if abs(current - previous) <= 0.00015:
                break
            previous = (previous + current) / 2.0
            natural_convective = 2.38 * abs(
                100.0 * previous - kelvin_air
            ) ** 0.25
            convective = max(forced_convective, natural_convective)
            current = (
                source + coefficient * kelvin_air * convective
                - radiative_coefficient * previous ** 4
            ) / (100.0 + convective_coefficient * convective)
        else:
            return _unavailable()

        clothing_temperature = 100.0 * current - 273.0
        heat_loss_skin = 0.00305 * (
            5733 - 6.99 * net_metabolic - partial_vapor_pressure
        )
        heat_loss_sweating = (
            0.42 * (net_metabolic - MET_TO_W_M2)
            if net_metabolic > MET_TO_W_M2 else 0.0
        )
        heat_loss_breathing_latent = (
            0.000017 * metabolic * (5867 - partial_vapor_pressure)
        )
        heat_loss_breathing_sensible = 0.0014 * metabolic * (34 - air)
        heat_loss_radiant = (
            3.96 * clothing_area
            * (current ** 4 - (kelvin_radiant / 100.0) ** 4)
        )
        heat_loss_convection = (
            clothing_area * convective * (clothing_temperature - air)
        )
        thermal_load = (
            net_metabolic - heat_loss_skin - heat_loss_sweating
            - heat_loss_breathing_latent - heat_loss_breathing_sensible
            - heat_loss_radiant - heat_loss_convection
        )
        pmv = (0.303 * exp(-0.036 * metabolic) + 0.028) * thermal_load
        if not isfinite(pmv) or (limit_inputs and not -2 < pmv < 2):
            return _unavailable()
        ppd = 100.0 - 95.0 * exp(
            -0.03353 * pmv ** 4 - 0.2179 * pmv ** 2
        )
        if not isfinite(ppd) or not 5 - 1e-8 <= ppd <= 100 + 1e-8:
            return _unavailable()
    except (ArithmeticError, ValueError, TypeError):
        return _unavailable()

    return PmvPpd(
        round(pmv, 2) if round_output else pmv,
        round(ppd, 1) if round_output else ppd,
    )
