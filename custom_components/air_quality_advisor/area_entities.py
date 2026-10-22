"""Per-area Home Environment Manager devices with minimal calculated entities.

The original climate/humidifier/fan/source integrations retain their native
entities, setpoints and modes. One room overview exposes observed inputs,
provenance, environmental decisions and controller diagnostics as attributes.
Only the genuinely calculated mold surface RH gets a numeric sensor.
No entity here sends a physical hardware command.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    CONF_AREAS, CONF_CLIMATE_ROOMS, CONF_MOLD_ROOMS, CONF_PID_ROOMS,
    CONF_USE_MOLD, DOMAIN, SIGNAL_UPDATED,
)
from .dashboard import dashboard_snapshot
from .device_hierarchy import (
    async_register_hierarchy, configured_area_ids, hierarchy_attributes,
)

_CONTROLLER_SOURCES = (
    "temperature_entity", "humidity_entity", "climate_entity",
    "heat_climate_entity", "cool_climate_entity",
    "heat_actuator", "cool_actuator",
    "humidifier_entity", "dehumidifier_entity",
    "fan_entity", "extractor_entity", "purifier_entity",
    "occupancy_sensors", "away_entities",
)
_ACTUATOR_STATUS_KEYS = (
    "actuation", "humidity_actuation", "humidity_power_actuation",
    "secondary_actuation", "fan_actuation", "fan_power_actuation",
    "native_air_mode_actuation",
)



def room_snapshot(manager: Any, area_id: str) -> dict[str, Any] | None:
    snapshot = dashboard_snapshot(manager.plan, manager.thresholds)
    return next((item for item in snapshot["rooms"]
                 if item["area_id"] == area_id), None)


def calculated_mold(room: dict[str, Any] | None) -> dict[str, Any] | None:
    if not room:
        return None
    for reading in room.get("readings", []):
        if reading.get("metric") == "mold":
            return reading
    return None


def input_snapshot(hass: Any, reading: dict[str, Any]) -> dict[str, Any]:
    """Expose the original HA state alongside the normalized reading.

    A synthetic derived value must never masquerade as a physical sensor.
    Missing/unavailable raw states stay missing; no zero or safe placeholder.
    """
    entity_id = reading.get("entity_id")
    state = (hass.states.get(entity_id)
             if isinstance(entity_id, str) and not entity_id.startswith("derived.")
             else None)
    raw = None if state is None or state.state in ("unknown", "unavailable") else state.state
    return {
        "entity_id": entity_id,
        "metric": reading.get("metric"),
        "raw_state": raw,
        "raw_unit": state.attributes.get("unit_of_measurement") if state else None,
        "value": reading.get("value"),
        "unit": reading.get("unit"),
        "available": reading.get("available") is True,
        "derived": state is None and isinstance(entity_id, str)
                   and entity_id.startswith("derived."),
    }


def _pid_overview(settings: dict, area_id: str) -> dict[str, Any] | None:
    """Expose the actual PID gain source and supervisor parameters on the room."""
    configured = settings.get(CONF_PID_ROOMS, {})
    active = configured.get(area_id) if isinstance(configured, dict) else None
    if not isinstance(active, dict) or active.get("enabled") is not True:
        return None
    from .device_controls import pid_settings, tuning_source

    config = pid_settings(settings, area_id)
    if config is None:
        return None
    return {
        "gain_source": tuning_source(config),
        "kp": config["kp"], "ki": config["ki"], "kd": config["kd"],
        "sample_seconds": config["sample_seconds"],
        "outer_loop_target_c": config["target_c"],
        "physical_thermostat_keeps_hvac_safety": True,
    }


def _mold_calibration_overview(settings: dict, area_id: str) -> dict | None:
    """Source choice and calibration evidence, not duplicated raw sensors."""
    if settings.get(CONF_USE_MOLD) is not True:
        return None
    rooms = settings.get(CONF_MOLD_ROOMS, {})
    raw = rooms.get(area_id, {}) if isinstance(rooms, dict) else {}
    if not isinstance(raw, dict):
        return None
    return {
        "indoor_temperature_entity": raw.get("indoor_temperature_entity"),
        "outdoor_weather_entity": raw.get("outdoor_weather_entity"),
        "measured_cold_surface_c": raw.get("critical_temperature_c"),
        "factor": raw.get("calibration_factor"),
        "calibrated_at": raw.get("calibrated_at"),
        "calibration_status": (
            "calibrated" if raw.get("calibration_factor") is not None
            else "needs_calibration"
        ),
    }


def overview_attributes(manager: Any, area_id: str) -> dict[str, Any]:
    from .room_sources import source_overview
    selected_inputs = source_overview(manager, area_id)
    room = room_snapshot(manager, area_id)
    if room is None:
        return {"area_id": area_id, "data_available": False, "selected_inputs": selected_inputs,
                **hierarchy_attributes(manager, area_id)}

    climate = room.get("environment", {}).get("climate_plan", {})
    climate = climate if isinstance(climate, dict) else {}
    environment = room.get("environment", {})
    environment = environment if isinstance(environment, dict) else {}
    config = manager.settings.get(CONF_CLIMATE_ROOMS, {})
    cfg = config.get(area_id, {}) if isinstance(config, dict) else {}
    cfg = cfg if isinstance(cfg, dict) else {}
    pid = environment.get("climate_pid")
    mold = calculated_mold(room)

    raw_inputs = [input_snapshot(manager.hass, reading)
                  for reading in room.get("readings", [])[:48]]
    window_inputs = []
    for window in room.get("windows", [])[:32]:
        entity_id = window.get("entity_id")
        state = manager.hass.states.get(entity_id)
        window_inputs.append({
            "entity_id": entity_id,
            "raw_state": state.state if state and
                         state.state not in ("unknown", "unavailable") else None,
            "opened": window.get("opened"),
        })

    sources = {key: cfg[key] for key in _CONTROLLER_SOURCES
               if key in cfg and cfg[key]}
    if cfg.get("enabled") is True:
        sources["controller"] = cfg.get("controller")

    assessment = {
        "status": room.get("status"),
        "detail": room.get("status_detail"),
        "window_action": room.get("action"),
        "action_windows": room.get("action_window_ids", []),
        "reasons": room.get("reasons", [])[:12],
        "high_count": room.get("high_count", 0),
        "available_count": room.get("available_count", 0),
    }
    calculated = {}
    if mold is not None:
        details = mold.get("details") or {}
        calculated["surface_relative_humidity_percent"] = mold.get("value")
        calculated["mold_status"] = details.get("status")
        calculated["dew_point_c"] = details.get("dewpoint_c")
        calculated["estimated_surface_temperature_c"] = details.get("estimated_surface_c")
        calculated["mold_missing_inputs"] = details.get("missing_inputs", [])
    for key in ("moisture", "thermal_comfort", "passive_cooling", "condensation"):
        val = environment.get(key)
        if isinstance(val, dict):
            # The dashboard already knows the full science model; keep room
            # attributes compact, without copying long histories.
            calculated[key] = {k: v for k, v in val.items()
                               if k in ("status", "reason", "dewpoint_c",
                                        "upper_80_c", "lower_80_c", "risk",
                                        "indicator", "indoor_dewpoint_c")}

    controller = {}
    if cfg.get("enabled") is True:
        controller = {
            "strategy": cfg.get("controller"),
            "mode": climate.get("mode"),
            "profile": climate.get("profile"),
            "status": climate.get("status"),
            "reason": climate.get("reason"),
            "auto_control_authorized": cfg.get("allow_actuation") is True,
            "occupancy": climate.get("occupancy"),
            "sleeping": climate.get("sleeping"),
            "at_home": climate.get("away"),
            "requested_target_c": climate.get("temperature_target_c"),
            "requested_low_c": climate.get("low_target_c"),
            "requested_high_c": climate.get("high_target_c"),
            "actuators": {
                key: climate[key] for key in _ACTUATOR_STATUS_KEYS
                if isinstance(climate.get(key), dict)
            },
        }
    return {
        "area_id": area_id,
        **hierarchy_attributes(manager, area_id),
        "room_name": room.get("name"),
        "data_available": True,
        "monitoring_enabled": not room.get("climate_only", False),
        "assessment": assessment,
        "raw_inputs": raw_inputs,
        "selected_inputs": selected_inputs,
        "window_inputs": window_inputs,
        "configured_controller_sources": sources,
        "calculated": calculated,
        "controller": controller,
        "pid": pid if isinstance(pid, dict) else None,
        "pid_tuning": _pid_overview(manager.settings, area_id),
        "mold_calibration": _mold_calibration_overview(manager.settings, area_id),
    }


async def async_area_entities(hass: Any, entry: Any) -> list[SensorEntity]:
    """Create one registry device per real selected area, keeping user area moves."""
    manager = entry.runtime_data
    areas = ar.async_get(hass)
    if not hasattr(manager, "_device_hierarchy"):
        # Direct platform setup (and tests) still gets ordered registration.
        async_register_hierarchy(hass, entry)
    result: list[SensorEntity] = []
    for area_id in configured_area_ids(manager.settings):
        area = areas.async_get_area(area_id)
        if area is None:  # Deleted/stale HA area; never invent a registry area.
            continue
        result.append(AreaOverview(manager, entry.entry_id, area_id))
        # Mold surface RH is a derived measurement; unlike raw room humidity,
        # it has no physical HA entity already representing the calculation.
        if manager.settings.get(CONF_USE_MOLD) is True:
            monitored = manager.settings.get(CONF_AREAS, [])
            if area_id in monitored:
                result.append(AreaMoldSurfaceHumidity(manager, entry.entry_id, area_id))
    return result


class _AreaEntity(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: Any, entry_id: str, area_id: str, suffix: str):
        self._manager = manager
        self._area_id = area_id
        self._attr_unique_id = f"{entry_id}_area_{area_id}_{suffix}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_area_{area_id}")},
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(
            self.hass, f"{SIGNAL_UPDATED}_{self._manager.entry.entry_id}",
            self._on_update,
        ))

    @callback
    def _on_update(self):
        self.async_write_ha_state()


class AreaOverview(_AreaEntity):
    """One calculated assessment entity; raw signals live in attributes only."""

    _attr_translation_key = "area_overview"
    _attr_icon = "mdi:home-analytics"

    def __init__(self, manager: Any, entry_id: str, area_id: str):
        super().__init__(manager, entry_id, area_id, "overview")

    @property
    def native_value(self):
        room = room_snapshot(self._manager, self._area_id)
        if room is None:
            return "unknown"
        if room.get("climate_only"):
            climate = room.get("environment", {}).get("climate_plan", {})
            return climate.get("status", "unknown") if isinstance(climate, dict) else "unknown"
        return room.get("status", "unknown")

    @property
    def extra_state_attributes(self):
        return overview_attributes(self._manager, self._area_id)


class AreaMoldSurfaceHumidity(_AreaEntity):
    """Optional calibrated relative humidity at the coldest room surface."""

    _attr_translation_key = "area_surface_humidity"
    _attr_icon = "mdi:water-percent"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, manager: Any, entry_id: str, area_id: str):
        super().__init__(manager, entry_id, area_id, "surface_humidity")

    @property
    def native_value(self):
        mold = calculated_mold(room_snapshot(self._manager, self._area_id))
        return mold.get("value") if mold and mold.get("available") else None

    @property
    def extra_state_attributes(self):
        mold = calculated_mold(room_snapshot(self._manager, self._area_id))
        if mold is None:
            return {"calibration_status": "not_configured"}
        details = mold.get("details") or {}
        return {
            "calibration_status": details.get("status", "unknown"),
            "dew_point_c": details.get("dewpoint_c"),
            "estimated_surface_temperature_c": details.get("estimated_surface_c"),
            "missing_inputs": details.get("missing_inputs", []),
            "calibration_factor": details.get("calibration_factor"),
            "calibrated_at": _mold_calibration_overview(
                self._manager.settings, self._area_id
            ).get("calibrated_at"),
            "measured_cold_surface_c": _mold_calibration_overview(
                self._manager.settings, self._area_id
            ).get("measured_cold_surface_c"),
        }
