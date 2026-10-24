"""Home-wide thresholds and room-specific supervisory number controls."""
from __future__ import annotations

from .room_hubs import async_add_grouped_entities

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory

from .const import (CONF_REPEAT_MINUTES, DEFAULT_REPEAT_MINUTES,
                    CONF_USE_MOLD, CONF_AREAS, CONF_MOLD_ROOMS,
                    DOMAIN, SIGNAL_UPDATED)
from .device_hierarchy import controller_device_info
from .device_controls import (
    PID_NUMBERS, PROFILE_NUMBERS, PROFILE_DEFAULTS, THRESHOLD_NUMBERS,
    GLOBAL_ENV_NUMBERS, GLOBAL_OCCUPANCY_NUMBERS,
    AREA_ENV_NUMBERS, CLIMATE_OPERATING_NUMBERS, DIRECT_CONTROLLER_NUMBERS,
    DEVICE_TARGET_NUMBERS,
    pid_settings, climate_settings, room_profile_number_fields,
    update_device_setting, configured_aqi_entities,
)
from .climate_strategy import profiles


def _registered_number(registry, unique_id: str) -> bool:
    """An exposed number must survive a temporarily missing native HA state."""
    lookup = getattr(registry, "async_get_entity_id", None)
    return bool(lookup and lookup("number", DOMAIN, unique_id))


def _profile_fields(manager, entry_id: str, area_id: str, registry) -> tuple[str, ...]:
    """Keep previously exposed room targets, even if source HVAC is starting.

    Never create fictional targets for a truly unconfigured room. Freshly
    discovered capabilities are added immediately; prior supported targets
    retain their stable unique IDs while native equipment is unavailable.
    """
    from . import equipment_model as equipment

    current = room_profile_number_fields(manager, area_id)
    selected = tuple(
        spec for spec in equipment.specs(manager) if spec.area_id == area_id
    )
    if not selected or all(
        equipment.capabilities(manager, spec) is not None for spec in selected
    ):
        return current
    existing = (
        key for key in PROFILE_NUMBERS
        if _registered_number(
            registry, f"{entry_id}_area_{area_id}_climate_profile_{key}"
        )
    )
    return tuple(dict.fromkeys((*current, *existing)))


def _equipment_numbers(manager, spec, registry) -> tuple["EquipmentNumber", ...]:
    """Keep controller configuration available without native HVAC readiness.

    The old capability gate removed *all* Kp/Kd/timing entities when the
    physical thermostat was unavailable during setup. Those numbers describe
    stored policy, not live measurements, and must not depend on hardware.
    """
    from . import equipment_model as equipment

    cap = equipment.capabilities(manager, spec)
    saved_mode = equipment.settings(manager, spec).get("control_mode")
    keys: list[str] = []
    for key in (*equipment.NUMBER_FIELDS, *equipment.PID_MODEL_FIELDS,
                *equipment.PID_FAN_CAPACITY_FIELDS):
        if cap is not None:
            if key in equipment.PID_FAN_CAPACITY_FIELDS:
                if (cap.domain not in ("climate", "humidifier")
                        or not cap.fan_modes
                        or "pid" not in equipment.control_modes(manager, spec)):
                    continue
                from .pid_fan_capacity import ordered_fan_stages, PERCENT_POINT_FIELDS
                if cap.fan_percentage and key.startswith("pid_capacity_stage_"):
                    continue
                if not cap.fan_percentage and key.startswith((
                    "pid_capacity_speed_", "pid_capacity_output_"
                )):
                    continue
                if key.startswith("pid_capacity_stage_"):
                    stages = ordered_fan_stages(cap.fan_modes)
                    index = int(key.rsplit("_", 1)[-1])
                    if not stages or index >= len(stages):
                        continue
            if key == "quiet_percentage" and not cap.fan_percentage:
                continue
            if key in equipment.POWER_FIELDS and cap.domain not in ("climate", "fan", "humidifier"):
                continue
            if (key in equipment.PID_MODEL_FIELDS
                    and "pid" not in equipment.control_modes(manager, spec)):
                continue
            if (key not in equipment.PID_MODEL_FIELDS
                    and key not in equipment.PID_FAN_CAPACITY_FIELDS
                    and key != "quiet_percentage" and key not in equipment.POWER_FIELDS
                    and "pid" not in equipment.control_modes(manager, spec)):
                continue
        else:
            # A managed physical native endpoint remains a managed controller
            # even when HA has not restored its state or advertised features.
            if not any(entity.partition(".")[0] in ("climate", "fan", "humidifier")
                       for entity in spec.source_entities):
                continue
            if key in equipment.PID_FAN_CAPACITY_FIELDS:
                if not _registered_number(registry, f"{spec.identifier}_{key}"):
                    continue
            elif key == "quiet_percentage":
                if not _registered_number(registry, f"{spec.identifier}_{key}"):
                    continue
            elif key not in equipment.POWER_FIELDS:
                if saved_mode != "pid" and not _registered_number(
                    registry, f"{spec.identifier}_{key}"
                ):
                    continue
        keys.append(key)
    return tuple(EquipmentNumber(manager, spec, key) for key in keys)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    from .device_hierarchy import configured_area_ids

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
    for entity_id in configured_aqi_entities(manager):
        numbers.append(ConfigNumber(
            manager, entry.entry_id, None, "aqi_limit",
            "custom_limit", (0.0, 10000.0, 1.0, None),
            entity_id=entity_id,
        ))
    from . import equipment_model as equipment
    # Query the registry before constructing number entities; offline source
    # recovery needs this same registry even when old-entity cleanup is skipped.
    from homeassistant.helpers import entity_registry as er
    registry = er.async_get(hass)
    # Beta17 briefly exposed room-wide limits on each physical controller.
    # Remove only those obsolete registry entities; their stored config values
    # remain available to equipment_model's conservative room migration.
    try:
        getter = getattr(registry, "async_get_entity_id", None)
        remover = getattr(registry, "async_remove", None)
        if getter is not None and remover is not None:
            for spec in equipment.specs(manager):
                for key in equipment.LIMIT_FIELDS:
                    if entity_id := getter("number", DOMAIN, f"{spec.identifier}_{key}"):
                        remover(entity_id)
    except (AttributeError, RuntimeError):
        pass

    for area_id in configured_area_ids(manager.settings):
        for key in equipment.available_room_limit_fields(manager, area_id):
            bounds = equipment.room_limit_bounds(manager, area_id, key)
            if bounds is not None:
                numbers.append(ConfigNumber(
                    manager, entry.entry_id, area_id, "room_equipment_limit", key, bounds,
                ))
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
        profile_fields = _profile_fields(manager, entry.entry_id, area_id, registry)
        numbers.extend(
            ConfigNumber(
                manager, entry.entry_id, area_id, "climate_profile",
                key, PROFILE_NUMBERS[key],
            )
            for key in profile_fields
        )
        if climate_settings(manager.settings, area_id) is not None:
            numbers.extend(
                ConfigNumber(manager, entry.entry_id, area_id, "climate_operating", key, bounds[:4])
                for key, bounds in CLIMATE_OPERATING_NUMBERS.items()
            )
            cfg = manager.settings.get("climate_rooms", {}).get(area_id, {})
            if isinstance(cfg, dict) and cfg.get("controller") in ("pwm", "proportional"):
                for key, bounds in DIRECT_CONTROLLER_NUMBERS.items():
                    if (cfg["controller"] == "pwm" and
                            key in ("max_demand_change", "min_demand_change")):
                        continue
                    numbers.append(ConfigNumber(
                        manager, entry.entry_id, area_id, "direct_tuning",
                        key, bounds[:4],
                    ))
            active = cfg.get("device_settings", {}) if isinstance(cfg, dict) else {}
            active = active if isinstance(active, dict) else {}
            selected = cfg.get("selected_devices", []) if isinstance(cfg, dict) else []
            for entity_id in selected:
                if controller_device_info(manager, area_id, entity_id) is None:
                    continue
                device_cfg = active.get(entity_id)
                if not isinstance(device_cfg, dict) or device_cfg.get("auto_control") is not True:
                    continue
                prefix = entity_id.split(".", 1)[0]
                if prefix == "climate":
                    chosen = []
                elif prefix == "humidifier":
                    # Humidity operating targets are room/profile-owned.
                    chosen = []
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
    for spec in equipment.specs(manager):
        numbers.extend(_equipment_numbers(manager, spec, registry))
    async_add_grouped_entities(entry.runtime_data, async_add_entities, numbers)

    # Home Assistant restores physical devices asynchronously. If its source
    # state arrives *after* this platform setup, register newly supported room
    # targets and device tuning without requiring another HA restart. Existing
    # entity IDs and unique IDs are never removed or recreated unnecessarily.
    added = {item.unique_id for item in numbers}
    watched = {
        entity_id for spec in equipment.specs(manager)
        for entity_id in spec.source_entities
    }

    if watched:
        from homeassistant.const import EVENT_STATE_CHANGED

        @callback
        def _source_updated(event) -> None:
            if event.data.get("entity_id") not in watched:
                return
            recovered = []
            for area_id in configured_area_ids(manager.settings):
                for key in _profile_fields(
                    manager, entry.entry_id, area_id, registry
                ):
                    candidate = ConfigNumber(
                        manager, entry.entry_id, area_id, "climate_profile",
                        key, PROFILE_NUMBERS[key],
                    )
                    if candidate.unique_id not in added:
                        recovered.append(candidate)
            for spec in equipment.specs(manager):
                recovered.extend(
                    candidate for candidate in _equipment_numbers(
                        manager, spec, registry
                    )
                    if candidate.unique_id not in added
                )
            if not recovered:
                return
            # Prevent a duplicate add when several native attributes arrive
            # in the same HA event loop iteration.
            unique = {item.unique_id: item for item in recovered}
            added.update(unique)
            async_add_grouped_entities(
                manager, async_add_entities, unique.values()
            )

        entry.async_on_unload(
            hass.bus.async_listen(EVENT_STATE_CHANGED, _source_updated)
        )


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
        # Older room-level PID numbers are also sorted by friendly name;
        # avoid Home Assistant prefixing the room/device before "PID".
        if kind in ("pid", "direct_tuning"):
            self._attr_has_entity_name = False
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
            f"{entry_id}_home_{kind}_"
            f"{entity_id.replace('.', '_') + '_' if entity_id else ''}{key}"
            if area_id is None else
            f"{entry_id}_area_{area_id}_{kind}_"
            f"{entity_id.replace('.', '_') + '_' if entity_id else ''}{key}"
        )
        self._attr_device_info = {"identifiers": {
            (DOMAIN, entry_id if area_id is None else f"{entry_id}_area_{area_id}")
        }}
        if kind == "device_target" and entity_id:
            child = controller_device_info(manager, area_id, entity_id)
            if child is None:
                raise ValueError("Controller source is not registered in this area hub")
            self._attr_device_info = child
        self._attr_native_min_value = bounds[0]
        self._attr_native_max_value = bounds[1]
        self._attr_native_step = bounds[2]
        self._attr_native_unit_of_measurement = bounds[3]

    @property
    def native_value(self):
        settings = self._manager.settings
        if self._kind == "aqi_limit":
            env = settings.get("environment_global", {})
            scales = env.get("aqi_scales", {}) if isinstance(env, dict) else {}
            cfg = scales.get(self._entity_id, {}) if isinstance(scales, dict) else {}
            return float(cfg.get("custom_limit", 100)) if isinstance(cfg, dict) else 100.0
        if self._kind in ("global_environment", "global_occupancy"):
            section, bounds = (
                ("environment_global", GLOBAL_ENV_NUMBERS) if self._kind == "global_environment"
                else ("occupancy_global", GLOBAL_OCCUPANCY_NUMBERS)
            )
            cfg = settings.get(section, {})
            cfg = cfg if isinstance(cfg, dict) else {}
            raw = cfg.get(self._key, bounds[self._key][4])
            return float(raw) if raw is not None else None
        if self._kind == "room_equipment_limit":
            from . import equipment_model as equipment
            return equipment.room_limit_values(self._manager, self._area_id).get(self._key)
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
        if self._kind == "direct_tuning":
            rooms = settings.get("climate_rooms", {})
            cfg = rooms.get(self._area_id, {}) if isinstance(rooms, dict) else {}
            raw = cfg.get(self._key, DIRECT_CONTROLLER_NUMBERS[self._key][4])
            return float(raw) if raw is not None else None
        if self._kind == "device_target":
            rooms = settings.get("climate_rooms", {})
            cfg = rooms.get(self._area_id, {}) if isinstance(rooms, dict) else {}
            device_settings = cfg.get("device_settings", {}) if isinstance(cfg, dict) else {}
            dev = device_settings.get(self._entity_id, {}) if isinstance(device_settings, dict) else {}
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
            rooms = settings.get("climate_rooms", {})
            config = rooms.get(self._area_id, {}) if isinstance(rooms, dict) else {}
            config = config if isinstance(config, dict) else {}
            group, mode = self._key.rsplit("_", 1)
            if group not in PROFILE_DEFAULTS:
                return None
            if mode == "humidity":
                raw = config.get("profiles", {})
                raw = raw if isinstance(raw, dict) else {}
                band = raw.get(group, {})
                band = band if isinstance(band, dict) else {}
                legacy = config.get(
                    "sleep_humidity_target" if group == "sleep" else "humidity_target"
                )
                value = band.get(
                    "humidity",
                    legacy if legacy is not None else PROFILE_DEFAULTS[group]["humidity"],
                )
                try:
                    return float(value)
                except (TypeError, ValueError, OverflowError):
                    return None
            parsed, problem = profiles(config)
            if problem:
                return None
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


from .equipment_entity import EquipmentEntity
from . import equipment_model as equipment


class EquipmentNumber(EquipmentEntity, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(self, manager, spec, key):
        self._equipment_init(manager, spec, key)
        cap = equipment.capabilities(manager, spec)
        if key in equipment.PID_FAN_CAPACITY_FIELDS:
            bounds = equipment.PID_FAN_CAPACITY_FIELDS[key]
        elif key in equipment.PID_MODEL_FIELDS:
            # 0 is a deliberate "not yet identified" sentinel, never
            # interpreted as a measured plant model by the calibration code.
            low, high, step, unit = equipment.PID_MODEL_FIELDS[key]
            bounds = (0.0, high, step, unit)
        elif cap is None:
            bounds = equipment.NUMBER_FIELDS[key][:4]
        else:
            bounds = equipment.number_bounds(cap, key)
        self._attr_native_min_value, self._attr_native_max_value = bounds[:2]
        self._attr_native_step, self._attr_native_unit_of_measurement = bounds[2:4]
        if key == "quiet_percentage" and cap and cap.fan_percentage:
            fan_bounds = equipment.number_bounds(cap, "fan_min_percentage")
            self._attr_native_min_value, self._attr_native_max_value = fan_bounds[:2]
            self._attr_native_step = fan_bounds[2]
        if key in ("min_on_seconds", "min_off_seconds") and cap and cap.domain != "fan":
            self._attr_native_min_value = 600
        if key == "max_on_seconds" and cap and cap.domain != "fan":
            self._attr_native_max_value = 28800

    @property
    def available(self):
        if self._key in equipment.PID_FAN_CAPACITY_FIELDS:
            cap = equipment.capabilities(self._manager, self._spec)
            return bool(self.controller_settings["control_mode"] == "pid"
                        and cap and cap.fan_modes
                        and cap.domain in ("climate", "humidifier"))
        if self._key in equipment.PID_MODEL_FIELDS:
            settings = self.controller_settings
            return (settings["control_mode"] == "pid"
                    and settings["pid_calibration_method"] != "manual")
        return super().available

    @property
    def extra_state_attributes(self):
        attributes = super().extra_state_attributes
        if self._key in equipment.PID_FAN_CAPACITY_FIELDS:
            return {**attributes, "pid_fan_capacity_field": self._key}
        if self._key in equipment.PID_MODEL_FIELDS:
            return {**attributes, "pid_calibration_field": self._key}
        return attributes

    @property
    def native_value(self):
        return self.controller_settings[self._key]

    async def async_set_native_value(self, value):
        await self._manager.equipment.async_update(self._spec, {self._key: value})
