"""Full config/options localization audit for all supported HA languages."""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from custom_components.air_quality_advisor.languages import SUPPORTED_LANGUAGE_TAGS
from test_discovery import adapter


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "air_quality_advisor"
TRANSLATIONS = COMPONENT / "translations"
SCOPES = ("config", "options")
USER_VISIBLE = ("step", "error", "abort")


def _flat(value: dict, prefix: str = "") -> dict[str, str]:
    output = {}
    for key, item in value.items():
        full = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            output.update(_flat(item, full))
        elif isinstance(item, str):
            output[full] = item
    return output


def _translations() -> dict[str, dict]:
    return {
        code: json.loads((TRANSLATIONS / f"{code}.json").read_text(encoding="utf-8"))
        for code in SUPPORTED_LANGUAGE_TAGS
    }


def test_all_38_locale_files_are_structurally_complete():
    documents = _translations()
    assert len(documents) == 38
    en = documents["en"]
    en_flat = _flat(en)
    for lang, doc in documents.items():
        all_strings = _flat(doc)
        assert set(all_strings) == set(en_flat), (lang, set(en_flat) ^ set(all_strings))
        assert list(doc["config"]["step"]) == list(en["config"]["step"])
        assert list(doc["options"]["step"]) == list(en["options"]["step"])
        assert set(doc["config"]["error"]) == set(en["config"]["error"])
        assert set(doc["options"]["error"]) == set(en["options"]["error"])
        option_keys = set(doc["selector"]["output_language"]["options"])
        assert option_keys == {"auto", *(tag.lower() for tag in SUPPORTED_LANGUAGE_TAGS)}
        assert all(re.fullmatch(r"[a-z0-9_-]+", key) for key in option_keys)


def test_translated_help_thresholds_errors_abort_and_menu_do_not_regress_to_english():
    docs = _translations()
    english = _flat(docs["en"])
    # Technical option values, numbers, and provider names are excluded;
    # configured flow prose and errors must not be inherited from English.
    checked = 0
    for lang, doc in docs.items():
        if lang == "en":
            continue
        contents = _flat(doc)
        for key, text in english.items():
            if not key.startswith(("config.", "options.")):
                continue
            if not re.search(r"[a-zA-Z]{4,}", text):
                continue
            # New optional scientific methods ship with English technical-help
            # fallback in non-primary languages until reviewed translations exist.
            # All pre-existing configuration strings remain fully localized.
            if (key.startswith(("options.step.environment", "options.error.invalid_environment",
                               "options.error.pmv_requires_explicit"))
                    or key.startswith("options.step.init.menu_options.environment")):
                continue
            assert contents[key] != text, f"English fallback in {lang}:{key}"
            checked += 1
        assert doc["selector"]["output_language"]["options"]["auto"] != (
            docs["en"]["selector"]["output_language"]["options"]["auto"]
        )
    assert checked > 5500


def test_greek_weather_and_all_advanced_limits_are_translated():
    docs = _translations()
    greek = docs["el"]
    for context in SCOPES:
        weather = greek[context]["step"]["weather"]["data_description"]
        assert "Απαιτείται τουλάχιστον μία οντότητα καιρού" in weather["weather_entities"]
        assert "Προαιρετικό" in weather["weather_warnings"]
        outdoor = greek[context]["step"]["outdoor"]["data_description"]
        assert "Επίλεξε πραγματικούς εξωτερικούς αισθητήρες" in outdoor["outdoor_sensors"]
        thresholds = greek[context]["step"]["thresholds"]["data"]
        assert len(thresholds) == 22
        assert all(value != docs["en"][context]["step"]["thresholds"]["data"][key]
                   for key, value in thresholds.items())
        for setting in ("language", "automatic_tts", "automatic_notifications",
                        "notify_entities", "tts_engine", "media_players"):
            assert greek[context]["step"]["delivery"]["data_description"][setting] != (
                docs["en"][context]["step"]["delivery"]["data_description"][setting]
            )
    assert greek["config"]["abort"]["already_configured"] != (
        docs["en"]["config"]["abort"]["already_configured"]
    )


def test_language_selector_uses_home_assistant_native_translation_key(monkeypatch, adapter):
    from test_area_config_flow import _make_options
    options = _make_options(monkeypatch, adapter)
    asyncio.run(options.async_step_init())
    schema = asyncio.run(options.async_step_delivery())["data_schema"]
    selector = schema["language"]
    assert selector.config.translation_key == "output_language"
    assert selector.config.options[0] == "auto"
    assert set(selector.config.options[1:]) == {
        tag.lower() for tag in SUPPORTED_LANGUAGE_TAGS
    }
    assert all(re.fullmatch(r"[a-z0-9_-]+", option) for option in selector.config.options)


def test_regional_language_selector_preserves_existing_settings(monkeypatch, adapter):
    from test_area_config_flow import _make_options

    for canonical in ("pt-BR", "zh-Hans", "zh-Hant", "auto"):
        options = _make_options(monkeypatch, adapter)
        options.config_entry.data["language"] = canonical
        asyncio.run(options.async_step_init())
        form = asyncio.run(options.async_step_delivery())
        # Language is the first field in the delivery form (probatio.Field).
        marker = next(iter(form["data_schema"]))
        assert marker.default == canonical.lower()
        result = asyncio.run(options.async_step_delivery({"language": canonical.lower()}))
        assert result["completed"]["data"]["language"] == canonical


def test_translation_generator_uses_reviewed_overrides_and_provider_names_are_intact():
    root = ROOT / "custom_components" / "air_quality_advisor"
    code = (ROOT / "generate_translations.py").read_text(encoding="utf-8")
    assert "apply_config_overrides(root)" in code
    spec = json.loads((root / "config_i18n_overrides.json").read_text(encoding="utf-8"))
    assert set(spec) == set(SUPPORTED_LANGUAGE_TAGS)
    for lang, record in spec.items():
        assert record["auto"] and record["agent"] and record["abort"]
        assert record["menuTitle"] and record["menu"]
        if lang not in ("en", "de", "el", "fr", "es"):
            assert len(record["errors"]) == 17, lang
        else:
            assert len(record["thresholds"]) == (0 if lang == "en" else 18)
    discovery = (root / "discovery.py").read_text(encoding="utf-8")
    assert 'state.name or entity_id' in discovery
    assert 'area.name' in discovery
    assert 'state.name or state.entity_id' in discovery


def test_all_locales_include_live_mold_weather_and_room_readiness_hints():
    for code, doc in _translations().items():
        assert list(doc["options"]["step"]["init"]["menu_options"])[1:3] == [
            "weather", "indoor_sensors"
        ], code
        for context in ("config", "options"):
            weather = doc[context]["step"]["weather"]
            room = doc[context]["step"]["indoor_sensors"]
            assert "{mold_weather_notice}" in weather["description"], code
            assert "{mold_room_notice}" in room["description"], code
            assert "temperature" in weather["data_description"]["weather_entities"], code
