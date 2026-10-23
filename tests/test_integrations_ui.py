"""Validate metadata and UI strings without loading the HA runtime."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = ROOT / "custom_components" / "enviroment_manager"


def test_is_visible_in_home_assistant_integrations_not_helpers():
    manifest = json.loads((DOMAIN / "manifest.json").read_text())
    assert manifest["integration_type"] == "hub"
    assert manifest["config_flow"] is True
    assert manifest["domain"] == "enviroment_manager"


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
        assert next(iter(document["config"]["step"])) == "areas"
        assert document["options"]["step"]["init"]["menu_options"]
        assert next(iter(document["options"]["step"]["init"]["menu_options"])) == "outside_data"
        assert "window_sensors" in document["options"]["step"]["area_settings"]["menu_options"]
        for context in ("config", "options"):
            room = document[context]["step"]["indoor_sensors"]
            assert room["data"]["excluded_indoor_entities"]
            assert "{area_name}" in room["description"]
            assert "edit_thresholds" not in document[context]["step"]["delivery"]["data"]
        assert "invalid_window_exclusions" in document["config"]["error"]
        for context in ("config", "options"):
            assert "no_windows_after_exclusions" in document[context]["error"]
            assert "review_areas_after_exclusions" in document[context]["error"]


def test_runtime_exclusions_are_applied_before_window_recommendations():
    from custom_components.enviroment_manager.const import CONF_EXCLUDED_WINDOWS, CONF_EXCLUDED_INDOOR
    source = (DOMAIN / "manager.py").read_text()
    assert "set(config.get(CONF_EXCLUDED_WINDOWS, []))" in source
    assert "config.get(CONF_EXCLUDED_INDOOR, {})" in source
    assert "| excluded_indoor" in source
    assert CONF_EXCLUDED_WINDOWS == "excluded_window_entities"
    assert CONF_EXCLUDED_INDOOR == "excluded_indoor_entities"
    assert "excluded_window_entities" in (DOMAIN / "sensor.py").read_text()
    assert "excluded_indoor_entities" in (DOMAIN / "sensor.py").read_text()
