"""Check PID friendly-name prefix behavior against installed Home Assistant.

Home Assistant prepends native device names when has_entity_name=True; those
names can sort before PID even if the translation itself begins with PID.
The PID-specific flag is False; hardware binding and entity unique IDs stay
unchanged. No HA automation or device service is called.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from homeassistant.components.number import NumberEntity
from homeassistant.components.select import SelectEntity
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import EntityCategory

from custom_components.environment_manager.device_hierarchy import ManagedDevice
from custom_components.environment_manager.number import EquipmentNumber, ConfigNumber
from custom_components.environment_manager.select import EquipmentSelect, ConfigSelect
from custom_components.environment_manager.button import (
    EquipmentCalibrationButton, EquipmentFanCapacityButton, EquipmentResumeButton
)

spec = ManagedDevice(
    "entry_controller_sample", "living", "Thermostat",
    "native_hardware", ("climate.native_sample",),
)
manager = SimpleNamespace(
    settings={"areas": ["living"], "climate_rooms": {},
              "equipment_controllers": {spec.identifier: {"control_mode": "pid"}}},
    hass=SimpleNamespace(states=SimpleNamespace(get=lambda name: None)),
)
pid = [
    EquipmentNumber(manager, spec, "kp"),
    EquipmentNumber(manager, spec, "ki"),
    EquipmentNumber(manager, spec, "sample_seconds"),
    EquipmentNumber(manager, spec, "cycle_seconds"),
    EquipmentNumber(manager, spec, "pid_process_gain"),
    EquipmentNumber(manager, spec, "pid_capacity_stage_1"),
    EquipmentSelect(manager, spec, "pid_calibration_method"),
    EquipmentSelect(manager, spec, "pid_fan_capacity_mode"),
    EquipmentSelect(manager, spec, "pid_fan_capacity_for_mode"),
    EquipmentCalibrationButton(manager, spec),
    EquipmentFanCapacityButton(manager, spec),
    ConfigNumber(manager, "entry", "living", "pid", "kp",
                 (0., 100., 0.1, None)),
    ConfigNumber(manager, "entry", "living", "direct_tuning", "sample_seconds",
                 (120., 3600., 30., "s")),
    ConfigSelect(manager, "entry", "living", "pid_gain_source",
                 ("defaults", "manual")),
]
non_pid = [
    EquipmentNumber(manager, spec, "quiet_percentage"),
    EquipmentNumber(manager, spec, "min_on_seconds"),
    EquipmentSelect(manager, spec, "control_mode"),
    EquipmentResumeButton(manager, spec),
    ConfigNumber(manager, "entry", "living", "climate_profile", "home_heat",
                 (5., 35., 0.5, "°C")),
    ConfigSelect(manager, "entry", "living", "manual_profile",
                 ("auto", "home")),
]


def main() -> None:
    for entity in pid:
        assert isinstance(entity, (NumberEntity, SelectEntity, ButtonEntity))
        assert entity.has_entity_name is False, (type(entity).__name__, entity.unique_id)
        assert entity.translation_key is not None
        suffix = getattr(entity, "_key", None) or getattr(entity, "_kind", None)
        assert isinstance(suffix, str)
        assert entity.unique_id.endswith("_" + suffix)
        assert entity.device_info["identifiers"]
        assert entity.entity_category == EntityCategory.CONFIG
    for entity in non_pid:
        assert entity.has_entity_name is True, (type(entity).__name__, entity.unique_id)
    # Existing entity registry keys and native sources are unchanged.
    assert pid[0].unique_id == spec.identifier + "_kp"
    assert pid[4].unique_id == spec.identifier + "_pid_process_gain"
    assert pid[10].unique_id == spec.identifier + "_pid_apply_fan_capacity"
    assert pid[11].unique_id == "entry_area_living_pid_kp"
    assert pid[12].unique_id == "entry_area_living_direct_tuning_sample_seconds"
    assert pid[13].unique_id == "entry_area_living_pid_gain_source"
    print("HA 2026.10: PID friendly names not device-prefixed; IDs and non-PID names unchanged: PASS")


if __name__ == "__main__":
    main()
