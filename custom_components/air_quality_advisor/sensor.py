"""The single recommendation entity; actions and reasons are its attributes."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, NAME, SIGNAL_UPDATED
from .dashboard import dashboard_snapshot
from .messages import announcement, explain


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Create exactly one entity per config entry."""
    async_add_entities([AirQualityRecommendation(entry.runtime_data, entry.entry_id)])


class AirQualityRecommendation(SensorEntity):
    """Expose open/close actions and their human-readable justifications."""

    _attr_has_entity_name = True
    _attr_translation_key = "recommendation"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["open", "close", "idle", "blocked"]
    _attr_icon = "mdi:window-open-variant"
    _attr_should_poll = False

    def __init__(self, manager: Any, entry_id: str) -> None:
        self._manager = manager
        self._attr_unique_id = f"{entry_id}_recommendation"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": NAME,
            "manufacturer": "Air Quality Advisor",
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
        return {
            # outdoor_safe means no *known* blockers, not that every selected
            # sensor currently provides a verified air-quality measurement.
            "outdoor_safe": plan.outdoor_safe,
            "outdoor_data_complete": not plan.unavailable_outdoor,
            "unavailable_outdoor_sensors": list(plan.unavailable_outdoor),
            "open_windows": open_ids,
            "close_windows": close_ids,
            "recommendations": actionable,
            "outside_blockers": [explain(reason, language) for reason in plan.outside_reasons],
            "diagnostics": [
                {"area": name, "problem": problem} for name, problem in plan.diagnostics
            ],
            "language": language,
            "announcement_hub_available": self._manager.hub_available,
            "dashboard": dashboard_snapshot(plan, self._manager.thresholds),
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(
            self.hass, f"{SIGNAL_UPDATED}_{self._manager.entry.entry_id}", self._on_update
        ))

    @callback
    def _on_update(self) -> None:
        self.async_write_ha_state()
