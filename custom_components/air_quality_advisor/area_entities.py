"""One compact environment overview entity per configured Home Assistant area.

Measurements remain owned by their original source integrations. Native climate
entities own their supported targets and controls. This device reports only the
manager's room assessment, with a dashboard-friendly raw-input snapshot.
"""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers import area_registry as ar, device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    CONF_AREAS, CONF_CLIMATE_ROOMS, CONF_PID_ROOMS, DOMAIN, SIGNAL_UPDATED,
)
from .dashboard import dashboard_snapshot


def _configured_areas(manager):
    settings = manager.settings
    areas = list(settings.get(CONF_AREAS, []) or [])
    for key in (CONF_CLIMATE_ROOMS, CONF_PID_ROOMS):
        extra = settings.get(key, {})
        if isinstance(extra, dict):
            areas.extend(extra)
    return tuple(dict.fromkeys(a for a in areas if isinstance(a, str) and a))


def _room_snapshot(manager, area_id):
    snapshot = dashboard_snapshot(manager.plan, manager.thresholds)
    return next((room for room in snapshot["rooms"]
                 if room["area_id"] == area_id), None)


async def async_area_entities(hass, entry):
    """Create one device and one overview sensor for every selected area."""
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
        result.append(AreaOverview(manager, entry.entry_id, area_id))
    return result


class AreaOverview(SensorEntity):
    """Calculated room assessment; raw inputs are attributes, never duplicates."""

    _attr_has_entity_name = True
    _attr_name = "Environment overview"
    _attr_icon = "mdi:home-analytics"
    _attr_should_poll = False

    def __init__(self, manager, entry_id, area_id):
        self._manager = manager
        self._area_id = area_id
        self._attr_unique_id = f"{entry_id}_area_{area_id}_overview"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_area_{area_id}")},
        }

    @property
    def native_value(self):
        room = _room_snapshot(self._manager, self._area_id)
        if room is None:
            return "unknown"
        # A configured climate-only room has no air-quality assessment;
        # expose the manager's climate decision instead.
        if room.get("climate_only"):
            plan = room.get("environment", {}).get("climate_plan", {})
            return plan.get("status", "unknown") if isinstance(plan, dict) else "unknown"
        return room.get("status", "unknown")

    @property
    def extra_state_attributes(self):
        room = _room_snapshot(self._manager, self._area_id)
        if room is None:
            return {"area_id": self._area_id, "data_available": False}
        environment = room.get("environment", {})
        if not isinstance(environment, dict):
            environment = {}
        climate = environment.get("climate_plan", {})
        if not isinstance(climate, dict):
            climate = {}
        # Keep attributes finite and dashboard-friendly: no full history,
        # arbitrary nested equipment payloads, or duplicated climate controls.
        inputs = [
            {
                "entity_id": item.get("entity_id"),
                "metric": item.get("metric"),
                "value": item.get("value"),
                "unit": item.get("unit"),
                "available": item.get("available", False),
            }
            for item in room.get("readings", [])
        ]
        pid = getattr(getattr(self._manager, "pid", None), "statuses", {})
        pid_status = pid.get(self._area_id) if isinstance(pid, dict) else None
        assessment = {
            "status": room.get("status"),
            "status_detail": room.get("status_detail"),
            "action": room.get("action"),
            "reasons": room.get("reasons", []),
            "high_count": room.get("high_count", 0),
            "available_count": room.get("available_count", 0),
            "ventilating": room.get("ventilating", False),
        }
        controller = {
            "status": climate.get("status"),
            "profile": climate.get("profile"),
            "mode": climate.get("mode"),
            "occupancy": climate.get("occupancy"),
            "sleeping": climate.get("sleeping"),
            "away": climate.get("away"),
            "reason": climate.get("reason"),
            "actuation": climate.get("actuation"),
            "pid": pid_status,
        }
        return {
            "area_id": self._area_id,
            "data_available": True,
            "assessment": assessment,
            "inputs": inputs,
            "window_contacts": room.get("windows", []),
            "controller": {key: value for key, value in controller.items()
                           if value is not None},
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(
            self.hass, f"{SIGNAL_UPDATED}_{self._manager.entry.entry_id}",
            self._update,
        ))

    @callback
    def _update(self):
        self.async_write_ha_state()
