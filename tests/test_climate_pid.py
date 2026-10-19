"""Mocked climate service contract; never power-cycle HVAC or overwrite manual actions."""
import asyncio
import sys
import types
from types import SimpleNamespace

import pytest
from custom_components.air_quality_advisor.pid_math import DEFAULT_PID
from custom_components.air_quality_advisor.logic import Room, Window
from test_discovery import MockState, FakeHass, adapter


class FakeStore:
    def __init__(self,*_):
        self.data=None
    async def async_load(self):
        return self.data
    async def async_save(self,value):
        self.data=value
    def async_delay_save(self,callback,delay):
        self.data=callback()


class Services:
    def __init__(self,hass):
        self.hass=hass
        self.calls=[]
        self.ack=True
        self.fail=False
    def has_service(self,domain,action):
        return (domain,action)==("climate","set_temperature")
    async def async_call(self,domain,action,data,**kwargs):
        self.calls.append((domain,action,data,kwargs))
        if self.fail:
            raise RuntimeError("climate integration offline")
        if self.ack:
            self.hass.states.get(kwargs["target"]["entity_id"]).attributes["temperature"]=data["temperature"]


def fake_home(*,temp_age=0,hvac="heat",window_open=False,ready=True):
    air=MockState("sensor.room_temperature",20,device_class="temperature",unit="°C",hours_old=temp_age)
    climate=MockState("climate.room_thermostat",hvac)
    climate.attributes.update({"supported_features":1,"temperature_unit":"°C",
        "temperature":20,"min_temp":7,"max_temp":30,"target_temp_step":0.5})
    hass=FakeHass([air,climate],{"sensor.room_temperature":"living",
                               "climate.room_thermostat":"living"})
    hass.services=Services(hass)
    hass.async_create_task=asyncio.create_task
    room=Room("living","Living",(Window("binary_sensor.window","Window",window_open),),())
    return hass,room


def config(**changes):
    return {**DEFAULT_PID,"enabled":True,"target_c":23,"temperature_entity":"sensor.room_temperature",
            "climate_entities":["climate.room_thermostat"],**changes}


@pytest.fixture
def pid_store(monkeypatch):
    store=types.ModuleType("homeassistant.helpers.storage")
    store.Store=FakeStore
    monkeypatch.setitem(sys.modules,"homeassistant.helpers.storage",store)
    import importlib
    controller=importlib.import_module("custom_components.air_quality_advisor.climate_pid")
    store.Coordinator=controller.ClimatePidCoordinator
    return store


async def tick(engine,room,profile,clock):
    engine.schedule((room,),{"living":profile})
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    await asyncio.sleep(0)


def test_disabled_climate_never_calls_home_assistant(adapter,pid_store):
    async def scenario():
        hass,room=fake_home()
        clock=[1000.0]
        engine=pid_store.Coordinator(hass,"e",report_changed=lambda:None,clock=lambda:clock[0])
        await engine.async_start()
        engine.schedule((room,),{"living":{**config(),"enabled":False}})
        assert engine.statuses["living"]["status"]=="disabled"
        assert hass.services.calls==[]
        await engine.async_stop()
    asyncio.run(scenario())


def test_pid_controls_setpoint_and_latches_manual_override(adapter,pid_store):
    async def scenario():
        hass,room=fake_home()
        clock=[1000.0]
        changes=[]
        engine=pid_store.Coordinator(hass,"e",report_changed=lambda:changes.append(1),clock=lambda:clock[0])
        await engine.async_start()
        profile=config()
        engine.schedule((room,),{"living":profile},initial=True)
        assert hass.services.calls==[]
        clock[0]=1600
        await tick(engine,room,profile,clock)
        assert hass.services.calls==[]   # wait first fully observed PID interval
        clock[0]=1900
        await tick(engine,room,profile,clock)
        assert len(hass.services.calls)==1
        domain, action, data, kwargs=hass.services.calls[0]
        assert (domain,action)==("climate","set_temperature")
        assert "hvac_mode" not in data
        assert kwargs["target"]=={"entity_id":"climate.room_thermostat"}
        assert data["temperature"]==20.5  # hard max 0.5 C change per cycle
        assert engine.statuses["living"]["status"]=="controlling"
        # A person changes their physical thermostat: the PID must stop.
        hass.states.get("climate.room_thermostat").attributes["temperature"]=19
        clock[0]=2200
        await tick(engine,room,profile,clock)
        assert engine.statuses["living"]["status"]=="paused"
        assert engine._paused["living"]=="manual_temperature_change_or_unacknowledged_write"
        assert len(hass.services.calls)==1
        # Explicit action is required to clear the persistent latch.
        assert (await engine.async_action("living","resume",{"living":profile}))["accepted"]
        assert "living" not in engine._paused
        await engine.async_stop()
    asyncio.run(scenario())


def test_unsafe_windows_unknown_temperature_and_off_modes_never_call(adapter,pid_store):
    async def scenario(temp_age,hvac,window):
        hass,room=fake_home(temp_age=temp_age,hvac=hvac,window_open=window)
        clock=[1000.]
        engine=pid_store.Coordinator(hass,"e",report_changed=lambda:None,clock=lambda:clock[0])
        await engine.async_start()
        clock[0]=1600
        await tick(engine,room,config(),clock)
        assert hass.services.calls==[]
        assert engine.statuses["living"]["status"] in (
            "window_open_or_unknown","temperature_unavailable_or_stale","paused")
        await engine.async_stop()
    asyncio.run(scenario(0,"heat",True))
    asyncio.run(scenario(5,"heat",False))
    asyncio.run(scenario(0,"off",False))


def test_expected_targets_are_restored_after_restart(adapter,pid_store):
    async def scenario():
        hass,room=fake_home()
        clock=[1000.]
        store=FakeStore()
        store.data={"version":1,"paused":{"living":"manual_hvac_mode_change"},
                    "expected":{"living":{"climate.room_thermostat":{"value":21,"when":800}}}}
        pid_store.Store=lambda *_:store
        engine=pid_store.Coordinator(hass,"x",report_changed=lambda:None,clock=lambda:clock[0])
        await engine.async_start()
        assert engine._paused["living"]=="manual_hvac_mode_change"
        clock[0]=2000
        await tick(engine,room,config(),clock)
        assert hass.services.calls==[]
        await engine.async_stop()
    asyncio.run(scenario())


def test_duplicate_climate_target_across_rooms_is_refused(adapter,pid_store):
    async def scenario():
        hass,room=fake_home()
        clock=[1000.]
        engine=pid_store.Coordinator(hass,"e",report_changed=lambda:None,clock=lambda:clock[0])
        await engine.async_start()
        second=Room("other","Other",(Window("binary_sensor.o","Other window",False),),())
        both={"living":config(),"other":config()}
        engine.schedule((room,second),both)
        assert engine.statuses["living"]["status"]=="duplicate_target"
        assert engine.statuses["other"]["status"]=="duplicate_target"
        assert not hass.services.calls
        await engine.async_stop()
    asyncio.run(scenario())

def test_climate_service_failure_latches_pause_and_does_not_retry(adapter,pid_store):
    async def scenario():
        hass,room=fake_home()
        clock=[1000.]
        engine=pid_store.Coordinator(hass,"failure",report_changed=lambda:None,clock=lambda:clock[0])
        await engine.async_start()
        profile=config()
        clock[0]=1600
        await tick(engine,room,profile,clock)
        assert not hass.services.calls
        hass.services.fail=True
        clock[0]=1900
        await tick(engine,room,profile,clock)
        assert engine._paused["living"]=="climate_service_failure"
        assert engine.statuses["living"]["status"]=="paused"
        assert len(hass.services.calls)==1
        clock[0]=2500
        await tick(engine,room,profile,clock)
        assert len(hass.services.calls)==1
        await engine.async_stop()
    asyncio.run(scenario())


def test_manual_pause_always_blocks_future_device_writes(adapter,pid_store):
    async def scenario():
        hass,room=fake_home()
        clock=[1000.]
        engine=pid_store.Coordinator(hass,"pause",report_changed=lambda:None,clock=lambda:clock[0])
        await engine.async_start()
        conf=config()
        assert (await engine.async_action("living","pause",{"living":conf}))["accepted"]
        clock[0]=4000
        await tick(engine,room,conf,clock)
        assert engine.statuses["living"]["status"]=="paused"
        assert not hass.services.calls
        await engine.async_stop()
    asyncio.run(scenario())
