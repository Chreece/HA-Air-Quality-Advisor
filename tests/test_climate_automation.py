"""Fake HA integration: explicit safety, ownership, occupancy and service routing."""
from __future__ import annotations

import asyncio
import importlib
import sys
import types
from types import SimpleNamespace

import pytest
from custom_components.air_quality_advisor.climate_policy import DEFAULT_CLIMATE
from custom_components.air_quality_advisor.logic import Room, Window
from test_discovery import FakeHass, MockState, adapter


class TestStore:
    def __init__(self,*_):
        self.data=None
    async def async_load(self):
        return self.data
    async def async_save(self,value):
        self.data=value
    def async_delay_save(self,callback,delay):
        self.data=callback()


class Service:
    def __init__(self,hass):
        self.hass=hass
        self.calls=[]
        self.fail=False
    def has_service(self,domain,action):
        return (domain,action) in {
            ("climate","set_temperature"),("climate","set_hvac_mode"),
            ("switch","turn_on"),("switch","turn_off"),
            ("input_boolean","turn_on"),("input_boolean","turn_off"),
            ("number","set_value"),("fan","set_percentage"),
        }
    async def async_call(self,domain,action,data,**kwargs):
        if self.fail:
            raise RuntimeError("simulated device offline")
        self.calls.append((domain,action,data,kwargs))
        entity=kwargs["target"]["entity_id"]
        state=self.hass.states.get(entity)
        if action=="set_temperature":
            state.attributes["temperature"]=data["temperature"]
        elif action=="set_hvac_mode":
            state.state=data["hvac_mode"]
        elif action in ("turn_on","turn_off"):
            state.state="on" if action=="turn_on" else "off"
        elif action=="set_value":
            state.state=str(data["value"])
        elif action=="set_percentage":
            state.attributes["percentage"]=data["percentage"]


@pytest.fixture
def env_runtime(monkeypatch,adapter):
    storage=types.ModuleType("homeassistant.helpers.storage")
    storage.Store=TestStore
    monkeypatch.setitem(sys.modules,"homeassistant.helpers.storage",storage)
    module=importlib.import_module("custom_components.air_quality_advisor.climate_automation")
    return module.ClimateAutomationCoordinator


def home(with_relay=False,occupied="on",at_home="home",mode="heat",temp=19):
    values=[
        MockState("sensor.living_temperature",temp,device_class="temperature",unit="°C"),
        MockState("binary_sensor.living_presence",occupied,device_class="occupancy"),
        MockState("person.household",at_home),
    ]
    if with_relay:
        values.extend([
            MockState("switch.living_heat","off"),
            MockState("switch.living_cool","off"),
        ])
    else:
        climate=MockState("climate.living_thermostat",mode)
        climate.attributes.update({
            "temperature":18, "temperature_unit":"°C","min_temp":7,"max_temp":30,
            "target_temp_step":0.5,"supported_features":1,
            "hvac_modes":["off","heat","cool"],"preset_mode":"none",
        })
        values.append(climate)
    assigned={s.entity_id:"living" for s in values if not s.entity_id.startswith("person.")}
    hass=FakeHass(values,assigned)
    hass.config=SimpleNamespace(time_zone="UTC")
    hass.services=Service(hass)
    hass.async_create_task=asyncio.create_task
    room=Room("living","Living",(Window("binary_sensor.window","Window",False),),())
    return hass,room


def conf(**overrides):
    return {**DEFAULT_CLIMATE,"enabled":True,
            "temperature_entity":"sensor.living_temperature",
            "climate_entity":"climate.living_thermostat",
            "occupancy_entities":["binary_sensor.living_presence"],
            "home_entities":["person.household"],
            **overrides}


async def run(engine,room,profile,clock):
    engine.schedule((room,),{"living":profile})
    for _ in range(4):await asyncio.sleep(0)


def test_device_native_never_uses_pid_or_changes_mode_without_opt_in(env_runtime):
    async def scenario():
        hass,room=home()
        now=[1000.0]
        engine=env_runtime(hass,"native",changed=lambda:None,clock=lambda:now[0])
        await engine.async_start()
        profile=conf()
        engine.schedule((room,),{"living":profile},initial=True)
        assert not hass.services.calls
        now[0]=1600
        await run(engine,room,profile,now)
        assert any(a=="set_temperature" for _,a,_,_ in hass.services.calls)
        assert all(a!="set_hvac_mode" for _,a,_,_ in hass.services.calls)
        hass.states.get("climate.living_thermostat").attributes["temperature"]=14
        now[0]=1900
        await run(engine,room,profile,now)
        assert engine.statuses["living"]["status"]=="paused"
        assert engine._paused["living"]=="manual_thermostat_override"
        await engine.async_stop()
    asyncio.run(scenario())


def test_unknown_occupancy_does_not_force_away_setback(env_runtime):
    async def scenario():
        hass,room=home(occupied="unavailable",at_home="unavailable")
        now=[1000.0]
        engine=env_runtime(hass,"presence",changed=lambda:None,clock=lambda:now[0])
        await engine.async_start()
        profile=conf()
        effective,room_presence,house=engine._profile("living",profile,1600)
        assert (effective,room_presence,house)==("home","unknown","unknown")
        await engine.async_stop()
    asyncio.run(scenario())


def test_away_requires_all_home_trackers_absent_and_hold_time(env_runtime):
    async def scenario():
        hass,room=home(occupied="off",at_home="not_home")
        now=[1000.0]
        engine=env_runtime(hass,"away",changed=lambda:None,clock=lambda:now[0])
        await engine.async_start()
        profile=conf(vacancy_delay_seconds=300,away_delay_seconds=900)
        assert engine._profile("living",profile,1500)[0]=="home"
        assert engine._profile("living",profile,1900)[0]=="unoccupied"
        assert engine._profile("living",profile,2401)[0]=="away"
        await engine.async_stop()
    asyncio.run(scenario())


def test_onoff_switch_minimum_off_and_safe_window_stop(env_runtime):
    async def scenario():
        hass,room=home(with_relay=True,temp=18)
        now=[1000.]
        engine=env_runtime(hass,"relay",changed=lambda:None,clock=lambda:now[0])
        await engine.async_start()
        profile=conf(strategy="on_off",relay_hardware_confirmed=True,
                     heat_entity="switch.living_heat",climate_entity=None)
        now[0]=1600
        await run(engine,room,profile,now)
        assert hass.states.get("switch.living_heat").state=="off"
        now[0]=1920
        await run(engine,room,profile,now)
        assert hass.states.get("switch.living_heat").state=="on"
        open_room=Room("living","Living",(Window("binary_sensor.window","Window",True),),())
        now[0]=2200
        await run(engine,open_room,profile,now)
        assert hass.states.get("switch.living_heat").state=="off"
        assert engine.statuses["living"]["status"]=="window_open_or_unknown"
        await engine.async_stop()
    asyncio.run(scenario())


def test_auto_hvac_mode_requires_permission_and_capability(env_runtime):
    async def scenario():
        hass,room=home(mode="heat",temp=29)
        now=[1000.]
        engine=env_runtime(hass,"auto",changed=lambda:None,clock=lambda:now[0])
        await engine.async_start()
        profile=conf(operation="auto",allow_hvac_mode_change=True)
        now[0]=1600
        await run(engine,room,profile,now)
        assert ("climate","set_hvac_mode") in [(d,a) for d,a,*_ in hass.services.calls]
        assert hass.states.get("climate.living_thermostat").state=="cool"
        assert all(c[1]!="set_temperature" for c in hass.services.calls)
        await engine.async_stop()
    asyncio.run(scenario())


def test_relay_pwm_rejects_missing_hardware_confirmation(env_runtime):
    async def scenario():
        hass,room=home(with_relay=True,temp=18)
        now=[1000.]
        engine=env_runtime(hass,"pwm",changed=lambda:None,clock=lambda:now[0])
        await engine.async_start()
        profile=conf(strategy="pwm",heat_entity="switch.living_heat",climate_entity=None,
                     relay_hardware_confirmed=True,pwm_hardware_confirmed=False)
        now[0]=1600
        await run(engine,room,profile,now)
        assert engine.statuses["living"]["status"]=="invalid_configuration"
        assert not hass.services.calls
        await engine.async_stop()
    asyncio.run(scenario())


def test_service_failure_sticks_pause_and_no_repeat(env_runtime):
    async def scenario():
        hass,room=home()
        hass.services.fail=True
        now=[1000.]
        engine=env_runtime(hass,"fail",changed=lambda:None,clock=lambda:now[0])
        await engine.async_start()
        profile=conf()
        now[0]=1600
        await run(engine,room,profile,now)
        assert engine._paused.get("living")=="climate_service_failure"
        now[0]=2500
        await run(engine,room,profile,now)
        assert engine.statuses["living"]["status"]=="paused"
        await engine.async_stop()
    asyncio.run(scenario())


def test_duplicate_target_fails_closed(env_runtime):
    async def scenario():
        hass,room=home()
        now=[1000.]
        engine=env_runtime(hass,"dup",changed=lambda:None,clock=lambda:now[0])
        await engine.async_start()
        other=Room("other","Other",(Window("binary_sensor.other","Window",False),),())
        settings={"living":conf(),"other":conf()}
        engine.schedule((room,other),settings)
        assert engine.statuses["living"]["status"]=="target_conflict"
        assert engine.statuses["other"]["status"]=="target_conflict"
        assert not hass.services.calls
        await engine.async_stop()
    asyncio.run(scenario())
