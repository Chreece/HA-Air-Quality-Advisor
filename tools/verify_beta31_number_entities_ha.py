"""Actual Home Assistant 2026.10 NumberEntity smoke checks for beta31.

No config entry is loaded and no physical service call can occur. Validate the
configuration-only entities' native values against the installed HA entity API
while the native source is deliberately unavailable.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from homeassistant.components.number import NumberEntity
from homeassistant.helpers.entity import EntityCategory
from custom_components.environment_manager.device_hierarchy import ManagedDevice
from custom_components.environment_manager.number import (
    ConfigNumber, EquipmentNumber, _equipment_numbers, _profile_fields,
)


def main() -> None:
    spec = ManagedDevice(
        "entry_controller_thermostat", "living", "Thermostat",
        "native_hardware", ("climate.thermostat",),
    )
    manager = SimpleNamespace(
        settings={
            "areas": ["living"],
            "climate_rooms": {
                "living": {
                    "enabled": True,
                    "selected_devices": ["climate.thermostat"],
                },
            },
            "equipment_controllers": {
                spec.identifier: {"control_mode": "pid"},
            },
        },
        _device_hierarchy={
            "controllers": {spec.identifier: {"spec": spec}},
        },
        hass=SimpleNamespace(states=SimpleNamespace(get=lambda name: None)),
    )
    known = {f"entry_area_living_climate_profile_{preset}_heat"
             for preset in ("comfort", "home", "away", "sleep", "eco")}
    registry = SimpleNamespace(
        async_get_entity_id=lambda domain, platform, unique_id:
        "number.saved" if unique_id in known else None
    )
    actual = _equipment_numbers(manager, spec, registry)
    assert all(isinstance(entity, NumberEntity) for entity in actual)
    values = {entity._key: entity.native_value for entity in actual}
    assert values["kp"] == 10.0
    assert values["ki"] == 0.1
    assert values["kd"] == 0.0
    assert values["sample_seconds"] == 300.0
    assert values["min_on_seconds"] == 600.0
    assert values["min_off_seconds"] == 600.0
    assert values["max_on_seconds"] == 7200.0
    assert all(entity.available and entity.native_value is not None for entity in actual)
    assert all(entity.entity_category == EntityCategory.CONFIG for entity in actual)

    fields = _profile_fields(manager, "entry", "living", registry)
    assert len(fields) == 5
    for key in fields:
        room = ConfigNumber(
            manager, "entry", "living", "climate_profile",
            key, (5.0, 35.0, 0.5, "°C"),
        )
        assert isinstance(room, NumberEntity)
        assert room.native_value is not None

    print("HA 2026.10 number entities recover when physical climate is offline: PASS")


if __name__ == "__main__":
    main()
