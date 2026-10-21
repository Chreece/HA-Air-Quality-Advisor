"""Guarded writes from Home Environment Manager device configuration entities.

Only soft supervisor settings may change here. Physical equipment selections,
automated relay permissions, safety attestation and controller enablement stay
in the config flow. Every write is validated and stored through HA's config
entry API; no direct hardware service call is made by these entities.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
import math
from typing import Any

from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_CLIMATE_ROOMS, CONF_PID_ROOMS, CONF_THRESHOLDS,
    CONF_AUTO_NOTIFY, CONF_AUTO_TTS, CONF_TTS_ENGINE,
    CONF_MEDIA_PLAYERS, CONF_HUB, CONF_AI_REWRITE, CONF_REPEAT_MINUTES,
    DEFAULT_THRESHOLDS, MAX_REPEAT_MINUTES,
)
from .pid_math import DEFAULT_PID, validate_settings
from .climate_strategy import profiles

# PID gain units are percent-per-degree, per degree-minute and
# percent-minute-per-degree. No physical HVAC self-tuning is implied.
PID_GAIN_FIELDS = ("kp", "ki", "kd")
PID_NUMBERS = {
    "target_c": (5.0, 36.0, 0.1, "°C"),
    "kp": (0.01, 100.0, 0.01, "%/°C"),
    "ki": (0.0, 10.0, 0.01, "%/(°C·min)"),
    "kd": (0.0, 50.0, 0.1, "%·min/°C"),
    "offset_c": (0.25, 5.0, 0.05, "°C"),
    "min_setpoint_c": (5.0, 35.0, 0.1, "°C"),
    "max_setpoint_c": (6.0, 40.0, 0.1, "°C"),
    "sample_seconds": (120.0, 3600.0, 60.0, "s"),
    "max_change_c": (0.1, 2.0, 0.05, "°C"),
    "min_change_c": (0.05, 1.0, 0.05, "°C"),
}
# These are supervisory profile bands (home/away/sleep) and not copies of
# a thermostat's native currently active setpoint.
PROFILE_NUMBERS = {
    f"{profile}_{mode}": (5.0 if mode == "heat" else 6.0,
                           35.0 if mode == "heat" else 40.0, 0.5, "°C")
    for profile in ("home", "unoccupied", "away", "sleep")
    for mode in ("heat", "cool")
}
THRESHOLD_NUMBERS = {
    key: (
        -40.0 if key in ("min_outdoor_temp", "max_outdoor_temp") else
        1.0 if key == "max_age_minutes" else 0.0,
        100000.0 if key == "max_age_minutes" else
        100.0 if key in ("indoor_mold", "indoor_humidity", "max_outdoor_humidity") else
        10000.0,
        1.0,
        "°C" if key in ("min_outdoor_temp", "max_outdoor_temp") else
        "%" if key in ("indoor_mold", "indoor_humidity", "max_outdoor_humidity") else
        "min" if key == "max_age_minutes" else
        "km/h" if key == "max_wind_kmh" else
        "ppm" if key.endswith("_co2") else
        "ppb" if key.endswith("_voc_parts") else
        "µg/m³" if key.endswith(("_pm25", "_pm10", "_voc", "_no2", "_o3", "_so2"))
        else None,
    )
    for key in DEFAULT_THRESHOLDS
}


def _finite(value: Any, bounds: tuple) -> float:
    if isinstance(value, bool):
        raise HomeAssistantError("Boolean values are not numeric controller settings")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise HomeAssistantError("Invalid numeric controller setting") from error
    low, high = bounds[:2]
    if not math.isfinite(number) or not low <= number <= high:
        raise HomeAssistantError(f"Setting outside supported range {low}–{high}")
    return number


def pid_settings(settings: dict, area: str) -> dict | None:
    rooms = settings.get(CONF_PID_ROOMS, {})
    raw = rooms.get(area) if isinstance(rooms, dict) else None
    return {**DEFAULT_PID, **raw} if isinstance(raw, dict) and raw.get("enabled") is True else None


def tuning_source(config: dict) -> str:
    choice = config.get("tuning_source")
    if choice in ("defaults", "manual"):
        return choice
    return ("manual" if any(config.get(k, DEFAULT_PID[k]) != DEFAULT_PID[k]
                            for k in PID_GAIN_FIELDS) else "defaults")


def climate_settings(settings: dict, area: str) -> dict | None:
    rooms = settings.get(CONF_CLIMATE_ROOMS, {})
    room = rooms.get(area) if isinstance(rooms, dict) else None
    return room if isinstance(room, dict) and room.get("enabled") is True else None


async def update_device_setting(manager: Any, kind: str, key: str,
                                value: Any, *, area: str | None = None) -> None:
    """One atomic, validated options update; never broaden device ownership."""
    if kind not in ("pid", "profile", "climate_profile", "global_threshold",
                    "global_setting", "pid_gain_source"):
        raise HomeAssistantError("Unsupported settings editor")
    if kind in ("pid", "profile", "climate_profile", "pid_gain_source") and not area:
        raise HomeAssistantError("A configured Home Assistant area is required")

    lock = getattr(manager, "_device_settings_write_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        manager._device_settings_write_lock = lock

    async with lock:
        current = deepcopy(manager.settings)
        options = deepcopy(manager.entry.options)
        if kind in ("pid", "pid_gain_source"):
            rooms = current.get(CONF_PID_ROOMS, {})
            rooms = deepcopy(rooms) if isinstance(rooms, dict) else {}
            original = rooms.get(area)
            if not isinstance(original, dict) or original.get("enabled") is not True:
                raise HomeAssistantError("PID must first be safely configured and enabled")
            draft = {**DEFAULT_PID, **original}
            if kind == "pid_gain_source":
                if value not in ("manual", "defaults"):
                    raise HomeAssistantError("Unknown PID gain source")
                draft["tuning_source"] = value
                if value == "defaults":
                    for field in PID_GAIN_FIELDS:
                        draft[field] = DEFAULT_PID[field]
            else:
                if key not in PID_NUMBERS:
                    raise HomeAssistantError("Unknown PID setting")
                draft[key] = _finite(value, PID_NUMBERS[key])
                if key in PID_GAIN_FIELDS:
                    draft["tuning_source"] = "manual"
            valid, why = validate_settings(draft)
            if not valid:
                raise HomeAssistantError(f"Unsafe PID settings: {why}")
            rooms[area] = {**original, **draft}
            options[CONF_PID_ROOMS] = rooms
        elif kind in ("profile", "climate_profile"):
            rooms = current.get(CONF_CLIMATE_ROOMS, {})
            rooms = deepcopy(rooms) if isinstance(rooms, dict) else {}
            original = rooms.get(area)
            if not isinstance(original, dict) or original.get("enabled") is not True:
                raise HomeAssistantError("Room climate management is not enabled")
            draft = dict(original)
            if kind == "profile":
                if key != "manual_profile" or value not in (
                    "auto", "home", "unoccupied", "away", "sleep"
                ):
                    raise HomeAssistantError("Invalid room occupancy profile")
                draft[key] = value
            else:
                if key not in PROFILE_NUMBERS:
                    raise HomeAssistantError("Unsupported comfort profile target")
                group, mode = key.rsplit("_", 1)
                old = draft.get("profiles", {})
                old = deepcopy(old) if isinstance(old, dict) else {}
                default_profiles, err = profiles(draft)
                if err:
                    raise HomeAssistantError(f"Invalid existing profile configuration: {err}")
                band = {
                    "heat_c": default_profiles[group].heat_c,
                    "cool_c": default_profiles[group].cool_c,
                    **(old.get(group, {}) if isinstance(old.get(group), dict) else {}),
                }
                band[f"{mode}_c"] = _finite(value, PROFILE_NUMBERS[key])
                old[group] = band
                draft["profiles"] = old
                _, reason = profiles(draft)
                if reason:
                    raise HomeAssistantError(f"Invalid comfort band: {reason}")
            rooms[area] = draft
            options[CONF_CLIMATE_ROOMS] = rooms
        elif kind == "global_threshold":
            if area is not None or key not in DEFAULT_THRESHOLDS:
                raise HomeAssistantError("Invalid home-wide threshold")
            draft = deepcopy(current.get(CONF_THRESHOLDS, {}))
            draft = draft if isinstance(draft, dict) else {}
            draft[key] = _finite(value, THRESHOLD_NUMBERS[key])
            updated = {**DEFAULT_THRESHOLDS, **draft}
            if updated["min_outdoor_temp"] >= updated["max_outdoor_temp"]:
                raise HomeAssistantError("Minimum outdoor temperature must be below maximum")
            options[CONF_THRESHOLDS] = draft
        elif kind == "global_setting":
            if area is not None:
                raise HomeAssistantError("Home-wide settings cannot target one room")
            if key == CONF_REPEAT_MINUTES:
                number = _finite(value, (0.0, float(MAX_REPEAT_MINUTES)))
                if not number.is_integer():
                    raise HomeAssistantError("Announcement interval must be whole minutes")
                options[key] = int(number)
            elif key in (CONF_AUTO_NOTIFY, CONF_AUTO_TTS, CONF_HUB, CONF_AI_REWRITE):
                if type(value) is not bool:
                    raise HomeAssistantError("Global on/off settings require a boolean")
                if value and key == CONF_HUB and not manager.hub_available:
                    raise HomeAssistantError("Announcement Hub must be configured and running")
                proposed_hub = (value if key == CONF_HUB else current.get(CONF_HUB))
                hub_ready = bool(proposed_hub and manager.hub_available)
                direct_speech = bool(
                    current.get(CONF_TTS_ENGINE) and current.get(CONF_MEDIA_PLAYERS)
                )
                if value and key == CONF_AUTO_TTS and not (
                    hub_ready or direct_speech
                ):
                    raise HomeAssistantError(
                        "Configure a TTS engine/player or Announcement Hub before enabling speech"
                    )
                if key == CONF_HUB and not value and (
                    current.get(CONF_AUTO_TTS) and not direct_speech
                ):
                    raise HomeAssistantError(
                        "Configure direct speech before disconnecting the only TTS route"
                    )
                if value and key == CONF_AI_REWRITE and not hub_ready and not (
                    manager.hass.services.has_service("conversation", "process")
                ):
                    raise HomeAssistantError(
                        "An available conversation agent or Announcement Hub is required"
                    )
                options[key] = value
            elif key == "language":
                from .const import LANGUAGES
                if value not in LANGUAGES:
                    raise HomeAssistantError("Unsupported output language")
                options[key] = value
            else:
                raise HomeAssistantError("Unsupported home setting")

        if options == manager.entry.options:
            return

        # Pending PID writes must not execute using obsolete gains after a
        # changed setpoint/tuning policy. Keep old manual-pause safety latches.
        if kind in ("pid", "pid_gain_source"):
            prepare = getattr(manager.pid, "async_prepare_reconfigure", None)
            if prepare is not None:
                try:
                    await prepare(area)
                except RuntimeError as error:
                    raise HomeAssistantError(str(error)) from error

        manager.hass.config_entries.async_update_entry(manager.entry, options=options)
        # HA may replace the manager during a reload. Refresh only the current
        # live instance and force entity listeners to see the new settings.
        if getattr(manager, "_active", False):
            manager._recalculate(initial=True)
