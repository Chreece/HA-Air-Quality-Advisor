"""Already-running separate AC/radiator controls: never energize HVAC."""
import asyncio
import importlib
import sys
import types
from datetime import datetime, timezone

import pytest
from test_discovery import FakeHass, MockState, adapter
from test_climate_pid import FakeStore


@pytest.fixture
def secondary(adapter, monkeypatch):
    storage=types.ModuleType("homeassistant.helpers.storage")
    storage.Store=FakeStore
    monkeypatch.setitem(sys.modules,"homeassistant.helpers.storage",storage)
    return importlib.import_module(
        "custom_components.air_quality_advisor.climate_secondary_native")


class Services:
    def __init__(self, hass):
        self.hass=hass
        self.calls=[]
        self.fail=False
        self.ack=True
    def has_service(self, domain, service):
        return (domain,service)==("climate","set_temperature")
    async def async_call(self, domain, service, data, **kwargs):
        self.calls.append((domain,service,data,kwargs))
        if self.fail:
            raise RuntimeError("climate integration failed")
        if self.ack:
            self.hass.states.get(kwargs["target"]["entity_id"]).attributes[
                "temperature"]=data["temperature"]


def system(*, primary="off", secondary_state="cool", window=None,
           sensor_age=0, secondary_features=1, outside_area=False):
    sensor=MockState("sensor.lounge_temperature",28,device_class="temperature",
                     unit="°C", hours_old=sensor_age)
    main=MockState("climate.radiator",primary)
    main.attributes.update({"hvac_modes":["off","heat"],"supported_features":1,
                            "hvac_action":"idle"})
    ac=MockState("climate.ac",secondary_state)
    ac.attributes.update({"hvac_modes":["off","cool","dry","fan_only"],
                          "supported_features":secondary_features,"temperature":24.0,
                          "temperature_unit":"°C","target_temp_step":0.5,
                          "min_temp":16.0,"max_temp":32.0,"hvac_action":"idle"})
    entities=[sensor,main,ac]
    if window is not None:
        win=MockState("binary_sensor.lounge_window",window,device_class="window")
        entities.append(win)
    areas={st.entity_id:"lounge" for st in entities}
    if outside_area:
        areas["climate.ac"]="kitchen"
    hass=FakeHass(entities,areas)
    hass.services=Services(hass)
    hass.async_create_task=asyncio.create_task
    return hass


def config(**changes):
    return {"enabled":True,"controller":"device","allow_actuation":True,
            "secondary_climate_setpoint_auto":True,
            "climate_entity":"climate.radiator",
            "cool_climate_entity":"climate.ac",
            "temperature_entity":"sensor.lounge_temperature",**changes}


def plan(*, target=26.0, windows=None):
    return {"status":"hold","reason":"secondary_thermal_driver_pending",
            "window_safe":True,"window_contacts":windows or [],
            "mode":"cool","temperature_target_c":target,
            "equipment_plan":{"status":"ready","thermal":{
                "status":"selected","mode":"cool","role":"cool_climate_entity",
                "entity_id":"climate.ac"}}}


async def tick(c, room_config, report, *, pid=None):
    c.schedule({"lounge":room_config},{"lounge":report},
               pid_rooms=pid or {})
    for _ in range(6):
        await asyncio.sleep(0)


def test_opt_in_and_valid_cooling_climate_setpoint_only(secondary):
    async def run():
        h=system()
        clk=[1000.0]
        c=secondary.SecondaryClimateSetpoint(h,"test",clock=lambda:clk[0])
        await c.async_start()
        clk[0]=1400
        await tick(c, config(secondary_climate_setpoint_auto=False),plan())
        assert h.services.calls==[]
        assert c.statuses["lounge"]["status"]=="advisory_only"
        await tick(c,config(),plan())
        assert len(h.services.calls)==1
        service=h.services.calls[0]
        assert service[:3]==("climate","set_temperature",{"temperature":24.5})
        assert service[3]["target"]=={"entity_id":"climate.ac"}
        assert c.expected["lounge"]["mode"]=="cool"
        assert c.statuses["lounge"]["status"]=="setpoint_commanded"
        await c.async_stop()
    asyncio.run(run())


def test_off_device_is_never_started_and_mode_cannot_be_switched(secondary):
    async def run():
        for mode,required in [
            ("off","thermostat_switched_off"),
            ("dry","native_mode_mismatch_no_mode_switch"),
            ("heat","native_mode_mismatch_no_mode_switch")
        ]:
            h=system(secondary_state=mode)
            clk=[1000.]
            c=secondary.SecondaryClimateSetpoint(h,"test",clock=lambda:clk[0])
            await c.async_start()
            clk[0]=1400
            await tick(c,config(),plan())
            assert c.statuses["lounge"]["status"] in (
                "paused","native_mode_mismatch_no_mode_switch")
            if mode=="off":
                assert c.paused["lounge"]==required
            assert h.services.calls==[]
            await c.async_stop()
    asyncio.run(run())


def test_opposing_native_mode_armed_blocks_secondary_cooling(secondary):
    async def run():
        h=system(primary="heat")
        clk=[1000.]
        c=secondary.SecondaryClimateSetpoint(h,"test",clock=lambda:clk[0])
        await c.async_start()
        clk[0]=1400
        await tick(c,config(),plan())
        assert c.statuses["lounge"]["status"]=="other_thermostat_opposing_mode_armed"
        assert not h.services.calls
        await c.async_stop()
    asyncio.run(run())


def test_stale_source_and_window_interlocks_prevent_commands(secondary):
    async def run():
        for h,config_,p,reason in [
            (system(sensor_age=24), config(), plan(), "temperature_stale_or_wrong_room"),
            (system(window="on"),config(),
             plan(windows=["binary_sensor.lounge_window"]),"window_open_or_unavailable"),
            (system(window="unavailable"),config(),
             plan(windows=["binary_sensor.lounge_window"]),"window_open_or_unavailable"),
            (system(outside_area=True),config(),plan(),"secondary_device_unavailable_or_unsupported"),
            (system(secondary_features=0),config(),plan(),"secondary_device_unavailable_or_unsupported"),
        ]:
            clk=[1000.]
            c=secondary.SecondaryClimateSetpoint(h,"test",clock=lambda:clk[0])
            await c.async_start()
            clk[0]=1400
            await tick(c,config_,p)
            assert c.statuses["lounge"]["status"]==reason
            assert not h.services.calls
            await c.async_stop()
    asyncio.run(run())


def test_setpoint_manual_override_pauses_persistently(secondary):
    async def run():
        h=system()
        clk=[1000.]
        c=secondary.SecondaryClimateSetpoint(h,"test",clock=lambda:clk[0])
        await c.async_start()
        clk[0]=1400
        await tick(c,config(),plan())
        assert len(h.services.calls)==1
        h.states.get("climate.ac").attributes["temperature"]=29.0
        clk[0]=1800
        await tick(c,config(),plan())
        assert c.paused["lounge"]=="manual_setpoint_or_missing_ack"
        assert len(h.services.calls)==1
        assert c.expected["lounge"]["target"]==24.5
        assert (await c.command("lounge","resume"))["accepted"]
        assert "lounge" not in c.paused
        await c.async_stop()
    asyncio.run(run())


def test_duplicate_pid_owner_and_write_error_fail_closed(secondary):
    async def run():
        h=system()
        clk=[1000.]
        c=secondary.SecondaryClimateSetpoint(h,"test",clock=lambda:clk[0])
        await c.async_start()
        clk[0]=1400
        await tick(c,config(),plan(),pid={"other":{"enabled":True,
                         "climate_entities":["climate.ac"]}})
        assert c.statuses["lounge"]["status"]=="conflicting_controller_or_equipment_owner"
        assert not h.services.calls
        h.services.fail=True
        await tick(c,config(),plan())
        assert c.paused["lounge"]=="climate_setpoint_write_failed"
        assert len(h.services.calls)==1
        await c.async_stop()
    asyncio.run(run())


def test_restart_latches_secondary_manual_changes_without_reenergizing(secondary):

    class PersistedStore(FakeStore):
        records={}
        def __init__(self,*args):
            super().__init__(*args)
            self.key=args[-1]
        async def async_load(self):
            return self.records.get(self.key)
        async def async_save(self,value):
            self.records[self.key]=value
        def async_delay_save(self,callback,delay):
            self.records[self.key]=callback()

    sys.modules["homeassistant.helpers.storage"].Store=PersistedStore

    async def scenario():
        h=system()
        clk=[1000.0]
        first=secondary.SecondaryClimateSetpoint(h,"restart",clock=lambda:clk[0])
        await first.async_start()
        clk[0]=1400
        await tick(first,config(),plan())
        assert first.expected["lounge"]["target"]==24.5
        await first.async_stop()

        # An operator changed a previously commanded target while HA was down.
        h.states.get("climate.ac").attributes["temperature"]=29
        second=secondary.SecondaryClimateSetpoint(h,"restart",clock=lambda:clk[0])
        await second.async_start()
        assert second.expected["lounge"]["target"]==24.5
        clk[0]=2000
        await tick(second,config(),plan())
        assert second.paused["lounge"]=="manual_setpoint_or_missing_ack"
        assert len(h.services.calls)==1
        await second.async_stop()
    asyncio.run(scenario())
