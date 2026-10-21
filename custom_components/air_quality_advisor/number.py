"""Home-wide thresholds and room-specific supervisory number controls."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory

from .const import (CONF_REPEAT_MINUTES, DEFAULT_REPEAT_MINUTES,
                    CONF_USE_MOLD, CONF_AREAS, CONF_MOLD_ROOMS,
                    DOMAIN, SIGNAL_UPDATED)
from .device_controls import (
    PID_NUMBERS, PROFILE_NUMBERS, THRESHOLD_NUMBERS,
    GLOBAL_ENV_NUMBERS, GLOBAL_OCCUPANCY_NUMBERS,
    AREA_ENV_NUMBERS, CLIMATE_OPERATING_NUMBERS, DEVICE_TARGET_NUMBERS,
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
    for kind, fields in (
        ("global_environment", GLOBAL_ENV_NUMBERS),
        ("global_occupancy", GLOBAL_OCCUPANCY_NUMBERS),
    ):
        numbers.extend(
            ConfigNumber(manager, entry.entry_id, None, kind, key, bounds[:4])
            for key, bounds in fields.items()
        )
    for area_id in configured_area_ids(manager.settings):
        if pid_settings(manager.settings, area_id) is not None:
            numbers.extend(
                ConfigNumber(manager, entry.entry_id, area_id, "pid", key, bounds)
                for key, bounds in PID_NUMBERS.items()
            )
        if area_id in manager.settings.get(CONF_AREAS, []):
            numbers.extend(
                ConfigNumber(manager, entry.entry_id, area_id, "area_environment", key, bounds[:4])
                for key, bounds in AREA_ENV_NUMBERS.items()
            )
        if climate_settings(manager.settings, area_id) is not None:
            numbers.extend(
                ConfigNumber(manager, entry.entry_id, area_id, "climate_profile", key, bounds)
                for key, bounds in PROFILE_NUMBERS.items()
            )
            numbers.extend(
                ConfigNumber(manager, entry.entry_id, area_id, "climate_operating", key, bounds[:4])
                for key, bounds in CLIMATE_OPERATING_NUMBERS.items()
            )
            cfg = manager.settings.get("climate_rooms", {}).get(area_id, {})
            active = cfg.get("device_settings", {}) if isinstance(cfg, dict) else {}
            active = active if isinstance(active, dict) else {}
            selected = cfg.get("selected_devices", []) if isinstance(cfg, dict) else []
            for entity_id in selected:
                device_cfg = active.get(entity_id)
                if not isinstance(device_cfg, dict) or device_cfg.get("auto_control") is not True:
                    continue
                prefix = entity_id.split(".", 1)[0]
                if prefix == "climate":
                    chosen = [key for key in DEVICE_TARGET_NUMBERS if key.endswith(("_heat_c", "_cool_c"))]
                elif prefix == "humidifier":
                    chosen = ["humidity_target", "sleep_humidity_target"]
                elif prefix == "fan":
                    chosen = ["fan_speed_percent"]
                else:
                    continue
                numbers.extend(
                    ConfigNumber(
                        manager, entry.entry_id, area_id, "device_target",
                        key, DEVICE_TARGET_NUMBERS[key][:4],
                        entity_id=entity_id,
                    )
                    for key in chosen
                )
    if manager.settings.get(CONF_USE_MOLD) is True:
        for area_id in manager.settings.get(CONF_AREAS, []):
            numbers.append(ConfigNumber(
                manager, entry.entry_id, area_id, "mold_surface",
                "critical_temperature_c", (-60.0, 85.0, 0.1, "°C"),
            ))
    async_add_entities(numbers)


class ConfigNumber(NumberEntity):
    """Configuration-only setting, not a second physical thermostat entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(self, manager, entry_id, area_id, kind, key, bounds, *, entity_id=None):
        self._manager = manager
        self._area_id = area_id
        self._kind = kind
        self._key = key
        self._entity_id = entity_id
        if entity_id:
            self._attr_name = f"{entity_id} · {key.replace('_', ' ')}"
        else:
            self._attr_translation_key = (
                f"{kind}_{key}" if area_id is None else
                f"area_{kind}_{key}"
            )
        # Unique per source device, even when two physical thermostats share
        # the same room and expose corresponding profile settings.
        self._attr_unique_id = (
            f"{entry_id}_home_{kind}_{key}" if area_id is None else
            f"{entry_id}_area_{area_id}_{kind}_"
            f"{entity_id.replace('.', '_') + '_' if entity_id else ''}{key}"
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
        if self._kind in ("global_environment", "global_occupancy"):
            section, bounds = (
                ("environment_global", GLOBAL_ENV_NUMBERS) if self._kind == "global_environment"
                else ("occupancy_global", GLOBAL_OCCUPANCY_NUMBERS)
            )
            cfg = settings.get(section, {})
            cfg = cfg if isinstance(cfg, dict) else {}
            raw = cfg.get(self._key, bounds[self._key][4])
            return float(raw) if raw is not None else None
        if self._kind in ("area_environment", "climate_operating"):
            section, bounds = (
                ("environment_rooms", AREA_ENV_NUMBERS) if self._kind == "area_environment"
                else ("climate_rooms", CLIMATE_OPERATING_NUMBERS)
            )
            rooms = settings.get(section, {})
            cfg = rooms.get(self._area_id, {}) if isinstance(rooms, dict) else {}
            cfg = cfg if isinstance(cfg, dict) else {}
            raw = cfg.get(self._key, bounds[self._key][4])
            return float(raw) if raw is not None else None
        if self._kind == "device_target":
            rooms = settings.get("climate_rooms", {})
            cfg = rooms.get(self._area_id, {}) if isinstance(rooms, dict) else {}
            profiles = cfg.get("device_settings", {}) if isinstance(cfg, dict) else {}
            dev = profiles.get(self._entity_id, {}) if isinstance(profiles, dict) else {}
            raw = dev.get(self._key, DEVICE_TARGET_NUMBERS[self._key][4])
            return float(raw) if raw is not None else None
        if self._kind == "global_threshold":
            return float(self._manager.thresholds[self._key])
        if self._kind == "global_setting":
            return float(settings.get(CONF_REPEAT_MINUTES, DEFAULT_REPEAT_MINUTES))
        if self._kind == "mold_surface":
            rooms = settings.get(CONF_MOLD_ROOMS, {})
            config = rooms.get(self._area_id, {}) if isinstance(rooms, dict) else {}
            raw = config.get(self._key) if isinstance(config, dict) else None
            return float(raw) if raw is not None else None
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
        if self._kind == "mold_surface":
            from .mold_controls import async_set_surface_temperature
            await async_set_surface_temperature(self._manager, self._area_id, value)
        else:
            await update_device_setting(
                self._manager, self._kind, self._key, value, area=self._area_id,
                entity_id=self._entity_id
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
