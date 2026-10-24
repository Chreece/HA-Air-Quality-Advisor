"""The single recommendation entity; actions and reasons are its attributes."""

from __future__ import annotations

from .room_hubs import async_add_grouped_entities

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_EXCLUDED_WINDOWS, CONF_EXCLUDED_INDOOR, DOMAIN, NAME, SIGNAL_UPDATED
from .recorder_attributes import bounded_attributes
from .messages import announcement, explain
from . import equipment_model as equipment
from .equipment_status import ControllerStatusSensor


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Create exactly one entity per config entry."""
    from .area_entities import async_area_entities
    area_entities = await async_area_entities(hass, entry)
    controllers = [
        ControllerStatusSensor(entry.runtime_data, spec)
        for spec in equipment.specs(entry.runtime_data)
    ]
    async_add_grouped_entities(entry.runtime_data, async_add_entities, [
        AirQualityRecommendation(entry.runtime_data, entry.entry_id),
        *area_entities, *controllers,
    ])


class AirQualityRecommendation(SensorEntity):
    """Expose open/close actions and their human-readable justifications."""

    _attr_has_entity_name = True
    _attr_translation_key = "recommendation"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["open", "close", "idle", "blocked"]
    # icons.json supplies distinct Home Assistant icons for open/close/idle/blocked.
    _attr_should_poll = False

    def __init__(self, manager: Any, entry_id: str) -> None:
        self._manager = manager
        self._dashboard_revision = 0
        self._attr_unique_id = f"{entry_id}_recommendation"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": NAME,
            "manufacturer": "Home Environment Manager",
        }

    @property
    def native_value(self) -> str:
        return self._manager.plan.status

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        plan = self._manager.plan
        language = self._manager.get_language(None)
        actionable = []
        open_ids = []
        close_ids = []
        for rec in plan.recommendations:
            title, message = announcement(rec, language)
            entity_ids = [win.entity_id for win in rec.windows]
            (open_ids if rec.action == "open" else close_ids).extend(entity_ids)
            actionable.append({
                "action": rec.action,
                "area_id": rec.area_id,
                "area": rec.area_name,
                "windows": entity_ids,
                "window_names": [win.name for win in rec.windows],
                "reasons": [
                    {"code": reason.code, "entity": reason.label, "value": reason.value}
                    for reason in rec.reasons
                ],
                "message": message,
            })
        details = {
            # outdoor_safe means no *known* blockers, not that every selected
            # sensor currently provides a verified air-quality measurement.
            "outdoor_safe": plan.outdoor_safe,
            "outdoor_data_complete": not plan.unavailable_outdoor,
            "unavailable_outdoor_sensors": list(plan.unavailable_outdoor),
            "excluded_window_entities": list(self._manager.settings.get(CONF_EXCLUDED_WINDOWS, [])),
            "excluded_indoor_entities": dict(self._manager.settings.get(CONF_EXCLUDED_INDOOR, {})),
            "open_windows": open_ids,
            "close_windows": close_ids,
            "recommendations": actionable,
            "outside_blockers": [explain(reason, language) for reason in plan.outside_reasons],
            "diagnostics": [
                {"area": name, "problem": problem} for name, problem in plan.diagnostics
            ],
            "mold_input_warnings": [
                {
                    "area_id": room.area_id,
                    "area": room.name,
                    "missing_inputs": list(item.details.get("missing_inputs", [])),
                }
                for room in plan.rooms for item in room.readings
                if item.metric == "mold" and item.value is None
                and item.details and item.details.get("missing_inputs")
            ],
            "language": language,
            "announcement_hub_available": self._manager.hub_available,
            # This existing recommendation belongs to the new parent Home
            # device and remains the one complete aggregated dashboard source.
            "home_settings": {
                "thresholds": dict(self._manager.thresholds),
                "automatic_notifications": self._manager.settings.get("automatic_notifications", False),
                "automatic_tts": self._manager.settings.get("automatic_tts", False),
                "announcement_repeat_minutes": self._manager.repeat_minutes,
                "language": self._manager.settings.get("language", "auto"),
                "global_occupancy": dict(self._manager.settings.get("occupancy_global") or {}),
                "outdoor_sources": list(self._manager.settings.get("outdoor_sensors", [])),
                "weather_sources": list(self._manager.settings.get("weather_entities", [])),
                "warning_sources": list(self._manager.settings.get("weather_warnings", [])),
                "pollen_sources": list((self._manager.settings.get("environment_global") or {}).get(
                    "pollen_entities", [])),
                "announcement_hub_enabled": self._manager.settings.get("use_announcement_hub", False),
                "ai_provider": self._manager.settings.get("ai_conversation_agent", "default"),
                "tts_engine": self._manager.settings.get("tts_engine"),
                "tts_language": self._manager.settings.get("language", "auto"),
                "away_cooldown_minutes": (self._manager.settings.get("occupancy_global") or {}).get(
                    "away_cooldown_minutes", 10),
            },
        }
        # The full dashboard snapshot used to be embedded here. On a
        # multi-room home that routinely exceeds Recorder's hard 16 KB
        # attribute limit, causing repeated database warnings and losing
        # *all* state attributes in history. Serve that complete snapshot
        # separately via the authenticated read-only Home Assistant WebSocket
        # API; this sensor remains the stable automation/recommendation source.
        summary = {
            "dashboard_api": "environment_manager/dashboard",
            "dashboard_version": 1,
            "dashboard_revision": self._dashboard_revision,
            "outdoor_safe": plan.outdoor_safe,
            "outdoor_data_complete": not plan.unavailable_outdoor,
            "recommendation_count": len(actionable),
            "open_window_count": len(open_ids),
            "close_window_count": len(close_ids),
            "language": language,
        }
        priority = (
            "open_windows", "close_windows", "recommendations",
            "outside_blockers", "diagnostics", "mold_input_warnings",
            "unavailable_outdoor_sensors", "excluded_window_entities",
            "excluded_indoor_entities", "home_settings",
            "announcement_hub_available",
        )
        return bounded_attributes(
            summary, {key: details[key] for key in priority if key in details},
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(
            self.hass, f"{SIGNAL_UPDATED}_{self._manager.entry.entry_id}", self._on_update
        ))

    @callback
    def _on_update(self) -> None:
        # A small monotonic change token tells frontend cards when their
        # on-demand WS snapshot needs refresh without writing that JSON to
        # the Recorder. It is intentionally instance-local and resets on reload.
        self._dashboard_revision += 1
        self.async_write_ha_state()

