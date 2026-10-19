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
