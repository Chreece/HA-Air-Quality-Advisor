"""Home Environment Manager (backward-compatible Home Assistant domain)."""

from __future__ import annotations

import json
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
PUBLIC_ACTION_DOMAIN = "home_environment_manager"  # Alias only; existing domain remains.


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Serve and register the card once; installation needs no www copy/YAML."""
    hass.data.setdefault(DOMAIN, {})
    card_path = Path(__file__).parent / "frontend" / "air-quality-advisor-card.js"
    await hass.http.async_register_static_paths([
        StaticPathConfig(f"/{DOMAIN}/air-quality-advisor-card.js", str(card_path), True),
    ])
    # This is a native HA frontend registration, not a Lovelace storage mutation.
    # Pin the cache key to the integration version so HACS updates refresh the JS.
    manifest = json.loads(
        (Path(__file__).parent / "manifest.json").read_text(encoding="utf-8")
    )
    # Bundled asset and HACS release version share ONE authoritative source.
    # Rebranding must not change the original integration domain/path.
    add_extra_js_url(
        hass, f"/{DOMAIN}/air-quality-advisor-card.js?v={manifest['version']}"
    )
    return True


NATIVE_CLIMATE_SCHEMA = probatio.Schema({
    probatio.Required("area"): cv.string,
    probatio.Required("action"): probatio.In(["pause", "resume"]),
})

CLIMATE_DIAGNOSTICS_SCHEMA = probatio.Schema({
    probatio.Optional("area"): cv.string,
})

PID_CONTROL_SCHEMA = probatio.Schema({
    probatio.Required("area"): cv.string,
    probatio.Required("action"): probatio.In(["pause", "resume", "reset"]),
})


SERVICE_SCHEMA = probatio.Schema({
    probatio.Optional("language"): probatio.In([tag for tag in LANGUAGES if tag != "auto"]),
    probatio.Optional("channels", default="both"): probatio.In(["both", "tts", "notification"]),
    probatio.Optional("areas"): probatio.All(probatio.EnsureList(), [cv.string]),
})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Existing installations retain entry IDs and selected devices. Only the
    # uncustomized legacy display title is migrated to the new product name.
    if getattr(entry, "title", None) in ("Air Quality Advisor", "Home Environment Advisor"):
        hass.config_entries.async_update_entry(entry, title="Home Environment Manager")
    manager = AirQualityManager(hass, entry)
    entry.runtime_data = manager
    # Even if an experimental device controller fails during its startup,
    # attempt to stop any earlier-started controllers. Leave the original
    # installation error visible and never register partial service routes.
    try:
        await manager.async_start()
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
        # A user-facing service alias for the rebrand. Both service domains
        # intentionally call the same manager: no duplicate announcements.
        if not hass.services.has_service(PUBLIC_ACTION_DOMAIN, "announce"):
            hass.services.async_register(
                PUBLIC_ACTION_DOMAIN, "announce", async_announce_action,
                schema=SERVICE_SCHEMA, supports_response=SupportsResponse.OPTIONAL,
            )
    if not hass.services.has_service(PUBLIC_ACTION_DOMAIN, "pid_control"):
        async def async_pid_action(call: ServiceCall) -> ServiceResponse:
            managers = list(hass.data.get(DOMAIN, {}).values())
            if not managers:
                return {"accepted": False, "reason": "Integration is not loaded"}
            # Accept only the selected registry area ID, no implicit whole-house
            # or fanout targeting; the PID service never changes HVAC modes.
            result = await managers[0].async_pid_control(
                area=call.data["area"], action=call.data["action"],
            )
            return result if call.return_response else None

        for service_domain in (PUBLIC_ACTION_DOMAIN, DOMAIN):
            if not hass.services.has_service(service_domain, "pid_control"):
                hass.services.async_register(
                    service_domain, "pid_control", async_pid_action,
                    schema=PID_CONTROL_SCHEMA, supports_response=SupportsResponse.OPTIONAL,
                )
    if not hass.services.has_service(PUBLIC_ACTION_DOMAIN, "climate_control"):
        async def async_native_action(call: ServiceCall) -> ServiceResponse:
            managers=list(hass.data.get(DOMAIN, {}).values())
            if not managers:
                return {"accepted":False,"reason":"not_loaded"}
            result=await managers[0].async_climate_control(
                call.data["area"],call.data["action"]
            )
            return result if call.return_response else None
        for domain in (DOMAIN,PUBLIC_ACTION_DOMAIN):
            if not hass.services.has_service(domain,"climate_control"):
                hass.services.async_register(
                    domain,"climate_control",async_native_action,
                    schema=NATIVE_CLIMATE_SCHEMA,
                    supports_response=SupportsResponse.OPTIONAL,
                )
    if not hass.services.has_service(PUBLIC_ACTION_DOMAIN, "climate_diagnostics"):
        async def async_diagnostics(call: ServiceCall) -> ServiceResponse:
            # This is an explicit read-only request. Only configured rooms
            # are reported; no raw registry secrets, device identifiers, or
            # HA service commands are collected or executed.
            managers = list(hass.data.get(DOMAIN, {}).values())
            if not managers:
                return {"schema_version": 1, "status": "not_loaded",
                        "read_only": True, "no_commands_sent": True, "rooms": []}
            area = call.data.get("area")
            responses = [manager.climate_diagnostics(area=area)
                         for manager in managers]
            rooms = [room for response in responses
                     for room in response.get("rooms", [])]
            response = {
                "schema_version": 1,
                "status": "ok" if rooms or area is None else "area_not_configured",
                "read_only": True,
                "no_commands_sent": True,
                "physical_hardware_safety_verified": False,
                "rooms": rooms,
            }
            return response if call.return_response else None

        for domain in (DOMAIN, PUBLIC_ACTION_DOMAIN):
            if not hass.services.has_service(domain, "climate_diagnostics"):
                hass.services.async_register(
                    domain, "climate_diagnostics", async_diagnostics,
                    schema=CLIMATE_DIAGNOSTICS_SCHEMA,
                    supports_response=SupportsResponse.OPTIONAL,
                )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.async_stop()
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, "announce")
        if hass.services.has_service(PUBLIC_ACTION_DOMAIN, "announce"):
            hass.services.async_remove(PUBLIC_ACTION_DOMAIN, "announce")
        for service_domain in (PUBLIC_ACTION_DOMAIN, DOMAIN):
            if hass.services.has_service(service_domain, "pid_control"):
                hass.services.async_remove(service_domain, "pid_control")
            if hass.services.has_service(service_domain, "climate_control"):
                hass.services.async_remove(service_domain, "climate_control")
            if hass.services.has_service(service_domain, "climate_diagnostics"):
                hass.services.async_remove(service_domain, "climate_diagnostics")
    return True
