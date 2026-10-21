"""Home language and room policy selectors; never direct equipment modes."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, SIGNAL_UPDATED, LANGUAGES
from .device_controls import (
    climate_settings, pid_settings, tuning_source, update_device_setting,
    CLIMATE_POLICY_OPTIONS, DEVICE_POLICY_OPTIONS, GLOBAL_POLICY_OPTIONS,
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
    entities.extend(
        ConfigSelect(manager, entry.entry_id, None, "global_policy",
                     GLOBAL_POLICY_OPTIONS["home_policy"], setting_key="home_policy")
        for _ in (0,)
    )
    for area in configured_area_ids(manager.settings):
        if climate_settings(manager.settings, area) is None:
            continue
        for key, values in CLIMATE_POLICY_OPTIONS.items():
            entities.append(ConfigSelect(
                manager, entry.entry_id, area, "climate_policy", values, setting_key=key
            ))
        cfg = manager.settings.get("climate_rooms", {}).get(area, {})
        selected = cfg.get("selected_devices", []) if isinstance(cfg, dict) else []
        active = cfg.get("device_settings", {}) if isinstance(cfg, dict) else {}
        for entity_id in selected:
            device = active.get(entity_id) if isinstance(active, dict) else None
            if not isinstance(device, dict) or device.get("auto_control") is not True:
                continue
            for key, choices in DEVICE_POLICY_OPTIONS.items():
                entities.append(ConfigSelect(
                    manager, entry.entry_id, area, "device_policy", choices,
                    setting_key=key, entity_id=entity_id
                ))
    async_add_entities(entities)


class ConfigSelect(SelectEntity):
    """Only supervisor profile/gain-source and language, never native HVAC mode."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, manager, entry_id, area, kind, options, *,
                 setting_key=None, entity_id=None):
        self._manager = manager
        self._area_id = area
        self._kind = kind
        self._setting_key = setting_key or kind
        self._entity_id = entity_id
        self._attr_options = list(options)
        suffix = f"{kind}_{self._setting_key}" if setting_key else kind
        if entity_id:
            suffix = f"{kind}_{entity_id.replace('.', '_')}_{self._setting_key}"
            self._attr_name = f"{entity_id} · {self._setting_key.replace('_', ' ')}"
        else:
            self._attr_translation_key = (
                f"home_{suffix}" if area is None else f"area_{suffix}"
            )
        self._attr_unique_id = (
            f"{entry_id}_home_{suffix}" if area is None else
            f"{entry_id}_area_{area}_{suffix}"
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
        if self._kind == "pid_gain_source":
            config = pid_settings(settings, self._area_id)
            return tuning_source(config) if config else "defaults"
        if self._kind == "global_policy":
            cfg = settings.get("occupancy_global", {})
            return cfg.get(self._setting_key, "any_home") if isinstance(cfg, dict) else "any_home"
        cfg = settings.get("climate_rooms", {}).get(self._area_id, {})
        if self._kind == "device_policy":
            devices = cfg.get("device_settings", {}) if isinstance(cfg, dict) else {}
            dev = devices.get(self._entity_id, {}) if isinstance(devices, dict) else {}
            fallback = "always" if self._setting_key == "presence_requirement" else "normal"
            return dev.get(self._setting_key, fallback) if isinstance(dev, dict) else fallback
        defaults = {
            "unknown_occupancy": "occupied",
            "away_policy": "any_home",
            "target_source": "temperature",
        }
        return cfg.get(self._setting_key, defaults[self._setting_key]) if isinstance(cfg, dict) else defaults[self._setting_key]

    async def async_select_option(self, option: str):
        if option not in self._attr_options:
            raise ValueError("Unknown selectable device option")
        if self._kind == "language":
            await update_device_setting(self._manager, "global_setting", "language", option)
        elif self._kind == "manual_profile":
            await update_device_setting(self._manager, "profile", "manual_profile", option,
                                        area=self._area_id)
        elif self._kind == "pid_gain_source":
            await update_device_setting(self._manager, "pid_gain_source",
                                        "tuning_source", option, area=self._area_id)
        else:
            await update_device_setting(
                self._manager, self._kind, self._setting_key, option,
                area=self._area_id, entity_id=self._entity_id
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
