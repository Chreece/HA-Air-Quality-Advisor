"""Supported Home Assistant UI and announcement languages.

A locale fallback is explicit: region variants map to their language unless
Portuguese or Chinese script variants are separately translated.
"""
from __future__ import annotations

from .locale_pack_europe import LOCALES as _EUROPE
from .locale_pack_europe2 import LOCALES as _EUROPE2
from .locale_pack_global import LOCALES as _GLOBAL

EXTRA_LOCALES = {**_EUROPE, **_EUROPE2, **_GLOBAL}
BASE_NATIVE = {
    "en": "English",
    "de": "Deutsch",
    "el": "Ελληνικά",
    "fr": "Français",
    "es": "Español",
}
SUPPORTED_LANGUAGE_TAGS = (*BASE_NATIVE, *EXTRA_LOCALES)
NATIVE_NAMES = {**BASE_NATIVE, **{tag: loc["native"] for tag, loc in EXTRA_LOCALES.items()}}
LANGUAGE_OPTIONS = tuple(
    {"value": lang, "label": NATIVE_NAMES[lang]}
    for lang in sorted(SUPPORTED_LANGUAGE_TAGS, key=lambda tag: NATIVE_NAMES[tag].casefold())
)
_RTL = frozenset(tag for tag, loc in EXTRA_LOCALES.items() if loc.get("rtl"))

def resolve_language(language: str | None) -> str:
    """Resolve HA BCP47 language tags without collapsing script distinctions."""
    text = str(language or "en").strip().replace("_", "-").lower()
    if text in ("", "auto"):
        return "en"
    folded = {tag.lower(): tag for tag in SUPPORTED_LANGUAGE_TAGS}
    if text in folded:
        return folded[text]
    if text.startswith("zh"):
        if any(token in text for token in ("hant", "-tw", "-hk", "-mo")):
            return "zh-Hant"
        return "zh-Hans"
    if text.startswith("pt-"):
        return "pt-BR" if text == "pt-br" else "pt"
    root = text.split("-", 1)[0]
    if root == "no":
        return "nb"
    return folded.get(root, "en")

RTL_LANGUAGES = _RTL
