"""Guard the only currently authorized secondary humidity write: setpoint."""
import asyncio
import importlib
import sys
import types

import pytest
from test_discovery import FakeHass, MockState, adapter
from test_climate_pid import FakeStore


@pytest.fixture
def module(adapter, monkeypatch):
    storage=types.ModuleType("homeassistant.helpers.storage")
    storage.Store=FakeStore
    monkeypatch.setitem(sys.modules,"homeassistant.helpers.storage",storage)
    return importlib.import_module(
        "custom_components.environment_manager.climate_humidity_native")


class Services:
    def __init__(self, hass):
        self.hass=hass
        self.calls=[]
        self.fail=False

    def has_service(self,domain,action):
        return (domain,action)==("humidifier","set_humidity")

    async def async_call(self,domain,action,data,**kwargs):
        self.calls.append((domain,action,data,kwargs))
        if self.fail:
            raise RuntimeError("device did not acknowledge")
        entity=kwargs["target"]["entity_id"]
        self.hass.states.get(entity).attributes["humidity"]=data["humidity"]


def home(device_state="on", sensor_age=0):
    humidity=MockState("sensor.room_humidity",72,device_class="humidity",
                       unit="%",hours_old=sensor_age)
    dehum=MockState("humidifier.dehum",device_state,device_class="dehumidifier")
    dehum.attributes.update({"humidity":50,"min_humidity":30,"max_humidity":80,
                             "target_humidity_step":1})
    humid=MockState("humidifier.hum","off",device_class="humidifier")
    humid.attributes.update({"humidity":42,"min_humidity":30,"max_humidity":80,
                             "target_humidity_step":1})
    h=FakeHass([humidity,dehum,humid],
               {i.entity_id:"living" for i in (humidity,dehum,humid)})
    h.services=Services(h)
    h.async_create_task=asyncio.create_task
    return h


def config(**changes):
    return {"enabled":True,"allow_actuation":True,
            "humidity_setpoint_auto":True,
            "humidity_entity":"sensor.room_humidity",
            "dehumidifier_entity":"humidifier.dehum",
            "humidifier_entity":"humidifier.hum",
            "humidity_low_rh":40,"humidity_high_rh":60,
            "humidity_hysteresis_rh":3,**changes}


def report():
    return {"window_safe":True,
            "equipment_plan":{"status":"ready",
                "moisture":{"status":"selected","action":"dry",
                            "entity_id":"humidifier.dehum",
                            "role":"dehumidifier_entity"}}}


async def flush():
    for _ in range(8):
        await asyncio.sleep(0)


def test_target_bound_and_uncertain_limits_fail_closed(module):
    assert module._bounded_setpoint(
        {"min_humidity":30,"max_humidity":80,"target_humidity_step":1},
        50,60)==("command",55)
    assert module._bounded_setpoint({"min_humidity":30,"max_humidity":80},
                                     50,60)[0]=="device_limits_or_resolution_unknown"
    assert module._target({"humidity":50,"target_humidity":55}) is None
    assert module._target({}) is None


def test_optin_required_and_only_one_native_setpoint_written(module):
    async def scenario():
        h=home()
        t=[1000.]
        ctrl=module.HumiditySetpointControl(h,"x",clock=lambda:t[0])
        await ctrl.async_start()
        t[0]=1400
        ctrl.schedule({"living":config(humidity_setpoint_auto=False)},
                      {"living":report()})
        assert not h.services.calls
        assert ctrl.statuses["living"]["status"]=="advisory_only"
        ctrl.schedule({"living":config()},{"living":report()})
        await flush()
        assert len(h.services.calls)==1
        assert h.services.calls[0][0:3]==(
            "humidifier","set_humidity",{"humidity":55})
        assert h.services.calls[0][3]["target"]=={"entity_id":"humidifier.dehum"}
        assert ctrl.expected["living"]["target"]==55
        assert ctrl.statuses["living"]["status"]=="target_commanded"
        await ctrl.async_stop()
    asyncio.run(scenario())


def test_does_not_turn_on_off_device_or_unverified_sensor(module):
    async def scenario():
        h=home(device_state="off")
        t=[1400.]
        ctrl=module.HumiditySetpointControl(h,"x",clock=lambda:t[0])
        await ctrl.async_start()
        t[0]=1800
        await ctrl._apply("living",config(),report(),t[0])
        assert not h.services.calls
        assert ctrl.statuses["living"]["status"]=="device_off_no_automatic_start"
        h.states.get("humidifier.dehum").state="on"
        await ctrl._apply("living",config(humidity_entity=None),report(),t[0])
        assert ctrl.statuses["living"]["status"]=="explicit_fresh_humidity_sensor_required"
        await ctrl.async_stop()
    asyncio.run(scenario())


def test_manual_override_latches_until_resume(module):
    async def scenario():
        h=home()
        t=[1000.]
        ctrl=module.HumiditySetpointControl(h,"x",clock=lambda:t[0])
        await ctrl.async_start()
        t[0]=1400
        await ctrl._apply("living",config(),report(),t[0])
        assert ctrl.expected["living"]["target"]==55
        h.states.get("humidifier.dehum").attributes["humidity"]=45
        t[0]=1600
        await ctrl._apply("living",config(),report(),t[0])
        assert ctrl.paused["living"]=="manual_setpoint_change_or_unacknowledged_write"
        assert len(h.services.calls)==1
        assert (await ctrl.command("living","resume"))["accepted"]
        assert "living" not in ctrl.paused
        await ctrl.async_stop()
    asyncio.run(scenario())


def test_dehumidifier_timeout_and_cross_room_ownership(module):
    async def scenario():
        h=home()
        t=[1000.]
        ctrl=module.HumiditySetpointControl(h,"x",clock=lambda:t[0])
        await ctrl.async_start()
        t[0]=1400
        h.services.fail=True
        await ctrl._apply("living",config(),report(),t[0])
        assert ctrl.paused["living"]=="humidity_service_failure"
        assert len(h.services.calls)==1
        await ctrl.command("living","resume")
        t[0]=1800
        h.services.fail=False
        ctrl.schedule({"living":config(),
                       "kitchen":{"enabled":True,
                                  "dehumidifier_entity":"humidifier.dehum"}},
                      {"living":report()})
        assert ctrl.statuses["living"]["status"]=="duplicate_equipment_owner"
        assert len(h.services.calls)==1
        await ctrl.async_stop()
    asyncio.run(scenario())
