from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OLD = ROOT / "custom_components" / "enviroment_manager"
PKG = ROOT / "custom_components" / "environment_manager"
TEXT = {".py", ".json", ".md", ".js", ".cjs", ".yml", ".yaml", ".txt"}


def rewrite(path: Path, version: bool = False) -> None:
    if not path.is_file() or path.resolve() == Path(__file__).resolve():
        return
    if path == ROOT / "tests" / "test_beta21_domain_repair.py":
        return
    try:
        value = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    new = value.replace("custom_components/enviroment_manager", "custom_components/environment_manager")
    new = new.replace("custom_components.enviroment_manager", "custom_components.environment_manager")
    new = new.replace("enviroment_manager", "environment_manager")
    if version:
        new = new.replace("0.6.0b20", "0.6.0b21")
        new = new.replace("beta/v0.6.0b20", "beta/v0.6.0b21")
    if new != value:
        path.write_text(new, encoding="utf-8")


if OLD.exists() and PKG.exists():
    raise RuntimeError("Both typo and canonical integration packages exist")
if OLD.exists():
    OLD.rename(PKG)
if not PKG.is_dir():
    raise RuntimeError("Home Environment Manager package is missing")

for base in (PKG, ROOT / "tests", ROOT / "tools"):
    for path in base.rglob("*"):
        if path.suffix in TEXT:
            rewrite(path, version=True)
for path in ROOT.glob("*.py"):
    rewrite(path, version=True)
for name in ("README.md", "CHANGELOG.md", "RELEASING.md"):
    rewrite(ROOT / name, version=True)
for name in (
    "validate.yml",
    "controller-development.yml",
    "readme-screenshots.yml",
    "refresh-compact-translations.yml",
    "sync-home-environment-locales.yml",
):
    rewrite(ROOT / ".github" / "workflows" / name, version=True)

const_path = PKG / "const.py"
const = const_path.read_text(encoding="utf-8")
old = '''DOMAIN = "environment_manager"
LEGACY_DOMAIN = "air_quality_advisor"
LEGACY_PUBLIC_ACTION_DOMAIN = "home_environment_manager"
'''
new = '''DOMAIN = "environment_manager"
LEGACY_DOMAIN = "air_quality_advisor"
BETA20_DOMAIN = "enviroment_manager"
LEGACY_DOMAINS = (BETA20_DOMAIN, LEGACY_DOMAIN)
LEGACY_PUBLIC_ACTION_DOMAIN = "home_environment_manager"
'''
if old not in const:
    raise RuntimeError("Unexpected domain constants")
const_path.write_text(const.replace(old, new, 1), encoding="utf-8")

flow_path = PKG / "config_flow.py"
flow = flow_path.read_text(encoding="utf-8")
flow = flow.replace(
    "DEFAULT_THRESHOLDS, DOMAIN, LEGACY_DOMAIN, CONF_USE_MOLD, CONF_MOLD_ROOMS,",
    "DEFAULT_THRESHOLDS, DOMAIN, LEGACY_DOMAIN, LEGACY_DOMAINS, CONF_USE_MOLD, CONF_MOLD_ROOMS,",
    1,
)
flow = flow.replace(
    "legacy = entries.async_entries(LEGACY_DOMAIN) if entries is not None else []",
    "legacy = ([entry for domain in LEGACY_DOMAINS for entry in entries.async_entries(domain)] if entries is not None else [])",
    1,
)
flow = flow.replace(
    "if legacy is None or legacy.domain != LEGACY_DOMAIN:",
    "if legacy is None or legacy.domain not in LEGACY_DOMAINS:",
    1,
)
needle = '''        data=dict(legacy.data)
        data["_legacy_entry_id"]=legacy.entry_id
        subentries=[sub.as_dict() for sub in legacy.subentries.values()]
'''
replacement = '''        data=dict(legacy.data)
        previous_id=data.get("_legacy_entry_id")
        previous_domain=data.get("_legacy_domain")
        chain=list(data.get("_legacy_entry_chain") or [])
        if isinstance(previous_id,str) and previous_id:
            chain.insert(0,{
                "domain": previous_domain if previous_domain in LEGACY_DOMAINS else LEGACY_DOMAIN,
                "entry_id": previous_id,
            })
        data["_legacy_entry_id"]=legacy.entry_id
        data["_legacy_domain"]=legacy.domain
        if chain:
            data["_legacy_entry_chain"]=chain
        subentries=[sub.as_dict() for sub in legacy.subentries.values()]
'''
if needle not in flow:
    raise RuntimeError("Unexpected config flow migration block")
flow_path.write_text(flow.replace(needle, replacement, 1), encoding="utf-8")

init_path = PKG / "__init__.py"
init = init_path.read_text(encoding="utf-8")
init = init.replace(
    "from .const import DOMAIN, LEGACY_DOMAIN, LEGACY_PUBLIC_ACTION_DOMAIN, PLATFORMS, LANGUAGES",
    "from .const import (DOMAIN, LEGACY_DOMAIN, BETA20_DOMAIN, LEGACY_PUBLIC_ACTION_DOMAIN, PLATFORMS, LANGUAGES)",
    1,
)
init = init.replace(
    'PUBLIC_ACTION_DOMAIN = "home_environment_manager"  # Alias only; existing domain remains.',
    'PUBLIC_ACTION_DOMAIN = LEGACY_PUBLIC_ACTION_DOMAIN\nSERVICE_ALIAS_DOMAINS = (PUBLIC_ACTION_DOMAIN, BETA20_DOMAIN, LEGACY_DOMAIN)',
    1,
)
init = init.replace(
    '        StaticPathConfig(f"/{LEGACY_DOMAIN}/air-quality-advisor-card.js", str(card_path), True),',
    '        StaticPathConfig(f"/{BETA20_DOMAIN}/air-quality-advisor-card.js", str(card_path), True),\n        StaticPathConfig(f"/{LEGACY_DOMAIN}/air-quality-advisor-card.js", str(card_path), True),',
    1,
)
init = init.replace("(PUBLIC_ACTION_DOMAIN, LEGACY_DOMAIN)", "SERVICE_ALIAS_DOMAINS")
init = init.replace("(DOMAIN, PUBLIC_ACTION_DOMAIN, LEGACY_DOMAIN)", "(DOMAIN, *SERVICE_ALIAS_DOMAINS)")
init_path.write_text(init, encoding="utf-8")

migration = r'''"""Safe one-click migration from every previous Home Environment Manager domain."""
from __future__ import annotations
from typing import Any

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, LEGACY_DOMAIN, LEGACY_DOMAINS


def legacy_entries(hass: Any) -> list[Any]:
    entries = []
    for domain in LEGACY_DOMAINS:
        entries.extend(hass.config_entries.async_entries(domain))
    return entries


def _new_identifiers(identifiers, source_domain: str):
    return {(DOMAIN if domain == source_domain else domain, value)
            for domain, value in identifiers}


async def async_migrate_legacy_registry(hass: Any, legacy: Any, new: Any) -> None:
    from homeassistant.config_entries import ConfigEntryState
    from homeassistant.helpers import device_registry as dr, entity_registry as er

    source_domain = legacy.domain
    if source_domain not in LEGACY_DOMAINS or new.domain != DOMAIN:
        raise HomeAssistantError("Unexpected domain migration endpoints")
    if legacy.entry_id == new.entry_id:
        raise HomeAssistantError("Domain migration requires a distinct config entry")
    if legacy.state is ConfigEntryState.LOADED:
        if not await hass.config_entries.async_unload(legacy.entry_id):
            raise HomeAssistantError("Could not unload legacy Environment Manager entry")

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    devices = list(dr.async_entries_for_config_entry(dev_reg, legacy.entry_id))
    entities = list(er.async_entries_for_config_entry(ent_reg, legacy.entry_id))
    devices.sort(key=lambda d: bool(getattr(d, "parent_device_id", None)))
    moved_devices = []
    moved_entities = []
    try:
        for entity in entities:
            ent_reg.async_update_entity_platform(
                entity.entity_id, DOMAIN,
                new_config_entry_id=new.entry_id,
                new_config_subentry_id=entity.config_subentry_id,
            )
            moved_entities.append((entity.entity_id, entity.config_subentry_id))
        for device in devices:
            old_ids = set(device.identifiers)
            dev_reg.async_update_device(
                device.id,
                new_config_entry_id=new.entry_id,
                new_config_subentry_id=device.config_subentry_id,
                new_identifiers=_new_identifiers(old_ids, source_domain),
            )
            moved_devices.append((device.id, old_ids, device.config_subentry_id))
        await hass.config_entries.async_remove(legacy.entry_id)
    except Exception:
        if hass.config_entries.async_get_entry(legacy.entry_id) is not None:
            for device_id, old_ids, subentry_id in reversed(moved_devices):
                try:
                    dev_reg.async_update_device(
                        device_id,
                        new_config_entry_id=legacy.entry_id,
                        new_config_subentry_id=subentry_id,
                        new_identifiers=old_ids,
                    )
                except Exception:
                    pass
            for entity_id, subentry_id in reversed(moved_entities):
                try:
                    ent_reg.async_update_entity_platform(
                        entity_id, source_domain,
                        new_config_entry_id=legacy.entry_id,
                        new_config_subentry_id=subentry_id,
                    )
                except Exception:
                    pass
        raise


def _migration_markers(entry: Any) -> list[tuple[str, str]]:
    data = getattr(entry, "data", {}) if entry is not None else {}
    if not isinstance(data, dict):
        return []
    markers = []
    entry_id = data.get("_legacy_entry_id")
    domain = data.get("_legacy_domain")
    if isinstance(entry_id, str) and entry_id:
        markers.append((domain if domain in LEGACY_DOMAINS else LEGACY_DOMAIN, entry_id))
    chain = data.get("_legacy_entry_chain")
    if isinstance(chain, list):
        for item in chain:
            if not isinstance(item, dict):
                continue
            item_id = item.get("entry_id")
            item_domain = item.get("domain")
            if isinstance(item_id, str) and item_id and item_domain in LEGACY_DOMAINS:
                marker = (item_domain, item_id)
                if marker not in markers:
                    markers.append(marker)
    return markers


async def async_open_migrated_store(hass: Any, version: int, suffix: str, entry_or_id: Any):
    from homeassistant.helpers.storage import Store

    entry = entry_or_id if hasattr(entry_or_id, "entry_id") else None
    entry_id = getattr(entry_or_id, "entry_id", entry_or_id)
    if not isinstance(entry_id, str) or not entry_id:
        raise HomeAssistantError("Missing Environment Manager config entry identity")
    store = Store(hass, version, f"{DOMAIN}.{suffix}_{entry_id}")
    loaded = await store.async_load()
    if loaded is not None:
        return store, loaded
    if entry is None:
        entries = getattr(hass, "config_entries", None)
        getter = getattr(entries, "async_get_entry", None)
        if getter is not None:
            entry = getter(entry_id)
    for legacy_domain, legacy_id in _migration_markers(entry):
        legacy = Store(hass, version, f"{legacy_domain}.{suffix}_{legacy_id}")
        loaded = await legacy.async_load()
        if loaded is not None:
            await store.async_save(loaded)
            return store, loaded
    return store, None
'''
(PKG / "domain_migration.py").write_text(migration, encoding="utf-8")

test = ROOT / "tests" / "test_beta20_regressions.py"
if test.exists():
    value = test.read_text(encoding="utf-8")
    value = value.replace(
        '    assert not (ROOT/"custom_components/environment_manager").exists()\n',
        '    assert not (ROOT/"custom_components/enviroment_manager").exists()\n',
        1,
    )
    test.write_text(value, encoding="utf-8")


# Tests that intentionally describe beta21 itself must keep the beta20 typo as
# legacy evidence while following the new release workflow.
distribution = ROOT / "tests" / "test_beta_distribution.py"
if distribution.exists():
    value = distribution.read_text(encoding="utf-8")
    value = value.replace(
        '.github/workflows/beta20-domain-runtime.yml',
        '.github/workflows/beta21-canonical-domain.yml',
    )
    distribution.write_text(value, encoding="utf-8")

lifecycle = ROOT / "tests" / "test_legacy_entry_lifecycle.py"
if lifecycle.exists():
    value = lifecycle.read_text(encoding="utf-8")
    marker = 'PUBLIC_ACTION_DOMAIN = "home_environment_manager"\n'
    if 'BETA20_DOMAIN = "enviroment_manager"' not in value:
        value = value.replace(marker, marker + 'BETA20_DOMAIN = "enviroment_manager"\n', 1)
    value = value.replace(
        '        f"/{LEGACY_DOMAIN}/air-quality-advisor-card.js",\n',
        '        f"/{BETA20_DOMAIN}/air-quality-advisor-card.js",\n'
        '        f"/{LEGACY_DOMAIN}/air-quality-advisor-card.js",\n',
        1,
    )
    value = value.replace(
        'for domain in (CANONICAL_DOMAIN,PUBLIC_ACTION_DOMAIN,LEGACY_DOMAIN)',
        'for domain in (CANONICAL_DOMAIN,PUBLIC_ACTION_DOMAIN,BETA20_DOMAIN,LEGACY_DOMAIN)',
    )
    value = value.replace('assert len(h.services.registered)==12', 'assert len(h.services.registered)==16')
    value = value.replace('assert len(h.services.callbacks)==12', 'assert len(h.services.callbacks)==16')
    lifecycle.write_text(value, encoding="utf-8")


changelog = ROOT / "CHANGELOG.md"
if changelog.exists():
    value = changelog.read_text(encoding="utf-8")
    heading = "## 0.6.0b21 - Canonical environment_manager domain repair (beta)"
    if heading not in value:
        section = """## 0.6.0b21 - Canonical environment_manager domain repair (beta)

- Correct the beta20 `enviroment_manager` package/domain typo to canonical `environment_manager`.
- Migrate registry ownership from both `air_quality_advisor` and beta20 `enviroment_manager` while preserving entity/device IDs, subentries and user customizations.
- Preserve chained storage migration markers for beta19 -> beta20 -> beta21 and direct beta19 -> beta21 upgrades.
- Keep temporary service/card compatibility for the historical domains while making `environment_manager` authoritative.
- Preserve beta20 room-owned presets, room-wide limits, selected-room feedback and controller safety behavior.
- Validate both migration paths on installed Home Assistant 2026.10 before publishing.

"""
        value = value.replace("# Changelog\n\n", "# Changelog\n\n" + section, 1)
        changelog.write_text(value, encoding="utf-8")

manifest_path = PKG / "manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
manifest["domain"] = "environment_manager"
manifest["version"] = "0.6.0b21"
manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print("Applied beta21 canonical environment_manager domain repair")
