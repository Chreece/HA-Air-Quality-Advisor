"""Verify the card is bundled and served, without requiring Home Assistant Core."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "air_quality_advisor"


def test_frontend_card_is_bundled_inside_hacs_integration():
    asset = INTEGRATION / "frontend" / "air-quality-advisor-card.js"
    assert asset.is_file()
    source = asset.read_text()
    assert "air-quality-advisor-card" in source
    assert "getEntitySuggestion" in source
    assert "hass.language" in source
    assert "AirQualityAdvisorCardEditor" in source
    assert "customElements.define" in source


def test_static_registration_and_cache_version_are_declared():
    manifest = json.loads((INTEGRATION / "manifest.json").read_text())
    source = (INTEGRATION / "__init__.py").read_text()
    assert {"frontend", "http"}.issubset(manifest["dependencies"])
    assert "async_register_static_paths" in source
    assert "add_extra_js_url" in source
    # The resource version comes from the same manifest that HACS installs,
    # so upcoming releases cannot accidentally reuse an older cache key.
    assert "manifest.json" in source
    assert "manifest['version']" in source
    assert 'f"/{DOMAIN}/air-quality-advisor-card.js?v={manifest[\'version\']}"' in source


def test_single_sensor_still_exposes_dashboard_without_new_entities():
    source = (INTEGRATION / "sensor.py").read_text()
    assert "dashboard_snapshot" in source
    assert "async_add_grouped_entities(entry.runtime_data, async_add_entities, [AirQualityRecommendation" in source
