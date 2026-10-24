"""Home Environment Manager."""

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

async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Serve the canonical integration."""
    hass.data.setdefault(DOMAIN, {})
    card_path = Path(__file__).parent / "frontend" / "air-quality-advisor-card.js"
    await hass.http.async_register_static_paths([
        StaticPathConfig(f"/{DOMAIN}/air-quality-advisor-card.js", str(card_path), True),
    ])
    # This is a native HA frontend registration, not a Lovelace storage mutation.
    # Pin the cache key to the integration version so HACS updates refresh the JS.
    # File reads are blocking operations, even for a tiny manifest. Load
    # this once in HA's executor instead of opening it on the event loop.
    manifest = await hass.async_add_executor_job(
        lambda: json.loads(
            (Path(__file__).parent / "manifest.json").read_text(encoding="utf-8")
        )
    )
    # Bundled asset and HACS release version share ONE authoritative source.
    # Rebranding must not change the original integration domain/path.
    add_extra_js_url(
        hass, f"/{DOMAIN}/air-quality-advisor-card.js?v={manifest['version']}"
    )
    # A full multi-room dashboard cannot safely fit in Recorder attributes.
    # Its authenticated WebSocket API is read-only and registered just once
    # per canonical integration setup, not once per config entry.
    from .dashboard_api import async_register_dashboard_api

    async_register_dashboard_api(hass)
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


def _exact_room_manager(hass: HomeAssistant, area: str,
                        section: str) -> tuple[Any | None, str | None]:
    """Select exactly one active owner for room-scoped control actions.

    Multiple config entries must never silently route
    a room to the first one or broadcast a control action to multiple
    managers; ambiguous area ownership must fail closed.
    """
    candidates=[]
    for manager in hass.data.get(DOMAIN, {}).values():
        entry=getattr(manager,"entry",None)
        if entry is None:
            continue
        data=getattr(entry,"data",{})
        options=getattr(entry,"options",{})
        if not isinstance(data,dict) or not isinstance(options,dict):
            continue
        room_settings={**data,**options}.get(section,{})
        if not isinstance(room_settings,dict):
            continue
        config=room_settings.get(area)
        if isinstance(config,dict) and config.get("enabled") is True:
            candidates.append(manager)
    if len(candidates)>1:
        return None,"ambiguous_room_across_config_entries"
    if not candidates:
        return None,"room_not_configured_or_disabled"
    return candidates[0],None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    from .room_hubs import async_sync_room_hubs, async_watch_room_hubs, home_subentry_id
    room_subentries = async_sync_room_hubs(hass, entry)
    manager = AirQualityManager(hass, entry)
    manager._room_subentries = room_subentries
    manager._home_subentry = home_subentry_id(entry)
    entry.runtime_data = manager
    # Even if an experimental device controller fails during its startup,
    # attempt to stop any earlier-started controllers. Leave the original
    # installation error visible and never register partial service routes.
    try:
        from .device_hierarchy import async_register_hierarchy
        async_register_hierarchy(hass, entry)
        await manager.async_start()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await manager.async_stop()
        raise
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager
    entry.async_on_unload(async_watch_room_hubs(hass, entry))

    if not hass.services.has_service(DOMAIN, "announce"):
        async def async_announce_action(call: ServiceCall) -> ServiceResponse:
            managers = list(hass.data.get(DOMAIN, {}).values())
            if not managers:
                return {"submitted": 0, "reason": "Integration is not loaded"}
            requested=call.data.get("areas")
            if requested is not None and not isinstance(requested,(list,tuple)):
                return {"submitted":0,"reason":"invalid_room_filter"}
            # An announcement belongs to an actual pending recommendation,
            # not an arbitrary config entry. The Hub alone routes speakers,
            # visual outputs, occupancy and fallback after submission.
            claims={}
            for manager in managers:
                plan=getattr(manager,"plan",None)
                for recommendation in (
                    *getattr(plan,"recommendations",()),
                    *getattr(plan,"climate_recommendations",()),
                ):
                    area=getattr(recommendation,"area_id",None)
                    if not isinstance(area,str):
                        continue
                    claims.setdefault(area,[]).append(manager)
            if requested is None:
                selected=sorted(claims)
            else:
                selected=list(dict.fromkeys(requested))
            conflicts=[area for area in selected
                       if len(set(claims.get(area,())))>1]
            if conflicts:
                # Fail the WHOLE request before any output is routed, rather
                # than partly announcing and then discovering ambiguity.
                return {"submitted":0,"reason":"ambiguous_room_across_config_entries",
                        "areas":conflicts}
            grouped={}
            for area in selected:
                owners=claims.get(area,())
                if len(owners)==1:
                    grouped.setdefault(owners[0],[]).append(area)
            if not grouped:
                return {"submitted":0,"reason":"No actionable window recommendations"}
            total=0
            errors=[]
            for manager,area_ids in grouped.items():
                outcome=await manager.async_announce(
                    language=call.data.get("language"),
                    channels=call.data.get("channels","both"),
                    areas=area_ids,
                )
                if isinstance(outcome,dict):
                    total+=int(outcome.get("submitted",0))
                    errors.extend(outcome.get("errors",[]) or [])
            result={"submitted":total}
            if errors:
                result["errors"]=errors
            return result if call.return_response else None

        hass.services.async_register(
            DOMAIN, "announce", async_announce_action,
            schema=SERVICE_SCHEMA, supports_response=SupportsResponse.OPTIONAL,
        )
    if not hass.services.has_service(DOMAIN, "pid_control"):
        async def async_pid_action(call: ServiceCall) -> ServiceResponse:
            manager,why=_exact_room_manager(
                hass,call.data["area"],"pid_rooms",
            )
            if manager is None:
                return {"accepted":False,"reason":why}
            # Exact area owner: never choose the first manager implicitly.
            result = await manager.async_pid_control(
                area=call.data["area"], action=call.data["action"],
            )
            return result if call.return_response else None

        hass.services.async_register(
            DOMAIN, "pid_control", async_pid_action,
            schema=PID_CONTROL_SCHEMA, supports_response=SupportsResponse.OPTIONAL,
        )
    if not hass.services.has_service(DOMAIN, "climate_control"):
        async def async_native_action(call: ServiceCall) -> ServiceResponse:
            manager,why=_exact_room_manager(
                hass,call.data["area"],"climate_rooms",
            )
            if manager is None:
                return {"accepted":False,"reason":why}
            result=await manager.async_climate_control(
                call.data["area"],call.data["action"]
            )
            return result if call.return_response else None
        hass.services.async_register(
            DOMAIN, "climate_control", async_native_action,
            schema=NATIVE_CLIMATE_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )
    if not hass.services.has_service(DOMAIN, "climate_diagnostics"):
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

        hass.services.async_register(
            DOMAIN, "climate_diagnostics", async_diagnostics,
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
        if hass.services.has_service(DOMAIN, "announce"):
            hass.services.async_remove(DOMAIN, "announce")
        if hass.services.has_service(DOMAIN, "pid_control"):
            hass.services.async_remove(DOMAIN, "pid_control")
        if hass.services.has_service(DOMAIN, "climate_control"):
            hass.services.async_remove(DOMAIN, "climate_control")
        if hass.services.has_service(DOMAIN, "climate_diagnostics"):
            hass.services.async_remove(DOMAIN, "climate_diagnostics")
    return True
