"""Multi-appliance arbitration is fail-closed and never writes to hardware."""
import pytest

@pytest.fixture
def coordinator(adapter):
    # discovery imports HA registries; the adapter must be installed first.
    from custom_components.air_quality_advisor import climate_coordination
    return climate_coordination

from custom_components.air_quality_advisor.logic import Reading
from test_discovery import MockState, FakeHass, adapter


def home():
    states = [
        MockState("climate.radiator", "heat"),
        MockState("climate.ac", "cool"),
        MockState("humidifier.dryer", "off", device_class="dehumidifier"),
        MockState("humidifier.hum", "off", device_class="humidifier"),
        MockState("fan.extractor", "off"),
        MockState("fan.purifier", "off"),
    ]
    states[0].attributes.update({"hvac_modes": ["off", "heat"], "supported_features": 1,
                                 "hvac_action": "idle"})
    states[1].attributes.update({"hvac_modes": ["off", "cool", "dry", "fan_only"],
                                 "supported_features": 1, "hvac_action": "idle"})
    return FakeHass(states, {state.entity_id: "bedroom" for state in states})


def config():
    return {
        "climate_entity": "climate.radiator",
        "heat_climate_entity": "climate.radiator",
        "cool_climate_entity": "climate.ac",
        "dry_climate_entity": "climate.ac",
        "dehumidifier_entity": "humidifier.dryer",
        "humidifier_entity": "humidifier.hum",
        "extraction_fan_entity": "fan.extractor",
        "purifier_fan_entity": "fan.purifier",
    }


def test_correct_room_and_real_device_classes(coordinator):
    h = home()
    found = coordinator.device_inventory(h, "bedroom", config())
    assert found["heat_climate_entity"]["status"] == "ready"
    assert found["dehumidifier_entity"]["status"] == "ready"
    assert found["humidifier_entity"]["status"] == "ready"
    h._values["humidifier.dryer"].attributes["device_class"] = "humidifier"
    assert coordinator.device_inventory(h, "bedroom", config())["dehumidifier_entity"]["status"] == "device_class_not_verified"
    assert coordinator.device_inventory(h, "kitchen", config())["cool_climate_entity"]["status"] == "wrong_room_or_unassigned"


def test_explicit_heat_cool_selection_is_exclusive(coordinator):
    h = home()
    cfg = config()
    temp = {"status": "ready", "mode": "cool", "window_safe": True}
    item = coordinator.room_equipment_plan(h, "bedroom", cfg, temp,
                               (Reading("sensor.rh", "Humidity", "humidity", 51),))
    assert item["thermal"]["entity_id"] == "climate.ac"
    assert item["thermal"]["control"] == "advisory_secondary_driver_pending"
    assert item["humidity"]["action"] == "idle"
    assert item["automatic_secondary_actuation"] is False
    h._values["climate.radiator"].attributes["hvac_action"] = "heating"
    item = coordinator.room_equipment_plan(h, "bedroom", cfg, temp, ())
    assert item["thermal"]["status"] == "opposing_equipment_active"


def test_no_silent_fallback_on_unavailable_selected_ac(coordinator):
    h = home()
    h._values["climate.ac"].state = "unavailable"
    temp = {"status": "ready", "mode": "cool", "window_safe": True}
    item = coordinator.room_equipment_plan(h, "bedroom", config(), temp, ())
    assert item["thermal"]["status"] == "no_verified_device"


def test_drying_secondary_device_and_no_parallel_compressor_mode(coordinator):
    h = home()
    cfg = config()
    wet = (Reading("sensor.rh", "Humidity", "humidity", 72),)
    idle = {"status": "ready", "mode": "off", "window_safe": True}
    item = coordinator.room_equipment_plan(h, "bedroom", cfg, idle, wet)
    assert item["moisture"]["entity_id"] == "humidifier.dryer"
    cfg.pop("dehumidifier_entity")
    item = coordinator.room_equipment_plan(h, "bedroom", cfg, idle, wet)
    assert item["moisture"]["entity_id"] == "climate.ac"
    heating = {"status": "ready", "mode": "heat", "window_safe": True}
    item = coordinator.room_equipment_plan(h, "bedroom", cfg, heating, wet)
    assert item["moisture"]["status"] == "thermal_priority_defer_dry"


def test_humidity_missing_or_ambiguous_fails_closed(coordinator):
    h = home()
    idle = {"status": "ready", "mode": "off", "window_safe": True}
    cfg = config()
    r = Reading("sensor.first", "First", "humidity", 72)
    s = Reading("sensor.second", "Second", "humidity", 31)
    item = coordinator.room_equipment_plan(h, "bedroom", cfg, idle, (r, s))
    assert item["humidity_evidence"] == "multiple_sensors_choose_one"
    assert item["humidity"]["status"] == "insufficient_data"
    cfg["humidity_entity"] = "sensor.first"
    item = coordinator.room_equipment_plan(h, "bedroom", cfg, idle, (r, s))
    assert item["moisture"]["action"] == "dry"


def test_duplicate_cross_room_ownership_and_open_window_hold(coordinator):
    cfg = config()
    assert coordinator.duplicate_owners({"bedroom": cfg, "lounge": cfg})
    assert coordinator.duplicate_owners({"bedroom": cfg, "lounge": {}}) == {}
    item = coordinator.room_equipment_plan(
        home(), "bedroom", cfg,
        {"status": "ready", "mode": "heat", "window_safe": False},
        (), duplicates={"climate.ac": ["bedroom", "lounge"]})
    assert item["status"] == "duplicate_equipment_owner"
    item = coordinator.room_equipment_plan(
        home(), "bedroom", cfg,
        {"status": "ready", "mode": "heat", "window_safe": False},
        (Reading("sensor.rh", "Humidity", "humidity", 75),))
    assert item["thermal"]["status"] == "window_interlock"
    assert item["moisture"]["status"] == "window_interlock"


def test_fans_need_outdoor_evidence(coordinator):
    h = home()
    cfg = config()
    no_temp = {"status": "hold", "window_safe": True}
    not_safe = coordinator.room_equipment_plan(h, "bedroom", cfg, no_temp, (), outdoor_safe=False)
    safe = coordinator.room_equipment_plan(h, "bedroom", cfg, no_temp, (), outdoor_safe=True)
    assert not_safe["ventilation"]["status"] == "outdoor_air_unverified_or_fan_unavailable"
    assert safe["ventilation"]["status"] == "available_if_outdoor_evidence_supports"
    assert "fan.purifier" in coordinator.assigned_entities(cfg)
