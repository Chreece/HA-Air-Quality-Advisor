"""Native DRY/FAN_ONLY mode control: no compressor powers or fake capabilities."""
import asyncio
import importlib
import sys
import types
from datetime import datetime,timezone

import pytest

from test_climate_pid import FakeStore
from test_discovery import FakeHass,MockState,adapter


@pytest.fixture
def mode_module(adapter,monkeypatch):
    storage=types.ModuleType("homeassistant.helpers.storage")
    storage.Store=FakeStore
    monkeypatch.setitem(sys.modules,"homeassistant.helpers.storage",storage)
    return importlib.import_module(
        "custom_components.air_quality_advisor.climate_air_mode_native"
    )


class Services:
    def __init__(self,hass,clock):
        self.hass=hass
        self.clock=clock
        self.calls=[]
        self.fail=False
        self.ack=True

    def has_service(self,domain,service):
        return (domain,service)==("climate","set_hvac_mode")

    async def async_call(self,domain,service,data,**kwargs):
        self.calls.append((domain,service,data,kwargs))
        if self.fail:
            raise RuntimeError("simulated AC driver failure")
        if self.ack:
            entity=kwargs["target"]["entity_id"]
            self.hass.states.get(entity).state=data["hvac_mode"]
            self.hass.states.get(entity).last_changed=datetime.fromtimestamp(
                self.clock[0],timezone.utc,
            )


def system(*,mode="fan_only",rh=76,hvac_action="fan",
           hvac_modes=None,include_window=True):
    ac=MockState("climate.bedroom_ac",mode)
    ac.attributes.update({
        "hvac_modes":hvac_modes or ["off","dry","fan_only"],
        "supported_features":0,
        "hvac_action":hvac_action,
    })
    ac.last_changed=datetime.fromtimestamp(1000,timezone.utc)
    sensor=MockState("sensor.bedroom_rh",rh,device_class="humidity",unit="%")
    states=[ac,sensor]
    if include_window:
        states.append(MockState("binary_sensor.bedroom_window","off",
                                device_class="window"))
    h=FakeHass(states,{s.entity_id:"bedroom" for s in states})
    clock=[1000.]
    h.services=Services(h,clock)
    h.async_create_task=asyncio.create_task
    return h,clock


def cfg(**overrides):
    return {
        "enabled":True,"allow_actuation":True,
        "controller":"environment",
        "dry_climate_entity":"climate.bedroom_ac",
        "dry_fan_mode_auto":True,
        "dry_fan_hardware_confirmed":True,
        "dry_fan_windowless_confirmed":False,
        "dry_fan_mode_dwell_s":1800,
        "humidity_entity":"sensor.bedroom_rh",
        "humidity_low_rh":40,
        "humidity_high_rh":60,
        "humidity_hysteresis_rh":3,
        **overrides,
    }


def plan(hass,settings,*,include_window=True):
    from custom_components.air_quality_advisor.climate_coordination import (
        room_equipment_plan,
    )
    from custom_components.air_quality_advisor.logic import Reading
    rh=float(hass.states.get("sensor.bedroom_rh").state)
    base={"status":"advisory","mode":None,"window_safe":True,
          "window_contacts":(["binary_sensor.bedroom_window"]
                             if include_window else [])}
    base["equipment_plan"]=room_equipment_plan(
        hass,"bedroom",settings,base,
        (Reading("sensor.bedroom_rh","Humidity","humidity",rh),),
    )
    return base


async def tick(controller,config,report):
    controller.schedule({"bedroom":config},{"bedroom":report})
    for _ in range(10):
        await asyncio.sleep(0)


def test_default_disabled_and_unattested_are_never_actuated(mode_module):
    async def case():
        hass,clock=system()
        driver=mode_module.NativeAirModeControl(
            hass,"disabled",clock=lambda:clock[0])
        await driver.async_start()
        clock[0]=5000
        await tick(driver,cfg(dry_fan_mode_auto=False),plan(hass,cfg()))
        await tick(driver,cfg(dry_fan_hardware_confirmed=False),plan(hass,cfg()))
        assert not hass.services.calls
        assert driver.statuses["bedroom"]["status"]=="advisory_only"
        await driver.async_stop()
    asyncio.run(case())


def test_measured_humidity_switches_only_previously_running_fan_to_dry(mode_module):
    async def case():
        hass,clock=system()
        policy=cfg()
        driver=mode_module.NativeAirModeControl(hass,"modes",clock=lambda:clock[0])
        await driver.async_start()
        clock[0]=5000
        await tick(driver,policy,plan(hass,policy))
        assert hass.services.calls==[(
            "climate","set_hvac_mode",{"hvac_mode":"dry"},
            {"target":{"entity_id":"climate.bedroom_ac"},"blocking":True},
        )]
        assert driver.expected["bedroom"]["mode"]=="dry"
        assert driver.statuses["bedroom"]["status"]=="native_mode_commanded"
        # The compressor must become IDLE before returning to FAN_ONLY.
        hass.states.get("sensor.bedroom_rh").state="55"
        hass.states.get("climate.bedroom_ac").attributes["hvac_action"]="drying"
        clock[0]=7000
        await tick(driver,policy,plan(hass,policy))
        assert len(hass.services.calls)==1
        assert driver.statuses["bedroom"]["status"]=="active_compressor_wait_for_idle"
        hass.states.get("climate.bedroom_ac").attributes["hvac_action"]="idle"
        await tick(driver,policy,plan(hass,policy))
        assert [item[2]["hvac_mode"] for item in hass.services.calls]==[
            "dry","fan_only",
        ]
        assert all(item[0:2]==("climate","set_hvac_mode")
                   and item[3]["target"]=={"entity_id":"climate.bedroom_ac"}
                   for item in hass.services.calls)
        await driver.async_stop()
    asyncio.run(case())


def test_dry_only_unit_can_never_invent_fan_only_or_switch_to_off(mode_module):
    async def case():
        hass,clock=system(mode="dry",rh=55,hvac_action="idle",
                          hvac_modes=["dry"])
        driver=mode_module.NativeAirModeControl(
            hass,"dry-only",clock=lambda:clock[0])
        await driver.async_start()
        clock[0]=5000
        await tick(driver,cfg(),plan(hass,cfg()))
        assert not hass.services.calls
        assert driver.statuses["bedroom"]["status"]=="both_dry_and_fan_only_required"
        await driver.async_stop()
    asyncio.run(case())


def test_off_and_heat_cool_are_never_started_or_taken_over(mode_module):
    async def case():
        for mode in ("off","heat","cool","auto","heat_cool"):
            hass,clock=system(mode=mode)
            driver=mode_module.NativeAirModeControl(
                hass,mode,clock=lambda:clock[0])
            await driver.async_start()
            clock[0]=5000
            await tick(driver,cfg(),plan(hass,cfg()))
            assert not hass.services.calls,mode
            assert driver.statuses["bedroom"]["status"]=="unit_must_be_running_dry_or_fan_only"
            await driver.async_stop()
    asyncio.run(case())


def test_missing_window_contact_or_missing_current_sensor_hold(mode_module):
    async def case():
        hass,clock=system()
        driver=mode_module.NativeAirModeControl(
            hass,"safety",clock=lambda:clock[0])
        await driver.async_start()
        clock[0]=5000
        report=plan(hass,cfg())
        hass.states.get("binary_sensor.bedroom_window").state="on"
        await tick(driver,cfg(),report)
        assert driver.statuses["bedroom"]["status"]=="window_open_or_unknown"
        hass.states.get("binary_sensor.bedroom_window").state="off"
        hass.states.get("sensor.bedroom_rh").state="unavailable"
        await tick(driver,cfg(),report)
        assert driver.statuses["bedroom"]["status"]=="humidity_sensor_invalid_or_stale"
        assert not hass.services.calls
        await driver.async_stop()
    asyncio.run(case())


def test_compressor_dwell_manual_override_and_service_failure_latch(mode_module):
    async def case():
        hass,clock=system()
        policy=cfg()
        driver=mode_module.NativeAirModeControl(hass,"manual",clock=lambda:clock[0])
        await driver.async_start()
        clock[0]=2500
        await tick(driver,policy,plan(hass,policy))
        assert driver.statuses["bedroom"]["status"] in (
            "mode_dwell_not_met","native_mode_dwell_not_met",
        )
        assert not hass.services.calls
        clock[0]=5000
        hass.services.ack=False
        await tick(driver,policy,plan(hass,policy))
        assert len(hass.services.calls)==1
        clock[0]=5130
        await tick(driver,policy,plan(hass,policy))
        assert driver.paused["bedroom"]=="manual_mode_or_unacknowledged_write"
        assert len(hass.services.calls)==1
        assert (await driver.command("bedroom","resume"))["accepted"] is True
        hass.services.fail=True
        clock[0]=9000
        await tick(driver,policy,plan(hass,policy))
        assert driver.paused["bedroom"]=="native_mode_service_failure"
        assert len(hass.services.calls)==2
        await driver.async_stop()
    asyncio.run(case())


def test_competing_heating_unit_and_unaudited_humidity_outputs_hold(mode_module):
    async def case():
        hass,clock=system()
        heater=MockState("climate.other_heater","heat")
        heater.attributes.update({"hvac_modes":["off","heat"],
                                  "hvac_action":"idle","supported_features":1})
        hass._values[heater.entity_id]=heater
        hass._entity_areas[heater.entity_id]="bedroom"
        policy=cfg(heat_climate_entity=heater.entity_id)
        driver=mode_module.NativeAirModeControl(
            hass,"other-device",clock=lambda:clock[0])
        await driver.async_start()
        clock[0]=5000
        await tick(driver,policy,plan(hass,policy))
        assert driver.statuses["bedroom"]["status"]=="other_hvac_armed"
        heater.state="off"
        await tick(driver,policy,plan(hass,policy))
        assert [c[2]["hvac_mode"] for c in hass.services.calls]==["dry"]
        await driver.async_stop()
    asyncio.run(case())


def test_restart_unacknowledged_command_does_not_repeat_hvac_write(mode_module,monkeypatch):
    async def case():
        snapshots={}
        class Store:
            def __init__(self,*args):
                self.key=args[-1]
            async def async_load(self):
                return snapshots.get(self.key)
            def async_delay_save(self,callback,delay):
                snapshots[self.key]=callback()
            async def async_save(self,payload):
                snapshots[self.key]=payload
        monkeypatch.setattr(sys.modules["homeassistant.helpers.storage"],
                            "Store",Store)
        hass,clock=system()
        policy=cfg()
        hass.services.ack=False
        first=mode_module.NativeAirModeControl(
            hass,"reboot",clock=lambda:clock[0])
        await first.async_start()
        clock[0]=5000
        await tick(first,policy,plan(hass,policy))
        assert len(hass.services.calls)==1
        await first.async_stop()
        second=mode_module.NativeAirModeControl(
            hass,"reboot",clock=lambda:clock[0])
        await second.async_start()
        clock[0]=5400
        await tick(second,policy,plan(hass,policy))
        assert second.paused["bedroom"]=="manual_mode_or_unacknowledged_write"
        assert len(hass.services.calls)==1
        await second.async_stop()
    asyncio.run(case())


def test_bad_dwell_and_duplicate_device_ownership_fail_closed(mode_module):
    async def case():
        hass,clock=system()
        driver=mode_module.NativeAirModeControl(
            hass,"owners",clock=lambda:clock[0])
        await driver.async_start()
        clock[0]=5000
        bad=cfg(dry_fan_mode_dwell_s=60)
        await tick(driver,bad,plan(hass,bad))
        assert driver.statuses["bedroom"]["status"]=="invalid_mode_dwell"
        same=cfg()
        driver.schedule({"bedroom":same,"kitchen":{
            "enabled":True,"dry_climate_entity":"climate.bedroom_ac",
        }},{"bedroom":plan(hass,same)})
        for _ in range(10):
            await asyncio.sleep(0)
        assert driver.statuses["bedroom"]["status"]=="duplicate_device_owner"
        assert not hass.services.calls
        await driver.async_stop()
    asyncio.run(case())
