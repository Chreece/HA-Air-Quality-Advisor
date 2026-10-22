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
    ("outdoor", "outside"), ("outside", "outside"),
    ("indoor", "room"), ("control", "control"),
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



# Explicitly reviewed, visible labels for important Greek climate options.
# Generated synonyms should never obscure the difference between monitoring
# and permission to issue a physical device command.
_GREEK_LABELS = {
    "climate.climate_area": "Χώρος για ρύθμιση κλίματος",
    "climate_room.climate_enabled": "Ενεργοποίηση σχεδιασμού κλίματος",
    "climate_room.climate_allow_actuation": "Άδεια εντολών στις επιλεγμένες συσκευές",
    "climate_room.climate_auto_switch_hvac": "Αυτόματη εναλλαγή θέρμανσης / ψύξης",
    "climate_room.climate_prefer_native_auto": "Προτίμηση εγγενούς HEAT_COOL",
    "climate_room.climate_controller": "Μέθοδος κλιματικού ελέγχου",
    "climate_room.climate_mode": "Λειτουργία θέρμανσης / ψύξης",
    "climate_room.climate_entity": "Βασικός θερμοστάτης χώρου",
    "climate_room.climate_temperature_entity": "Αισθητήρας θερμοκρασίας χώρου",
    "climate_presence.climate_unknown_occupancy": "Χειρισμός άγνωστης παρουσίας",
    "climate_presence.climate_away_policy": "Κανόνας απουσίας από το σπίτι",
    "climate_presence.climate_manual_profile": "Χειροκίνητη επιλογή προφίλ",
    "climate_presence.climate_sleep_active": "Ενεργό προφίλ ύπνου",
    "climate_presence.climate_sleep_start": "Ώρα έναρξης ύπνου",
    "climate_presence.climate_sleep_end": "Ώρα λήξης ύπνου",
    "device_settings.device_method": "Μέθοδος ελέγχου συσκευής",
    "device_settings.device_presence_requirement": "Απαίτηση παρουσίας για έλεγχο",
    "device_settings.device_absence_action": "Ενέργεια όταν δεν υπάρχει παρουσία",
    "device_settings.device_sleep_behavior": "Συμπεριφορά κατά τον ύπνο",
    "device_settings.device_hardware_confirmed": "Επιβεβαιωμένες ανεξάρτητες προστασίες",
    "device_settings.device_auto_control": "Αυτόματος έλεγχος αυτής της συσκευής",
    "general_settings.general_room_occupancy_sensors": "Αισθητήρες παρουσίας ανά χώρο",
    "general_settings.general_home_trackers": "Συσκευές εντοπισμού κατοίκων",
    "general_settings.general_home_policy": "Κανόνας παρουσίας στο σπίτι",
}
_KEY_TAGS = (
    ("dry_fan", "DRY/FAN_ONLY"), ("humidity_power", "RH POWER"),
    ("dehumidifier", "DEHUMIDIFIER"), ("humidifier", "HUMIDIFIER"),
    ("heat_climate", "HEAT"), ("cool_climate", "COOL"),
    ("dry_climate", "DRY"), ("fan_climate", "FAN_ONLY"),
    ("pm25", "PM2.5"), ("co2", "CO₂"),
    ("radon", "RADON"), ("formaldehyde", "HCHO"),
    ("melanopic", "EDI"), ("illuminance", "LUX"),
    ("noise", "dB(A)"), ("purifier", "PURIFIER"),
    ("extractor", "EXTRACT"), ("extraction", "EXTRACT"),
    ("pollen", "POLLEN"), ("humidity", "RH"), ("fan", "FAN"),
    ("heat", "HEAT"), ("cool", "COOL"),
)


def _semantic_label(lang: str, step: str, field: str, english: str,
                    vocab: dict[str, str], terms: dict[str, str]) -> str:
    """Give controls distinct native labels; preserve units and HA code tokens."""
    if lang == "el" and (name := _GREEK_LABELS.get(f"{step}.{field}")):
        return name
    profile = re.fullmatch(
        r"(?:device_)?(home|unoccupied|away|sleep)_(heat|cool)(?:_c)?",
        field
    )
    if profile:
        context, mode = profile.groups()
        return f"{terms[mode]} · {terms[context]} (°C)"
    if field in ("kp", "ki", "kd", "pid_kp", "pid_ki", "pid_kd"):
        code = field.removeprefix("pid_")
        return f"PID K{code[-1]} · {vocab['control']} ({_unit_for(english, code)})"
    if field in ("heat_actuator", "cool_actuator"):
        mode = "heat" if field.startswith("heat") else "cool"
        return f"{terms[mode]} · {vocab['devices']}"
    if field.endswith("_entity") and ("purifier" in field or "extractor" in field):
        role = "purifier" if "purifier" in field else "extractor"
        return f"{terms[role]} · {vocab['source']}"
    tags = [label for part, label in _KEY_TAGS if part in field]
    topic = tags[0] if tags else ""
    tail = _topic(field, english, vocab)
    details = []
    if re.search(r"(?:^|_)min_on(?:_|$)", field): details.append("MIN ON")
    if re.search(r"(?:^|_)min_off(?:_|$)", field): details.append("MIN OFF")
    if re.search(r"(?:^|_)max_on(?:_|$)", field): details.append("MAX ON")
    if "max_demand" in field: details.append("MAX Δ")
    if "min_demand" in field: details.append("MIN Δ")
    if "max_change" in field: details.append("MAX Δ")
    if "min_change" in field: details.append("MIN Δ")
    if "max_setpoint" in field: details.append("MAX TARGET")
    if "min_setpoint" in field: details.append("MIN TARGET")
    if "mode_dwell" in field: details.append("MODE DWELL")
    if "hysteresis" in field: details.append("± RH" if "humidity" in field else "±")
    if "sample" in field: details.append("SAMPLE")
    if "pwm_period" in field: details.append("PWM PERIOD")
    if "low_rh" in field: details.append("RH MIN")
    if "high_rh" in field: details.append("RH MAX")
    if "scale" in field: details.append("SCALE")
    if "high_from" in field: details.append("HIGH")
    if "avoid_ventilation" in field: details.append("NO VENT")
    if field.endswith("_start"): details.append("START")
    if field.endswith("_end"): details.append("END")
    if "windowless" in field: details.append("NO WINDOW")
    if "hardware_confirmed" in field: details.append("HW ✓")
    if "sensor_verified" in field: details.append("SENSOR ✓")
    if "speed_percent" in field: details.append("SPEED %")
    if "fan_speed_auto" in field: details.append("SPEED AUTO")
    if "power_auto" in field: details.append("POWER AUTO")
    if "setpoint_auto" in field: details.append("TARGET AUTO")
    if "mode_auto" in field: details.append("MODE AUTO")
    if "auto_switch" in field: details.append("MODE SWITCH")
    if "prefer_native" in field: details.append("NATIVE")
    if field.endswith("_enabled"): details.append("AUTO")
    if field.endswith("_mode"): details.append("MODE")
    if field.endswith("_policy"): details.append("POLICY")
    if field.endswith("_verified"): details.append("VERIFIED")
    if not topic:
        return tail + (" · " + " · ".join(details) if details else "")
    return f"{topic} · {tail}" + (
        " · " + " · ".join(details) if details else ""
    )


def _unit_for(english: str, code: str) -> str:
    # Kp/Ki/Kd each have distinct physical dimensions; use the exact
    # English source unit verbatim rather than inventing a conversion.
    match = re.search(r"\(([^)]+(?:\)[^)]*)?)\)", english)
    return match.group(1) if match else {"kp":"P","ki":"I","kd":"D"}[code]


def _needs_clearer_label(value: str, vocab: dict[str, str]) -> bool:
    common = {
        vocab[key] for key in ("source","sensor","devices","control",
                               "settings","automatic","house","sleep",
                               "presence","target","pollen","room")
    }
    return value.strip() in common


def _unique_field_labels(lang: str, step: str, data: dict,
                         english: dict, vocab: dict, terms: dict,
                         descriptions: dict) -> None:
    """No two different fields in one form should have identical labels."""
    from collections import Counter
    if lang == "en":
        return
    counts = Counter(data.values())
    for field, original in list(data.items()):
        if counts[original] <= 1 and not _needs_clearer_label(original, vocab):
            continue
        candidate = _semantic_label(lang, step, field, english[field],
                                    vocab, terms)
        # A technical suffix is clearer than two indistinguishable controls.
        if candidate in data.values() and candidate != original:
            candidate += " · " + field.upper()
        if candidate == original and counts[original] > 1:
            candidate += " · " + field.upper()
        data[field] = candidate
        help_text = descriptions.get(field)
        if isinstance(help_text, str) and original in help_text:
            descriptions[field] = help_text.replace(original, candidate)
    # A localized flow with duplicate controls can lead to the wrong
    # hardware consent. Fail generation loudly if disambiguation regresses.
    if len(data) != len(set(data.values())):
        repeated = sorted(x for x in data.values() if list(data.values()).count(x)>1)
        raise ValueError(f"Ambiguous {lang}/{step} labels: {repeated[:12]}")


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
    label_terms = json.loads((root / "config_label_terms.json").read_text(encoding="utf-8"))
    if set(label_terms) != set(locales) or any(set(v) != {
        "home","unoccupied","away","sleep","heat","cool","purifier","extractor"
    } for v in label_terms.values()):
        raise ValueError("Every one of the 38 languages needs distinct device/profile labels")
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
                    # The original translators collapsed Home/Away and
                    # HEAT/COOL into indistinguishable labels in several
                    # languages. Unlike other descriptive names, profile
                    # heat/cool pairs must ALWAYS carry their exact context.
                    if (lang != "en" and step in ("climate_profiles", "device_settings")
                        and re.fullmatch(
                            r"(?:device_)?(?:home|unoccupied|away|sleep)_(?:heat|cool)(?:_c)?",
                            field
                        )):
                        display = _semantic_label(
                            lang, step, field, source_label, vocab, label_terms[lang]
                        )
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
                _unique_field_labels(lang, step, translated, source_labels,
                                     vocab, label_terms[lang], descriptions)
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
                    minimum = 18 if lang in ("ja", "ko", "zh-Hans", "zh-Hant", "th") else 35
                    if field not in fields:
                        continue
                    if not explanation or len(explanation.strip()) < minimum:
                        # Some reviewed, concise legacy translations are
                        # perfectly understandable, but too short to explain
                        # the setting to a first-time user. Append an actual
                        # localized operational explanation, never pad with
                        # punctuation or silently discard the original.
                        category = _kind(step, field)
                        addition = templates[lang][category].format(
                            label=fields[field]
                        )
                        original = (explanation or "").strip()
                        record["data_description"][field] = (
                            (original.rstrip(". ") + ". " if original else "") +
                            addition
                        )
                    if len(record["data_description"][field].strip()) < minimum:
                        raise ValueError(f"Too short explanation: {lang} {scope}.{step}.{field}")

        content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        path.write_text(content, encoding="utf-8")
        if lang == "en":
            (root / "strings.json").write_text(content, encoding="utf-8")
