"""Native thermostat actuation requires explicit authority and physical safety."""
import asyncio
import importlib
import sys
import types

import pytest
from test_climate_pid import FakeStore, fake_home
from test_discovery import adapter


@pytest.fixture
def native(adapter,monkeypatch):
    storage=types.ModuleType("homeassistant.helpers.storage")
    storage.Store=FakeStore
    monkeypatch.setitem(sys.modules,"homeassistant.helpers.storage",storage)
    return importlib.import_module("custom_components.air_quality_advisor.climate_native")


def settings(**changes):
    return {"enabled":True,"controller":"device",
            "allow_actuation":True,"auto_switch_hvac":False,
            "climate_entity":"climate.room_thermostat",**changes}


def report(mode="heat",target=22,status="ready"):
    return {"status":status,"mode":mode,"temperature_target_c":target}


async def scheduled(ctrl,settings_,plan):
    ctrl.schedule({"living":settings_},{"living":plan})
    for _ in range(4):await asyncio.sleep(0)


def test_native_default_does_not_send_any_commands(native):
    async def scenario():
        hass,room=fake_home()
        hass.states.get("climate.room_thermostat").attributes["hvac_modes"]=["off","heat","cool"]
        clock=[1000.]
        c=native.NativeClimateControl(hass,"x",clock=lambda:clock[0])
        await c.async_start()
        clock[0]=4000
        await scheduled(c,{**settings(),"allow_actuation":False},report())
        assert not hass.services.calls
        assert c.statuses["living"]["status"]=="advisory_only"
        await c.async_stop()
    asyncio.run(scenario())


def test_heat_target_rate_limit_and_manual_pause(native):
    async def scenario():
        hass,_=fake_home()
        st=hass.states.get("climate.room_thermostat")
        st.attributes["hvac_modes"]=["off","heat","cool"]
        clock=[1000.]
        c=native.NativeClimateControl(hass,"x",clock=lambda:clock[0])
        await c.async_start()
        clock[0]=1400
        await scheduled(c,settings(),report())
        assert len(hass.services.calls)==1
        assert hass.services.calls[0][1]=="set_temperature"
        assert hass.services.calls[0][2]["temperature"]==20.5
        clock[0]=1800
        st.attributes["temperature"]=25
        await scheduled(c,settings(),report())
        assert c.paused["living"]=="manual_setpoint_or_unacknowledged_write"
        assert len(hass.services.calls)==1
        assert (await c.command("living","resume"))["accepted"]
        assert "living" not in c.paused
        await c.async_stop()
    asyncio.run(scenario())


def test_device_off_is_never_started_automatically(native):
    async def scenario():
        hass,_=fake_home(hvac="off")
        st=hass.states.get("climate.room_thermostat")
        st.attributes["hvac_modes"]=["off","heat","cool"]
        clock=[1000.]
        c=native.NativeClimateControl(hass,"x",clock=lambda:clock[0])
        await c.async_start()
        clock[0]=3000
        await scheduled(c,settings(auto_switch_hvac=True),report("heat"))
        assert c.paused["living"]=="thermostat_turned_off"
        assert not hass.services.calls
        await c.async_stop()
    asyncio.run(scenario())


def test_heat_to_cool_requires_optin_and_mode_dwell(native):
    async def scenario():
        hass,_=fake_home(hvac="heat")
        st=hass.states.get("climate.room_thermostat")
        st.attributes["hvac_modes"]=["off","heat","cool"]
        clock=[1000.]
        c=native.NativeClimateControl(hass,"x",clock=lambda:clock[0])
        await c.async_start()
        clock[0]=4000
        await scheduled(c,settings(auto_switch_hvac=False),report("cool",25))
        assert not hass.services.calls
        clock[0]=4200
        hass.services.has_service=lambda domain,action: domain=="climate" and action in ("set_temperature","set_hvac_mode")
        await scheduled(c,settings(auto_switch_hvac=True),report("cool",25))
        assert hass.services.calls[0][1]=="set_hvac_mode"
        assert hass.services.calls[0][2]["hvac_mode"]=="cool"
        assert all("temperature" not in call[2] for call in hass.services.calls)
        await c.async_stop()
    asyncio.run(scenario())


def test_conflicting_pid_owner_never_commands_native(native):
    async def scenario():
        hass,_=fake_home()
        clock=[1000.]
        c=native.NativeClimateControl(hass,"x",clock=lambda:clock[0])
        await c.async_start()
        clock[0]=4000
        c.schedule({"living":settings()},{"living":report()},
                   pid_rooms={"living":{"enabled":True}})
        assert c.statuses["living"]["status"]=="conflicting_controller"
        assert not hass.services.calls
        await c.async_stop()
    asyncio.run(scenario())
