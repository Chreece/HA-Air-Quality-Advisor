"""Public rebrand must not damage existing Home Assistant installations."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = ROOT / "custom_components" / "enviroment_manager"


def test_public_name_and_domain_migration_is_canonical_and_backward_compatible():
    manifest = json.loads((DOMAIN / "manifest.json").read_text(encoding="utf-8"))
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert manifest["domain"] == "enviroment_manager"
    assert manifest["name"] == "Home Environment Manager"
    assert hacs["name"] == "Home Environment Manager"
    requested = json.loads((ROOT / ".github" / "release-request.json").read_text(encoding="utf-8"))
    assert manifest["version"] == requested["version"]
    assert manifest["requirements"] == []
    assert (DOMAIN / "pmv_core.py").is_file()


def test_domain_migration_and_legacy_action_aliases_are_preserved():
    source = (DOMAIN / "__init__.py").read_text(encoding="utf-8")
    const = (DOMAIN / "const.py").read_text(encoding="utf-8")
    assert 'DOMAIN = "enviroment_manager"' in const
    assert 'LEGACY_DOMAIN = "air" + "_quality_advisor"' not in const
    assert 'LEGACY_DOMAIN = "' + "air" + '_quality_advisor"' in const
    assert 'LEGACY_PUBLIC_ACTION_DOMAIN = "home_environment_manager"' in const
    assert "LEGACY_DOMAIN" in source and "LEGACY_PUBLIC_ACTION_DOMAIN" in source
    assert 'DOMAIN, "announce"' in source


def test_old_card_and_new_alias_both_render():
    js = (DOMAIN / "frontend" / "air-quality-advisor-card.js").read_text(encoding="utf-8")
    for name in ("air-quality-advisor-card", "home-environment-manager-card"):
        assert f"customElements.get('{name}')" in js
    assert 'const BRAND_TITLE = "Home Environment Manager"' in js
    assert "show_science" in js
    assert "_pollenIndicator" in js
    assert "international" in js


def test_brand_art_and_recreated_screenshots_are_real_local_assets():
    for asset in ("home-environment-manager-banner.svg",
                  "home-environment-manager-workflow.svg"):
        path = ROOT / ".github" / "assets" / asset
        assert path.is_file()
        root = ET.fromstring(path.read_text(encoding="utf-8"))
        assert root.tag.endswith("svg")
    for name in ("dashboard-science-desktop.png","dashboard-science-mobile.png"):
        png = ROOT / ".github" / "assets" / "screenshots" / name
        assert png.is_file() and png.stat().st_size > 5000
