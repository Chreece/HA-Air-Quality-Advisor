"""Beta21 canonical domain repair and beta20 compatibility."""
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


def test_b19_and_b20_are_both_migration_sources():
    const = source("const.py")
    migration = source("domain_migration.py")
    flow = source("config_flow.py")
    assert 'DOMAIN = "environment_manager"' in const
    assert 'LEGACY_DOMAIN = "air_quality_advisor"' in const
    assert 'BETA20_DOMAIN = "enviroment_manager"' in const
    assert 'LEGACY_DOMAINS = (BETA20_DOMAIN, LEGACY_DOMAIN)' in const
    assert "source_domain not in LEGACY_DOMAINS" in migration
    assert "for domain in LEGACY_DOMAINS" in flow
    assert "async_migrate_legacy_registry(self.hass, legacy)" in flow
    assert "async_create_entry" not in flow[flow.index("async def async_step_migrate_legacy"):flow.index("async def _finish")]


def test_service_and_card_compatibility_aliases_remain():
    init = source("__init__.py")
    const = source("const.py")
    assert 'LEGACY_PUBLIC_ACTION_DOMAIN = "home_environment_manager"' in const
    assert 'BETA20_DOMAIN = "enviroment_manager"' in const
    assert "SERVICE_ALIAS_DOMAINS" in init
    assert "BETA20_DOMAIN" in init
    assert 'StaticPathConfig(f"/{BETA20_DOMAIN}/air-quality-advisor-card.js"' in init
