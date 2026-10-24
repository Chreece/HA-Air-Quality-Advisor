"""Actual HA 2026.10 identity-preserving domain migration verification."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import MappingProxyType

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from homeassistant import loader
from homeassistant.config_entries import (
    ConfigEntries,
    ConfigEntry,
    ConfigEntryState,
    SOURCE_USER,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.environment_manager.const import (
    DOMAIN,
    LEGACY_STORAGE_DEFAULT_DOMAIN,
    MIGRATION_SOURCE_DOMAINS,
)

BETA20_DOMAIN = MIGRATION_SOURCE_DOMAINS[0]
LEGACY_DOMAIN = LEGACY_STORAGE_DEFAULT_DOMAIN
from custom_components.environment_manager.domain_migration import (
    async_migrate_legacy_registry,
    async_quarantine_legacy_component_dirs,
)


async def check(config_dir: str, source_domain: str) -> None:
    hass = HomeAssistant(config_dir)
    loader.async_setup(hass)
    hass.config_entries = ConfigEntries(hass, {})
    dr.async_setup(hass)
    await dr.async_load(hass)
    await er.async_load(hass)
    devices = dr.async_get(hass)
    entities = er.async_get(hass)

    sub_id = "room-subentry-unchanged"
    entry_id = f"same-entry-{source_domain}"
    sub = [{
        "subentry_id": sub_id,
        "data": {"area_id": "living"},
        "subentry_type": "room",
        "title": "Living",
        "unique_id": "living",
    }]
    old_data = {"areas": ["living"]}
    if source_domain == BETA20_DOMAIN:
        # Simulate a real chained beta19 -> beta20 installation. Beta22 must
        # preserve this ancestry while keeping the beta20 config-entry ID.
        old_data.update({
            "_legacy_entry_id": "older-beta19-entry",
            "_legacy_domain": LEGACY_DOMAIN,
        })

    old = ConfigEntry(
        data=old_data,
        options={"saved": True},
        domain=source_domain,
        entry_id=entry_id,
        title="Home Environment Advisor",
        source=SOURCE_USER,
        unique_id="home",
        version=1,
        minor_version=1,
        discovery_keys=MappingProxyType({}),
        subentries_data=sub,
        state=ConfigEntryState.SETUP_ERROR,
    )
    hass.config_entries._entries[old.entry_id] = old

    device = devices.async_get_or_create(
        config_entry_id=old.entry_id,
        config_subentry_id=sub_id,
        identifiers={(source_domain, "managed-device")},
        name="Managed device",
    )
    devices.async_update_device(device.id, name_by_user="My custom device")
    entity = entities.async_get_or_create(
        "number",
        source_domain,
        "stable-unique",
        config_entry=old,
        config_subentry_id=sub_id,
        device_id=device.id,
        suggested_object_id="stable_entity",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    old_entity_id = entity.entity_id
    old_device_id = device.id
    old_subentry = old.subentries[sub_id]

    migrated = await async_migrate_legacy_registry(hass, old)

    # The contract: exact same ConfigEntry object and exact same entry_id.
    assert migrated is old
    assert migrated.entry_id == entry_id
    assert hass.config_entries.async_get_entry(entry_id) is old
    assert old.domain == DOMAIN
    assert old.state is ConfigEntryState.NOT_LOADED
    assert hass.config_entries.async_entries(source_domain) == []
    assert hass.config_entries.async_entries(DOMAIN) == [old]
    assert old.subentries[sub_id] is old_subentry
    assert old.options["saved"] is True
    assert old.title == "Home Environment Manager"
    assert old.data["_legacy_entry_id"] == entry_id
    assert old.data["_legacy_domain"] == source_domain
    if source_domain == BETA20_DOMAIN:
        assert {
            "domain": LEGACY_DOMAIN,
            "entry_id": "older-beta19-entry",
        } in old.data["_legacy_entry_chain"]

    migrated_entity = entities.async_get(old_entity_id)
    assert migrated_entity is not None
    assert migrated_entity.entity_id == old_entity_id
    assert migrated_entity.unique_id == "stable-unique"
    assert migrated_entity.platform == DOMAIN
    assert migrated_entity.config_entry_id == entry_id
    assert migrated_entity.config_subentry_id == sub_id
    assert migrated_entity.device_id == old_device_id
    assert migrated_entity.disabled_by is er.RegistryEntryDisabler.USER

    moved = devices.async_get(old_device_id)
    assert moved is not None
    assert moved.id == old_device_id
    assert moved.config_entry_id == entry_id
    assert moved.config_subentry_id == sub_id
    assert moved.name_by_user == "My custom device"
    assert (DOMAIN, "managed-device") in moved.identifiers
    assert not any(domain == source_domain for domain, _ in moved.identifiers)

    await hass.async_block_till_done()
    await hass.async_stop(force=True)


async def check_legacy_folder_cleanup(config_dir: str) -> None:
    """Verified old packages leave custom_components but remain recoverable."""
    config = Path(config_dir)
    custom = config / "custom_components"
    custom.mkdir(parents=True, exist_ok=True)

    for domain in MIGRATION_SOURCE_DOMAINS:
        folder = custom / domain
        folder.mkdir()
        (folder / "manifest.json").write_text(
            json.dumps({"domain": domain, "name": "Legacy"}),
            encoding="utf-8",
        )
        (folder / "marker.txt").write_text(domain, encoding="utf-8")

    # A foreign folder must never be touched merely because it exists.
    foreign = custom / "unrelated_component"
    foreign.mkdir()
    (foreign / "manifest.json").write_text(
        json.dumps({"domain": "unrelated_component", "name": "Other"}),
        encoding="utf-8",
    )

    hass = HomeAssistant(config_dir)
    loader.async_setup(hass)
    moved = await async_quarantine_legacy_component_dirs(hass)

    assert set(moved) == set(MIGRATION_SOURCE_DOMAINS)
    for domain in MIGRATION_SOURCE_DOMAINS:
        assert not (custom / domain).exists()
        backups = sorted(
            (config / ".environment_manager_legacy_components").glob(f"{domain}*")
        )
        assert backups
        assert any((item / "marker.txt").read_text(encoding="utf-8") == domain for item in backups)

    assert foreign.is_dir()
    await hass.async_block_till_done()
    await hass.async_stop(force=True)


if __name__ == "__main__":
    for domain in (LEGACY_DOMAIN, BETA20_DOMAIN):
        with TemporaryDirectory(prefix=f"hem-domain-{domain}-") as directory:
            asyncio.run(check(directory, domain))
    with TemporaryDirectory(prefix="hem-legacy-folders-") as directory:
        asyncio.run(check_legacy_folder_cleanup(directory))
    print(
        "Home Assistant 2026.10 single-domain migration and legacy-folder cleanup: PASS"
    )
