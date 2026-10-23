"""Exact-device authorization from its own controls, not a hidden setup menu.

Choosing Automatic, PID or Manual is explicit consent for this exact native
controller to regulate setpoints/speed and to turn its supported native mode
on/off as needed. Raw relay commissioning is never inferred. Input/identity changes invalidate consent until reselected.
"""
from __future__ import annotations
from .config_data import mutable_copy


def authority_context(manager, spec):
    from homeassistant.helpers import entity_registry as er
    from . import equipment_model as model
    registry = er.async_get(manager.hass)
    room = model.room_config(manager, spec)
    source_map = manager.settings.get("room_sources", {}).get(spec.area_id)
    pins = {}
    for entity in spec.source_entities:
        dev = model.device_config(manager, spec, entity)
        pins[entity] = {key: [room.get(key), dev.get(key)] for key in (
            "temperature_entity", "humidity_entity", "co2_entity", "pm25_entity")}
        pins[entity]["selection_generation"] = dev.get("selection_generation", 0)
        pins[entity]["legacy_permission"] = [dev.get("auto_control"), dev.get("hardware_confirmed"), dev.get("method")]
    return mutable_copy({"area": spec.area_id, "physical_device": spec.source_device_id,
        "sources": [[entity, getattr(registry.async_get(entity), "id", None),
                     getattr(registry.async_get(entity), "unique_id", None)] for entity in spec.source_entities],
        "inputs": {key: source_map.get(key, []) for key in ("windows", "temperature", "humidity", "air_quality")}
                   if source_map is not None else None,
        "source_revision": room.get("source_revision", 0),
        "excluded": manager.settings.get("excluded_indoor_entities", {}).get(spec.area_id, []),
        "pins": pins})


def authorized(manager, spec):
    from . import equipment_model as model
    value = model.settings(manager, spec).get("_native_authorization")
    return isinstance(value, dict) and value == authority_context(manager, spec)


def effective_device(manager, spec, entity):
    from . import equipment_model as model
    original = model.device_config(manager, spec, entity)
    result = dict(original)
    cfg = model.settings(manager, spec)
    if authorized(manager, spec):
        result["auto_control"] = True
    for key in ("presence_requirement", "sleep_behavior", "fan_purpose", "sensor_verified"):
        if key in cfg and cfg[key] is not None and cfg[key] != "auto":
            result[key] = cfg[key]
    if not result.get("fan_purpose") or result["fan_purpose"] == "auto":
        from .room_sources import selected
        from .discovery import supported_metric
        ids = selected(manager.settings, spec.area_id, "air_quality")
        metrics = {supported_metric(manager.hass, state, outdoor=False)
                   for entity in ids or () if (state := manager.hass.states.get(entity)) is not None}
        if ("co2" in metrics) != ("pm25" in metrics):
            result["fan_purpose"] = "extraction" if "co2" in metrics else "filtration"
    return result


def planning_rooms(manager):
    """Generate room evidence without enabling any previous actuator driver."""
    from . import equipment_model as model
    rooms = mutable_copy(manager.settings.get("climate_rooms", {}))
    for spec in model.specs(manager):
        if model.settings(manager, spec)["control_mode"] in ("automatic", "pid") and authorized(manager, spec):
            room = rooms.setdefault(spec.area_id, {})
            if room.get("enabled") is not True:
                room.update(enabled=True, controller="environment", allow_actuation=False)
    return rooms
