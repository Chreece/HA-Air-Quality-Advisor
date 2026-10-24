"""Regression: measured fan capacity compensates ON/OFF PID duty safely.

All capacity data must be real operator-supplied relative physical output,
not a normalized guess based on airflow. Physical actuation keeps independent
power permissions, minimum dwell, native ACK and quiet-room gates.
"""
from __future__ import annotations

import asyncio
import pytest

from custom_components.environment_manager.pid_fan_capacity import (
    build_model, allocate, model_is_valid,
)
from test_equipment_control import home, runtime_module
from custom_components.environment_manager import equipment_model as model
from test_discovery import adapter


def discrete():
    return build_model(
        percentage=False, advertised_modes=("low","medium","high"),
        measured={"pid_capacity_stage_1":30,"pid_capacity_stage_2":65},
    )


def valid_record(direction="heat"):
    return {**discrete(), "direction":direction,
        "physical_entity":"climate.room","fan_entity":"climate.room",
        "sources":["climate.room"]}


def test_duty_compensates_actual_measured_medium_capacity():
    allocated = allocate(50,discrete(),quiet=False,quiet_mode=None,
        quiet_percentage=30,fan_min_percentage=1,fan_max_percentage=100)
    assert allocated.speed=="medium"
    assert allocated.stage_capacity_percent==65
    assert allocated.compensated_duty_percent==pytest.approx(50/65*100)
    assert allocated.expected_delivered_percent==50
    assert allocated.unmet_demand_percent==0


def test_quiet_limit_reports_unserved_demand_instead_of_overriding_cap():
    actual=allocate(50,discrete(),quiet=True,quiet_mode="low",
        quiet_percentage=30,fan_min_percentage=1,fan_max_percentage=100)
    assert actual.speed=="low"
    assert actual.compensated_duty_percent==100
    assert actual.stage_capacity_percent==30
    assert actual.expected_delivered_percent==30
    assert actual.unmet_demand_percent==20
    assert actual.quiet_limited
    assert allocate(90,discrete(),quiet=True,quiet_mode="high",
        quiet_percentage=30,fan_min_percentage=1,fan_max_percentage=100).speed=="high"


def test_variable_percentage_curve_supports_real_non_25_percent_native_steps():
    native=tuple(str(i) for i in range(10,101,10))
    measured={"pid_capacity_speed_1":40,"pid_capacity_output_1":35,
              "pid_capacity_speed_2":70,"pid_capacity_output_2":75,
              "pid_capacity_speed_3":0,"pid_capacity_output_3":0}
    curve=build_model(percentage=True,advertised_modes=native,
                      measured=measured,min_speed=40)
    a=allocate(50,curve,quiet=False,quiet_mode=None,quiet_percentage=50,
               fan_min_percentage=40,fan_max_percentage=100)
    assert a.speed==60
    assert a.stage_capacity_percent==pytest.approx(61.6666666)
    assert a.compensated_duty_percent==pytest.approx(50/61.6666666*100)
    capped=allocate(50,curve,quiet=True,quiet_mode=None,
                   quiet_percentage=50,fan_min_percentage=40,fan_max_percentage=100)
    assert capped.speed==50
    assert capped.compensated_duty_percent==100
    assert capped.unmet_demand_percent==pytest.approx(1.6666666)
    assert allocate(50,curve,quiet=True,quiet_mode=None,
                    quiet_percentage=20,fan_min_percentage=40,
                    fan_max_percentage=100) is not None


@pytest.mark.parametrize("measured,error",[
    ({"pid_capacity_stage_1":0,"pid_capacity_stage_2":65},
     "complete_measured_stage_capacities_required"),
    ({"pid_capacity_stage_1":70,"pid_capacity_stage_2":60},
     "measured_fan_capacities_must_increase_monotonically"),
    ({"pid_capacity_stage_1":30,"pid_capacity_stage_2":101},
     "complete_measured_stage_capacities_required"),
])
def test_invalid_discrete_capacity_never_assumed(measured,error):
    with pytest.raises(ValueError, match=error):
        build_model(percentage=False,advertised_modes=("low","medium","high"),
                    measured=measured)


def test_unsupported_native_modes_and_incomplete_percentage_readings_fail_closed():
    with pytest.raises(ValueError,match="two_to_five_ordered_native_fan_stages_required"):
        build_model(percentage=False,advertised_modes=("sleep","auto","turbo"),
                    measured={"pid_capacity_stage_1":33,"pid_capacity_stage_2":66})
    native=("20","40","60","80","100")
    with pytest.raises(ValueError,match="incomplete_measured_percentage_pair"):
        build_model(percentage=True,advertised_modes=native,
            measured={"pid_capacity_speed_1":40,"pid_capacity_output_1":0})
    with pytest.raises(ValueError,match="two_measured_percentage_capacity_points_required"):
        build_model(percentage=True,advertised_modes=native,
            measured={"pid_capacity_speed_1":40,"pid_capacity_output_1":30})


def test_capacity_record_is_specific_to_mode_physical_source_and_native_choices():
    saved=valid_record()
    args={"physical_entity":"climate.room","fan_entity":"climate.room",
          "percentage":False,"advertised_modes":("low","medium","high")}
    assert model_is_valid(saved,mode="heat",**args)
    assert not model_is_valid(saved,mode="dry",**args)
    assert not model_is_valid(saved,mode="heat",**{**args,"fan_entity":"fan.other"})
    assert not model_is_valid(saved,mode="heat",**{**args,
        "advertised_modes":("low","high")})


def test_apply_only_when_native_power_off_no_pending_and_no_hardware_command(runtime_module):
    async def run():
        cfg={"pid_fan_capacity_for_mode":"heat",
             "pid_capacity_stage_1":30,"pid_capacity_stage_2":65}
        h=home(runtime_module,domain="climate",mode="pid",state="off",controls=cfg)
        assert h.manager.settings[model.SETTINGS][h.spec.identifier]["pid_fan_capacity_mode"]=="legacy"
        await h.runtime.async_apply_fan_capacity(h.spec)
        selected=h.manager.settings[model.SETTINGS][h.spec.identifier]
        assert selected["pid_fan_capacity_mode"]=="measured"
        assert selected["pid_fan_capacity_models"]["heat"]["points"]==[
            [1,30.],[2,65.],[3,100.]
        ]
        assert h.hass.services.calls == []
        h.state.state="heat"
        with pytest.raises(Exception,match="OFF"):
            await h.runtime.async_apply_fan_capacity(h.spec)
        h.state.state="off"
        h.runtime._record(h.spec)["pending"]={"phase":"intent"}
        with pytest.raises(Exception,match="safely OFF"):
            await h.runtime.async_apply_fan_capacity(h.spec)
        assert h.hass.services.calls == []
    asyncio.run(run())


def test_runtime_uses_capacity_compensation_and_sends_matching_real_speed(runtime_module):
    async def run():
        cfg={"pid_fan_capacity_for_mode":"heat",
             "pid_capacity_stage_1":30,"pid_capacity_stage_2":65,
             "kp":10,"ki":0,"kd":0}
        h=home(runtime_module,domain="climate",mode="pid",state="off",controls=cfg)
        await h.runtime.async_apply_fan_capacity(h.spec)
        await h.runtime.tick(h.spec)
        a=h.runtime._fan_allocations[h.spec.identifier]
        assert a["speed"]=="medium"
        assert a["compensated_duty_percent"]==pytest.approx(50/65*100)
        assert a["status"]=="capacity_compensated"
        assert h.hass.services.calls[0][1:3]==("set_hvac_mode",{"hvac_mode":"heat"})
        for _ in range(8):
            await h.runtime.tick(h.spec)
            if any(c[1]=="set_fan_mode" for c in h.hass.services.calls):
                break
        fan=[c for c in h.hass.services.calls if c[1]=="set_fan_mode"]
        assert fan and fan[-1][2]["fan_mode"]=="medium",h.hass.services.calls
    asyncio.run(run())


def test_runtime_quiet_capacity_saturates_and_reports_shortfall(runtime_module):
    async def run():
        cfg={"pid_fan_capacity_for_mode":"heat",
             "pid_capacity_stage_1":30,"pid_capacity_stage_2":65,
             "kp":100,"ki":0,"kd":0,"quiet_sleep":True}
        h=home(runtime_module,domain="climate",mode="pid",state="off",controls=cfg)
        h.plan["sleeping"]=True
        await h.runtime.async_apply_fan_capacity(h.spec)
        await h.runtime.tick(h.spec)
        a=h.runtime._fan_allocations[h.spec.identifier]
        assert a["speed"]=="low" and a["status"]=="capacity_limited"
        assert a["compensated_duty_percent"]==100
        assert a["stage_capacity_percent"]==30
        assert a["unmet_demand_percent"]>0
        assert a["unmet_demand_percent"]==pytest.approx(
            a["demand_percent"]-a["stage_capacity_percent"])
        assert h.hass.services.calls[0][1]=="set_hvac_mode"
    asyncio.run(run())


def test_legacy_strategy_unchanged_when_no_capacity_model(runtime_module):
    async def run():
        h=home(runtime_module,domain="climate",mode="pid",state="off")
        await h.runtime.tick(h.spec)
        assert h.spec.identifier not in h.runtime._fan_allocations
        assert h.hass.services.calls[0][1]=="set_hvac_mode"
    asyncio.run(run())
