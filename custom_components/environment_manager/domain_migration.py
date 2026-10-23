"""Safe one-click migration from the frozen legacy HA config-entry domain."""
from __future__ import annotations
from typing import Any

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, LEGACY_DOMAIN


def legacy_entries(hass: Any) -> list[Any]:
    return list(hass.config_entries.async_entries(LEGACY_DOMAIN))


def _new_identifiers(identifiers):
    return {(DOMAIN if domain == LEGACY_DOMAIN else domain, value)
            for domain, value in identifiers}


async def async_migrate_legacy_registry(
    hass: Any, legacy: Any, new: Any
) -> None:
    """Move registry ownership first; remove legacy entry only after success."""
    from homeassistant.config_entries import ConfigEntryState
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    if legacy.domain != LEGACY_DOMAIN or new.domain != DOMAIN:
        raise HomeAssistantError("Unexpected domain migration endpoints")
    if legacy.entry_id == new.entry_id:
        raise HomeAssistantError("Domain migration requires a distinct config entry")

    if legacy.state is ConfigEntryState.LOADED:
        if not await hass.config_entries.async_unload(legacy.entry_id):
            raise HomeAssistantError("Could not unload legacy Environment Manager entry")

    dev_reg=dr.async_get(hass)
    ent_reg=er.async_get(hass)
    devices=list(dr.async_entries_for_config_entry(dev_reg, legacy.entry_id))
    entities=list(er.async_entries_for_config_entry(ent_reg, legacy.entry_id))

    # Move entities before their devices. HA 2026.10 device reassignment can
    # reconcile registry relationships; platform ownership first preserves
    # entity_id/unique_id/device_id deterministically.
    devices.sort(key=lambda d: bool(getattr(d,"parent_device_id",None)))
    moved_devices=[]
    moved_entities=[]
    try:
        for entity in entities:
            ent_reg.async_update_entity_platform(
                entity.entity_id,
                DOMAIN,
                new_config_entry_id=new.entry_id,
                new_config_subentry_id=entity.config_subentry_id,
            )
            moved_entities.append((entity.entity_id,entity.config_subentry_id))

        for device in devices:
            old_ids=set(device.identifiers)
            dev_reg.async_update_device(
                device.id,
                new_config_entry_id=new.entry_id,
                new_config_subentry_id=device.config_subentry_id,
                new_identifiers=_new_identifiers(old_ids),
            )
            moved_devices.append((device.id,old_ids,device.config_subentry_id))

        # Cleanup no longer touches migrated registries because ownership moved.
        await hass.config_entries.async_remove(legacy.entry_id)
    except Exception:
        # Best-effort rollback while the legacy entry still exists.
        if hass.config_entries.async_get_entry(legacy.entry_id) is not None:
            for device_id,old_ids,subentry_id in reversed(moved_devices):
                try:
                    dev_reg.async_update_device(
                        device_id,
                        new_config_entry_id=legacy.entry_id,
                        new_config_subentry_id=subentry_id,
                        new_identifiers=old_ids,
                    )
                except Exception:
                    pass
            for entity_id,subentry_id in reversed(moved_entities):
                try:
                    ent_reg.async_update_entity_platform(
                        entity_id, LEGACY_DOMAIN,
                        new_config_entry_id=legacy.entry_id,
                        new_config_subentry_id=subentry_id,
                    )
                except Exception:
                    pass
        raise


async def async_open_migrated_store(hass: Any, version: int, suffix: str, entry_or_id: Any):
    """Open canonical store and import legacy state when a migration marker exists.

    Lightweight unit runtimes often expose only entry_id; that must continue
    using the canonical store without requiring a full ConfigEntries object.
    """
    from homeassistant.helpers.storage import Store
    entry = entry_or_id if hasattr(entry_or_id, "entry_id") else None
    entry_id = getattr(entry_or_id, "entry_id", entry_or_id)
    if not isinstance(entry_id, str) or not entry_id:
        raise HomeAssistantError("Missing Environment Manager config entry identity")
    store=Store(hass,version,f"{DOMAIN}.{suffix}_{entry_id}")
    loaded=await store.async_load()
    if loaded is not None:
        return store,loaded
    if entry is None:
        entries=getattr(hass,"config_entries",None)
        getter=getattr(entries,"async_get_entry",None)
        if getter is not None:
            entry=getter(entry_id)
    legacy_id=getattr(entry,"data",{}).get("_legacy_entry_id") if entry is not None else None
    if not isinstance(legacy_id,str) or not legacy_id:
        return store,None
    legacy=Store(hass,version,f"{LEGACY_DOMAIN}.{suffix}_{legacy_id}")
    loaded=await legacy.async_load()
    if loaded is not None:
        await store.async_save(loaded)
    return store,loaded
