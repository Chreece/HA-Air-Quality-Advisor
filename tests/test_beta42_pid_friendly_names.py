"""PID parameters sort under PID in every Home Environment Manager locale.

The new naming is presentation-only. Keep IDs, model fields, controller
settings, native service targets and all non-PID entities unchanged.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from apply_pid_sort_i18n import (
    _is_pid_parameter, apply_pid_sort_i18n, pid_first,
)

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "environment_manager"

REQUIRED_KEYS = {
    "number": {
        "equipment_kp", "equipment_ki", "equipment_kd",
        "equipment_sample_seconds", "equipment_cycle_seconds",
        "equipment_pid_process_gain", "equipment_pid_time_constant_minutes",
        "equipment_pid_dead_time_minutes", "equipment_pid_lambda_minutes",
        *(f"equipment_pid_capacity_stage_{i}" for i in range(1, 5)),
        *(f"equipment_pid_capacity_speed_{i}" for i in range(1, 4)),
        *(f"equipment_pid_capacity_output_{i}" for i in range(1, 4)),
        *(f"area_pid_{key}" for key in (
            "target_c", "kp", "ki", "kd", "offset_c",
            "min_setpoint_c", "max_setpoint_c", "sample_seconds",
            "max_change_c", "min_change_c",
        )),
        *(f"area_direct_tuning_{key}" for key in (
            "kp", "ki", "kd", "sample_seconds",
            "max_demand_change", "min_demand_change",
        )),
    },
    "select": {
        "area_pid_gain_source", "equipment_pid_calibration_method",
        "equipment_pid_fan_capacity_mode", "equipment_pid_fan_capacity_for_mode",
    },
    "button": {
        "equipment_pid_apply_calibration", "equipment_pid_apply_fan_capacity",
    },
}


@pytest.mark.parametrize("sample,expected", [
    ("Proportional gain Kp (% per °C)", "PID · Proportional gain Kp (% per °C)"),
    ("{channel}Αναλογικός συντελεστής Kp", "PID · {channel}Αναλογικός συντελεστής Kp"),
    ("PID-Kalibrierungsverfahren", "PID · Kalibrierungsverfahren"),
    ("Διάστημα δειγματοληψίας PID (δευτ.)", "PID · Διάστημα δειγματοληψίας (δευτ.)"),
    ("{channel}PID sampling period", "PID · {channel}sampling period"),
])
def test_pid_first_names_are_readable_and_channel_follows_pid(sample, expected):
    assert pid_first(sample) == expected
    assert pid_first(expected) == expected


def test_all_38_locales_and_canonical_strings_have_pid_first_names():
    paths = [INTEGRATION / "strings.json", *
             sorted((INTEGRATION / "translations").glob("*.json"))]
    assert len(paths) == 39
    for path in paths:
        source = json.loads(path.read_text(encoding="utf-8"))
        for domain, required in REQUIRED_KEYS.items():
            actual = source["entity"][domain]
            assert required <= set(actual), f"Missing {path.name}/{domain}: {required-set(actual)}"
            for key in required:
                label = actual[key]["name"]
                assert label.startswith("PID"), (path.name, domain, key, label)
                assert label == pid_first(label), (path.name, domain, key, label)
                assert not label.startswith("{channel}"), (path.name, key, label)
                assert label.count("PID") == 1, (path.name, key, label)
        # Exact field/option meanings and other entity groups are still there.
        assert source["entity"]["select"]["equipment_control_mode"]["state"]["pid"]
        assert not source["entity"]["select"]["equipment_control_mode"]["name"].startswith("PID")
        assert not source["entity"]["switch"]["equipment_quiet_sleep"]["name"].startswith("PID")
        assert not source["entity"]["climate"]["equipment_climate"]["name"].startswith("PID")


def test_pid_matcher_excludes_quiet_physical_controls_and_profiles():
    assert _is_pid_parameter("number", "equipment_pid_capacity_stage_1")
    assert _is_pid_parameter("number", "equipment_kp")
    assert _is_pid_parameter("number", "area_pid_sample_seconds")
    assert _is_pid_parameter("number", "area_direct_tuning_max_demand_change")
    assert _is_pid_parameter("button", "equipment_pid_apply_fan_capacity")
    assert _is_pid_parameter("select", "area_pid_gain_source")
    for domain, name in (
        ("number", "equipment_quiet_percentage"),
        ("number", "equipment_min_on_seconds"),
        ("number", "area_climate_profile_home_heat"),
        ("switch", "equipment_quiet_sleep"),
        ("select", "equipment_control_mode"),
        ("button", "equipment_resume"),
    ):
        assert not _is_pid_parameter(domain, name)


def test_pid_sorting_pass_is_idempotent_and_does_not_change_other_fields(tmp_path):
    root = tmp_path / "environment_manager"
    (root / "translations").mkdir(parents=True)
    original = json.loads((INTEGRATION/"translations"/"el.json").read_text(encoding="utf-8"))
    # This helper requires 38 locale files to avoid quietly skipping languages.
    for file in (INTEGRATION/"translations").glob("*.json"):
        (root/"translations"/file.name).write_text(
            file.read_text(encoding="utf-8"), encoding="utf-8")
    (root/"strings.json").write_text(
        (INTEGRATION/"strings.json").read_text(encoding="utf-8"), encoding="utf-8")

    apply_pid_sort_i18n(root)
    first = json.loads((root/"translations"/"el.json").read_text(encoding="utf-8"))
    apply_pid_sort_i18n(root)
    second = json.loads((root/"translations"/"el.json").read_text(encoding="utf-8"))
    assert first == second
    assert first["entity"]["climate"] == original["entity"]["climate"]
    assert first["entity"]["select"]["equipment_control_mode"] == original["entity"]["select"]["equipment_control_mode"]
    assert first["entity"]["switch"] == original["entity"]["switch"]
