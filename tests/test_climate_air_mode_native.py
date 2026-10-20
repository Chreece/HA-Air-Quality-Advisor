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
        assert driver.statuses["bedroom"]["status"]=="compressor_idle_confirmation_pending"
        assert len(hass.services.calls)==1
        clock[0]=7250
        await tick(driver,policy,plan(hass,policy))
        assert driver.statuses["bedroom"]["status"]=="compressor_idle_confirmation_pending"
        assert len(hass.services.calls)==1
        clock[0]=7301
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
        # Resume cannot erase the outstanding mode-change cooldown.
        assert (await driver.command("bedroom","resume"))=={
            "accepted":False,
            "reason":"manual_fan_only_reconciliation_and_full_dwell_required",
        }
        clock[0]=7000
        assert (await driver.command("bedroom","resume"))["accepted"] is True
        assert driver.last_write["bedroom"]==5000
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



def test_mode_write_intent_is_durable_before_hvac_service_and_after_restart(
    mode_module,monkeypatch,
):
    async def case():
        persisted={}
        order=[]
        class Store:
            def __init__(self,*args):
                self.key=args[-1]
            async def async_load(self):
                return persisted.get(self.key)
            def async_delay_save(self,callback,delay):
                persisted[self.key]=callback()
            async def async_save(self,payload):
                persisted[self.key]={
                    "version":payload["version"],
                    "paused":dict(payload["paused"]),
                    "expected":{k:dict(v) for k,v in payload["expected"].items()},
                    "last_write":dict(payload["last_write"]),
                }
                order.append("persist_"+payload["expected"].get(
                    "bedroom",{}).get("phase","unknown"))
        monkeypatch.setattr(sys.modules["homeassistant.helpers.storage"],
                            "Store",Store)
        hass,clock=system()
        class Interrupted:
            def has_service(self,domain,service):
                return (domain,service)==("climate","set_hvac_mode")
            async def async_call(self,*args,**kwargs):
                order.append("service_attempt")
                raise asyncio.CancelledError
        hass.services=Interrupted()
        first=mode_module.NativeAirModeControl(
            hass,"interrupted",clock=lambda:clock[0],
        )
        await first.async_start()
        clock[0]=5000
        await tick(first,cfg(),plan(hass,cfg()))
        assert order[:2]==["persist_intent","service_attempt"]
        assert persisted[first._store.key]["expected"]["bedroom"]["phase"]=="intent"
        await first.async_stop()
        second=mode_module.NativeAirModeControl(
            hass,"interrupted",clock=lambda:clock[0],
        )
        await second.async_start()
        assert second.paused["bedroom"]==(
            "interrupted_mode_write_requires_manual_reconciliation"
        )
        assert second.statuses["bedroom"]["status"]=="paused"
        clock[0]=5400
        await tick(second,cfg(),plan(hass,cfg()))
        assert second.paused["bedroom"]==(
            "interrupted_mode_write_requires_manual_reconciliation"
        )
        assert order.count("service_attempt")==1
        await second.async_stop()
    asyncio.run(case())


def test_failed_write_ahead_storage_forbids_any_hvac_command(
    mode_module,monkeypatch,
):
    async def case():
        class FailingStore:
            def __init__(self,*args):
                pass
            async def async_load(self):
                return None
            def async_delay_save(self,callback,delay):
                pass
            async def async_save(self,payload):
                raise OSError("storage device unavailable")
        monkeypatch.setattr(sys.modules["homeassistant.helpers.storage"],
                            "Store",FailingStore)
        hass,clock=system()
        driver=mode_module.NativeAirModeControl(
            hass,"storage-failure",clock=lambda:clock[0],
        )
        await driver.async_start()
        clock[0]=5000
        await tick(driver,cfg(),plan(hass,cfg()))
        assert driver.paused["bedroom"]=="mode_intent_storage_failed"
        assert not hass.services.calls
        # An explicit resume is not permitted until the history and
        # physical mode can be reconciled, so no immediate second try.
        assert (await driver.command("bedroom","resume"))["accepted"] is False
        assert not hass.services.calls
        # Storage failure is already latched; stopping this controller
        # must not block shutdown of every other HA device controller.
        await driver.async_stop()
    asyncio.run(case())


def test_manual_resume_requires_physical_fan_only_and_keeps_last_hvac_dwell(
    mode_module,
):
    async def case():
        hass,clock=system()
        driver=mode_module.NativeAirModeControl(
            hass,"manual-reconcile",clock=lambda:clock[0],
        )
        await driver.async_start()
        clock[0]=5000
        await tick(driver,cfg(),plan(hass,cfg()))
        assert [c[2]["hvac_mode"] for c in hass.services.calls]==["dry"]
        assert (await driver.command("bedroom","pause"))["accepted"] is True
        # Current physical DRY mode must not be silently taken back over.
        clock[0]=7100
        denied=await driver.command("bedroom","resume")
        assert denied["accepted"] is False
        # Operator manually switches to FAN_ONLY and allows stable dwell.
        ac=hass.states.get("climate.bedroom_ac")
        ac.state="fan_only"
        ac.attributes["hvac_action"]="fan"
        ac.last_changed=datetime.fromtimestamp(7200,timezone.utc)
        clock[0]=8500
        assert (await driver.command("bedroom","resume"))["accepted"] is False
        clock[0]=9100
        assert (await driver.command("bedroom","resume"))["accepted"] is True
        assert driver.last_write["bedroom"]==5000
        assert "bedroom" not in driver.expected
        clock[0]=9200
        await tick(driver,cfg(),plan(hass,cfg()))
        assert len(hass.services.calls)==1
        await driver.async_stop()
    asyncio.run(case())



@pytest.mark.parametrize("payload",[
    {"version":2,"expected":{},"paused":{},"last_write":{}},
    {"version":1,"expected":[],"paused":{},"last_write":{}},
    {"version":1,"expected":{"bedroom":None},"paused":{},"last_write":{}},
    {"version":1,"expected":{},"paused":{},"last_write":{"bedroom":"nan"}},
])
def test_corrupt_or_future_mode_safety_history_disables_actuation(
    mode_module,monkeypatch,payload,
):
    async def case():
        class Store:
            def __init__(self,*args):
                pass
            async def async_load(self):
                return payload
            def async_delay_save(self,fn,delay):
                raise AssertionError("Must not overwrite unsupported store")
            async def async_save(self,payload):
                raise AssertionError("Must not overwrite unsupported store")
        monkeypatch.setattr(sys.modules["homeassistant.helpers.storage"],
                            "Store",Store)
        hass,clock=system()
        driver=mode_module.NativeAirModeControl(
            hass,"future-store",clock=lambda:clock[0],
        )
        await driver.async_start()
        assert driver._ready is False
        assert driver.statuses["*"]["status"]=="safety_history_unsupported"
        clock[0]=5000
        await tick(driver,cfg(),plan(hass,cfg()))
        assert not hass.services.calls
        await driver.async_stop()
    asyncio.run(case())


def test_mode_resume_preserves_earliest_possible_next_write_after_restart(
    mode_module,monkeypatch,
):
    async def case():
        payload={}
        class Store:
            def __init__(self,*args):
                self.key=args[-1]
            async def async_load(self):
                return payload.get(self.key)
            def async_delay_save(self,fn,delay):
                payload[self.key]=fn()
            async def async_save(self,value):
                payload[self.key]=value
        monkeypatch.setattr(sys.modules["homeassistant.helpers.storage"],
                            "Store",Store)
        hass,clock=system()
        driver=mode_module.NativeAirModeControl(
            hass,"manual-resume-restart",clock=lambda:clock[0],
        )
        await driver.async_start()
        clock[0]=5000
        await tick(driver,cfg(),plan(hass,cfg()))
        assert len(hass.services.calls)==1
        await driver.command("bedroom","pause")
        await driver.async_stop()
        next_driver=mode_module.NativeAirModeControl(
            hass,"manual-resume-restart",clock=lambda:clock[0],
        )
        await next_driver.async_start()
        assert next_driver.paused["bedroom"]=="user_paused"
        ac=hass.states.get("climate.bedroom_ac")
        ac.state="fan_only"
        ac.attributes["hvac_action"]="fan"
        ac.last_changed=datetime.fromtimestamp(5200,timezone.utc)
        clock[0]=7000
        await tick(next_driver,cfg(),plan(hass,cfg()))
        attempt=await next_driver.command("bedroom","resume")
        assert attempt["accepted"] is True
        assert next_driver.last_write["bedroom"]==5000
        # A fresh resumed controller must honor warmup as well as dwell.
        clock[0]=7150
        await tick(next_driver,cfg(),plan(hass,cfg()))
        assert len(hass.services.calls)==1
        clock[0]=7400
        await tick(next_driver,cfg(),plan(hass,cfg()))
        assert len(hass.services.calls)==2
        await next_driver.async_stop()
    asyncio.run(case())



def test_new_compressor_activity_invalidates_the_full_idle_observation(
    mode_module,
):
    async def case():
        hass,clock=system(mode="dry",rh=55,hvac_action="idle")
        policy=cfg()
        driver=mode_module.NativeAirModeControl(
            hass,"native-idle-recheck",clock=lambda:clock[0],
        )
        await driver.async_start()
        clock[0]=5000
        await tick(driver,policy,plan(hass,policy))
        assert driver.statuses["bedroom"]["status"]==(
            "compressor_idle_confirmation_pending"
        )
        # A DRYING report between observations resets the idle window.
        clock[0]=5200
        hass.states.get("climate.bedroom_ac").attributes["hvac_action"]="drying"
        await tick(driver,policy,plan(hass,policy))
        assert driver.statuses["bedroom"]["status"]=="active_compressor_wait_for_idle"
        assert "bedroom" not in driver._dry_idle_since
        clock[0]=5300
        hass.states.get("climate.bedroom_ac").attributes["hvac_action"]="idle"
        await tick(driver,policy,plan(hass,policy))
        assert driver.statuses["bedroom"]["status"]==(
            "compressor_idle_confirmation_pending"
        )
        clock[0]=5599
        await tick(driver,policy,plan(hass,policy))
        assert not hass.services.calls
        clock[0]=5600
        await tick(driver,policy,plan(hass,policy))
        assert [c[2]["hvac_mode"] for c in hass.services.calls]==["fan_only"]
        await driver.async_stop()
    asyncio.run(case())



def test_window_opened_during_write_ahead_prevents_hvac_mode_service(
    mode_module,monkeypatch,
):
    async def case():
        hass,clock=system()
        saved={}
        snapshots=[]
        class RaceStore:
            def __init__(self,*args):
                self.key=args[-1]
            async def async_load(self):
                return saved.get(self.key)
            def async_delay_save(self,fn,delay):
                saved[self.key]=fn()
            async def async_save(self,payload):
                snapshots.append({
                    "phase":payload["expected"].get("bedroom",{}).get("phase"),
                    "mode":payload["expected"].get("bedroom",{}).get("mode"),
                })
                saved[self.key]=payload
                if payload["expected"].get("bedroom",{}).get("phase")=="intent":
                    # HA state arrives while the physical command intent
                    # is being flushed. This must be re-checked before the
                    # controller writes a climate.set_hvac_mode request.
                    hass.states.get("binary_sensor.bedroom_window").state="on"
        monkeypatch.setattr(sys.modules["homeassistant.helpers.storage"],
                            "Store",RaceStore)
        driver=mode_module.NativeAirModeControl(
            hass,"write-ahead-live-window",clock=lambda:clock[0],
        )
        await driver.async_start()
        clock[0]=5000
        await tick(driver,cfg(),plan(hass,cfg()))
        assert snapshots[0]=={"phase":"intent","mode":"dry"}
        assert driver.paused["bedroom"]=="mode_intent_aborted_by_live_interlock"
        assert driver.expected["bedroom"]["phase"]=="intent"
        assert not hass.services.calls
        # The externally closed window does not let the controller retry
        # an uncertain durable intent without explicit reconciliation.
        hass.states.get("binary_sensor.bedroom_window").state="off"
        clock[0]=7000
        await tick(driver,cfg(),plan(hass,cfg()))
        assert not hass.services.calls
        await driver.async_stop()
    asyncio.run(case())


def test_competing_ac_armed_during_persist_is_rejected_before_service(
    mode_module,monkeypatch,
):
    async def case():
        hass,clock=system()
        other=MockState("climate.bedroom_heater","off")
        other.attributes.update({
            "hvac_modes":["off","heat"],"supported_features":1,
            "hvac_action":"idle",
        })
        hass._values[other.entity_id]=other
        hass._entity_areas[other.entity_id]="bedroom"
        class RaceStore:
            def __init__(self,*args):
                pass
            async def async_load(self):
                return None
            def async_delay_save(self,fn,delay):
                pass
            async def async_save(self,payload):
                if payload["expected"].get("bedroom",{}).get("phase")=="intent":
                    other.state="heat"
        monkeypatch.setattr(sys.modules["homeassistant.helpers.storage"],
                            "Store",RaceStore)
        policy=cfg(heat_climate_entity=other.entity_id)
        driver=mode_module.NativeAirModeControl(
            hass,"write-ahead-live-hvac",clock=lambda:clock[0],
        )
        await driver.async_start()
        clock[0]=5000
        await tick(driver,policy,plan(hass,policy))
        assert driver.paused["bedroom"]=="mode_intent_aborted_by_live_interlock"
        assert not hass.services.calls
        await driver.async_stop()
    asyncio.run(case())


def test_permission_revoked_during_durable_intent_never_changes_native_mode(
    mode_module,monkeypatch,
):
    async def scenario():
        hass,clock=system()
        config=cfg()
        approved=plan(hass,config)
        snapshots=[]
        class Store:
            def __init__(self,*args):
                pass
            async def async_load(self):
                return None
            def async_delay_save(self,fn,delay):
                pass
            async def async_save(self,record):
                snapshots.append(record["expected"].get("bedroom",{}).get("phase"))
                if snapshots[-1]=="intent":
                    # A second options evaluation revokes consent while
                    # the service is awaiting the durable write-ahead.
                    config["dry_fan_mode_auto"]=False
        monkeypatch.setattr(
            sys.modules["homeassistant.helpers.storage"],"Store",Store,
        )
        controller=mode_module.NativeAirModeControl(
            hass,"revoked-permission",clock=lambda:clock[0],
        )
        await controller.async_start()
        clock[0]=5000
        await tick(controller,config,approved)
        assert snapshots==["intent"]
        assert not hass.services.calls
        assert controller.paused["bedroom"]=="mode_intent_aborted_by_live_interlock"
        assert controller.expected["bedroom"]["phase"]=="intent"
        await controller.async_stop()
    asyncio.run(scenario())


def test_plan_superseded_while_persisting_dry_intent_never_commands_ac(
    mode_module,monkeypatch,
):
    async def scenario():
        hass,clock=system()
        settings=cfg()
        approved=plan(hass,settings)
        updated=[]
        controller=None
        class Store:
            def __init__(self,*args):
                pass
            async def async_load(self):
                return None
            def async_delay_save(self,fn,delay):
                pass
            async def async_save(self,payload):
                if payload["expected"].get("bedroom",{}).get("phase")=="intent":
                    updated.append("new_room_plan")
                    # Another HA recalculation invalidates the original
                    # room decision after the write was durably staged.
                    controller._planned["bedroom"]={
                        **approved,"window_safe":False,
                    }
        monkeypatch.setattr(
            sys.modules["homeassistant.helpers.storage"],"Store",Store,
        )
        controller=mode_module.NativeAirModeControl(
            hass,"superseded-plan",clock=lambda:clock[0],
        )
        await controller.async_start()
        clock[0]=5000
        await tick(controller,settings,approved)
        assert updated==["new_room_plan"]
        assert not hass.services.calls
        assert controller.paused["bedroom"]=="mode_intent_aborted_by_live_interlock"
        assert controller.expected["bedroom"]["phase"]=="intent"
        await controller.async_stop()
    asyncio.run(scenario())


def test_full_custom_mode_dwell_is_rechecked_after_durable_storage(
    mode_module,monkeypatch,
):
    async def scenario():
        hass,clock=system()
        settings=cfg(dry_fan_mode_dwell_s=3600)
        source=plan(hass,settings)
        seen=[]
        class Store:
            def __init__(self,*args):
                pass
            async def async_load(self):
                return None
            def async_delay_save(self,fn,delay):
                pass
            async def async_save(self,record):
                phase=record["expected"].get("bedroom",{}).get("phase")
                seen.append(phase)
                if phase=="intent":
                    # A real device event occurred after the initial 4-hour
                    # dwell check, but before the final service call.
                    # Still older than the advisor's 30-minute gate.
                    hass.states.get("climate.bedroom_ac").last_changed=(
                        datetime.fromtimestamp(2400,timezone.utc)
                    )
        monkeypatch.setattr(
            sys.modules["homeassistant.helpers.storage"],"Store",Store,
        )
        driver=mode_module.NativeAirModeControl(
            hass,"full-dwell-recheck",clock=lambda:clock[0],
        )
        await driver.async_start()
        clock[0]=5000
        await tick(driver,settings,source)
        assert seen==["intent"]
        assert hass.services.calls==[]
        assert driver.paused["bedroom"]=="mode_intent_aborted_by_live_interlock"
        assert driver.expected["bedroom"]["phase"]=="intent"
        await driver.async_stop()
    asyncio.run(scenario())


def test_failed_post_command_write_never_promotes_persisted_intent(
    mode_module,monkeypatch,
):
    async def scenario():
        hass,clock=system()
        snapshots=[]
        class Store:
            def __init__(self,*args):
                pass
            async def async_load(self):
                return None
            def async_delay_save(self,fn,delay):
                pass
            async def async_save(self,payload):
                snapshots.append(payload)
                if payload["expected"].get("bedroom",{}).get("phase")=="commanded":
                    raise OSError("disk failed after native mode command")
        monkeypatch.setattr(
            sys.modules["homeassistant.helpers.storage"],"Store",Store,
        )
        driver=mode_module.NativeAirModeControl(
            hass,"commanded-store-fail",clock=lambda:clock[0],
        )
        await driver.async_start()
        clock[0]=5000
        await tick(driver,cfg(),plan(hass,cfg()))
        assert len(hass.services.calls)==1
        assert driver.expected["bedroom"]["phase"]=="intent"
        assert driver.paused["bedroom"]=="mode_command_history_persist_failed"
        # Snapshot #1 must be independent of later Python dict mutations.
        assert snapshots[0]["expected"]["bedroom"]["phase"]=="intent"
        assert snapshots[1]["expected"]["bedroom"]["phase"]=="commanded"
        clock[0]=9200
        await tick(driver,cfg(),plan(hass,cfg()))
        assert len(hass.services.calls)==1
        await driver.async_stop()
    asyncio.run(scenario())
