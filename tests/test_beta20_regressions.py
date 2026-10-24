"""b20 user-reported regressions without requiring HA at import time."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PKG=ROOT/"custom_components/environment_manager"

def source(name):
    return (PKG/name).read_text(encoding="utf-8")

def test_exact_requested_domain_and_only_one_package():
    manifest=(PKG/"manifest.json").read_text()
    const=source("const.py")
    assert '"domain": "environment_manager"' in manifest
    assert 'DOMAIN = "environment_manager"' in const
    assert 'MIGRATION_SOURCE_DOMAINS = ("enviroment_manager", "air_quality_advisor")' in const
    assert PKG.is_dir()
    assert not (ROOT/"custom_components/enviroment_manager").exists()
    assert not (ROOT/"custom_components/air_quality_advisor").exists()

def test_no_allow_power_backend_or_entity():
    for path in PKG.rglob("*.py"):
        assert "allow_power" not in path.read_text(), path
    assert "allow_power" not in (ROOT/"apply_equipment_i18n.py").read_text()

def test_room_owned_preset_inputs_and_no_device_temperature_duplicates():
    controls=source("device_controls.py")
    numbers=source("number.py")
    assert 'for profile in ("comfort", "home", "sleep", "eco")' in controls
    assert '"humidity_target"' in controls and '"fan_speed_percent"' in controls
    assert 'f"{profile}_{mode}_c"' not in controls
    assert 'chosen = []' in numbers

def test_automatic_preset_meanings_are_encoded():
    strategy=source("climate_strategy.py")
    assert 'return "away","nobody_home"' in strategy
    assert 'return "sleep","sleep_mode_active"' in strategy
    assert 'return "comfort","room_occupied"' in strategy
    assert 'return "home","someone_home_room_unoccupied"' in strategy
    assert 'if manual in ("comfort","home","away","sleep","eco")' in strategy

def test_eco_is_explicit_only_in_profile_selector():
    strategy=source("climate_strategy.py")
    automatic=strategy[strategy.index('def select_profile'):strategy.index('def capabilities')]
    assert automatic.count('"eco"') == 1
    assert 'manual in ("comfort","home","away","sleep","eco")' in automatic

def test_general_settings_has_no_submit_rerender_state():
    source=(ROOT/"custom_components/environment_manager/room_setup.py").read_text()
    assert "_setup_general_rendered" not in source
    assert "_setup_general_draft" not in source

