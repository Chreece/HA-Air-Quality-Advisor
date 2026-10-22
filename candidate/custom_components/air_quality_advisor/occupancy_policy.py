"""Global, room and device occupancy policy.

Only actual Home Assistant states and configured Area Registry IDs are accepted.
A missing/old/ambiguous source is UNKNOWN, never 'nobody home'. An explicit
empty JSON array from a fresh source does mean no rooms are occupied.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from collections.abc import Mapping
from typing import Any

from .discovery import entity_area


def _fresh(state: Any, max_age_minutes: float = 240) -> bool:
    if state is None or str(getattr(state, "state", "")).lower() in (
        "unknown", "unavailable", "none", ""
    ):
        return False
    stamp = getattr(state, "last_reported", None) or getattr(state, "last_updated", None)
    if not isinstance(stamp, datetime) or stamp.tzinfo is None:
        return False
    age = (datetime.now(timezone.utc) - stamp).total_seconds()
    return 0 <= age <= max_age_minutes * 60


def _area_aliases(hass: Any, identifiers: set[str]) -> dict[str, str]:
    from homeassistant.helpers import area_registry
    registry = area_registry.async_get(hass)
    aliases: dict[str, str] = {}
    available = set(identifiers)
    if hasattr(registry, "async_list_areas"):
        available.update(
            item.id for item in registry.async_list_areas()
            if isinstance(getattr(item, "id", None), str)
        )
    for area in available:
        if not isinstance(area, str) or not area:
            continue
        aliases[area.strip().casefold()] = area
        actual = registry.async_get_area(area)
        name = getattr(actual, "name", None)
        if isinstance(name, str) and name.strip():
            aliases[name.strip().casefold()] = area
    return aliases


def _tokens(raw: Any) -> list[str] | None:
    """Parse explicit room lists; reject ambiguous free-text statuses."""
    if isinstance(raw, Mapping):
        for key in ("occupied_rooms", "sleep_rooms", "areas", "rooms"):
            if key in raw:
                return _tokens(raw[key])
        if all(isinstance(k, str) and type(v) is bool for k, v in raw.items()):
            return [k for k, v in raw.items() if v]
        return None
    if isinstance(raw, (list, tuple, set)):
        return list(raw) if all(isinstance(v, str) for v in raw) else None
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    if value == "[]":
        return []
    if value.startswith("[") or value.startswith("{"):
        try:
            return _tokens(json.loads(value))
        except (TypeError, ValueError):
            return None
    if value.casefold() in ("none", "no_rooms"):
        return []
    if "," in value:
        return [part.strip() for part in value.split(",") if part.strip()]
    return [value] if value else None


def configured_rooms(hass: Any, entity_id: str | None, attribute: str | None,
                     known_areas: set[str], *, max_age_minutes: float = 240,
                     ) -> tuple[set[str] | None, str]:
    """Read state/one explicit attribute. Unknown names invalidate the list."""
    if not isinstance(entity_id, str) or not entity_id:
        return None, "not_configured"
    state = hass.states.get(entity_id)
    if not _fresh(state, max_age_minutes):
        return None, "missing_or_stale_rooms_source"
    if isinstance(attribute, str) and attribute.strip():
        raw = state.attributes.get(attribute.strip())
    else:
        raw = state.state
    parsed = _tokens(raw)
    if parsed is None:
        return None, "invalid_rooms_format"
    aliases = _area_aliases(hass, known_areas)
    resolved: set[str] = set()
    for name in parsed:
        area = aliases.get(name.strip().casefold())
        if area is None:
            return None, "unrecognized_room_in_occupancy_source"
        resolved.add(area)
    return resolved, "verified_rooms_list"


def _bool_presence(state: Any, minutes: float = 240) -> bool | None:
    if not _fresh(state, minutes):
        return None
    if state.domain == "binary_sensor":
        if state.state == "on":
            return True
        if state.state == "off":
            return False
    if state.domain in ("person", "device_tracker"):
        if state.state == "home":
            return True
        if state.state not in ("unknown", "unavailable", "none", ""):
            return False
    return None


def home_presence(hass: Any, global_settings: Mapping,
                  fallback_trackers: list[str] | None = None) -> tuple[str, str, list[str]]:
    """Require fresh, explicit away evidence; unknown trackers never mean away."""
    source = global_settings.get("home_trackers") or fallback_trackers or []
    if not isinstance(source, list):
        source = []
    allowed = [e for e in source if isinstance(e, str) and
               e.startswith(("person.", "device_tracker.", "binary_sensor."))]
    if not allowed:
        return "home", "no_trackers_assume_home", []
    values = [_bool_presence(hass.states.get(e)) for e in allowed]
    if any(v is None for v in values):
        return "unknown", "unverified_home_trackers", allowed
    if global_settings.get("home_policy", "any_home") == "all_home":
        return ("home" if all(values) else "away"), "all_home_policy", allowed
    return ("home" if any(values) else "away"), "any_home_policy", allowed


def room_presence(hass: Any, area: str, settings: Mapping,
                  global_settings: Mapping, *, known_areas: set[str],
                  ) -> tuple[str, str, list[str]]:
    """Combine configured room sensor evidence and selected room-list entity.

    Any affirmative evidence wins; negative evidence is valid only when every
    configured source gives a fresh, explicit negative reading.
    """
    local = settings.get("occupancy_sensors")
    chosen = global_settings.get("room_occupancy_sensors", [])
    if isinstance(local, list) and local:
        sensors = local
    elif isinstance(chosen, list) and chosen:
        sensors = chosen
    else:
        sensors = [state.entity_id for state in hass.states.async_all("binary_sensor")
                   if entity_area(hass, state.entity_id) == area and
                   str(state.attributes.get("device_class", "")).casefold()
                   in ("occupancy", "presence")]
    area_sensors = [e for e in sensors if isinstance(e, str) and
                    e.startswith("binary_sensor.") and entity_area(hass, e) == area]
    evidence: list[bool | None] = [
        _bool_presence(hass.states.get(e),
                       settings.get("occupancy_stale_minutes", 240))
        for e in area_sensors
    ]
    entity = global_settings.get("occupied_rooms_entity")
    if entity:
        occupied, reason = configured_rooms(
            hass, entity, global_settings.get("occupied_rooms_attribute"),
            known_areas, max_age_minutes=global_settings.get("source_stale_minutes", 240))
        evidence.append(None if occupied is None else area in occupied)
    if any(value is True for value in evidence):
        return "occupied", "verified_room_occupied", area_sensors
    if evidence and all(value is False for value in evidence):
        return "unoccupied", "all_configured_room_sources_empty", area_sensors
    if evidence:
        return "unknown", "room_occupancy_source_unknown", area_sensors
    return "occupied", "no_room_presence_source_conservative", area_sensors


def sleep_presence(hass: Any, area: str, global_settings: Mapping,
                   known_areas: set[str]) -> tuple[bool | None, str]:
    if not global_settings.get("sleep_rooms_entity"):
        return None, "sleep_rooms_not_configured"
    rooms, reason = configured_rooms(
        hass, global_settings.get("sleep_rooms_entity"),
        global_settings.get("sleep_rooms_attribute"),
        known_areas, max_age_minutes=global_settings.get("source_stale_minutes", 240))
    return (area in rooms if rooms is not None else None), reason


def device_permission(device: Mapping, room_status: str, home_status: str,
                      sleeping: bool | None) -> tuple[str, str]:
    """Prioritize explicit sleep pause over occupancy-triggered power OFF.

    Device controllers must still pass the independent electrical,
    compressor and minimum-run protections. An unknown input is NEVER empty.
    """
    if device.get("auto_control") is not True:
        return "held", "device_auto_control_disabled"
    sleep = device.get("sleep_behavior", "normal")
    if sleep == "pause":
        if sleeping is True:
            return "held", "sleep_room_control_paused"
        if sleeping is None:
            return "held", "sleep_room_evidence_unknown"
    elif sleep == "sleep_targets":
        if sleeping is None:
            return "held", "sleep_room_evidence_unknown"
    elif sleep != "normal":
        return "held", "invalid_sleep_policy"
    source = device.get("presence_requirement", "always")
    if source == "room":
        if room_status == "unoccupied":
            return "absent", "room_unoccupied"
        if room_status != "occupied":
            return "held", "room_occupancy_unknown"
    elif source == "home":
        if home_status == "away":
            return "absent", "house_unoccupied"
        if home_status != "home":
            return "held", "house_occupancy_unknown"
    elif source != "always":
        return "held", "invalid_presence_policy"
    return "eligible", "device_policy_approved"



def live_device_permission(hass: Any, area: str, room_config: Mapping,
                           plan: Mapping, device: Mapping) -> tuple[str, str]:
    """Re-check sensor/occupancy evidence at the actual write boundary.

    A plan evaluated before a person enters, leaves or starts sleeping must
    not authorize a stale command. No new entity is discovered or controlled.
    """
    global_settings = plan.get("global_presence")
    area_ids = plan.get("known_presence_areas")
    if isinstance(global_settings, Mapping) and global_settings:
        known = (set(area_ids) if isinstance(area_ids, (tuple,list,set))
                 else {area})
        room,_,_=room_presence(hass,area,room_config,global_settings,
                               known_areas=known or {area})
        home,_,_=home_presence(hass,global_settings,
                               plan.get("tracker_entities",[]))
        sleeping=plan.get("sleeping")
        if global_settings.get("sleep_rooms_entity"):
            value,_=sleep_presence(hass,area,global_settings,known or {area})
            if value is None:
                sleeping=None
            elif value is True:
                sleeping=True
            elif sleeping is None:
                sleeping=False
        return device_permission(device,room,home,sleeping)
    room = plan.get("occupancy","unknown")
    sensors=plan.get("presence_entities")
    if isinstance(sensors,list) and sensors:
        readings=[_bool_presence(hass.states.get(entity)) for entity in sensors]
        if any(value is True for value in readings):
            room="occupied"
        elif any(value is None for value in readings):
            room="unknown"
        else:
            room="unoccupied"
    home=plan.get("away","unknown")
    trackers=plan.get("tracker_entities")
    if isinstance(trackers,list) and trackers:
        home,_,_=home_presence(hass,{"home_trackers":trackers})
    return device_permission(device,room,home,plan.get("sleeping"))
