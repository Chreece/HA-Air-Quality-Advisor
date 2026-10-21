"""Final field-by-field Home Assistant config/options localization layer.

This must run LAST: earlier generators intentionally retain legacy settings and
their default English documentation; this replaces those fallbacks with
meaningful language-specific descriptions without changing entity identifiers,
option values, HA selector schemas, configuration structure or safety policy.

In particular, a setting's data_description explains its effect, not merely
"choose a source". Each of the 38 locales has complete translated templates.
The canonical EN/Greek safety and scientific explanations are hand-authored.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


FILES = ("full_config_help_core.json", "full_config_help_climate.json",
         "full_config_help_science.json")
TEMPLATES_FILE = "full_config_help_templates.json"
_GENERIC_HELP = ("Device/source-specific configuration.",
                 "Select source; Required",
                 "Choose explicit Home Assistant entities.",
                 "Select optional extra HVAC,",
                 "Configure each selected room independently.")
_UNITS = re.compile(r"(?<![a-zA-Z])(?:°C|°F|ppm|ppb|µg/m³|mg/m³|Bq/m³|pCi/L|dB\(A\)|m³/h|m³|m/s|km/h|lx|lux|met|clo|kWh|g/kg|%|h⁻¹)(?![a-zA-Z])")
_PLACEHOLDERS = re.compile(r"(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*)\}(?!\})")
_WORDS = (
    ("pm25", "PM2.5"), ("pm10", "PM10"), ("co2", "CO₂"),
    ("no2", "NO₂"), ("so2", "SO₂"), ("o3", "O₃"),
    ("voc", "VOC"), ("aqi", "AQI"), ("hcho", "HCHO"),
    ("radon", "Rn"), ("pmv", "PMV / PPD"), ("pid", "PID"),
    ("cadr", "CADR"), ("melanopic", "EDI"),
    ("temperature", "temperature"), ("humidity", "humidity"),
    ("mold", "humidity"), ("pollen", "pollen"),
    ("presence", "presence"), ("occupancy", "presence"),
    ("sleep", "sleep"), ("away", "house"), ("home", "house"),
    ("fan", "speed"), ("actuator", "devices"),
    ("thermostat", "devices"), ("climate", "devices"),
    ("equipment", "devices"), ("device", "devices"),
    ("sensor", "sensor"), ("entity", "source"),
    ("power", "power"), ("speed", "speed"),
    ("source", "source"), ("target", "target"),
    ("light", "sensor"), ("noise", "sensor"),
    ("air", "outside"), ("wind", "outside"),
    ("outdoor", "outside"), ("control", "control"),
    ("enable", "automatic"), ("auto", "automatic"),
    ("maximum", "target"), ("minimum", "target"),
    ("limit", "target"), ("threshold", "target"),
)
_LANGUAGE_NEUTRAL = {"AQI", "CO₂", "PM2.5", "PM10", "VOC", "HCHO",
                     "NO₂", "SO₂", "O₃", "PID", "PMV", "CADR",
                     "US EPA AQI (0–500)", "EEA AQI (1–6)"}


def _topic(field: str, en_label: str, vocab: dict[str, str]) -> str:
    slug = field.casefold()
    parts = []
    if slug.startswith("aqi_scale_") or slug.startswith("aqi_custom_limit_"):
        ordinal = int(slug.rsplit("_", 1)[-1]) + 1
        tail = vocab["source"] if "scale" in slug else vocab["target"]
        return f"AQI #{ordinal} · {tail}"
    # The displayed name must identify the exact field even if the original
    # English text was inherited. Keep scientifically meaningful units.
    for key, value in _WORDS:
        if key not in slug:
            continue
        word = vocab.get(value, value)
        if word not in parts:
            parts.append(word)
    if re.search(r"(?:^|_)(?:heat|heating)(?:_|$)", slug):
        parts.append(vocab["temperature"] + " +")
    elif re.search(r"(?:^|_)(?:cool|cooling)(?:_|$)", slug):
        parts.append(vocab["temperature"] + " −")
    if "stale" in slug or "age" in slug:
        parts.extend((vocab["sensor"], vocab["required"]))
    if "calibrat" in slug or "verified" in slug or "confirmed" in slug:
        parts.append(vocab["required"])
    if "min_on" in slug or "min_off" in slug or "max_on" in slug:
        parts.extend((vocab["power"], vocab["off"] if "off" in slug else vocab["automatic"]))
    if not parts:
        parts = [vocab["settings"], vocab["source"]]
    # "°C", "ppm" etc. are physical symbols, not untranslated English.
    units = list(dict.fromkeys(_UNITS.findall(en_label)))
    if not units and slug.endswith(("_seconds", "_on_s", "_off_s", "_dwell_s", "_period_s")):
        units = ["s"]
    if not units and slug.endswith(("_heat", "_cool", "_heat_c", "_cool_c")):
        units = ["°C"]
    return " · ".join(dict.fromkeys(parts[:5])) + (
        " (" + ", ".join(units[:2]) + ")" if units else ""
    )


def _kind(step: str, field: str) -> str:
    s = field.lower()
    if step == "thresholds":
        return "threshold"
    if (re.search(r"^(?:device_)?(?:home|away|unoccupied|sleep)_(?:heat|cool)", s)
        or "sleep_humidity_target" in s):
        return "profile"
    if (re.search(r"(?:min_on|min_off|max_on|dwell|sample_seconds|period_s|delay_minutes|stale_minutes|age_minutes|_start$|_end$)", s)):
        return "timing"
    if (s.endswith(("_entity", "_entities", "_sensor", "_sensors"))
        or s.endswith("_trackers") or s in ("area_devices_area", "device_choice", "selected_devices")):
        return "source"
    if ("verified" in s or "calibrat" in s or "confirmed" in s
        or s in ("met", "clo", "air_speed_m_s", "room_volume_m3", "particle_cadr_m3h")):
        return "science"
    if ("target" in s or "limit" in s or "threshold" in s
        or "high_rh" in s or "low_rh" in s
        or s.endswith(("_heat", "_cool", "_rh", "_percent", "_c", "_ppm", "_ug_m3"))):
        return "threshold"
    if ("auto" in s or "enabled" in s or "control" in s or "action" in s
        or "method" in s or "policy" in s or "mode" in s
        or "pause" in s or "profile" in s or "hardware" in s
        or s.startswith(("pid_", "climate_"))):
        return "control"
    return "generic"


def _is_generic_help(value: object) -> bool:
    if not isinstance(value, str) or len(value.strip()) < 30:
        return True
    return value.startswith(_GENERIC_HELP)


def _step_title(step_id: str, current: str | None,
                english: str | None, lang: str, vocab: dict) -> str:
    if lang == "en" or (current and english and current != english):
        return current or english or step_id
    tokens = _topic(step_id, english or step_id, vocab)
    return vocab["settings"] + " · " + tokens


def _translated_help(lang: str, step_id: str, field: str,
                     display: str, templates: dict, specials: dict,
                     current: str | None, english: str | None) -> str:
    manual = specials.get(f"{step_id}.{field}", {})
    if lang in manual:
        return manual[lang]
    if (current and isinstance(current, str) and len(current.strip()) >= 35
        and not _is_generic_help(current)
        and ((lang == "en") or (current != english))):
        return current
    category = _kind(step_id, field)
    return templates[lang][category].format(label=display)


def _generated_error(lang: str, key: str, vocab: dict, templates: dict) -> str:
    context = _topic(key, key.replace("_", " "), vocab)
    return templates[lang]["error"].format(label=context)


def apply_full_config_i18n(root: Path) -> None:
    locales = json.loads((root / "compact_locales.json").read_text(encoding="utf-8"))
    templates = json.loads((root / TEMPLATES_FILE).read_text(encoding="utf-8"))
    manuals: dict[str, dict] = {}
    for filename in FILES:
        mapping = json.loads((root / filename).read_text(encoding="utf-8"))
        collision = set(mapping) & set(manuals)
        if collision:
            raise ValueError(f"Duplicate field descriptions in {filename}: {sorted(collision)}")
        manuals.update(mapping)
    paths = sorted((root / "translations").glob("*.json"))
    languages = {p.stem for p in paths}
    if languages != set(locales) or languages != set(templates) or len(paths) != 38:
        raise ValueError("All 38 locale files and translated templates are mandatory")
    for code, text in templates.items():
        if set(text) != {"source", "threshold", "control", "timing",
                         "profile", "science", "generic", "error"}:
            raise ValueError(f"Incomplete template phrases: {code}")
    # Snapshot canonical English before making any changes to generated files.
    english = json.loads((root / "translations" / "en.json").read_text(encoding="utf-8"))

    for path in paths:
        lang = path.stem
        data = json.loads(path.read_text(encoding="utf-8"))
        vocab = locales[lang]
        for scope in ("config", "options"):
            localized_steps = data[scope]["step"]
            original_steps = english[scope]["step"]
            for step, original in original_steps.items():
                record = localized_steps[step]
                record["title"] = _step_title(
                    step, record.get("title"), original.get("title"), lang, vocab
                )
                if original.get("description") and (
                    not record.get("description")
                    or (lang != "en" and record["description"] == original["description"])
                ):
                    new = templates[lang]["generic"].format(label=record["title"])
                    placeholders = _PLACEHOLDERS.findall(original["description"])
                    record["description"] = new + (
                        "\n\n" + " · ".join("{" + k + "}" for k in placeholders)
                        if placeholders else ""
                    )
                source_labels = original.get("data", {})
                translated = record.setdefault("data", {})
                descriptions = record.setdefault("data_description", {})
                original_help = original.get("data_description", {})
                for field, source_label in source_labels.items():
                    display = translated.get(field, source_label)
                    # Keep already translated and reviewed native labels.
                    if (lang != "en" and
                        (not display or display == source_label
                         or display == field.replace("_", " ").capitalize())):
                        display = _topic(field, source_label, vocab)
                        translated[field] = display
                    existing_help = descriptions.get(field)
                    # Older compact and climate generators wrote vague
                    # localized placeholder text. Being non-English does
                    # NOT make that help useful. Replace it deterministically.
                    inherited_generic = (
                        isinstance(existing_help, str) and
                        (existing_help.startswith(
                            f"{vocab['select']} {vocab['source']};"
                        ) or existing_help.startswith(
                            f"{vocab['area']} · {vocab['settings']} ·"
                        ))
                    )
                    descriptions[field] = _translated_help(
                        lang, step, field, display, templates, manuals,
                        None if inherited_generic else existing_help,
                        original_help.get(field)
                    )
                for key, label in original.get("menu_options", {}).items():
                    menus = record.setdefault("menu_options", {})
                    if lang != "en" and (not menus.get(key) or menus[key] == label):
                        menus[key] = localized_steps.get(key, {}).get(
                            "title", _step_title(key, label, label, lang, vocab)
                        )

            # Make validation messages useful in the same locale too.
            for key, en_error in english[scope].get("error", {}).items():
                translated = data[scope].setdefault("error", {})
                if (lang != "en" and (not translated.get(key)
                    or translated[key] == en_error)):
                    translated[key] = _generated_error(lang, key, vocab, templates)

        # Selector option values are stable API identifiers; only labels may
        # change. Existing native translation is preferred over generated text.
        for group, spec in english.get("selector", {}).items():
            src_options = spec.get("options", {})
            dst_options = data.setdefault("selector", {}).setdefault(
                group, {}
            ).setdefault("options", {})
            for key, en_value in src_options.items():
                if lang == "en" or (
                    dst_options.get(key) and dst_options[key] != en_value
                ) or en_value in _LANGUAGE_NEUTRAL:
                    continue
                dst_options[key] = _topic(key, en_value, vocab)

        # Preserve placeholders and force complete field help, including
        # thresholds that historically had 22 labels and ZERO descriptions.
        for scope in ("config", "options"):
            for step, record in data[scope]["step"].items():
                fields = record.get("data", {})
                if fields and set(fields) - set(record.get("data_description", {})):
                    raise ValueError(f"Missing {lang} {scope}.{step} explanations")
                for field, explanation in record.get("data_description", {}).items():
                    if field in fields and (not explanation or len(explanation.strip()) < 35):
                        raise ValueError(f"Too short explanation: {lang} {scope}.{step}.{field}")

        content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        path.write_text(content, encoding="utf-8")
        if lang == "en":
            (root / "strings.json").write_text(content, encoding="utf-8")
