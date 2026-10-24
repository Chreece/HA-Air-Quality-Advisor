"""Read-only operational status on each managed physical controller device.

The managed climate entity intentionally reports the *physical* HVAC mode.
When PID/Automatic is selected and physical HVAC is OFF, this sensor explains
whether there is no demand, a minimum-OFF hold, a missing input, or a safety
pause. It never makes a hardware decision or calls a Home Assistant service.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory

from .equipment_entity import EquipmentEntity
from . import equipment_model as equipment


class ControllerStatusSensor(EquipmentEntity, SensorEntity):
    """Show the evaluated controller state beside its native climate facade."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:information-outline"
    _attr_should_poll = False

    def __init__(self, manager: Any, spec: equipment.ManagedDevice) -> None:
        self._equipment_init(manager, spec, "control_status")

    @property
    def native_value(self) -> str:
        runtime = self._manager.equipment
        observed = runtime.statuses.get(self._spec.identifier, {})
        if isinstance(observed, dict) and isinstance(observed.get("status"), str):
            return observed["status"]
        mode = self.controller_settings.get("control_mode", "existing")
        if mode in ("existing", "off"):
            return mode
        if not getattr(runtime, "_active", False):
            return "inactive"
        if not getattr(runtime, "_ready", False):
            return "storage_unavailable"
        return "awaiting_evaluation"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        runtime = self._manager.equipment
        cfg = self.controller_settings
        observed = runtime.statuses.get(self._spec.identifier, {})
        observed = observed if isinstance(observed, dict) else {}
        record = runtime.records.get(self._spec.identifier, {})
        record = record if isinstance(record, dict) else {}
        physical = {
            entity_id: (
                state.state if (state := self._manager.hass.states.get(entity_id))
                is not None else "unavailable"
            )
            for entity_id in self._spec.source_entities
        }
        return {
            "area_id": self._spec.area_id,
            "control_method": cfg.get("control_mode", "existing"),
            "selected_preset": cfg.get("preset", "none"),
            "status_reason": observed.get("reason"),
            "last_evaluated_mode": observed.get("mode"),
            "demand_percent": observed.get("demand_percent"),
            "physical_entity_states": physical,
            "controller_owns_power": bool(record.get("power")),
            "paused_reason": record.get("paused"),
            "command_pending": bool(record.get("pending")),
        }
