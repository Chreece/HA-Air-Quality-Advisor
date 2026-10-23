"""Build the beta19 environment_manager domain migration candidate.

One-use staging helper. It renames the only HACS-managed integration, patches
canonical domain references, adds a one-click registry migration from the frozen
legacy config-entry domain, preserves legacy service/card aliases, and adds
migration-safe storage loading. It is removed from the final source tree.
"""
from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
OLD="air_quality_advisor"
NEW="environment_manager"
OLD_DIR=ROOT/"custom_components"/OLD
NEW_DIR=ROOT/"custom_components"/NEW

def git(*args):
    return subprocess.run(["git",*args],cwd=ROOT,check=True,capture_output=True,text=True).stdout

def replace(path: Path, old: str, new: str, *, count: int=-1):
    text=path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Missing patch anchor in {path}: {old[:80]!r}")
    path.write_text(text.replace(old,new,count),encoding="utf-8")

def main():
    if not OLD_DIR.is_dir() or NEW_DIR.exists():
        raise RuntimeError("Expected beta18 legacy integration directory only")
    subprocess.run(["git","mv",str(OLD_DIR.relative_to(ROOT)),str(NEW_DIR.relative_to(ROOT))],cwd=ROOT,check=True)

    # Canonical imports/paths/domain literals throughout active code and tests.
    targets=[NEW_DIR,*[p for p in (ROOT/"tests").glob("*.py")],
             *[p for p in (ROOT/"tools").glob("*.py")],
             *[p for p in ROOT.glob("*.py")],
             ROOT/"README.md",ROOT/"RELEASING.md",ROOT/"CHANGELOG.md"]
    targets += list((ROOT/".github"/"workflows").glob("*.yml"))
    for item in targets:
        paths=item.rglob("*") if item.is_dir() else [item]
        for path in paths:
            if not path.is_file() or path.suffix.lower() not in {".py",".json",".yaml",".yml",".js",".md"}:
                continue
            text=path.read_text(encoding="utf-8")
            text=text.replace("custom_components.air_quality_advisor","custom_components.environment_manager")
            text=text.replace("custom_components/air_quality_advisor","custom_components/environment_manager")
            text=text.replace('"air_quality_advisor"','"environment_manager"')
            text=text.replace("'air_quality_advisor'","'environment_manager'")
            path.write_text(text,encoding="utf-8")

    const=NEW_DIR/"const.py"
    replace(const,'DOMAIN = "environment_manager"\n',
            'DOMAIN = "environment_manager"\nLEGACY_DOMAIN = "air_quality_advisor"\nLEGACY_PUBLIC_ACTION_DOMAIN = "home_environment_manager"\n')

    # Registry/config-entry migration helper.
    (NEW_DIR/"domain_migration.py").write_text(r'''"""Safe one-click migration from the frozen legacy HA config-entry domain."""
from __future__ import annotations
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN, LEGACY_DOMAIN


def legacy_entries(hass: Any) -> list[ConfigEntry]:
    return list(hass.config_entries.async_entries(LEGACY_DOMAIN))


def _new_identifiers(identifiers):
    return {(DOMAIN if domain == LEGACY_DOMAIN else domain, value)
            for domain, value in identifiers}


async def async_migrate_legacy_registry(
    hass: Any, legacy: ConfigEntry, new: ConfigEntry
) -> None:
    """Move registry ownership first; remove legacy entry only after success."""
    if legacy.domain != LEGACY_DOMAIN or new.domain != DOMAIN:
        raise HomeAssistantError("Unexpected domain migration endpoints")
    if legacy.entry_id == new.entry_id:
        raise HomeAssistantError("Domain migration requires a distinct config entry")

    if legacy.state is ConfigEntryState.LOADED:
        if not await hass.config_entries.async_unload(legacy.entry_id):
            raise HomeAssistantError("Could not unload legacy Environment Manager entry")

    dev_reg=dr.async_get(hass)
    ent_reg=er.async_get(hass)
    devices=list(dr.async_entries_for_config_entry(dev_reg, legacy.entry_id))
    entities=list(er.async_entries_for_config_entry(ent_reg, legacy.entry_id))

    # Parent/main devices first so child references remain valid.
    devices.sort(key=lambda d: bool(getattr(d,"parent_device_id",None)))
    moved_devices=[]
    moved_entities=[]
    try:
        for device in devices:
            old_ids=set(device.identifiers)
            dev_reg.async_update_device(
                device.id,
                new_config_entry_id=new.entry_id,
                new_config_subentry_id=device.config_subentry_id,
                new_identifiers=_new_identifiers(old_ids),
            )
            moved_devices.append((device.id,old_ids,device.config_subentry_id))

        for entity in entities:
            ent_reg.async_update_entity_platform(
                entity.entity_id,
                DOMAIN,
                new_config_entry_id=new.entry_id,
                new_config_subentry_id=entity.config_subentry_id,
            )
            moved_entities.append((entity.entity_id,entity.config_subentry_id))

        # Cleanup no longer touches migrated registries because ownership moved.
        await hass.config_entries.async_remove(legacy.entry_id)
    except Exception:
        # Best-effort rollback while the legacy entry still exists.
        if hass.config_entries.async_get_entry(legacy.entry_id) is not None:
            for entity_id,subentry_id in reversed(moved_entities):
                try:
                    ent_reg.async_update_entity_platform(
                        entity_id, LEGACY_DOMAIN,
                        new_config_entry_id=legacy.entry_id,
                        new_config_subentry_id=subentry_id,
                    )
                except Exception:
                    pass
            for device_id,old_ids,subentry_id in reversed(moved_devices):
                try:
                    dev_reg.async_update_device(
                        device_id,
                        new_config_entry_id=legacy.entry_id,
                        new_config_subentry_id=subentry_id,
                        new_identifiers=old_ids,
                    )
                except Exception:
                    pass
        raise


async def async_open_migrated_store(hass: Any, version: int, suffix: str, entry: ConfigEntry):
    """Open canonical store, importing the matching legacy-entry store once."""
    from homeassistant.helpers.storage import Store
    store=Store(hass,version,f"{DOMAIN}.{suffix}_{entry.entry_id}")
    loaded=await store.async_load()
    if loaded is not None:
        return store,loaded
    legacy_id=entry.data.get("_legacy_entry_id")
    if not isinstance(legacy_id,str) or not legacy_id:
        return store,None
    legacy=Store(hass,version,f"{LEGACY_DOMAIN}.{suffix}_{legacy_id}")
    loaded=await legacy.async_load()
    if loaded is not None:
        await store.async_save(loaded)
    return store,loaded
''',encoding="utf-8")

    # Config flow: detect old entries and offer a one-click migration.
    flow=NEW_DIR/"config_flow.py"
    text=flow.read_text(encoding="utf-8")
    text=text.replace(
        "    DEFAULT_THRESHOLDS, DOMAIN, CONF_USE_MOLD, CONF_MOLD_ROOMS,",
        "    DEFAULT_THRESHOLDS, DOMAIN, LEGACY_DOMAIN, CONF_USE_MOLD, CONF_MOLD_ROOMS,"
    )
    old='''    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        # Show the first setup form without reserving our static unique ID.
'''
    new='''    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        legacy = self.hass.config_entries.async_entries(LEGACY_DOMAIN)
        if len(legacy) > 1:
            return self.async_abort(reason="legacy_migration_ambiguous")
        if len(legacy) == 1:
            self._legacy_entry_id = legacy[0].entry_id
            return await self.async_step_migrate_legacy()
        # Show the first setup form without reserving our static unique ID.
'''
    if old not in text: raise RuntimeError("config flow user anchor")
    text=text.replace(old,new)
    # Remove now-duplicate old current-entry check from user body.
    text=text.replace('''        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        self._editing = False
''','''        self._editing = False
''',1)
    marker='''    async def _finish(self) -> ConfigFlowResult:
        # A stale, unfinished setup flow must not prevent a fresh attempt
'''
    migrate=r'''    async def async_step_migrate_legacy(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        legacy_id=getattr(self,"_legacy_entry_id",None)
        legacy=self.hass.config_entries.async_get_entry(legacy_id) if legacy_id else None
        if legacy is None or legacy.domain != LEGACY_DOMAIN:
            return self.async_abort(reason="legacy_migration_missing")
        if user_input is None:
            return self.async_show_form(
                step_id="migrate_legacy",
                data_schema=probatio.Schema({
                    probatio.Required("confirm",default=True): selector.BooleanSelector()
                }),
                last_step=True,
            )
        if user_input.get("confirm") is not True:
            return self.async_abort(reason="legacy_migration_cancelled")
        await self.async_set_unique_id("home", raise_on_progress=False)
        self._abort_if_unique_id_configured()
        self._migrating_legacy_entry_id=legacy.entry_id
        data=dict(legacy.data)
        data["_legacy_entry_id"]=legacy.entry_id
        subentries=[sub.as_dict() for sub in legacy.subentries.values()]
        return self.async_create_entry(
            title="Home Environment Manager",
            data=data,
            options=dict(legacy.options),
            subentries=subentries,
        )

    async def async_on_create_entry(self, result: ConfigFlowResult) -> ConfigFlowResult:
        legacy_id=getattr(self,"_migrating_legacy_entry_id",None)
        if legacy_id:
            legacy=self.hass.config_entries.async_get_entry(legacy_id)
            if legacy is None:
                raise RuntimeError("Legacy entry vanished during domain migration")
            from .domain_migration import async_migrate_legacy_registry
            await async_migrate_legacy_registry(self.hass,legacy,result["result"])
        return result

'''
    if marker not in text: raise RuntimeError("config flow finish anchor")
    text=text.replace(marker,migrate+marker)
    flow.write_text(text,encoding="utf-8")

    # Storage migration for safety/history state.
    runtime=NEW_DIR/"equipment_runtime.py"
    text=runtime.read_text(encoding="utf-8")
    old='''            from homeassistant.helpers.storage import Store
            self._store = Store(self.hass, 1, f"{DOMAIN}.equipment_{self.manager.entry.entry_id}")
            saved = await self._store.async_load()
'''
    new='''            from .domain_migration import async_open_migrated_store
            self._store, saved = await async_open_migrated_store(
                self.hass, 1, "equipment", self.manager.entry
            )
'''
    if old not in text: raise RuntimeError("equipment store anchor")
    runtime.write_text(text.replace(old,new),encoding="utf-8")

    manager=NEW_DIR/"manager.py"
    text=manager.read_text(encoding="utf-8")
    old='''            from homeassistant.helpers.storage import Store
            self._environment_store = Store(
                self.hass, 1, f"{DOMAIN}.environment_history_{self.entry.entry_id}",
            )
            stored = await self._environment_store.async_load()
'''
    new='''            from .domain_migration import async_open_migrated_store
            self._environment_store, stored = await async_open_migrated_store(
                self.hass, 1, "environment_history", self.entry
            )
'''
    if old not in text: raise RuntimeError("history store anchor")
    manager.write_text(text.replace(old,new),encoding="utf-8")

    for filename,suffix,old_snippet in (
        ("climate_pid.py","pid", 'self._store = Store(self.hass, 1, f"air_quality_advisor.pid_{self.entry_id}")\n            data = await self._store.async_load()'),
        ("climate_fan_power.py","fan_power", 'self._store = Store(\n                self.hass, 1,\n                f"air_quality_advisor.fan_power_{self.entry_id}",\n            )\n            saved = await self._store.async_load()'),
        ("climate_humidity_power.py","humidity_power", 'self._store = Store(self.hass, 1,\n                f"air_quality_advisor.humidity_power_{self.entry_id}")\n            loaded = await self._store.async_load()'),
    ):
        path=NEW_DIR/filename
        text=path.read_text(encoding="utf-8")
        if old_snippet not in text:
            raise RuntimeError(f"store anchor missing: {filename}")
        # These legacy coordinators have entry_id only; migration marker is looked
        # up from the actual config entry.
        result_name = "data" if filename=="climate_pid.py" else "saved" if filename=="climate_fan_power.py" else "loaded"
        replacement=f'''from .domain_migration import async_open_migrated_store
            entry = self.hass.config_entries.async_get_entry(self.entry_id)
            if entry is None:
                raise RuntimeError("Missing Environment Manager config entry")
            self._store, {result_name} = await async_open_migrated_store(
                self.hass, 1, "{suffix}", entry
            )'''
        text=text.replace(old_snippet,replacement)
        path.write_text(text,encoding="utf-8")

    # Canonical domain + compatibility aliases/static URL.
    init=NEW_DIR/"__init__.py"
    text=init.read_text(encoding="utf-8")
    text=text.replace("from .const import DOMAIN, PLATFORMS, LANGUAGES",
                      "from .const import DOMAIN, LEGACY_DOMAIN, LEGACY_PUBLIC_ACTION_DOMAIN, PLATFORMS, LANGUAGES")
    text=text.replace('PUBLIC_ACTION_DOMAIN = "home_environment_manager"  # Alias only; existing domain remains.',
                      'PUBLIC_ACTION_DOMAIN = LEGACY_PUBLIC_ACTION_DOMAIN  # compatibility alias')
    text=text.replace(
        '''    await hass.http.async_register_static_paths([
        StaticPathConfig(f"/{DOMAIN}/air-quality-advisor-card.js", str(card_path), True),
    ])''',
        '''    await hass.http.async_register_static_paths([
        StaticPathConfig(f"/{DOMAIN}/air-quality-advisor-card.js", str(card_path), True),
        StaticPathConfig(f"/{LEGACY_DOMAIN}/air-quality-advisor-card.js", str(card_path), True),
    ])'''
    )
    text=text.replace("for service_domain in (PUBLIC_ACTION_DOMAIN, DOMAIN):",
                      "for service_domain in (DOMAIN, PUBLIC_ACTION_DOMAIN, LEGACY_DOMAIN):")
    text=text.replace("for domain in (DOMAIN,PUBLIC_ACTION_DOMAIN):",
                      "for domain in (DOMAIN, PUBLIC_ACTION_DOMAIN, LEGACY_DOMAIN):")
    text=text.replace("for domain in (DOMAIN, PUBLIC_ACTION_DOMAIN):",
                      "for domain in (DOMAIN, PUBLIC_ACTION_DOMAIN, LEGACY_DOMAIN):")
    # announce has explicit registrations.
    text=text.replace('''        if not hass.services.has_service(PUBLIC_ACTION_DOMAIN, "announce"):
            hass.services.async_register(
                PUBLIC_ACTION_DOMAIN, "announce", async_announce_action,
                schema=SERVICE_SCHEMA, supports_response=SupportsResponse.OPTIONAL,
            )''',
        '''        for alias in (PUBLIC_ACTION_DOMAIN, LEGACY_DOMAIN):
            if not hass.services.has_service(alias, "announce"):
                hass.services.async_register(
                    alias, "announce", async_announce_action,
                    schema=SERVICE_SCHEMA, supports_response=SupportsResponse.OPTIONAL,
                )''')
    init.write_text(text,encoding="utf-8")

    # Localized migration text and new room profile names.
    gen=ROOT/"apply_device_controls_i18n.py"
    text=gen.read_text(encoding="utf-8")
    text=text.replace('for kind in ("home", "unoccupied", "away", "sleep"):',
                      'for kind in ("comfort", "home", "sleep", "eco"):')
    gen.write_text(text,encoding="utf-8")

    (ROOT/"apply_beta19_i18n.py").write_text(r'''"""Beta19 domain migration and room-preset labels."""
from __future__ import annotations
import json
from pathlib import Path

MIGRATION={
 "en":("Migrate Home Environment Manager","An existing Air Quality Advisor / Home Environment Manager installation was found. Migrate its rooms, devices, settings and registry identities to the new environment_manager domain.","Migrate existing installation"),
 "el":("Μεταφορά Home Environment Manager","Βρέθηκε υπάρχουσα εγκατάσταση. Μετέφερε δωμάτια, συσκευές, ρυθμίσεις και ταυτότητες registry στο νέο domain environment_manager.","Μεταφορά υπάρχουσας εγκατάστασης"),
 "de":("Home Environment Manager migrieren","Eine bestehende Installation wurde gefunden. Räume, Geräte, Einstellungen und Registry-Identitäten in die neue Domain environment_manager übernehmen.","Bestehende Installation migrieren"),
 "fr":("Migrer Home Environment Manager","Une installation existante a été trouvée. Migrer pièces, appareils, réglages et identités de registre vers le nouveau domaine environment_manager.","Migrer l’installation existante"),
 "es":("Migrar Home Environment Manager","Se encontró una instalación existente. Migra habitaciones, dispositivos, ajustes e identidades del registro al nuevo dominio environment_manager.","Migrar instalación existente"),
}
def apply_beta19_i18n(root:Path)->None:
    vocab=json.loads((root/"compact_locales.json").read_text(encoding="utf-8"))
    files=sorted((root/"translations").glob("*.json"))
    for path in [root/"strings.json",*files]:
        lang="en" if path.name=="strings.json" else path.stem
        doc=json.loads(path.read_text(encoding="utf-8"))
        title,desc,label=MIGRATION.get(lang,(
            f"Home Environment Manager · {vocab[lang]['settings']}",
            f"Home Environment Manager · environment_manager · {vocab[lang]['settings']}",
            f"{vocab[lang]['select']} · environment_manager",
        ))
        step=doc.setdefault("config",{}).setdefault("step",{}).setdefault("migrate_legacy",{})
        step["title"]=title; step["description"]=desc
        step.setdefault("data",{})["confirm"]=label
        abort=doc["config"].setdefault("abort",{})
        abort["legacy_migration_ambiguous"]="Multiple legacy entries were found; migration is blocked to avoid merging homes."
        abort["legacy_migration_missing"]="The legacy entry disappeared before migration."
        abort["legacy_migration_cancelled"]="Migration was cancelled."
        path.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
''',encoding="utf-8")
    gen=ROOT/"generate_translations.py"
    text=gen.read_text(encoding="utf-8")
    text += '\nfrom apply_beta19_i18n import apply_beta19_i18n\napply_beta19_i18n(root)\n'
    gen.write_text(text,encoding="utf-8")

    # Migration and semantic regressions.
    (ROOT/"tests"/"test_beta19_domain_presets.py").write_text(r'''"""Beta19 domain migration and room preset semantics."""
from types import SimpleNamespace
from custom_components.environment_manager import equipment_model as model
from custom_components.environment_manager.climate_strategy import select_profile, profiles

def test_automatic_profile_semantics():
    assert select_profile({},at_home="home",occupied="occupied")[0]=="comfort"
    assert select_profile({},at_home="home",occupied="unoccupied")[0]=="home"
    assert select_profile({},at_home="away",occupied="unoccupied")[0]=="away"
    assert select_profile({},at_home="home",occupied="occupied",sleeping=True)[0]=="sleep"
    assert select_profile({},at_home="unknown",occupied="unknown")[0]=="home"
    assert select_profile({},at_home="home",occupied="occupied",manual="eco")[0]=="eco"

def test_room_profile_migration_and_eco():
    parsed,problem=profiles({"profiles":{
        "home":{"heat_c":20,"cool_c":26},
        "unoccupied":{"heat_c":18,"cool_c":28},
    }})
    assert problem is None
    assert parsed["comfort"].heat_c==20
    assert parsed["home"].heat_c==18
    assert parsed["eco"].heat_c==17

def test_new_domain_and_legacy_constant():
    from custom_components.environment_manager.const import DOMAIN,LEGACY_DOMAIN
    assert DOMAIN=="environment_manager"
    assert LEGACY_DOMAIN=="air_quality_advisor"
''',encoding="utf-8")

    # New manifest identity; development keeps current version until release commit.
    manifest=NEW_DIR/"manifest.json"
    data=json.loads(manifest.read_text())
    data["domain"]=NEW
    manifest.write_text(json.dumps(data,indent=2)+"\n")

    # Regenerate catalogs after folder rename/profile changes.
    subprocess.run([sys.executable,"generate_translations.py"],cwd=ROOT,check=True)
    git("add","-A")
    print("BETA19_STAGED_TREE="+git("write-tree").strip())

if __name__=="__main__":
    main()
