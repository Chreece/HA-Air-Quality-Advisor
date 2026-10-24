"""Opt-in per-area manual mold calibration. No actuator services."""
from __future__ import annotations

from .room_hubs import async_add_grouped_entities

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import EntityCategory

from .const import CONF_AREAS, CONF_USE_MOLD, CONF_MOLD_ROOMS, DOMAIN
from .mold_controls import async_recalculate_mold_factor


async def async_setup_entry(hass, entry, async_add_entities):
    settings = entry.runtime_data.settings
    from . import equipment_model as equipment
    controllers = equipment.specs(entry.runtime_data)
    async_add_grouped_entities(entry.runtime_data, async_add_entities, [
        *[EquipmentResumeButton(entry.runtime_data, spec) for spec in controllers],
        *[EquipmentCalibrationButton(entry.runtime_data, spec) for spec in controllers
          if "pid" in equipment.control_modes(entry.runtime_data, spec)],
    ])
    if settings.get(CONF_USE_MOLD) is not True:
        return
    async_add_grouped_entities(entry.runtime_data, async_add_entities, [
        AreaMoldCalibrationButton(entry.runtime_data, entry.entry_id, area)
        for area in settings.get(CONF_AREAS, [])
        if isinstance(area, str)
    ])


class AreaMoldCalibrationButton(ButtonEntity):
    """Recalculate using fresh room/outside sensors and user-measured surface °C."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "area_recalculate_mold"
    _attr_icon = "mdi:calculator-variant-outline"

    def __init__(self, manager, entry_id, area):
        self._manager = manager
        self._area = area
        self._attr_unique_id = f"{entry_id}_area_{area}_mold_recalibrate"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry_id}_area_{area}")},
        }

    async def async_press(self):
        await async_recalculate_mold_factor(self._manager, self._area)

    @property
    def extra_state_attributes(self):
        rooms = self._manager.settings.get(CONF_MOLD_ROOMS, {})
        saved = rooms.get(self._area, {}) if isinstance(rooms, dict) else {}
        if not isinstance(saved, dict):
            saved = {}
        return {
            "calibration_factor": saved.get("calibration_factor"),
            "calibrated_at": saved.get("calibrated_at"),
            "indoor_temperature_entity": saved.get("indoor_temperature_entity"),
            "outdoor_weather_entity": saved.get("outdoor_weather_entity"),
            "measured_cold_surface_c": saved.get("critical_temperature_c"),
            "status": "calibrated" if saved.get("calibration_factor") is not None
                      else "needs_calibration",
        }


from .equipment_entity import EquipmentEntity


class EquipmentResumeButton(EquipmentEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:play-pause"

    def __init__(self, manager, spec):
        self._equipment_init(manager, spec, "resume")

    async def async_press(self):
        await self._manager.equipment.async_resume(self._spec)


class EquipmentCalibrationButton(EquipmentEntity, ButtonEntity):
    """Apply a measured-model mathematical tune to one physical device.

    No step test, actuator pulse or service call occurs. Calibration requires
    known plant gain/time/delay and a physically OFF, reconciled controller.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:calculator-variant-outline"

    def __init__(self, manager, spec):
        self._equipment_init(manager, spec, "pid_apply_calibration")

    @property
    def available(self):
        cfg = self.controller_settings
        return cfg["control_mode"] == "pid" and cfg["pid_calibration_method"] != "manual"

    @property
    def extra_state_attributes(self):
        from . import equipment_model as model
        from .pid_calibration import tune
        result = {**super().extra_state_attributes,
                  "pid_calibration_role": "apply",
                  "calibration_method": self.controller_settings["pid_calibration_method"],
                  "manual_gains": {
                      key: self.controller_settings[key] for key in ("kp", "ki", "kd")
                  },
                  "measured_model": {
                      key: self.controller_settings[key] for key in model.PID_MODEL_FIELDS
                  },
                  "last_applied": self.controller_settings.get("pid_last_calibration")}
        if not self.available:
            result["calibration_status"] = "select_pid_and_nonmanual_method"
            return result
        try:
            calculated = tune(
                self.controller_settings["pid_calibration_method"],
                self.controller_settings,
                sample_seconds=self.controller_settings["sample_seconds"],
                constraints=model.NUMBER_FIELDS,
            )
        except ValueError as error:
            result["calibration_status"] = str(error)
        else:
            result["calibration_status"] = "ready_to_apply_when_physical_off"
            result["proposed_gains"] = {
                "kp": calculated.kp, "ki": calculated.ki, "kd": calculated.kd,
            }
        return result

    async def async_press(self):
        await self._manager.equipment.async_apply_pid_calibration(self._spec)
