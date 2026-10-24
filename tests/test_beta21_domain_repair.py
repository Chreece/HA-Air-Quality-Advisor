"""Canonical environment_manager domain and migration-only legacy sources."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "environment_manager"


def source(name: str) -> str:
    return (PKG / name).read_text(encoding="utf-8")


def test_canonical_package_and_manifest():
    manifest = json.loads((PKG / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["domain"] == "environment_manager"
    assert manifest["version"].startswith("0.6.0b")
    assert PKG.is_dir()
    assert not (ROOT / "custom_components" / "enviroment_manager").exists()
    assert not (ROOT / "custom_components" / "air_quality_advisor").exists()


def test_historical_domains_are_migration_inputs_only():
    const = source("const.py")
    migration = source("domain_migration.py")
    flow = source("config_flow.py")
    init = source("__init__.py")

    assert 'DOMAIN = "environment_manager"' in const
    assert 'MIGRATION_SOURCE_DOMAINS = ("enviroment_manager", "air_quality_advisor")' in const
    assert "for domain in MIGRATION_SOURCE_DOMAINS" in flow
    assert "source_domain not in MIGRATION_SOURCE_DOMAINS" in migration
    assert "async_migrate_legacy_registry(self.hass, legacy)" in flow

    # Historical names must never be registered as services/front-end paths.
    assert "SERVICE_ALIAS_DOMAINS" not in init
    assert "LEGACY_PUBLIC_ACTION_DOMAIN" not in init
    assert "BETA20_DOMAIN" not in init
    assert "LEGACY_DOMAIN" not in init
    assert 'StaticPathConfig(f"/{DOMAIN}/air-quality-advisor-card.js"' in init
    assert 'StaticPathConfig(f"/{BETA20_DOMAIN}' not in init
    assert 'StaticPathConfig(f"/{LEGACY_DOMAIN}' not in init


def test_migration_flow_does_not_create_second_config_entry():
    flow = source("config_flow.py")
    section = flow[
        flow.index("async def async_step_migrate_legacy"):
        flow.index("async def _finish")
    ]
    assert "async_migrate_legacy_registry(self.hass, legacy)" in section
    assert "async_create_entry" not in section
