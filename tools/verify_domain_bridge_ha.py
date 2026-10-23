"""Verify legacy-domain registry migration with real Home Assistant 2026.10."""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import MappingProxyType

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from homeassistant.config_entries import ConfigEntries, ConfigEntry, ConfigSubentry, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er

from custom_components.air_quality_advisor.domain_migration import (
    NEW_DOMAIN,
    OLD_DOMAIN,
    _copy_entry_with_new_domain,
    _migrate_registries,
    _preflight_registry_migration,
)


async def check(config_dir: str) -> None:
    hass = HomeAssistant(config_dir)
    hass.config_entries = ConfigEntries(hass, {})
    dr.async_setup(hass)
    await ar.async_load(hass)
    await dr.async_load(hass)
    await er.async_load(hass)
    devices = dr.async_get(hass)
    entities = er.async_get(hass)

    subentry = ConfigSubentry(
        data=MappingProxyType({"area_id": "living"}),
        subentry_id="stable-room-subentry",
        subentry_type="room",
        title="Living room",
        unique_id="living",
    )
    old = ConfigEntry(
        data={"areas": ["living"]},
        options={"language": "el"},
        domain=OLD_DOMAIN,
        entry_id="stable-entry-id",
        title="Home Environment Manager",
        source=SOURCE_USER,
        unique_id="home",
        version=1,
        minor_version=0,
        discovery_keys=MappingProxyType({}),
        subentries_data=(subentry.as_dict(),),
    )
    hass.config_entries._entries[old.entry_id] = old

    home = devices.async_get_or_create(
        config_entry_id=old.entry_id,
        config_subentry_id=subentry.subentry_id,
        identifiers={(OLD_DOMAIN, old.entry_id)},
        name="Home",
    )
    devices.async_update_device(
        home.id,
        area_id="living",
        name_by_user="My Home",
        disabled_by=dr.DeviceEntryDisabler.USER,
    )
    number = entities.async_get_or_create(
        "number",
        OLD_DOMAIN,
        "stable-number-unique-id",
        config_entry=old,
        config_subentry_id=subentry.subentry_id,
        device_id=home.id,
        suggested_object_id="stable_room_limit",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    entities.async_update_entity(
        number.entity_id,
        name="My limit",
        icon="mdi:thermometer",
    )

    old_device_id = home.id
    old_entity_id = number.entity_id
    old_entity_registry_id = number.id

    _preflight_registry_migration(hass, old.entry_id)
    replacement = _copy_entry_with_new_domain(old)
    _migrate_registries(hass, old.entry_id)

    del hass.config_entries._entries[old.entry_id]
    hass.config_entries._entries[replacement.entry_id] = replacement

    migrated_device = devices.async_get(old_device_id)
    migrated_entity = entities.async_get(old_entity_id)
    current = hass.config_entries.async_get_entry(old.entry_id)

    assert current is not None
    assert current.entry_id == old.entry_id
    assert current.domain == NEW_DOMAIN
    assert current.options["language"] == "el"
    assert list(current.subentries) == [subentry.subentry_id]

    assert migrated_device is not None
    assert migrated_device.id == old_device_id
    assert (NEW_DOMAIN, old.entry_id) in migrated_device.identifiers
    assert all(domain != OLD_DOMAIN for domain, _ in migrated_device.identifiers)
    assert migrated_device.name_by_user == "My Home"
    assert migrated_device.area_id == "living"
    assert migrated_device.disabled_by == dr.DeviceEntryDisabler.USER

    assert migrated_entity is not None
    assert migrated_entity.id == old_entity_registry_id
    assert migrated_entity.entity_id == old_entity_id
    assert migrated_entity.unique_id == "stable-number-unique-id"
    assert migrated_entity.platform == NEW_DOMAIN
    assert migrated_entity.config_entry_id == old.entry_id
    assert migrated_entity.config_subentry_id == subentry.subentry_id
    assert migrated_entity.device_id == old_device_id
    assert migrated_entity.disabled_by == er.RegistryEntryDisabler.USER
    assert migrated_entity.name == "My limit"
    assert migrated_entity.icon == "mdi:thermometer"

    await hass.async_block_till_done()
    await hass.async_stop(force=True)
    print("HA 2026.10 domain bridge registry identity migration: PASS")


if __name__ == "__main__":
    with TemporaryDirectory(prefix="hem-domain-bridge-") as directory:
        asyncio.run(check(directory))
