"""Evidence-qualified occupancy, profile priority, hysteresis and PWM invariants."""
import pytest
from custom_components.air_quality_advisor.climate_policy import (
    DEFAULT_CLIMATE, choose_occupancy, choose_home, stable_absence,
    choose_profile, in_sleep_window, targets_for_profile, select_mode,
    hysteresis_demand, onoff_decision, pwm_decision, validate_climate_config,
)


def test_unknown_presence_is_not_away_or_unoccupied():
    assert choose_occupancy([])=="unknown"
    assert choose_occupancy([False,None])=="unknown"
    assert choose_occupancy([True,None])=="occupied"
    assert choose_occupancy([False,False])=="unoccupied"
    assert choose_home([False,None])=="unknown"
    assert choose_home([True,False])=="home"
    assert choose_home([False,False])=="away"


def test_room_occupancy_overrides_stale_global_tracker_and_sleep_is_explicit():
    assert choose_profile("occupied","away")=="occupied"
    assert choose_profile("occupied","home",sleeping=True)=="sleep"
    assert choose_profile("unoccupied","away")=="away"
    assert choose_profile("unoccupied","unknown")=="unoccupied"
    assert choose_profile("unknown","unknown")=="home"
    assert stable_absence("away",100,200,900)=="unknown"
    assert stable_absence("away",100,1000,900)=="away"
    assert stable_absence("unoccupied",None,1000,900)=="unknown"


def test_sleep_window_crosses_midnight_in_local_wall_clock():
    assert in_sleep_window("23:30","23:00","07:00")
    assert in_sleep_window("05:10","23:00","07:00")
    assert not in_sleep_window("12:15","23:00","07:00")
    assert not in_sleep_window("23:30","25:00","07:00")


def test_occupied_unoccupied_away_comfort_profiles_and_deadband():
    config=dict(DEFAULT_CLIMATE)
    assert targets_for_profile(config,"occupied") == (21.0,24.5)
    assert targets_for_profile(config,"unoccupied")==(18.5,27.0)
    assert targets_for_profile(config,"away")==(16.0,29.0)
    config["target_source"]="comfort"
    assert targets_for_profile(config,"occupied")==(21.0,24.5)
    config["occupied_uses_comfort"]=False
    assert targets_for_profile(config,"home")==(21.0,24.5)
    config["comfort_heat_c"]=24
    config["comfort_cool_c"]=25
    with pytest.raises(ValueError):
        targets_for_profile(config,"home")


def test_heat_cool_switch_has_deadband_and_minimum_dwell():
    assert select_mode(19,20,25,"auto").mode=="heat"
    assert select_mode(27,20,25,"auto").mode=="cool"
    assert select_mode(23,20,25,"auto").mode=="idle"
    out=select_mode(27,20,25,"auto",previous_mode="heat",
                    seconds_since_mode_change=4000,min_mode_seconds=1800)
    assert out.mode=="idle" and out.status=="held_deadband"
    staying=select_mode(20.1,20,25,"heat",previous_mode="heat",
                        seconds_since_mode_change=1800)
    assert staying.mode=="heat"
    assert select_mode(20.5,20,25,"heat",previous_mode="heat").mode=="idle"


def test_onoff_hysteresis_and_lockouts():
    assert hysteresis_demand(19,20,"heat",was_on=False)
    assert not hysteresis_demand(19.9,20,"heat",was_on=False)
    assert hysteresis_demand(19.9,20,"heat",was_on=True)
    assert hysteresis_demand(26,25,"cool",was_on=False)
    assert onoff_decision(True,False,seconds_since_switch=None,
                          min_on_seconds=300,min_off_seconds=300).status=="unknown_actuator_cycle_state"
    assert not onoff_decision(True,False,seconds_since_switch=200,
                              min_on_seconds=300,min_off_seconds=300).desired_on
    assert onoff_decision(True,False,seconds_since_switch=301,
                          min_on_seconds=300,min_off_seconds=300).status=="change"
    assert not onoff_decision(True,True,seconds_since_switch=3601,
                              min_on_seconds=300,min_off_seconds=300,max_on_seconds=3600).desired_on


def test_pwm_never_has_short_unsafe_pulses():
    config={**DEFAULT_CLIMATE,"strategy":"pwm","pwm_hardware_confirmed":False,
            "relay_hardware_confirmed":True}
    assert validate_climate_config(config)[1]=="pwm_equipment_not_confirmed"
    config["pwm_hardware_confirmed"]=True
    assert validate_climate_config(config)[0]
    assert pwm_decision(50,0,0,period_seconds=1800,min_pulse_seconds=300)["desired_on"]
    assert not pwm_decision(50,950,0,period_seconds=1800,min_pulse_seconds=300)["desired_on"]
    assert pwm_decision(5,0,0,period_seconds=1800,min_pulse_seconds=300)["on_seconds"]==0
    assert pwm_decision(95,0,0,period_seconds=1800,min_pulse_seconds=300)["on_seconds"]==1800
    assert pwm_decision(50,0,0,period_seconds=600,min_pulse_seconds=300)["status"]=="invalid"


def test_validation_rejects_conflicting_targets_and_unverified_switch():
    assert validate_climate_config(DEFAULT_CLIMATE)==(True,"ready")
    assert not validate_climate_config({**DEFAULT_CLIMATE,"home_heat_c":23,"home_cool_c":23})[0]
    assert validate_climate_config({**DEFAULT_CLIMATE,"strategy":"on_off"})[1]=="relay_equipment_not_confirmed"
    assert validate_climate_config({**DEFAULT_CLIMATE,"operation":"auto"})[1]=="auto_requires_explicit_mode_switch_permission"
