"""Area mold recalibration is explicit, repeatable, and cannot overwrite good data on error."""
from __future__ import annotations

import asyncio
import importlib
import sys
import types
from types import SimpleNamespace

import pytest

from test_discovery import FakeHass, MockState, adapter


@pytest.fixture
def mold_editor(monkeypatch, adapter):
    mod = types.ModuleType("homeassistant.exceptions")
    class HomeAssistantError(Exception):
        pass
    mod.HomeAssistantError = HomeAssistantError
    monkeypatch.setitem(sys.modules, "homeassistant.exceptions", mod)
    monkeypatch.delitem(sys.modules, "custom_components.air_quality_advisor.mold_controls", raising=False)
    controls = importlib.import_module("custom_components.air_quality_advisor.mold_controls")
    return controls, HomeAssistantError


def model():
    st = [
        MockState("sensor.living_temperature", 21, device_class="temperature", unit="°C"),
        MockState("weather.home", "sunny"),
        MockState("sensor.another_temperature", 19, device_class="temperature", unit="°C"),
    ]
    st[1].attributes.update({"temperature": 6, "temperature_unit": "°C"})
    hass = FakeHass(st, {
        "sensor.living_temperature": "living",
        "sensor.another_temperature": "another",
    })
    revisions = []
    notifications = []
    config = {
        "areas": ["living"],
        "use_mold_indicator": True,
        "weather_entities": ["weather.home"],
        "mold_rooms": {
            "living": {
                "indoor_temperature_entity": "sensor.living_temperature",
                "critical_temperature_c": 13.5,
            }
        },
        "thresholds": {"max_age_minutes": 90},
    }
    entry = SimpleNamespace(data=config, options={})
    def update_entry(ent, *, options):
        ent.options = options
        revisions.append(options)
    hass.config_entries = SimpleNamespace(async_update_entry=update_entry)
    class Manager:
        _active=True
        def __init__(self):
            self.hass=hass
            self.entry=entry
        @property
        def settings(self):
            return {**self.entry.data, **self.entry.options}
        @property
        def thresholds(self):
            return {"max_age_minutes":90}
        def _recalculate(self, **kwargs):
            notifications.append(kwargs)
    return Manager(), revisions, notifications


def test_area_calibration_button_uses_live_temperatures_and_persists_factor(mold_editor):
    module, _ = mold_editor
    manager, revisions, notifications = model()
    value = asyncio.run(module.async_recalculate_mold_factor(manager, "living"))
    assert value == 2.0
    saved = manager.settings["mold_rooms"]["living"]
    assert saved["calibration_factor"] == 2
    assert saved["calibrated_indoor_c"] == 21
    assert saved["calibrated_outdoor_c"] == 6
    assert saved["critical_temperature_c"] == 13.5
    assert saved["outdoor_weather_entity"] == "weather.home"
    assert saved["calibrated_at"].endswith("+00:00")
    assert len(revisions) == 1 and notifications


def test_surface_temperature_change_marks_factor_stale_until_button_pressed(mold_editor):
    module, _ = mold_editor
    manager, _, _ = model()
    asyncio.run(module.async_recalculate_mold_factor(manager, "living"))
    asyncio.run(module.async_set_surface_temperature(manager, "living", 14.5))
    saved = manager.settings["mold_rooms"]["living"]
    assert saved["critical_temperature_c"] == 14.5
    assert "calibration_factor" not in saved
    assert "calibrated_at" not in saved
    assert saved["indoor_temperature_entity"] == "sensor.living_temperature"
    factor = asyncio.run(module.async_recalculate_mold_factor(manager, "living"))
    assert factor != 2.0


def test_bad_recalculation_does_not_destroy_previous_factor(mold_editor):
    module, Err = mold_editor
    manager, revisions, _ = model()
    asyncio.run(module.async_recalculate_mold_factor(manager, "living"))
    previous = dict(manager.settings["mold_rooms"]["living"])
    count=len(revisions)
    manager.hass.states.get("weather.home").attributes.pop("temperature")
    with pytest.raises(Err, match="Outdoor temperature"):
        asyncio.run(module.async_recalculate_mold_factor(manager, "living"))
    assert len(revisions) == count
    assert manager.settings["mold_rooms"]["living"] == previous


def test_invalid_geometry_and_cross_room_sensor_fail_closed(mold_editor):
    module, Err = mold_editor
    manager, revisions, _ = model()
    asyncio.run(module.async_set_surface_temperature(manager, "living", 6))
    before=len(revisions)
    with pytest.raises(Err, match="at least 3°C"):
        asyncio.run(module.async_recalculate_mold_factor(manager, "living"))
    assert len(revisions)==before
    manager.entry.options["mold_rooms"]["living"]["indoor_temperature_entity"] = "sensor.another_temperature"
    with pytest.raises(Err, match="indoor temperature source"):
        asyncio.run(module.async_recalculate_mold_factor(manager, "living"))


def test_disabled_or_missing_room_has_no_device_calibration_control(mold_editor):
    module, Err = mold_editor
    manager, _, _ = model()
    with pytest.raises(Err, match="not selected"):
        asyncio.run(module.async_recalculate_mold_factor(manager, "kitchen"))
    manager.entry.options["use_mold_indicator"] = False
    with pytest.raises(Err, match="not selected"):
        asyncio.run(module.async_set_surface_temperature(manager, "living", 12))
