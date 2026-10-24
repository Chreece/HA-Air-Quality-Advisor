"""Native HA climate interface for each Manager equipment controller.

Standalone fans/humidity units retain their native source entities. Their
Manager climate interface advertises only FAN_ONLY/DRY/AUTO as appropriate,
not fictional heating/cooling or temperature targets.
"""
from __future__ import annotations

from .room_hubs import async_add_grouped_entities

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode, HVACAction
from homeassistant.const import UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError

from .equipment_entity import EquipmentEntity
from . import equipment_model as model
from .pid_math import finite, target_from_unit

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    manager = entry.runtime_data
    async_add_grouped_entities(entry.runtime_data, async_add_entities, [ManagedClimate(manager, spec) for spec in model.specs(manager)])


class ManagedClimate(EquipmentEntity, ClimateEntity):
    """Room measurements, native capabilities and Manager-controlled presets."""

    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_temperature_unit = UnitOfTemperature.CELSIUS  # HA 2026.10 compatibility.
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, manager, spec):
        self._equipment_init(manager, spec, "climate")

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self._watch_native_updates()

    @property
    def _caps(self):
        return model.capabilities(self._manager, self._spec)

    @property
    def _state(self):
        cap = self._caps
        return self._manager.hass.states.get(cap.primary) if cap else None

    @property
    def available(self):
        state = self._state
        return state is not None and state.state not in ("unknown", "unavailable") and self._manager.equipment._current_spec(self._spec)

    @property
    def hvac_modes(self):
        return [HVACMode(v) for v in self._caps.modes] if self._caps else []

    @property
    def _physical_hvac_mode(self):
        """Observed native output, not the independently selected controller mode."""
        cap, state = self._caps, self._state
        if cap is None or state is None or state.state in ("unknown", "unavailable"):
            return None
        if cap.domain == "climate":
            return HVACMode(state.state) if state.state in cap.modes else None
        if cap.domain in ("number", "input_number"):
            value = finite(state.state, 0, 100)
            if value is None:
                return None
            return HVACMode.OFF if value == 0 else HVACMode(
                next(v for v in cap.modes if v != "off")
            )
        return HVACMode.OFF if state.state == "off" else HVACMode(
            next(v for v in cap.modes if v != "off")
        )

    @property
    def hvac_mode(self):
        """Supervisory intent: an idle thermostat remains armed, not OFF.

        HA's climate state denotes the selected controller mode. It must not
        mirror native appliance OFF during hysteresis, a PID OFF interval or
        a minimum-off safety hold. Only the existing/native passthrough mode
        deliberately mirrors physical hardware.

        Never invent heat/cool/dry capabilities: selected and evaluated modes
        must belong to this exact physical endpoint's advertised modes.
        """
        cap = self._caps
        if cap is None or not self.available:
            return None
        settings = self.controller_settings
        method = settings["control_mode"]
        native_mode = self._physical_hvac_mode
        if method == "existing":
            return native_mode
        if method == "off":
            return HVACMode.OFF

        requested = settings.get("requested_mode")
        status = self._manager.equipment.statuses.get(self._spec.identifier, {})
        evaluated = status.get("mode") if isinstance(status, dict) else None
        # Automatic is selected from measured needs by the active controller;
        # PID preserves an explicit single-direction selection when supplied.
        if method in ("automatic", "pid") and evaluated in cap.modes and evaluated != "off":
            return HVACMode(evaluated)
        if method in ("manual", "pid", "automatic") and requested in cap.modes and requested != "off":
            return HVACMode(requested)
        if native_mode is not None and native_mode != HVACMode.OFF:
            return native_mode
        active = [mode for mode in cap.modes if mode != "off"]
        if method in ("automatic", "pid") and len(active) == 1:
            return HVACMode(active[0])
        # A multichannel device with no selected/evaluated direction cannot
        # claim to be heating/cooling while the direction is still unknown.
        return HVACMode.OFF

    @property
    def hvac_action(self):
        state, cap = self._state, self._caps
        if state is None or cap is None or state.state in ("unknown", "unavailable"):
            return None
        selected = self.hvac_mode
        if selected is None:
            return None
        if selected == HVACMode.OFF:
            return HVACAction.OFF
        # Logical controller remains armed while the physical output is OFF:
        # HA climate must show IDLE, not OFF or fictitious heating/drying.
        if self._physical_hvac_mode == HVACMode.OFF:
            return HVACAction.IDLE
        if cap.domain == "climate":
            value = state.attributes.get("hvac_action")
            return HVACAction(value) if value in {item.value for item in HVACAction} else None
        if cap.domain == "fan":
            return HVACAction.FAN
        # Native humidifiers/dehumidifiers do not expose a reliable HVACAction.
        # Never turn an observed ON state into fabricated DRYING/HEATING.
        return None

    @property
    def supported_features(self):
        cap = self._caps
        if cap is None:
            return ClimateEntityFeature(0)
        result = ClimateEntityFeature.PRESET_MODE
        for allowed, feature in ((cap.temperature, ClimateEntityFeature.TARGET_TEMPERATURE),
                                 (cap.temperature_range, ClimateEntityFeature.TARGET_TEMPERATURE_RANGE),
                                 (cap.humidity, ClimateEntityFeature.TARGET_HUMIDITY),
                                 (bool(cap.fan_modes), ClimateEntityFeature.FAN_MODE),
                                 (bool(cap.swing_modes), ClimateEntityFeature.SWING_MODE),
                                 (bool(cap.swing_horizontal_modes), ClimateEntityFeature.SWING_HORIZONTAL_MODE)):
            if allowed:
                result |= feature
        if "off" in cap.modes:
            result |= ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
        return result

    @property
    def native_current_temperature(self):
        cap = self._caps
        return self._manager.equipment.measurements(self._spec, cap)["temperature"] if cap else None

    current_temperature = property(lambda self: self.native_current_temperature)

    @property
    def current_humidity(self):
        cap = self._caps
        return self._manager.equipment.measurements(self._spec, cap)["humidity"] if cap else None

    def _target(self, kind):
        cap, state = self._caps, self._state
        if cap is None:
            return None
        cfg = self.controller_settings
        manual_native = (cfg["control_mode"] == "manual" and cfg["preset"] == "none"
                         and kind not in cfg.get("profile_targets", {}).get("manual", {}))
        if cfg["control_mode"] == "existing" or manual_native:
            key = {"heat": "target_temp_low", "cool": "target_temp_high", "humidity": "humidity"}[kind]
            value = state.attributes.get(key)
            if value is None and kind != "humidity":
                value = state.attributes.get("temperature")
            return finite(value, 0, 100) if kind == "humidity" else target_from_unit(value, state.attributes.get("temperature_unit", "°C"))
        values = model.targets(self._manager, self._spec, cap, self.controller_settings, model.plan_for(self._manager, self._spec))
        return values[kind]

    @property
    def native_target_temperature(self):
        cap = self._caps
        if cap is None or not cap.temperature:
            return None
        mode = self.controller_settings.get("requested_mode") or self.hvac_mode
        return self._target("cool" if mode == "cool" else "heat")

    target_temperature = property(lambda self: self.native_target_temperature)
    native_target_temperature_low = property(lambda self: self._target("heat") if self._caps and self._caps.temperature_range else None)
    native_target_temperature_high = property(lambda self: self._target("cool") if self._caps and self._caps.temperature_range else None)
    target_temperature_low = property(lambda self: self.native_target_temperature_low)
    target_temperature_high = property(lambda self: self.native_target_temperature_high)
    target_humidity = property(lambda self: self._target("humidity") if self._caps and self._caps.humidity else None)
    @property
    def min_temp(self):
        cap = self._caps
        return model.device_limits(self._manager, self._spec, cap)["temperature_min_limit"] if cap else 5

    @property
    def max_temp(self):
        cap = self._caps
        return model.device_limits(self._manager, self._spec, cap)["temperature_max_limit"] if cap else 35

    target_temperature_step = property(lambda self: self._caps.temp_step if self._caps else .5)

    @property
    def min_humidity(self):
        cap = self._caps
        return model.device_limits(self._manager, self._spec, cap)["humidity_min_limit"] if cap else 20

    @property
    def max_humidity(self):
        cap = self._caps
        return model.device_limits(self._manager, self._spec, cap)["humidity_max_limit"] if cap else 80
    preset_modes = property(lambda self: list(model.PRESETS))
    preset_mode = property(lambda self: self.controller_settings["preset"])
    fan_modes = property(lambda self: list(self._caps.fan_modes) if self._caps else [])
    swing_modes = property(lambda self: list(self._caps.swing_modes) if self._caps else [])
    swing_horizontal_modes = property(lambda self: list(self._caps.swing_horizontal_modes) if self._caps else [])
    swing_mode = property(lambda self: self._state.attributes.get("swing_mode") if self._state else None)
    swing_horizontal_mode = property(lambda self: self._state.attributes.get("swing_horizontal_mode") if self._state else None)

    @property
    def fan_mode(self):
        cap = self._caps
        if cap is None or not cap.fan_entity:
            return None
        state = self._manager.hass.states.get(cap.fan_entity)
        key = "percentage" if cap.fan_percentage else "fan_mode" if cap.fan_entity.startswith("climate.") else "preset_mode"
        value = state.attributes.get(key) if state else None
        return str(round(value)) if isinstance(value, (float, int)) else value

    @property
    def extra_state_attributes(self):
        cap = self._caps
        cfg = self.controller_settings
        return {**super().extra_state_attributes, "control_mode": cfg["control_mode"],
                "requested_hvac_mode": cfg["requested_mode"],
                "active_profile": model.profile_name(cfg, model.plan_for(self._manager, self._spec)),
                "physical_hvac_mode": self._physical_hvac_mode,
                "physical_source_state": self._state.state if self._state else "unavailable",
                "controller_mode_selected": cfg["control_mode"] in ("automatic", "pid", "manual"),
                "power_control_commissioned": model.permission(self._manager, self._spec, cap)[1] if cap else False,
                "measurements": self._manager.equipment.measurements(self._spec, cap) if cap else {}}

    async def async_set_hvac_mode(self, hvac_mode):
        mode = str(hvac_mode)
        if mode not in [str(v) for v in self.hvac_modes]:
            raise HomeAssistantError("Unsupported physical HVAC mode")
        algorithm = self.controller_settings["control_mode"]
        await self._manager.equipment.async_update(self._spec, {
            "control_mode": "off" if mode == "off" else "pid" if algorithm == "pid" else "manual",
            "requested_mode": mode})

    async def async_turn_off(self):
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self):
        cap = self._caps
        if cap is None:
            raise HomeAssistantError("Device unavailable")
        active = [m for m in cap.modes if m != "off"]
        # Never guess a compressor mode for a multi-mode device.
        previous = self.controller_settings.get("requested_mode")
        if previous not in active:
            if len(active) != 1:
                raise HomeAssistantError("Select an explicit supported HVAC mode")
            previous = active[0]
        await self.async_set_hvac_mode(previous)

    async def async_set_temperature(self, **kwargs):
        cap = self._caps
        if cap is None:
            raise HomeAssistantError("Device unavailable")
        values = {}
        if "temperature" in kwargs:
            if not cap.temperature:
                raise HomeAssistantError("This device has no temperature setpoint")
            mode = kwargs.get("hvac_mode") or self.controller_settings.get("requested_mode") or self.hvac_mode
            values["cool" if mode == "cool" else "heat"] = kwargs["temperature"]
        for key, target in (("target_temp_low", "heat"), ("target_temp_high", "cool")):
            if key in kwargs:
                if not cap.temperature_range:
                    raise HomeAssistantError("This device has no native temperature range")
                values[target] = kwargs[key]
        if not values:
            raise HomeAssistantError("No supported temperature target supplied")
        # Validate the complete edit before changing mode; never partial writes.
        if "hvac_mode" in kwargs and str(kwargs["hvac_mode"]) not in cap.modes:
            raise HomeAssistantError("Unsupported HVAC mode")
        await self._manager.equipment.async_set_targets(self._spec, values,
            mode=str(kwargs["hvac_mode"]) if "hvac_mode" in kwargs else None)

    async def async_set_humidity(self, humidity):
        if self._caps is None or not self._caps.humidity:
            raise HomeAssistantError("This device has no humidity target")
        await self._manager.equipment.async_set_targets(self._spec, {"humidity": humidity})

    async def _choice(self, key, value):
        changes = {key: value}
        cfg = self.controller_settings
        # A native choice takes over only an Existing controller. Manual,
        # automatic and PID retain their selected algorithm; target lookup
        # belongs in _target(), not the preset/swing command path.
        if cfg["control_mode"] == "existing":
            changes["control_mode"] = "manual"
        await self._manager.equipment.async_update(self._spec, changes)

    async def async_set_preset_mode(self, preset_mode):
        await self._choice("preset", preset_mode)

    async def async_set_fan_mode(self, fan_mode):
        await self._manager.equipment.async_set_fan(self._spec, fan_mode)

    async def async_set_swing_mode(self, swing_mode):
        await self._choice("swing_mode", swing_mode)

    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode):
        await self._choice("swing_horizontal_mode", swing_horizontal_mode)
