"""Regression: config-only numbers survive a late native climate startup.

The *physical* thermostat can be offline for the entire platform setup, while
PID gains, dwell controls and prior room profile targets are still editable.
No source command is issued by these tests.
"""
from __future__ import annotations

import asyncio
import importlib
import sys
import types
from types import SimpleNamespace

import pytest

from test_discovery import adapter
from custom_components.environment_manager.device_hierarchy import ManagedDevice


@pytest.fixture
def numbers(monkeypatch, adapter):
    class NumberEntity:
        @property
        def unique_id(self):
            return self._attr_unique_id

    modules = {
        "homeassistant.components.number": {
            "NumberEntity": NumberEntity,
            "NumberMode": SimpleNamespace(BOX="box"),
        },
        "homeassistant.helpers.dispatcher": {
            "async_dispatcher_connect": lambda *args: lambda: None,
        },
        "homeassistant.helpers.entity": {
            "EntityCategory": SimpleNamespace(CONFIG="config"),
        },
        "homeassistant.exceptions": {"HomeAssistantError": RuntimeError},
        "homeassistant.const": {"EVENT_STATE_CHANGED": "state_changed"},
    }
    for name, attrs in modules.items():
        mod = types.ModuleType(name)
        vars(mod).update(attrs)
        monkeypatch.setitem(sys.modules, name, mod)
    from homeassistant import core

    monkeypatch.setattr(core, "callback", lambda func: func, raising=False)
    monkeypatch.delitem(
        sys.modules, "custom_components.environment_manager.number",
        raising=False,
    )
    return importlib.import_module("custom_components.environment_manager.number")


def configured(mode="pid"):
    state = {}
    spec = ManagedDevice(
        "entry_controller_heater", "living", "Radiator",
        "native_hardware", ("climate.heater",),
    )
    settings = {
        "areas": ["living"],
        "climate_rooms": {
            "living": {
                "enabled": True,
                "selected_devices": ["climate.heater"],
            },
        },
        "equipment_controllers": {
            spec.identifier: {"control_mode": mode},
        },
    }
    listeners = {}
    manager = SimpleNamespace(
        settings=settings,
        _device_hierarchy={
            "controllers": {spec.identifier: {"spec": spec}},
            "device_subentries": {},
        },
    )
    manager.hass = SimpleNamespace(
        states=SimpleNamespace(get=state.get),
        bus=SimpleNamespace(
            async_listen=lambda key, callback: (
                listeners.setdefault(key, callback), lambda: None
            )[1],
        ),
    )
    entry = SimpleNamespace(
        runtime_data=manager, entry_id="entry",
        async_on_unload=lambda callback: None,
    )
    return manager, entry, state, spec, listeners


def test_offline_controller_pid_gains_and_hardware_times_still_have_values(numbers):
    manager, _, _, spec, _ = configured("pid")
    registry = SimpleNamespace(async_get_entity_id=lambda *args: None)
    all_numbers = numbers._equipment_numbers(manager, spec, registry)
    values = {number._key: number.native_value for number in all_numbers}
    assert values["kp"] == 10.0
    assert values["kd"] == 0.0
    assert values["sample_seconds"] == 300.0
    assert values["min_on_seconds"] == 600.0
    assert values["min_off_seconds"] == 600.0
    assert values["max_on_seconds"] == 7200.0


def test_existing_room_targets_survive_offline_native_climate(numbers):
    manager, _, _, _, _ = configured()
    prior = {
        f"entry_area_living_climate_profile_{profile}_heat"
        for profile in ("comfort", "home", "away", "sleep", "eco")
    }
    registry = SimpleNamespace(
        async_get_entity_id=lambda domain, platform, uid:
        "number.restored" if uid in prior else None
    )
    fields = numbers._profile_fields(manager, "entry", "living", registry)
    assert fields == tuple(f"{profile}_heat" for profile in
                           ("comfort", "home", "away", "sleep", "eco"))


def test_native_entity_recovery_adds_missing_room_numbers_without_restart(
    numbers, monkeypatch,
):
    manager, entry, states, spec, listeners = configured("automatic")
    registry = SimpleNamespace(async_get_entity_id=lambda *args: None)
    from homeassistant.helpers import entity_registry as er
    monkeypatch.setattr(er, "async_get", lambda hass: registry)
    monkeypatch.setattr(numbers, "configured_area_ids", lambda s: ("living",),
                        raising=False)
    added = []

    def add_entities(batch, **kwargs):
        added.extend(batch)

    asyncio.run(numbers.async_setup_entry(
        manager.hass, entry, add_entities,
    ))
    assert any(isinstance(e, numbers.EquipmentNumber)
               and e._key == "min_off_seconds" for e in added)
    assert not any(isinstance(e, numbers.ConfigNumber)
                   and e._kind == "climate_profile" for e in added)

    states["climate.heater"] = SimpleNamespace(
        state="off",
        attributes={
            "hvac_modes": ["off", "heat"],
            "supported_features": 1,
            "min_temp": 5,
            "max_temp": 35,
        },
    )
    listeners["state_changed"](SimpleNamespace(
        data={"entity_id": "climate.heater"},
    ))
    targets = [
        e for e in added if isinstance(e, numbers.ConfigNumber)
        and e._kind == "climate_profile"
    ]
    assert len(targets) == 5
    assert all(e._key.endswith("_heat") for e in targets)
    assert len({entity.unique_id for entity in added}) == len(added)

    # An irrelevant room event and a duplicate native event cannot register
    # the same number twice or cause a physical service call.
    listeners["state_changed"](SimpleNamespace(
        data={"entity_id": "sensor.outside_temperature"},
    ))
    before = len(added)
    listeners["state_changed"](SimpleNamespace(
        data={"entity_id": "climate.heater"},
    ))
    assert len(added) == before


def test_every_room_profile_number_has_a_real_native_value(numbers):
    manager, _, _, _, _ = configured()
    from custom_components.environment_manager.device_controls import (
        PROFILE_NUMBERS, PROFILE_DEFAULTS,
    )

    for key, bounds in PROFILE_NUMBERS.items():
        entity = numbers.ConfigNumber(
            manager, "entry", "living", "climate_profile", key, bounds,
        )
        group, mode = key.rsplit("_", 1)
        expected = PROFILE_DEFAULTS[group][mode]
        assert entity.native_value == expected, key
