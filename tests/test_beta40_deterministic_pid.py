"""Deterministic per-device PID tuning and capability-based output allocator.

No spontaneous physical calibration cycle is ever performed. Tests explicitly
assert no native service is sent by model tuning, and that fan/valve demand
cannot be applied twice through speed *and* duty-cycle modulation.
"""
from __future__ import annotations

import asyncio
import math

import pytest

from custom_components.environment_manager.pid_calibration import (
    MODEL_FIELDS, METHODS, tune,
)
from custom_components.environment_manager.pid_output_allocator import (
    ordered_fan_stages, fan_speed_for_pid, percentage_output_requested,
)
from test_equipment_control import home, runtime_module
from test_equipment_entities import platforms
from test_discovery import adapter
from custom_components.environment_manager import equipment_model as model


MODEL = {
    "pid_process_gain": 100.,
    "pid_time_constant_minutes": 30.,
    "pid_dead_time_minutes": 5.,
    "pid_lambda_minutes": 90.,
}


def test_calibration_methods_are_deterministic_nonactuating_and_dimensionally_parallel():
    assert METHODS == ("manual", "imc_lambda", "cohen_coon")
    first=tune("imc_lambda", MODEL, sample_seconds=300,
               constraints=model.NUMBER_FIELDS)
    second=tune("imc_lambda",MODEL,sample_seconds=300,
                constraints=model.NUMBER_FIELDS)
    assert first==second
    assert first.kp==pytest.approx(30/95)
    assert first.ki==pytest.approx(first.kp/30)
    assert first.kd==0
    assert first.lambda_minutes==90
    cohen=tune("cohen_coon",MODEL,sample_seconds=300,
               constraints=model.NUMBER_FIELDS)
    assert cohen.kp==pytest.approx(8.25)
    assert cohen.ki>0
    assert cohen.kd>0
    assert cohen.kp>first.kp
    assert cohen.lambda_minutes is None


@pytest.mark.parametrize("method,changes,error", [
    ("manual",{}, "select_imc_lambda_or_cohen_coon"),
    ("imc_lambda",{"pid_process_gain":0.0},"calibration_model_outside_bounds"),
    ("imc_lambda",{"pid_time_constant_minutes":2.},"process_faster_than_pid_sampling"),
    ("imc_lambda",{"pid_lambda_minutes":1.},"imc_lambda_too_aggressive"),
    ("cohen_coon",{"pid_process_gain":0.1},"calculated_kp_outside_safe_bounds"),
    ("imc_lambda",{"pid_dead_time_minutes":float("nan")},"calibration_model_missing_or_invalid"),
])
def test_missing_unsafe_or_unidentified_models_reject_instead_of_clamping(
    method,changes,error,
):
    values={**MODEL,**changes}
    with pytest.raises(ValueError,match=error):
        tune(method,values,sample_seconds=300,
             constraints=model.NUMBER_FIELDS)


def test_pid_allocator_never_guesses_native_stage_order_or_doubles_speed():
    assert ordered_fan_stages(["high","low","medium"]) == ("low","medium","high")
    assert ordered_fan_stages(["sleep","auto","turbo"])==()
    assert ordered_fan_stages(["level_3","level_1","level_2"]) == (
        "level_1","level_2","level_3")
    assert fan_speed_for_pid(15,modes=["high","medium","low"],percentage=False)=="low"
    assert fan_speed_for_pid(55,modes=["high","medium","low"],percentage=False)=="medium"
    assert fan_speed_for_pid(95,modes=["high","medium","low"],percentage=False)=="high"
    assert fan_speed_for_pid(95,modes=["low","medium","high"],percentage=False,
                             quiet=True,quiet_mode="low")=="low"
    assert fan_speed_for_pid(95,modes=["sleep","auto","turbo"],percentage=False) is None
    assert fan_speed_for_pid(75,modes=["10","20","30","40","50","60","70","80","90","100"],
                             percentage=True,quiet=True,quiet_percentage=30)==30
    assert fan_speed_for_pid(75,modes=["40","60","80","100"],percentage=True,
                             min_percentage=40,max_percentage=80,
                             quiet=True,quiet_percentage=20)==40
    assert percentage_output_requested(30,min_percentage=10)
    assert not percentage_output_requested(5,min_percentage=10)
    assert not percentage_output_requested(0,min_percentage=10)


def test_per_device_pid_calibration_selector_and_apply_button(platforms):
    async def scenario():
        h=home(platforms.runtime,domain="climate",state="off",mode="pid")
        h.manager.entry.data[model.SETTINGS][h.spec.identifier].update(MODEL)
        choice=platforms.select.EquipmentSelect(h.manager,h.spec,"pid_calibration_method")
        button=platforms.button.EquipmentCalibrationButton(h.manager,h.spec)
        assert choice.options==list(METHODS)
        assert choice.current_option=="manual"
        assert not button.available
        await choice.async_select_option("imc_lambda")
        assert choice.current_option=="imc_lambda"
        assert button.available
        assert button.extra_state_attributes["calibration_status"]=="ready_to_apply_when_physical_off"
        assert h.hass.services.calls==[]
        before={k:h.manager.settings[model.SETTINGS][h.spec.identifier][k]
                for k in ("kp","ki","kd")}
        await button.async_press()
        after={k:h.manager.settings[model.SETTINGS][h.spec.identifier][k]
               for k in ("kp","ki","kd")}
        assert after!=before
        assert after["kp"]==pytest.approx(30/95)
        assert after["ki"]==pytest.approx(after["kp"]/30)
        assert after["kd"]==0
        evidence=h.manager.settings[model.SETTINGS][h.spec.identifier]["pid_last_calibration"]
        assert evidence["method"]=="imc_lambda"
        assert evidence["observed_sources"]==[h.entity]
        assert h.hass.services.calls==[], "Model tuning must never invoke hardware"
    asyncio.run(scenario())


def test_calibration_rejected_during_actual_on_or_incomplete_model(runtime_module):
    async def scenario():
        h=home(runtime_module,domain="climate",state="heat",mode="pid",
               controls={**MODEL,"pid_calibration_method":"imc_lambda"})
        with pytest.raises(Exception,match="OFF"):
            await h.runtime.async_apply_pid_calibration(h.spec)
        assert h.hass.services.calls==[]
        assert h.manager.settings[model.SETTINGS][h.spec.identifier]["pid_last_calibration"] is None
        h.state.state="off"
        h.manager.entry.data[model.SETTINGS][h.spec.identifier]["pid_process_gain"]=0
        with pytest.raises(Exception,match="measured model"):
            await h.runtime.async_apply_pid_calibration(h.spec)
        assert h.hass.services.calls==[]
    asyncio.run(scenario())


def test_pid_modulating_fan_turns_on_once_and_uses_percentage_not_double_pwm(
    runtime_module,
):
    async def scenario():
        h=home(runtime_module,domain="fan",state="off",mode="pid",
               controls={"kp":0.05,"ki":0.001,"kd":0.0})
        await h.runtime.tick(h.spec)
        assert [c[1] for c in h.hass.services.calls]==["turn_on"]
        await h.runtime.tick(h.spec)
        cmds=[c for c in h.hass.services.calls if c[1]=="set_percentage"]
        assert cmds, "PID modulating fan must adjust its actual native speed"
        assert cmds[-1][2]["percentage"]==30
        assert h.state.state=="on"
        assert h.runtime.statuses[h.spec.identifier]["status"] != "physical_device_unavailable"
        # A 5% PID demand cannot silently request the unavailable minimum
        # 10% output or send a second short PWM pulse.
        assert not percentage_output_requested(5,min_percentage=10)
    asyncio.run(scenario())


def test_climate_pid_allocates_same_demand_to_native_discrete_fan_with_quiet_cap(
    runtime_module,
):
    async def scenario():
        h=home(runtime_module,domain="climate",state="off",mode="pid",
               controls={"quiet_sleep":True})
        h.plan["sleeping"]=True
        await h.runtime.tick(h.spec)
        assert h.hass.services.calls[0][1:3]==(
            "set_hvac_mode",{"hvac_mode":"heat"})
        await h.runtime.tick(h.spec)
        fan=[call for call in h.hass.services.calls if call[1]=="set_fan_mode"]
        assert fan and fan[-1][2]=={"fan_mode":"low"},fan
        assert all(call[1] != "set_percentage" for call in h.hass.services.calls)
    asyncio.run(scenario())


def test_unverified_sleep_evidence_prevents_new_pid_power_activation(runtime_module):
    async def scenario():
        h=home(runtime_module,domain="climate",state="off",mode="pid",
               controls={"quiet_sleep":True})
        h.plan["sleeping"]=None
        await h.runtime.tick(h.spec)
        assert h.hass.services.calls==[]
        assert h.runtime.statuses[h.spec.identifier]["status"]=="quiet_context_unknown"
    asyncio.run(scenario())
