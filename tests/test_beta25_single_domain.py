"""Beta25 exposes exactly one active Home Assistant integration domain."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "environment_manager"


def test_only_environment_manager_is_installable_and_registered():
    manifest = json.loads((PKG / "manifest.json").read_text(encoding="utf-8"))
    root_manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    init = (PKG / "__init__.py").read_text(encoding="utf-8")
    const = (PKG / "const.py").read_text(encoding="utf-8")

    assert manifest["domain"] == root_manifest["domain"] == "environment_manager"
    assert manifest["version"] == root_manifest["version"] == "0.6.0b25"
    assert not (ROOT / "custom_components" / "air_quality_advisor").exists()
    assert not (ROOT / "custom_components" / "enviroment_manager").exists()

    # Legacy names may exist only in migration constants/logic, never runtime aliases.
    assert "SERVICE_ALIAS_DOMAINS" not in init
    assert "LEGACY_PUBLIC_ACTION_DOMAIN" not in init
    assert 'hass.services.async_register(\n            DOMAIN' in init
    assert 'StaticPathConfig(f"/{DOMAIN}/air-quality-advisor-card.js"' in init
    assert 'StaticPathConfig(f"/{BETA20_DOMAIN}' not in init
    assert 'StaticPathConfig(f"/{LEGACY_DOMAIN}' not in init
    assert 'MIGRATION_SOURCE_DOMAINS = ("enviroment_manager", "air_quality_advisor")' in const


def test_legacy_component_folders_are_quarantined_not_deleted():
    migration = (PKG / "domain_migration.py").read_text(encoding="utf-8")
    init = (PKG / "__init__.py").read_text(encoding="utf-8")

    assert "async_quarantine_legacy_component_dirs" in migration
    assert '".environment_manager_legacy_components"' in migration
    assert 'manifest.get("domain") != legacy_domain' in migration
    assert "source.rename(target)" in migration
    assert "async_quarantine_legacy_component_dirs(hass)" in init


def test_no_user_facing_legacy_service_domains_in_readme():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for prefix in (
        "home_environment_manager.",
        "air_quality_advisor.announce",
        "air_quality_advisor.pid_control",
        "air_quality_advisor.climate_control",
        "air_quality_advisor.climate_diagnostics",
        "enviroment_manager.",
    ):
        assert prefix not in readme
    assert "environment_manager.climate_diagnostics" in readme
