"""One-time staged migration from air_quality_advisor to environment_manager.

HACS manages one integration directory per repository. The bridge release remains
installed under the legacy domain. Once a later release has installed the new
`environment_manager` package, this shim replaces the config entry in-place while
preserving its entry ID, subentry IDs, registry IDs and user customizations.
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

OLD_DOMAIN = "air_quality_advisor"
NEW_DOMAIN = "environment_manager"
DATA_KEY = f"{OLD_DOMAIN}_domain_migration"


async def async_new_domain_available(hass: HomeAssistant) -> bool:
    """Return whether the new custom integration package is installed."""
    try:
        from homeassistant import loader
    except ImportError:
        # Unit-test/minimal HA stubs: migration remains dormant.
        return False
    try:
        await loader.async_get_integration(hass, NEW_DOMAIN)
    except loader.IntegrationNotFound:
        return False
    return True


def is_domain_migration_stub(hass: HomeAssistant, entry_id: str) -> bool:
    """True while the old config entry is intentionally running without platforms."""
    return entry_id in hass.data.get(DATA_KEY, set())


def async_schedule_domain_migration(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Schedule replacement after the old config-entry setup lock is released."""
    pending = hass.data.setdefault(DATA_KEY, set())
    if entry.entry_id in pending:
        return
    pending.add(entry.entry_id)
    hass.async_create_background_task(
        _async_migrate_domain_entry(hass, entry.entry_id),
        name=f"migrate {OLD_DOMAIN} config entry {entry.entry_id} to {NEW_DOMAIN}",
    )


def _new_device_identifiers(identifiers: set[tuple[str, str]]) -> set[tuple[str, str]]:
    return {
        (NEW_DOMAIN, value) if domain == OLD_DOMAIN else (domain, value)
        for domain, value in identifiers
    }


def _preflight_registry_migration(hass: HomeAssistant, entry_id: str) -> None:
    """Fail before writes if any new-domain registry identity already conflicts."""
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    entity_registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(entity_registry, entry_id):
        if entity.platform != OLD_DOMAIN:
            continue
        conflict = entity_registry.async_get_entity_id(
            entity.domain, NEW_DOMAIN, entity.unique_id
        )
        if conflict is not None and conflict != entity.entity_id:
            raise ValueError(
                f"Cannot migrate {entity.entity_id}: new-domain unique ID is already "
                f"owned by {conflict}"
            )

    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry_id):
        for identifier in _new_device_identifiers(set(device.identifiers)):
            if identifier[0] != NEW_DOMAIN:
                continue
            conflict = device_registry.async_get_device_by_identifier(
                identifier, entry_id
            )
            if conflict is not None and conflict.id != device.id:
                raise ValueError(
                    f"Cannot migrate device {device.id}: identifier {identifier!r} "
                    f"is already owned by {conflict.id}"
                )


def _migrate_registries(hass: HomeAssistant, entry_id: str) -> None:
    """Move registry ownership namespaces without changing registry IDs."""
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    entity_registry = er.async_get(hass)
    for entity in list(er.async_entries_for_config_entry(entity_registry, entry_id)):
        if entity.platform != OLD_DOMAIN:
            continue
        entity_registry.async_update_entity_platform(
            entity.entity_id,
            NEW_DOMAIN,
            new_config_entry_id=entry_id,
            new_config_subentry_id=entity.config_subentry_id,
            new_unique_id=entity.unique_id,
            new_device_id=entity.device_id,
        )

    device_registry = dr.async_get(hass)
    for device in list(dr.async_entries_for_config_entry(device_registry, entry_id)):
        identifiers = _new_device_identifiers(set(device.identifiers))
        if identifiers != set(device.identifiers):
            device_registry.async_update_device(
                device.id, new_identifiers=identifiers
            )


def _copy_entry_with_new_domain(entry: ConfigEntry) -> ConfigEntry:
    """Build the replacement entry while preserving all stable identity fields."""
    from homeassistant.config_entries import ConfigEntry
    return ConfigEntry(
        created_at=entry.created_at,
        data=dict(entry.data),
        disabled_by=entry.disabled_by,
        discovery_keys=entry.discovery_keys,
        domain=NEW_DOMAIN,
        entry_id=entry.entry_id,
        minor_version=entry.minor_version,
        modified_at=entry.modified_at,
        options=dict(entry.options),
        pref_disable_new_entities=entry.pref_disable_new_entities,
        pref_disable_polling=entry.pref_disable_polling,
        source=entry.source,
        subentries_data=[subentry.as_dict() for subentry in entry.subentries.values()],
        title=entry.title,
        unique_id=entry.unique_id,
        version=entry.version,
    )


async def _async_migrate_domain_entry(hass: HomeAssistant, entry_id: str) -> None:
    """Replace the old config entry without clearing its registries."""
    from homeassistant.config_entries import ConfigEntryChange
    # async_setup_entry scheduled this task while its setup lock was held.
    await asyncio.sleep(0)
    pending = hass.data.setdefault(DATA_KEY, set())
    try:
        old_entry = hass.config_entries.async_get_entry(entry_id)
        if old_entry is None or old_entry.domain != OLD_DOMAIN:
            return
        if not await async_new_domain_available(hass):
            return
        if any(
            entry.entry_id != entry_id
            for entry in hass.config_entries.async_entries(NEW_DOMAIN)
        ):
            raise ValueError(
                "A separate environment_manager config entry already exists; "
                "automatic domain migration is refusing to merge entries"
            )

        _preflight_registry_migration(hass, entry_id)
        replacement = _copy_entry_with_new_domain(old_entry)

        # Registry entities are not loaded because the bridge intentionally did
        # not forward any old-domain platforms.
        _migrate_registries(hass, entry_id)

        # Private low-level APIs are intentional here: public async_remove()
        # clears the entity/device registries we are preserving. This sequence
        # mirrors ConfigEntriesFlowManager replacement, but retains entry_id.
        await hass.config_entries._async_remove(entry_id)  # noqa: SLF001
        hass.config_entries._entries[entry_id] = replacement  # noqa: SLF001
        hass.config_entries.async_update_issues()
        hass.config_entries._async_dispatch(  # noqa: SLF001
            ConfigEntryChange.ADDED, replacement
        )
        hass.config_entries._async_schedule_save()  # noqa: SLF001
        await hass.config_entries.async_setup(entry_id)
    finally:
        pending.discard(entry_id)
