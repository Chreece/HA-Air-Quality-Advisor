"""Home language and room policy selectors; never direct equipment modes."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, SIGNAL_UPDATED, LANGUAGES
from .device_controls import (
    climate_settings, pid_settings, tuning_source, update_device_setting,
)
from .area_entities import configured_area_ids

PROFILE_OPTIONS = ("auto", "home", "unoccupied", "away", "sleep")
GAIN_SOURCE_OPTIONS = ("defaults", "manual")


async def async_setup_entry(hass, entry, async_add_entities):
    manager = entry.runtime_data
    entities = [ConfigSelect(manager, entry.entry_id, None, "language",
                             LANGUAGES)]
    for area in configured_area_ids(manager.settings):
        if climate_settings(manager.settings, area) is not None:
            entities.append(ConfigSelect(manager, entry.entry_id, area, "manual_profile",
                                         PROFILE_OPTIONS))
        if pid_settings(manager.settings, area) is not None:
            entities.append(ConfigSelect(manager, entry.entry_id, area, "pid_gain_source",
                                         GAIN_SOURCE_OPTIONS))
    async_add_entities(entities)


class ConfigSelect(SelectEntity):
    """Only supervisor profile/gain-source and language, never native HVAC mode."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, manager, entry_id, area, kind, options):
        self._manager = manager
        self._area_id = area
        self._kind = kind
        self._attr_options = list(options)
        self._attr_unique_id = (
            f"{entry_id}_home_{kind}" if area is None else
            f"{entry_id}_area_{area}_{kind}"
        )
        self._attr_translation_key = (
            f"home_{kind}" if area is None else f"area_{kind}"
        )
        self._attr_device_info = {"identifiers": {
            (DOMAIN, entry_id if area is None else f"{entry_id}_area_{area}")
        }}
        self._attr_icon = (
            "mdi:translate" if area is None else
            "mdi:tune-variant" if kind == "pid_gain_source" else
            "mdi:home-thermometer"
        )

    @property
    def current_option(self):
        settings = self._manager.settings
        if self._kind == "language":
            lang = settings.get("language", "auto")
            return lang if lang in LANGUAGES else "auto"
        if self._kind == "manual_profile":
            config = climate_settings(settings, self._area_id)
            option = config.get("manual_profile", "auto") if config else "auto"
            return option if option in PROFILE_OPTIONS else "auto"
        config = pid_settings(settings, self._area_id)
        return tuning_source(config) if config else "defaults"

    async def async_select_option(self, option: str):
        if option not in self._attr_options:
            raise ValueError("Unknown selectable device option")
        if self._kind == "language":
            await update_device_setting(self._manager, "global_setting", "language", option)
        elif self._kind == "manual_profile":
            await update_device_setting(self._manager, "profile", "manual_profile", option,
                                        area=self._area_id)
        else:
            await update_device_setting(self._manager, "pid_gain_source",
                                        "tuning_source", option, area=self._area_id)
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
