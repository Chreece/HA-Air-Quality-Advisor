"""Authenticated, read-only full Home Environment Manager dashboard snapshots.

A complete multi-room snapshot is presentation data, not sensor state. Keeping
it off state attributes avoids Home Assistant Recorder's 16384-byte limit
without discarding any measurements, actions or per-device climate details.
"""
from __future__ import annotations

from typing import Any

import probatio

from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .dashboard import dashboard_snapshot

COMMAND = f"{DOMAIN}/dashboard"


@websocket_api.websocket_command({
    probatio.Required("type"): COMMAND,
    probatio.Required("entity_id"): str,
})
@callback
def websocket_dashboard(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Fetch full state of precisely this accessible recommendation sensor."""
    entity_id = msg["entity_id"]
    if not entity_id.startswith("sensor."):
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND,
                              "Recommendation sensor not found")
        return

    record = er.async_get(hass).async_get(entity_id)
    entry_id = getattr(record, "config_entry_id", None)
    if (record is None
            or getattr(record, "platform", None) != DOMAIN
            or not isinstance(entry_id, str)
            or getattr(record, "unique_id", None) != f"{entry_id}_recommendation"):
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND,
                              "Recommendation sensor not found")
        return

    # Equivalent to the access checks used for get_states / subscribe_entities.
    # Never expose other people's room details merely because an entry ID was
    # guessed or the requester can read some unrelated Home Assistant entity.
    user = connection.user
    if not (user.is_admin or user.permissions.check_entity(entity_id, POLICY_READ)):
        connection.send_error(msg["id"], websocket_api.ERR_UNAUTHORIZED,
                              "Not authorized to read recommendation sensor")
        return

    manager = hass.data.get(DOMAIN, {}).get(entry_id)
    if manager is None or manager.entry.entry_id != entry_id:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND,
                              "Home Environment Manager not loaded")
        return

    # Pure transformation of the latest validated Plan; no I/O, no physical
    # control, no registry changes, and no Recorder/database writes.
    connection.send_result(
        msg["id"], dashboard_snapshot(manager.plan, manager.thresholds),
    )


@callback
def async_register_dashboard_api(hass: HomeAssistant) -> None:
    """Register once when the canonical integration is initialized."""
    websocket_api.async_register_command(hass, websocket_dashboard)
