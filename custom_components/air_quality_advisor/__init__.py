"""Air Quality Advisor for Home Assistant."""

from __future__ import annotations

from typing import Any

import probatio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, PLATFORMS
from .manager import AirQualityManager

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


SERVICE_SCHEMA = probatio.Schema({
    probatio.Optional("language"): probatio.In(["en", "de", "el", "fr", "es"]),
    probatio.Optional("channels", default="both"): probatio.In(["both", "tts", "notification"]),
    probatio.Optional("areas"): probatio.All(probatio.EnsureList(), [cv.string]),
})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    manager = AirQualityManager(hass, entry)
    entry.runtime_data = manager
    await manager.async_start()
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await manager.async_stop()
        raise
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager

    if not hass.services.has_service(DOMAIN, "announce"):
        async def async_announce_action(call: ServiceCall) -> ServiceResponse:
            managers = list(hass.data.get(DOMAIN, {}).values())
            if not managers:
                return {"submitted": 0, "reason": "Integration is not loaded"}
            manager = managers[0]
            result = await manager.async_announce(
                language=call.data.get("language"),
                channels=call.data.get("channels", "both"),
                areas=call.data.get("areas"),
            )
            return result if call.return_response else None

        hass.services.async_register(
            DOMAIN, "announce", async_announce_action,
            schema=SERVICE_SCHEMA, supports_response=SupportsResponse.OPTIONAL,
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.async_stop()
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, "announce")
    return True
