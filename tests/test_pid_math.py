"""Supervisory PID math: anti-windup, quantization, units, invalid timing."""
import pytest
from custom_components.enviroment_manager.pid_math import (
    DEFAULT_PID, Memory, validate_settings, step, setpoint_c, bounded_command,
    target_to_unit, target_from_unit,
)


def test_defaults_are_bounded_and_disabled_until_opt_in():
    assert not DEFAULT_PID["enabled"]
    assert validate_settings(DEFAULT_PID) == (True, "ready")
    assert validate_settings({**DEFAULT_PID,"min_setpoint_c":24,"max_setpoint_c":20})[0] is False
    assert validate_settings({**DEFAULT_PID,"mode":"heat_cool"})[0] is False
    assert validate_settings({**DEFAULT_PID,"sample_seconds":10})[0] is False


def test_pid_ignores_initial_sample_and_never_runs_subminute():
    result=step(20,22,1000,"heat",20,0.2,0,300,Memory())
    assert result.status == "initializing"
    assert result.demand_percent is None
    assert step(20,22,1200,"heat",20,0.2,0,300,result.memory).status == "waiting_sample"
    active=step(20,22,1300,"heat",20,0.2,0,300,result.memory)
    assert active.status=="ready"
    assert active.demand_percent > 40
    assert step(20,22,999,"heat",20,0.2,0,300,result.memory).status=="nonmonotonic_time"


def test_pid_sign_and_saturation_antiwindup():
    h=step(16,22,1300,"heat",100,1,0,300,
           Memory(integral=0,last_c=16,last_s=1000))
    c=step(30,24,1300,"cool",100,1,0,300,
           Memory(integral=0,last_c=30,last_s=1000))
    assert h.demand_percent == c.demand_percent == 100
    assert h.integral == c.integral == 0
    # Heat over target drives demand down without using a negative actuator.
    off=step(28,22,1300,"heat",20,0.5,0,300,
             Memory(integral=0,last_c=28,last_s=1000))
    assert off.demand_percent == 0


def test_pid_derivative_is_measurement_not_setpoint_kick():
    state=Memory(integral=2,last_c=19,last_s=1000)
    a=step(19.5,22,1300,"heat",0.01,0,12,300,state)
    b=step(19.5,24,1300,"heat",0.01,0,12,300,state)
    assert a.derivative == b.derivative  # target change must not kick D term
    assert a.derivative < 0


def test_cool_and_heat_setpoint_trim_never_toggle_hvac():
    assert setpoint_c(21,0,"heat",2,17,26)==21
    assert setpoint_c(21,100,"heat",2,17,26)==23
    assert setpoint_c(25,100,"cool",2,19,29)==23
    assert setpoint_c(25,100,"heat",2,19,26)==26
    assert setpoint_c(25,50,"auto",2,19,28) is None


def test_celsius_fahrenheit_and_device_step_are_respected():
    assert target_to_unit(20,"°F")==68
    assert target_from_unit(68,"°F")==20
    assert target_to_unit(20,"K") is None
    status,value=bounded_command(22,20,max_change_c=0.5,min_change_c=0.1,
                                 unit="°C",device_min=7,device_max=30,device_step=0.5)
    assert status=="command" and value==20.5
    status,value=bounded_command(20.1,20,max_change_c=0.5,min_change_c=0.2,
                                 unit="°C",device_min=7,device_max=30,device_step=0.5)
    assert status=="no_meaningful_change" and value is None
    status,value=bounded_command(21,20,max_change_c=0.5,min_change_c=0.1,
                                 unit="°F",device_min=50,device_max=90,device_step=1)
    assert status in ("command","device_step_exceeds_rate_limit")
    assert bounded_command(22,20,max_change_c=0.5,min_change_c=0.1,
                           unit="K",device_min=0,device_max=500,device_step=1)[0]=="unsupported_temperature_unit"


@pytest.mark.parametrize("bad", [None,float("nan"),float("inf"),True])
def test_bad_measurement_does_not_influence_actuator(bad):
    assert step(bad,22,1300,"heat",20,0.2,0,300).status=="invalid_input"
