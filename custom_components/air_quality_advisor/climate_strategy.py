"""Capability-gated room climate policy; pure functions, no Home Assistant I/O.

ASHRAE Guideline 36's occupied/unoccupied heating and cooling band philosophy
is adapted as a user-configurable operating policy, NOT standard certification.
The equipment's independent freeze, overheat and compressor protections remain
mandatory. Unsupported commands are never guessed from brand or entity name.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import math


@dataclass(frozen=True)
class Profile:
    name: str
    heat_c: float
    cool_c: float


@dataclass(frozen=True)
class Output:
    state: str
    profile: str
    temperature_c: float | None
    desired_hvac_mode: str | None
    reason: str
    controller: str
    range_low_c: float | None = None
    range_high_c: float | None = None


def _num(value: Any, low: float, high: float) -> float | None:
    if isinstance(value,bool): return None
    try: value=float(value)
    except (TypeError,ValueError,OverflowError): return None
    return value if math.isfinite(value) and low <= value <= high else None


def profiles(settings: dict) -> tuple[dict[str,Profile],str|None]:
    """Reject heating/cooling overlap or biologically unsafe defaults."""
    raw=settings.get("profiles",{}) if isinstance(settings,dict) else {}
    if not isinstance(raw,dict):
        return {},"invalid_profile_collection"
    tolerance=_num(settings.get("hysteresis_c",0.7),0.2,3.0) if isinstance(settings,dict) else None
    if tolerance is None:
        return {},"invalid_hysteresis"
    defaults={
        "home": {"heat_c":20.0,"cool_c":26.0},
        "unoccupied": {"heat_c":18.0,"cool_c":28.0},
        "away": {"heat_c":16.0,"cool_c":30.0},
        "sleep": {"heat_c":18.0,"cool_c":26.0},
    }
    parsed={}
    for name, fallback in defaults.items():
        v=raw.get(name,fallback)
        if not isinstance(v,dict): return {},f"invalid_profile_{name}"
        heat=_num(v.get("heat_c"),5,35)
        cool=_num(v.get("cool_c"),6,40)
        if heat is None or cool is None or cool-heat<max(1.0,2*tolerance):
            return {},f"overlapping_or_invalid_{name}"
        parsed[name]=Profile(name,heat,cool)
    return parsed,None


def occupied_evidence(values: list[bool|None], *, unknown_policy: str="occupied") -> tuple[str,str]:
    """Multiple room presence/occupancy sensors: any on dominates.

    All-off is only 'unoccupied' when every selected sensor is valid; missing
    readings default to occupied (safest for comfort), not false vacancy.
    """
    if unknown_policy not in ("occupied","hold"):
        return "unknown","invalid_policy"
    if not values:
        return ("occupied","no_sensor_conservative") if unknown_policy=="occupied" else ("unknown","no_sensor")
    if any(v is True for v in values): return "occupied","one_or_more_presence_sensors_on"
    if all(v is False for v in values): return "unoccupied","all_presence_sensors_off"
    return ("occupied","unknown_sensor_conservative") if unknown_policy=="occupied" else ("unknown","partial_presence_data")


def home_away_evidence(states: list[bool|None], *, mode: str="any_home") -> tuple[str,str]:
    """True means person at home from a tracker or explicit binary sensor."""
    if mode not in ("any_home","all_home"): return "unknown","invalid_policy"
    if not states: return "home","no_tracker_configured"
    if any(s is None for s in states): return "home","unknown_tracker_conservative"
    if mode=="any_home":
        return ("home","someone_home") if any(states) else ("away","everyone_away")
    return ("home","everyone_home") if all(states) else ("away","not_everyone_home")


def select_profile(settings:dict, *, at_home:str, occupied:str,
                   sleeping:bool=False, manual:str|None=None) -> tuple[str,str]:
    if manual in ("home","unoccupied","away","sleep"):
        return manual,"manual_profile"
    if at_home=="away": return "away","all_trackers_away"
    if at_home=="unknown" or occupied=="unknown":
        return "home","incomplete_evidence"
    if sleeping: return "sleep","sleep_mode_active"
    if occupied=="unoccupied": return "unoccupied","room_unoccupied"
    return "home","room_occupied"


def capabilities(attributes: dict, current_mode: str) -> dict:
    if not isinstance(attributes,dict): return {"kind":"unavailable"}
    try: feature=int(attributes.get("supported_features",0))
    except (ValueError,TypeError,OverflowError): return {"kind":"unavailable"}
    modes=attributes.get("hvac_modes",())
    modes=modes if isinstance(modes,(tuple,list)) else []
    modes=[str(v).lower() for v in modes if isinstance(v,str)]
    single=bool(feature&1)
    dual=bool(feature&2)
    heat="heat" in modes
    cool="cool" in modes
    return {"kind":"climate","current":current_mode,"heat":heat,"cool":cool,
            "setpoint":single,"range":dual,
            "auto":("heat_cool" in modes or "auto" in modes),
            "modes":modes}


def auto_mode(temp_c:float|None, heat_c:float, cool_c:float,
              previous:str|None, *, hysteresis_c:float=0.7) -> tuple[str|None,str]:
    """Mutual exclusion and Schmitt hysteresis; never oscillate across center."""
    t=_num(temp_c,-10,50)
    h=_num(hysteresis_c,0.2,3)
    if t is None or h is None or cool_c-heat_c < max(1.0,2*h):
        return None,"invalid_temperature_or_deadband"
    if previous=="heat" and t <= heat_c+h: return "heat","heating_hysteresis"
    if previous=="cool" and t >= cool_c-h: return "cool","cooling_hysteresis"
    if t <= heat_c-h: return "heat","heating_demand"
    if t >= cool_c+h: return "cool","cooling_demand"
    return "off","within_deadband"


def policy(settings:dict, *, temp_c:float|None,
           capability:dict, at_home:str, occupied:str,
           sleeping:bool=False, manual_profile:str|None=None,
           prior_mode:str|None=None, window_safe:bool=True,
           comfort_target_c:float|None=None) -> Output:
    default=Output("disabled","home",None,None,"not_enabled","none")
    if not isinstance(settings,dict) or settings.get("enabled") is not True: return default
    all_profiles,err=profiles(settings)
    if err: return Output("invalid_config","home",None,None,err,"none")
    name,why=select_profile(settings,at_home=at_home,occupied=occupied,
                            sleeping=sleeping,manual=manual_profile)
    band=all_profiles[name]
    if not window_safe:
        return Output("hold",name,None,None,"open_or_unknown_window","none")
    strategy=settings.get("controller","device")
    if strategy not in ("device","setpoint_pid","on_off","pwm","proportional"):
        return Output("invalid_config",name,None,None,"unknown_strategy","none")
    if strategy in ("on_off","pwm","proportional"):
        # Switch relays and proportional number controls are distinct drivers;
        # neither one can be inferred from a climate.* entity name.
        expected_kind = "number" if strategy=="proportional" else "switch"
        if capability.get("kind")!=expected_kind:
            return Output("unsupported_device",name,None,None,"verified_direct_actuator_required",strategy)
    if strategy in ("device","setpoint_pid") and capability.get("kind")!="climate":
        return Output("unsupported_device",name,None,None,"climate_required",strategy)
    mode_choice=settings.get("mode","auto")
    if mode_choice not in ("auto","heat","cool","off"):
        return Output("invalid_config",name,None,None,"invalid_mode","none")
    if mode_choice=="off":
        return Output("advisory",name,None,"off","explicit_off_requested",strategy)
    if mode_choice=="auto":
        desired,reason=auto_mode(temp_c,band.heat_c,band.cool_c,prior_mode,
                                 hysteresis_c=float(settings.get("hysteresis_c",0.7)))
        if desired is None: return Output("hold",name,None,None,reason,strategy)
    else:
        desired,reason=mode_choice,"explicit_heating_or_cooling"
    if desired in ("heat","cool") and not capability.get(desired,False):
        return Output("unsupported_mode",name,None,None,"device_does_not_support_"+desired,strategy)
    heat_target,cool_target=band.heat_c,band.cool_c
    # Apply PMV only as a bounded modification to *home/sleep* comfort
    # bands. The preconfigured away and unoccupied setbacks are sacrosanct.
    if settings.get("target_source")=="pmv" and name in ("home","sleep"):
        comfort=_num(comfort_target_c,16,30)
        influence=_num(settings.get("comfort_adjustment_max_c",1.5),0,2.5)
        if comfort is not None and influence is not None:
            adjusted_heat=min(band.heat_c+influence,max(
                band.heat_c,min(comfort-0.5,band.cool_c-1.0)))
            adjusted_cool=max(band.cool_c-influence,min(
                band.cool_c,max(comfort+0.5,band.heat_c+1.0)))
            if adjusted_cool-adjusted_heat>=1:
                heat_target,cool_target=round(adjusted_heat,2),round(adjusted_cool,2)
    # Native dual-setpoint thermostats should use their own internal
    # heat/cool control whenever its range feature and mode are present.
    if (mode_choice=="auto" and strategy=="device"
            and settings.get("prefer_native_auto",True)
            and capability.get("range") and
            "heat_cool" in capability.get("modes",[])):
        return Output("ready",name,None,"heat_cool",
                      "native_heat_cool_range",strategy,
                      heat_target,cool_target)
    target=heat_target if desired=="heat" else cool_target if desired=="cool" else None
    # Manual setpoint PID must never be stacked over an unknown device's PID.
    if strategy=="setpoint_pid" and settings.get("native_pid",False):
        return Output("conflicting_controllers",name,None,None,"nested_pid_forbidden","none")
    return Output("ready",name,target,desired,reason,strategy)


def relay_demand(temp_c:float, target_c:float, mode:str, *,
                 cold_tolerance_c:float=0.3, hot_tolerance_c:float=0.3,
                 previous_on:bool=False)-> bool|None:
    """Schmitt relay hysteresis; not compressor cycle management."""
    t=_num(temp_c,-10,50)
    target=_num(target_c,5,36)
    cold=_num(cold_tolerance_c,0.1,5)
    hot=_num(hot_tolerance_c,0.1,5)
    if None in (t,target,cold,hot) or mode not in ("heat","cool"): return None
    if mode=="heat":
        return t < target+hot if previous_on else t <= target-cold
    return t > target-cold if previous_on else t >= target+hot


def guarded_transition(*, demand_on:bool, current_on:bool,
                       now:float,last_changed:float,
                       min_on_s:float,min_off_s:float,
                       maximum_on_s:float|None=None)->tuple[str,bool]:
    """Protect equipment and detect runaways; fail closed if state unknown."""
    dt=_num(now,0,1e13)
    last=_num(last_changed,0,1e13)
    on=_num(min_on_s,60,7200)
    off=_num(min_off_s,60,7200)
    if None in (dt,last,on,off) or dt<last or type(demand_on) is not bool or type(current_on) is not bool:
        return "invalid",current_on
    running=dt-last
    if current_on and maximum_on_s is not None and running>=maximum_on_s:
        return "maximum_runtime_exceeded",False
    if demand_on==current_on: return "unchanged",current_on
    if current_on and running<on: return "minimum_on_hold",True
    if not current_on and running<off: return "minimum_off_hold",False
    return "transition",demand_on


def pwm_slot(demand_percent:float, *, period_s:float, now_s:float,
             anchor_s:float, min_on_s:float,min_off_s:float)->tuple[str,bool]:
    """Time-proportioning PWM for slow thermal loads, never raw compressors.

    One deterministic stable cycle anchor is required. Incompatible requested
    minimum pulse lengths are rejected rather than generating tiny pulses.
    """
    duty=_num(demand_percent,0,100)
    period=_num(period_s,300,7200)
    clock=_num(now_s,0,1e13)
    anchor=_num(anchor_s,0,1e13)
    on=_num(min_on_s,60,7200)
    off=_num(min_off_s,60,7200)
    if None in (duty,period,clock,anchor,on,off) or clock<anchor:
        return "invalid",False
    if duty==0: return "off",False
    if duty==100: return "on",True
    on_time=period*duty/100
    if on_time<on or period-on_time<off:
        return "pulse_too_short",False
    return "ready",(clock-anchor)%period<on_time
