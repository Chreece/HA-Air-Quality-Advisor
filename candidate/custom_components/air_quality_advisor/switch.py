"""Home-wide opt-in announcement switches on the home device."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory

from .const import (
    CONF_AUTO_NOTIFY, CONF_AUTO_TTS, CONF_HUB, CONF_AI_REWRITE, DOMAIN, SIGNAL_UPDATED,
)
from .device_controls import update_device_setting

CONTROLS = (CONF_AUTO_NOTIFY, CONF_AUTO_TTS, CONF_HUB, CONF_AI_REWRITE)


async def async_setup_entry(hass, entry, async_add_entities):
    manager = entry.runtime_data
    from .device_hierarchy import configured_area_ids
    from .device_controls import AREA_ENV_FLAGS, CLIMATE_OPERATING_FLAGS, GLOBAL_ENV_FLAGS
    from .const import CONF_AREAS
    from .device_controls import climate_settings
    entities = [HomeSettingSwitch(manager, entry.entry_id, key) for key in CONTROLS]
    entities.extend(
        HomeSettingSwitch(manager, entry.entry_id, key, kind="global_environment")
        for key in GLOBAL_ENV_FLAGS
    )
    for area in configured_area_ids(manager.settings):
        if area in manager.settings.get(CONF_AREAS, []):
            entities.extend(HomeSettingSwitch(
                manager, entry.entry_id, key, kind="area_environment", area=area,
            ) for key in AREA_ENV_FLAGS)
        if climate_settings(manager.settings, area) is not None:
            entities.extend(HomeSettingSwitch(
                manager, entry.entry_id, key, kind="climate_operating", area=area,
            ) for key in CLIMATE_OPERATING_FLAGS)
    from . import equipment_model as equipment
    entities.extend(EquipmentQuietSwitch(manager, spec, key)
                    for spec in equipment.specs(manager)
                    if (cap := equipment.capabilities(manager, spec)) is not None and cap.fan_modes
                    for key in equipment.QUIET_FLAGS)
    async_add_entities(entities)


class HomeSettingSwitch(SwitchEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, manager, entry_id, key, *, kind="global_setting", area=None):
        self._manager = manager
        self._key = key
        self._kind = kind
        self._area = area
        self._attr_unique_id = (
            f"{entry_id}_area_{area}_{kind}_{key}" if area else
            f"{entry_id}_home_{kind}_{key}" if kind != "global_setting" else
            f"{entry_id}_home_{key}"
        )
        self._attr_translation_key = (
            f"area_{kind}_{key}" if area else
            f"home_{kind}_{key}" if kind != "global_setting" else f"home_{key}"
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_area_{area}" if area else entry_id)}
        }
        self._attr_icon = {
            CONF_AUTO_NOTIFY: "mdi:message-badge-outline",
            CONF_AUTO_TTS: "mdi:account-voice",
            CONF_HUB: "mdi:home-assistant",
            CONF_AI_REWRITE: "mdi:robot-outline",
            "pollen_avoid_ventilation": "mdi:flower-pollen",
            "sleep_room": "mdi:bed",
            "enable_pmv": "mdi:human-male-board-poll",
            "sleep_active": "mdi:sleep",
            "sleep_schedule_enabled": "mdi:clock-check-outline",
            "window_efficiency_notify": "mdi:window-open-variant",
        }.get(key, "mdi:cog")

    @property
    def is_on(self):
        settings = self._manager.settings
        if self._kind == "global_setting":
            return settings.get(self._key, False) is True
        section = "environment_global" if self._kind == "global_environment" else (
            "environment_rooms" if self._kind == "area_environment" else "climate_rooms"
        )
        cfg = settings.get(section, {})
        if self._area:
            cfg = cfg.get(self._area, {}) if isinstance(cfg, dict) else {}
        return isinstance(cfg, dict) and cfg.get(self._key, False) is True

    async def async_turn_on(self, **kwargs):
        await update_device_setting(self._manager, self._kind, self._key, True, area=self._area)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        await update_device_setting(self._manager, self._kind, self._key, False, area=self._area)
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


from .equipment_entity import EquipmentEntity


class EquipmentQuietSwitch(EquipmentEntity, SwitchEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:fan-speed-1"

    def __init__(self, manager, spec, key):
        self._equipment_init(manager, spec, key)

    @property
    def is_on(self):
        return self.controller_settings[self._key] is True

    async def async_turn_on(self, **kwargs):
        await self._manager.equipment.async_update(self._spec, {self._key: True})

    async def async_turn_off(self, **kwargs):
        await self._manager.equipment.async_update(self._spec, {self._key: False})
