"""Native quiet controls are capability-driven and survive late HA startups.

Regression covers all native climate models rather than brands or entity names.
No physical command is dispatched while refreshing the configuration entities.
"""
from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

import pytest
from test_equipment_control import home, runtime_module
from test_equipment_entities import platforms
from test_discovery import adapter

from custom_components.environment_manager import equipment_model as equipment


@pytest.fixture
def setup(platforms, monkeypatch):
    const = sys.modules["homeassistant.const"]
    const.EVENT_STATE_CHANGED = "state_changed"
    from homeassistant.helpers import entity_registry as er

    def create(*, stored=()):
        instance = home(platforms.runtime, domain="climate", state="off")
        h, native = instance.hass, instance.state
        native.attributes.update(fan_modes=["low", "medium", "high"],
                                 supported_features=1 | 8)
        _registrations = set(stored)
        original_get = er.async_get

        def registry(hass):
            old = original_get(hass)
            old.async_get_entity_id = lambda platform, domain, uid: (
                f"{platform}.previous" if (platform, uid) in _registrations
                else None
            )
            return old

        monkeypatch.setattr(er, "async_get", registry)
        listeners, off = {}, []
        def listen(event, callback):
            listeners.setdefault(event, []).append(callback)
            def unsubscribe():
                off.append(callback)
            return unsubscribe
        h.bus = SimpleNamespace(async_listen=listen)
        instance.manager._device_hierarchy["device_subentries"] = {
            instance.spec.identifier: "room-subentry"
        }
        instance.manager.entry.async_on_unload = lambda unsub: off.append(unsub)

        select_new, switch_new = [], []
        def add_select(entities, **kwargs):
            select_new.extend(entities)
            if any(getattr(obj, "_spec", None) for obj in entities):
                assert kwargs.get("config_subentry_id") == "room-subentry"
        def add_switch(entities, **kwargs):
            switch_new.extend(entities)
            if any(getattr(obj, "_spec", None) for obj in entities):
                assert kwargs.get("config_subentry_id") == "room-subentry"

        return SimpleNamespace(
            h=instance, select_new=select_new, switch_new=switch_new,
            add_select=add_select, add_switch=add_switch,
            listeners=listeners, off=off,
        )
    return create


def _physical_event(loaded, *, eid=None, before=None, after=None):
    return SimpleNamespace(data={
        "entity_id": eid or loaded.h.entity,
        "old_state": before,
        "new_state": after,
    })


def _keys(entities):
    return {
        (entity._spec.identifier, entity._key)
        for entity in entities
        if hasattr(entity, "_spec")
    }


def test_quiet_switches_and_dropdown_created_only_for_native_discrete_fan(
    setup, platforms,
):
    loaded=setup()
    asyncio.run(platforms.select.async_setup_entry(
        loaded.h.hass, loaded.h.manager.entry, loaded.add_select,
    ))
    asyncio.run(platforms.switch.async_setup_entry(
        loaded.h.hass, loaded.h.manager.entry, loaded.add_switch,
    ))
    assert _keys(loaded.select_new) == {
        (loaded.h.spec.identifier, "control_mode"),
        (loaded.h.spec.identifier, "pid_calibration_method"),
        (loaded.h.spec.identifier, "presence_requirement"),
        (loaded.h.spec.identifier, "sleep_behavior"),
        (loaded.h.spec.identifier, "quiet_fan_mode"),
    }
    switches=_keys(loaded.switch_new)
    assert (loaded.h.spec.identifier, "quiet_sleep") in switches
    assert (loaded.h.spec.identifier, "quiet_occupied") in switches
    quiet=next(x for x in loaded.select_new
               if getattr(x, "_key", None) == "quiet_fan_mode")
    assert quiet.options == ["low", "medium", "high"]
    assert quiet.current_option == "low"
    assert quiet.available
    assert not any(loaded.h.hass.services.calls)


def test_offline_at_start_recovers_prior_registry_ids_without_hardware_write(
    setup, platforms,
):
    loaded=setup(stored={
        ("select", "entry_controller_one_quiet_fan_mode"),
        ("switch", "entry_controller_one_quiet_sleep"),
        ("switch", "entry_controller_one_quiet_occupied"),
    })
    original=loaded.h.state.attributes.copy()
    loaded.h.state.attributes["supported_features"] = 1
    loaded.h.state.attributes.pop("fan_modes", None)
    asyncio.run(platforms.select.async_setup_entry(
        loaded.h.hass, loaded.h.manager.entry, loaded.add_select,
    ))
    asyncio.run(platforms.switch.async_setup_entry(
        loaded.h.hass, loaded.h.manager.entry, loaded.add_switch,
    ))
    assert "quiet_fan_mode" in {key for _,key in _keys(loaded.select_new)}
    assert {"quiet_sleep", "quiet_occupied"} <= {
        key for _,key in _keys(loaded.switch_new)
    }
    quiet=next(x for x in loaded.select_new
               if getattr(x,"_key",None)=="quiet_fan_mode")
    assert not quiet.available and quiet.options == []
    loaded.h.state.attributes.update(original)
    assert quiet.available
    assert quiet.options == ["low", "medium", "high"]
    assert loaded.h.hass.services.calls == []


def test_missing_unregistered_controls_added_once_on_native_capability_recovery(
    setup, platforms,
):
    loaded=setup()
    original=loaded.h.state.attributes.copy()
    loaded.h.state.attributes["supported_features"] = 1
    loaded.h.state.attributes.pop("fan_modes", None)
    asyncio.run(platforms.select.async_setup_entry(
        loaded.h.hass, loaded.h.manager.entry, loaded.add_select,
    ))
    asyncio.run(platforms.switch.async_setup_entry(
        loaded.h.hass, loaded.h.manager.entry, loaded.add_switch,
    ))
    assert "quiet_fan_mode" not in {k for _, k in _keys(loaded.select_new)}
    assert not {"quiet_sleep","quiet_occupied"} & {
        k for _, k in _keys(loaded.switch_new)
    }

    loaded.h.state.attributes.update(original)
    callback = _physical_event(loaded)
    for cb in tuple(loaded.listeners["state_changed"]):
        cb(callback)
    assert {k for _, k in _keys(loaded.select_new)}.issuperset({"quiet_fan_mode"})
    assert {k for _, k in _keys(loaded.switch_new)}.issuperset({
        "quiet_sleep","quiet_occupied"
    })

    # Duplicate native reports and Manager-generated events cannot create
    # duplicate entries or trigger a physical fan-mode command.
    for cb in tuple(loaded.listeners["state_changed"]):
        cb(callback)
        cb(_physical_event(loaded, eid="climate.manager_generated"))
    assert len({
        (x._spec.identifier,x._key) for x in loaded.select_new
        if hasattr(x, "_spec")
    }) == len([x for x in loaded.select_new if hasattr(x,"_spec")])
    assert len({
        (x._spec.identifier,x._key) for x in loaded.switch_new
        if hasattr(x, "_spec")
    }) == len([x for x in loaded.switch_new if hasattr(x,"_spec")])
    assert loaded.h.hass.services.calls == []


def test_native_percentage_and_no_fan_never_invent_discrete_low_mode(
    setup, platforms,
):
    loaded=setup()
    loaded.h.state.attributes["supported_features"] = 1
    loaded.h.state.attributes.pop("fan_modes",None)
    asyncio.run(platforms.select.async_setup_entry(
        loaded.h.hass, loaded.h.manager.entry, loaded.add_select,
    ))
    asyncio.run(platforms.switch.async_setup_entry(
        loaded.h.hass, loaded.h.manager.entry, loaded.add_switch,
    ))
    assert "quiet_fan_mode" not in {k for _,k in _keys(loaded.select_new)}
    assert not {"quiet_sleep","quiet_occupied"} & {
        k for _,k in _keys(loaded.switch_new)
    }
    assert loaded.h.hass.services.calls == []


def test_managed_climate_refresh_observes_physical_availability(
    setup, platforms, monkeypatch,
):
    loaded=setup()
    facade=platforms.climate.ManagedClimate(
        loaded.h.manager, loaded.h.spec,
    )
    assert facade.available
    changes=[]
    facade.hass = loaded.h.hass
    facade.async_on_remove = lambda fn: None
    facade.async_write_ha_state = lambda: changes.append(facade.available)
    # Use actual watcher implementation and simulate physical events.
    facade._watch_native_updates()
    before=SimpleNamespace(state="off",attributes={"fan_modes":["low"]})
    after=SimpleNamespace(state="unavailable",attributes={"fan_modes":["low"]})
    loaded.h.state.state = "unavailable"
    for cb in tuple(loaded.listeners["state_changed"]):
        cb(_physical_event(loaded,before=before,after=after))
    assert not facade.available and changes[-1] is False
    loaded.h.state.state = "off"
    for cb in tuple(loaded.listeners["state_changed"]):
        cb(_physical_event(loaded,before=after,after=before))
    assert facade.available and changes[-1] is True
    assert loaded.h.hass.services.calls == []
