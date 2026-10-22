"""Per-area devices expose Manager products without duplicating source entities."""
from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from custom_components.air_quality_advisor.const import DEFAULT_THRESHOLDS
from custom_components.air_quality_advisor.logic import (
    Reading, Room, Weather, Window, evaluate,
)

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "custom_components" / "air_quality_advisor" / "area_entities.py"


@pytest.fixture
def area_module(monkeypatch):
    """Minimal Home Assistant sensor and registry API, no HA runtime needed."""
    components = types.ModuleType("homeassistant.components")
    sensor = types.ModuleType("homeassistant.components.sensor")
    core = types.ModuleType("homeassistant.core")
    helpers = types.ModuleType("homeassistant.helpers")
    area_registry = types.ModuleType("homeassistant.helpers.area_registry")
    device_registry = types.ModuleType("homeassistant.helpers.device_registry")
    dispatcher = types.ModuleType("homeassistant.helpers.dispatcher")

    class SensorEntity:
        async def async_added_to_hass(self):
            pass

        def async_on_remove(self, callback):
            pass

        def async_write_ha_state(self):
            pass

    sensor.SensorEntity = SensorEntity
    sensor.SensorStateClass = SimpleNamespace(MEASUREMENT="measurement")
    core.callback = lambda fn: fn
    dispatcher.async_dispatcher_connect = lambda *args: (lambda: None)

    registry = SimpleNamespace(created=[], assigned=[])
    areas = {
        "kitchen": SimpleNamespace(name="Küche"),
        "bedroom": SimpleNamespace(name="Bedroom"),
        "office": SimpleNamespace(name="Office"),
    }
    area_registry.async_get = lambda hass: SimpleNamespace(
        async_get_area=lambda area: areas.get(area)
    )

    class Devices:
        def async_get_or_create(self, **fields):
            registry.created.append(fields)
            return SimpleNamespace(id=f"device-{len(registry.created)}", area_id=None)

        def async_update_device(self, device_id, **changes):
            registry.assigned.append((device_id, changes))

    device_registry.DeviceEntryType = SimpleNamespace(SERVICE="service")
    device_registry.async_get = lambda hass: Devices()
    for name, value in {
        "homeassistant.components": components,
        "homeassistant.components.sensor": sensor,
        "homeassistant.core": core,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.area_registry": area_registry,
        "homeassistant.helpers.device_registry": device_registry,
        "homeassistant.helpers.dispatcher": dispatcher,
    }.items():
        monkeypatch.setitem(sys.modules, name, value)

    name = "custom_components.air_quality_advisor._area_devices_under_test"
    spec = importlib.util.spec_from_file_location(name, MODULE)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "custom_components.air_quality_advisor"
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module, registry


def example_manager():
    room = Room(
        "kitchen", "Küche",
        (Window("binary_sensor.window", "Window", False),),
        (
            Reading("sensor.co2", "CO2", "co2", 820.0),
            Reading("derived.mold_kitchen", "Mold", "mold", 74.3, {
                "status": "ready", "dewpoint_c": 12.5,
                "estimated_surface_c": 13.1, "missing_inputs": [],
            }),
        ),
    )
    plan = evaluate(
        (Reading("sensor.outside_pm", "Outside PM", "pm25", 8.0),),
        (Weather("weather.home", "sunny", 22, 47, 3),),
        (), (room,),
    )
    states = {
        "sensor.co2": SimpleNamespace(
            state="820", attributes={"unit_of_measurement": "ppm"},
        ),
        "binary_sensor.window": SimpleNamespace(state="off", attributes={}),
    }
    hass = SimpleNamespace(states=SimpleNamespace(get=states.get),
                           services=SimpleNamespace(async_call=lambda *a, **k:
                                                    pytest.fail("No physical commands expected")))
    settings = {
        "areas": ["kitchen"],
        "use_mold_indicator": True,
        "climate_rooms": {
            "bedroom": {"enabled": True, "controller": "device",
                        "allow_actuation": False},
            "office": {"enabled": False, "controller": "device"},
        },
    }
    manager = SimpleNamespace(
        settings=settings, plan=plan, thresholds=DEFAULT_THRESHOLDS, hass=hass,
        entry=SimpleNamespace(entry_id="entry-42"),
    )
    return manager


def test_one_device_per_selected_area_and_only_calculated_optional_sensor(area_module):
    module, registry = area_module
    manager = example_manager()
    entry = SimpleNamespace(entry_id="entry-42", runtime_data=manager,
                            data=manager.settings, options={})
    entities = asyncio.run(module.async_area_entities(manager.hass, entry))
    assert len(registry.created) == 3  # Parent home device + two rooms
    assert registry.created[0]["identifiers"] == {("air_quality_advisor", "entry-42")}
    assert [row[1]["area_id"] for row in registry.assigned] == [
        "kitchen", "bedroom",
    ]
    assert len(entities) == 3  # Kitchen overview + computed mold; bedroom overview
    assert [e._attr_unique_id for e in entities] == [
        "entry-42_area_kitchen_overview",
        "entry-42_area_kitchen_surface_humidity",
        "entry-42_area_bedroom_overview",
    ]
    assert all(not name.endswith(("co2", "temperature", "target_temperature"))
               for name in (e._attr_unique_id for e in entities))


def test_overview_preserves_raw_inputs_and_derived_provenance(area_module):
    module, _ = area_module
    manager = example_manager()
    entity = module.AreaOverview(manager, "entry-42", "kitchen")
    attrs = entity.extra_state_attributes
    assert attrs["raw_inputs"][0] == {
        "entity_id": "sensor.co2", "metric": "co2",
        "raw_state": "820", "raw_unit": "ppm",
        "value": 820.0, "unit": "ppm",
        "available": True, "derived": False,
    }
    assert attrs["raw_inputs"][1]["derived"] is True
    assert attrs["raw_inputs"][1]["raw_state"] is None
    assert attrs["window_inputs"][0]["opened"] is False
    assert attrs["calculated"]["dew_point_c"] == 12.5
    assert attrs["calculated"]["surface_relative_humidity_percent"] == 74.3
    assert attrs["controller"] == {}
    assert entity.native_value == "attention"  # 74% calibrated mold indication


def test_optional_mold_sensor_returns_unavailable_on_missing_calibration(area_module):
    module, _ = area_module
    manager = example_manager()
    entity = module.AreaMoldSurfaceHumidity(manager, "entry-42", "kitchen")
    assert entity.native_value == 74.3
    assert entity.extra_state_attributes["dew_point_c"] == 12.5
    room = manager.plan.rooms[0]
    readings = (room.readings[0], Reading(
        "derived.mold_kitchen", "Mold", "mold", None,
        {"status": "needs_calibration", "missing_inputs": ["calibration"]},
    ))
    manager.plan = replace(manager.plan, rooms=(replace(room, readings=readings),))
    assert entity.native_value is None
    assert entity.extra_state_attributes["missing_inputs"] == ["calibration"]
    attrs = module.AreaOverview(manager, "entry-42", "kitchen").extra_state_attributes
    assert attrs["raw_inputs"][1]["available"] is False
    assert attrs["calculated"]["surface_relative_humidity_percent"] is None


def test_disabled_climate_only_rooms_do_not_create_devices(area_module):
    module, _ = area_module
    assert module.configured_area_ids({
        "areas": ["kitchen", "kitchen", ""],
        "climate_rooms": {
            "bedroom": {"enabled": True}, "office": {"enabled": False},
        },
        "pid_rooms": {"bedroom": {"enabled": True}, "hall": {"enabled": False}},
    }) == ("kitchen", "bedroom")
