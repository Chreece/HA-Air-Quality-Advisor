"""Direct slow-load actuator safety and Home Assistant service contract.

No real relay, boiler or compressor is controlled by this suite.
"""
from __future__ import annotations

import asyncio
import importlib
import sys
import types
from types import SimpleNamespace

import pytest

from test_discovery import FakeHass, MockState, adapter


class MemoryStore:
    payload = None
    def __init__(self,*args):
        self.data = type(self).payload
    async def async_load(self):
        return self.data
    async def async_save(self,data):
        self.data = data
        type(self).payload = data
    def async_delay_save(self,callback,delay):
        self.data = callback()
        type(self).payload = self.data


class Services:
    def __init__(self,hass):
        self.hass=hass
        self.calls=[]
        self.fail=False
        self.ack=True
    def has_service(self,domain,service):
        return (domain,service) in (("switch","turn_on"),("switch","turn_off"),
                                    ("number","set_value"))
    async def async_call(self,domain,service,data,**kwargs):
        self.calls.append((domain,service,data,kwargs))
        if self.fail:
            raise RuntimeError("simulated integration failure")
        if self.ack:
            state=self.hass.states.get(kwargs["target"]["entity_id"])
            state.state=(
                "on" if service=="turn_on" else
                "off" if service=="turn_off" else str(data["value"])
            )


@pytest.fixture
def runtime(adapter,monkeypatch):
    MemoryStore.payload=None
    storage=types.ModuleType("homeassistant.helpers.storage")
    storage.Store=MemoryStore
    monkeypatch.setitem(sys.modules,storage.__name__,storage)
    return importlib.import_module("custom_components.air_quality_advisor.climate_direct")


def home(*,include_cool=False,proportional=False):
    temp=MockState("sensor.living_temperature",16,device_class="temperature",unit="°C")
    entity="number.living_heat" if proportional else "switch.living_heat"
    heat=MockState(entity,"0" if proportional else "off")
    values=[temp,heat]
    if proportional:
        heat.attributes.update({"unit_of_measurement":"%","min":0,
                                "max":100,"step":1})
    if include_cool:
        cool=MockState("switch.living_cool","off")
        values.append(cool)
    hass=FakeHass(values,{s.entity_id:"living" for s in values})
    hass.services=Services(hass)
    hass.async_create_task=asyncio.create_task
    return hass


def settings(**overrides):
    return {"enabled":True,"allow_actuation":True,
            "direct_hardware_confirmed":True,
            "controller":"on_off",
            "temperature_entity":"sensor.living_temperature",
            "heat_actuator":"switch.living_heat",
            "min_on_s":120,"min_off_s":180,"max_on_s":7200,
            "mode_dwell_s":900,"sample_seconds":300,
            **overrides}


def planned(mode="heat",*,target=20,valid=True):
    return {"status":"ready" if valid else "hold",
            "mode":mode,"window_safe":valid,
            "temperature_target_c":target,"reason":"simulation"}


async def advance(driver,clock,config,report):
    driver.schedule({"living":config},{"living":report})
    for _ in range(5):
        await asyncio.sleep(0)


def test_default_no_actuator_permission_never_energizes(runtime):
    async def case():
        hass=home()
        clock=[1000.]
        driver=runtime.DirectClimateControl(hass,"unit",clock=lambda:clock[0])
        await driver.async_start()
        clock[0]=2400.
        await advance(driver,clock,settings(allow_actuation=False),planned())
        assert driver.statuses["living"]["status"]=="advisory_only"
        assert hass.services.calls==[]
        await driver.async_stop()
    asyncio.run(case())


def test_onoff_relay_uses_dwell_and_never_broadcasts(runtime):
    async def case():
        hass=home()
        clock=[1000.]
        driver=runtime.DirectClimateControl(hass,"unit",clock=lambda:clock[0])
        await driver.async_start()
        clock[0]=1350.
        await advance(driver,clock,settings(),planned())
        assert hass.services.calls==[]
        clock[0]=2000.
        await advance(driver,clock,settings(),planned())
        assert len(hass.services.calls)==1
        domain,service,data,kwargs=hass.services.calls[0]
        assert (domain,service)==("switch","turn_on")
        assert kwargs["target"]=={"entity_id":"switch.living_heat"}
        assert not data
        await driver.async_stop()
    asyncio.run(case())


def test_manual_switch_override_pauses_instead_of_fighting_user(runtime):
    async def case():
        hass=home()
        clock=[1000.]
        driver=runtime.DirectClimateControl(hass,"unit",clock=lambda:clock[0])
        await driver.async_start()
        clock[0]=2000.
        await advance(driver,clock,settings(),planned())
        assert hass.services.calls
        hass.states.get("switch.living_heat").state="off"
        clock[0]=2300.
        await advance(driver,clock,settings(),planned())
        assert driver.paused["living"]=="manual_override_or_unacknowledged_output"
        assert len(hass.services.calls)==1
        await driver.async_stop()
    asyncio.run(case())


def test_maximum_energized_runtime_cuts_off_even_when_still_demanded(runtime):
    async def case():
        hass=home()
        clock=[1000.]
        driver=runtime.DirectClimateControl(hass,"unit",clock=lambda:clock[0])
        await driver.async_start()
        clock[0]=2000.
        await advance(driver,clock,settings(max_on_s=600),planned())
        assert hass.services.calls[-1][1]=="turn_on"
        clock[0]=2601.
        await advance(driver,clock,settings(max_on_s=600),planned())
        assert hass.services.calls[-1][1]=="turn_off"
        assert driver.paused["living"]=="maximum_on_runtime_exceeded"
        await driver.async_stop()
    asyncio.run(case())


def test_window_hold_sends_safe_off_after_earlier_authorized_on(runtime):
    async def case():
        hass=home()
        clock=[1000.]
        driver=runtime.DirectClimateControl(hass,"unit",clock=lambda:clock[0])
        await driver.async_start()
        clock[0]=2000.
        await advance(driver,clock,settings(),planned())
        assert hass.states.get("switch.living_heat").state=="on"
        clock[0]=2100.
        await advance(driver,clock,settings(),planned(valid=False))
        assert hass.services.calls[-1][1]=="turn_off"
        await driver.async_stop()
    asyncio.run(case())


def test_missing_temperature_safely_deenergizes_owned_output(runtime):
    async def case():
        hass=home()
        clock=[1000.]
        driver=runtime.DirectClimateControl(hass,"unit",clock=lambda:clock[0])
        await driver.async_start()
        clock[0]=2000.
        await advance(driver,clock,settings(),planned())
        hass.states.get("sensor.living_temperature").state="unavailable"
        clock[0]=2100.
        await advance(driver,clock,settings(),planned())
        assert hass.services.calls[-1][1]=="turn_off"
        await driver.async_stop()
    asyncio.run(case())


def test_restart_unowned_on_never_creates_new_on_command(runtime):
    async def case():
        hass=home()
        hass.states.get("switch.living_heat").state="on"
        clock=[1000.]
        driver=runtime.DirectClimateControl(hass,"unit",clock=lambda:clock[0])
        await driver.async_start()
        clock[0]=2000.
        await advance(driver,clock,settings(),planned())
        assert driver.paused["living"]=="unowned_active_output"
        assert not hass.services.calls
        await driver.async_stop()
    asyncio.run(case())


def test_cooling_interlock_turns_off_opposing_heat_before_cool(runtime):
    async def case():
        hass=home(include_cool=True)
        clock=[1000.]
        driver=runtime.DirectClimateControl(hass,"unit",clock=lambda:clock[0])
        await driver.async_start()
        clock[0]=2000.
        conf=settings(cool_actuator="switch.living_cool")
        await advance(driver,clock,conf,planned("heat"))
        assert hass.states.get("switch.living_heat").state=="on"
        clock[0]=2300.
        await advance(driver,clock,conf,planned("cool",target=12))
        assert hass.services.calls[-1][1]=="turn_off"
        assert hass.services.calls[-1][3]["target"]["entity_id"]=="switch.living_heat"
        assert all(not (c[1]=="turn_on" and c[3]["target"]["entity_id"]=="switch.living_cool")
                   for c in hass.services.calls)
        await driver.async_stop()
    asyncio.run(case())


def test_unverified_percent_output_is_not_controlled(runtime):
    async def case():
        hass=home(proportional=True)
        hass.states.get("number.living_heat").attributes["unit_of_measurement"]="not percent"
        clock=[1000.]
        driver=runtime.DirectClimateControl(hass,"unit",clock=lambda:clock[0])
        await driver.async_start()
        clock[0]=2000.
        conf=settings(controller="proportional",heat_actuator="number.living_heat")
        await advance(driver,clock,conf,planned())
        assert driver.statuses["living"]["status"]=="unverified_proportional_range"
        assert not hass.services.calls
        await driver.async_stop()
    asyncio.run(case())


def test_pwm_is_sampled_and_refuses_too_short_pulses(runtime):
    async def case():
        hass=home()
        clock=[1000.]
        driver=runtime.DirectClimateControl(hass,"unit",clock=lambda:clock[0])
        await driver.async_start()
        conf=settings(controller="pwm",pwm_period_s=900,kp=18,ki=.12,kd=0)
        clock[0]=2000.
        await advance(driver,clock,conf,planned())
        assert not hass.services.calls
        clock[0]=2300.
        await advance(driver,clock,conf,planned())
        assert driver.statuses["living"]["status"] in (
            "holding","commanded","minimum_off_hold","mode_transfer_dwell"
        )
        assert all(call[0]=="switch" for call in hass.services.calls)
        await driver.async_stop()
    asyncio.run(case())

def test_pause_explicitly_deenergizes_only_owned_output(runtime):
    async def case():
        hass=home()
        clock=[1000.]
        driver=runtime.DirectClimateControl(hass,"pause",clock=lambda:clock[0])
        await driver.async_start()
        conf=settings()
        clock[0]=2000.
        await advance(driver,clock,conf,planned())
        assert hass.states.get("switch.living_heat").state=="on"
        result=await driver.command("living","pause",{"living":conf})
        assert result["accepted"] is True
        assert hass.states.get("switch.living_heat").state=="off"
        assert hass.services.calls[-1][1]=="turn_off"
        clock[0]=2300.
        await advance(driver,clock,conf,planned())
        assert driver.paused["living"]=="user_paused"
        await driver.async_stop()
    asyncio.run(case())


def test_unload_switches_off_controller_owned_heat_without_powering_on(runtime):
    async def case():
        hass=home()
        clock=[1000.]
        driver=runtime.DirectClimateControl(hass,"stop",clock=lambda:clock[0])
        await driver.async_start()
        conf=settings()
        clock[0]=2000.
        await advance(driver,clock,conf,planned())
        assert hass.states.get("switch.living_heat").state=="on"
        await driver.async_stop()
        assert hass.states.get("switch.living_heat").state=="off"
        assert hass.services.calls[-1][1]=="turn_off"
    asyncio.run(case())


def test_manual_pause_does_not_overwrite_unowned_energized_relay(runtime):
    async def case():
        hass=home()
        hass.states.get("switch.living_heat").state="on"
        clock=[1000.]
        driver=runtime.DirectClimateControl(hass,"unowned",clock=lambda:clock[0])
        await driver.async_start()
        result=await driver.command("living","pause",{"living":settings()})
        assert not result["accepted"]
        assert driver.paused["living"]=="pause_output_unconfirmed"
        assert hass.services.calls==[]
        await driver.async_stop()
    asyncio.run(case())

def test_proportional_actuator_has_both_step_and_sample_rate_limit(runtime):
    async def case():
        hass=home(proportional=True)
        clock=[1000.]
        driver=runtime.DirectClimateControl(hass,"percent",clock=lambda:clock[0])
        await driver.async_start()
        settings_=settings(controller="proportional",
            heat_actuator="number.living_heat",
            kp=18,ki=.12,kd=0,sample_seconds=300,
            max_demand_change=10,min_demand_change=2)
        clock[0]=2000.
        await advance(driver,clock,settings_,planned())
        assert not hass.services.calls   # initializes derivative and integral
        clock[0]=2300.
        await advance(driver,clock,settings_,planned())
        assert len(hass.services.calls)==1
        command=hass.services.calls[-1]
        assert command[0:2]==("number","set_value")
        assert command[2]["value"]==10.0
        clock[0]=2330.
        await advance(driver,clock,settings_,planned())
        assert len(hass.services.calls)==1  # 30-sec poll is not a PID cycle
        clock[0]=2600.
        await advance(driver,clock,settings_,planned())
        assert len(hass.services.calls)==2
        assert hass.services.calls[-1][2]["value"]==20.0
        await driver.async_stop()
        assert hass.states.get("number.living_heat").state=="0.0"
    asyncio.run(case())


def test_switch_actuation_does_not_assume_compressor_safety(runtime):
    async def case():
        hass=home()
        clock=[1000.]
        engine=runtime.DirectClimateControl(hass,"attestation",clock=lambda:clock[0])
        await engine.async_start()
        clock[0]=4000.
        await advance(engine,clock,settings(direct_hardware_confirmed=False),planned())
        assert engine.statuses["living"]["status"]=="advisory_only"
        assert hass.services.calls==[]
        await engine.async_stop()
    asyncio.run(case())


def test_two_controllers_cannot_run_same_room_even_for_different_devices(runtime):
    async def case():
        hass=home()
        clock=[1000.]
        engine=runtime.DirectClimateControl(hass,"collision",clock=lambda:clock[0])
        await engine.async_start()
        clock[0]=4000.
        engine.schedule({"living":settings()},{"living":planned()},
                        pid_rooms={"living":{"enabled":True,
                            "climate_entities":["climate.other_thermostat"]}})
        assert engine.statuses["living"]["status"]=="conflicting_pid_room"
        assert not hass.services.calls
        await engine.async_stop()
    asyncio.run(case())

def test_proportional_step_quantization_never_overshoots_rate_limit(runtime):
    async def case():
        hass=home(proportional=True)
        hass.states.get("number.living_heat").attributes["step"]=7
        clock=[1000.]
        driver=runtime.DirectClimateControl(hass,"step7",clock=lambda:clock[0])
        await driver.async_start()
        config=settings(controller="proportional",heat_actuator="number.living_heat",
            max_demand_change=10,min_demand_change=2)
        clock[0]=2000.
        await advance(driver,clock,config,planned())
        clock[0]=2300.
        await advance(driver,clock,config,planned())
        assert hass.services.calls[-1][2]["value"]==7.0
        clock[0]=2600.
        await advance(driver,clock,config,planned())
        assert hass.services.calls[-1][2]["value"]==14.0
        assert all(entry[2]["value"]%7==0 for entry in hass.services.calls)
        await driver.async_stop()
    asyncio.run(case())

def test_modulation_cannot_reset_continuous_output_watchdog(runtime):
    async def case():
        hass=home(proportional=True)
        clock=[1000.]
        driver=runtime.DirectClimateControl(hass,"modwatch",clock=lambda:clock[0])
        await driver.async_start()
        config=settings(controller="proportional",
            heat_actuator="number.living_heat",max_on_s=900,
            max_demand_change=10,min_demand_change=2)
        clock[0]=2000.
        await advance(driver,clock,config,planned())
        clock[0]=2300.
        await advance(driver,clock,config,planned())
        assert driver.energized_since["number.living_heat"]==2300.
        clock[0]=2600.
        await advance(driver,clock,config,planned())
        assert driver.energized_since["number.living_heat"]==2300.
        clock[0]=2900.
        await advance(driver,clock,config,planned())
        assert driver.energized_since["number.living_heat"]==2300.
        clock[0]=3201.
        await advance(driver,clock,config,planned())
        assert hass.states.get("number.living_heat").state=="0.0"
        assert driver.paused["living"]=="maximum_on_runtime_exceeded"
        assert "number.living_heat" not in driver.energized_since
        await driver.async_stop()
    asyncio.run(case())


def test_missing_continuous_runtime_history_is_fail_safe_even_with_valid_ack(runtime):
    async def case():
        hass=home(proportional=True)
        clock=[1000.]
        driver=runtime.DirectClimateControl(hass,"history",clock=lambda:clock[0])
        await driver.async_start()
        config=settings(controller="proportional",
                        heat_actuator="number.living_heat")
        clock[0]=2000.
        await advance(driver,clock,config,planned())
        clock[0]=2300.
        await advance(driver,clock,config,planned())
        assert driver.energized_since
        driver.energized_since.clear()  # Corrupted/incomplete persisted state
        clock[0]=2360.
        await advance(driver,clock,config,planned())
        assert driver.paused["living"]=="continuous_runtime_history_missing"
        assert hass.states.get("number.living_heat").state=="0.0"
        await driver.async_stop()
    asyncio.run(case())


def test_direct_noncompressor_heat_off_holds_when_opposing_ac_arms(runtime):
    async def case():
        from custom_components.air_quality_advisor.climate_arbitration import (
            room_coordination,
        )
        hass=home()
        cooling=MockState("climate.living_ac","off")
        cooling.attributes.update({
            "hvac_modes":["off","cool"],"supported_features":1,
            "hvac_action":"idle",
        })
        hass._values[cooling.entity_id]=cooling
        hass._entity_areas[cooling.entity_id]="living"
        conf=settings(cool_climate_entity=cooling.entity_id)
        proposed=planned()
        proposed["equipment_plan"]={
            "status":"ready",
            "thermal":{"status":"no_thermal_demand"},
        }
        proposed["coordination"]=room_coordination(
            hass,"living",conf,proposed,now=1400,
        )
        assert proposed["coordination"]["channels"]["thermal"]["status"]=="eligible"
        clock=[1000.]
        controller=runtime.DirectClimateControl(
            hass,"shared-coordination",clock=lambda:clock[0],
        )
        await controller.async_start()
        clock[0]=2000
        cooling.state="cool"
        await advance(controller,clock,conf,proposed)
        assert not hass.services.calls
        assert controller.statuses["living"]["status"]=="safe_off"
        assert controller.statuses["living"]["reason"]=="opposing_native_mode_armed"
        cooling.state="off"
        await advance(controller,clock,conf,proposed)
        assert hass.services.calls[0][:2]==("switch","turn_on")
        await controller.async_stop()
    asyncio.run(case())


def test_direct_output_rejects_corrupt_or_future_safety_history(runtime):
    async def case():
        original={"version":999,"expected":{"switch.living_heat":{
            "state":True,"when":4000}}}
        MemoryStore.payload=original
        hass=home()
        clock=[1000.]
        driver=runtime.DirectClimateControl(hass,"future",clock=lambda:clock[0])
        await driver.async_start()
        assert driver._ready is False
        assert driver.statuses["*"]["status"]=="safety_history_unsupported"
        clock[0]=4000.
        await advance(driver,clock,settings(),planned())
        assert not hass.services.calls
        await driver.async_stop()
        assert MemoryStore.payload is original
    asyncio.run(case())


def test_direct_output_requires_durable_intent_before_energizing(runtime):
    async def case():
        hass=home()
        clock=[1000.]
        driver=runtime.DirectClimateControl(hass,"no_store",clock=lambda:clock[0])
        await driver.async_start()
        async def no_disk(data):
            raise OSError("Simulated persistent storage fault")
        driver._store.async_save=no_disk
        clock[0]=2000.
        await advance(driver,clock,settings(),planned())
        assert not hass.services.calls
        assert driver.paused["living"]=="direct_intent_storage_failed"
        assert driver.expected["switch.living_heat"]["phase"]=="intent"
        await driver.async_stop()
        assert hass.states.get("switch.living_heat").state=="off"
    asyncio.run(case())


def test_direct_on_ack_storage_failure_requires_manual_off_across_restart(runtime):
    async def case():
        hass=home()
        clock=[1000.]
        driver=runtime.DirectClimateControl(hass,"interrupted",clock=lambda:clock[0])
        await driver.async_start()
        save=driver._store.async_save
        calls=[0]
        async def lose_second(data):
            calls[0]+=1
            if calls[0]==2:
                raise OSError("Simulated crash after physical ON")
            await save(data)
        driver._store.async_save=lose_second
        clock[0]=2000.
        await advance(driver,clock,settings(),planned())
        assert hass.states.get("switch.living_heat").state=="on"
        assert driver.paused["living"]=="direct_command_history_persist_failed"
        assert MemoryStore.payload["expected"]["switch.living_heat"]["phase"]=="intent"
        # The new process sees the original write-ahead intent, never a
        # fabricated confirmed ON ownership record.
        driver._active=False
        next_driver=runtime.DirectClimateControl(hass,"interrupted",clock=lambda:clock[0])
        await next_driver.async_start()
        assert next_driver.paused["living"]==(
            "interrupted_direct_write_requires_manual_reconciliation"
        )
        clock[0]=3000.
        await advance(next_driver,clock,settings(),planned())
        assert len(hass.services.calls)==1  # no retry, no new ON/OFF
        result=await next_driver.command("living","resume",{"living":settings()})
        assert not result["accepted"]  # the physical relay is still ON
        from datetime import datetime,timezone
        output=hass.states.get("switch.living_heat")
        output.state="off"
        output.last_changed=datetime.fromtimestamp(2600,timezone.utc)
        result=await next_driver.command("living","resume",{"living":settings()})
        assert result["accepted"] is True
        assert "switch.living_heat" not in next_driver.expected
        assert next_driver._started==3000
        await next_driver.async_stop()
    asyncio.run(case())


def test_direct_rechecks_revoked_actuation_after_persisting_intent(runtime):
    async def case():
        hass=home()
        clock=[1000.]
        driver=runtime.DirectClimateControl(hass,"revoked",clock=lambda:clock[0])
        await driver.async_start()
        save=driver._store.async_save
        async def reconfigure_mid_store(data):
            # Simulate a live options update during asynchronous Store I/O.
            driver._last_config["living"]["allow_actuation"]=False
            await save(data)
        driver._store.async_save=reconfigure_mid_store
        clock[0]=2000.
        await advance(driver,clock,settings(),planned())
        assert hass.services.calls==[]
        assert driver.paused["living"]=="direct_intent_revoked_before_dispatch"
        assert MemoryStore.payload["expected"]["switch.living_heat"]["phase"]=="intent"
        await driver.async_stop()
    asyncio.run(case())
