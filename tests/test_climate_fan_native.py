"""Fan SET_SPEED only on already-on, measured and authorized equipment."""
import asyncio
import importlib
import sys
import types

import pytest
from test_discovery import FakeHass,MockState,adapter
from test_climate_pid import FakeStore


@pytest.fixture
def fan_module(adapter,monkeypatch):
    mock=types.ModuleType("homeassistant.helpers.storage")
    mock.Store=FakeStore
    monkeypatch.setitem(sys.modules,"homeassistant.helpers.storage",mock)
    return importlib.import_module("custom_components.enviroment_manager.climate_fan_native")


class FanServices:
    def __init__(self,hass):
        self.hass=hass
        self.calls=[]
        self.fail=False
        self.ack=True
    def has_service(self,domain,action):
        return (domain,action)==("fan","set_percentage")
    async def async_call(self,domain,action,data,**kwargs):
        self.calls.append((domain,action,data,kwargs))
        if self.fail:
            raise RuntimeError("device went offline")
        if self.ack:
            self.hass.states.get(kwargs["target"]["entity_id"]).attributes[
                "percentage"]=data["percentage"]


def home(*, on=True, sensor_age=0, step=5):
    pm=MockState("sensor.pm25",64,device_class="pm25",unit="µg/m³",hours_old=sensor_age)
    co=MockState("sensor.co2",1500,device_class="co2",unit="ppm",hours_old=sensor_age)
    fan=MockState("fan.purifier","on" if on else "off")
    fan.attributes.update({"supported_features":1,"percentage":40,
                           "percentage_step":step})
    exhaust=MockState("fan.extractor","on")
    exhaust.attributes.update({"supported_features":1,"percentage":30,
                               "percentage_step":5})
    h=FakeHass([pm,co,fan,exhaust],{entity.entity_id:"bedroom"
                                for entity in (pm,co,fan,exhaust)})
    h.services=FanServices(h)
    h.async_create_task=asyncio.create_task
    return h


def config(**kw):
    return {"enabled":True,"allow_actuation":True,"controller":"device",
            "fan_speed_auto":True,
            "purifier_fan_entity":"fan.purifier",
            "pm25_entity":"sensor.pm25",
            "pm25_sensor_verified":True,
            "purifier_speed_percent":70,
            **kw}


def plan(*, extraction=False):
    return {"air_actions":{
        "status":"advisory",
        "thresholds":{"pm25_short_term_action_ug_m3":35,"co2_operational_ppm":1200},
        "filtration":{
            "status":"recommended",
            "entity_id":"fan.purifier","reasons":["measured_short_term_pm25_trigger"],
            "speed_control_eligible":True},
        "extraction":{
            "status":"recommended" if extraction else "no_ventilation_demand",
            "entity_id":"fan.extractor",
            "reasons":["elevated_measured_co2"] if extraction else [],
            "speed_control_eligible":extraction},
    }}


async def tick(controller,cfg,report,*,additional=None):
    configs={"bedroom":cfg,**(additional or {})}
    controller.schedule(configs,{"bedroom":report})
    for _ in range(7):
        await asyncio.sleep(0)


def test_ramp_is_upward_only_and_never_zero(fan_module):
    f=fan_module.next_fan_speed
    assert f(40,70,5)==("command",50)
    assert f(50,70,5)==("command",60)
    assert f(70,40,5)==("already_sufficient_speed",None)
    assert f(40,80,25)[0]=="native_step_exceeds_safe_ramp"
    assert f(40,0,5)[0]=="missing_percent_or_native_step"


def test_fan_only_when_already_on_opted_in_and_pm_measured(fan_module):
    async def run():
        h=home()
        clk=[1000.]
        c=fan_module.RunningFanSpeedControl(h,"test",clock=lambda:clk[0])
        await c.async_start()
        clk[0]=1400
        await tick(c,config(fan_speed_auto=False),plan())
        assert not h.services.calls
        await tick(c,config(),plan())
        assert h.services.calls==[("fan","set_percentage",{"percentage":50},
                    {"target":{"entity_id":"fan.purifier"},"blocking":True})]
        assert c.expected["fan.purifier"]["percentage"]==50
        await c.async_stop()
    asyncio.run(run())


def test_does_not_turn_on_off_or_change_native_preset(fan_module):
    async def run():
        h=home(on=False)
        clk=[1000.]
        c=fan_module.RunningFanSpeedControl(h,"test",clock=lambda:clk[0])
        await c.async_start()
        clk[0]=1400
        await tick(c,config(),plan())
        assert c.statuses["bedroom"]["status"]=="fan_off_no_automatic_power_on"
        assert not h.services.calls
        h.states.get("fan.purifier").state="on"
        h.states.get("fan.purifier").attributes["preset_mode"]="eco"
        await tick(c,config(),plan())
        assert c.statuses["bedroom"]["status"]=="manual_fan_preset_active"
        assert not h.services.calls
        await c.async_stop()
    asyncio.run(run())


def test_sensor_or_device_invalid_never_commands_speed(fan_module):
    async def run():
        for h,reason in [
            (home(sensor_age=24),"sensor_unknown_or_stale"),
            (home(step=20),"native_step_exceeds_safe_ramp"),
        ]:
            clk=[1000.]
            c=fan_module.RunningFanSpeedControl(h,"test",clock=lambda:clk[0])
            await c.async_start()
            clk[0]=1400
            await tick(c,config(),plan())
            assert c.statuses["bedroom"]["status"]==reason
            assert not h.services.calls
            await c.async_stop()
    asyncio.run(run())


def test_manual_override_and_failed_command_pause(fan_module):
    async def run():
        h=home()
        clk=[1000.]
        c=fan_module.RunningFanSpeedControl(h,"test",clock=lambda:clk[0])
        await c.async_start()
        clk[0]=1400
        await tick(c,config(),plan())
        assert len(h.services.calls)==1
        h.states.get("fan.purifier").attributes["percentage"]=35
        clk[0]=1800
        await tick(c,config(),plan())
        assert c.paused["bedroom"]=="manual_speed_or_unacknowledged_fan"
        assert len(h.services.calls)==1
        assert (await c.command("bedroom","resume"))["accepted"]
        await c.async_stop()
        second=home()
        second.services.fail=True
        next_ctrl=fan_module.RunningFanSpeedControl(second,"second",
            clock=lambda:clk[0])
        await next_ctrl.async_start()
        clk[0]=2200
        await tick(next_ctrl,config(),plan())
        assert next_ctrl.paused["bedroom"]=="fan_speed_service_failure"
        assert len(second.services.calls)==1
        await next_ctrl.async_stop()
    asyncio.run(run())


def test_conflicting_assignment_and_extract_requires_verified_co2(fan_module):
    async def run():
        h=home()
        clk=[1000.]
        c=fan_module.RunningFanSpeedControl(h,"test",clock=lambda:clk[0])
        await c.async_start()
        clk[0]=1400
        await tick(c,config(extraction_fan_entity="fan.purifier"),plan(extraction=True))
        assert c.statuses["bedroom"]["status"]=="duplicate_or_ambiguous_fan_assignment"
        assert not h.services.calls
        cfg={"enabled":True,"allow_actuation":True,"fan_speed_auto":True,
             "extraction_fan_entity":"fan.extractor","co2_entity":"sensor.co2",
             "extraction_speed_percent":65}
        await tick(c,cfg,plan(extraction=True))
        assert len(h.services.calls)==1
        assert h.services.calls[0][3]["target"]=={"entity_id":"fan.extractor"}
        await c.async_stop()
    asyncio.run(run())


def test_restart_detects_manual_fan_speed_and_never_rewrites_it(fan_module):

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
        h=home()
        clk=[1000.0]
        first=fan_module.RunningFanSpeedControl(h,"restart",clock=lambda:clk[0])
        await first.async_start()
        clk[0]=1400
        await tick(first,config(),plan())
        assert first.expected["fan.purifier"]["percentage"]==50
        await first.async_stop()

        # During the HA outage somebody selected a different fan speed.
        h.states.get("fan.purifier").attributes["percentage"]=35
        recovered=fan_module.RunningFanSpeedControl(h,"restart",clock=lambda:clk[0])
        await recovered.async_start()
        assert recovered.expected["fan.purifier"]["percentage"]==50
        clk[0]=1800
        await tick(recovered,config(),plan())
        assert recovered.paused["bedroom"]=="manual_speed_or_unacknowledged_fan"
        assert len(h.services.calls)==1
        await recovered.async_stop()
    asyncio.run(scenario())


def test_expired_air_evidence_never_commands_fan_speed(fan_module):
    async def run():
        h=home()
        t=[1000.]
        engine=fan_module.RunningFanSpeedControl(h,"ttl",clock=lambda:t[0])
        await engine.async_start()
        t[0]=1400
        stale={**plan(),"air_evidence_at":1200}
        await tick(engine,config(),stale)
        assert engine.statuses["bedroom"]["status"]=="air_quality_decision_expired"
        assert not h.services.calls
        future={**plan(),"air_evidence_at":2000}
        await tick(engine,config(),future)
        assert engine.statuses["bedroom"]["status"]=="air_quality_decision_expired"
        assert not h.services.calls
        current={**plan(),"air_evidence_at":1390}
        await tick(engine,config(),current)
        assert len(h.services.calls)==1
        await engine.async_stop()
    asyncio.run(run())


def test_running_extractor_speed_rechecks_window_after_room_grant(fan_module):
    async def scenario():
        from custom_components.enviroment_manager.climate_arbitration import (
            room_coordination,
        )
        h=home()
        window=MockState("binary_sensor.window","off",device_class="window")
        h._values[window.entity_id]=window
        h._entity_areas[window.entity_id]="bedroom"
        conf={
            "enabled":True,"allow_actuation":True,"fan_speed_auto":True,
            "extraction_fan_entity":"fan.extractor",
            "co2_entity":"sensor.co2",
            "extraction_speed_percent":65,
        }
        report=plan(extraction=True)
        report.update({
            "window_contacts":[window.entity_id],
            "window_safe":True,
            "air_evidence_at":1400,
            "equipment_plan":{"status":"ready"},
        })
        report["air_actions"]["outdoor_air_verified"]=True
        clk=[1000.]
        controller=fan_module.RunningFanSpeedControl(
            h,"shared-air",clock=lambda:clk[0],
        )
        await controller.async_start()
        clk[0]=1400
        report["coordination"]=room_coordination(
            h,"bedroom",conf,report,now=1400,
        )
        assert report["coordination"]["channels"]["extraction"]["status"]=="eligible"
        window.state="on"  # New opening after the last policy evaluation
        await tick(controller,conf,report)
        assert not h.services.calls
        assert controller.statuses["bedroom"]=={
            "status":"coordination_hold","entity_id":"fan.extractor",
            "reason":"window_open_or_unknown",
        }
        window.state="off"
        await tick(controller,conf,report)
        assert h.services.calls[0][:2]==("fan","set_percentage")
        await controller.async_stop()
    asyncio.run(scenario())
