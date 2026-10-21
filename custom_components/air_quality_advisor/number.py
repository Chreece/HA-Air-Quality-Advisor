"""Home-wide thresholds and room-specific supervisory number controls."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory

from .const import (CONF_REPEAT_MINUTES, DEFAULT_REPEAT_MINUTES,
                    DOMAIN, SIGNAL_UPDATED)
from .device_controls import (
    PID_NUMBERS, PROFILE_NUMBERS, THRESHOLD_NUMBERS,
    pid_settings, climate_settings, update_device_setting,
)
from .climate_strategy import profiles


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    from .area_entities import configured_area_ids

    manager = entry.runtime_data
    numbers = [
        ConfigNumber(manager, entry.entry_id, None, "global_setting",
                     CONF_REPEAT_MINUTES, (0.0, 1440.0, 1.0, "min")),
    ]
    numbers.extend(
        ConfigNumber(manager, entry.entry_id, None, "global_threshold", key, bounds)
        for key, bounds in THRESHOLD_NUMBERS.items()
    )
    for area_id in configured_area_ids(manager.settings):
        if pid_settings(manager.settings, area_id) is not None:
            numbers.extend(
                ConfigNumber(manager, entry.entry_id, area_id, "pid", key, bounds)
                for key, bounds in PID_NUMBERS.items()
            )
        if climate_settings(manager.settings, area_id) is not None:
            numbers.extend(
                ConfigNumber(manager, entry.entry_id, area_id, "climate_profile", key, bounds)
                for key, bounds in PROFILE_NUMBERS.items()
            )
    async_add_entities(numbers)


class ConfigNumber(NumberEntity):
    """Configuration-only setting, not a second physical thermostat entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = "box"

    def __init__(self, manager, entry_id, area_id, kind, key, bounds):
        self._manager = manager
        self._area_id = area_id
        self._kind = kind
        self._key = key
        self._attr_translation_key = (
            f"{kind}_{key}" if area_id is None else
            f"area_{kind}_{key}"
        )
        self._attr_unique_id = (
            f"{entry_id}_home_{kind}_{key}" if area_id is None else
            f"{entry_id}_area_{area_id}_{kind}_{key}"
        )
        self._attr_device_info = {"identifiers": {
            (DOMAIN, entry_id if area_id is None else f"{entry_id}_area_{area_id}")
        }}
        self._attr_native_min_value = bounds[0]
        self._attr_native_max_value = bounds[1]
        self._attr_native_step = bounds[2]
        self._attr_native_unit_of_measurement = bounds[3]

    @property
    def native_value(self):
        settings = self._manager.settings
        if self._kind == "global_threshold":
            return float(self._manager.thresholds[self._key])
        if self._kind == "global_setting":
            return float(settings.get(CONF_REPEAT_MINUTES, DEFAULT_REPEAT_MINUTES))
        if self._kind == "pid":
            config = pid_settings(settings, self._area_id)
            return float(config[self._key]) if config is not None else None
        if self._kind == "climate_profile":
            config = climate_settings(settings, self._area_id)
            if config is None:
                return None
            parsed, problem = profiles(config)
            if problem:
                return None
            group, mode = self._key.rsplit("_", 1)
            return float(getattr(parsed[group], mode + "_c"))
        return None

    async def async_set_native_value(self, value: float) -> None:
        await update_device_setting(
            self._manager, self._kind, self._key, value, area=self._area_id
        )
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(
            self.hass, f"{SIGNAL_UPDATED}_{self._manager.entry.entry_id}",
            self._update,
        ))

    @callback
    def _update(self):
        self.async_write_ha_state()
