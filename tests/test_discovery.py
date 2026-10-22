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
        self._entity_details = {}
        self._device_details = {}
        self._entity_devices = {}
        self._device_areas = {}
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
    errors = types.ModuleType("homeassistant.exceptions")
    errors.HomeAssistantError = type("HomeAssistantError", (Exception,), {})
    monkeypatch.setitem(sys.modules, "homeassistant.exceptions", errors)
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
                    if (e in hass._entity_areas or e in hass._entity_devices
                            or e in hass._entity_details):
                        return SimpleNamespace(
                            area_id=hass._entity_areas.get(e),
                            device_id=hass._entity_devices.get(e),
                            **hass._entity_details.get(e, {}),
                        )
                    return None
                return SimpleNamespace(async_get=get)
            reg.async_get = entity_registry
        elif name == "device_registry":
            reg.async_get = lambda hass: SimpleNamespace(async_get=lambda device_id: (
                SimpleNamespace(
                    area_id=hass._device_areas.get(device_id),
                    **hass._device_details.get(device_id, {}),
                ) if device_id in hass._device_areas or device_id in hass._device_details
                else None
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


def test_window_cover_is_not_a_window_contact(adapter):
    home = FakeHass([
        MockState("cover.bedroom_window", "open", device_class="window"),
        MockState("binary_sensor.hall_window", "off", device_class="window"),
    ], {"cover.bedroom_window": "bedroom", "binary_sensor.hall_window": "hall"})
    assert adapter.window_area_choices(home) == [{"value": "hall", "label": "hall · 1 🪟"}]
    scanned = adapter.rooms(home, ["bedroom", "hall"], 90)
    assert scanned[0].windows == ()
    assert [w.entity_id for w in scanned[1].windows] == ["binary_sensor.hall_window"]


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


def test_virtual_window_detector_default_suggestions_and_labels(adapter):
    """Best effort: climate device, 'detected' labels, and diagnostics are hints."""
    home = FakeHass([
        MockState("binary_sensor.kitchen_window", "off", device_class="window", name="Kitchen Window"),
        MockState("binary_sensor.bathroom_window", "off", device_class="window", name="Bath window"),
        MockState("climate.bathroom_trv", "heat"),
        MockState("binary_sensor.living_window_open_detected", "on", device_class="window"),
        MockState("binary_sensor.bedroom_diagnostic", "off", device_class="window"),
        MockState("cover.kitchen_window", "open", device_class="window"),
    ], {
        "binary_sensor.kitchen_window": "kitchen",
        "binary_sensor.bathroom_window": "bath",
        "binary_sensor.living_window_open_detected": "living",
        "binary_sensor.bedroom_diagnostic": "bedroom",
    })
    home._entity_devices = {
        "binary_sensor.bathroom_window": "heating_1", "climate.bathroom_trv": "heating_1",
    }
    home._entity_details["binary_sensor.bedroom_diagnostic"] = {"entity_category": "diagnostic"}
    suggested = adapter.suggested_window_exclusions(home)
    assert suggested == {
        "binary_sensor.bathroom_window",
        "binary_sensor.living_window_open_detected",
        "binary_sensor.bedroom_diagnostic",
    }
    options = adapter.window_exclusion_choices(home)
    assert len(options) == 4
    assert all(" · " in option["label"] and option["value"] in option["label"] for option in options)
    assert not any(option["value"].startswith("cover.") for option in options)
    assert not next(option for option in options if option["value"] == "binary_sensor.kitchen_window")["label"].startswith("⚠")
    assert next(option for option in options if option["value"] == "binary_sensor.bathroom_window")["label"].startswith("⚠")


def test_thermostat_model_suggested_even_without_climate_entity(adapter):
    home = FakeHass([MockState("binary_sensor.kitchen_window", "off", device_class="window")],
                    {"binary_sensor.kitchen_window": "kitchen"})
    home._entity_devices = {"binary_sensor.kitchen_window": "trv_dev"}
    home._device_details = {"trv_dev": {"model": "TRV-100", "name": "Smart Radiator"}}
    assert adapter.suggested_window_exclusions(home) == {"binary_sensor.kitchen_window"}


def test_excluded_window_is_removed_from_area_count_rooms_and_recommendation(adapter):
    from custom_components.air_quality_advisor.const import DEFAULT_THRESHOLDS
    from custom_components.air_quality_advisor.dashboard import dashboard_snapshot
    from custom_components.air_quality_advisor.logic import Reading, Weather, evaluate

    fake = "binary_sensor.bathroom_window_detection"
    real = "binary_sensor.living_real_window"
    home = FakeHass([
        MockState(fake, "on", device_class="window"),
        MockState(real, "off", device_class="window"),
        MockState("sensor.living_co2", "1400", device_class="co2", unit="ppm"),
    ], {fake: "bathroom", real: "living", "sensor.living_co2": "living"})
    excluded = {fake}
    assert [opt["value"] for opt in adapter.window_area_choices(home, excluded_entities=excluded)] == ["living"]
    parsed = adapter.rooms(home, ["bathroom", "living"], 90, excluded_entities=excluded)
    assert parsed[0].windows == ()
    assert [w.entity_id for w in parsed[1].windows] == [real]
    plan = evaluate(
        (Reading("sensor.out_pm25", "Outside", "pm25", 8),),
        (Weather("weather.home", "sunny", 20, 50, 7),),
        (), parsed, DEFAULT_THRESHOLDS,
    )
    assert all(fake not in (win.entity_id for win in rec.windows) for rec in plan.recommendations)
    snap = dashboard_snapshot(plan, DEFAULT_THRESHOLDS)
    assert snap["rooms"][0]["window_count"] == 0
    assert snap["rooms"][1]["window_count"] == 1


def test_previously_excluded_missing_sensor_stays_in_dropdown(adapter):
    home = FakeHass([])
    choices = adapter.window_exclusion_choices(home, ["binary_sensor.no_longer_available"])
    assert choices == [{"value": "binary_sensor.no_longer_available", "label": "⚠ binary_sensor.no_longer_available"}]


def test_supported_indoor_exclusions_include_humidity_and_all_supported_air_metrics(adapter):
    metrics = [
        ("aqi", "aqi", "index"),
        ("co2", "co2", "ppm"),
        ("pm25", "pm25", "µg/m³"),
        ("pm10", "pm10", "µg/m³"),
        ("voc", "volatile_organic_compounds", "µg/m³"),
        ("voc_parts", "volatile_organic_compounds_parts", "ppb"),
        ("humidity", "humidity", "%"),
    ]
    values = [MockState(f"sensor.office_{kind}", 5, device_class=device_class, unit=unit)
              for kind, device_class, unit in metrics]
    home = FakeHass(values, {value.entity_id: "office" for value in values})
    choices = adapter.indoor_sensor_exclusion_choices(home, "office")
    assert {choice["value"] for choice in choices} == {value.entity_id for value in values}


def test_indoor_exclusions_change_recommendations_and_card_without_disabling_sensors(adapter):
    from custom_components.air_quality_advisor.const import DEFAULT_THRESHOLDS
    from custom_components.air_quality_advisor.dashboard import dashboard_snapshot
    from custom_components.air_quality_advisor.logic import Reading, Weather, evaluate

    window = "binary_sensor.office_window"
    co2 = "sensor.office_co2"
    humidity = "sensor.office_humidity"
    home = FakeHass([
        MockState(window, "off", device_class="window"),
        MockState(co2, 1550, device_class="co2", unit="ppm"),
        MockState(humidity, 48, device_class="humidity", unit="%"),
    ], {window: "office", co2: "office", humidity: "office"})

    def snapshot(excluded):
        all_rooms = adapter.rooms(home, ["office"], 90, excluded_entities=excluded)
        plan = evaluate((Reading("sensor.outdoor_pm25", "Outside", "pm25", 7),),
                        (Weather("weather.home", "sunny", 20, 35, 2),),
                        (), all_rooms, DEFAULT_THRESHOLDS)
        return plan, dashboard_snapshot(plan, DEFAULT_THRESHOLDS)

    plan, card = snapshot(set())
    assert plan.status == "open"
    assert card["summary"]["attention"] == 1
    assert {item["entity_id"] for item in card["rooms"][0]["readings"]} == {co2, humidity}
    plan, card = snapshot({co2})
    assert plan.status == "idle"
    assert card["summary"]["safe"] == 1
    assert [item["entity_id"] for item in card["rooms"][0]["readings"]] == [humidity]
    assert home.states.get(co2).state == "1550"  # Integration never disables HA entities.


def test_device_area_inheritance_for_indoor_selector(adapter):
    co2 = "sensor.study_co2"
    home = FakeHass([MockState(co2, 900, device_class="co2", unit="ppm", name="Indoor CO2")])
    home._entity_devices[co2] = "meter"
    home._device_areas["meter"] = "study"
    home._device_details["meter"] = {"name":"Default model name", "name_by_user":"Office monitor"}
    choices = adapter.indoor_sensor_exclusion_choices(home, "study")
    assert len(choices) == 1
    assert "Office monitor" in choices[0]["label"]
    assert "Indoor CO2" in choices[0]["label"]
    assert not adapter.indoor_sensor_exclusion_choices(home, "kitchen")


def test_mold_temperature_sensor_fahrenheit_conversion_and_staleness(adapter):
    from custom_components.air_quality_advisor.discovery import (
        indoor_temperature_choices, temperature_sensor_c,
    )
    ha = FakeHass([
        MockState("sensor.bedroom_temperature", 68, device_class="temperature", unit="°F"),
        MockState("sensor.bedroom_humidity", 55, device_class="humidity", unit="%"),
        MockState("sensor.outside_temperature", 12, device_class="temperature", unit="°C"),
    ], {"sensor.bedroom_temperature": "bedroom",
        "sensor.bedroom_humidity": "bedroom",
        "sensor.outside_temperature": "outside"})
    assert [item["value"] for item in indoor_temperature_choices(ha, "bedroom")] == [
        "sensor.bedroom_temperature"
    ]
    assert temperature_sensor_c(ha, "sensor.bedroom_temperature", 90) == 20
    ha._values["sensor.bedroom_temperature"].last_reported -= timedelta(hours=3)
    assert temperature_sensor_c(ha, "sensor.bedroom_temperature", 90) is None

def test_physically_implausible_co2_and_humidity_are_unknown_not_safe(adapter):
    home = FakeHass([
        MockState("sensor.co2", 190, device_class="co2", unit="ppm"),
        MockState("sensor.humidity", 140, device_class="humidity", unit="%"),
    ])
    assert adapter.reading(home, "sensor.co2", 90, outdoor=False).value is None
    assert adapter.reading(home, "sensor.humidity", 90, outdoor=False).value is None
    home._values["sensor.co2"] = MockState("sensor.co2", 1200, device_class="co2", unit="ppm")
    assert adapter.reading(home, "sensor.co2", 90, outdoor=False).value == 1200

def test_international_no2_o3_so2_gases_are_recognized_only_with_real_mass_units(adapter):
    home = FakeHass([
        MockState("sensor.outdoor_nitrogen_dioxide", 0.020, device_class="nitrogen_dioxide", unit="mg/m³"),
        MockState("sensor.outdoor_o3", 70, unit="µg/m³"),
        MockState("sensor.outdoor_so2", 30, unit="µg/m³"),
        MockState("sensor.outdoor_ozone_bad", 0.08, unit="ppm"),
    ])
    assert adapter.reading(home, "sensor.outdoor_nitrogen_dioxide", 90, outdoor=True).value == 20
    assert adapter.reading(home, "sensor.outdoor_o3", 90, outdoor=True).value == 70
    assert adapter.reading(home, "sensor.outdoor_so2", 90, outdoor=True).value == 30
    assert adapter.reading(home, "sensor.outdoor_ozone_bad", 90, outdoor=True).value is None
