"""Beta19 domain migration and room-preset labels."""
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
        step.setdefault("data_description",{})["confirm"]=desc
        abort=doc["config"].setdefault("abort",{})
        if lang=="en":
            abort["legacy_migration_ambiguous"]="Multiple legacy entries were found; migration is blocked to avoid merging homes."
            abort["legacy_migration_missing"]="The legacy entry disappeared before migration."
            abort["legacy_migration_cancelled"]="Migration was cancelled."
        else:
            base=f"{vocab[lang]['settings']} · environment_manager"
            abort["legacy_migration_ambiguous"]=base+" · 2+"
            abort["legacy_migration_missing"]=base+" · ?"
            abort["legacy_migration_cancelled"]=base+" · ×"

        number=doc.setdefault("entity",{}).setdefault("number",{})
        old_profiles=doc.get("options",{}).get("step",{}).get("climate_profiles",{}).get("data",{})
        heat_old=str(old_profiles.get("home_heat","Heating"))
        cool_old=str(old_profiles.get("home_cool","Cooling"))
        heat_prefix=heat_old.split("·",1)[0].strip()
        cool_prefix=cool_old.split("·",1)[0].strip()
        profile_names={
            "comfort": f"{vocab[lang]['room']} · {vocab[lang].get('presence','Comfort')}",
            "home": f"{vocab[lang].get('house','Home')} · {vocab[lang]['room']}",
            "sleep": f"{vocab[lang]['room']} · {vocab[lang]['sleep']}",
            "eco": f"{vocab[lang].get('house','Home')} · ECO",
        }
        for profile,pname in profile_names.items():
            number[f"area_climate_profile_{profile}_heat"]={"name":f"{heat_prefix} · {pname}"}
            number[f"area_climate_profile_{profile}_cool"]={"name":f"{cool_prefix} · {pname}"}
        for old_key in ("unoccupied_heat","unoccupied_cool","away_heat","away_cool"):
            number.pop("area_climate_profile_"+old_key,None)
        path.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
