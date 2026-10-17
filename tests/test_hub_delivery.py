"""Announcement Hub presence, AI overrides and fallback acknowledgements."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from custom_components.air_quality_advisor.hub_delivery import (
    hub_installed, hub_available, make_hub_payload,
    async_submit_hub, async_system_notification,
)
from custom_components.air_quality_advisor.logic import Recommendation, Window, Reason


REC = Recommendation(
    "open", "living", "Living room",
    (Window("binary_sensor.living_window", "Living window", False),),
    (Reason("inside_co2", "CO₂", "1,250 ppm"),),
)


class Registry:
    def __init__(self, *, hub_active=True, fail=None, reply=None, pn_active=True):
        self.hub_active = hub_active
        self.pn_active = pn_active
        self.fail = fail
        self.reply = reply
        self.calls = []

    def has_service(self, domain, action):
        if (domain, action) == ("notify", "announcement_hub"):
            return self.hub_active
        if (domain, action) == ("persistent_notification", "create"):
            return self.pn_active
        return False

    async def async_call(self, domain, action, data, **kwargs):
        self.calls.append((domain, action, data, kwargs))
        if (domain, action) == ("notify", "announcement_hub"):
            if isinstance(self.fail, Exception):
                raise self.fail
            if callable(self.fail):
                return await self.fail()
            return self.reply
        return None


def home(*, configured=True, running=True, action=True, reply=None, fail=None, state="loaded"):
    manager = SimpleNamespace(running=running)
    reg = Registry(hub_active=action, reply=reply, fail=fail)
    entries = [SimpleNamespace(state=state)] if configured else []
    hass = SimpleNamespace(
        services=reg,
        config_entries=SimpleNamespace(async_entries=lambda domain: entries if domain == "announcement_hub" else []),
        data={"announcement_hub": {"manager": manager}},
    )
    return hass, reg


def test_hub_not_offered_when_notification_action_registered_but_not_configured():
    hass, _ = home(configured=False)
    assert not hub_installed(hass)
    assert not hub_available(hass)


def test_configured_hub_shown_even_when_temporarily_stopped_but_is_not_ready():
    hass, _ = home(configured=True, running=False)
    assert hub_installed(hass)
    assert not hub_available(hass)
    hass.data["announcement_hub"]["manager"].running = True
    assert hub_available(hass)


def test_hub_without_manager_requires_loaded_entry():
    hass, _ = home(state="not_loaded")
    hass.data.pop("announcement_hub")
    assert not hub_available(hass)
    hass.config_entries.async_entries = lambda domain: [SimpleNamespace(state="loaded")]
    assert hub_available(hass)


def test_true_and_false_ai_overrides_are_forwarded_and_agent_optional():
    enabled = make_hub_payload(REC, "Open", "Good fresh air", speech=True, visual=True,
                               language="el", use_ai=True, agent_id="conversation.ai")
    assert enabled["use_ai"] is True
    assert enabled["ai_agent"] == "conversation.ai"
    assert enabled["text_tts"] == enabled["text_notify"] == "Good fresh air"
    assert enabled["output"] == ["living"]
    assert enabled["occupied_only"] is False
    assert enabled["language"] == "el"
    disabled = make_hub_payload(REC, "Open", "Original", speech=False, visual=True,
                                language="auto", use_ai=False, agent_id="conversation.ai")
    assert disabled["use_ai"] is False
    assert "ai_agent" not in disabled
    assert "language" not in disabled
    default = make_hub_payload(REC, "Open", "Original", speech=True, visual=False,
                               language="en", use_ai=True, agent_id="default")
    assert default["use_ai"] is True and "ai_agent" not in default


def test_hub_queue_acknowledgement_is_the_only_success_criterion():
    payload = {"text_notify": "hello"}
    for response in (
        {"accepted": True, "job_id": "test-1", "status": "pending",
         "notify_outputs": [], "room_tts_players": [], "tts_engines": []},
        {"accepted": True, "job_id": "test-2", "status": "processing"},
        {"accepted": True},
    ):
        good, reg = home(reply=response)
        assert asyncio.run(async_submit_hub(good, payload))
        assert reg.calls == [("notify", "announcement_hub", payload,
                             {"blocking": True, "return_response": True})]

    for response in (None, {"accepted": False}, {"status": "pending"}):
        hass, _ = home(reply=response)
        assert not asyncio.run(async_submit_hub(hass, payload))


def test_hub_allows_slow_acknowledgements_before_falling_back():
    import custom_components.air_quality_advisor.hub_delivery as delivery
    assert delivery.HUB_RESPONSE_TIMEOUT >= 90  # Hub may rewrite before queueing.
    async def delayed_acceptance():
        await asyncio.sleep(0.025)
        return {"accepted": True, "job_id": "slow-accepted", "status": "pending"}
    hass, _ = home(fail=delayed_acceptance)
    assert asyncio.run(async_submit_hub(hass, {"text_notify": "hello"}))


def test_unconfigured_or_unavailable_hub_never_called():
    for configured, running, registered in (
        (False, True, True), (True, False, True), (True, True, False)
    ):
        hass, services = home(configured=configured, running=running, action=registered)
        assert not asyncio.run(async_submit_hub(hass, {"text_notify": "test"}))
        assert services.calls == []


@pytest.mark.parametrize("error", [ValueError("unsupported use_ai"), RuntimeError("offline")])
def test_hub_service_rejection_uses_fallback(error):
    hass, _ = home(fail=error)
    assert not asyncio.run(async_submit_hub(hass, {"use_ai": True}))


def test_hub_timeout_falls_back_without_suppressing_main_task(monkeypatch):
    import custom_components.air_quality_advisor.hub_delivery as delivery

    async def slow():
        await asyncio.sleep(1)
    hass, _ = home(fail=slow)
    monkeypatch.setattr(delivery, "HUB_RESPONSE_TIMEOUT", 0.002)
    assert not asyncio.run(async_submit_hub(hass, {"text_notify": "hello"}))


def test_system_notification_uses_stable_room_id_and_catches_failures():
    hass, reg = home()
    assert asyncio.run(async_system_notification(hass, "Air quality", "Open window", "living"))
    assert reg.calls[0][:3] == (
        "persistent_notification", "create",
        {"title": "Air quality", "message": "Open window",
         "notification_id": "air_quality_advisor_living"},
    )
    hass, reg = home()
    reg.pn_active = False
    assert not asyncio.run(async_system_notification(hass, "Title", "Message", "room"))
    assert reg.calls == []
    hass, reg = home(fail=None)
    original = reg.async_call
    async def failing(*args, **kwargs):
        raise RuntimeError("offline")
    reg.async_call = failing
    assert not asyncio.run(async_system_notification(hass, "T", "M", "living"))
