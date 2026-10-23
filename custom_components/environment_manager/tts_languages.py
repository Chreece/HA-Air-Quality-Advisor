"""Provider-aware TTS language labels and validation."""
from __future__ import annotations

from collections import Counter
from typing import Any

from .languages import NATIVE_NAMES, SUPPORTED_LANGUAGE_TAGS, resolve_language

_REGION_LABELS = {"GB": "UK", "US": "US"}


def _canonical(value: Any) -> str:
    return str(value or "").strip().replace("_", "-")


def _supported_base(value: Any) -> str | None:
    text = _canonical(value).casefold()
    folded = {tag.casefold(): tag for tag in SUPPORTED_LANGUAGE_TAGS}
    if text in folded:
        return folded[text]
    if text.startswith("zh"):
        return "zh-Hant" if any(token in text for token in ("hant", "-tw", "-hk", "-mo")) else "zh-Hans"
    if text.startswith("pt-"):
        return "pt-BR" if text == "pt-br" else "pt"
    root = text.split("-", 1)[0]
    if root == "no":
        root = "nb"
    return folded.get(root)


def _provider_entity(hass: Any, entity_id: str | None):
    if not isinstance(entity_id, str) or not entity_id.startswith("tts."):
        return None
    try:
        from homeassistant.components.tts.const import DATA_COMPONENT
        component = hass.data.get(DATA_COMPONENT)
        if component is not None:
            entity = component.get_entity(entity_id)
            if entity is not None:
                return entity
    except Exception:
        pass
    return None


def provider_languages(hass: Any, entity_id: str | None) -> tuple[tuple[str, ...], str | None]:
    """Read actual TTS entity capabilities, with state attributes only as fallback."""
    entity = _provider_entity(hass, entity_id)
    languages = None
    default = None
    if entity is not None:
        try:
            languages = list(entity.supported_languages)
        except (AttributeError, TypeError):
            languages = None
        try:
            default = entity.default_language
        except (AttributeError, TypeError):
            default = None
    if not languages and isinstance(entity_id, str):
        state = hass.states.get(entity_id)
        attrs = state.attributes if state is not None else {}
        raw = attrs.get("supported_languages")
        if isinstance(raw, (list, tuple)):
            languages = list(raw)
        default = default or attrs.get("default_language")
    cleaned = tuple(dict.fromkeys(
        tag for item in (languages or ()) if (tag := _canonical(item))
    ))
    return cleaned, (_canonical(default) or None)


def language_options(hass: Any, entity_id: str | None) -> list[dict[str, str]]:
    """Human language names; show a region only when the provider has variants."""
    supported, _ = provider_languages(hass, entity_id)
    tags = supported or tuple(SUPPORTED_LANGUAGE_TAGS)
    resolved = [(tag, base) for tag in tags if (base := _supported_base(tag)) is not None]
    counts = Counter(base for _, base in resolved)
    options = [{"value": "auto", "label": "Automatic (Home Assistant)"}]
    seen: set[str] = {"auto"}
    for tag, base in resolved:
        if tag.casefold() in seen:
            continue
        seen.add(tag.casefold())
        name = NATIVE_NAMES.get(base, base)
        if counts[base] > 1:
            parts = _canonical(tag).split("-")
            suffix = parts[-1].upper() if len(parts) > 1 else ""
            if suffix:
                suffix = _REGION_LABELS.get(suffix, suffix)
                name = f"{name} ({suffix})"
        options.append({"value": tag, "label": name})
    return options


def preferred_language(hass: Any, entity_id: str | None, saved: str | None) -> str:
    options = language_options(hass, entity_id)
    allowed = [item["value"] for item in options]
    wanted = _canonical(saved or "auto")
    if wanted == "auto" or wanted in allowed:
        return wanted
    base = _supported_base(wanted)
    compatible = next((value for value in allowed if value != "auto"
                       and _supported_base(value) == base), None)
    if compatible:
        return compatible
    _, default = provider_languages(hass, entity_id)
    if default in allowed:
        return default
    return "auto"


def supports_language(hass: Any, entity_id: str | None, value: str) -> bool:
    if value == "auto":
        return True
    return value in {item["value"] for item in language_options(hass, entity_id)}
