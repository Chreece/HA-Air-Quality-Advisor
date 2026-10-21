"""Per-area Home Assistant devices and safe environment observations.

These entities mirror the existing decision engine; they never independently
command equipment or manufacture measurements from missing sensors.
"""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.core import callback
from homeassistant.helpers import area_registry as ar, device_registry as dr

from .const import (DOMAIN, CONF_AREAS, CONF_CLIMATE_ROOMS, CONF_PID_ROOMS,
                    SIGNAL_UPDATED)
from .dashboard import dashboard_snapshot

# A stable unit and name for each actual measurement or requested target.
FIELDS = {
    "temperature": ("Temperature", "°C", "mdi:thermometer"),
    "humidity": ("Relative humidity", "%", "mdi:water-percent"),
    "co2": ("CO2", "ppm", "mdi:molecule-co2"),
    "pm25": ("PM2.5", "µg/m³", "mdi:blur"),
    "target_temperature": ("Temperature target", "°C", "mdi:thermometer-check"),
    "target_low": ("Minimum target", "°C", "mdi:thermometer-low"),
    "target_high": ("Maximum target", "°C", "mdi:thermometer-high"),
    "control_status": ("Climate control status", None, "mdi:thermostat"),
    "control_profile": ("Climate profile", None, "mdi:home-thermometer"),
    "requested_mode": ("Requested HVAC mode", None, "mdi:hvac"),
}

def _configured_areas(manager):
    settings = manager.settings
    areas = list(settings.get(CONF_AREAS, []) or [])
    for key in (CONF_CLIMATE_ROOMS, CONF_PID_ROOMS):
        extra = settings.get(key, {})
        if isinstance(extra, dict):
            areas.extend(extra)
    return tuple(dict.fromkeys(a for a in areas if isinstance(a, str) and a))

def _values(manager, area_id):
    snapshot = dashboard_snapshot(manager.plan, manager.thresholds)
    room = next((r for r in snapshot["rooms"] if r["area_id"] == area_id), None)
    if room is None:
        return {}
    readings = {r["metric"]: r["value"] for r in room["readings"]
                if r.get("available") and r.get("value") is not None}
    climate = room.get("environment", {}).get("climate_plan", {})
    if not isinstance(climate, dict):
        climate = {}
    pid_config = manager.settings.get(CONF_PID_ROOMS, {})
    pid_config = pid_config.get(area_id, {}) if isinstance(pid_config, dict) else {}
    pid_status = getattr(getattr(manager, "pid", None), "statuses", {}).get(area_id, {})
    result = {
        "humidity": readings.get("humidity"),
        "co2": readings.get("co2"),
        "pm25": readings.get("pm25"),
        "temperature": climate.get("temperature_c", readings.get("temperature")),
        "target_temperature": climate.get("temperature_target_c", pid_config.get("target_c")),
        "target_low": climate.get("low_target_c"),
        "target_high": climate.get("high_target_c"),
        "control_status": climate.get("status", pid_status.get("status")),
        "control_profile": climate.get("profile"),
        "requested_mode": climate.get("mode"),
    }
    return result

async def async_area_entities(hass, entry):
    """Register one device per selected area; attach only meaningful entities."""
    manager = entry.runtime_data
    areas = ar.async_get(hass)
    devices = dr.async_get(hass)
    result = []
    for area_id in _configured_areas(manager):
        area = areas.async_get_area(area_id)
        if area is None:
            continue
        device = devices.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"{entry.entry_id}_area_{area_id}")},
            name=f"{area.name} Environment",
            manufacturer="Home Environment Manager",
            model="Room Environment Controller",
        )
        if device.area_id is None:
            devices.async_update_device(device.id, area_id=area_id)
        # Only offer metrics that have relevant configured sources. A missing
        # reading is then unavailable, not zero or falsely healthy.
        configured_climate = manager.settings.get(CONF_CLIMATE_ROOMS, {})
        configured_pid = manager.settings.get(CONF_PID_ROOMS, {})
        climate_enabled = isinstance(configured_climate, dict) and area_id in configured_climate
        pid_enabled = isinstance(configured_pid, dict) and area_id in configured_pid
        snapshot = dashboard_snapshot(manager.plan, manager.thresholds)
        room = next((item for item in snapshot["rooms"]
                     if item["area_id"] == area_id), None)
        present_metrics = {item["metric"] for item in room["readings"]} if room else set()
        candidates = [field for field in ("humidity", "co2", "pm25")
                      if field in present_metrics]
        climate = (room or {}).get("environment", {}).get("climate_plan", {})
        if climate_enabled and isinstance(climate, dict) and climate:
            candidates += ["temperature", "target_temperature", "target_low",
                           "target_high", "control_status", "control_profile",
                           "requested_mode"]
        elif pid_enabled:
            # Legacy PID exposes its status via the coordinator, not the
            # separate climate-plan payload. Do not create empty placeholders.
            candidates += ["temperature", "target_temperature", "control_status"]
        for field in candidates:
            result.append(AreaEnvironmentSensor(manager, entry.entry_id, area_id, field))
    return result

class AreaEnvironmentSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager, entry_id, area_id, field):
        self._manager = manager
        self._area_id = area_id
        self._field = field
        name, unit, icon = FIELDS[field]
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry_id}_area_{area_id}_{field}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_area_{area_id}")},
        }
        self._attr_native_unit_of_measurement = unit
        if unit is not None:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        return _values(self._manager, self._area_id).get(self._field)

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(
            self.hass, f"{SIGNAL_UPDATED}_{self._manager.entry.entry_id}",
            self._update,
        ))

    @callback
    def _update(self):
        self.async_write_ha_state()
