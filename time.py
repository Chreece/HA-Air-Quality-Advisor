"""Room sleep schedule as Home Assistant Time entities, not setup questions."""
from __future__ import annotations

from .room_hubs import async_add_grouped_entities

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory

from .device_hierarchy import configured_area_ids
from .const import DOMAIN, SIGNAL_UPDATED
from .device_controls import climate_settings, update_device_setting


async def async_setup_entry(hass, entry, async_add_entities):
    manager = entry.runtime_data
    result = []
    for area in configured_area_ids(manager.settings):
        if climate_settings(manager.settings, area) is None:
            continue
        for key in ("sleep_start", "sleep_end"):
            result.append(AreaScheduleTime(manager, entry.entry_id, area, key))
    async_add_grouped_entities(entry.runtime_data, async_add_entities, result)


class AreaScheduleTime(TimeEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False

    def __init__(self, manager, entry_id, area, key):
        self._manager = manager
        self._area = area
        self._key = key
        self._attr_unique_id = f"{entry_id}_area_{area}_climate_{key}"
        self._attr_translation_key = f"area_climate_{key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, f"{entry_id}_area_{area}")}}

    @property
    def native_value(self) -> time | None:
        config = climate_settings(self._manager.settings, self._area)
        value = (config or {}).get(self._key, "22:00" if self._key=="sleep_start" else "07:00")
        try:
            return time.fromisoformat(str(value))
        except ValueError:
            return None

    async def async_set_value(self, value: time):
        await update_device_setting(
            self._manager, "climate_schedule", self._key, value, area=self._area
        )
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(
            self.hass, f"{SIGNAL_UPDATED}_{self._manager.entry.entry_id}",
            self._update,
        ))

    @callback
    def _update(self):
        self.async_write_ha_state()
