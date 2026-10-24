"""Deterministic allocation of one PID demand to supported actuator outputs.

No hardware calls or inferred native capabilities. A binary output is duty-
cycled, a percentage-capable output modulates continuously, and genuinely
ordered discrete fan modes use stages. Quiet mode caps a fan's *speed* and
never authorizes its power, raises valve demand, or invents a fan mode.
"""
from __future__ import annotations

import math
import re
from typing import Iterable


_ORDER = {
    "silent": 0, "quiet": 0, "low": 1, "medium": 2,
    "mid": 2, "high": 3, "turbo": 4,
}


def ordered_fan_stages(modes: Iterable[str]) -> tuple[str, ...]:
    """Only sort modes with explicitly understood physical speed order.

    The provided names must all be explicit low/mid/high type aliases or a
    numeric level_# group. Unknown presets such as 'auto', 'natural', or
    'sleep' are not an ordering and must not be assigned invented power.
    """
    choices = tuple(mode for mode in modes if isinstance(mode, str))
    if not choices:
        return ()
    if all(key.casefold() in _ORDER for key in choices):
        return tuple(sorted(dict.fromkeys(choices),
                            key=lambda mode: (_ORDER[mode.casefold()], choices.index(mode))))
    numeric = [re.fullmatch(r"(?:level|speed|fan)[_ -]?(\d+)", mode.casefold())
               for mode in choices]
    if all(numeric):
        return tuple(sorted(dict.fromkeys(choices),
                            key=lambda mode: int(re.search(r"(\d+)$",mode).group(1))))
    return ()


def fan_speed_for_pid(
    demand: float,
    *,
    modes: Iterable[str], percentage: bool,
    min_percentage: float = 1.0, max_percentage: float = 100.0,
    quiet: bool = False, quiet_percentage: float = 30.0,
    quiet_mode: str | None = None,
) -> float | str | None:
    """Pick exactly one supported native speed without affecting ON/OFF.

    For percentage devices demand is the desired percent, not a second PWM
    fraction. For discrete stages, only advertised ordered modes are mapped.
    The final hardware service still verifies capabilities, limits and owner.
    """
    if type(demand) not in (int, float) or not math.isfinite(demand):
        return None
    if demand <= 0:
        return None
    if percentage:
        if not (0 < min_percentage <= max_percentage <= 100):
            return None
        speed = max(min_percentage, min(max_percentage, demand))
        if quiet:
            speed = min(speed, max(min_percentage, min(max_percentage, quiet_percentage)))
        # Rounding/native percentage_step happens in the existing runtime,
        # never silently invent a hardware step here.
        return float(speed)
    stages = ordered_fan_stages(modes)
    if not stages:
        return None
    index = max(0,min(len(stages)-1,
                      math.ceil(min(100., demand)*len(stages)/100)-1))
    if quiet:
        cap = quiet_mode or ("low" if "low" in stages else None)
        if cap not in stages:
            return None
        index = min(index, stages.index(cap))
    return stages[index]


def percentage_output_requested(demand: float, *,
                                min_percentage: float) -> bool:
    """Avoid cycling speed-modulating fans AND modulating them by the same PID.

    Below the lowest physical operating speed a continuous fan cannot realize
    this demand safely. Preserve OFF instead of forcing a higher steady flow.
    Native min ON/OFF is still checked independently when switching power.
    """
    return (type(demand) in (int, float) and math.isfinite(demand)
            and 0 < min_percentage <= 100 and demand >= min_percentage)
