"""Locate supported HA sensors and windows without integration-specific assumptions."""

from __future__ import annotations

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
    "volatile_organic_compounds": "voc",
    "volatile_organic_compounds_parts": "voc_parts",
    "humidity": "humidity",
}
# Exact trailing names are useful for template sensors that omit device_class.
SUFFIX_METRICS = {
    "aqi": "aqi", "air_quality_index": "aqi", "co2": "co2",
    "pm25": "pm25", "pm2_5": "pm25", "pm10": "pm10",
    "tvoc": "voc", "voc": "voc", "humidity": "humidity",
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
        (entry.device_class or entry.original_device_class) if entry else ""
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
    if metric in ("pm25", "pm10", "voc"):
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
    # Unknown readings can remain in the list if device_class declares a valid
    # metric and units are consistent; evaluated readings then fail closed.
    return metric if _normalize(metric, 1.0, unit) is not None else None


def is_stale(state: State | None, max_age_minutes: float) -> bool:
    if state is None or state.state in ("unknown", "unavailable", "none", ""):
        return True
    last = getattr(state, "last_reported", None) or state.last_updated
    return dt_util.utcnow() - last > timedelta(minutes=max_age_minutes)


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


def is_window(hass: HomeAssistant, state: State) -> bool:
    return (
        (state.domain == "binary_sensor" or state.domain == "cover")
        and _device_class(hass, state) == "window"
    )


def _window_opened(state: State) -> bool | None:
    value = state.state.casefold()
    if state.domain == "binary_sensor":
        return True if value == "on" else False if value == "off" else None
    return True if value in ("open", "opening", "closing") else False if value == "closed" else None


def rooms(
    hass: HomeAssistant, areas: list[str], max_age_minutes: float,
    excluded_entities: set[str] | None = None,
) -> tuple[Room, ...]:
    area_registry = ar.async_get(hass)
    excluded_entities = excluded_entities or set()
    by_area_windows: dict[str, list[Window]] = {area: [] for area in areas}
    by_area_readings: dict[str, list[Reading]] = {area: [] for area in areas}
    for state in hass.states.async_all():
        area = entity_area(hass, state.entity_id)
        if area not in by_area_windows:
            continue
        if is_window(hass, state):
            by_area_windows[area].append(Window(state.entity_id, state.name or state.entity_id, _window_opened(state)))
        elif state.entity_id not in excluded_entities and supported_metric(hass, state, outdoor=False):
            by_area_readings[area].append(reading(hass, state.entity_id, max_age_minutes, outdoor=False))

    return tuple(
        Room(
            area,
            (area_registry.async_get_area(area).name if area_registry.async_get_area(area) else area),
            tuple(sorted(by_area_windows[area], key=lambda s: s.entity_id)),
            tuple(sorted(by_area_readings[area], key=lambda s: s.entity_id)),
        )
        for area in areas
    )


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
