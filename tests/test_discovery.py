"""Adapter validation with tiny HA stand-ins (no HA installation required)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib
import sys
import types
from types import SimpleNamespace

import pytest


class MockState:
    def __init__(self, entity_id, value, *, device_class=None, unit=None, name=None, hours_old=0):
        self.entity_id = entity_id
        self.domain = entity_id.split(".")[0]
        self.state = str(value)
        self.name = name or entity_id
        self.attributes = {}
        if device_class:
            self.attributes["device_class"] = device_class
        if unit is not None:
            self.attributes["unit_of_measurement"] = unit
        self.last_reported = datetime.now(timezone.utc) - timedelta(hours=hours_old)
        self.last_updated = self.last_reported


class FakeHass:
    def __init__(self, values, entity_areas=None):
        self._values = {s.entity_id: s for s in values}
        self._entity_areas = entity_areas or {}
        self.states = SimpleNamespace(get=self._values.get, async_all=self._async_all)

    def _async_all(self, domain=None):
        return [s for s in self._values.values() if domain is None or s.domain == domain]


@pytest.fixture
def adapter(monkeypatch):
    # Only standard module references needed by discovery.py are provided.
    root = types.ModuleType("homeassistant")
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = object
    core.State = object
    helpers = types.ModuleType("homeassistant.helpers")
    util = types.ModuleType("homeassistant.util")
    dt = types.ModuleType("homeassistant.util.dt")
    dt.utcnow = lambda: datetime.now(timezone.utc)
    monkeypatch.setitem(sys.modules, "homeassistant", root)
    monkeypatch.setitem(sys.modules, "homeassistant.core", core)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers", helpers)
    monkeypatch.setitem(sys.modules, "homeassistant.util", util)
    monkeypatch.setitem(sys.modules, "homeassistant.util.dt", dt)
    for name in ("entity_registry", "device_registry", "area_registry"):
        reg = types.ModuleType(f"homeassistant.helpers.{name}")
        if name == "entity_registry":
            def entity_registry(hass):
                def get(e):
                    if e in hass._entity_areas or e in getattr(hass, "_entity_devices", {}):
                        return SimpleNamespace(
                            area_id=hass._entity_areas.get(e),
                            device_id=getattr(hass, "_entity_devices", {}).get(e),
                        )
                    return None
                return SimpleNamespace(async_get=get)
            reg.async_get = entity_registry
        elif name == "device_registry":
            reg.async_get = lambda hass: SimpleNamespace(async_get=lambda device_id: (
                SimpleNamespace(area_id=hass._device_areas[device_id])
                if device_id in getattr(hass, "_device_areas", {}) else None
            ))
        else:
            reg.async_get = lambda hass: SimpleNamespace(async_get_area=lambda area: SimpleNamespace(name=area))
        setattr(helpers, name, reg)
        monkeypatch.setitem(sys.modules, f"homeassistant.helpers.{name}", reg)
    name = "custom_components.air_quality_advisor.discovery"
    monkeypatch.delitem(sys.modules, name, raising=False)
    module = importlib.import_module(name)
    yield module
    sys.modules.pop(name, None)


def test_recognised_outdoor_sensors_filtered_from_monitored_rooms(adapter):
    home = FakeHass([
        MockState("sensor.living_co2", 1100, device_class="co2", unit="ppm"),
        MockState("sensor.outside_pm25", 8, device_class="pm25", unit="µg/m³"),
        MockState("sensor.unsupported", 10, unit="ppm"),
        MockState("sensor.outside_humidity", 83, device_class="humidity", unit="%"),
    ], {"sensor.living_co2": "living_room", "sensor.outside_pm25": "outside"})
    choices = adapter.outdoor_choices(home, ["living_room"])
    assert [c["value"] for c in choices] == ["sensor.outside_pm25"]


def test_pm_milligrams_are_converted_to_micrograms(adapter):
    home = FakeHass([MockState("sensor.air_pm10", 0.023, device_class="pm10", unit="mg/m³")])
    val = adapter.reading(home, "sensor.air_pm10", 90, outdoor=True)
    assert val.value == pytest.approx(23.0)


def test_voc_ppm_is_converted_to_ppb(adapter):
    home = FakeHass([MockState("sensor.voc", 0.5, device_class="volatile_organic_compounds_parts", unit="ppm")])
    val = adapter.reading(home, "sensor.voc", 90, outdoor=True)
    assert val.value == pytest.approx(500.0)


def test_wrong_unit_does_not_get_accepted_as_aqi(adapter):
    home = FakeHass([MockState("sensor.aqi", 3, device_class="aqi", unit="µg/m³")])
    assert adapter.outdoor_choices(home) == []


def test_stale_air_quality_prevents_safe_outdoors(adapter):
    home = FakeHass([MockState("sensor.co2", 450, device_class="co2", unit="ppm", hours_old=5)])
    assert adapter.reading(home, "sensor.co2", 90, outdoor=True).value is None


def test_dwd_warning_numeric_zero_is_clear_and_positive_is_active(adapter):
    home = FakeHass([MockState("sensor.dwd_warnstufe", 0)])
    assert adapter.warning(home, "sensor.dwd_warnstufe", 90).active is False
    home._values["sensor.dwd_warnstufe"] = MockState("sensor.dwd_warnstufe", 2)
    assert adapter.warning(home, "sensor.dwd_warnstufe", 90).active is True


def test_unavailable_warning_stays_unknown_not_clear(adapter):
    home = FakeHass([MockState("sensor.weather_warning", "unavailable")])
    assert adapter.warning(home, "sensor.weather_warning", 90).active is None


def test_window_class_only(adapter):
    home = FakeHass([
        MockState("binary_sensor.living_window", "on", device_class="window"),
        MockState("binary_sensor.living_door", "on", device_class="door"),
        MockState("sensor.living_co2", "1300", device_class="co2", unit="ppm"),
    ], {
        "binary_sensor.living_window": "living_room",
        "binary_sensor.living_door": "living_room",
        "sensor.living_co2": "living_room",
    })
    room = adapter.rooms(home, ["living_room"], 90)[0]
    assert [w.entity_id for w in room.windows] == ["binary_sensor.living_window"]
    assert room.windows[0].opened is True


def test_quiet_warning_sensor_need_not_republish_off_every_hour(adapter):
    home = FakeHass([MockState("binary_sensor.weather_warning", "off", hours_old=72)])
    assert adapter.warning(home, "binary_sensor.weather_warning", 90).active is False



def test_window_area_choices_only_contain_areas_with_recognized_windows(adapter):
    home = FakeHass([
        MockState("binary_sensor.living_window", "off", device_class="window", name="Living window"),
        MockState("cover.living_window", "closed", device_class="window", name="Living cover"),
        MockState("binary_sensor.kitchen_door", "off", device_class="door"),
        MockState("sensor.bedroom_co2", 1250, device_class="co2", unit="ppm"),
        MockState("binary_sensor.outside_window", "on", device_class="window"),
    ], {
        "binary_sensor.living_window": "living",
        "cover.living_window": "living",
        "binary_sensor.kitchen_door": "kitchen",
        "sensor.bedroom_co2": "bedroom",
    })
    choices = adapter.window_area_choices(home)
    assert len(choices) == 1
    assert choices[0]["value"] == "living"
    assert "1" in choices[0]["label"]


def test_window_class_cover_does_not_count_as_window(adapter):
    home = FakeHass([
        MockState("cover.bedroom_window", "open", device_class="window"),
        MockState("binary_sensor.hall_window", "off", device_class="window"),
    ], {
        "cover.bedroom_window": "bedroom",
        "binary_sensor.hall_window": "hall",
    })
    assert [choice["value"] for choice in adapter.window_area_choices(home)] == ["hall"]
    scanned = adapter.rooms(home, ["bedroom", "hall"], 90)
    assert scanned[0].windows == ()
    assert [window.entity_id for window in scanned[1].windows] == ["binary_sensor.hall_window"]


def test_window_area_choices_use_device_area_when_entity_has_no_override(adapter):
    home = FakeHass([
        MockState("binary_sensor.bedroom_window", "off", device_class="window"),
    ])
    home._entity_devices = {"binary_sensor.bedroom_window": "device_1"}
    home._device_areas = {"device_1": "bedroom"}
    assert adapter.window_area_choices(home)[0]["value"] == "bedroom"


def test_window_area_choices_keep_previous_selection_without_suggesting_empty_areas(adapter):
    home = FakeHass([
        MockState("binary_sensor.kitchen_window", "off", device_class="window"),
    ], {"binary_sensor.kitchen_window": "kitchen"})
    assert {c["value"] for c in adapter.window_area_choices(home)} == {"kitchen"}
    choices = adapter.window_area_choices(home, ["bedroom", "kitchen"])
    assert {c["value"] for c in choices} == {"bedroom", "kitchen"}
    assert choices[0]["value"] == "kitchen"
    assert "⚠" in next(c["label"] for c in choices if c["value"] == "bedroom")


def test_window_area_choices_empty_when_no_recognized_windows(adapter):
    home = FakeHass([MockState("binary_sensor.lounge_door", "off", device_class="door")],
                    {"binary_sensor.lounge_door": "lounge"})
    assert adapter.window_area_choices(home) == []
