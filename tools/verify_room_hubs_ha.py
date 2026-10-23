"""Isolated registry migration using installed Home Assistant, not HA test doubles.

Run in a separate environment with homeassistant==2026.10.0. No integration
setup or actuator service is called. The private config-entry insertion is test
fixture construction only; all code under test uses supported registry APIs.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import MappingProxyType, SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from homeassistant.config_entries import ConfigEntries, ConfigEntry, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from custom_components.enviroment_manager.const import DOMAIN
from custom_components.enviroment_manager.device_hierarchy import async_register_hierarchy
from custom_components.enviroment_manager.room_hubs import (
    HOME_TYPE, async_sync_room_hubs, home_subentry_id,
)


async def check(config_dir: str) -> None:
    hass = HomeAssistant(config_dir)
    hass.config_entries = ConfigEntries(hass, {})
    # HA 2026.10 registers devices before loading the registry stores;
    # async_load() returns None, so fetch the registry instances afterwards.
    dr.async_setup(hass)
    await ar.async_load(hass)
    await dr.async_load(hass)
    await er.async_load(hass)
    area_registry = ar.async_get(hass)
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    area = area_registry.async_create("Test room")
    entry = ConfigEntry(
        data={"areas": [area.id]}, options={}, domain=DOMAIN,
        entry_id="room-hubs-migration-test", title="Home Environment Manager",
        source=SOURCE_USER, unique_id="room-hubs-migration-test", version=1,
        minor_version=1, discovery_keys=MappingProxyType({}), subentries_data=(),
    )
    # Register a stored entry without starting the integration or any hardware.
    hass.config_entries._entries[entry.entry_id] = entry
    old = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_area_{area.id}")},
        entry_type=dr.DeviceEntryType.SERVICE, name="Existing room settings",
    )
    device_registry.async_update_device(old.id, name_by_user="My room settings", area_id=area.id)
    entity = entity_registry.async_get_or_create(
        "number", DOMAIN, "existing-setting-unique-id", config_entry=entry,
        device_id=old.id, suggested_object_id="existing_room_setting",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    manager = SimpleNamespace(hass=hass, entry=entry, settings={**entry.data, **entry.options})
    entry.runtime_data = manager
    groups = async_sync_room_hubs(hass, entry)
    manager._room_subentries = groups
    async_register_hierarchy(hass, entry)
    current = device_registry.async_get(old.id)
    actual_entity = entity_registry.async_get(entity.entity_id)
    assert current is not None and current.entry_type is None
    assert current.id == old.id and current.name_by_user == "My room settings"
    assert current.config_subentry_id == groups[area.id]
    assert actual_entity.unique_id == entity.unique_id
    assert actual_entity.device_id == old.id
    assert actual_entity.config_subentry_id == groups[area.id]
    assert actual_entity.disabled_by == er.RegistryEntryDisabler.USER
    before = dict(groups)
    manager._room_subentries = async_sync_room_hubs(hass, entry)
    async_register_hierarchy(hass, entry)
    assert manager._room_subentries == before
    home_sid = home_subentry_id(entry)
    assert home_sid is not None
    assert entry.subentries[home_sid].subentry_type == HOME_TYPE
    assert len(entry.subentries) == 2  # Home + selected room.
    assert manager._device_hierarchy["device_subentries"][entry.entry_id] == home_sid
    home_device = device_registry.async_get(manager._device_hierarchy["home_device_id"])
    assert home_device is not None and home_device.config_subentry_id == home_sid
    assert device_registry.async_get(old.id).config_subentry_id == groups[area.id]
    # Room removal uses the real config-entry and registry cleanup paths.
    hass.config_entries.async_remove_subentry(entry, groups[area.id])
    assert async_sync_room_hubs(hass, entry) == {}
    assert area.id not in entry.options["areas"]
    remaining = list(entry.subentries.values())
    assert len(remaining) == 1 and remaining[0].subentry_type == HOME_TYPE
    await hass.async_block_till_done()
    await hass.async_stop(force=True)
    print("Home Assistant 2026.10 real-registry migration, identity preservation, reload and room removal: PASS")


if __name__ == "__main__":
    with TemporaryDirectory(prefix="hem-room-hubs-") as directory:
        asyncio.run(check(directory))
