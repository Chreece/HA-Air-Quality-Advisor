"""Per-device control, facade, PID and ownership regression tests (no hardware)."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from enum import IntFlag, StrEnum
import importlib
import sys
import types
from types import SimpleNamespace

import pytest

from test_discovery import FakeHass, MockState, adapter
from custom_components.environment_manager.device_hierarchy import ManagedDevice
from custom_components.environment_manager import equipment_model as m


class Store:
    def __init__(self):
        self.value = None
        self.saved = []
        self.fail = False
        self.hook = None

    async def async_save(self, data):
        if self.fail:
            raise OSError("storage failed")
        self.value = deepcopy(data)
        self.saved.append(deepcopy(data))
        if self.hook:
            callback, self.hook = self.hook, None
            callback()

    async def async_load(self):
        return deepcopy(self.value)


class Services:
    def __init__(self, hass, store):
        self.hass, self.store = hass, store
        self.calls = []
        self.ack = True
        self.fail = False
        self.before = None
        self.delayed = None

    def has_service(self, domain, action):
        return action in {"turn_on", "turn_off", "set_hvac_mode", "set_temperature", "set_humidity", "set_percentage", "set_fan_mode", "set_preset_mode", "set_swing_mode", "set_swing_horizontal_mode", "set_value"}

    async def async_call(self, domain, action, data, *, target, blocking):
        entity = target["entity_id"]
        intents = [r.get("pending") for r in self.store.value["records"].values()]
        assert any(p and p["phase"] == "intent" and p["entity"] == entity for p in intents), "Must persist exact intent BEFORE dispatch"
        assert isinstance(entity, str) and "," not in entity and blocking
        self.calls.append((domain, action, dict(data), entity))
        if self.before:
            self.before()
        if self.delayed:
            await self.delayed.wait()
        if self.fail:
            raise RuntimeError("physical service error")
        if not self.ack:
            return
        state = self.hass.states.get(entity)
        if action in ("turn_on", "turn_off"):
            state.state = "on" if action == "turn_on" else "off"
        elif action == "set_hvac_mode":
            state.state = data["hvac_mode"]
        elif action == "set_value":
            state.state = str(data["value"])
        else:
            state.attributes.update(data)


@pytest.fixture
def runtime_module(adapter, monkeypatch):
    dispatcher = types.ModuleType("homeassistant.helpers.dispatcher")
    dispatcher.async_dispatcher_send = lambda *a: None
    dispatcher.async_dispatcher_connect = lambda *a: lambda: None
    monkeypatch.setitem(sys.modules, dispatcher.__name__, dispatcher)
    monkeypatch.delitem(sys.modules, "custom_components.environment_manager.equipment_runtime", raising=False)
    return importlib.import_module("custom_components.environment_manager.equipment_runtime")


def home(module, *, domain="fan", state="off", device_class=None, speed=True,
         mode="automatic", power=True, controls=None, **device_changes):
    entity = f"{domain}.room"
    actuator = MockState(entity, state, device_class=device_class)
    if domain == "fan":
        actuator.attributes.update(supported_features=1 if speed else 0, percentage=60, percentage_step=10)
    elif domain == "climate":
        actuator.attributes.update(supported_features=1 | 8 | 32 | 512,
            hvac_modes=["off", "heat", "cool", "dry", "fan_only"], temperature=20,
            temperature_unit="°C", min_temp=5, max_temp=35, target_temp_step=.5,
            fan_modes=["low", "medium", "high"], fan_mode="high",
            swing_modes=["off", "on"], swing_mode="off",
            swing_horizontal_modes=["off", "on"], swing_horizontal_mode="off", hvac_action="idle")
    elif domain == "humidifier":
        actuator.attributes.update(device_class=device_class or "dehumidifier", humidity=60,
                                   min_humidity=20, max_humidity=80)
    elif domain == "number":
        actuator.attributes.update(unit_of_measurement="%", min=0, max=100, step=1)
    sensor_values = [MockState("sensor.temp", 15, device_class="temperature", unit="°C"),
                     MockState("sensor.rh", 70, device_class="humidity", unit="%"),
                     MockState("sensor.co2", 1600, device_class="co2", unit="ppm"),
                     MockState("sensor.pm25", 50, device_class="pm25", unit="µg/m³"),
                     MockState("binary_sensor.window", "off", device_class="window")]
    hass = FakeHass([actuator, *sensor_values], {s.entity_id: "room" for s in [actuator, *sensor_values]})
    hass._entity_devices[entity] = "native-device"
    hass._device_areas["native-device"] = "room"
    store = Store()
    hass.services = Services(hass, store)
    hass.async_create_task = asyncio.create_task
    spec = ManagedDevice("entry_controller_one", "room", "Room equipment", "native-device", (entity,))
    clock = [10000.]
    role = {"fan": "extraction_fan_entity", "climate": "climate_entity", "humidifier": "dehumidifier_entity",
            "switch": "heat_actuator", "number": "heat_actuator"}[domain]
    dev = {"auto_control": True, "hardware_confirmed": power,
           "method": ("native" if domain == "climate" else "power") if power else "speed" if domain == "fan" else "setpoint",
           "presence_requirement": "always", "sleep_behavior": "normal", "absence_action": "hold",
           "temperature_entity": "sensor.temp", "humidity_entity": "sensor.rh", "co2_entity": "sensor.co2",
           "pm25_entity": "sensor.pm25", "fan_purpose": "extraction", "sensor_verified": True,
           "min_on_s": 600, "min_off_s": 600, "max_on_s": 7200, "fan_speed_percent": 60,
           "humidity_target": 60, "sleep_humidity_target": 55, **device_changes}
    room = {"enabled": True, "allow_actuation": True, "controller": "device" if domain == "climate" else "environment",
            role: entity, "selected_devices": [entity], "device_settings": {entity: dev},
            "temperature_entity": "sensor.temp", "humidity_entity": "sensor.rh", "co2_entity": "sensor.co2",
            "pm25_entity": "sensor.pm25", "pm25_sensor_verified": True}
    if domain in ("number", "switch"):
        room.update(controller="proportional" if domain == "number" else "pwm", direct_hardware_confirmed=True)
    cfg = {**m.DEFAULTS, "control_mode": mode, **(controls or {})}
    entry = SimpleNamespace(entry_id="entry", data={"areas": ["room"], "climate_rooms": {"room": room},
        m.SETTINGS: {spec.identifier: cfg}}, options={})
    hass.config_entries = SimpleNamespace(async_update_entry=lambda e, **kw: vars(e).update(kw), async_entries=lambda _: [entry])
    plan = {"status": "ready", "mode": "heat", "profile": "home", "window_safe": True,
            "window_contacts": ["binary_sensor.window"], "temperature_c": 15,
            "occupancy": "occupied", "occupancy_evidence": "verified_room_occupied", "away": "home", "sleeping": False,
            "air_evidence_at": clock[0], "air_actions": {"outdoor_air_verified": True,
            "thresholds": {"co2_operational_ppm": 1000, "pm25_short_term_action_ug_m3": 35}}}
    class Manager:
        _active = False
        @property
        def settings(self):
            return {**self.entry.data, **self.entry.options}
        def _recalculate(self, **kwargs):
            pass
    manager = Manager()
    manager.hass, manager.entry = hass, entry
    manager.plan = SimpleNamespace(environment={"room": {"climate_plan": plan}})
    manager._device_hierarchy = {"controllers": {spec.identifier: {"spec": spec, "device_id": "logical-device"}}}
    runtime = module.EquipmentRuntime(manager, clock=lambda: clock[0])
    runtime._ready, runtime._active, runtime._started, runtime._store = True, True, 0, store
    manager.equipment = runtime
    entry.runtime_data = manager
    hass.data = {"environment_manager": {"entry": manager}}
    runtime._record(spec)["off_at"][entity] = 0
    return SimpleNamespace(manager=manager, runtime=runtime, spec=spec, cap=m.capabilities(manager, spec),
                           hass=hass, store=store, clock=clock, plan=plan, room=room, dev=dev,
                           cfg=cfg, entity=entity, state=actuator)


async def tick(h, *, advance=0):
    h.clock[0] += advance
    h.plan["air_evidence_at"] = h.clock[0]
    await h.runtime.tick(h.spec)


def test_capabilities_use_native_modes_and_no_fake_thermal_fan(runtime_module):
    h = home(runtime_module, speed=False)
    cap = m.capabilities(h.manager, h.spec)
    assert cap.modes == ("off", "fan_only")
    assert not cap.temperature and not cap.humidity and not cap.fan_modes
    h = home(runtime_module, domain="climate")
    h.state.attributes["hvac_modes"] = ["off", "heat"]
    cap = m.capabilities(h.manager, h.spec)
    assert "cool" not in cap.modes
    assert cap.swing_horizontal_modes == ("off", "on")


@pytest.mark.parametrize("increasing,value,target", [(True, 15., 20.), (False, 70., 55.), (False, 1600., 1000.)])
def test_dimension_independent_pid_and_anti_windup(increasing, value, target):
    result = m.pid_step(value, target, 1000., increasing=increasing, kp=10., ki=.1, kd=0., sample=120.)
    assert 0 < result.demand <= 100
    for t in range(1120, 4000, 120):
        result = m.pid_step(value, target, float(t), increasing=increasing, kp=10., ki=.1, kd=0., sample=120., memory=result)
    assert -100 <= result.integral <= 100
    assert 0 <= result.demand <= 100
    held = m.pid_step(value, target, result.stamp+1, increasing=increasing, kp=10., ki=.1, kd=0., sample=120., memory=result)
    assert held is result
    invalid = m.pid_step(float("nan"), target, 5000., increasing=increasing, kp=10., ki=.1, kd=0., sample=120.)
    assert invalid.demand == 0


def test_duty_limits_skip_tiny_and_late_pulses():
    assert not m.duty_on(1, 0, 3600, 600, 600)
    assert m.duty_on(50, 0, 3600, 600, 600)
    assert not m.duty_on(50, 1900, 3600, 600, 600)
    assert not m.duty_on(50, 1500, 3600, 600, 600, starting=True)
    assert m.duty_on(50, 1500, 3600, 600, 600)
    assert not m.duty_on(100, 0, 1000, 600, 600)


@pytest.mark.parametrize("domain", ["fan", "humidifier", "climate", "switch"])
def test_power_demand_exact_target_and_durable_intent(runtime_module, domain):
    async def run():
        h = home(runtime_module, domain=domain)
        await tick(h)
        assert len(h.hass.services.calls) == 1
        assert h.hass.services.calls[0][3] == h.entity
        assert h.runtime.records[h.spec.identifier]["pending"]["phase"] == "commanded"
        await tick(h, advance=1)
        assert h.entity in h.runtime.records[h.spec.identifier]["power"]
    asyncio.run(run())


@pytest.mark.parametrize("domain", ["fan", "humidifier", "climate"])
def test_binary_pid_controls_supported_equipment(runtime_module, domain):
    async def run():
        h = home(runtime_module, domain=domain, mode="pid", speed=False, controls={"kp": 20., "ki": .1})
        await tick(h)
        assert h.hass.services.calls
        assert h.hass.services.calls[0][1] in ("turn_on", "set_hvac_mode")
        await tick(h, advance=1)
        # Demand resolves but does not violate the physical minimum ON duration.
        metric = "sensor.co2" if domain == "fan" else "sensor.rh" if domain == "humidifier" else "sensor.temp"
        h.hass.states.get(metric).state = "400" if domain == "fan" else "20" if domain == "humidifier" else "30"
        before = len(h.hass.services.calls)
        await tick(h, advance=300)
        assert not any(call[1] == "turn_off" or call[2].get("hvac_mode") == "off" for call in h.hass.services.calls[before:])
    asyncio.run(run())


def test_controller_distinguishes_no_demand_from_pid_duty_idle(runtime_module):
    async def scenario():
        automatic = home(runtime_module, domain="climate", mode="automatic")
        automatic.hass.states.get("sensor.temp").state = "20"
        await tick(automatic)
        assert automatic.hass.services.calls == []
        assert automatic.runtime.statuses[automatic.spec.identifier]["status"] == "within_target_band"

        pid = home(runtime_module, domain="climate", mode="pid")
        pid.hass.states.get("sensor.temp").state = "19.8"
        await tick(pid)
        assert pid.hass.services.calls == []
        status = pid.runtime.statuses[pid.spec.identifier]
        assert status["status"] == "pid_output_inactive"
        assert 0 < status["demand_percent"] < 100
    asyncio.run(scenario())


def test_uncommissioned_power_never_starts_a_device(runtime_module):
    async def run():
        h = home(runtime_module, power=False)
        await tick(h)
        assert h.hass.services.calls == []
        await h.runtime.async_update(h.spec, {"control_mode": "off"})
        assert h.hass.services.calls == []
    asyncio.run(run())


def test_pid_can_start_without_window_contact_and_blocks_missing_selected_contact(runtime_module):
    async def scenario(selection, should_start):
        h = home(runtime_module, domain="climate", state="off", mode="pid",
                 controls={"kp": 20., "ki": .1})
        # No previously computed plan: exercise the live fallback used during
        # setup/reconfiguration. An explicitly empty windows list means that
        # the room has no contact interlock, not that a contact is unknown.
        h.manager.plan.environment = {}
        h.manager.entry.data["room_sources"] = {
            "room": {"windows": selection, "temperature": ["sensor.temp"]}
        }
        plan = m.plan_for(h.manager, h.spec)
        assert plan["window_safe"] is should_start
        await tick(h)
        assert bool(h.hass.services.calls) is should_start
        if should_start:
            assert h.hass.services.calls[0][1] == "set_hvac_mode"
            assert h.hass.services.calls[0][2]["hvac_mode"] == "heat"
        else:
            assert h.runtime.statuses[h.spec.identifier]["status"] == "open_or_unknown_window"

    asyncio.run(scenario([], True))
    asyncio.run(scenario(["binary_sensor.missing_window"], False))


def test_selecting_active_control_mode_rearms_and_uses_real_off_age(runtime_module):
    async def run(algorithm):
        h = home(runtime_module, domain="climate", mode="existing")
        # The physical unit has already satisfied its minimum-OFF dwell.
        h.state.last_changed = datetime.fromtimestamp(
            h.clock[0] - 900, tz=timezone.utc
        )
        record = h.runtime._record(h.spec)
        record["paused"] = "physical_manual_override"
        record["off_at"][h.entity] = h.clock[0]  # stale selector-time value

        await h.runtime.async_update(
            h.spec,
            {"control_mode": algorithm},
        )
        saved = m.settings(h.manager, h.spec)
        assert saved["control_mode"] == algorithm
        assert saved["requested_mode"] is None
        assert "paused" not in record
        assert record["off_at"][h.entity] == h.clock[0] - 900

        await tick(h)
        assert h.hass.services.calls
        assert h.hass.services.calls[0][1] == "set_hvac_mode"
        assert h.hass.services.calls[0][2]["hvac_mode"] == "heat"

    asyncio.run(run("automatic"))
    asyncio.run(run("pid"))


def test_mode_selector_is_explicit_exact_device_authorization(runtime_module):
    async def run():
        h = home(runtime_module, mode="existing")
        h.dev["auto_control"] = False
        await h.runtime.async_update(h.spec, {"control_mode": "automatic"})
        assert m.settings(h.manager, h.spec)["control_mode"] == "automatic"
        assert m.permission(h.manager, h.spec, h.cap) == (True, True)
        assert h.dev["auto_control"] is False
        assert not h.hass.services.calls
    asyncio.run(run())


def test_presets_are_independent_and_change_policy_targets(runtime_module):
    h = home(runtime_module, domain="climate")
    old = m.targets(h.manager, h.spec, h.cap, {**h.cfg, "preset": "home"}, h.plan)
    sleep = m.targets(h.manager, h.spec, h.cap, {**h.cfg, "preset": "sleep"}, h.plan)
    away = m.targets(h.manager, h.spec, h.cap, {**h.cfg, "preset": "away"}, h.plan)
    comfort = m.targets(h.manager, h.spec, h.cap, {**h.cfg, "preset": "comfort"}, h.plan)
    assert away["heat"] == 16
    assert away["cool"] == 30
    assert comfort["heat"] > old["heat"]
    assert sleep["heat"] >= away["heat"]
    eco=m.targets(h.manager,h.spec,h.cap,{**h.cfg,"preset":"eco"},h.plan)
    assert eco["heat"] <= old["heat"] and eco["cool"] >= comfort["cool"]


def test_bad_targets_rejected_without_persistence(runtime_module):
    async def run():
        h = home(runtime_module, domain="climate")
        for table in ({"home": {"heat": 40}}, {"home": {"heat": 25, "cool": 25}}, {"bad": {"heat": 10}}):
            with pytest.raises(Exception):
                await h.runtime.async_update(h.spec, {"profile_targets": table})
            assert h.manager.entry.options == {}
        with pytest.raises(Exception, match="cycle"):
            await h.runtime.async_update(h.spec, {"control_mode": "pid", "cycle_seconds": 600})
    asyncio.run(run())


def test_manual_mode_without_request_does_not_operate_equipment(runtime_module):
    async def run():
        h = home(runtime_module, domain="climate", state="heat", mode="manual")
        await tick(h)
        assert h.hass.services.calls == []
        await h.runtime.async_set_targets(h.spec, {"heat": 22})
        await tick(h)
        assert h.hass.services.calls[0][1:3] == ("set_temperature", {"temperature": 22.0})
    asyncio.run(run())


def test_manual_override_latches_and_preset_does_not_clear_it(runtime_module):
    async def run():
        h = home(runtime_module, state="on", power=False)
        await tick(h)
        h.state.attributes["percentage"] = 90
        await tick(h)
        assert h.runtime.records[h.spec.identifier]["paused"] == "physical_manual_override"
        await h.runtime.async_update(h.spec, {"preset": "sleep"})
        await tick(h)
        assert h.runtime.records[h.spec.identifier]["paused"]
    asyncio.run(run())


def test_ack_timeout_and_service_failure_do_not_retry(runtime_module):
    async def run():
        for fail in (False, True):
            h = home(runtime_module)
            h.hass.services.ack, h.hass.services.fail = False, fail
            await tick(h)
            await tick(h, advance=121)
            await tick(h, advance=700)
            assert len(h.hass.services.calls) == 1
            assert h.runtime.records[h.spec.identifier]["paused"]
    asyncio.run(run())


def test_missing_sensor_or_open_window_cannot_start(runtime_module):
    async def run():
        for problem in ("sensor", "window", "outside", "deselected", "moved"):
            h = home(runtime_module)
            if problem == "sensor":
                h.hass.states.get("sensor.co2").state = "unknown"
            if problem == "window":
                h.hass.states.get("binary_sensor.window").state = "on"
            if problem == "outside":
                h.plan["air_actions"]["outdoor_air_verified"] = False
            if problem == "deselected":
                h.room["selected_devices"] = []
            if problem == "moved":
                h.hass._entity_areas[h.entity] = "elsewhere"
            await tick(h)
            assert h.hass.services.calls == [], problem
    asyncio.run(run())


def test_gate_rechecked_after_durable_storage(runtime_module):
    async def run():
        h = home(runtime_module)
        h.store.hook = lambda: setattr(h.hass.states.get("binary_sensor.window"), "state", "on")
        await tick(h)
        assert h.hass.services.calls == []
        assert not h.runtime.records[h.spec.identifier].get("pending")
    asyncio.run(run())


def test_storage_failure_prevents_any_hardware_command(runtime_module):
    async def run():
        h = home(runtime_module)
        h.store.fail = True
        with pytest.raises(Exception, match="persist"):
            await tick(h)
        assert h.hass.services.calls == []
        assert not h.runtime._ready
    asyncio.run(run())


def test_minimum_off_and_minimum_on_are_observed(runtime_module):
    async def run():
        h = home(runtime_module)
        h.runtime._record(h.spec)["off_at"][h.entity] = h.clock[0]
        await tick(h)
        assert not h.hass.services.calls
        await tick(h, advance=600)
        assert h.hass.services.calls[0][1] == "turn_on"
        await tick(h, advance=1)
        h.hass.states.get("sensor.co2").state = "400"
        await tick(h, advance=300)
        assert len(h.hass.services.calls) == 1
        await tick(h, advance=300)
        assert h.hass.services.calls[-1][1] == "turn_off"
    asyncio.run(run())


def test_quiet_sleep_and_occupied_reduce_and_restore_fan(runtime_module):
    async def run():
        for flag, evidence in (("quiet_sleep", "sleeping"), ("quiet_occupied", "occupancy")):
            h = home(runtime_module, state="on", power=False, controls={flag: True})
            h.plan[evidence] = True if evidence == "sleeping" else "occupied"
            await tick(h)
            assert h.hass.services.calls[0][1:3] == ("set_percentage", {"percentage": 30})
            await tick(h, advance=1)
            h.plan[evidence] = False if evidence == "sleeping" else "unoccupied"
            await tick(h, advance=30)
            assert h.hass.services.calls[-1][2]["percentage"] == 60
            assert all(call[1] != "turn_on" for call in h.hass.services.calls)
    asyncio.run(run())


def test_quiet_native_fan_uses_only_advertised_choice(runtime_module):
    async def run():
        h = home(runtime_module, domain="climate", state="heat", power=False,
                 controls={"quiet_sleep": True})
        h.plan["sleeping"] = True
        h.state.attributes["temperature"] = 18
        await tick(h)
        assert h.hass.services.calls[-1][1:3] == ("set_fan_mode", {"fan_mode": "low"})
        with pytest.raises(Exception, match="Unsupported"):
            await h.runtime.async_update(h.spec, {"quiet_fan_mode": "turbo"})
    asyncio.run(run())


def test_legacy_sources_filtered_and_runtime_gate_blocks_old_driver(runtime_module):
    from custom_components.environment_manager.climate_arbitration import new_command_gate
    h = home(runtime_module)
    h.room["purifier_fan_entity"] = "fan.other"
    h.room["selected_devices"].append("fan.other")
    rooms, _ = m.legacy_settings(h.manager)
    assert "extraction_fan_entity" not in rooms["room"]
    assert rooms["room"]["purifier_fan_entity"] == "fan.other"
    assert new_command_gate(h.hass, "room", h.room, h.plan, "extraction", h.entity, entry_id="entry") == "per_device_controller_owns_source"


def test_legacy_ownership_transfer_rejected_while_old_power_owned(runtime_module):
    async def run():
        h = home(runtime_module, mode="existing")
        h.manager.fan_power = SimpleNamespace(owned={h.entity: {}}, _tasks={})
        with pytest.raises(Exception, match="reconcile"):
            await h.runtime.async_update(h.spec, {"control_mode": "automatic"})
        assert h.manager.entry.options == {}
    asyncio.run(run())


def test_restart_requires_explicit_off_reconciliation(runtime_module, monkeypatch):
    async def run():
        h = home(runtime_module)
        await tick(h)
        await tick(h, advance=1)
        storage = types.ModuleType("homeassistant.helpers.storage")
        storage.Store = lambda *args: h.store
        monkeypatch.setitem(sys.modules, storage.__name__, storage)
        restarted = runtime_module.EquipmentRuntime(h.manager, clock=lambda: h.clock[0])
        h.manager.equipment = restarted
        await restarted.async_start()
        assert restarted.records[h.spec.identifier]["paused"] == "restart_reconciliation_required"
        with pytest.raises(Exception, match="OFF"):
            await restarted.async_resume(h.spec)
        h.state.state = "off"
        await restarted.async_resume(h.spec)
        assert not restarted.records[h.spec.identifier]["paused"]
        assert restarted.records[h.spec.identifier]["off_at"][h.entity] == h.clock[0]
    asyncio.run(run())


def test_different_devices_do_not_wait_for_one_another(runtime_module):
    async def run():
        a, b = home(runtime_module), home(runtime_module)
        a.hass.services.delayed = asyncio.Event()
        task = asyncio.create_task(a.runtime._run(a.spec))
        await asyncio.sleep(0)
        await b.runtime._run(b.spec)
        assert b.hass.services.calls and not task.done()
        a.hass.services.delayed.set()
        await task
    asyncio.run(run())


@pytest.mark.parametrize("reason", ["feedback", "config", "capability", "identity", "defrost", "quiet"])
def test_dispatch_revalidates_all_mutable_evidence(runtime_module, reason):
    async def run():
        h = home(runtime_module, domain="climate", state="heat", power=False,
                 controls={"quiet_sleep": True})
        h.state.attributes["temperature"] = 18
        if reason == "feedback":
            hook = lambda: setattr(h.hass.states.get("sensor.temp"), "state", "25")
        elif reason == "config":
            hook = lambda: h.cfg.update(preset="away")
        elif reason == "capability":
            hook = lambda: h.state.attributes.update(supported_features=0)
        elif reason == "identity":
            hook = lambda: h.hass._entity_devices.update({h.entity: "replacement"})
        elif reason == "defrost":
            hook = lambda: h.state.attributes.update(hvac_action="defrosting")
        else:
            hook = lambda: h.plan.update(sleeping=True)
        h.store.hook = hook
        await tick(h)
        assert h.hass.services.calls == []
        assert not h.runtime.records[h.spec.identifier].get("pending")
    asyncio.run(run())


@pytest.mark.parametrize("domain", ["fan", "humidifier", "climate"])
def test_maximum_runtime_requests_off_without_early_restart(runtime_module, domain):
    async def run():
        h = home(runtime_module, domain=domain)
        await tick(h)
        await tick(h, advance=1)
        record = h.runtime.records[h.spec.identifier]
        assert h.entity in record["power"]
        await tick(h, advance=7201)
        assert h.hass.services.calls[-1][1] in ("turn_off", "set_hvac_mode")
        assert h.state.state == "off"
        await tick(h, advance=1)
        size = len(h.hass.services.calls)
        await tick(h, advance=599)
        assert len(h.hass.services.calls) == size
    asyncio.run(run())


@pytest.mark.parametrize("change", ["deselected", "removed_room", "disabled", "unavailable_feedback"])
def test_owned_power_retires_with_original_minimum_run_time(runtime_module, change):
    async def run():
        h = home(runtime_module)
        await tick(h)
        await tick(h, advance=1)
        if change == "deselected":
            h.room["selected_devices"] = []
        elif change == "removed_room":
            h.manager.entry.data["climate_rooms"] = {}
        elif change == "disabled":
            h.dev["auto_control"] = False
        else:
            h.hass.states.get("sensor.co2").state = "unknown"
        await tick(h, advance=30)
        assert h.state.state == "on"
        await tick(h, advance=570)
        assert h.state.state == "off"
        assert h.hass.services.calls[-1][1] == "turn_off"
        await tick(h, advance=1)
        assert h.entity not in h.runtime.records[h.spec.identifier]["power"]
    asyncio.run(run())


def test_owned_retirement_never_targets_replacement_physical_identity(runtime_module):
    async def run():
        h = home(runtime_module)
        await tick(h)
        await tick(h, advance=1)
        h.room["selected_devices"] = []
        h.hass._entity_devices[h.entity] = "different-physical-device"
        await tick(h, advance=8000)
        assert not any(call[1] == "turn_off" for call in h.hass.services.calls)
        assert h.runtime.records[h.spec.identifier]["power"]
    asyncio.run(run())


def test_binary_climate_without_native_setpoints_gets_external_pid(runtime_module):
    async def run():
        h = home(runtime_module, domain="climate", mode="pid")
        h.state.attributes.update(supported_features=0, hvac_modes=["off", "heat"])
        cap = m.capabilities(h.manager, h.spec)
        assert cap.temperature and "pid" in m.control_modes(h.manager, h.spec)
        await tick(h)
        assert h.state.state == "heat"
        await tick(h, advance=1)
        assert all(call[1] != "set_temperature" for call in h.hass.services.calls)
    asyncio.run(run())


def test_dry_only_climate_pid_uses_rh_not_fake_temperature(runtime_module):
    async def run():
        h = home(runtime_module, domain="climate", mode="pid")
        h.state.attributes.update(supported_features=0, hvac_modes=["off", "dry"])
        cap = m.capabilities(h.manager, h.spec)
        assert cap.humidity and not cap.temperature
        await tick(h)
        assert h.hass.services.calls[0][2] == {"hvac_mode": "dry"}
        await tick(h, advance=1)
        assert all(call[1] not in ("set_humidity", "set_temperature") for call in h.hass.services.calls)
    asyncio.run(run())


def test_native_fan_only_pid_can_use_verified_air_quality(runtime_module):
    async def run():
        h = home(runtime_module, domain="climate", mode="pid")
        h.state.attributes.update(supported_features=0, hvac_modes=["off", "fan_only"])
        assert "pid" in m.control_modes(h.manager, h.spec)
        await tick(h)
        assert h.hass.services.calls[0][2] == {"hvac_mode": "fan_only"}
    asyncio.run(run())


def test_native_heat_cool_range_can_start_with_qualified_outside_band(runtime_module):
    async def run():
        h = home(runtime_module, domain="climate")
        h.state.attributes.update(supported_features=2, hvac_modes=["off", "heat_cool"],
                                  target_temp_low=20, target_temp_high=26)
        await tick(h)
        assert h.state.state == "heat_cool"
        assert "pid" not in m.control_modes(h.manager, h.spec)
    asyncio.run(run())


def test_fahrenheit_setpoint_write_converts_and_bounds_rate(runtime_module):
    async def run():
        h = home(runtime_module, domain="climate", state="heat", power=False)
        h.state.attributes.update(temperature_unit="°F", temperature=64.4,
                                  min_temp=41, max_temp=95, target_temp_step=.1)
        await tick(h)
        value = h.hass.services.calls[0][2]["temperature"]
        assert 64.4 < value <= 65.3
        assert 5 == m.capabilities(h.manager, h.spec).min_temp
        assert 35 == m.capabilities(h.manager, h.spec).max_temp
    asyncio.run(run())


def test_proportional_pid_records_ownership_and_shutdown(runtime_module):
    async def run():
        h = home(runtime_module, domain="number", state="0", mode="pid")
        await tick(h)
        assert h.hass.services.calls[0][1:3] == ("set_value", {"value": 10.})
        await tick(h, advance=1)
        record = h.runtime.records[h.spec.identifier]
        assert record["power"][h.entity]["since"] == h.clock[0]
        h.manager.entry.data["climate_rooms"] = {}
        await tick(h, advance=600)
        assert h.hass.services.calls[-1][2] == {"value": 0.}
        await tick(h, advance=1)
        assert not record["power"]
    asyncio.run(run())


def test_manual_fan_selection_does_not_apply_unrequested_temperature(runtime_module):
    async def run():
        h = home(runtime_module, domain="climate", state="heat", mode="manual", power=False,
                 controls={"fan_mode": "low"})
        h.state.attributes["temperature"] = 24
        await tick(h)
        assert h.hass.services.calls[0][1:3] == ("set_fan_mode", {"fan_mode": "low"})
        assert h.state.attributes["temperature"] == 24
    asyncio.run(run())


def test_target_and_mode_edit_atomically_authorizes_native_manual_control(runtime_module):
    async def run():
        h = home(runtime_module, domain="climate", state="heat", mode="existing", power=False)
        await h.runtime.async_set_targets(h.spec, {"cool": 23}, mode="cool")
        saved = h.manager.settings[m.SETTINGS][h.spec.identifier]
        assert saved["control_mode"] == "manual"
        assert saved["requested_mode"] == "cool"
        assert saved["profile_targets"]["manual"]["cool"] == 23
        assert saved.get("_native_authorization")
        assert "allow_power" not in saved
    asyncio.run(run())


def test_quiet_unknown_presence_never_restores_high_speed(runtime_module):
    async def run():
        h = home(runtime_module, state="on", power=False, controls={"quiet_occupied": True})
        await tick(h)
        await tick(h, advance=1)
        h.plan["occupancy"] = "unknown"
        await tick(h, advance=30)
        assert h.state.attributes["percentage"] == 30
        h.state.attributes["percentage_step"] = 25
        # Native capability changes are a manual reconciliation boundary.
        await tick(h)
        assert h.runtime.records[h.spec.identifier]["paused"] == "physical_manual_override"
    asyncio.run(run())


def test_quiet_requires_real_discrete_mode_selection(runtime_module):
    async def run():
        h = home(runtime_module, domain="climate", state="heat", power=False)
        h.state.attributes["fan_modes"] = ["level_1", "level_2"]
        with pytest.raises(Exception, match="quiet fan mode"):
            await h.runtime.async_update(h.spec, {"quiet_sleep": True})
        await h.runtime.async_update(h.spec, {"quiet_fan_mode": "level_1", "quiet_sleep": True})
    asyncio.run(run())


def test_control_transfer_storage_failure_leaves_old_owner_selected(runtime_module):
    async def run():
        h = home(runtime_module, mode="existing")
        h.store.fail = True
        with pytest.raises(Exception, match="persist"):
            await h.runtime.async_update(h.spec, {"control_mode": "automatic"})
        assert h.manager.settings[m.SETTINGS][h.spec.identifier]["control_mode"] == "existing"
    asyncio.run(run())


def test_multi_endpoint_device_retains_all_channels_under_one_child(runtime_module):
    h = home(runtime_module, domain="climate")
    second = MockState("climate.second", "off", name="Second zone")
    second.attributes.update(h.state.attributes)
    h.hass._values[second.entity_id] = second
    h.hass._entity_areas[second.entity_id] = "room"
    h.hass._entity_devices[second.entity_id] = "native-device"
    h.room["selected_devices"].append(second.entity_id)
    h.room["device_settings"][second.entity_id] = dict(h.dev)
    grouped = ManagedDevice(h.spec.identifier, "room", "Physical device", "native-device", (h.entity, second.entity_id))
    h.manager._device_hierarchy["controllers"][grouped.identifier]["spec"] = grouped
    channels = m.specs(h.manager)
    assert len(channels) == 2
    assert {m.device_identifier(c) for c in channels} == {grouped.identifier}
    assert {m.capabilities(h.manager, c).primary for c in channels} == {h.entity, second.entity_id}
    assert h.runtime._lock(channels[0].identifier) is h.runtime._lock(channels[1].identifier)


def test_shared_runtime_different_physical_devices_do_not_block(runtime_module):
    async def run():
        h = home(runtime_module)
        second = MockState("fan.second", "off")
        second.attributes.update(h.state.attributes)
        h.hass._values[second.entity_id] = second
        h.hass._entity_areas[second.entity_id] = "room"
        h.hass._entity_devices[second.entity_id] = "second-device"
        h.hass._device_areas["second-device"] = "room"
        h.room["selected_devices"].append(second.entity_id)
        h.room["device_settings"][second.entity_id] = dict(h.dev)
        spec2 = ManagedDevice("controller_two", "room", "Second fan", "second-device", (second.entity_id,))
        h.manager._device_hierarchy["controllers"][spec2.identifier] = {"spec": spec2, "device_id": "logical-two"}
        h.manager.entry.data[m.SETTINGS][spec2.identifier] = dict(h.cfg)
        h.runtime._record(spec2)["off_at"][second.entity_id] = 0
        release, dispatched = asyncio.Event(), asyncio.Event()
        original = h.hass.services.async_call
        async def dispatch(domain, action, data, **kwargs):
            if kwargs["target"]["entity_id"] == h.entity:
                dispatched.set()
                await release.wait()
            await original(domain, action, data, **kwargs)
        h.hass.services.async_call = dispatch
        first = asyncio.create_task(h.runtime._run(h.spec))
        await dispatched.wait()
        await h.runtime._run(spec2)
        assert second.state == "on" and not first.done()
        release.set()
        await first
    asyncio.run(run())


def test_automatic_power_does_not_adopt_unowned_running_device(runtime_module):
    async def run():
        h = home(runtime_module, state="on", mode="existing")
        await h.runtime.async_update(h.spec, {"control_mode": "automatic"})
        assert m.settings(h.manager, h.spec)["control_mode"] == "automatic"
        await tick(h)
        assert not h.hass.services.calls
        assert not h.runtime.records[h.spec.identifier]["power"]
    asyncio.run(run())


def test_pid_keeps_explicit_dry_mode_on_multimode_native_climate(runtime_module):
    async def run():
        h = home(runtime_module, domain="climate", mode="pid", controls={"requested_mode": "dry"})
        await tick(h)
        assert h.hass.services.calls[0][2] == {"hvac_mode": "dry"}
    asyncio.run(run())


def test_manual_targets_never_follow_presence_or_sleep_changes(runtime_module):
    async def run():
        h=home(runtime_module,domain="climate",state="heat",mode="manual",power=False)
        await h.runtime.async_set_targets(h.spec,{"heat":22})
        await tick(h)
        await tick(h,advance=1)
        h.plan.update(away="away",sleeping=True,occupancy="unoccupied")
        await tick(h,advance=300)
        assert h.state.attributes["temperature"]==22
        assert m.profile_name(m.settings(h.manager,h.spec),h.plan)=="manual"
    asyncio.run(run())


def test_fan_choices_are_saved_per_preset_not_one_global_setting(runtime_module):
    async def run():
        h=home(runtime_module,state="on",power=False,mode="manual",controls={"preset":"home"})
        await h.runtime.async_set_fan(h.spec,"70")
        await tick(h)
        await tick(h,advance=1)
        await h.runtime.async_update(h.spec,{"preset":"sleep"})
        await h.runtime.async_set_fan(h.spec,"30")
        await tick(h)
        await tick(h,advance=1)
        assert h.state.attributes["percentage"]==30
        await h.runtime.async_update(h.spec,{"preset":"home"})
        await tick(h)
        assert h.state.attributes["percentage"]==70
    asyncio.run(run())



def test_unavailable_physical_device_blocks_all_control_calculations(runtime_module, monkeypatch):
    """No capability/policy/target/measurement/PID work runs before availability."""
    async def run():
        h = home(runtime_module, domain="climate", mode="pid")
        h.state.state = "unavailable"
        def forbidden(*args, **kwargs):
            raise AssertionError("control calculation ran before physical availability")
        for name in ("capabilities", "plan_for", "targets", "pid_step"):
            monkeypatch.setattr(m, name, forbidden)
        monkeypatch.setattr(h.runtime, "measurements", forbidden)
        await tick(h)
        assert h.runtime.statuses[h.spec.identifier]["status"] == "waiting_for_physical_device"
        assert h.hass.services.calls == []
        assert h.runtime._memory == {}
    asyncio.run(run())


@pytest.mark.parametrize(
    "policy,allowed_state,blocked_state",
    [("occupied", "occupied", "unoccupied"), ("absent", "unoccupied", "occupied")],
)
def test_per_device_presence_policy_drives_only_in_selected_room_state(
    runtime_module, policy, allowed_state, blocked_state
):
    async def run():
        h = home(runtime_module, controls={"presence_requirement": policy})
        h.plan["occupancy"] = blocked_state
        await tick(h)
        assert h.hass.services.calls == []
        h.plan["occupancy"] = allowed_state
        await tick(h, advance=1)
        assert h.hass.services.calls and h.hass.services.calls[-1][1] == "turn_on"
        await tick(h, advance=1)  # acknowledge ownership
        h.plan["occupancy"] = blocked_state
        await tick(h, advance=600)
        assert h.hass.services.calls[-1][1] == "turn_off"
    asyncio.run(run())


def test_per_device_presence_always_ignores_unknown_occupancy(runtime_module):
    async def run():
        h = home(runtime_module, controls={"presence_requirement": "always"})
        h.plan["occupancy"] = "unknown"
        await tick(h)
        assert h.hass.services.calls and h.hass.services.calls[-1][1] == "turn_on"
    asyncio.run(run())


def test_legacy_room_and_home_presence_settings_migrate_to_strict_occupied(runtime_module):
    for old in ("room", "home"):
        h = home(runtime_module, controls={"presence_requirement": old})
        assert m.settings(h.manager, h.spec)["presence_requirement"] == "occupied"


def test_percentage_fan_limits_override_normal_and_quiet_demands(runtime_module):
    async def run():
        h = home(runtime_module, state="on", power=False, controls={
            "quiet_occupied": True, "quiet_percentage": 20,
        })
        h.manager.entry.data["environment_rooms"] = {
            "room": {"equipment_limits": {"fan_min_percentage": 40, "fan_max_percentage": 50}}
        }
        h.plan["occupancy"] = "occupied"
        await tick(h)
        # Quiet request 20% is below the device minimum, so the minimum wins.
        assert h.hass.services.calls[-1][1:3] == ("set_percentage", {"percentage": 40})
        await tick(h, advance=1)
        h.plan["occupancy"] = "unoccupied"
        await tick(h, advance=30)
        # Normal configured 60% is above the device maximum, so 50% wins.
        assert h.hass.services.calls[-1][1:3] == ("set_percentage", {"percentage": 50})
    asyncio.run(run())


def test_unknown_quiet_context_holds_current_fan_speed_without_command(runtime_module):
    async def run():
        h = home(runtime_module, state="on", power=False, controls={"quiet_occupied": True})
        h.plan["occupancy"] = "unknown"
        before = h.state.attributes["percentage"]
        await tick(h)
        assert h.hass.services.calls == []
        assert h.state.attributes["percentage"] == before
        assert h.runtime.statuses[h.spec.identifier]["status"] == "quiet_context_unknown"
    asyncio.run(run())


def test_temperature_limits_clamp_profile_and_native_write(runtime_module):
    async def run():
        h = home(runtime_module, domain="climate", state="heat", power=False)
        h.room["profiles"] = {"comfort": {"heat_c": 10, "cool_c": 30}}
        h.manager.entry.data["environment_rooms"] = {
            "room": {"equipment_limits": {
                "temperature_min_limit": 19, "temperature_max_limit": 21}}
        }
        h.state.attributes["temperature"] = 30  # native target is already above max
        cap = m.capabilities(h.manager, h.spec)
        values = m.targets(h.manager, h.spec, cap, m.settings(h.manager, h.spec), h.plan)
        assert values["heat"] == 19 and values["cool"] == 21
        await tick(h)
        assert h.hass.services.calls[-1][1] == "set_temperature"
        assert 19 <= h.hass.services.calls[-1][2]["temperature"] <= 21
    asyncio.run(run())


def test_humidity_limits_override_target_and_rate_limit(runtime_module):
    async def run():
        h = home(runtime_module, domain="humidifier", state="on", power=False)
        h.room["profiles"] = {
            "comfort": {"heat_c": 20, "cool_c": 26, "humidity": 60}
        }
        h.manager.entry.data["environment_rooms"] = {
            "room": {"equipment_limits": {
                "humidity_min_limit": 40, "humidity_max_limit": 55}}
        }
        h.state.attributes["humidity"] = 70
        await tick(h)
        assert h.hass.services.calls[-1][1:3] == ("set_humidity", {"humidity": 55})
    asyncio.run(run())


def test_per_device_limit_edits_are_removed_and_room_limits_are_authoritative(runtime_module):
    async def run():
        h = home(runtime_module, domain="climate", state="heat", power=False)
        with pytest.raises(Exception, match="Unsupported controller setting"):
            await h.runtime.async_update(h.spec, {"temperature_min_limit": 18})
        assert h.manager.entry.options == {}
    asyncio.run(run())


def test_beta17_device_limits_migrate_conservatively_to_room(runtime_module):
    h = home(runtime_module, domain="climate", state="heat", power=False, controls={
        "temperature_min_limit": 18, "temperature_max_limit": 24,
    })
    values = m.room_limit_values(h.manager, "room")
    assert values["temperature_min_limit"] == 18
    assert values["temperature_max_limit"] == 24


def test_room_limit_bounds_intersect_available_physical_devices(runtime_module):
    h = home(runtime_module, domain="climate", state="off")
    second = MockState("climate.second_room", "off")
    second.attributes.update(h.state.attributes)
    second.attributes.update(min_temp=16, max_temp=30, target_temp_step=1)
    h.hass._values[second.entity_id] = second
    h.hass._entity_areas[second.entity_id] = "room"
    h.hass._entity_devices[second.entity_id] = "second-device"
    h.hass._device_areas["second-device"] = "room"
    h.room["selected_devices"].append(second.entity_id)
    h.room["device_settings"][second.entity_id] = dict(h.dev)
    spec2 = ManagedDevice("controller_two", "room", "Second climate",
                          "second-device", (second.entity_id,))
    h.manager._device_hierarchy["controllers"][spec2.identifier] = {
        "spec": spec2, "device_id": "logical-two"}
    h.manager.entry.data[m.SETTINGS][spec2.identifier] = dict(h.cfg)
    assert m.room_limit_bounds(h.manager, "room", "temperature_min_limit")[:2] == (16.0, 30.0)
    assert m.room_limit_bounds(h.manager, "room", "temperature_max_limit")[:2] == (16.0, 30.0)


def test_room_selected_temperature_and_humidity_override_device_sources(runtime_module):
    h = home(runtime_module, domain="climate", state="heat", power=False)
    t2 = MockState("sensor.temp2", 25, device_class="temperature", unit="°C")
    rh2 = MockState("sensor.rh2", 50, device_class="humidity", unit="%")
    for state in (t2, rh2):
        h.hass._values[state.entity_id] = state
        h.hass._entity_areas[state.entity_id] = "room"
    h.state.attributes["current_temperature"] = 99
    h.state.attributes["current_humidity"] = 1
    h.dev["temperature_entity"] = "sensor.temp"
    h.dev["humidity_entity"] = "sensor.rh"
    h.manager.entry.data["room_sources"] = {
        "room": {
            "temperature": ["sensor.temp", "sensor.temp2"],
            "humidity": ["sensor.rh", "sensor.rh2"],
            "air_quality": [],
        }
    }
    measured = h.runtime.measurements(h.spec, m.capabilities(h.manager, h.spec))
    assert measured["temperature"] == 20
    assert measured["humidity"] == 60
    assert measured["temperature_entity"] is None
    assert measured["humidity_entity"] is None
    assert measured["temperature_source"] == "room_selected_mean"
    assert measured["humidity_source"] == "room_selected_mean"
