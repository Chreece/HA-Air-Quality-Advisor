"""Locate supported HA sensors and windows without integration-specific assumptions."""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
import re
from typing import Any

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from .const import INDOOR_METRICS, SUPPORTED_AIR_METRICS
from .logic import Reading, Room, Warning, Weather, Window


DEVICE_CLASS_METRICS = {
    "aqi": "aqi",
    "co2": "co2",
    "pm25": "pm25",
    "pm10": "pm10",
    "nitrogen_dioxide": "no2",
    "ozone": "o3",
    "sulphur_dioxide": "so2",
    "sulfur_dioxide": "so2",
    "volatile_organic_compounds": "voc",
    "volatile_organic_compounds_parts": "voc_parts",
    "humidity": "humidity",
}
# Exact trailing names are useful for template sensors that omit device_class.
SUFFIX_METRICS = {
    "aqi": "aqi", "air_quality_index": "aqi", "co2": "co2",
    "pm25": "pm25", "pm2_5": "pm25", "pm10": "pm10",
    "tvoc": "voc", "voc": "voc", "humidity": "humidity",
    "no2": "no2", "o3": "o3", "so2": "so2",
    "nitrogen_dioxide": "no2", "ozone": "o3",
    "sulphur_dioxide": "so2", "sulfur_dioxide": "so2",
}
WARNING_HINTS = re.compile(
    r"warning|warnung|warnstufe|alert|meteoalarm|weatheralarm|"
    r"weather_warning|dwd|nina_|storm|gewitter|severe_weather|"
    r"avis_meteo|aviso_meteorol|προειδοποι|κακοκαιρ", re.IGNORECASE
)
INACTIVE_ALERT_STATES = {
    "off", "no", "none", "clear", "green", "safe", "normal", "inactive",
    "no warning", "no warnings", "no alert", "no alerts", "0", "", "ok",
    "keine", "keine warnung", "keine warnungen", "keine alarmierung",
    "χωρίς προειδοποίηση", "καμία", "όχι", "aucune", "sin alertas",
}


def entity_area(hass: HomeAssistant, entity_id: str) -> str | None:
    """Respect entity-area override ahead of device area; never infer by name."""
    registration = er.async_get(hass).async_get(entity_id)
    if registration is None:
        return None
    if registration.area_id:
        return registration.area_id
    if registration.device_id:
        device = dr.async_get(hass).async_get(registration.device_id)
        if device:
            return device.area_id
    return None


def _device_class(hass: HomeAssistant, state: State) -> str:
    entry = er.async_get(hass).async_get(state.entity_id)
    return str(state.attributes.get("device_class") or (
        (getattr(entry, "device_class", None) or getattr(entry, "original_device_class", None))
        if entry else ""
    ) or "").casefold()


def _metric(hass: HomeAssistant, state: State) -> str | None:
    if not state.entity_id.startswith("sensor."):
        return None
    metric = DEVICE_CLASS_METRICS.get(_device_class(hass, state))
    if metric:
        return metric
    slug = state.entity_id.split(".", 1)[-1]
    return next(
        (result for suffix, result in SUFFIX_METRICS.items() if slug == suffix or slug.endswith("_" + suffix)),
        None,
    )


def _numeric(value: Any) -> float | None:
    try:
        number = float(value)
        if -1e15 < number < 1e15 and number == number:
            return number
    except (ValueError, TypeError, OverflowError):
        pass
    return None


def _normalize(metric: str, value: float, unit: str | None) -> float | None:
    u = str(unit or "").strip().lower().replace("μ", "µ").replace("³", "3").replace(" ", "")
    if metric == "aqi":
        return value if u in ("", "aqi", "index") else None
    if metric == "humidity":
        return value if u in ("", "%") else None
    if metric == "co2":
        return value if u in ("ppm",) else None
    if metric in ("pm25", "pm10", "voc", "no2", "o3", "so2"):
        if u in ("µg/m3", "ug/m3"):
            return value
        return value * 1000 if u in ("mg/m3",) else None
    if metric == "voc_parts":
        if u == "ppb":
            return value
        return value * 1000 if u == "ppm" else None
    return None


def supported_metric(hass: HomeAssistant, state: State, *, outdoor: bool) -> str | None:
    """Expose only supported numeric units, and never list indoor humidity outside."""
    metric = _metric(hass, state)
    if metric not in (SUPPORTED_AIR_METRICS if outdoor else INDOOR_METRICS):
        return None
    unit = state.attributes.get("unit_of_measurement")
    # Unknown/unavailable states can remain in the picker when their device
    # class and units are supported. Evaluation treats missing values as neutral
    # and exposes them separately as incomplete data.
    return metric if _normalize(metric, 1.0, unit) is not None else None


def is_stale(state: State | None, max_age_minutes: float) -> bool:
    if state is None or state.state in ("unknown", "unavailable", "none", ""):
        return True
    last = getattr(state, "last_reported", None) or state.last_updated
    return dt_util.utcnow() - last > timedelta(minutes=max_age_minutes)


def indoor_temperature_choices(
    hass: HomeAssistant, area_id: str, previous: str | None = None,
) -> list[dict[str, str]]:
    """Select only room temperature sensors with supported Celsius/Fahrenheit units."""
    choices = []
    seen = set()
    for state in hass.states.async_all("sensor"):
        if entity_area(hass, state.entity_id) != area_id:
            continue
        name = state.entity_id.casefold()
        if _device_class(hass, state) != "temperature" and not (
            name.endswith("_temperature") or name.endswith("_temp")
        ):
            continue
        if _temperature_c(20.0, state.attributes.get("unit_of_measurement")) is None:
            continue
        choices.append({"value": state.entity_id,
                        "label": f"{state.name or state.entity_id} · {state.entity_id}"})
        seen.add(state.entity_id)
    if previous and previous not in seen and previous.startswith("sensor."):
        choices.append({"value": previous, "label": f"⚠ {previous}"})
    return sorted(choices, key=lambda option: option["label"].casefold())


def temperature_sensor_c(
    hass: HomeAssistant, entity_id: str, max_age_minutes: float,
) -> float | None:
    """Read a current indoor temperature in Celsius; stale/invalid is unavailable."""
    state = hass.states.get(entity_id)
    if state is None or is_stale(state, max_age_minutes):
        return None
    if _device_class(hass, state) != "temperature" and not (
        entity_id.casefold().endswith("_temperature")
        or entity_id.casefold().endswith("_temp")
    ):
        return None
    value = _numeric(state.state)
    return _temperature_c(value, state.attributes.get("unit_of_measurement"))


def reading(hass: HomeAssistant, entity_id: str, max_age_minutes: float, *, outdoor: bool) -> Reading:
    state = hass.states.get(entity_id)
    if state is None:
        return Reading(entity_id, entity_id, "unknown", None)
    metric = supported_metric(hass, state, outdoor=outdoor)
    name = state.name or entity_id
    if metric is None:
        return Reading(entity_id, name, "unknown", None)
    value = _numeric(state.state)
    if value is None or value < 0 or is_stale(state, max_age_minutes):
        return Reading(entity_id, name, metric, None)
    normalized = _normalize(metric, value, state.attributes.get("unit_of_measurement"))
    # Sanity bounds are not calibration. They reject physically implausible
    # concentrations so a broken low sensor cannot make an unsafe room green.
    # Keep supported_metric() unit checks independent of value validation.
    if metric == "co2" and normalized is not None and not 250 <= normalized <= 20000:
        normalized = None
    if metric == "humidity" and normalized is not None and not 0 < normalized <= 100:
        normalized = None
    return Reading(entity_id, name, metric, normalized)


def is_warning_entity(state: State) -> bool:
    return state.domain in ("sensor", "binary_sensor") and bool(
        WARNING_HINTS.search(state.entity_id) or WARNING_HINTS.search(state.name)
    )


def warning(hass: HomeAssistant, entity_id: str, max_age_minutes: float) -> Warning:
    state = hass.states.get(entity_id)
    # Some warning sensors publish only on transitions: an unchanged 'off'
    # state is not stale simply because it has no periodic measurements.
    # HA's unknown/unavailable signals still fail closed.
    if state is None or state.state in ("unknown", "unavailable", "none", ""):
        return Warning(entity_id, state.name if state else entity_id, None)
    lowered = str(state.state).strip().casefold()
    if state.domain == "binary_sensor":
        result = True if lowered == "on" else False if lowered == "off" else None
    elif lowered in INACTIVE_ALERT_STATES:
        result = False
    elif (number := _numeric(lowered)) is not None:
        result = number > 0
    else:
        # Conservatively treat textual warning levels as active, including
        # yellow/orange/red, minor/moderate/severe and provider descriptions.
        result = True
    return Warning(entity_id, state.name or entity_id, result)


def _temperature_c(value: Any, unit: str | None) -> float | None:
    x = _numeric(value)
    if x is None:
        return None
    if unit in ("°F", "F"):
        return (x - 32) * 5 / 9
    if unit in ("K",):
        return x - 273.15
    return x if unit in ("°C", "C", None) else None


def _wind_kmh(value: Any, unit: str | None) -> float | None:
    x = _numeric(value)
    if x is None:
        return None
    if unit in ("m/s", "mps"):
        return x * 3.6
    if unit in ("mph",):
        return x * 1.609344
    if unit in ("kn", "kts"):
        return x * 1.852
    return x if unit in ("km/h", "kmh", None) else None


def weather(hass: HomeAssistant, entity_id: str, max_age_minutes: float) -> Weather:
    state = hass.states.get(entity_id)
    if state is None or is_stale(state, max_age_minutes):
        return Weather(entity_id, None)
    attrs = state.attributes
    return Weather(
        entity_id=entity_id,
        condition=state.state.casefold(),
        temperature_c=_temperature_c(attrs.get("temperature"), attrs.get("temperature_unit", "°C")),
        humidity=_numeric(attrs.get("humidity")),
        wind_kmh=_wind_kmh(attrs.get("wind_speed"), attrs.get("wind_speed_unit", "km/h")),
    )


# Automatic *suggestions*, not hard exclusions: a window device class describes
# on/off semantics, not whether the signal comes from a physical window contact.
# Window detection inferred by HVAC devices is common and should be reviewed.
_VIRTUAL_WINDOW_LABEL = re.compile(
    r"(?:\b(?:window|fenster|ventana|fenêtre|παράθυρ\w*)\b.{0,35}"
    r"\b(?:detection|detected|recognition|simulation|virtual|prediction|alarm|warning|"
    r"erkennung|erkannt|simulation|détection|détectée?|detecci[oó]n|simulado|"
    r"ανίχνευσ\w*|προσομοίωσ\w*)\b)"
    r"|(?:\b(?:open|offen|abierta?|ouverte?|ανοιχτ\w*)\b.{0,20}"
    r"\b(?:window|fenster|ventana|fenêtre|παράθυρ\w*)\b.{0,30}"
    r"\b(?:detect\w*|erkannt|erkennung|détect\w*|detectad\w*|ανίχνευσ\w*)\b)"
    r"|(?:\b(?:detection|detected|erkennung|erkannt|détection|detecci[oó]n|"
    r"ανίχνευσ\w*)\b.{0,35}\b(?:window|fenster|ventana|fenêtre|παράθυρ\w*)\b)",
    re.IGNORECASE,
)
_HVAC_LABEL = re.compile(
    r"\b(?:thermostat|thermostatkopf|trv|radiator|hvac|heizkörper|"
    r"heizungsregler|heizkörperthermostat|heating valve|chauffage|"
    r"termostato|termostática|θερμοστάτ\w*)\b", re.IGNORECASE
)


def suggested_window_exclusions(hass: HomeAssistant) -> set[str]:
    """Suggest auxiliary/derived window signals, never silently enforce them.

    This intentionally uses only high-signal clues. A generic entity named
    'Bedroom window' stays enabled. Physical/virtual cannot always be proven
    from HA metadata, so every choice remains user-editable and persistent.
    """
    states = hass.states.async_all()
    registry = er.async_get(hass)
    devices = dr.async_get(hass)
    climate_devices = {
        entry.device_id for state in states if state.domain == "climate"
        if (entry := registry.async_get(state.entity_id)) is not None
        and getattr(entry, "device_id", None)
    }
    recommended: set[str] = set()
    for state in states:
        if not is_window(hass, state):
            continue
        entry = registry.async_get(state.entity_id)
        raw_category = (
            (getattr(entry, "entity_category", None) if entry else None)
            or state.attributes.get("entity_category") or ""
        )
        category = str(getattr(raw_category, "value", raw_category)).casefold()
        if category in ("diagnostic", "config"):
            recommended.add(state.entity_id)
            continue
        label = " ".join(str(value or "") for value in (
            state.entity_id.replace("_", " "), state.name,
            getattr(entry, "name", None) if entry else None,
            getattr(entry, "original_name", None) if entry else None,
        ))
        if _VIRTUAL_WINDOW_LABEL.search(label) or _HVAC_LABEL.search(label):
            recommended.add(state.entity_id)
            continue
        device_id = getattr(entry, "device_id", None) if entry else None
        if device_id and device_id in climate_devices:
            recommended.add(state.entity_id)
            continue
        device = devices.async_get(device_id) if device_id else None
        device_name = " ".join(str(value or "") for value in (
            getattr(device, "name", None), getattr(device, "name_by_user", None),
            getattr(device, "model", None),
        )) if device else ""
        if device_name and _HVAC_LABEL.search(device_name):
            recommended.add(state.entity_id)
    return recommended


def window_exclusion_choices(
    hass: HomeAssistant, previously_selected: list[str] | None = None
) -> list[dict[str, str]]:
    """Offer all Window-class binary sensors, with area/name/ID for review."""
    areas = ar.async_get(hass)
    suggested = suggested_window_exclusions(hass)
    choices = []
    seen: set[str] = set()
    for state in hass.states.async_all("binary_sensor"):
        if not is_window(hass, state):
            continue
        entity_id = state.entity_id
        seen.add(entity_id)
        area_id = entity_area(hass, entity_id)
        area = areas.async_get_area(area_id) if area_id else None
        area_name = area.name if area else "—"
        label = f"{state.name or entity_id} · {area_name} · {entity_id}"
        choices.append({"value": entity_id, "label": ("⚠ " if entity_id in suggested else "") + label})
    # Keep saved exclusions if an entity is currently missing/renamed. It can
    # still be deselected, and will not be dropped by unrelated reconfiguration.
    for entity_id in previously_selected or []:
        if entity_id not in seen and entity_id.startswith("binary_sensor."):
            choices.append({"value": entity_id, "label": f"⚠ {entity_id}"})
    return sorted(choices, key=lambda item: (item["label"].lstrip("⚠ ").casefold(), item["value"]))


def is_window(hass: HomeAssistant, state: State) -> bool:
    """Recognize only physical window contacts, never motorized covers."""
    return state.domain == "binary_sensor" and _device_class(hass, state) == "window"


def _window_opened(state: State) -> bool | None:
    return True if state.state == "on" else False if state.state == "off" else None


def rooms(
    hass: HomeAssistant, areas: list[str], max_age_minutes: float,
    excluded_entities: set[str] | None = None,
    source_selections: dict | None = None,
) -> tuple[Room, ...]:
    area_registry = ar.async_get(hass)
    excluded_entities = excluded_entities or set()
    from .room_sources import selected, native
    scoped = {"room_sources": source_selections or {}}
    by_area_windows: dict[str, list[Window]] = {area: [] for area in areas}
    by_area_readings: dict[str, list[Reading]] = {area: [] for area in areas}
    for state in hass.states.async_all():
        area = entity_area(hass, state.entity_id)
        if area not in by_area_windows:
            continue
        if state.entity_id in excluded_entities:
            continue
        if is_window(hass, state):
            allowed = selected(scoped, area, "windows")
            if allowed is None or state.entity_id in allowed and native(hass, state.entity_id):
                by_area_windows[area].append(Window(state.entity_id, state.name or state.entity_id, _window_opened(state)))
        elif (metric := supported_metric(hass, state, outdoor=False)):
            allowed = selected(scoped, area, "humidity" if metric == "humidity" else "air_quality")
            if allowed is None or state.entity_id in allowed and native(hass, state.entity_id):
                by_area_readings[area].append(reading(hass, state.entity_id, max_age_minutes, outdoor=False))

    # A missing/retyped/moved selected contact is unknown, never silently closed.
    for area in areas:
        seen = {item.entity_id for item in by_area_windows[area]}
        for entity in selected(scoped, area, "windows") or ():
            if entity not in seen:
                by_area_windows[area].append(Window(entity, entity, None))
        seen = {item.entity_id for item in by_area_readings[area]}
        for group in ("air_quality", "humidity"):
            for entity in selected(scoped, area, group) or ():
                if entity not in seen:
                    by_area_readings[area].append(Reading(entity, entity,
                        "humidity" if group == "humidity" else "unknown", None))

    return tuple(
        Room(
            area,
            (area_registry.async_get_area(area).name if area_registry.async_get_area(area) else area),
            tuple(sorted(by_area_windows[area], key=lambda s: s.entity_id)),
            tuple(sorted(by_area_readings[area], key=lambda s: s.entity_id)),
        )
        for area in areas
    )


def window_area_choices(
    hass: HomeAssistant, previously_selected: list[str] | None = None,
    excluded_entities: set[str] | None = None,
) -> list[dict[str, str]]:
    """Suggest only areas with recognized windows; retain old selections in Options.

    A window must be a ``binary_sensor`` with the ``window`` device class.
    Covers are never treated as window contacts, even with that device class.
    Areas come from entity overrides or device assignments, not name guesses.

    Existing selections with temporarily removed/disabled windows remain
    selectable so editing an unrelated setting never silently loses rooms.
    """
    registry = ar.async_get(hass)
    excluded_entities = excluded_entities or set()
    counts: Counter[str] = Counter()
    for state in hass.states.async_all():
        if state.entity_id in excluded_entities or not is_window(hass, state):
            continue
        area_id = entity_area(hass, state.entity_id)
        if area_id and registry.async_get_area(area_id) is not None:
            counts[area_id] += 1

    choices = []
    for area_id, count in counts.items():
        area = registry.async_get_area(area_id)
        choices.append({
            "value": area_id,
            "label": f"{area.name} · {count} 🪟",
        })

    for area_id in set(previously_selected or []) - counts.keys():
        area = registry.async_get_area(area_id)
        if area is not None:
            choices.append({
                "value": area_id,
                "label": f"{area.name} · ⚠ 0 🪟",
            })

    return sorted(
        choices,
        key=lambda choice: (
            choice["value"] not in counts,
            choice["label"].casefold(),
        ),
    )



def indoor_sensor_exclusion_choices(
    hass: HomeAssistant, area_id: str, previously_selected: list[str] | None = None
) -> list[dict[str, str]]:
    """Build a strict supported-sensor list for one selected room.

    Use entity-area overrides and device areas exactly like runtime discovery.
    Show the registered device name, user-visible entity name, metric and ID so
    users can distinguish e.g. the humidity entity of a combined CO₂ device.
    Already excluded entities that went offline or vanished remain removable.
    """
    registry = er.async_get(hass)
    devices = dr.async_get(hass)
    titles = {
        "aqi": "AQI", "co2": "CO₂", "pm25": "PM2.5", "pm10": "PM10",
        "voc": "VOC (µg/m³)", "voc_parts": "VOC (ppb)", "humidity": "RH (%)",
    }
    known: set[str] = set()
    options: list[dict[str, str]] = []
    for state in hass.states.async_all("sensor"):
        if entity_area(hass, state.entity_id) != area_id:
            continue
        metric = supported_metric(hass, state, outdoor=False)
        if metric is None:
            continue
        entity_id = state.entity_id
        entry = registry.async_get(entity_id)
        device_id = getattr(entry, "device_id", None) if entry else None
        device = devices.async_get(device_id) if device_id else None
        device_name = (
            (getattr(device, "name_by_user", None) or getattr(device, "name", None))
            if device else None
        )
        entity_name = (getattr(entry, "name", None) if entry else None) or state.name or entity_id
        prefix = f"{device_name} › " if device_name else ""
        options.append({
            "value": entity_id,
            "label": f"{prefix}{entity_name} · {titles[metric]} · {entity_id}",
        })
        known.add(entity_id)
    for entity_id in previously_selected or []:
        # Keep a previously excluded missing sensor removable without offering
        # arbitrary new entity IDs or pulling in sensors from another room.
        if entity_id not in known and entity_id.startswith("sensor."):
            options.append({"value": entity_id, "label": f"⚠ {entity_id}"})
    return sorted(options, key=lambda item: (item["label"].casefold(), item["value"]))


def outdoor_choices(
    hass: HomeAssistant, excluded_areas: list[str] | None = None
) -> list[dict[str, str]]:
    choices = []
    blocked = set(excluded_areas or [])
    for state in hass.states.async_all("sensor"):
        if entity_area(hass, state.entity_id) in blocked:
            continue
        if (metric := supported_metric(hass, state, outdoor=True)) is not None:
            choices.append({"value": state.entity_id, "label": f"{state.name} ({metric.upper()})"})
    return sorted(choices, key=lambda item: item["label"].casefold())


def warning_choices(hass: HomeAssistant) -> list[dict[str, str]]:
    return sorted(
        (
            {"value": state.entity_id, "label": state.name or state.entity_id}
            for state in hass.states.async_all()
            if is_warning_entity(state)
        ),
        key=lambda item: item["label"].casefold(),
    )
