"""Optional Announcement Hub integration with a deterministic HA fallback.

A registered notify action alone is insufficient: Announcement Hub registers
its action before an integration instance is fully configured. Only offer the
Hub when a matching config entry exists and route through it when loaded.
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
    """Explicit AI override is authoritative even if Hub defaults differ."""
    data: dict[str, Any] = {
        "title": title,
        "output": [recommendation.area_id],
        "level": "warning" if recommendation.action == "close" else "info",
        "occupied_only": False,
        "use_ai": bool(use_ai),
    }
    if speech:
        data["text_tts"] = message
    if visual:
        data["text_notify"] = message
    if language and language != "auto":
        data["language"] = language
    if use_ai and agent_id and agent_id != "default":
        data["ai_agent"] = agent_id
    return data


async def async_submit_hub(hass: Any, payload: dict[str, Any]) -> bool:
    """Return True when Hub acknowledges acceptance into its queue.

    Hub's accepted=True is authoritative; do not inspect its routes or AI
    result. Hub currently rewrites before acknowledgement, so allow time for
    a slow conversation agent. The timeout here is only an acknowledgement
    fail-safe, never an AI processing deadline.
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
        _LOGGER.warning("Announcement Hub submission failed; using Home Assistant: %s", err)
        return False
    if not isinstance(reply, dict) or reply.get("accepted") is not True:
        _LOGGER.warning("Announcement Hub did not acknowledge a queued announcement")
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
                "notification_id": f"air_quality_advisor_{area_id}",
            },
            blocking=True,
        )
    except asyncio.CancelledError:
        raise
    except Exception as err:
        _LOGGER.warning("Home Assistant persistent notification fallback failed: %s", err)
        return False
    return True
