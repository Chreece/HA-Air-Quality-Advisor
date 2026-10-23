"""Safe one-click migration from every previous Home Environment Manager domain."""
from __future__ import annotations
from typing import Any

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, LEGACY_DOMAIN, LEGACY_DOMAINS


def legacy_entries(hass: Any) -> list[Any]:
    entries = []
    for domain in LEGACY_DOMAINS:
        entries.extend(hass.config_entries.async_entries(domain))
    return entries


def _new_identifiers(identifiers, source_domain: str):
    return {(DOMAIN if domain == source_domain else domain, value)
            for domain, value in identifiers}


async def async_migrate_legacy_registry(hass: Any, legacy: Any, new: Any) -> None:
    from homeassistant.config_entries import ConfigEntryState
    from homeassistant.helpers import device_registry as dr, entity_registry as er

    source_domain = legacy.domain
    if source_domain not in LEGACY_DOMAINS or new.domain != DOMAIN:
        raise HomeAssistantError("Unexpected domain migration endpoints")
    if legacy.entry_id == new.entry_id:
        raise HomeAssistantError("Domain migration requires a distinct config entry")
    if legacy.state is ConfigEntryState.LOADED:
        if not await hass.config_entries.async_unload(legacy.entry_id):
            raise HomeAssistantError("Could not unload legacy Environment Manager entry")

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    devices = list(dr.async_entries_for_config_entry(dev_reg, legacy.entry_id))
    entities = list(er.async_entries_for_config_entry(ent_reg, legacy.entry_id))
    devices.sort(key=lambda d: bool(getattr(d, "parent_device_id", None)))
    moved_devices = []
    moved_entities = []
    try:
        for entity in entities:
            ent_reg.async_update_entity_platform(
                entity.entity_id, DOMAIN,
                new_config_entry_id=new.entry_id,
                new_config_subentry_id=entity.config_subentry_id,
            )
            moved_entities.append((entity.entity_id, entity.config_subentry_id))
        for device in devices:
            old_ids = set(device.identifiers)
            dev_reg.async_update_device(
                device.id,
                new_config_entry_id=new.entry_id,
                new_config_subentry_id=device.config_subentry_id,
                new_identifiers=_new_identifiers(old_ids, source_domain),
            )
            moved_devices.append((device.id, old_ids, device.config_subentry_id))
        await hass.config_entries.async_remove(legacy.entry_id)
    except Exception:
        if hass.config_entries.async_get_entry(legacy.entry_id) is not None:
            for device_id, old_ids, subentry_id in reversed(moved_devices):
                try:
                    dev_reg.async_update_device(
                        device_id,
                        new_config_entry_id=legacy.entry_id,
                        new_config_subentry_id=subentry_id,
                        new_identifiers=old_ids,
                    )
                except Exception:
                    pass
            for entity_id, subentry_id in reversed(moved_entities):
                try:
                    ent_reg.async_update_entity_platform(
                        entity_id, source_domain,
                        new_config_entry_id=legacy.entry_id,
                        new_config_subentry_id=subentry_id,
                    )
                except Exception:
                    pass
        raise


def _migration_markers(entry: Any) -> list[tuple[str, str]]:
    data = getattr(entry, "data", {}) if entry is not None else {}
    if not isinstance(data, dict):
        return []
    markers = []
    entry_id = data.get("_legacy_entry_id")
    domain = data.get("_legacy_domain")
    if isinstance(entry_id, str) and entry_id:
        markers.append((domain if domain in LEGACY_DOMAINS else LEGACY_DOMAIN, entry_id))
    chain = data.get("_legacy_entry_chain")
    if isinstance(chain, list):
        for item in chain:
            if not isinstance(item, dict):
                continue
            item_id = item.get("entry_id")
            item_domain = item.get("domain")
            if isinstance(item_id, str) and item_id and item_domain in LEGACY_DOMAINS:
                marker = (item_domain, item_id)
                if marker not in markers:
                    markers.append(marker)
    return markers


async def async_open_migrated_store(hass: Any, version: int, suffix: str, entry_or_id: Any):
    from homeassistant.helpers.storage import Store

    entry = entry_or_id if hasattr(entry_or_id, "entry_id") else None
    entry_id = getattr(entry_or_id, "entry_id", entry_or_id)
    if not isinstance(entry_id, str) or not entry_id:
        raise HomeAssistantError("Missing Environment Manager config entry identity")
    store = Store(hass, version, f"{DOMAIN}.{suffix}_{entry_id}")
    loaded = await store.async_load()
    if loaded is not None:
        return store, loaded
    if entry is None:
        entries = getattr(hass, "config_entries", None)
        getter = getattr(entries, "async_get_entry", None)
        if getter is not None:
            entry = getter(entry_id)
    for legacy_domain, legacy_id in _migration_markers(entry):
        legacy = Store(hass, version, f"{legacy_domain}.{suffix}_{legacy_id}")
        loaded = await legacy.async_load()
        if loaded is not None:
            await store.async_save(loaded)
            return store, loaded
    return store, None
