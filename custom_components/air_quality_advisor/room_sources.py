"""Explicit room input inventories, shared by setup and runtime monitoring.

No registry or hardware writes. Absent configuration retains legacy discovery;
an explicit empty list means no input, never 'discover all again'.
"""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any

from .const import DOMAIN

CONF_ROOM_SOURCES = "room_sources"
GROUPS = ("windows", "air_quality", "temperature", "humidity", "pressure", "climate_devices")
PRESSURE_UNITS = {"pa": .01, "hpa": 1., "kpa": 10., "mbar": 1., "bar": 1000.,
                  "inhg": 33.8638866667, "mmhg": 1.33322387415, "psi": 68.9475729317}


def selected(settings: dict, area: str, group: str) -> tuple[str, ...] | None:
    rooms = settings.get(CONF_ROOM_SOURCES, {})
    if not isinstance(rooms, dict) or area not in rooms:
        return None
    room = rooms[area]
    values = room.get(group, []) if isinstance(room, dict) else []
    return tuple(dict.fromkeys(e for e in values if isinstance(e, str))) if isinstance(values, list) else ()


def native(hass: Any, entity: str) -> bool:
    from homeassistant.helpers import entity_registry as er
    entry = er.async_get(hass).async_get(entity)
    return entry is None or getattr(entry, "platform", None) != DOMAIN


def label(hass: Any, entity: str) -> str:
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    entry = er.async_get(hass).async_get(entity)
    device = dr.async_get(hass).async_get(entry.device_id) if entry and entry.device_id else None
    state = hass.states.get(entity)
    device_name = ((getattr(device, "name_by_user", None) or getattr(device, "name", None))
                   if device else None) or "—"
    entity_name = (getattr(entry, "name", None) if entry else None) or (
        getattr(state, "name", None) or (getattr(entry, "original_name", None) if entry else None) or entity)
    return f"{device_name} — {entity_name} · {entity}"


def category(hass: Any, state: Any) -> str | None:
    from .discovery import _device_class, is_window, supported_metric
    if not native(hass, state.entity_id):
        return None
    if is_window(hass, state):
        return "windows"
    if state.domain in ("climate", "fan", "humidifier"):
        if state.domain != "climate" or isinstance(state.attributes.get("hvac_modes"), (list, tuple)):
            return "climate_devices"
        return None
    if state.domain != "sensor":
        return None
    klass = _device_class(hass, state)
    unit = str(state.attributes.get("unit_of_measurement", "")).strip()
    if klass == "temperature" or state.entity_id.endswith(("_temperature", "_temp")):
        return "temperature" if unit in ("°C", "C", "°F", "F", "K") else None
    if klass in ("atmospheric_pressure", "pressure"):
        return "pressure" if unit.casefold() in PRESSURE_UNITS else None
    units = unit.replace("μ", "µ").replace("³", "3").replace(" ", "").casefold()
    if klass in ("sound_pressure", "noise") and units in ("db(a)", "dba"):
        return "air_quality"
    if klass == "illuminance" and units in ("lx", "lux"):
        return "air_quality"
    if state.entity_id.endswith("_air_speed") and units in ("m/s", "mps"):
        return "air_quality"
    metric = supported_metric(hass, state, outdoor=False)
    if metric:
        return "humidity" if metric == "humidity" else "air_quality"
    # Existing environmental adapters, with exact units (no new safety claims).
    units = unit.replace("μ", "µ").replace("³", "3").replace(" ", "").casefold()
    if klass in ("radon",) and units in ("bq/m3", "bq/m^3", "pci/l"):
        return "air_quality"
    if (klass in ("formaldehyde",) or state.entity_id.endswith(("_hcho", "_formaldehyde"))) and units in ("µg/m3", "ug/m3", "mg/m3"):
        return "air_quality"
    return None


def choices(hass: Any, area: str, previous: dict | None = None) -> dict[str, list[dict]]:
    from homeassistant.helpers import entity_registry as er
    from .discovery import entity_area
    previous = previous if isinstance(previous, dict) else {}
    result = {group: {} for group in GROUPS}
    for state in hass.states.async_all():
        if entity_area(hass, state.entity_id) == area and (group := category(hass, state)):
            result[group][state.entity_id] = label(hass, state.entity_id)
    for group in GROUPS:
        values = previous.get(group, [])
        for entity in values if isinstance(values, list) else ():
            if not isinstance(entity, str) or entity_area(hass, entity) != area or not native(hass, entity):
                continue
            state = hass.states.get(entity)
            # Keep registered unavailable inputs, never a retyped or moved input.
            if (state is None or state.state in ("unknown", "unavailable")
                    or group == "climate_devices" and entity.partition(".")[0] in ("switch", "input_boolean", "number", "input_number")) and er.async_get(hass).async_get(entity):
                result[group].setdefault(entity, label(hass, entity))
    return {group: sorted(({"value": e, "label": name} for e, name in values.items()),
                          key=lambda item: (item["label"].casefold(), item["value"]))
            for group, values in result.items()}


def defaults(hass: Any, settings: dict, area: str) -> dict[str, list[str]]:
    """Import existing inclusions/exclusions; do not restore removed grants."""
    existing = settings.get(CONF_ROOM_SOURCES, {}).get(area)
    if isinstance(existing, dict):
        return {k: list(selected(settings, area, k) or ()) for k in GROUPS}
    from .device_hierarchy import configured_sources
    available = choices(hass, area)
    excluded = set(settings.get("excluded_window_entities", [])) | set(
        settings.get("excluded_indoor_entities", {}).get(area, []))
    result = {k: [v["value"] for v in values if v["value"] not in excluded]
              for k, values in available.items()}
    room = settings.get("climate_rooms", {}).get(area, {})
    if "selected_devices" in room or configured_sources(settings, area):
        result["climate_devices"] = list(configured_sources(settings, area))
    return result


def store_selection(hass: Any, settings: dict, area: str, inputs: dict) -> None:
    """Change a flow-local draft only. Actual persistence happens on Finish."""
    from .compact_options import _reconcile_device_selection
    from .device_hierarchy import configured_sources
    prior_sources = set(configured_sources(settings, area))
    rooms = settings.setdefault("climate_rooms", {})
    previous = deepcopy(rooms.get(area, {}))
    room = deepcopy(previous)
    devices = inputs["climate_devices"]
    profiles = room.setdefault("device_settings", {})
    for entity in devices:
        if entity not in prior_sources:
            profiles[entity] = {**profiles.get(entity, {}), "auto_control": False}
    room["selected_devices"] = list(devices)
    room = _reconcile_device_selection(previous, room)
    pid = settings.get("pid_rooms", {}).get(area)
    if isinstance(pid, dict):
        pid["climate_entities"] = [e for e in pid.get("climate_entities", []) if e in devices]
        if not pid["climate_entities"]:
            pid["enabled"] = False
    # Explicitly remove stale source references. Never substitute a new sensor
    # into a previously armed feedback loop without withdrawing its grant.
    from .discovery import supported_metric
    def metric_ids(metric):
        return [e for e in inputs["air_quality"] if (s := hass.states.get(e)) is not None
                and supported_metric(hass, s, outdoor=False) == metric]
    allowed = {"temperature_entity": inputs["temperature"], "humidity_entity": inputs["humidity"],
               "co2_entity": metric_ids("co2"), "pm25_entity": metric_ids("pm25")}
    for target in [room, *room.get("device_settings", {}).values(), *([pid] if isinstance(pid, dict) else [])]:
        if not isinstance(target, dict):
            continue
        for key, sources in allowed.items():
            if target.get(key) and target[key] not in sources:
                target[key] = None
                if target is room:
                    target["allow_actuation"] = False
                elif target is pid:
                    target["enabled"] = False
                else:
                    target["auto_control"] = False
            elif not target.get(key) and len(sources) == 1:
                target[key] = sources[0]
    rooms[area] = room
    env = settings.setdefault("environment_rooms", {}).setdefault(area, {})
    if env.get("temperature_entity") not in inputs["temperature"]:
        env["temperature_entity"] = inputs["temperature"][0] if len(inputs["temperature"]) == 1 else None
    for key in ("radon_entity", "formaldehyde_entity", "noise_entity", "illuminance_entity", "melanopic_edi_entity", "air_speed_entity"):
        if env.get(key) and env[key] not in inputs["air_quality"]:
            env[key] = None
    optional = {}
    for entity in inputs["air_quality"]:
        state = hass.states.get(entity)
        klass = state.attributes.get("device_class") if state else None
        key = ({"radon": "radon_entity", "formaldehyde": "formaldehyde_entity",
                "sound_pressure": "noise_entity", "noise": "noise_entity",
                "illuminance": "illuminance_entity"}.get(klass))
        if entity.endswith("_air_speed"):
            key = "air_speed_entity"
        if key:
            optional.setdefault(key, []).append(entity)
    for key, candidates in optional.items():
        if not env.get(key):
            env[key] = candidates[0] if len(candidates) == 1 else None
    if env.get("radiant_temperature_entity") not in inputs["temperature"]:
        env["radiant_temperature_entity"] = None
    mold = settings.setdefault("mold_rooms", {}).setdefault(area, {})
    if isinstance(mold, dict) and mold.get("indoor_temperature_entity") not in inputs["temperature"]:
        mold["indoor_temperature_entity"] = inputs["temperature"][0] if len(inputs["temperature"]) == 1 else None
        mold.pop("calibration_factor", None)
        mold.pop("calibrated_at", None)
    settings.setdefault(CONF_ROOM_SOURCES, {})[area] = deepcopy(inputs)
    included = {e for key in GROUPS for e in inputs[key]}
    settings["excluded_window_entities"] = [e for e in settings.get("excluded_window_entities", []) if e not in included]
    exclusions = settings.setdefault("excluded_indoor_entities", {})
    exclusions[area] = [e for e in exclusions.get(area, []) if e not in included]


def restrict_rooms(settings: dict, areas: list[str]) -> None:
    settings["areas"] = list(areas)
    for key in ("climate_rooms", "pid_rooms"):
        for area, cfg in settings.get(key, {}).items():
            if area in areas or not isinstance(cfg, dict):
                continue
            cfg["enabled"] = False
            if key == "climate_rooms":
                cfg["allow_actuation"] = False
                cfg["selected_devices"] = []
                for dev in cfg.get("device_settings", {}).values():
                    if isinstance(dev, dict):
                        dev["auto_control"] = False
            else:
                cfg["climate_entities"] = []


def numeric(hass: Any, entity: str, area: str, group: str, age: float) -> float | None:
    from .discovery import entity_area, is_stale, reading, temperature_sensor_c
    state = hass.states.get(entity)
    if (state is None or entity_area(hass, entity) != area or not native(hass, entity)
            or is_stale(state, age)):
        return None
    if group == "temperature":
        value = temperature_sensor_c(hass, entity, age)
        return value if value is not None and -60 <= value <= 85 else None
    if group == "pressure":
        if category(hass, state) != "pressure":
            return None
        try:
            value = float(state.state) * PRESSURE_UNITS[str(state.attributes["unit_of_measurement"]).strip().casefold()]
        except (ValueError, TypeError, KeyError, OverflowError):
            return None
        return value if math.isfinite(value) and 300 <= value <= 1100 else None
    value = reading(hass, entity, age, outdoor=False)
    return value.value


def aggregate(hass: Any, entities, area: str, group: str, age: float) -> tuple[float | None, str]:
    if not entities:
        return None, "not_selected"
    values = [numeric(hass, e, area, group, age) for e in entities]
    if any(v is None for v in values):
        return None, "selected_source_unavailable"
    return sum(values) / len(values), "selected_mean" if len(values) > 1 else "selected_sensor"


def source_overview(manager: Any, area: str) -> dict:
    if selected(manager.settings, area, "windows") is None:
        return {}
    from .discovery import entity_area
    result = {}
    for group in GROUPS:
        values = selected(manager.settings, area, group)
        if values is None:
            continue
        rows = []
        for entity in values:
            state = manager.hass.states.get(entity)
            valid = entity_area(manager.hass, entity) == area and native(manager.hass, entity)
            rows.append({"entity_id": entity, "label": label(manager.hass, entity),
                         "state": state.state if state and valid else None,
                         "unit": state.attributes.get("unit_of_measurement") if state and valid else None,
                         "assigned_to_room": valid})
        result[group] = rows
    pressures = selected(manager.settings, area, "pressure")
    if pressures is not None:
        value, status = aggregate(manager.hass, pressures, area, "pressure", getattr(manager, "thresholds", {}).get("max_age_minutes", 90))
        result["pressure_summary"] = {"value_hpa": value, "status": status}
    return result
