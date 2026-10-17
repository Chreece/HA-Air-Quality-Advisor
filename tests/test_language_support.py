"""Language catalogs, Home Assistant translation schemas and locale fallbacks."""
from __future__ import annotations

import json
import string
from pathlib import Path

from custom_components.air_quality_advisor.languages import (
    EXTRA_LOCALES, NATIVE_NAMES, SUPPORTED_LANGUAGE_TAGS, LANGUAGE_OPTIONS,
    resolve_language, RTL_LANGUAGES,
)
from custom_components.air_quality_advisor.messages import TEXT, announcement
from custom_components.air_quality_advisor.logic import Window, Reason, Recommendation

ROOT = Path(__file__).resolve().parents[1]
TRANSLATIONS = ROOT / "custom_components" / "air_quality_advisor" / "translations"


def test_38_unique_and_named_supported_languages():
    assert len(SUPPORTED_LANGUAGE_TAGS) == 38
    assert len(set(SUPPORTED_LANGUAGE_TAGS)) == 38
    assert len(EXTRA_LOCALES) == 33
    assert set(SUPPORTED_LANGUAGE_TAGS) == set(NATIVE_NAMES)
    assert {item["value"] for item in LANGUAGE_OPTIONS} == set(SUPPORTED_LANGUAGE_TAGS)
    assert RTL_LANGUAGES == {"ar", "he", "fa", "ur"}


def test_country_and_script_variants_are_preserved():
    cases = {
        "el_GR": "el", "de-DE": "de",
        "pt-BR": "pt-BR", "pt_PT": "pt",
        "zh-CN": "zh-Hans", "zh-Hans": "zh-Hans",
        "zh-Hant": "zh-Hant", "zh_TW": "zh-Hant",
        "zh-HK": "zh-Hant", "no-NO": "nb",
        "ar-EG": "ar", "en-US": "en",
        "xx-XX": "en",
    }
    for raw, expected in cases.items():
        assert resolve_language(raw) == expected


def test_every_ui_locale_ships_complete_home_assistant_json():
    english = json.loads((TRANSLATIONS / "en.json").read_text(encoding="utf-8"))
    steps = set(english["config"]["step"])
    expected_order = list(english["config"]["step"])
    for language in SUPPORTED_LANGUAGE_TAGS:
        path = TRANSLATIONS / f"{language}.json"
        assert path.exists(), f"missing translation {path.name}"
        translation = json.loads(path.read_text(encoding="utf-8"))
        assert set(translation) == set(english), language
        assert list(translation["config"]["step"]) == expected_order
        assert set(translation["config"]["step"]) == steps
        assert set(translation["options"]["step"]) == set(english["options"]["step"])
        assert list(translation["options"]["step"]["init"]["menu_options"]) == [
            "areas", "indoor_sensors", "window_sensors", "outdoor",
            "weather", "delivery", "thresholds",
        ]
        assert set(translation["config"]["error"]) == set(english["config"]["error"])
        assert set(translation["options"]["error"]) == set(english["options"]["error"])
        assert "{area_name}" in translation["config"]["step"]["indoor_sensors"]["description"]
        assert "{position}" in translation["config"]["step"]["indoor_sensors"]["description"]
        assert "{total}" in translation["config"]["step"]["indoor_sensors"]["description"]


def test_all_spoken_announcement_placeholders_and_reasons_work():
    r = Recommendation(
        "open", "room", "Sample room",
        (Window("binary_sensor.sample_window", "Sample window", False),),
        (Reason("inside_co2", "CO₂", "1,200 ppm"),),
    )
    variables = {
        "open": {"windows", "area", "reasons"},
        "close": {"windows", "area", "reasons"},
        "inside": {"name", "value"},
        "outside": {"name", "value"},
    }
    for locale in SUPPORTED_LANGUAGE_TAGS:
        table = TEXT[locale]
        for key in ("open", "close", "title_open", "title_close", "inside", "outside"):
            assert table[key]
        for key, expected in variables.items():
            tokens = {name for _, name, _, _ in string.Formatter().parse(table[key]) if name}
            assert tokens == expected, (locale, key, tokens)
        title, message = announcement(r, locale)
        assert "Sample window" in message, locale
        assert "Sample room" in message, locale
        assert "CO₂" in message, locale
        assert "1,200 ppm" in message, locale
        assert title
        assert "{" not in message and "}" not in message
