"""Home Environment Manager-to-Announcement Hub message handoff.

The Advisor owns the actionable recommendation, text, and Home Assistant room
name, but never selects a Hub device, room-policy fallback, or occupancy
restriction. When Hub is running, rejected submissions are errors under Hub
ownership, not instructions to send a parallel HA notification.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)
HUB_DOMAIN = "announcement_hub"
HUB_ACTION = "announcement_hub"
HUB_RESPONSE_TIMEOUT = 120  # Safety bound for Hub acknowledgement, not an AI limit.


def _hub_entries(hass: Any) -> list[Any]:
    getter = getattr(getattr(hass, "config_entries", None), "async_entries", None)
    if not callable(getter):
        return []
    try:
        return list(getter(HUB_DOMAIN))
    except (TypeError, ValueError, AttributeError):
        return []


def hub_installed(hass: Any) -> bool:
    """Only a configured Announcement Hub instance enables the GUI option."""
    return bool(_hub_entries(hass))


def hub_available(hass: Any) -> bool:
    """Require an installed, loaded Hub with a registered notify action."""
    entries = _hub_entries(hass)
    if not entries or not hass.services.has_service("notify", HUB_ACTION):
        return False
    hub_data = getattr(hass, "data", {}).get(HUB_DOMAIN) or {}
    manager = hub_data.get("manager") if isinstance(hub_data, dict) else None
    if manager is not None:
        return bool(getattr(manager, "running", False))
    # Support older/newer Hub versions where the runtime manager is private.
    return any(
        str(getattr(getattr(entry, "state", ""), "value", getattr(entry, "state", ""))).lower()
        == "loaded"
        for entry in entries
    )


def make_hub_payload(
    recommendation: Any, title: str, message: str, *,
    speech: bool, visual: bool, language: str,
    use_ai: bool, agent_id: str,
) -> dict[str, Any]:
    """Forward original text and the room's actual HA name to Hub.

    Hub accepts both IDs and names. Use the area name already resolved by
    Advisor's HA area registry, preserving umlauts and user renames. Hub owns
    physical outputs, fallback routing, AI, queueing and occupancy policy.
    The shared "text" field is used whenever both channels were selected;
    single-channel calls retain channel-specific fields so one cannot
    accidentally enable the other via Hub's shared-text semantics.
    """
    data: dict[str, Any] = {
        "title": title,
        "area": [recommendation.area_name],
        "level": "warning" if recommendation.action == "close" else "info",
        "use_ai": bool(use_ai),
    }
    if speech and visual:
        data["text"] = message
    elif speech:
        data["text_tts"] = message
    elif visual:
        data["text_notify"] = message
    if language and language != "auto":
        data["language"] = language
    if use_ai and agent_id and agent_id != "default":
        data["ai_agent"] = agent_id
    return data


async def async_submit_hub(hass: Any, payload: dict[str, Any]) -> bool:
    """Report whether Hub actually queued the submitted message.

    Hub's accepted=True is authoritative; do not inspect its routes or AI
    result. Hub currently rewrites before acknowledgement, so allow time for
    a slow conversation agent. A rejection returns False but must NEVER make
    Advisor produce an additional native notification while Hub is live.
    """
    if not hub_available(hass):
        return False
    try:
        reply = await asyncio.wait_for(
            hass.services.async_call(
                "notify", HUB_ACTION, payload,
                blocking=True, return_response=True,
            ),
            timeout=HUB_RESPONSE_TIMEOUT,
        )
    except asyncio.CancelledError:
        raise
    except Exception as err:
        _LOGGER.warning("Announcement Hub did not accept announcement (no Advisor fallback while Hub is running): %s", err)
        return False
    if not isinstance(reply, dict) or reply.get("accepted") is not True:
        _LOGGER.warning("Announcement Hub did not acknowledge queue acceptance; native fallback suppressed while Hub is running")
        return False
    # Hub is the delivery authority. Its acknowledgement means the job has
    # been queued, regardless of output details (which Hub may resolve later).
    # Never retry locally after accepted=True: that would duplicate alerts.
    _LOGGER.debug(
        "Announcement Hub accepted queued job %s (status=%s)",
        reply.get("job_id", "unknown"),
        reply.get("status", "unknown"),
    )
    return True


async def async_system_notification(hass: Any, title: str, message: str, area_id: str) -> bool:
    """Final, built-in visual fallback when configured direct outputs fail."""
    if not hass.services.has_service("persistent_notification", "create"):
        _LOGGER.warning("No Home Assistant persistent_notification.create action for fallback")
        return False
    try:
        await hass.services.async_call(
            "persistent_notification", "create",
            {
                "title": title,
                "message": message,
                "notification_id": f"environment_manager_{area_id}",
            },
            blocking=True,
        )
    except asyncio.CancelledError:
        raise
    except Exception as err:
        _LOGGER.warning("Home Assistant persistent notification fallback failed: %s", err)
        return False
    return True
