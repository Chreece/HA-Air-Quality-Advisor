"""Validate metadata and UI strings without loading the HA runtime."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = ROOT / "custom_components" / "air_quality_advisor"


def test_is_visible_in_home_assistant_integrations_not_helpers():
    manifest = json.loads((DOMAIN / "manifest.json").read_text())
    assert manifest["integration_type"] == "service"
    assert manifest["config_flow"] is True
    assert manifest["domain"] == "air_quality_advisor"


def test_all_languages_have_usable_area_picker_error_messages():
    for name in ("strings.json", "translations/en.json", "translations/de.json",
                 "translations/el.json", "translations/fr.json", "translations/es.json"):
        doc = json.loads((DOMAIN / name).read_text())
        assert doc["config"]["step"]["areas"]["data"]["areas"]
        assert doc["options"]["step"]["areas"]["data"]["areas"]
        assert "no_window_areas" in doc["config"]["error"]
        assert "invalid_areas" in doc["options"]["error"]


def test_exclusion_selector_is_translated_for_setup_and_options():
    for name in ("strings.json", "translations/en.json", "translations/de.json",
                 "translations/el.json", "translations/fr.json", "translations/es.json"):
        document = json.loads((DOMAIN / name).read_text())
        assert document["config"]["step"]["window_sensors"]["data"]["excluded_window_entities"]
        assert document["options"]["step"]["window_sensors"]["data"]["excluded_window_entities"]
        assert "window_sensors" in document["options"]["step"]["init"]["menu_options"]
        assert "invalid_window_exclusions" in document["config"]["error"]


def test_runtime_exclusions_are_applied_before_window_recommendations():
    from custom_components.air_quality_advisor.const import CONF_EXCLUDED_WINDOWS
    source = (DOMAIN / "manager.py").read_text()
    assert "excluded_entities=selected_outdoor | set(config.get(CONF_EXCLUDED_WINDOWS, []))" in source
    assert CONF_EXCLUDED_WINDOWS == "excluded_window_entities"
    assert "excluded_window_entities" in (DOMAIN / "sensor.py").read_text()
