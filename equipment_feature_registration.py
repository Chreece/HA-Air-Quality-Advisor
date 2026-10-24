"""Register real native capability-dependent configuration controls.

Only a registered source belonging to a managed physical controller can
authorize adding controls. A delayed native fan capability must not leave
orphaned HA entity-registry entries or require another restart. Nothing here
calls a physical HA service or infers a capability from a device's name.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from . import equipment_model as equipment
from .room_hubs import async_add_grouped_entities


def registered_control(registry: Any, platform: str, spec: Any, key: str) -> bool:
    """Preserve unique IDs of previously supported native controller controls."""
    getter = getattr(registry, "async_get_entity_id", None)
    return bool(getter and getter(platform, DOMAIN, f"{spec.identifier}_{key}"))


def quiet_keys(manager: Any, registry: Any, spec: Any,
               *, platform: str) -> tuple[str, ...]:
    """Capability-gated controls; never interpret a physical OFF as no fan.

    When HA has not loaded native modes yet, recreate only the existing
    registry controls so they recover under their previous unique IDs.
    An unregistered/unsupported feature is never invented or enabled.
    """
    cap = equipment.capabilities(manager, spec)
    if platform == "switch":
        choices = equipment.QUIET_FLAGS
        offered = bool(cap and cap.fan_modes)
    elif platform == "select":
        choices = ("quiet_fan_mode",)
        offered = bool(cap and cap.fan_modes and not cap.fan_percentage)
    else:
        raise ValueError("Only native quiet configuration platforms are supported")

    if offered:
        return choices
    return tuple(
        key for key in choices
        if registered_control(registry, platform, spec, key)
    )


def register_late_capabilities(
    hass: Any,
    entry: Any,
    async_add_entities: Callable[..., Any],
    original: Iterable[Any],
    candidates: Callable[[], Iterable[Any]],
) -> None:
    """Register newly discovered features only for exact physical source events.

    Track added unique IDs before forwarding platform additions to prevent
    duplicate registration. Room hub identity and user-customized entity IDs
    remain untouched. A manager-generated logical entity never triggers this.
    """
    manager = entry.runtime_data
    registered_ids = {
        entity._attr_unique_id for entity in original
    }
    watched = frozenset(
        source for spec in equipment.specs(manager)
        for source in spec.source_entities
    )
    if not watched:
        return

    @callback
    def native_changed(event: Any) -> None:
        if event.data.get("entity_id") not in watched:
            return
        missing = {}
        for candidate in candidates():
            unique_id = candidate._attr_unique_id
            if unique_id not in registered_ids:
                missing[unique_id] = candidate
        if not missing:
            return
        registered_ids.update(missing)
        async_add_grouped_entities(
            entry.runtime_data, async_add_entities, missing.values()
        )

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_STATE_CHANGED, native_changed)
    )
