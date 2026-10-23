"""Guard fan.* power ownership and never start unverified extraction or climate."""
import asyncio
import importlib
import sys
import types

import pytest

from test_climate_pid import FakeStore
from test_discovery import FakeHass, MockState, adapter


@pytest.fixture
def driver(adapter,monkeypatch):
    m=types.ModuleType("homeassistant.helpers.storage")
    m.Store=FakeStore
    monkeypatch.setitem(sys.modules,"homeassistant.helpers.storage",m)
    return importlib.import_module("custom_components.enviroment_manager.climate_fan_power")


class Services:
    def __init__(self,hass):
        self.hass=hass
        self.calls=[]
        self.ack=True
        self.fail=False

    def has_service(self,domain,action):
        return domain=="fan" and action in ("turn_on","turn_off")

    async def async_call(self,domain,action,data,**kwargs):
        self.calls.append((domain,action,data,kwargs))
        if self.fail:
            raise RuntimeError("physical fan controller unavailable")
        if self.ack:
            self.hass.states.get(kwargs["target"]["entity_id"]).state=(
                "on" if action=="turn_on" else "off"
            )


def home(*,on=False):
    fan=MockState("fan.bedroom_extractor","on" if on else "off")
    fan.attributes.update({"supported_features":1,"percentage":30})
    purifier=MockState("fan.bedroom_purifier","off")
    purifier.attributes.update({"supported_features":1,"percentage":30})
    co=MockState("sensor.bedroom_co2",1600,device_class="co2",unit="ppm")
    pm=MockState("sensor.bedroom_pm",56,device_class="pm25",unit="µg/m³")
    h=FakeHass([fan,purifier,co,pm],{s.entity_id:"bedroom"
                                  for s in (fan,purifier,co,pm)})
    h.services=Services(h)
    h.async_create_task=asyncio.create_task
    return h


def cfg(**mod):
    return {"enabled":True,"allow_actuation":True,
            "fan_power_auto":True,"fan_speed_auto":False,
            "fan_power_hardware_confirmed":True,
            "fan_power_min_on_s":300,"fan_power_min_off_s":300,
            "fan_power_max_on_s":3600,
            "extraction_fan_entity":"fan.bedroom_extractor",
            "co2_entity":"sensor.bedroom_co2",
            **mod}


def plan(t=1400, extraction=True, verified=True, purifier=False):
    return {"status":"advisory","window_safe":True,
      "air_evidence_at":t,
      "air_actions":{"status":"advisory",
        "outdoor_air_verified":verified,
        "thresholds":{"co2_operational_ppm":1200,
                      "pm25_short_term_action_ug_m3":35},
        "extraction":{"status":"recommended" if extraction else "no_ventilation_demand",
                      "entity_id":"fan.bedroom_extractor",
                      "speed_control_eligible":extraction},
        "filtration":{"status":"recommended" if purifier else "no_particle_demand",
                      "entity_id":"fan.bedroom_purifier",
                      "speed_control_eligible":purifier},
      }}


async def tick(c,profile,report):
    c.schedule({"bedroom":profile},{"bedroom":report})
    for _ in range(7):
        await asyncio.sleep(0)


def test_disabled_attestation_never_issues_power(driver):
    async def run():
        h=home()
        t=[1000.]
        c=driver.FanPowerControl(h,"disabled",clock=lambda:t[0])
        await c.async_start()
        t[0]=1400
        await tick(c,cfg(fan_power_auto=False),plan(t[0]))
        assert c.statuses["bedroom"]["status"]=="advisory_only"
        await tick(c,cfg(fan_power_hardware_confirmed=False),plan(t[0]))
        assert not h.services.calls
        await c.async_stop()
    asyncio.run(run())


def test_measured_extraction_runs_then_stops_after_demand_clear(driver):
    async def run():
        h=home()
        t=[1000.]
        c=driver.FanPowerControl(h,"extract",clock=lambda:t[0])
        await c.async_start()
        t[0]=1400
        await tick(c,cfg(),plan(t[0]))
        assert c.statuses["bedroom"]["status"]=="minimum_fan_off_hold"
        t[0]=1750
        await tick(c,cfg(),plan(t[0]))
        assert len(h.services.calls)==1
        assert h.services.calls[0][:2]==("fan","turn_on")
        assert h.services.calls[0][3]["target"]=={"entity_id":"fan.bedroom_extractor"}
        t[0]=1800
        await tick(c,cfg(),plan(t[0]))
        assert c.statuses["bedroom"]["status"]=="owned_fan_running"
        h.states.get("sensor.bedroom_co2").state="900"
        t[0]=1900
        await tick(c,cfg(),plan(t[0],extraction=False))
        assert len(h.services.calls)==1
        assert c.statuses["bedroom"]["status"]=="minimum_fan_on_hold"
        t[0]=2100
        await tick(c,cfg(),plan(t[0],extraction=False))
        assert len(h.services.calls)==2
        assert h.services.calls[-1][:2]==("fan","turn_off")
        t[0]=2200
        await tick(c,cfg(),plan(t[0],extraction=False))
        assert "fan.bedroom_extractor" not in c.owned
        await c.async_stop()
    asyncio.run(run())


def test_do_not_claim_manual_running_fan(driver):
    async def run():
        h=home(on=True)
        t=[1000.]
        c=driver.FanPowerControl(h,"manual",clock=lambda:t[0])
        await c.async_start()
        t[0]=1400
        await tick(c,cfg(),plan(t[0]))
        t[0]=1750
        await tick(c,cfg(),plan(t[0]))
        assert c.paused["bedroom"]=="already_running_fan_is_manual"
        assert not h.services.calls
        await c.async_stop()
    asyncio.run(run())


def test_extraction_requires_current_outdoor_and_verified_indoor_source(driver):
    async def run():
        h=home()
        t=[1000.]
        c=driver.FanPowerControl(h,"invalid",clock=lambda:t[0])
        await c.async_start()
        t[0]=1400
        await tick(c,cfg(),plan(t[0]))
        t[0]=1750
        await tick(c,cfg(),plan(t[0],verified=False))
        assert c.statuses["bedroom"]["status"]=="outdoor_pollutant_data_unverified"
        await tick(c,cfg(),plan(1500))
        assert c.statuses["bedroom"]["status"]=="air_quality_decision_expired"
        assert not h.services.calls
        await c.async_stop()
    asyncio.run(run())


def test_purifier_is_independent_of_outdoor_aqi_when_pm_verified(driver):
    async def run():
        h=home()
        t=[1000.]
        c=driver.FanPowerControl(h,"filter",clock=lambda:t[0])
        await c.async_start()
        conf=cfg(extraction_fan_entity=None,co2_entity=None,
                 purifier_fan_entity="fan.bedroom_purifier",
                 pm25_entity="sensor.bedroom_pm",pm25_sensor_verified=True)
        t[0]=1400
        await tick(c,conf,plan(t[0],extraction=False,purifier=True,verified=False))
        t[0]=1750
        await tick(c,conf,plan(t[0],extraction=False,purifier=True,verified=False))
        assert len(h.services.calls)==1
        assert h.services.calls[0][3]["target"]=={"entity_id":"fan.bedroom_purifier"}
        await c.async_stop()
    asyncio.run(run())


def test_manual_override_and_timeout_stop_future_commands(driver):
    async def run():
        h=home()
        t=[1000.]
        c=driver.FanPowerControl(h,"manual-change",clock=lambda:t[0])
        await c.async_start()
        t[0]=1400
        await tick(c,cfg(),plan(t[0]))
        t[0]=1750
        await tick(c,cfg(),plan(t[0]))
        h.states.get("fan.bedroom_extractor").state="off"
        t[0]=1900
        await tick(c,cfg(),plan(t[0]))
        assert c.paused["bedroom"]=="manual_fan_power_or_unacknowledged_write"
        t[0]=2400
        await tick(c,cfg(),plan(t[0]))
        assert len(h.services.calls)==1
        await c.async_stop()
        h2=home()
        h2.services.fail=True
        c2=driver.FanPowerControl(h2,"failed",clock=lambda:t[0])
        await c2.async_start()
        t[0]=2800
        await tick(c2,cfg(),plan(t[0]))
        t[0]=3150
        await tick(c2,cfg(),plan(t[0]))
        assert c2.paused["bedroom"]=="fan_power_command_failed"
        assert len(h2.services.calls)==1
        await c2.async_stop()
    asyncio.run(run())


def test_restart_with_owned_fan_requires_reconciliation_not_power_command(driver,monkeypatch):
    async def run():
        saved={}
        class SharedStore(FakeStore):
            def __init__(self,*args):
                self.key=args[-1]
            async def async_load(self):
                return saved.get(self.key)
            def async_delay_save(self,fn,delay):
                saved[self.key]=fn()
            async def async_save(self,value):
                saved[self.key]=value
        monkeypatch.setattr(sys.modules["homeassistant.helpers.storage"],
                            "Store",SharedStore)
        h=home()
        t=[1000.]
        c=driver.FanPowerControl(h,"restart",clock=lambda:t[0])
        await c.async_start()
        t[0]=1400
        await tick(c,cfg(),plan(t[0]))
        t[0]=1750
        await tick(c,cfg(),plan(t[0]))
        await c.async_stop()
        assert len(h.services.calls)==1
        again=driver.FanPowerControl(h,"restart",clock=lambda:t[0])
        await again.async_start()
        assert again.paused["bedroom"]=="restart_requires_manual_fan_off_reconciliation"
        t[0]=2600
        await tick(again,cfg(),plan(t[0]))
        assert len(h.services.calls)==1
        assert not (await again.command("bedroom","resume"))["accepted"]
        h.states.get("fan.bedroom_extractor").state="off"
        assert (await again.command("bedroom","resume"))["accepted"]
        # Manual reconciliation at 2600 requires a *new*, full 300-second
        # minimum-off and startup warmup period before another ON.
        t[0]=2850
        await tick(again,cfg(),plan(t[0]))
        assert len(h.services.calls)==1
        await again.async_stop()
    asyncio.run(run())


def test_live_room_gate_prevents_unsafe_extractor_start_after_window_change(driver):
    async def scenario():
        from custom_components.enviroment_manager.climate_arbitration import (
            room_coordination,
        )
        h=home()
        contact=MockState("binary_sensor.bedroom_window","off",
                          device_class="window")
        h._values[contact.entity_id]=contact
        h._entity_areas[contact.entity_id]="bedroom"
        conf=cfg()
        t=[1000.]
        manager=driver.FanPowerControl(h,"coordinated",clock=lambda:t[0])
        await manager.async_start()
        t[0]=1400
        pending=plan(t[0])
        pending["window_contacts"]=[contact.entity_id]
        pending["coordination"]=room_coordination(
            h,"bedroom",conf,pending,now=t[0],
        )
        assert pending["coordination"]["channels"]["extraction"]["status"]=="eligible"
        await tick(manager,conf,pending)
        t[0]=1750
        pending["air_evidence_at"]=t[0]  # fresh indoor/outdoor source update
        contact.state="on"  # room window opened AFTER plan validation
        await tick(manager,conf,pending)
        assert manager.statuses["bedroom"]=={
            "status":"coordination_hold",
            "entity_id":"fan.bedroom_extractor",
            "reason":"window_open_or_unknown",
        }
        assert not h.services.calls
        contact.state="off"
        await tick(manager,conf,pending)
        assert h.services.calls[0][:2]==("fan","turn_on")
        await manager.async_stop()
    asyncio.run(scenario())



def test_owned_fan_survives_room_removal_and_preserves_power_dwell(driver):
    async def scenario():
        hass=home()
        clock=[1000.]
        control=driver.FanPowerControl(
            hass,"room-removal",clock=lambda:clock[0],
        )
        await control.async_start()
        original=cfg(fan_power_min_on_s=900,
                     fan_power_min_off_s=300,
                     fan_power_max_on_s=3000)
        clock[0]=1400
        await tick(control,original,plan(clock[0]))
        clock[0]=1750
        await tick(control,original,plan(clock[0]))
        target="fan.bedroom_extractor"
        assert control.owned[target]["min_on_s"]==900
        assert [e[1] for e in hass.services.calls]==["turn_on"]
        clock[0]=2400
        control.schedule({}, {})
        for _ in range(8):
            await asyncio.sleep(0)
        assert [e[1] for e in hass.services.calls]==["turn_on"]
        assert control.statuses["bedroom"]["status"]=="minimum_fan_on_hold"
        clock[0]=2651
        control.schedule({}, {})
        for _ in range(8):
            await asyncio.sleep(0)
        assert [e[1] for e in hass.services.calls]==["turn_on","turn_off"]
        clock[0]=2700
        control.schedule({}, {})
        for _ in range(8):
            await asyncio.sleep(0)
        assert target not in control.owned
        await control.async_stop()
    asyncio.run(scenario())


def test_fan_options_change_does_not_shorten_active_minimum_on(driver):
    async def scenario():
        hass=home()
        clock=[1000.]
        control=driver.FanPowerControl(
            hass,"on-dwell-edited",clock=lambda:clock[0],
        )
        await control.async_start()
        original=cfg(fan_power_min_on_s=900,
                     fan_power_max_on_s=3000)
        clock[0]=1400
        await tick(control,original,plan(clock[0]))
        clock[0]=1750
        await tick(control,original,plan(clock[0]))
        changed=cfg(fan_power_min_on_s=120,fan_power_max_on_s=900,
                    enabled=False)
        clock[0]=2400
        await tick(control,changed,plan(clock[0]))
        assert [e[1] for e in hass.services.calls]==["turn_on"]
        clock[0]=2651
        await tick(control,changed,plan(clock[0]))
        assert [e[1] for e in hass.services.calls]==["turn_on","turn_off"]
        await control.async_stop()
    asyncio.run(scenario())


def test_fan_legacy_active_record_without_dwell_requires_manual_reconciliation(driver):
    async def scenario():
        hass=home(on=True)
        clock=[2000.]
        control=driver.FanPowerControl(
            hass,"legacy-fan-record",clock=lambda:clock[0],
        )
        await control.async_start()
        control.owned["fan.bedroom_extractor"]={
            "entity_id":"fan.bedroom_extractor",
            "area":"bedroom","role":"extraction_fan_entity",
            "power":"on","when":1000,"acknowledged":True,
        }
        control.schedule({}, {})
        for _ in range(8):
            await asyncio.sleep(0)
        assert control.paused["bedroom"]=="original_fan_dwell_unknown_reconcile_manually"
        assert not hass.services.calls
        await control.async_stop()
    asyncio.run(scenario())
