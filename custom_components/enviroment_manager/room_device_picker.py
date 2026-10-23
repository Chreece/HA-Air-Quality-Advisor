"""Group a room's supported native endpoints by physical device for selection.

The saved controller inventory remains a list of exact native entity IDs.
Selecting a product creates one Manager device, not one device per endpoint.
This module never changes a registry entry or grants actuation permissions.
"""
from __future__ import annotations

from typing import Any

from .const import DOMAIN
from .discovery import entity_area

NATIVE_DOMAINS = frozenset(("climate", "humidifier", "fan"))


def physical_device_choices(hass: Any, area: str, retained=()) -> tuple[list[dict], dict[str, tuple[str, ...]]]:
    """Return one option per native physical device in this specific room.

    Existing selected endpoints remain selectable while unavailable. Never
    include another room's endpoints or recursively include Manager entities.
    Registry-less sources remain individually selectable by exact entity ID.
    """
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    from .compact_options import _device_choices

    entities, devices = er.async_get(hass), dr.async_get(hass)
    candidates = {choice["value"] for choice in _device_choices(hass, area)}
    for entity_id in retained:
        if (not isinstance(entity_id, str)
                or entity_id.partition(".")[0] not in NATIVE_DOMAINS):
            continue
        entity = entities.async_get(entity_id)
        if (entity is not None and getattr(entity, "platform", None) != DOMAIN
                and entity_area(hass, entity_id) == area):
            candidates.add(entity_id)
    grouped: dict[str, dict] = {}
    for entity_id in sorted(candidates):
        entity = entities.async_get(entity_id)
        if entity is not None and getattr(entity, "platform", None) == DOMAIN:
            continue
        source_id = getattr(entity, "device_id", None)
        device = devices.async_get(source_id) if source_id else None
        state = hass.states.get(entity_id)
        if device is None:
            key = entity_id
            name = getattr(state, "name", None) or getattr(entity, "original_name", None) or entity_id
        else:
            key = "device:" + source_id
            name = getattr(device, "name_by_user", None) or getattr(device, "name", None) or source_id
        group = grouped.setdefault(key, {"name": name, "entities": []})
        group["entities"].append(entity_id)
    choices = [{"value": key,
                "label": value["name"] + " · " + ", ".join(value["entities"])}
               for key, value in grouped.items()]
    choices.sort(key=lambda item: (item["label"].casefold(), item["value"]))
    return choices, {key: tuple(value["entities"]) for key, value in grouped.items()}
