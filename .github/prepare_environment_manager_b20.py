"""Prepare the final environment_manager-domain source tree from beta19.

This transformation is intentionally staged and deterministic:
- HACS final source contains one component directory: environment_manager.
- Existing beta users rely on the already-published b19 bridge in their old
  local air_quality_advisor directory for the one-time config-entry handoff.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OLD = "air_quality_advisor"
NEW = "environment_manager"
OLD_DIR = ROOT / "custom_components" / OLD
NEW_DIR = ROOT / "custom_components" / NEW


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def replace(path: Path, old: str, new: str, *, count: int = -1) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected text not found in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new, count), encoding="utf-8")


def main() -> None:
    if NEW_DIR.exists() and not OLD_DIR.exists():
        print("environment_manager source already prepared")
        return
    if not OLD_DIR.is_dir() or NEW_DIR.exists():
        raise RuntimeError("Expected exactly the beta19 legacy component directory")
    manifest = json.loads((OLD_DIR / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("domain") != OLD or manifest.get("version") != "0.6.0b19":
        raise RuntimeError(f"Expected published b19 bridge baseline, got {manifest!r}")

    run("git", "mv", str(OLD_DIR.relative_to(ROOT)), str(NEW_DIR.relative_to(ROOT)))
    migration = NEW_DIR / "domain_migration.py"
    if not migration.is_file():
        raise RuntimeError("b19 bridge module missing")
    migration.unlink()
    legacy_verifier = ROOT / "tools" / "verify_domain_bridge_ha.py"
    if legacy_verifier.exists():
        legacy_verifier.unlink()

    # Repository Python/tests/workflows should follow the new package path.
    # Do not blanket-replace component source: old storage keys and compatibility
    # aliases deliberately retain the legacy string.
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or NEW_DIR in path.parents:
            continue
        if path.suffix.lower() not in {".py", ".yml", ".yaml", ".json", ".md"}:
            continue
        text = path.read_text(encoding="utf-8")
        text = text.replace("custom_components.air_quality_advisor", "custom_components.environment_manager")
        text = text.replace("custom_components/air_quality_advisor", "custom_components/environment_manager")
        if path.suffix == ".py":
            # Tests and repository utilities now exercise the real new domain.
            text = text.replace('"air_quality_advisor"', '"environment_manager"')
            text = text.replace("'air_quality_advisor'", "'environment_manager'")
        path.write_text(text, encoding="utf-8")

    # Actual integration domain.
    const = NEW_DIR / "const.py"
    text = const.read_text(encoding="utf-8")
    marker = 'DOMAIN = "air_quality_advisor"\n'
    if marker not in text:
        raise RuntimeError("DOMAIN constant baseline changed")
    text = text.replace(
        marker,
        'DOMAIN = "environment_manager"\n'
        'LEGACY_DOMAIN = "air_quality_advisor"\n'
        '# Safety/ownership/history stores keep their legacy namespace so a domain\n'
        '# migration cannot lose restart state.\n'
        'STORAGE_DOMAIN = LEGACY_DOMAIN\n',
        1,
    )
    const.write_text(text, encoding="utf-8")

    manifest_path = NEW_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["domain"] = NEW
    manifest["version"] = "0.6.0b20"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    # The two Store keys which used the dynamic DOMAIN must remain on the legacy
    # storage namespace. Other controller stores already use literal legacy keys.
    manager = NEW_DIR / "manager.py"
    text = manager.read_text(encoding="utf-8")
    text = text.replace(
        "DEFAULT_THRESHOLDS, DOMAIN, SIGNAL_UPDATED, CONF_USE_MOLD, CONF_MOLD_ROOMS,",
        "DEFAULT_THRESHOLDS, DOMAIN, STORAGE_DOMAIN, SIGNAL_UPDATED, CONF_USE_MOLD, CONF_MOLD_ROOMS,",
    )
    text = text.replace(
        'f"{DOMAIN}.environment_history_{self.entry.entry_id}"',
        'f"{STORAGE_DOMAIN}.environment_history_{self.entry.entry_id}"',
    )
    manager.write_text(text, encoding="utf-8")

    runtime = NEW_DIR / "equipment_runtime.py"
    text = runtime.read_text(encoding="utf-8")
    text = text.replace(
        "from .const import DOMAIN, SIGNAL_UPDATED, CONF_EXCLUDED_INDOOR",
        "from .const import DOMAIN, STORAGE_DOMAIN, SIGNAL_UPDATED, CONF_EXCLUDED_INDOOR",
    )
    text = text.replace(
        'f"{DOMAIN}.equipment_{self.manager.entry.entry_id}"',
        'f"{STORAGE_DOMAIN}.equipment_{self.manager.entry.entry_id}"',
    )
    runtime.write_text(text, encoding="utf-8")

    # Final integration no longer runs the old bridge; the already-installed b19
    # directory owns migration. Add legacy service/static aliases here.
    init = NEW_DIR / "__init__.py"
    text = init.read_text(encoding="utf-8")
    text = text.replace(
        'from .const import DOMAIN, PLATFORMS, LANGUAGES',
        'from .const import DOMAIN, LEGACY_DOMAIN, PLATFORMS, LANGUAGES',
    )
    text = text.replace(
        'PUBLIC_ACTION_DOMAIN = "home_environment_manager"  # Alias only; existing domain remains.',
        'PUBLIC_ACTION_DOMAIN = "home_environment_manager"  # Historical public alias.\\n'
        'SERVICE_DOMAINS = (DOMAIN, LEGACY_DOMAIN, PUBLIC_ACTION_DOMAIN)',
    )
    bridge_setup = '''    from .domain_migration import (
        async_new_domain_available, async_schedule_domain_migration,
    )
    # Bridge release: when the later environment_manager package exists, do
    # not load any old-domain platforms. Schedule in-place migration after
    # this setup lock is released so entity registry platform migration is safe.
    if await async_new_domain_available(hass):
        async_schedule_domain_migration(hass, entry)
        return True

'''
    if bridge_setup not in text:
        raise RuntimeError("b19 setup bridge block missing")
    text = text.replace(bridge_setup, "", 1)
    bridge_unload = '''    from .domain_migration import is_domain_migration_stub
    if is_domain_migration_stub(hass, entry.entry_id):
        return True
'''
    if bridge_unload not in text:
        raise RuntimeError("b19 unload bridge block missing")
    text = text.replace(bridge_unload, "", 1)

    static_old = '''    await hass.http.async_register_static_paths([
        StaticPathConfig(f"/{DOMAIN}/air-quality-advisor-card.js", str(card_path), True),
    ])
'''
    static_new = '''    await hass.http.async_register_static_paths([
        StaticPathConfig(f"/{DOMAIN}/air-quality-advisor-card.js", str(card_path), True),
        # Existing dashboards/browser caches may still reference the legacy URL.
        StaticPathConfig(f"/{LEGACY_DOMAIN}/air-quality-advisor-card.js", str(card_path), True),
    ])
'''
    if static_old not in text:
        raise RuntimeError("static path block changed")
    text = text.replace(static_old, static_new, 1)
    text = text.replace(
        "    # Bundled asset and HACS release version share ONE authoritative source.\\n"
        "    # Rebranding must not change the original integration domain/path.\\n",
        "    # Bundled asset and HACS release version share one authoritative source.\\n",
        1,
    )

    announce_old = '''        hass.services.async_register(
            DOMAIN, "announce", async_announce_action,
            schema=SERVICE_SCHEMA, supports_response=SupportsResponse.OPTIONAL,
        )
        # A user-facing service alias for the rebrand. Both service domains
        # intentionally call the same manager: no duplicate announcements.
        if not hass.services.has_service(PUBLIC_ACTION_DOMAIN, "announce"):
            hass.services.async_register(
                PUBLIC_ACTION_DOMAIN, "announce", async_announce_action,
                schema=SERVICE_SCHEMA, supports_response=SupportsResponse.OPTIONAL,
            )
'''
    announce_new = '''        for service_domain in SERVICE_DOMAINS:
            if not hass.services.has_service(service_domain, "announce"):
                hass.services.async_register(
                    service_domain, "announce", async_announce_action,
                    schema=SERVICE_SCHEMA,
                    supports_response=SupportsResponse.OPTIONAL,
                )
'''
    if announce_old not in text:
        raise RuntimeError("announce registration block changed")
    text = text.replace(announce_old, announce_new, 1)
    text = text.replace(
        'if not hass.services.has_service(PUBLIC_ACTION_DOMAIN, "pid_control"):',
        'if any(not hass.services.has_service(d, "pid_control") for d in SERVICE_DOMAINS):',
        1,
    )
    text = text.replace(
        "for service_domain in (PUBLIC_ACTION_DOMAIN, DOMAIN):",
        "for service_domain in SERVICE_DOMAINS:",
        1,
    )
    text = text.replace(
        'if not hass.services.has_service(PUBLIC_ACTION_DOMAIN, "climate_control"):',
        'if any(not hass.services.has_service(d, "climate_control") for d in SERVICE_DOMAINS):',
        1,
    )
    text = text.replace("for domain in (DOMAIN,PUBLIC_ACTION_DOMAIN):", "for domain in SERVICE_DOMAINS:", 1)
    text = text.replace(
        'if not hass.services.has_service(PUBLIC_ACTION_DOMAIN, "climate_diagnostics"):',
        'if any(not hass.services.has_service(d, "climate_diagnostics") for d in SERVICE_DOMAINS):',
        1,
    )
    text = text.replace("for domain in (DOMAIN, PUBLIC_ACTION_DOMAIN):", "for domain in SERVICE_DOMAINS:", 1)

    unload_old = '''        hass.services.async_remove(DOMAIN, "announce")
        if hass.services.has_service(PUBLIC_ACTION_DOMAIN, "announce"):
            hass.services.async_remove(PUBLIC_ACTION_DOMAIN, "announce")
        for service_domain in (PUBLIC_ACTION_DOMAIN, DOMAIN):
            if hass.services.has_service(service_domain, "pid_control"):
                hass.services.async_remove(service_domain, "pid_control")
            if hass.services.has_service(service_domain, "climate_control"):
                hass.services.async_remove(service_domain, "climate_control")
            if hass.services.has_service(service_domain, "climate_diagnostics"):
                hass.services.async_remove(service_domain, "climate_diagnostics")
'''
    unload_new = '''        for service_domain in SERVICE_DOMAINS:
            for service in (
                "announce", "pid_control", "climate_control", "climate_diagnostics"
            ):
                if hass.services.has_service(service_domain, service):
                    hass.services.async_remove(service_domain, service)
'''
    if unload_old not in text:
        raise RuntimeError("service unload block changed")
    text = text.replace(unload_old, unload_new, 1)

    # Schedule orphan legacy-directory cleanup only after the new entry has
    # successfully set up all platforms.
    return_marker = "    return True\\n\\n\\nasync def async_unload_entry"
    if return_marker not in text:
        raise RuntimeError("setup return marker changed")
    text = text.replace(
        return_marker,
        '''    from .legacy_cleanup import async_schedule_legacy_directory_cleanup
    async_schedule_legacy_directory_cleanup(hass, entry.entry_id)
    return True


async def async_unload_entry''',
        1,
    )
    init.write_text(text, encoding="utf-8")

    cleanup = NEW_DIR / "legacy_cleanup.py"
    cleanup.write_text(
        '''"""Remove the orphan b19 legacy directory only after new-domain setup succeeds."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import shutil

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import DOMAIN, LEGACY_DOMAIN


def async_schedule_legacy_directory_cleanup(hass: HomeAssistant, entry_id: str) -> None:
    hass.async_create_background_task(
        _async_cleanup(hass, entry_id),
        name=f"remove migrated {LEGACY_DOMAIN} custom-component directory",
    )


async def _async_cleanup(hass: HomeAssistant, entry_id: str) -> None:
    # Let the b19 bridge task return from async_setup(new entry) first.
    for _ in range(20):
        await asyncio.sleep(0.1)
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is not None and entry.domain == DOMAIN and entry.state is ConfigEntryState.LOADED:
            break
    else:
        return

    new_dir = Path(__file__).resolve().parent
    legacy_dir = new_dir.parent / LEGACY_DOMAIN
    if not legacy_dir.is_dir() or legacy_dir.is_symlink():
        return
    if new_dir.parent.resolve() != legacy_dir.parent.resolve():
        return
    manifest_path = legacy_dir / "manifest.json"
    bridge_path = legacy_dir / "domain_migration.py"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return
    # Never delete an arbitrary/older integration folder. Only the published
    # b19 bridge is eligible for automatic cleanup.
    if manifest.get("domain") != LEGACY_DOMAIN or manifest.get("version") != "0.6.0b19":
        return
    if not bridge_path.is_file():
        return
    await hass.async_add_executor_job(shutil.rmtree, legacy_dir)
''',
        encoding="utf-8",
    )

    # Final package-path/domain expectations in repository Python sources.
    # Outside the component, all active Python code should target the new domain.
    for path in ROOT.rglob("*.py"):
        if ".git" in path.parts or path == Path(__file__):
            continue
        if NEW_DIR in path.parents:
            continue
        text = path.read_text(encoding="utf-8")
        text = text.replace("air_quality_advisor", "environment_manager")
        path.write_text(text, encoding="utf-8")

    # Recreate the final migration verifier after the broad repository rewrite.
    verifier = ROOT / "tools" / "verify_domain_switch_ha.py"
    verifier.write_text(FINAL_VERIFIER, encoding="utf-8")

    # The legacy bridge verifier references a package that no longer exists.
    old_verify = ROOT / "tools" / "verify_domain_bridge_ha.py"
    if old_verify.exists():
        old_verify.unlink()

    # Regenerate from the new component path.
    subprocess.run([sys.executable, "generate_translations.py"], cwd=ROOT, check=True)

    # Fail loudly on unexpected legacy-domain source references. These are the
    # only intentional ones left inside the new component: compatibility,
    # preserved Store namespaces and legacy frontend/storage keys.
    allowed = (
        "LEGACY_DOMAIN",
        "STORAGE_DOMAIN",
        "air_quality_advisor.pid_",
        "air_quality_advisor.climate_native_",
        "air_quality_advisor.direct_",
        "air_quality_advisor.fan_power_",
        "air_quality_advisor.humidity_power_",
        "air_quality_advisor.running_fan_",
        "air_quality_advisor-card",
    )
    unexpected = []
    for path in NEW_DIR.rglob("*"):
        if not path.is_file() or path.suffix not in {".py", ".js", ".json", ".yaml", ".md"}:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if OLD in line and not any(token in line for token in allowed):
                unexpected.append(f"{path.relative_to(ROOT)}:{lineno}:{line.strip()}")
    if unexpected:
        raise RuntimeError("Unexpected legacy-domain references:\\n" + "\\n".join(unexpected))

    run("git", "add", "-A")
    print("environment_manager domain source prepared")


FINAL_VERIFIER = r'''"""Real HA 2026.10 check for b19 -> environment_manager identity handoff."""
from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import MappingProxyType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from homeassistant import loader
from homeassistant.config_entries import ConfigEntries, ConfigEntry, ConfigSubentry, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er

from custom_components.environment_manager.const import DOMAIN
from custom_components.environment_manager.device_hierarchy import async_register_hierarchy

OLD = "air_quality_advisor"
NEW = "environment_manager"


def load_bridge():
    source = subprocess.check_output(
        ["git", "show", "v0.6.0b19:custom_components/air_quality_advisor/domain_migration.py"],
        cwd=ROOT,
        text=True,
    )
    path = ROOT / ".domain_bridge_b19_test.py"
    path.write_text(source, encoding="utf-8")
    try:
        spec = importlib.util.spec_from_file_location("domain_bridge_b19_test", path)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module
    finally:
        path.unlink(missing_ok=True)


async def check(config_dir: str) -> None:
    assert DOMAIN == NEW
    hass = HomeAssistant(config_dir)
    hass.config_entries = ConfigEntries(hass, {})
    dr.async_setup(hass)
    await ar.async_load(hass)
    await dr.async_load(hass)
    await er.async_load(hass)
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    areas = ar.async_get(hass)
    room = areas.async_create("Living room")

    sub = ConfigSubentry(
        data=MappingProxyType({"area_id": room.id}),
        subentry_id="stable-room-subentry",
        subentry_type="room",
        title="Living room",
        unique_id=room.id,
    )
    old = ConfigEntry(
        data={"areas": [room.id]},
        options={"language": "el"},
        domain=OLD,
        entry_id="stable-entry-id",
        title="Home Environment Manager",
        source=SOURCE_USER,
        unique_id="home",
        version=1,
        minor_version=0,
        discovery_keys=MappingProxyType({}),
        subentries_data=(sub.as_dict(),),
    )
    hass.config_entries._entries[old.entry_id] = old

    device = devices.async_get_or_create(
        config_entry_id=old.entry_id,
        config_subentry_id=sub.subentry_id,
        identifiers={(OLD, old.entry_id)},
        name="Home",
    )
    devices.async_update_device(device.id, name_by_user="My Home", area_id=room.id)
    entity = entities.async_get_or_create(
        "number", OLD, "stable-limit",
        config_entry=old,
        config_subentry_id=sub.subentry_id,
        device_id=device.id,
        suggested_object_id="stable_limit",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    entities.async_update_entity(entity.entity_id, name="My limit", icon="mdi:thermometer")

    entity_id, entity_registry_id, device_id = entity.entity_id, entity.id, device.id
    bridge = load_bridge()
    integration = await loader.async_get_integration(hass, NEW)
    assert integration.domain == NEW
    bridge._preflight_registry_migration(hass, old.entry_id)
    replacement = bridge._copy_entry_with_new_domain(old)
    bridge._migrate_registries(hass, old.entry_id)
    del hass.config_entries._entries[old.entry_id]
    hass.config_entries._entries[replacement.entry_id] = replacement

    migrated = entities.async_get(entity_id)
    migrated_device = devices.async_get(device_id)
    assert replacement.entry_id == old.entry_id and replacement.domain == NEW
    assert list(replacement.subentries) == [sub.subentry_id]
    assert migrated.id == entity_registry_id and migrated.entity_id == entity_id
    assert migrated.unique_id == "stable-limit" and migrated.platform == NEW
    assert migrated.config_entry_id == old.entry_id
    assert migrated.config_subentry_id == sub.subentry_id
    assert migrated.device_id == device_id
    assert migrated.disabled_by == er.RegistryEntryDisabler.USER
    assert migrated.name == "My limit" and migrated.icon == "mdi:thermometer"
    assert migrated_device.id == device_id and (NEW, old.entry_id) in migrated_device.identifiers
    assert all(domain != OLD for domain, _ in migrated_device.identifiers)
    assert migrated_device.name_by_user == "My Home" and migrated_device.area_id == room.id

    # New hierarchy must reuse the migrated Home device, not create a duplicate.
    manager = SimpleNamespace(
        hass=hass,
        entry=replacement,
        settings={**replacement.data, **replacement.options},
        _room_subentries={room.id: sub.subentry_id},
        _home_subentry=None,
    )
    replacement.runtime_data = manager
    before = {d.id for d in dr.async_entries_for_config_entry(devices, old.entry_id)}
    async_register_hierarchy(hass, replacement)
    after = {d.id for d in dr.async_entries_for_config_entry(devices, old.entry_id)}
    assert device_id in after
    assert len(after) >= len(before)
    home_id = manager._device_hierarchy["home_device_id"]
    assert home_id == device_id

    await hass.async_stop(force=True)
    print("HA 2026.10 b19 -> environment_manager identity handoff: PASS")


if __name__ == "__main__":
    with TemporaryDirectory(prefix="hem-domain-switch-") as directory:
        asyncio.run(check(directory))
'''


if __name__ == "__main__":
    main()
