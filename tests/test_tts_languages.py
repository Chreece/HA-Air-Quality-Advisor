"""Provider-aware TTS language labels."""
from types import SimpleNamespace

from custom_components.air_quality_advisor.tts_languages import (
    language_options, preferred_language, supports_language,
)


class States:
    def __init__(self, state):
        self._state = state
    def get(self, entity_id):
        return self._state if entity_id == self._state.entity_id else None


def test_tts_language_names_only_disambiguate_multiple_provider_variants():
    state = SimpleNamespace(
        entity_id="tts.voice",
        attributes={"supported_languages": ["en-US", "en-GB", "de-DE", "af-ZA"],
                    "default_language": "en-GB"},
    )
    hass = SimpleNamespace(states=States(state), data={})
    options = language_options(hass, "tts.voice")
    labels = {item["value"]: item["label"] for item in options}
    assert labels["en-US"] == "English (US)"
    assert labels["en-GB"] == "English (UK)"
    assert labels["de-DE"] == "Deutsch"
    assert "af-ZA" not in labels
    assert preferred_language(hass, "tts.voice", "en") in ("en-US", "en-GB")
    assert supports_language(hass, "tts.voice", "de-DE")
    assert not supports_language(hass, "tts.voice", "fr-FR")
