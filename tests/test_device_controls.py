"""Regression checks for device-owned PID and home-wide settings.

All controllers are simulated. Changing soft preferences cannot send a physical
climate, relay, fan or humidifier service call.
"""
from __future__ import annotations

import asyncio
import importlib
import sys
import types
from types import SimpleNamespace

import pytest
from test_discovery import adapter


@pytest.fixture
def controls(monkeypatch, adapter):
    module = types.ModuleType("homeassistant.exceptions")

    class HomeAssistantError(Exception):
        pass

    module.HomeAssistantError = HomeAssistantError
    monkeypatch.setitem(sys.modules, "homeassistant.exceptions", module)
    monkeypatch.delitem(sys.modules, "custom_components.enviroment_manager.device_controls",
                        raising=False)
    impl = importlib.import_module("custom_components.enviroment_manager.device_controls")
    return impl, HomeAssistantError


def manager():
    data = {
        "pid_rooms": {
            "living": {
                "enabled": True,
                "climate_entities": ["climate.living"],
                "temperature_entity": "sensor.room",
            },
            "bedroom": {"enabled": False},
        },
        "climate_rooms": {
            "living": {
                "enabled": True,
                "controller": "device",
                "allow_actuation": False,
                "climate_entity": "climate.living",
            },
        },
        "thresholds": {"indoor_co2": 950.0},
        "automatic_notifications": False,
        "automatic_tts": False,
    }
    entry = SimpleNamespace(data=data, options={})
    writes = []
    prepared = []

    class FakeHass:
        def __init__(self):
            self.services = SimpleNamespace(has_service=lambda *args: False)
            self.config_entries = SimpleNamespace(async_update_entry=self.update)

        def update(self, original, *, options):
            assert original is entry
            original.options = options
            writes.append(options)

    class FakePid:
        async def async_prepare_reconfigure(self, area):
            prepared.append(area)

    class FakeManager:
        _active = True
        hub_available = False
        pid = FakePid()
        hass = FakeHass()
        rechecks = []

        @property
        def settings(self):
            return {**self.entry.data, **self.entry.options}

        def _recalculate(self, *, initial=False):
            self.rechecks.append(initial)

    obj = FakeManager()
    obj.entry = entry
    obj.thresholds = data["thresholds"]
    return obj, writes, prepared


def test_pid_defaults_and_manual_gains_update_only_requested_area(controls):
    module, _ = controls
    controller, writes, prepared = manager()
    pid = module.pid_settings(controller.settings, "living")
    assert (pid["kp"], pid["ki"], pid["kd"]) == (22, 0.25, 0)
    assert module.tuning_source(pid) == "defaults"
    asyncio.run(module.update_device_setting(
        controller, "pid", "kp", 13.5, area="living"))
    changed = controller.settings["pid_rooms"]
    assert changed["living"]["kp"] == 13.5
    assert changed["living"]["tuning_source"] == "manual"
    assert changed["bedroom"] == {"enabled": False}
    assert prepared == ["living"]
    assert writes and all(controller.rechecks)


def test_pid_invalid_target_rejected_without_persisting(controls):
    module, Err = controls
    controller, writes, prepared = manager()
    with pytest.raises(Err, match="Unsafe PID"):
        asyncio.run(module.update_device_setting(
            controller, "pid", "target_c", 36.0, area="living"))
    assert writes == []
    assert prepared == []


def test_pid_gain_source_can_restore_conservative_fixed_defaults(controls):
    module, _ = controls
    controller, _, prepared = manager()
    asyncio.run(module.update_device_setting(
        controller, "pid", "kp", 14, area="living"))
    asyncio.run(module.update_device_setting(
        controller, "pid_gain_source", "tuning_source", "defaults", area="living"))
    cfg = controller.settings["pid_rooms"]["living"]
    assert (cfg["kp"], cfg["ki"], cfg["kd"]) == (22.0, 0.25, 0.0)
    assert cfg["tuning_source"] == "defaults"
    assert prepared == ["living", "living"]


def test_profile_target_updates_preserve_room_comfort_band_and_safety(controls):
    module, Err = controls
    controller, writes, _ = manager()
    asyncio.run(module.update_device_setting(
        controller, "climate_profile", "comfort_heat", 21.0, area="living"))
    saved = controller.settings["climate_rooms"]["living"]
    assert saved["profiles"]["comfort"] == {"heat_c": 21.0, "cool_c": 26.0}
    with pytest.raises(Err, match="Invalid comfort band"):
        asyncio.run(module.update_device_setting(
            controller, "climate_profile", "comfort_cool", 21.2, area="living"))
    assert controller.settings["climate_rooms"]["living"]["profiles"]["comfort"]["cool_c"] == 26.0


def test_global_thresholds_are_home_only_and_check_temperature_limits(controls):
    module, Err = controls
    controller, _, _ = manager()
    assert len(module.THRESHOLD_NUMBERS) == 22
    with pytest.raises(Err, match="below maximum"):
        asyncio.run(module.update_device_setting(
            controller, "global_threshold", "min_outdoor_temp", 35))
    assert controller.entry.options == {}
    asyncio.run(module.update_device_setting(
        controller, "global_threshold", "indoor_co2", 850))
    assert controller.settings["thresholds"]["indoor_co2"] == 850
    assert controller.settings["pid_rooms"]["living"]["enabled"] is True


def test_home_tts_requires_a_working_provider(controls):
    module, Err = controls
    controller, _, _ = manager()
    with pytest.raises(Err, match="TTS engine"):
        asyncio.run(module.update_device_setting(
            controller, "global_setting", "automatic_tts", True))
    assert controller.entry.options == {}
    asyncio.run(module.update_device_setting(
        controller, "global_setting", "automatic_notifications", True))
    assert controller.entry.options["automatic_notifications"] is True


def test_deactivated_and_unknown_pid_cannot_be_reconfigured(controls):
    module, Err = controls
    controller, _, _ = manager()
    with pytest.raises(Err, match="safely configured"):
        asyncio.run(module.update_device_setting(
            controller, "pid", "kp", 15, area="bedroom"))
    with pytest.raises(Err, match="safely configured"):
        asyncio.run(module.update_device_setting(
            controller, "pid", "kp", 15, area="kitchen"))


@pytest.mark.parametrize("key,value", [("room_volume_m3", 45.0), ("sleep_room", True)])
def test_area_environment_controls_require_and_update_selected_room(controls, key, value):
    module, Err = controls
    controller, writes, _ = manager()
    controller.entry.data["areas"] = ["living"]
    asyncio.run(module.update_device_setting(
        controller, "area_environment", key, value, area="living"))
    assert controller.settings["environment_rooms"]["living"][key] == value
    before = len(writes)
    with pytest.raises(Err, match="Select the room"):
        asyncio.run(module.update_device_setting(
            controller, "area_environment", key, value, area="unconfigured"))
    assert len(writes) == before
