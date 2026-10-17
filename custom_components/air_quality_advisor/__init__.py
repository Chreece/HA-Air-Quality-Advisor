"""Air Quality Advisor for Home Assistant."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import probatio

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, PLATFORMS, LANGUAGES
from .manager import AirQualityManager

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Serve and register the card once; installation needs no www copy/YAML."""
    hass.data.setdefault(DOMAIN, {})
    card_path = Path(__file__).parent / "frontend" / "air-quality-advisor-card.js"
    await hass.http.async_register_static_paths([
        StaticPathConfig(f"/{DOMAIN}/air-quality-advisor-card.js", str(card_path), True),
    ])
    # This is a native HA frontend registration, not a Lovelace storage mutation.
    # Pin the cache key to the integration version so HACS updates refresh the JS.
    add_extra_js_url(hass, f"/{DOMAIN}/air-quality-advisor-card.js?v=0.2.4")
    return True


SERVICE_SCHEMA = probatio.Schema({
    probatio.Optional("language"): probatio.In([tag for tag in LANGUAGES if tag != "auto"]),
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
