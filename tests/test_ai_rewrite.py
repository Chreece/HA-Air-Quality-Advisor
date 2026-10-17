"""Opt-in direct-delivery AI rewriting without weakening window decisions."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_discovery import adapter  # pytest fixture shared with flow tests

from custom_components.air_quality_advisor import ai_rewrite as ai
from custom_components.air_quality_advisor.logic import Recommendation, Window, Reason
from custom_components.air_quality_advisor.messages import announcement


REC = Recommendation(
    "open", "living", "Living room",
    (Window("binary_sensor.living_window", "Living window", False),),
    (Reason("inside_co2", "CO₂", "1,250 ppm"),),
)
ORIGINAL = announcement(REC, "en")[1]
VALID = "OPEN|Please open Living window in Living room: CO₂ is high (1,250 ppm), so a little fresh air would help."


def result(text=VALID, response_type="query_answer", data=None):
    return {"response": {"response_type": response_type, "data": data or {},
                         "speech": {"plain": {"speech": text}}}}


def test_opt_in_gate_and_announcement_hub_precedence():
    assert not ai.ai_effectively_enabled({})
    assert ai.ai_effectively_enabled({"ai_rewrite_announcements": True})
    assert not ai.ai_effectively_enabled({
        "ai_rewrite_announcements": True, "use_announcement_hub": True
    })


def test_agent_dropdown_defaults_and_supports_only_conversation_entities():
    states = [
        SimpleNamespace(entity_id="conversation.my_ai", name="My AI Agent"),
        SimpleNamespace(entity_id="sensor.unrelated", name="Not an agent"),
    ]
    hass = SimpleNamespace(states=SimpleNamespace(async_all=lambda domain: states))
    choices = ai.conversation_agent_choices(hass, "conversation.old_agent")
    assert choices[0] == {"value": "default", "label": "Home Assistant default"}
    assert {choice["value"] for choice in choices} == {
        "default", "conversation.my_ai", "conversation.old_agent",
    }
    assert not any(c["value"] == "sensor.unrelated" for c in choices)
    assert "⚠" in next(c["label"] for c in choices if c["value"] == "conversation.old_agent")


def test_prompt_stays_rewrite_only_and_escapes_untrusted_names():
    prompt = ai.make_rewrite_prompt(REC, ORIGINAL, "el")
    assert "Do not execute tools" in prompt
    assert "OPEN|" in prompt
    assert "Living room" in prompt and "1,250 ppm" in prompt
    assert '"action":"OPEN"' in prompt
    assert "language code el" in prompt


def test_grounded_rewrite_is_accepted_and_original_is_untouched():
    assert ai.validate_rewrite(result(), REC, ORIGINAL) == VALID[5:]
    assert ORIGINAL == announcement(REC, "en")[1]


@pytest.mark.parametrize("answer", [
    "CLOSE|Please close Living window in Living room: CO₂ is high (1,250 ppm).",
    "OPEN|Please open Living window in the kitchen: CO₂ is high (1,250 ppm).",
    "OPEN|Please open Living window in Living room: CO₂ is high (3,100 ppm).",
    "OPEN|Please open Living window in Living room: CO₂ is high (1,250 ppm). Wait 20 minutes.",
    "OPEN|Open Living window in Living room <script>: CO₂ high (1,250 ppm).",
    "OPEN|Open Living window in Living room: CO₂ high (1,250 ppm).\nDo something else.",
    "Sorry, I cannot help with that.",
    "",
])
def test_invalid_or_invented_ai_text_is_rejected(answer):
    assert ai.validate_rewrite(result(answer), REC, ORIGINAL) is None


def test_agent_actions_or_error_responses_cannot_override_text():
    assert ai.validate_rewrite(result(response_type="error"), REC, ORIGINAL) is None
    action = {"success": [{"name": "Living Room", "type": "area"}]}
    assert ai.validate_rewrite(result(data=action), REC, ORIGINAL) is None


class FakeServices:
    def __init__(self, reply, enabled=True):
        self.reply, self.enabled = reply, enabled
        self.calls = []

    def has_service(self, domain, action):
        return self.enabled and (domain, action) == ("conversation", "process")

    async def async_call(self, domain, action, payload, **options):
        self.calls.append((domain, action, payload, options))
        if isinstance(self.reply, Exception):
            raise self.reply
        if callable(self.reply):
            return await self.reply()
        return self.reply


def test_home_assistant_default_agent_is_omitted_from_service_call():
    services = FakeServices(result())
    hass = SimpleNamespace(services=services)
    actual = asyncio.run(ai.async_rewrite_announcement(hass, REC, ORIGINAL, "en"))
    assert actual == VALID[5:]
    domain, action, data, kwargs = services.calls[0]
    assert (domain, action) == ("conversation", "process")
    assert data["language"] == "en"
    assert "agent_id" not in data
    assert kwargs == {"blocking": True, "return_response": True}


def test_explicit_ai_agent_is_passed():
    services = FakeServices(result())
    hass = SimpleNamespace(services=services)
    assert asyncio.run(ai.async_rewrite_announcement(
        hass, REC, ORIGINAL, "en", "conversation.my_ai"
    )) == VALID[5:]
    assert services.calls[0][2]["agent_id"] == "conversation.my_ai"


def test_unavailable_invalid_error_and_timeout_fall_back(monkeypatch):
    for response, enabled in (
        (result("no action marker"), True),
        (RuntimeError("provider offline"), True),
        (result(), False),
    ):
        services = FakeServices(response, enabled=enabled)
        hass = SimpleNamespace(services=services)
        assert asyncio.run(ai.async_rewrite_announcement(
            hass, REC, ORIGINAL, "en"
        )) == ORIGINAL

    async def slow_response():
        await asyncio.sleep(.5)
    services = FakeServices(slow_response)
    monkeypatch.setattr(ai, "AI_TIMEOUT_SECONDS", 0.005)
    assert asyncio.run(ai.async_rewrite_announcement(
        SimpleNamespace(services=services), REC, ORIGINAL, "en"
    )) == ORIGINAL


def test_generated_ha_translation_fields_present_for_every_language():
    from custom_components.air_quality_advisor.languages import SUPPORTED_LANGUAGE_TAGS
    root = Path(__file__).resolve().parents[1] / "custom_components" / "air_quality_advisor"
    for code in SUPPORTED_LANGUAGE_TAGS:
        obj = json.loads((root / "translations" / f"{code}.json").read_text(encoding="utf-8"))
        for scope in ("config", "options"):
            step = obj[scope]["step"]["delivery"]
            for key in ("ai_rewrite_announcements", "ai_conversation_agent"):
                assert step["data"][key]
                assert step["data_description"][key]
            assert obj[scope]["error"]["missing_ai_service"]
            assert obj[scope]["error"]["invalid_ai_agent"]


def test_delivery_form_agent_dropdown_and_independent_saving(monkeypatch, adapter):
    from test_area_config_flow import _make_options
    from test_discovery import MockState

    options = _make_options(monkeypatch, adapter)
    options.hass._values["conversation.my_ai"] = MockState(
        "conversation.my_ai", "unknown", name="Local Agent"
    )
    options.hass.services = SimpleNamespace(
        has_service=lambda d, s: (d, s) == ("conversation", "process")
    )
    asyncio.run(options.async_step_init())
    form = asyncio.run(options.async_step_delivery())
    assert "ai_rewrite_announcements" in form["data_schema"]
    assert "ai_conversation_agent" in form["data_schema"]
    selector = form["data_schema"]["ai_conversation_agent"]
    assert selector.config.options[0]["value"] == "default"
    assert next(k.default for k in form["data_schema"] if k == "ai_conversation_agent") == "default"
    save = asyncio.run(options.async_step_delivery({
        "ai_rewrite_announcements": True,
        "ai_conversation_agent": "conversation.my_ai"
    }))
    assert save["completed"]["data"]["ai_rewrite_announcements"] is True
    assert save["completed"]["data"]["ai_conversation_agent"] == "conversation.my_ai"
    assert save["completed"]["data"]["areas"] == ["living"]


def test_invalid_agent_and_missing_conversation_action_rejected(monkeypatch, adapter):
    from test_area_config_flow import _make_options

    options = _make_options(monkeypatch, adapter)
    asyncio.run(options.async_step_init())
    without_service = asyncio.run(options.async_step_delivery({
        "ai_rewrite_announcements": True,
        "ai_conversation_agent": "default",
    }))
    assert without_service["errors"] == {"base": "missing_ai_service"}

    options.hass.services = SimpleNamespace(
        has_service=lambda domain, action: (domain, action) == ("conversation", "process")
    )
    invalid = asyncio.run(options.async_step_delivery({
        "ai_rewrite_announcements": True,
        "ai_conversation_agent": "switch.not_an_agent"
    }))
    assert invalid["errors"] == {"base": "invalid_ai_agent"}


def test_ai_is_not_used_on_announcement_hub_path():
    root = Path(__file__).resolve().parents[1] / "custom_components" / "air_quality_advisor"
    manager = (root / "manager.py").read_text(encoding="utf-8")
    assert "if ai_effectively_enabled(config) and has_direct_receiver:" in manager
    assert "async_rewrite_announcement" in manager
