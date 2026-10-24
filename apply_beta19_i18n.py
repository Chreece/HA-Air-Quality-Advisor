"""Final room-profile entity labels; no domain migration compatibility."""
from __future__ import annotations

import json
from pathlib import Path


def apply_beta19_i18n(root: Path) -> None:
    """Keep all current room profile target labels after every generator pass."""
    vocab = json.loads((root / "compact_locales.json").read_text(encoding="utf-8"))
    files = sorted((root / "translations").glob("*.json"))
    for path in [root / "strings.json", *files]:
        lang = "en" if path.name == "strings.json" else path.stem
        doc = json.loads(path.read_text(encoding="utf-8"))

        # No historical-domain setup path exists. Remove stale generated keys
        # defensively so the UI can expose only the canonical integration.
        config = doc.setdefault("config", {})
        config.setdefault("step", {}).pop("migrate_legacy", None)
        abort = config.setdefault("abort", {})
        for key in (
            "legacy_migration_ambiguous",
            "legacy_migration_missing",
            "legacy_migration_cancelled",
        ):
            abort.pop(key, None)

        number = doc.setdefault("entity", {}).setdefault("number", {})
        old_profiles = (
            doc.get("options", {})
            .get("step", {})
            .get("climate_profiles", {})
            .get("data", {})
        )
        heat_old = str(old_profiles.get("home_heat", "Heating"))
        cool_old = str(old_profiles.get("home_cool", "Cooling"))
        heat_prefix = heat_old.split("·", 1)[0].strip()
        cool_prefix = cool_old.split("·", 1)[0].strip()
        words = vocab[lang]
        profile_names = {
            "comfort": f"{words['room']} · {words['presence']}",
            "home": words.get("house", "Home"),
            "away": f"{words.get('house', 'Home')} · {words['off']}",
            "sleep": words["sleep"],
            "eco": "ECO",
        }
        for profile, pname in profile_names.items():
            number[f"area_climate_profile_{profile}_heat"] = {
                "name": f"{heat_prefix} · {pname}"
            }
            number[f"area_climate_profile_{profile}_cool"] = {
                "name": f"{cool_prefix} · {pname}"
            }
            number[f"area_climate_profile_{profile}_humidity"] = {
                "name": f"{words['humidity']} · {pname} · {words['target']} (%)"
            }

        # These were beta18 flow names, not current Room Environment entities.
        for old_key in ("unoccupied_heat", "unoccupied_cool"):
            number.pop("area_climate_profile_" + old_key, None)

        path.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
