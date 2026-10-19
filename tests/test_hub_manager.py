"""Exercise real advisor delivery with a mocked HA runtime and Hub presence."""
from __future__ import annotations

import asyncio
import importlib
import sys
import types
from types import SimpleNamespace

import pytest

from test_discovery import adapter, FakeHass, MockState
from custom_components.air_quality_advisor.logic import Recommendation, Window, Reason, Plan


REC = Recommendation(
    "close", "living", "Living room",
    (Window("binary_sensor.living_window", "Living window", True),),
    (Reason("weather_wind", "Outdoor wind", "55 km/h"),),
)


@pytest.fixture
def delivery_module(monkeypatch, adapter):
    """Import manager with only its small HA import surface stubbed."""
    core = sys.modules["homeassistant.core"]
    core.Event = object
    core.HomeAssistant = object
    core.callback = lambda function: function
    const = types.ModuleType("homeassistant.const")
    const.EVENT_STATE_CHANGED = "state_changed"
    monkeypatch.setitem(sys.modules, "homeassistant.const", const)
    entries = types.ModuleType("homeassistant.config_entries")
    entries.ConfigEntry = object
    monkeypatch.setitem(sys.modules, "homeassistant.config_entries", entries)
    dispatch = types.ModuleType("homeassistant.helpers.dispatcher")
    dispatch.async_dispatcher_send = lambda *args: None
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.dispatcher", dispatch)
    events = types.ModuleType("homeassistant.helpers.event")
    events.async_call_later = lambda *args: None
    events.async_track_time_interval = lambda *args: None
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.event", events)
    package = "custom_components.air_quality_advisor.manager"
    monkeypatch.delitem(sys.modules, package, raising=False)
    return importlib.import_module(package)


class Services:
    def __init__(self, *, hub_response=None, hub_failure=None, hub_action=True,
                 direct=True, tts=True, persistent=True):
        self.hub_response = hub_response
        self.hub_failure = hub_failure
        self.hub_action = hub_action
        self.direct = direct
        self.tts = tts
        self.persistent = persistent
        self.calls = []

    def has_service(self, domain, action):
        return {
            ("notify", "announcement_hub"): self.hub_action,
            ("notify", "send_message"): self.direct,
            ("tts", "speak"): self.tts,
            ("persistent_notification", "create"): self.persistent,
        }.get((domain, action), False)

    async def async_call(self, domain, action, data, **kwargs):
        self.calls.append((domain, action, data, kwargs))
        if (domain, action) == ("notify", "announcement_hub"):
            if self.hub_failure:
                raise self.hub_failure
            return self.hub_response
        return None


def advisor(module, config=None, services=None, *, hub_installed=True, hub_running=True):
    config = config or {}
    if services is None:
        services = Services(hub_response={"accepted": True, "notify_outputs": ["notify.living"]})
    hass = FakeHass([
        MockState("notify.living", "idle"),
        MockState("media_player.living", "off"),
        MockState("tts.default", "idle"),
    ], {
        "notify.living": "living", "media_player.living": "living",
    })
    hass.config = SimpleNamespace(language="en")
    hass.services = services
    hass.data = {"announcement_hub": {"manager": SimpleNamespace(running=hub_running)}}
    hass.config_entries = SimpleNamespace(async_entries=lambda domain: (
        [SimpleNamespace(state="loaded")] if hub_installed and domain == "announcement_hub" else []
    ))
    entry = SimpleNamespace(
        entry_id="entry_1",
        data={
            "use_announcement_hub": True,
            "ai_rewrite_announcements": True,
            "ai_conversation_agent": "conversation.my_ai",
            "notify_entities": ["notify.living"],
            "tts_engine": "tts.default",
            "media_players": ["media_player.living"],
            "language": "en",
            **config,
        },
        options={},
    )
    manager = module.AirQualityManager(hass, entry)
    manager.plan = Plan("close", False, (), (REC,), ())
    return manager, services


def test_true_and_false_hub_ai_forwarding_without_local_rewrite(monkeypatch, delivery_module):
    module = delivery_module
    async def forbidden(*args, **kwargs):
        raise AssertionError("The Hub must rewrite its own queued messages")
    monkeypatch.setattr(module, "async_rewrite_announcement", forbidden)
    m, s = advisor(module)
    outcome = asyncio.run(m.async_announce(channels="both"))
    assert outcome["submitted"] == 1
    assert [(a, b) for a, b, *_ in s.calls] == [("notify", "announcement_hub")]
    data = s.calls[0][2]
    assert data["use_ai"] is True
    assert data["ai_agent"] == "conversation.my_ai"
    assert "text" in data and data["text"]
    assert "text_tts" not in data and "text_notify" not in data
    assert data["area"] == ["Living room"]
    assert "output" not in data
    assert "occupied_only" not in data

    m, s = advisor(module, {"ai_rewrite_announcements": False})
    assert asyncio.run(m.async_announce(channels="notification"))["submitted"] == 1
    assert s.calls[0][2]["use_ai"] is False
    assert s.calls[0][2]["text_notify"]
    assert "text" not in s.calls[0][2]
    assert "ai_agent" not in s.calls[0][2]


def test_hub_is_configured_but_stopped_routes_to_direct_notify_and_tts(monkeypatch, delivery_module):
    module = delivery_module
    counter = []
    async def rewrite(*args):
        counter.append(args)
        return "Rephrased safe instruction"
    monkeypatch.setattr(module, "async_rewrite_announcement", rewrite)
    m, s = advisor(module, hub_running=False)
    outcome = asyncio.run(m.async_announce(channels="both"))
    assert outcome["submitted"] == 2
    assert not any(domain == "notify" and action == "announcement_hub" for domain, action, *_ in s.calls)
    assert [(a, b) for a, b, *_ in s.calls] == [
        ("notify", "send_message"), ("tts", "speak"),
    ]
    assert s.calls[0][2]["message"] == s.calls[1][2]["message"] == "Rephrased safe instruction"
    assert len(counter) == 1


def test_hub_rejected_call_is_hub_owned_no_native_persistent_notification(delivery_module):
    services = Services(hub_failure=ValueError("Hub rejected use_ai"), direct=False, tts=False)
    manager, s = advisor(delivery_module, {
        "notify_entities": [], "tts_engine": None, "media_players": [],
        "ai_rewrite_announcements": False,
    }, services=services)
    outcome = asyncio.run(manager.async_announce(channels="notification"))
    assert outcome["submitted"] == 0  # Rejected is NOT claimed as queued.
    assert len(outcome["errors"]) == 1 and "did not queue" in outcome["errors"][0]
    assert [(a, b) for a, b, *_ in s.calls] == [("notify", "announcement_hub")]
    assert not any(a == "persistent_notification" for a, *_ in s.calls)


def test_unconfigured_hub_service_cannot_receive_a_message(delivery_module):
    manager, services = advisor(delivery_module, hub_installed=False)
    result = asyncio.run(manager.async_announce(channels="notification"))
    assert result["submitted"] == 1
    assert services.calls[0][:2] == ("notify", "send_message")
    assert all(action != "announcement_hub" for domain, action, *_ in services.calls)


def test_accepted_hub_job_never_triggers_duplicate_home_assistant_fallback(delivery_module):
    services = Services(hub_response={"accepted": True, "job_id": "queued-1",
                                     "status": "pending", "notify_outputs": [],
                                     "tts_engines": []}, direct=False, tts=False)
    manager, calls = advisor(delivery_module, {"notify_entities": [],
        "tts_engine": None, "media_players": [],
        "ai_rewrite_announcements": False}, services=services)
    result = asyncio.run(manager.async_announce(channels="notification"))
    assert result["submitted"] == 1
    assert result["errors"] == []
    assert [(domain, action) for domain, action, *_ in calls.calls] == [
        ("notify", "announcement_hub"),
    ]


def test_missing_all_system_fallback_services_returns_error(delivery_module):
    services = Services(hub_action=False, direct=False, tts=False, persistent=False)
    manager, calls = advisor(delivery_module, {"notify_entities": [], "tts_engine": None,
         "media_players": [], "ai_rewrite_announcements": False}, services=services)
    response = asyncio.run(manager.async_announce(channels="both"))
    assert response["submitted"] == 0
    assert response["errors"]


@pytest.mark.parametrize("reply, failure", [
    ({"accepted": False}, None),
    (None, None),
    (None, ValueError("The selected text has no configured matching output")),
    (None, RuntimeError("Hub queue full")),
])
def test_live_hub_rejections_never_trigger_direct_or_system_notifications(
    delivery_module, reply, failure,
):
    # Matches the real routing rejection observed in the user's logs.
    calls = Services(hub_response=reply, hub_failure=failure,
                     direct=True, tts=True, persistent=True)
    manager, services = advisor(delivery_module, services=calls)
    result = asyncio.run(manager.async_announce(channels="both"))
    assert result["submitted"] == 0
    assert len(result["errors"]) == 1
    assert [(a, b) for a, b, *_ in services.calls] == [
        ("notify", "announcement_hub"),
    ]


def test_live_hub_timeout_does_not_create_native_notification(
    monkeypatch, delivery_module,
):
    import custom_components.air_quality_advisor.hub_delivery as delivery
    async def slow_service(*args, **kwargs):
        await asyncio.sleep(0.05)
        return {"accepted":True,"job_id":"eventually"}
    calls = Services(direct=True, tts=True, persistent=True)
    calls.async_call = slow_service
    manager, _ = advisor(delivery_module, services=calls)
    monkeypatch.setattr(delivery, "HUB_RESPONSE_TIMEOUT", 0.001)
    result = asyncio.run(manager.async_announce(channels="both"))
    assert result["submitted"] == 0
    assert result["errors"]


def test_live_hub_uses_current_ha_area_name_from_recommendation(
    delivery_module,
):
    calls = Services(hub_response={"accepted":True, "job_id":"kitchen-queued"})
    manager, actual = advisor(delivery_module, services=calls)
    kitchen = Recommendation(
        "close", "kouzina", "Küche",
        (Window("binary_sensor.kuche_window","Fenster Küche",True),),
        (Reason("weather_condition","weather.home","rainy"),),
    )
    manager.plan = Plan("close",False,(),(kitchen,),())
    result = asyncio.run(manager.async_announce(channels="both"))
    assert result["submitted"] == 1 and result["errors"] == []
    assert [(a,b) for a,b,*_ in actual.calls] == [("notify","announcement_hub")]
    payload = actual.calls[0][2]
    assert payload["area"] == ["Küche"]
    assert "output" not in payload
    assert payload["text"]
    assert "occupied_only" not in payload
    assert "service" not in payload
