"""Global, room and device occupancy policy.

Only actual Home Assistant states and configured Area Registry IDs are accepted.
A missing/old/ambiguous source is UNKNOWN, never 'nobody home'. An explicit
empty JSON array from a fresh source does mean no rooms are occupied.
"""
from __future__ import annotations

import ast
import json
import re
import unicodedata
from datetime import datetime, timezone
from collections.abc import Mapping
from typing import Any

from .discovery import entity_area


def _fresh(state: Any, max_age_minutes: float = 240, *, allow_empty: bool = False) -> bool:
    if state is None:
        return False
    value = str(getattr(state, "state", "")).strip().casefold()
    if value in ("unknown", "unavailable") or not allow_empty and value in ("none", ""):
        return False
    stamp = getattr(state, "last_reported", None) or getattr(state, "last_updated", None)
    if not isinstance(stamp, datetime) or stamp.tzinfo is None:
        return False
    age = (datetime.now(timezone.utc) - stamp).total_seconds()
    return 0 <= age <= max_age_minutes * 60


def _room_key(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()


def _area_aliases(hass: Any, identifiers: set[str]) -> dict[str, str]:
    from homeassistant.helpers import area_registry
    registry = area_registry.async_get(hass)
    available = set(identifiers)
    if hasattr(registry, "async_list_areas"):
        available.update(item.id for item in registry.async_list_areas())
    elif hasattr(registry, "areas"):
        available.update(registry.areas)
    candidates: dict[str, set[str]] = {}
    for area in available:
        if not isinstance(area, str) or not area:
            continue
        actual = registry.async_get_area(area)
        names = (area, getattr(actual, "name", None), *(getattr(actual, "aliases", ()) or ()))
        for name in names:
            if isinstance(name, str) and name.strip():
                candidates.setdefault(_room_key(name), set()).add(area)
    # Ambiguous names cannot identify a safe room. Exact IDs still work.
    return {key: next(iter(values)) for key, values in candidates.items() if len(values) == 1}


def _tokens(raw: Any, _depth: int = 0) -> list[str] | None:
    """Read explicit template lists/CSV, without executing template content."""
    if _depth > 5:
        return None
    if isinstance(raw, Mapping):
        for key in ("occupied_rooms", "sleep_rooms", "sleeping_areas", "areas", "rooms"):
            if key in raw:
                return _tokens(raw[key], _depth + 1)
        if all(isinstance(k, str) and (type(v) is bool or type(v) is int and v >= 0)
               for k, v in raw.items()):
            return [k for k, v in raw.items() if v]
        return None
    if isinstance(raw, (list, tuple, set, frozenset)):
        return list(raw) if all(isinstance(v, str) and v.strip() for v in raw) else None
    if not isinstance(raw, str) or len(raw) > 8192:
        return None
    value = raw.strip()
    if value.casefold() in ("", "none", "no_rooms"):
        return []
    if value.startswith(("[", "{", "(")):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            # Jinja/Python-rendered lists commonly use single quotes. Limit
            # AST size first; literal_eval does not execute calls or names.
            try:
                tree = ast.parse(value, mode="eval")
                if sum(1 for _ in ast.walk(tree)) > 512:
                    return None
                decoded = ast.literal_eval(tree)
            except (ValueError, SyntaxError, TypeError, RecursionError):
                return None
        return _tokens(decoded, _depth + 1)
    if any(separator in value for separator in (",", ";", "\n")):
        return [part.strip() for part in re.split(r"[,;\n]", value) if part.strip()]
    return [value]


def configured_rooms(hass: Any, entity_id: str | None, attribute: str | None,
                     known_areas: set[str], *, max_age_minutes: float = 240,
                     ) -> tuple[set[str] | None, str]:
    """Read state/one explicit attribute. Unknown names invalidate the list."""
    if not isinstance(entity_id, str) or not entity_id:
        return None, "not_configured"
    state = hass.states.get(entity_id)
    if not _fresh(state, max_age_minutes, allow_empty=True):
        return None, "missing_or_stale_rooms_source"
    if isinstance(attribute, str) and attribute.strip() not in ("", "__state__"):
        raw = state.attributes.get(attribute.strip())
    else:
        raw = state.state
    parsed = _tokens(raw)
    if parsed is None:
        return None, "invalid_rooms_format"
    aliases = _area_aliases(hass, known_areas)
    resolved: set[str] = set()
    for name in parsed:
        area = aliases.get(_room_key(name))
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


def _after_away_cooldown(states: list[Any], minutes: Any, reason: str
                         ) -> tuple[str, str]:
    try:
        cooldown = max(0.0, min(240.0, float(minutes)))
    except (TypeError, ValueError, OverflowError):
        cooldown = 10.0
    if cooldown <= 0:
        return "away", reason
    stamps = [getattr(state, "last_changed", None) for state in states if state is not None]
    stamps = [stamp for stamp in stamps if isinstance(stamp, datetime) and stamp.tzinfo is not None]
    if not stamps:
        return "unknown", "away_cooldown_start_unknown"
    elapsed = (datetime.now(timezone.utc) - max(stamps)).total_seconds()
    if elapsed < 0:
        return "unknown", "away_cooldown_clock_invalid"
    if elapsed < cooldown * 60:
        return "home", "no_occupied_rooms_cooldown"
    return "away", reason


def home_presence(hass: Any, global_settings: Mapping,
                  fallback_trackers: list[str] | None = None) -> tuple[str, str, list[str]]:
    """Any fresh positive tracker or presence sensor is sufficient for HOME.

    Evaluate *all* explicitly configured presence signals before any negative
    priority/cooldown logic. A fresh device_tracker/person 'home' or binary
    sensor 'on' can never be vetoed by another 'not_home'/'off', a missing
    sensor, or an empty/stale occupied-rooms list. Only a real fresh positive
    qualifies; unavailable or stale values are not affirmative evidence.

    Once no positive evidence exists, retain conservative existing behavior
    for room lists, all-negative room sensors and away cooldowns.
    """
    cooldown = global_settings.get("away_cooldown_minutes", 10)
    room_entity = global_settings.get("occupied_rooms_entity")
    room_sources = global_settings.get("room_occupancy_sensors", [])
    allowed_rooms = list(dict.fromkeys(
        entity for entity in (room_sources if isinstance(room_sources, list) else [])
        if isinstance(entity, str) and entity.startswith("binary_sensor.")
    ))
    global_trackers = global_settings.get("home_trackers", [])
    # Legacy area trackers are explicit sources too: a positive should not
    # disappear merely because the General settings list is also configured.
    combined = [
        *(global_trackers if isinstance(global_trackers, list) else []),
        *(fallback_trackers if isinstance(fallback_trackers, list) else []),
    ]
    allowed = list(dict.fromkeys(
        entity for entity in combined
        if isinstance(entity, str)
        and entity.startswith(("person.", "device_tracker.", "binary_sensor."))
    ))
    all_sources = list(dict.fromkeys([
        *([room_entity] if isinstance(room_entity, str) and room_entity else []),
        *allowed_rooms, *allowed,
    ]))
    room_values = [_bool_presence(hass.states.get(e)) for e in allowed_rooms]
    tracker_values = [_bool_presence(hass.states.get(e)) for e in allowed]

    # Positive evidence has unconditional priority over contradictory/unknown
    # negative sources and old all_home configuration (which no longer vetoes
    # a known person at home). This affects only house presence; independent
    # physical compressor and per-room safety gates still apply.
    if any(value is True for value in tracker_values):
        return "home", "any_home_policy", all_sources
    if any(value is True for value in room_values):
        return "home", "room_sensor_occupied", all_sources

    if isinstance(room_entity, str) and room_entity:
        rooms, why = configured_rooms(
            hass, room_entity, global_settings.get("occupied_rooms_attribute"),
            set(), max_age_minutes=global_settings.get("source_stale_minutes", 240))
        if rooms is None:
            return "unknown", why, all_sources
        if rooms:
            return "home", "occupied_rooms_present", all_sources
        state = hass.states.get(room_entity)
        # A list stored in an attribute may change while the state string stays
        # constant, so use last_updated as the transition evidence in that case.
        attr = global_settings.get("occupied_rooms_attribute")
        if state is not None and isinstance(attr, str) and attr not in ("", "__state__"):
            proxy = type("_Stamp", (), {"last_changed": getattr(state, "last_updated", None)})()
            status, reason = _after_away_cooldown([proxy], cooldown, "occupied_rooms_empty")
        else:
            status, reason = _after_away_cooldown([state], cooldown, "occupied_rooms_empty")
        return status, reason, all_sources

    if room_values:
        if all(value is False for value in room_values):
            status, reason = _after_away_cooldown(
                [hass.states.get(e) for e in allowed_rooms], cooldown,
                "all_room_sensors_unoccupied")
            return status, reason, all_sources
        return "unknown", "room_presence_evidence_unknown", all_sources

    if not allowed:
        return "home", "no_trackers_assume_home", []
    if any(value is None for value in tracker_values):
        return "unknown", "unverified_home_trackers", all_sources
    return "away", "any_home_policy", all_sources


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
    # Legacy room/home semantics are retained for the old room drivers only.
    # The new per-controller UI never offers these values.
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
    elif source == "occupied":
        if room_status == "unoccupied":
            return "held", "room_not_occupied"
        if room_status != "occupied":
            return "held", "room_occupancy_unknown"
    elif source == "absent":
        if room_status == "occupied":
            return "held", "room_not_absent"
        if room_status != "unoccupied":
            return "held", "room_occupancy_unknown"
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
