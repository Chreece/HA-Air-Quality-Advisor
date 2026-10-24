"""Validate beta30 controller diagnostics with installed Home Assistant 2026.10."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from homeassistant.helpers.entity import EntityCategory

from custom_components.environment_manager.device_hierarchy import ManagedDevice
from custom_components.environment_manager.equipment_status import ControllerStatusSensor


def main() -> None:
    spec = ManagedDevice(
        "entry_controller_living", "living", "Living thermostat",
        "physical-device", ("climate.native_living",),
    )
    runtime = SimpleNamespace(
        statuses={spec.identifier: {"status": "minimum_off_hold"}},
        records={spec.identifier: {"area": "living", "power": {}, "off_at": {}}},
        _active=True,
        _ready=True,
    )
    manager = SimpleNamespace(
        settings={"equipment_controllers": {
            spec.identifier: {"control_mode": "pid", "preset": "none"}
        }},
        equipment=runtime,
        hass=SimpleNamespace(states=SimpleNamespace(
            get=lambda eid: SimpleNamespace(state="off")
            if eid == "climate.native_living" else None
        )),
    )
    entity = ControllerStatusSensor(manager, spec)
    assert entity.entity_category == EntityCategory.DIAGNOSTIC
    assert entity.unique_id == spec.identifier + "_control_status"
    assert entity.device_info["identifiers"] == {
        ("environment_manager", spec.identifier)
    }
    assert entity.native_value == "minimum_off_hold"
    attrs = entity.extra_state_attributes
    assert attrs["control_method"] == "pid"
    assert attrs["physical_entity_states"] == {"climate.native_living": "off"}
    assert attrs["controller_owns_power"] is False

    runtime.statuses[spec.identifier] = {
        "status": "paused", "reason": "physical_manual_override"
    }
    runtime.records[spec.identifier]["paused"] = "physical_manual_override"
    assert entity.native_value == "paused"
    assert entity.extra_state_attributes["paused_reason"] == "physical_manual_override"

    print("HA 2026.10 canonical ControllerStatusSensor: PASS")


if __name__ == "__main__":
    main()
