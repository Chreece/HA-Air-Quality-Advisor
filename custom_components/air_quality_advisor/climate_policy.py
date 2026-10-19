"""Deterministic, international per-room climate-control policy.

Methods:
- Device-native closed loop: send a target temperature; never impose a second PID.
- Outer-loop PID: bounded thermostat setpoint trim (pid_math).
- Hysteresis with independent minimum on/off times for relays.
- Time-proportioning PWM *only* on user-confirmed relay-safe equipment.
- Occupancy and home/away priority without treating unknown as absent.
- Explicit heating/cooling deadband and minimum mode dwell.

ASHRAE 55: standard/adaptive comfort applicability must be checked separately.
ASHRAE Guideline 36: occupied/unoccupied modes and deadband are engineering
precedents, not validation of residential HVAC operation.
HA Generic Thermostat: minimum cycle/lockout controls.
No equipment, device, local conditions, sensors, or global location inferred.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Sequence

STRATEGIES = frozenset(("device", "setpoint_pid", "on_off", "pwm", "proportional"))
MODE_OPTIONS = frozenset(("heat", "cool", "auto"))
PROFILE_OPTIONS = frozenset(("occupied", "unoccupied", "away", "home", "sleep", "unknown"))
MAX_TEMP_SPREAD_C = 10.0
DEFAULT_CLIMATE = {
    "enabled": False, "strategy": "device", "operation": "heat",
    "temperature_entity": None,
    "heat_entity": None, "cool_entity": None,
    "climate_entity": None,
    "allow_hvac_mode_change": False, "allow_turn_off": False,
    "target_source": "temperature",
    "home_heat_c": 20.5, "home_cool_c": 25.0,
    "occupied_heat_c": 21.0, "occupied_cool_c": 24.5,
    "unoccupied_heat_c": 18.5, "unoccupied_cool_c": 27.0,
    "away_heat_c": 16.0, "away_cool_c": 29.0,
    "sleep_heat_c": 19.0, "sleep_cool_c": 25.5,
    "comfort_heat_c": 21.0, "comfort_cool_c": 24.5,
    "occupied_uses_comfort": True,
    "occupancy_entities": [],
    "auto_discover_occupancy": True,
    "home_entities": [],
    "vacancy_delay_seconds": 900,
    "away_delay_seconds": 900,
    "sleep_enabled": False, "sleep_start": "23:00", "sleep_end": "07:00",
    "heat_cool_deadband_c": 2.0, "hysteresis_c": 0.3,
    "min_mode_seconds": 1800, "min_on_seconds": 300,
    "min_off_seconds": 300, "max_on_seconds": 3600,
    "pwm_period_seconds": 1800, "pwm_min_pulse_seconds": 300,
    "pwm_hardware_confirmed": False,
    "relay_hardware_confirmed": False,
    "pause_on_window_open": True, "turn_relay_off_on_bad_data": True,
    "output_min": 0.0, "output_max": 100.0,
    "sample_seconds": 300, "kp": 22.0, "ki": 0.25,
    "kd": 0.0, "offset_c": 1.5,
    "min_setpoint_c": 10, "max_setpoint_c": 32,
    "max_change_c": 0.5, "min_change_c": 0.15,
    "status": "automatic",
}


def safe_num(value: Any, low: float, high: float) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return n if math.isfinite(n) and low <= n <= high else None


def merge_config(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return dict(DEFAULT_CLIMATE)
    return {**DEFAULT_CLIMATE, **raw}


def choose_occupancy(states: Sequence[bool | None]) -> str:
    """Any true => occupied. All known false => unoccupied. Unknown != false."""
    if True in states:
        return "occupied"
    if states and all(value is False for value in states):
        return "unoccupied"
    return "unknown"


def choose_home(states: Sequence[bool | None]) -> str:
    if True in states:
        return "home"
    if states and all(value is False for value in states):
        return "away"
    return "unknown"


def valid_local_hhmm(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        return False
    try:
        hour, minute = map(int, value.split(":"))
        return 0 <= hour <= 23 and 0 <= minute <= 59
    except ValueError:
        return False


def in_sleep_window(now_hhmm: str, start: str, end: str) -> bool:
    if not all(valid_local_hhmm(v) for v in (now_hhmm, start, end)):
        return False
    if start == end:
        return False
    return (start <= now_hhmm < end) if start < end else (now_hhmm >= start or now_hhmm < end)


def stable_absence(raw: str, since: float | None, now: float, delay_seconds: float) -> str:
    if raw not in ("away", "unoccupied"):
        return raw
    if since is None or not math.isfinite(since) or now < since:
        return "unknown"
    return raw if now - since >= delay_seconds else "unknown"


def choose_profile(room_presence: str, home_presence: str, *,
                   sleeping: bool = False) -> str:
    # A positive local presence report dominates a conflicting stale global tracker.
    if room_presence == "occupied":
        return "occupied"
    if home_presence == "away":
        return "away"
    if sleeping and home_presence != "away":
        return "sleep"
    if room_presence == "unoccupied":
        return "unoccupied"
    return "home"


def targets_for_profile(config: dict, profile: str) -> tuple[float, float]:
    p = profile if profile in PROFILE_OPTIONS and profile != "unknown" else "home"
    if config.get("target_source") == "comfort" and p in ("occupied", "home") and (
        p != "occupied" or config.get("occupied_uses_comfort", True)
    ):
        heat, cool = config.get("comfort_heat_c"), config.get("comfort_cool_c")
    else:
        heat, cool = config.get(f"{p}_heat_c"), config.get(f"{p}_cool_c")
    h, c = safe_num(heat, 5, 36), safe_num(cool, 5, 40)
    if h is None or c is None or c - h < config.get("heat_cool_deadband_c", 2.0) - 1e-6:
        raise ValueError("heat_cool_deadband_invalid")
    return h, c


@dataclass(frozen=True)
class ModeDecision:
    mode: str              # heat | cool | idle
    status: str            # ready | held_deadband | held_min_dwell | invalid
    target_c: float | None = None


def select_mode(temp_c: float, heat_c: float, cool_c: float,
                operation: str, *, hysteresis_c: float = 0.3,
                previous_mode: str = "idle", seconds_since_mode_change: float | None = None,
                min_mode_seconds: float = 1800) -> ModeDecision:
    """Deadband + hysteresis; no direct heat->cool without safe off dwell."""
    t = safe_num(temp_c, -10, 50)
    h, c = safe_num(heat_c, 5, 36), safe_num(cool_c, 5, 40)
    hyst = safe_num(hysteresis_c, 0.1, 3)
    dwell = safe_num(min_mode_seconds, 300, 86400)
    if (t is None or h is None or c is None or hyst is None or dwell is None
            or operation not in MODE_OPTIONS or h >= c):
        return ModeDecision("idle", "invalid")
    wanted = "idle"
    if operation == "heat":
        wanted = "heat" if t < h - hyst else "idle"
        if previous_mode == "heat" and t < h + hyst:
            wanted = "heat"
    elif operation == "cool":
        wanted = "cool" if t > c + hyst else "idle"
        if previous_mode == "cool" and t > c - hyst:
            wanted = "cool"
    else:
        if t < h - hyst:
            wanted = "heat"
        elif t > c + hyst:
            wanted = "cool"
        elif previous_mode == "heat" and t < h + hyst:
            wanted = "heat"
        elif previous_mode == "cool" and t > c - hyst:
            wanted = "cool"
    # Never reverse directly from heating to cooling or vice versa.
    if previous_mode in ("heat", "cool") and wanted in ("heat", "cool") and previous_mode != wanted:
        return ModeDecision("idle", "held_deadband")
    if (wanted != previous_mode and previous_mode in ("heat", "cool")
            and seconds_since_mode_change is not None and seconds_since_mode_change < dwell):
        return ModeDecision(previous_mode, "held_min_dwell",
                            h if previous_mode == "heat" else c)
    return ModeDecision(wanted, "ready", h if wanted == "heat" else c if wanted == "cool" else None)


@dataclass(frozen=True)
class OnOffDecision:
    desired_on: bool
    status: str


def hysteresis_demand(measured: float, target: float, mode: str,
                      *, was_on: bool, hysteresis_c: float = .3) -> bool:
    delta = safe_num(measured, -10, 50)
    goal = safe_num(target, 5, 40)
    hyst = safe_num(hysteresis_c, .1, 3)
    if delta is None or goal is None or hyst is None or mode not in ("heat", "cool"):
        return False
    if mode == "heat":
        return delta < goal + hyst if was_on else delta < goal - hyst
    return delta > goal - hyst if was_on else delta > goal + hyst


def onoff_decision(wanted: bool, actual: bool, *,
                   seconds_since_switch: float | None, min_on_seconds: float,
                   min_off_seconds: float, max_on_seconds: float | None = None) -> OnOffDecision:
    minimum_on = safe_num(min_on_seconds, 60, 7200)
    minimum_off = safe_num(min_off_seconds, 60, 7200)
    max_on = safe_num(max_on_seconds, 60, 86400) if max_on_seconds is not None else None
    if minimum_on is None or minimum_off is None or (
        max_on_seconds is not None and max_on is None
    ):
        return OnOffDecision(False, "invalid_cycle_limits")
    if seconds_since_switch is None or not math.isfinite(seconds_since_switch) or seconds_since_switch < 0:
        return OnOffDecision(False, "unknown_actuator_cycle_state")
    if actual and max_on is not None and seconds_since_switch >= max_on:
        return OnOffDecision(False, "max_on_cutoff")
    if actual == wanted:
        return OnOffDecision(actual, "unchanged")
    if actual and seconds_since_switch < minimum_on:
        return OnOffDecision(True, "minimum_on_dwell")
    if not actual and seconds_since_switch < minimum_off:
        return OnOffDecision(False, "minimum_off_dwell")
    return OnOffDecision(wanted, "change")


def pwm_decision(duty_percent: float, now_s: float, start_s: float,
                 *, period_seconds: float, min_pulse_seconds: float) -> dict:
    duty = safe_num(duty_percent, 0, 100)
    period = safe_num(period_seconds, 900, 14400)
    pulse = safe_num(min_pulse_seconds, 60, 3600)
    if duty is None or period is None or pulse is None or pulse * 2 > period:
        return {"status":"invalid"}
    if not all(isinstance(x, (int,float)) and math.isfinite(x) for x in (now_s,start_s)) or now_s < start_s:
        return {"status":"invalid"}
    phase = (now_s - start_s) % period
    if duty == 0:
        on_s = 0
    elif duty == 100:
        on_s = period
    else:
        on_s = period * duty / 100
        on_s = 0 if on_s < pulse else (period if period-on_s < pulse else on_s)
    return {"status": "ready", "desired_on": phase < on_s,
            "phase_seconds": round(phase,2), "on_seconds": round(on_s,2),
            "period_seconds": period}


def validate_climate_config(raw: Any) -> tuple[bool,str]:
    config=merge_config(raw)
    if not isinstance(raw,dict) or config["strategy"] not in STRATEGIES:
        return False,"strategy"
    if config["operation"] not in MODE_OPTIONS:
        return False,"operation"
    for key in ("home","occupied","unoccupied","away","sleep","comfort"):
        try:
            targets_for_profile({**config,"target_source":"temperature"} if key != "comfort" else
                                {**config,"target_source":"comfort"},key)
        except (TypeError,ValueError):
            return False,"invalid_"+key+"_targets"
    for key,lo,hi in [
        ("heat_cool_deadband_c",1,8),("hysteresis_c",.1,3),
        ("vacancy_delay_seconds",0,86400),("away_delay_seconds",0,86400),
        ("min_mode_seconds",300,86400),("min_on_seconds",60,7200),
        ("min_off_seconds",60,7200),("max_on_seconds",60,86400),
        ("sample_seconds",120,3600),("pwm_period_seconds",900,14400),
        ("pwm_min_pulse_seconds",60,3600),("kp",.01,100),("ki",0,10),
        ("kd",0,50),("output_min",0,100),("output_max",0,100),
        ("offset_c",.25,5),("min_setpoint_c",5,35),("max_setpoint_c",6,40),
        ("max_change_c",.1,2),("min_change_c",.05,1),
    ]:
        if safe_num(config.get(key),lo,hi) is None:
            return False,"invalid_"+key
    if config["output_min"]>=config["output_max"]:
        return False,"invalid_output_limits"
    if config["min_setpoint_c"]>=config["max_setpoint_c"]:
        return False,"invalid_setpoint_limits"
    if config["max_on_seconds"] <= config["min_on_seconds"]:
        return False,"invalid_max_on"
    if config["pwm_min_pulse_seconds"] * 2 > config["pwm_period_seconds"]:
        return False,"invalid_pwm_pulse"
    if not valid_local_hhmm(config.get("sleep_start")) or not valid_local_hhmm(config.get("sleep_end")):
        return False,"invalid_sleep_schedule"
    if config["operation"]=="auto" and not config.get("allow_hvac_mode_change",False) and (
        config["strategy"] in ("device", "setpoint_pid")
    ):
        return False,"auto_requires_explicit_mode_switch_permission"
    if config["strategy"]=="pwm" and not config.get("pwm_hardware_confirmed"):
        return False,"pwm_equipment_not_confirmed"
    if config["strategy"] in ("on_off","pwm") and not config.get("relay_hardware_confirmed"):
        return False,"relay_equipment_not_confirmed"
    return True,"ready"
