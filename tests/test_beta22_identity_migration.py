"""Beta22 identity-preserving cross-domain migration contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "environment_manager"


def source(name: str) -> str:
    return (PKG / name).read_text(encoding="utf-8")


def test_migration_preserves_config_entry_identity_in_source_contract():
    migration = source("domain_migration.py")
    assert "async_migrate_legacy_registry(hass: Any, legacy: Any)" in migration
    assert "_reindex_entry_domain(hass, legacy, DOMAIN)" in migration
    assert "items._unindex_entry(entry.entry_id)" in migration
    assert 'object.__setattr__(entry, "domain", new_domain)' in migration
    assert "async_remove(legacy.entry_id)" not in migration
    assert "new_config_entry_id=legacy.entry_id" in migration
    assert "new_config_subentry_id=entity.config_subentry_id" in migration


def test_config_flow_migrates_existing_entry_without_creating_replacement():
    flow = source("config_flow.py")
    section = flow[
        flow.index("async def async_step_migrate_legacy"):
        flow.index("async def _finish")
    ]
    assert "async_migrate_legacy_registry(self.hass, legacy)" in section
    assert "async_create_entry" not in section
    assert "async_setup(migrated.entry_id)" in section


def test_storage_ancestry_and_fail_closed_private_api_guard():
    migration = source("domain_migration.py")
    assert 'data["_legacy_entry_id"] = entry.entry_id' in migration
    assert 'data["_legacy_domain"] = source_domain' in migration
    assert '"_legacy_entry_chain"' in migration
    assert 'required = ("data", "_unindex_entry", "_index_entry")' in migration
    assert "identity-preserving migration" in migration
