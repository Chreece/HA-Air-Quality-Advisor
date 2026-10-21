"""Home-wide opt-in announcement switches on the home device."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory

from .const import (
    CONF_AUTO_NOTIFY, CONF_AUTO_TTS, DOMAIN, SIGNAL_UPDATED,
)
from .device_controls import update_device_setting

CONTROLS = (CONF_AUTO_NOTIFY, CONF_AUTO_TTS)


async def async_setup_entry(hass, entry, async_add_entities):
    manager = entry.runtime_data
    async_add_entities([
        HomeSettingSwitch(manager, entry.entry_id, key) for key in CONTROLS
    ])


class HomeSettingSwitch(SwitchEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, manager, entry_id, key):
        self._manager = manager
        self._key = key
        self._attr_unique_id = f"{entry_id}_home_{key}"
        self._attr_translation_key = f"home_{key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry_id)}}
        self._attr_icon = (
            "mdi:message-badge-outline" if key == CONF_AUTO_NOTIFY
            else "mdi:account-voice"
        )

    @property
    def is_on(self):
        return self._manager.settings.get(self._key, False) is True

    async def async_turn_on(self, **kwargs):
        await update_device_setting(self._manager, "global_setting", self._key, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        await update_device_setting(self._manager, "global_setting", self._key, False)
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
