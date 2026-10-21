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
            "climate_entity":"climate.room_thermostat",
            "temperature_entity":"sensor.room_temperature",**changes}


def report(mode="heat",target=22,status="ready"):
    return {"status":status,"mode":mode,"temperature_target_c":target,
            "window_safe":True,"temperature_c":20.0}


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

def test_device_without_declared_hardware_limits_fails_closed(native):
    async def scenario():
        hass,_=fake_home()
        s=hass.states.get("climate.room_thermostat")
        s.attributes["hvac_modes"]=["off","heat","cool"]
        del s.attributes["min_temp"]
        clock=[1000.]
        c=native.NativeClimateControl(hass,"invalidlimits",clock=lambda:clock[0])
        await c.async_start()
        clock[0]=1400
        await scheduled(c,settings(),report())
        assert c.statuses["living"]["status"]=="device_limits_unknown"
        assert not hass.services.calls
        await c.async_stop()
    asyncio.run(scenario())

def test_native_heat_cool_range_uses_both_targets_and_preserves_mode(native):
    async def scenario():
        hass,_=fake_home(hvac="heat_cool")
        thermostat=hass.states.get("climate.room_thermostat")
        thermostat.attributes.update({
            "hvac_modes":["off","heat_cool"],"supported_features":2,
            "target_temp_low":18.0,"target_temp_high":28.0,
            "temperature_unit":"°C","min_temp":7,"max_temp":30,
            "target_temp_step":0.5,
        })
        async def send(domain,action,data,**kwargs):
            hass.services.calls.append((domain,action,data,kwargs))
            assert (domain,action)==("climate","set_temperature")
            assert "temperature" not in data
            thermostat.attributes["target_temp_low"]=data["target_temp_low"]
            thermostat.attributes["target_temp_high"]=data["target_temp_high"]
        hass.services.async_call=send
        clock=[1000.]
        manager=native.NativeClimateControl(hass,"range",clock=lambda:clock[0])
        await manager.async_start()
        clock[0]=1400.
        target={"status":"ready","mode":"heat_cool","window_safe":True,
                "low_target_c":20.0,"high_target_c":26.0}
        await scheduled(manager,settings(),target)
        assert len(hass.services.calls)==1
        call=hass.services.calls[0]
        assert call[2]=={"target_temp_low":18.5,"target_temp_high":27.5}
        assert thermostat.state=="heat_cool"  # no mode switch or compressor call
        assert manager.statuses["living"]["status"]=="native_range_commanded"
        clock[0]=1800.
        await scheduled(manager,settings(),target)
        assert len(hass.services.calls)==2
        assert hass.services.calls[-1][2]["target_temp_low"]==19.0
        assert hass.services.calls[-1][2]["target_temp_high"]==27.0
        thermostat.attributes["target_temp_low"]=23.5
        clock[0]=2200.
        await scheduled(manager,settings(),target)
        assert manager.paused["living"]=="manual_native_range_change"
        await manager.async_stop()
    asyncio.run(scenario())


def test_heat_cool_range_rejects_unsupported_single_target_mode(native):
    async def scenario():
        hass,_=fake_home(hvac="heat_cool")
        thermostat=hass.states.get("climate.room_thermostat")
        thermostat.attributes.update({
            "hvac_modes":["off","heat_cool"],"supported_features":1,
            "target_temp_low":18.0,"target_temp_high":28.0,
        })
        clock=[1000.]
        controller=native.NativeClimateControl(hass,"unsupported_range",clock=lambda:clock[0])
        await controller.async_start()
        clock[0]=1400
        await scheduled(controller,settings(),{
            "status":"ready","mode":"heat_cool","window_safe":True,
            "low_target_c":20,"high_target_c":26,
        })
        assert controller.statuses["living"]["status"]=="native_range_not_supported"
        assert not hass.services.calls
        await controller.async_stop()
    asyncio.run(scenario())

def test_native_range_respects_manual_change_from_previous_heat_mode(native):
    async def scenario():
        hass,_=fake_home(hvac="heat_cool")
        target=hass.states.get("climate.room_thermostat")
        target.attributes.update({
            "hvac_modes":["off","heat_cool"],"supported_features":2,
            "target_temp_low":18.0,"target_temp_high":28.0,
        })
        clock=[1000.]
        controller=native.NativeClimateControl(hass,"manual_mode_range",clock=lambda:clock[0])
        await controller.async_start()
        controller.expected_hvac["living"]="heat"
        clock[0]=2000.
        await scheduled(controller,settings(),{
            "status":"ready","mode":"heat_cool","window_safe":True,
            "low_target_c":20,"high_target_c":26,
        })
        assert controller.paused["living"]=="manual_hvac_mode_change"
        assert not hass.services.calls
        await controller.async_stop()
    asyncio.run(scenario())


def test_native_never_writes_to_cross_room_thermostat(native):
    async def scenario():
        hass,_=fake_home()
        hass._entity_areas["climate.room_thermostat"]="kitchen"
        clock=[1000.]
        c=native.NativeClimateControl(hass,"wrong-room",clock=lambda:clock[0])
        await c.async_start()
        clock[0]=1400
        await scheduled(c,settings(),report())
        assert c.statuses["living"]["status"]=="climate_target_wrong_room"
        assert not hass.services.calls
        await c.async_stop()
    asyncio.run(scenario())


def test_native_rechecks_window_contacts_after_plan_capture(native):
    async def scenario():
        hass,_=fake_home()
        from test_discovery import MockState
        contact=MockState("binary_sensor.living_window","on",device_class="window")
        hass._values[contact.entity_id]=contact
        hass._entity_areas[contact.entity_id]="living"
        clock=[1000.]
        c=native.NativeClimateControl(hass,"window-race",clock=lambda:clock[0])
        await c.async_start()
        clock[0]=1400
        plan={**report(),"window_contacts":[contact.entity_id]}
        await scheduled(c,settings(),plan)
        assert c.statuses["living"]["status"]=="window_changed_since_plan"
        assert not hass.services.calls
        await c.async_stop()
    asyncio.run(scenario())


def test_native_refuses_armed_opposing_secondary_climate(native):
    async def scenario():
        hass,_=fake_home()
        hass.states.get("climate.room_thermostat").attributes["hvac_modes"]=["off","heat","cool"]
        from test_discovery import MockState
        other=MockState("climate.ac","cool")
        other.attributes["hvac_action"]="idle"
        hass._values[other.entity_id]=other
        hass._entity_areas[other.entity_id]="living"
        clock=[1000.]
        c=native.NativeClimateControl(hass,"other-armed",clock=lambda:clock[0])
        await c.async_start()
        clock[0]=1400
        await scheduled(c,settings(cool_climate_entity=other.entity_id),report("heat"))
        assert c.statuses["living"]["status"]=="competing_climate_active_or_armed"
        assert not hass.services.calls
        other.state="off"
        await scheduled(c,settings(cool_climate_entity=other.entity_id),report("heat"))
        assert len(hass.services.calls)==1
        await c.async_stop()
    asyncio.run(scenario())


def test_unified_room_gate_rechecks_opposing_ac_after_plan_was_approved(native):
    async def scenario():
        from custom_components.air_quality_advisor.climate_arbitration import (
            room_coordination,
        )
        from test_discovery import MockState
        hass,_=fake_home()
        primary=hass.states.get("climate.room_thermostat")
        primary.attributes["hvac_modes"]=["off","heat","cool"]
        ac=MockState("climate.room_ac","off")
        ac.attributes.update({
            "hvac_modes":["off","cool"],"supported_features":1,
            "hvac_action":"idle",
        })
        hass._values[ac.entity_id]=ac
        hass._entity_areas[ac.entity_id]="living"
        cfg=settings(cool_climate_entity=ac.entity_id)
        plan_=report()
        plan_["equipment_plan"]={
            "status":"ready",
            "thermal":{"status":"selected","entity_id":primary.entity_id,
                       "role":"climate_entity","mode":"heat"},
            "moisture":{"status":"within_band"},
        }
        clock=[1000.]
        controller=native.NativeClimateControl(
            hass,"coordinated",clock=lambda:clock[0],
        )
        await controller.async_start()
        clock[0]=1400
        plan_["coordination"]=room_coordination(
            hass,"living",cfg,plan_,now=1400,
        )
        assert plan_["coordination"]["channels"]["thermal"]["status"]=="eligible"
        ac.state="cool"  # AC armed AFTER room planning but before command.
        await scheduled(controller,cfg,plan_)
        assert controller.statuses["living"]=={
            "status":"coordination_hold","reason":"opposing_native_mode_armed",
        }
        assert not hass.services.calls
        ac.state="off"
        await scheduled(controller,cfg,plan_)
        assert hass.services.calls[0][1]=="set_temperature"
        await controller.async_stop()
    asyncio.run(scenario())
