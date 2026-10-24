"""Native HA room groups, independent of controller/device identity.

A via-device link describes topology; only a config subentry groups devices
in the integrations UI. Each configured room therefore has a subentry whose
ordinary devices are its general settings hub and managed equipment. This
module changes registry/configuration metadata only, never physical hardware.
"""
from __future__ import annotations

from collections.abc import Iterable
from .config_data import mutable_copy as deepcopy
from types import MappingProxyType
from typing import Any

from .const import CONF_AREAS, CONF_CLIMATE_ROOMS, CONF_PID_ROOMS, DOMAIN

ROOM_TYPE = "room"
ROOM_IDS = "room_hub_subentry_ids"
HOME_TYPE = "home"


def home_subentry_id(entry: Any) -> str | None:
    """Resolve the single native Home group without persisting a private ID."""
    subentries = getattr(entry, "subentries", {}) or {}
    matches = [sub.subentry_id for sub in subentries.values()
               if sub.subentry_type == HOME_TYPE]
    return matches[0] if len(matches) == 1 else None


def _saved_ids(entry: Any) -> dict[str, str]:
    raw = entry.options.get(ROOM_IDS, {})
    return {area: sid for area, sid in raw.items()
            if isinstance(area, str) and isinstance(sid, str)} if isinstance(raw, dict) else {}


def async_reconcile_removed_rooms(hass: Any, entry: Any) -> set[str]:
    """A UI-deleted group must not be recreated or keep authorizing equipment.

    Retain its calibration, tuning and runtime recovery records. Only remove
    monitoring selection and disable that room's control grants. Original
    owned-output retirement/reconciliation remains with the existing drivers.
    """
    saved = _saved_ids(entry)
    removed = {area for area, sid in saved.items() if sid not in entry.subentries}
    if not removed:
        return set()
    settings = {**entry.data, **entry.options}
    options = deepcopy(dict(entry.options))
    options[ROOM_IDS] = {a: sid for a, sid in saved.items() if a not in removed}
    options[CONF_AREAS] = [a for a in settings.get(CONF_AREAS, []) if a not in removed]
    for section in (CONF_CLIMATE_ROOMS, CONF_PID_ROOMS):
        rooms = settings.get(section, {})
        if not isinstance(rooms, dict) or not removed.intersection(rooms):
            continue
        rooms = deepcopy(rooms)
        for area in removed:
            if isinstance(rooms.get(area), dict):
                rooms[area]["enabled"] = False
                if section == CONF_CLIMATE_ROOMS:
                    rooms[area]["allow_actuation"] = False
                    # Explicit UI removal withdraws inventory membership too;
                    # per-device tuning remains in device_settings for reuse.
                    rooms[area]["selected_devices"] = []
        options[section] = rooms
    hass.config_entries.async_update_entry(entry, options=options)
    return removed


def async_sync_room_hubs(hass: Any, entry: Any) -> dict[str, str]:
    """Create/migrate grouping once, preserving IDs and custom room titles."""
    from homeassistant.config_entries import ConfigSubentry
    from homeassistant.helpers import area_registry as ar
    from .device_hierarchy import configured_area_ids

    async_reconcile_removed_rooms(hass, entry)
    areas = ar.async_get(hass)
    settings = {**entry.data, **entry.options}
    selected = {area: obj for area in configured_area_ids(settings)
                if (obj := areas.async_get_area(area)) is not None}
    home_entries = [sub for sub in tuple(entry.subentries.values())
                    if sub.subentry_type == HOME_TYPE]
    if len(home_entries) > 1:
        raise ValueError("Duplicate Home Environment Manager Home hub")
    if home_entries:
        home = home_entries[0]
    else:
        home = ConfigSubentry(data=MappingProxyType({"kind": "home"}),
                              subentry_type=HOME_TYPE, title="Home",
                              unique_id="home")
        hass.config_entries.async_add_subentry(entry, home)

    existing = {}
    for sub in tuple(entry.subentries.values()):
        if sub.subentry_type != ROOM_TYPE or not isinstance(sub.data.get("area_id"), str):
            continue
        area_id = sub.data["area_id"]
        if area_id in existing:
            raise ValueError(f"Duplicate Home Environment Manager room hub: {area_id}")
        existing[area_id] = sub

    result = {}
    for area_id, area in selected.items():
        sub = existing.get(area_id)
        if sub is None:
            sub = ConfigSubentry(data=MappingProxyType({"area_id": area_id, "area_name": area.name}),
                                 subentry_type=ROOM_TYPE, title=area.name,
                                 unique_id=f"area:{area_id}")
            hass.config_entries.async_add_subentry(entry, sub)
        elif sub.data.get("area_name") != area.name:
            # Follow a native area rename only while the user has not renamed
            # the group independently. Never infer identity from display names.
            changes = {"data": {**sub.data, "area_name": area.name}}
            if sub.title == sub.data.get("area_name"):
                changes["title"] = area.name
            hass.config_entries.async_update_subentry(entry, sub, **changes)
        result[area_id] = sub.subentry_id

    # Explicitly removing a room in Configure removes only its own group. Core
    # removes the logical entities/devices; physical source integrations stay put.
    for area_id, sub in existing.items():
        if area_id not in selected:
            hass.config_entries.async_remove_subentry(entry, sub.subentry_id)
    if _saved_ids(entry) != result:
        options = deepcopy(dict(entry.options))
        options[ROOM_IDS] = result
        hass.config_entries.async_update_entry(entry, options=options)
    return result


def async_watch_room_hubs(hass: Any, entry: Any) -> Any:
    """React to UI add/remove without an OptionsFlowWithReload update listener."""
    from homeassistant.config_entries import ConfigEntryChange, SIGNAL_CONFIG_ENTRY_CHANGED
    from homeassistant.core import callback
    from homeassistant.helpers.dispatcher import async_dispatcher_connect

    known = set(entry.subentries)

    @callback
    def changed(change: Any, updated: Any) -> None:
        nonlocal known
        if updated.entry_id != entry.entry_id or change != ConfigEntryChange.UPDATED:
            return
        current = set(entry.subentries)
        if current == known:
            return  # Numerical/target edits and group renames never reload HVAC.
        known = current  # Set before nested metadata notifications.
        removed = async_reconcile_removed_rooms(hass, entry)
        manager = entry.runtime_data
        if removed and getattr(manager, "_active", False):
            manager._recalculate(initial=True)
        hass.config_entries.async_schedule_reload(entry.entry_id)

    return async_dispatcher_connect(hass, SIGNAL_CONFIG_ENTRY_CHANGED, changed)


def async_migrate_device_group(hass: Any, registry: Any, entry_id: str,
                               identifiers: set[tuple[str, str]],
                               subentry_id: str | None) -> None:
    """Move registry references in place before registering a different group.

    Explicit moves avoid HA's deprecated silent subentry reassignment. Disabled
    entities are included; unique IDs, entity IDs and user customization stay.
    """
    device = next((item for identifier in identifiers
                   if (item := registry.async_get_device_by_identifier(identifier, entry_id)) is not None), None)
    if device is None or device.config_subentry_id == subentry_id:
        return
    from homeassistant.helpers import entity_registry as er
    entities = er.async_get(hass)
    for entity in er.async_entries_for_device(entities, device.id, include_disabled_entities=True):
        if entity.config_entry_id == entry_id and entity.config_subentry_id != subentry_id:
            entities.async_update_entity(entity.entity_id, config_subentry_id=subentry_id)
    registry.async_update_device(device.id, new_config_subentry_id=subentry_id)


def async_add_grouped_entities(manager: Any, add_entities: Any,
                               entities: Iterable[Any]) -> None:
    """All platforms use the same device->room group; never reparent on reload."""
    mapping = getattr(manager, "_device_hierarchy", {}).get("device_subentries", {})
    groups: dict[str | None, list[Any]] = {}
    for entity in entities:
        info = getattr(entity, "_attr_device_info", None) or {}
        subentries = {mapping[identity] for domain, identity in info.get("identifiers", ())
                      if domain == DOMAIN and identity in mapping}
        if len(subentries) > 1:
            raise ValueError("One entity cannot belong to multiple room hubs")
        subentry_id = next(iter(subentries), None)
        groups.setdefault(subentry_id, []).append(entity)
    for subentry_id, batch in groups.items():
        if subentry_id is None:
            add_entities(batch)
        else:
            add_entities(batch, config_subentry_id=subentry_id)
