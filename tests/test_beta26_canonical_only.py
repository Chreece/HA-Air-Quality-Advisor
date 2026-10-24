"""Beta26 is a clean canonical-only environment_manager release."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "environment_manager"


def test_only_canonical_domain_exists_and_no_migration_code_ships():
    manifest = json.loads((PKG / "manifest.json").read_text(encoding="utf-8"))
    root_manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest == root_manifest
    assert manifest["domain"] == "environment_manager"
    assert manifest["version"] == "0.6.0b26"
    assert not (PKG / "domain_migration.py").exists()

    runtime = "\n".join(
        path.read_text(encoding="utf-8")
        for path in PKG.glob("*.py")
    )
    for forbidden in (
        "air_quality_advisor",
        "enviroment_manager",
        "home_environment_manager",
        "MIGRATION_SOURCE_DOMAINS",
        "LEGACY_STORAGE_DEFAULT_DOMAIN",
        "async_migrate_legacy_registry",
        "async_open_migrated_store",
        "async_quarantine_legacy_component_dirs",
    ):
        assert forbidden not in runtime

    flow = (PKG / "config_flow.py").read_text(encoding="utf-8")
    assert "migrate_legacy" not in flow
    assert "legacy_migration" not in flow


def test_no_migration_ui_keys_in_any_translation():
    paths = [PKG / "strings.json", *sorted((PKG / "translations").glob("*.json"))]
    assert len(paths) == 39  # strings.json + 38 shipped locale files
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "migrate_legacy" not in text, path
        assert "legacy_migration_" not in text, path


def test_room_profiles_have_temperature_and_humidity_targets_for_every_mode():
    controls = (PKG / "device_controls.py").read_text(encoding="utf-8")
    for profile in ("comfort", "home", "away", "sleep", "eco"):
        assert f'"{profile}": {{"heat":' in controls
        assert f'f"{{profile}}_humidity"' in controls

    strings = json.loads((PKG / "strings.json").read_text(encoding="utf-8"))
    numbers = strings["entity"]["number"]
    for profile in ("comfort", "home", "away", "sleep", "eco"):
        for suffix in ("heat", "cool", "humidity"):
            assert f"area_climate_profile_{profile}_{suffix}" in numbers


def test_controller_help_has_no_second_power_switch_contract():
    text = (ROOT / "apply_equipment_i18n.py").read_text(encoding="utf-8")
    assert "no Configure approval or second power switch is required" in text
    assert "Selecting the method authorizes this exact native controller" in text
