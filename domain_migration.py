"""Safe in-place migration from previous Home Environment Manager domains."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, LEGACY_STORAGE_DEFAULT_DOMAIN, MIGRATION_SOURCE_DOMAINS





async def async_quarantine_legacy_component_dirs(hass: Any) -> list[str]:
    """Move verified legacy integration folders out of custom_components.

    This removes duplicate installable integrations while keeping a recoverable
    backup. Only folders whose own manifest domain exactly matches a known
    historical domain are touched.
    """

    def _move() -> list[str]:
        config_dir = Path(hass.config.config_dir)
        custom_components = config_dir / "custom_components"
        backup_root = config_dir / ".environment_manager_legacy_components"
        moved: list[str] = []

        for legacy_domain in MIGRATION_SOURCE_DOMAINS:
            source = custom_components / legacy_domain
            manifest_path = source / "manifest.json"
            if not source.is_dir() or not manifest_path.is_file():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                continue
            if manifest.get("domain") != legacy_domain:
                continue

            backup_root.mkdir(parents=True, exist_ok=True)
            target = backup_root / legacy_domain
            suffix = 1
            while target.exists():
                target = backup_root / f"{legacy_domain}.{suffix}"
                suffix += 1
            source.rename(target)
            moved.append(legacy_domain)

        return moved

    moved = await hass.async_add_executor_job(_move)
    if moved:
        # Home Assistant caches discovered custom integrations. Rebuild the
        # cache so the removed legacy folders disappear from Add Integration.
        try:
            from homeassistant import loader

            hass.data.pop("custom_components", None)
            await loader.async_get_custom_components(hass)
        except Exception:
            # Disk cleanup succeeded; a normal restart will refresh the cache.
            pass
    return moved


def legacy_entries(hass: Any) -> list[Any]:
    """Return entries owned by a previous integration domain."""
    entries: list[Any] = []
    for domain in MIGRATION_SOURCE_DOMAINS:
        entries.extend(hass.config_entries.async_entries(domain))
    return entries


def _new_identifiers(identifiers: Any, source_domain: str) -> set[tuple[str, str]]:
    return {
        (DOMAIN if domain == source_domain else domain, value)
        for domain, value in identifiers
    }


def _migration_data(entry: Any, source_domain: str) -> dict[str, Any]:
    """Preserve storage ancestry while making the current source authoritative."""
    data = dict(entry.data)
    chain = list(data.get("_legacy_entry_chain") or [])
    previous_id = data.get("_legacy_entry_id")
    previous_domain = data.get("_legacy_domain")
    if isinstance(previous_id, str) and previous_id:
        marker = {
            "domain": (
                previous_domain if previous_domain in MIGRATION_SOURCE_DOMAINS else LEGACY_STORAGE_DEFAULT_DOMAIN
            ),
            "entry_id": previous_id,
        }
        if marker not in chain:
            chain.insert(0, marker)

    data["_legacy_entry_id"] = entry.entry_id
    data["_legacy_domain"] = source_domain
    if chain:
        data["_legacy_entry_chain"] = chain
    return data


def _entry_items(hass: Any, entry: Any) -> Any:
    """Return the HA 2026.10 indexed entry store or fail closed.

    Home Assistant intentionally freezes ConfigEntry.domain and exposes no public
    cross-domain update method. The migration therefore uses the same indexed
    ConfigEntryItems object HA itself uses, but only after checking the exact
    capabilities we depend on. A future HA change fails instead of risking a
    duplicate or a partially re-indexed home.
    """
    items = getattr(hass.config_entries, "_entries", None)
    required = ("data", "_unindex_entry", "_index_entry")
    if items is None or any(not hasattr(items, name) for name in required):
        raise HomeAssistantError(
            "This Home Assistant version does not expose the validated "
            "config-entry reindex API required for an identity-preserving migration"
        )
    if items.data.get(entry.entry_id) is not entry:
        raise HomeAssistantError("Legacy config entry identity changed during migration")
    return items


def _reset_domain_caches(entry: Any) -> None:
    """Clear values cached from the previous integration domain."""
    setter = object.__setattr__
    for name, value in (
        ("_integration_for_domain", None),
        ("_supports_options", None),
        ("_supports_reconfigure", None),
        ("_supported_subentry_types", None),
        ("supports_unload", None),
        ("supports_remove_device", None),
    ):
        if hasattr(entry, name):
            setter(entry, name, value)
    entry.clear_state_cache()
    entry.clear_storage_cache()


def _reindex_entry_domain(hass: Any, entry: Any, new_domain: str) -> None:
    """Move one existing ConfigEntry between domain indexes without changing ID."""
    items = _entry_items(hass, entry)
    old_domain = entry.domain
    if old_domain == new_domain:
        return
    items._unindex_entry(entry.entry_id)
    try:
        object.__setattr__(entry, "domain", new_domain)
        _reset_domain_caches(entry)
        items._index_entry(entry)
    except Exception:
        object.__setattr__(entry, "domain", old_domain)
        _reset_domain_caches(entry)
        items._index_entry(entry)
        raise


async def async_migrate_legacy_registry(hass: Any, legacy: Any) -> Any:
    """Re-home a legacy entry and registries while preserving its exact entry_id."""
    from homeassistant.config_entries import ConfigEntryState
    from homeassistant.helpers import device_registry as dr, entity_registry as er

    source_domain = legacy.domain
    if source_domain not in MIGRATION_SOURCE_DOMAINS:
        raise HomeAssistantError("Unexpected domain migration source")
    if hass.config_entries.async_entries(DOMAIN):
        raise HomeAssistantError(
            "A canonical Home Environment Manager entry already exists; "
            "migration will not merge homes"
        )

    # A HACS folder replacement commonly leaves the legacy entry in setup_error.
    # Loaded entries are unloaded first; non-recoverable/transitional states fail
    # closed rather than mutating identity while HA is operating on the entry.
    if legacy.state is ConfigEntryState.LOADED:
        if not await hass.config_entries.async_unload(legacy.entry_id):
            raise HomeAssistantError("Could not unload legacy Environment Manager entry")
    elif legacy.state in (
        ConfigEntryState.FAILED_UNLOAD,
        ConfigEntryState.SETUP_IN_PROGRESS,
        ConfigEntryState.UNLOAD_IN_PROGRESS,
        ConfigEntryState.MIGRATION_ERROR,
    ):
        raise HomeAssistantError(
            f"Legacy config entry is in unsafe migration state {legacy.state}"
        )

    legacy.async_cancel_retry_setup()
    original_state = legacy.state
    original_reason = getattr(legacy, "reason", None)
    original_data = dict(legacy.data)

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    devices = list(dr.async_entries_for_config_entry(dev_reg, legacy.entry_id))
    entities = list(er.async_entries_for_config_entry(ent_reg, legacy.entry_id))
    devices.sort(key=lambda d: bool(getattr(d, "parent_device_id", None)))

    moved_devices: list[tuple[str, set[tuple[str, str]]]] = []
    moved_entities: list[tuple[str, str | None]] = []
    domain_changed = False
    try:
        # Keep config_entry_id and config_subentry_id untouched. Only the
        # integration platform / Manager-owned identifier namespace changes.
        for entity in entities:
            ent_reg.async_update_entity_platform(
                entity.entity_id,
                DOMAIN,
                new_config_entry_id=legacy.entry_id,
                new_config_subentry_id=entity.config_subentry_id,
            )
            moved_entities.append((entity.entity_id, entity.config_subentry_id))

        for device in devices:
            old_ids = set(device.identifiers)
            dev_reg.async_update_device(
                device.id,
                new_identifiers=_new_identifiers(old_ids, source_domain),
            )
            moved_devices.append((device.id, old_ids))

        _reindex_entry_domain(hass, legacy, DOMAIN)
        domain_changed = True

        # setup_error/setup_retry from the now-missing old package must not
        # poison setup under the new canonical domain.
        legacy._async_set_state(hass, ConfigEntryState.NOT_LOADED, None)
        hass.config_entries.async_update_entry(
            legacy,
            data=_migration_data(legacy, source_domain),
            title=(
                "Home Environment Manager"
                if legacy.title in ("Air Quality Advisor", "Home Environment Advisor")
                else legacy.title
            ),
        )
        hass.config_entries.async_update_issues()
        hass.config_entries._async_schedule_save()
        return legacy
    except Exception:
        if domain_changed:
            try:
                _reindex_entry_domain(hass, legacy, source_domain)
            except Exception:
                pass
        try:
            hass.config_entries.async_update_entry(legacy, data=original_data)
        except Exception:
            pass
        try:
            object.__setattr__(legacy, "state", original_state)
            object.__setattr__(legacy, "reason", original_reason)
            legacy.clear_state_cache()
            legacy.clear_storage_cache()
        except Exception:
            pass
        for device_id, old_ids in reversed(moved_devices):
            try:
                dev_reg.async_update_device(device_id, new_identifiers=old_ids)
            except Exception:
                pass
        for entity_id, subentry_id in reversed(moved_entities):
            try:
                ent_reg.async_update_entity_platform(
                    entity_id,
                    source_domain,
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
    markers: list[tuple[str, str]] = []
    entry_id = data.get("_legacy_entry_id")
    domain = data.get("_legacy_domain")
    if isinstance(entry_id, str) and entry_id:
        markers.append(
            (domain if domain in MIGRATION_SOURCE_DOMAINS else LEGACY_STORAGE_DEFAULT_DOMAIN, entry_id)
        )
    chain = data.get("_legacy_entry_chain")
    if isinstance(chain, list):
        for item in chain:
            if not isinstance(item, dict):
                continue
            item_id = item.get("entry_id")
            item_domain = item.get("domain")
            if isinstance(item_id, str) and item_id and item_domain in MIGRATION_SOURCE_DOMAINS:
                marker = (item_domain, item_id)
                if marker not in markers:
                    markers.append(marker)
    return markers


async def async_open_migrated_store(
    hass: Any, version: int, suffix: str, entry_or_id: Any
):
    """Open canonical storage and import the first available legacy ancestor."""
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
        legacy_store = Store(
            hass, version, f"{legacy_domain}.{suffix}_{legacy_id}"
        )
        loaded = await legacy_store.async_load()
        if loaded is not None:
            await store.async_save(loaded)
            return store, loaded
    return store, None
