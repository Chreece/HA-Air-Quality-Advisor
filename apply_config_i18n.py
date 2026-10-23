"""Apply reviewed Home Assistant configuration/option translations.

The overrides file is the authoritative source for all 38 locales, including
selector labels. This runs AFTER base and extended translation generation.
Provider names, physical device/entity names and metrics are deliberately not
machine-translated: those are user/provider data rather than integration UI.
"""
from __future__ import annotations

import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "custom_components" / "enviroment_manager"
PACKAGE = ROOT / "translations"
OVERRIDE_FILE = ROOT / "config_i18n_overrides.json"

BASE_NATIVE = {
    "en": "English",
    "de": "Deutsch",
    "el": "Ελληνικά",
    "fr": "Français",
    "es": "Español",
}
PACK_FILES = (
    "locale_pack_europe.py", "locale_pack_europe2.py", "locale_pack_global.py",
)


def native_languages() -> dict[str, str]:
    result = dict(BASE_NATIVE)
    for name in PACK_FILES:
        pack = runpy.run_path(str(ROOT / name))["LOCALES"]
        for tag, record in pack.items():
            if tag in result:
                raise ValueError(f"Duplicate language {tag}")
            result[tag] = record["native"]
    return result


def apply_config_overrides(root: Path = ROOT) -> None:
    overrides = json.loads((root / "config_i18n_overrides.json").read_text(encoding="utf-8"))
    names = native_languages()
    if set(overrides) != set(names):
        raise ValueError(f"Missing or extra config translations: {set(overrides) ^ set(names)}")

    for code, values in overrides.items():
        target = root / "translations" / f"{code}.json"
        data = json.loads(target.read_text(encoding="utf-8"))
        if set(data["config"]["step"]) != set(data["options"]["step"]) - {"init"}:
            raise ValueError(f"Flow structure mismatch in {code}")
        for section in ("config", "options"):
            scope = data[section]
            for key, translation in values["help"].items():
                found = False
                for step in scope["step"].values():
                    if key in step.get("data_description", {}):
                        step["data_description"][key] = translation
                        found = True
                if not found:
                    raise ValueError(f"Unknown description field {code}: {key}")

            for key, translation in values["thresholds"].items():
                if key not in scope["step"]["thresholds"]["data"]:
                    raise ValueError(f"Unknown threshold {code}: {key}")
                scope["step"]["thresholds"]["data"][key] = translation

            for key, translation in values["errors"].items():
                if key not in scope["error"]:
                    raise ValueError(f"Unknown validation error {code}: {key}")
                scope["error"][key] = translation

        data["config"]["abort"]["already_configured"] = values["abort"]
        data["options"]["step"]["init"]["title"] = values["menuTitle"]
        data["options"]["step"]["init"]["description"] = values["menu"]

        # Hassfest requires lowercase selector translation keys. The UI
        # submits lowercase locale tags, while saved settings and messages
        # preserve canonical BCP47 spellings such as pt-BR and zh-Hant.
        selector_names = {tag.lower(): name for tag, name in names.items()}
        if len(selector_names) != len(names):
            raise ValueError("Ambiguous locale selector keys")
        data.setdefault("selector", {})["output_language"] = {
            "options": {"auto": values["auto"], **selector_names}
        }
        target.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if code == "en":
            (root / "strings.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )


if __name__ == "__main__":
    apply_config_overrides()
