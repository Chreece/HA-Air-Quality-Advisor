"""Local-time recurring comfort schedules (no cloud or geographic defaults).

Schedules use the Home Assistant time zone and are evaluated on every tick;
DST transitions therefore follow local wall clock time naturally. Invalid
inputs never accidentally activate away/sleep.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Any
import math
import re

TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def _minutes(value: Any) -> int | None:
    if not isinstance(value, str) or not TIME_RE.fullmatch(value):
        return None
    hours, minutes = (int(n) for n in value.split(":"))
    return hours*60+minutes


def local_interval_active(epoch_s: float, time_zone: str,
                          start: str, end: str) -> tuple[bool | None,str]:
    """Return whether HH:MM interval is active, supporting midnight crossing."""
    try:
        timestamp=float(epoch_s)
        if not math.isfinite(timestamp) or timestamp < 0:
            return None,"invalid_clock"
        local=ZoneInfo(time_zone)
        moment=datetime.fromtimestamp(timestamp,local)
    except (ValueError,TypeError,OverflowError,ZoneInfoNotFoundError):
        return None,"invalid_time_zone_or_clock"
    beginning,ending=_minutes(start),_minutes(end)
    if beginning is None or ending is None or beginning==ending:
        return None,"invalid_interval"
    current=moment.hour*60+moment.minute
    if beginning<ending:
        return beginning<=current<ending,"local_daytime_interval"
    return current>=beginning or current<ending,"local_overnight_interval"


def scheduled_sleep(settings:dict, now_s:float, zone:str)->tuple[bool,str]:
    if settings.get("sleep_active") is True:
        return True,"manual_sleep_enabled"
    if settings.get("sleep_schedule_enabled") is not True:
        return False,"sleep_schedule_disabled"
    on,reason=local_interval_active(
        now_s,zone,settings.get("sleep_start","22:00"),
        settings.get("sleep_end","07:00"),
    )
    # Fail closed for scheduled control: a bad timezone/time does not force
    # a nighttime heating/cooling target.
    return bool(on),reason if on is not None else "invalid_sleep_schedule"
