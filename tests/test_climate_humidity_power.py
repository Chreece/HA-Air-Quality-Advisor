"""Native humidity power can operate only explicitly attested, owned devices."""
import asyncio
import importlib
import sys
import types

import pytest

from test_climate_pid import FakeStore
from test_discovery import FakeHass, MockState, adapter


@pytest.fixture
def driver(adapter, monkeypatch):
    storage = types.ModuleType("homeassistant.helpers.storage")
    storage.Store = FakeStore
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.storage", storage)
    return importlib.import_module(
        "custom_components.enviroment_manager.climate_humidity_power"
    )


class Services:
    def __init__(self, hass):
        self.hass = hass
        self.calls = []
        self.ack = True
        self.fail = False

    def has_service(self, domain, service):
        return domain == "humidifier" and service in ("turn_on","turn_off")

    async def async_call(self, domain, service, data, **kwargs):
        self.calls.append((domain, service, data, kwargs))
        if self.fail:
            raise RuntimeError("remote device unavailable")
        if self.ack:
            self.hass.states.get(kwargs["target"]["entity_id"]).state = (
                "on" if service == "turn_on" else "off"
            )


def home(rh=75, device_on=False, window=True):
    humidity=MockState("sensor.bedroom_humidity",rh,
                       device_class="humidity",unit="%")
    dry=MockState("humidifier.bedroom_dehumidifier",
                  "on" if device_on else "off",device_class="dehumidifier")
    dry.attributes.update({"humidity":60,"min_humidity":35,
                           "max_humidity":75,"target_humidity_step":1})
    humid=MockState("humidifier.bedroom_humidifier","off",
                    device_class="humidifier")
    humid.attributes.update({"humidity":40,"min_humidity":30,
                             "max_humidity":70,"target_humidity_step":1})
    contacts=[MockState("binary_sensor.bedroom_window","off",
                        device_class="window")] if window else []
    states=[humidity,dry,humid,*contacts]
    hass=FakeHass(states,{s.entity_id:"bedroom" for s in states})
    hass.services=Services(hass)
    hass.async_create_task=asyncio.create_task
    return hass


def cfg(**updates):
    return {"enabled":True,"allow_actuation":True,
            "humidity_power_auto":True,
            "humidity_power_hardware_confirmed":True,
            "humidity_power_min_on_s":600,
            "humidity_power_min_off_s":600,
            "humidity_power_max_on_s":7200,
            "humidity_power_windowless_confirmed":False,
            "humidity_setpoint_auto":False,
            "humidity_entity":"sensor.bedroom_humidity",
            "humidity_low_rh":40,"humidity_high_rh":60,
            "humidity_hysteresis_rh":3,
            "dehumidifier_entity":"humidifier.bedroom_dehumidifier",
            "humidifier_entity":"humidifier.bedroom_humidifier",
            **updates}


def plan(window=True,moisture=True):
    entity="humidifier.bedroom_dehumidifier"
    return {"window_safe":True,
            "window_contacts":(["binary_sensor.bedroom_window"] if window else []),
            "equipment_plan":{"status":"ready",
                "moisture":{"status":"selected","action":"dry",
                            "role":"dehumidifier_entity","entity_id":entity}
                if moisture else {"status":"within_band"}}}


async def tick(driver, config, report):
    driver.schedule({"bedroom":config},{"bedroom":report})
    for _ in range(8):
        await asyncio.sleep(0)


def test_defaults_and_hardware_attestation_gate(driver):
    async def run():
        hass=home()
        t=[1000.]
        c=driver.HumidityPowerControl(hass,"attestation",clock=lambda:t[0])
        await c.async_start()
        t[0]=1400
        await tick(c,cfg(humidity_power_auto=False),plan())
        assert c.statuses["bedroom"]["status"]=="advisory_only"
        await tick(c,cfg(humidity_power_hardware_confirmed=False),plan())
        assert not hass.services.calls
        await c.async_stop()
    asyncio.run(run())


def test_only_owned_device_on_after_off_dwell_and_then_safe_off(driver):
    async def run():
        hass=home()
        t=[1000.]
        c=driver.HumidityPowerControl(hass,"cycle",clock=lambda:t[0])
        await c.async_start()
        t[0]=1400
        await tick(c,cfg(),plan())
        assert c.statuses["bedroom"]["status"]=="minimum_off_hold"
        assert not hass.services.calls
        t[0]=2000
        await tick(c,cfg(),plan())
        assert len(hass.services.calls)==1
        assert hass.services.calls[0][:3]==("humidifier","turn_on",{})
        assert hass.services.calls[0][3]["target"]=={
            "entity_id":"humidifier.bedroom_dehumidifier"}
        assert c.records["bedroom"]["power"]=="on"
        # RH 61 is below start threshold but still in drying hysteresis.
        hass.states.get("sensor.bedroom_humidity").state="61"
        t[0]=2200
        await tick(c,cfg(),plan(moisture=False))
        assert len(hass.services.calls)==1
        assert c.statuses["bedroom"]["status"]=="owned_running"
        hass.states.get("sensor.bedroom_humidity").state="56"
        t[0]=2400
        await tick(c,cfg(),plan(moisture=False))
        assert c.statuses["bedroom"]["status"]=="minimum_on_hold_before_safe_off"
        t[0]=2601
        await tick(c,cfg(),plan(moisture=False))
        assert hass.services.calls[-1][:3]==("humidifier","turn_off",{})
        assert len(hass.services.calls)==2
        t[0]=2650
        await tick(c,cfg(),plan(moisture=False))
        assert "bedroom" not in c.records
        await c.async_stop()
    asyncio.run(run())


def test_manual_start_is_not_owned_or_switched_off(driver):
    async def run():
        hass=home(device_on=True)
        t=[1000.]
        c=driver.HumidityPowerControl(hass,"manual-on",clock=lambda:t[0])
        await c.async_start()
        t[0]=1400
        await tick(c,cfg(),plan())
        assert c.paused["bedroom"]=="external_power_on_not_owned"
        assert not hass.services.calls
        await c.async_stop()
    asyncio.run(run())


def test_window_and_sensor_fail_closed_even_when_cached_plan_was_safe(driver):
    async def run():
        hass=home()
        t=[1000.]
        c=driver.HumidityPowerControl(hass,"window",clock=lambda:t[0])
        await c.async_start()
        t[0]=1400
        await tick(c,cfg(),plan())
        t[0]=2000
        hass.states.get("binary_sensor.bedroom_window").state="on"
        await tick(c,cfg(),plan())
        assert c.statuses["bedroom"]["status"]=="window_open_or_unavailable"
        assert not hass.services.calls
        hass.states.get("binary_sensor.bedroom_window").state="off"
        hass.states.get("sensor.bedroom_humidity").state="unavailable"
        await tick(c,cfg(),plan())
        assert c.statuses["bedroom"]["status"]=="humidity_sensor_stale"
        assert not hass.services.calls
        await c.async_stop()
    asyncio.run(run())


def test_compressor_target_guard_and_opposing_humidifier(driver):
    async def run():
        hass=home()
        t=[1000.]
        c=driver.HumidityPowerControl(hass,"limits",clock=lambda:t[0])
        await c.async_start()
        t[0]=1400
        await tick(c,cfg(),plan())
        t[0]=2000
        hass.states.get("humidifier.bedroom_dehumidifier").attributes["humidity"]=35
        await tick(c,cfg(),plan())
        assert c.statuses["bedroom"]["status"]=="native_target_must_be_commissioned"
        hass.states.get("humidifier.bedroom_dehumidifier").attributes["humidity"]=60
        hass.states.get("humidifier.bedroom_humidifier").state="on"
        await tick(c,cfg(),plan())
        assert c.statuses["bedroom"]["status"]=="opposing_humidity_output_on_or_unknown"
        assert not hass.services.calls
        await c.async_stop()
    asyncio.run(run())


def test_power_ack_timeout_latches_pause_without_retries(driver):
    async def run():
        hass=home()
        hass.services.ack=False
        t=[1000.]
        c=driver.HumidityPowerControl(hass,"no-ack",clock=lambda:t[0])
        await c.async_start()
        t[0]=1400
        await tick(c,cfg(),plan())
        t[0]=2000
        await tick(c,cfg(),plan())
        assert len(hass.services.calls)==1
        t[0]=2150
        await tick(c,cfg(),plan())
        assert c.paused["bedroom"]=="manual_power_or_failed_ack"
        t[0]=2600
        await tick(c,cfg(),plan())
        assert len(hass.services.calls)==1
        await c.async_stop()
    asyncio.run(run())


def test_user_pause_off_only_after_minimum_on_and_no_restart(driver):
    async def run():
        hass=home()
        t=[1000.]
        c=driver.HumidityPowerControl(hass,"pause",clock=lambda:t[0])
        await c.async_start()
        t[0]=1400
        await tick(c,cfg(),plan())
        t[0]=2000
        await tick(c,cfg(),plan())
        assert (await c.command("bedroom","pause"))["accepted"]
        t[0]=2200
        await tick(c,cfg(),plan())
        assert hass.states.get("humidifier.bedroom_dehumidifier").state=="on"
        t[0]=2601
        await tick(c,cfg(),plan())
        assert hass.states.get("humidifier.bedroom_dehumidifier").state=="off"
        t[0]=2650
        await tick(c,cfg(),plan())
        assert not c.records
        await tick(c,cfg(),plan())
        assert len(hass.services.calls)==2
        await c.async_stop()
    asyncio.run(run())


def test_restart_with_active_owned_output_requires_manual_reconciliation(driver,monkeypatch):
    async def run():
        hass=home()
        t=[1000.]
        snapshots={}
        storage=sys.modules["homeassistant.helpers.storage"]
        class SharedStore(FakeStore):
            def __init__(self,*args):
                self.key=args[-1]
            async def async_load(self):
                return snapshots.get(self.key)
            def async_delay_save(self,fn,delay):
                snapshots[self.key]=fn()
            async def async_save(self,value):
                snapshots[self.key]=value
        monkeypatch.setattr(storage,"Store",SharedStore)
        c=driver.HumidityPowerControl(hass,"restart",clock=lambda:t[0])
        await c.async_start()
        t[0]=1400
        await tick(c,cfg(),plan())
        t[0]=2000
        await tick(c,cfg(),plan())
        await c.async_stop()
        assert hass.states.get("humidifier.bedroom_dehumidifier").state=="on"
        replacement=driver.HumidityPowerControl(hass,"restart",clock=lambda:t[0])
        await replacement.async_start()
        assert replacement.paused["bedroom"]=="restart_requires_manual_output_reconciliation"
        t[0]=4000
        await tick(replacement,cfg(),plan())
        assert len(hass.services.calls)==1  # no command after restart
        assert not (await replacement.command("bedroom","resume"))["accepted"]
        hass.states.get("humidifier.bedroom_dehumidifier").state="off"
        assert (await replacement.command("bedroom","resume"))["accepted"]
        t[0]=4500
        await tick(replacement,cfg(),plan())
        assert len(hass.services.calls)==1
        await replacement.async_stop()
    asyncio.run(run())


def test_no_hardware_commands_for_conflicting_room_owner(driver):
    async def run():
        hass=home()
        t=[1000.]
        c=driver.HumidityPowerControl(hass,"dup",clock=lambda:t[0])
        await c.async_start()
        t[0]=1400
        await tick(c,cfg(),plan())
        t[0]=2000
        c.schedule({"bedroom":cfg(),
                    "kitchen":{"dehumidifier_entity":"humidifier.bedroom_dehumidifier",
                               "enabled":True}},{"bedroom":plan()})
        for _ in range(8):
            await asyncio.sleep(0)
        assert not hass.services.calls
        assert c.statuses["bedroom"]["status"]=="duplicate_humidity_device_owner"
        await c.async_stop()
    asyncio.run(run())


def test_real_ha_last_changed_blocks_recent_manual_toggle(driver):
    async def run():
        from datetime import datetime,timezone
        hass=home()
        t=[1000.]
        c=driver.HumidityPowerControl(hass,"manual-recent-toggle",
                                     clock=lambda:t[0])
        await c.async_start()
        t[0]=1400
        await tick(c,cfg(),plan())
        # Even after 600 seconds of apparent OFF observations, Home
        # Assistant reports a real state transition three minutes ago.
        t[0]=2000
        hass.states.get("humidifier.bedroom_dehumidifier").last_changed=(
            datetime.fromtimestamp(1820,timezone.utc))
        await tick(c,cfg(),plan())
        assert c.statuses["bedroom"]["status"]=="minimum_native_device_off_hold"
        assert not hass.services.calls
        t[0]=2500
        await tick(c,cfg(),plan())
        assert hass.services.calls[0][1]=="turn_on"
        await c.async_stop()
    asyncio.run(run())


def test_power_owner_refuses_live_competing_cooling_after_shared_plan(driver):
    async def scenario():
        from custom_components.enviroment_manager.climate_arbitration import (
            room_coordination,
        )
        hass=home(rh=66)
        cooling=MockState("climate.bedroom_ac","off")
        cooling.attributes.update({"hvac_modes":["off","cool"],
                                   "supported_features":1,"hvac_action":"idle"})
        hass._values[cooling.entity_id]=cooling
        hass._entity_areas[cooling.entity_id]="bedroom"
        config=cfg(cool_climate_entity=cooling.entity_id)
        report=plan()
        report["status"]="advisory"
        report["equipment_plan"]["humidity"]={
            "status":"advisory","action":"dry","measured_rh":66,
        }
        t=[1000.]
        owner=driver.HumidityPowerControl(
            hass,"coordinated-dry",clock=lambda:t[0],
        )
        await owner.async_start()
        t[0]=1400
        report["coordination"]=room_coordination(
            hass,"bedroom",config,report,now=1400,
        )
        assert report["coordination"]["channels"]["humidity"]["status"]=="eligible"
        await tick(owner,config,report)
        t[0]=2000
        cooling.state="cool"  # Auto-climate armed after initial plan.
        await tick(owner,config,report)
        assert owner.statuses["bedroom"]=={
            "status":"coordination_hold",
            "reason":"cooling_priority_observe_rh",
        }
        assert not hass.services.calls
        cooling.state="off"
        await tick(owner,config,report)
        assert hass.services.calls[0][1]=="turn_on"
        await owner.async_stop()
    asyncio.run(scenario())



def test_owned_humidity_output_survives_removed_config_without_shortening_dwell(driver):
    async def scenario():
        hass=home()
        clock=[1000.]
        control=driver.HumidityPowerControl(
            hass,"removed-room",clock=lambda:clock[0],
        )
        await control.async_start()
        original=cfg(humidity_power_min_on_s=1500,
                     humidity_power_min_off_s=600,
                     humidity_power_max_on_s=2700)
        clock[0]=1400
        await tick(control,original,plan())
        clock[0]=2050
        await tick(control,original,plan())
        assert [event[1] for event in hass.services.calls]==["turn_on"]
        assert control.records["bedroom"]["min_on_s"]==1500
        assert control.records["bedroom"]["max_on_s"]==2700
        # Options room removed while the actual humidifier is powered ON.
        # This must still inspect owned output and enforce original 1500 s,
        # rather than silently drop the record or use default 600 s.
        clock[0]=2750
        control.schedule({}, {})
        for _ in range(8):
            await asyncio.sleep(0)
        assert [event[1] for event in hass.services.calls]==["turn_on"]
        assert control.statuses["bedroom"]["status"]=="minimum_on_hold_before_safe_off"
        clock[0]=3551
        control.schedule({}, {})
        for _ in range(8):
            await asyncio.sleep(0)
        assert [event[1] for event in hass.services.calls]==["turn_on","turn_off"]
        clock[0]=3580
        control.schedule({}, {})
        for _ in range(8):
            await asyncio.sleep(0)
        assert "bedroom" not in control.records
        await control.async_stop()
    asyncio.run(scenario())


def test_humidity_power_options_edit_does_not_change_owned_compressor_dwell(driver):
    async def scenario():
        hass=home()
        clock=[1000.]
        control=driver.HumidityPowerControl(
            hass,"dwell-edit",clock=lambda:clock[0],
        )
        await control.async_start()
        original=cfg(humidity_power_min_on_s=1500,
                     humidity_power_max_on_s=2400)
        clock[0]=1400
        await tick(control,original,plan())
        clock[0]=2050
        await tick(control,original,plan())
        # New settings cannot cut an existing run short, even when someone
        # sets a new (otherwise allowed) 600-second min on duration.
        changed=cfg(humidity_power_min_on_s=600,
                    humidity_power_max_on_s=900,
                    enabled=False)
        clock[0]=2700
        await tick(control,changed,plan())
        assert [event[1] for event in hass.services.calls]==["turn_on"]
        clock[0]=3551
        await tick(control,changed,plan())
        assert [event[1] for event in hass.services.calls]==["turn_on","turn_off"]
        await control.async_stop()
    asyncio.run(scenario())


def test_humidity_legacy_active_record_without_dwell_fails_closed_when_removed(driver):
    async def scenario():
        hass=home(device_on=True)
        clock=[2000.]
        control=driver.HumidityPowerControl(
            hass,"legacy-removed",clock=lambda:clock[0],
        )
        await control.async_start()
        control.records["bedroom"]={
            "entity_id":"humidifier.bedroom_dehumidifier",
            "role":"dehumidifier_entity","area":"bedroom",
            "power":"on","when":1000,"acknowledged":True,"target":60,
        }
        control.schedule({}, {})
        for _ in range(8):
            await asyncio.sleep(0)
        assert control.paused["bedroom"]=="original_power_dwell_unknown_reconcile_manually"
        assert not hass.services.calls
        await control.async_stop()
    asyncio.run(scenario())
