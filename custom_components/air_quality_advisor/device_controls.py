"""Guarded writes from Home Environment Manager device configuration entities.

Shared scientific/policy preferences are edited here. Device-native control
permissions live on each managed controller, never in a hidden setup form. Every write is validated and stored through HA's config
entry API; no direct hardware service call is made by these entities.
"""
from __future__ import annotations

import asyncio
from .config_data import mutable_copy as deepcopy
import math
from typing import Any

from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_AREAS, CONF_CLIMATE_ROOMS, CONF_PID_ROOMS, CONF_THRESHOLDS,
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


# A small, finite set of actual scientific/policy inputs. Selectors for
# sources and hardware authorizations remain in the config flow.
GLOBAL_ENV_NUMBERS = {
    "pollen_high_from": (0.0, 100.0, 0.1, None, 3.0),
    "pollen_max_scale": (1.0, 100.0, 0.1, None, 5.0),
}
GLOBAL_OCCUPANCY_NUMBERS = {
    "source_stale_minutes": (10.0, 1440.0, 1.0, "min", 240.0),
}
AREA_ENV_NUMBERS = {
    "room_volume_m3": (1.0, 30000.0, 1.0, "m³", None),
    "particle_cadr_m3h": (0.1, 100000.0, 0.1, "m³/h", None),
    "co2_target_ppm": (400.0, 3000.0, 1.0, "ppm", 1000.0),
    "radon_reference_bq_m3": (25.0, 1000.0, 1.0, "Bq/m³", 100.0),
    "air_speed_m_s": (0.01, 0.99, 0.01, "m/s", None),
    "met": (0.81, 3.99, 0.01, "met", None),
    "clo": (0.01, 1.99, 0.01, "clo", None),
}
CLIMATE_OPERATING_NUMBERS = {
    "unoccupied_delay_minutes": (0.0, 240.0, 1.0, "min", 10.0),
    "occupancy_stale_minutes": (10.0, 1440.0, 1.0, "min", 240.0),
    "comfort_adjustment_max_c": (0.0, 2.5, 0.1, "°C", 1.5),
    "humidity_low_rh": (20.0, 70.0, 0.5, "%", 40.0),
    "humidity_high_rh": (30.0, 80.0, 0.5, "%", 60.0),
    "humidity_hysteresis_rh": (0.5, 10.0, 0.5, "%", 3.0),
    "cooling_dry_deferral_rh_points": (0.0, 20.0, 0.5, "%", 10.0),
    "pm25_action_ug_m3": (5.0, 250.0, 1.0, "µg/m³", 35.0),
    "extraction_speed_percent": (30.0, 100.0, 1.0, "%", 65.0),
    "purifier_speed_percent": (30.0, 100.0, 1.0, "%", 65.0),
}
DIRECT_CONTROLLER_NUMBERS = {
    "kp": (0.01, 100.0, 0.1, None, 18.0),
    "ki": (0.0, 10.0, 0.01, None, 0.12),
    "kd": (0.0, 50.0, 0.1, None, 0.0),
    "sample_seconds": (120.0, 3600.0, 60.0, "s", 300.0),
    "max_demand_change": (1.0, 50.0, 1.0, "%", 10.0),
    "min_demand_change": (0.1, 20.0, 0.1, "%", 2.0),
}
DEVICE_TARGET_NUMBERS = {
    **{
        f"{profile}_{mode}_c": (
            5.0 if mode == "heat" else 6.0,
            35.0 if mode == "heat" else 40.0, 0.5, "°C",
            {"home": (20, 26), "unoccupied": (18, 28),
             "away": (16, 30), "sleep": (18, 26)}[profile][
                0 if mode == "heat" else 1]
        )
        for profile in ("home", "unoccupied", "away", "sleep")
        for mode in ("heat", "cool")
    },
    "humidity_target": (20.0, 80.0, 1.0, "%", 50.0),
    "sleep_humidity_target": (20.0, 80.0, 1.0, "%", 50.0),
    "fan_speed_percent": (10.0, 100.0, 1.0, "%", 60.0),
}
CLIMATE_POLICY_OPTIONS = {
    "unknown_occupancy": ("occupied", "hold"),
    "away_policy": ("any_home", "all_home"),
    "target_source": ("temperature", "pmv"),
}
DEVICE_POLICY_OPTIONS = {
    "presence_requirement": ("always", "room", "home"),
    "sleep_behavior": ("normal", "pause", "sleep_targets"),
}
GLOBAL_POLICY_OPTIONS = {"home_policy": ("any_home", "all_home")}
CLIMATE_OPERATING_FLAGS = ("sleep_active", "sleep_schedule_enabled",
                           "window_efficiency_notify")
AREA_ENV_FLAGS = ("sleep_room", "enable_pmv")
GLOBAL_ENV_FLAGS = ("pollen_avoid_ventilation",)


AQI_SCALES = ("not_configured", "us_epa", "eea_category", "custom")


def configured_aqi_entities(manager: Any) -> tuple[str, ...]:
    """Only selected outdoor AQI sources, not arbitrary sensor entities."""
    configured = manager.settings.get("outdoor_sensors", [])
    if not isinstance(configured, list):
        return ()
    result = []
    for entity in configured:
        state = manager.hass.states.get(entity) if isinstance(entity, str) else None
        if not isinstance(entity, str) or not entity.startswith("sensor.") or state is None:
            continue
        if (str(state.attributes.get("device_class", "")).casefold() == "aqi"
                or entity.endswith(("_aqi", "_air_quality_index"))):
            result.append(entity)
    return tuple(dict.fromkeys(result))


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


def science_source_options(manager: Any, area: str, key: str) -> tuple[str, ...]:
    """Scientific source pinning only within the user's selected room inputs."""
    from .room_sources import selected, choices
    group = "temperature" if key == "radiant_temperature_entity" else "air_quality"
    ids = selected(manager.settings, area, group)
    if ids is None:
        ids = tuple(item["value"] for item in choices(manager.hass, area)[group])
    if key == "air_speed_entity":
        ids = tuple(e for e in ids if (state := manager.hass.states.get(e)) is not None
                    and str(state.attributes.get("unit_of_measurement", "")).lower() in ("m/s", "mps")
                    and e.endswith("_air_speed"))
    return ("none", *ids)


async def update_device_setting(manager: Any, kind: str, key: str,
                                value: Any, *, area: str | None = None,
                                entity_id: str | None = None) -> None:
    """One atomic, validated options update; never broaden device ownership."""
    if kind not in (
        "pid", "profile", "climate_profile", "global_threshold", "global_setting",
        "pid_gain_source", "global_environment", "global_occupancy",
        "area_environment", "climate_operating", "global_policy", "climate_policy",
        "device_target", "device_policy", "aqi_scale", "aqi_limit",
        "climate_schedule", "direct_tuning", "area_science",
    ):
        raise HomeAssistantError("Unsupported settings editor")
    if kind in (
        "pid", "profile", "climate_profile", "pid_gain_source",
        "area_environment", "climate_operating", "climate_policy",
        "device_target", "device_policy", "climate_schedule", "direct_tuning", "area_science",
    ) and not area:
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
        elif kind in ("global_environment", "global_occupancy",
                          "area_environment", "climate_operating"):
            from .const import CONF_ENVIRONMENT_GLOBAL, CONF_ENVIRONMENT_ROOMS, CONF_OCCUPANCY_GLOBAL
            section, fields = {
                "global_environment": (CONF_ENVIRONMENT_GLOBAL, GLOBAL_ENV_NUMBERS),
                "global_occupancy": (CONF_OCCUPANCY_GLOBAL, GLOBAL_OCCUPANCY_NUMBERS),
                "area_environment": (CONF_ENVIRONMENT_ROOMS, AREA_ENV_NUMBERS),
                "climate_operating": (CONF_CLIMATE_ROOMS, CLIMATE_OPERATING_NUMBERS),
            }[kind]
            flags = (
                GLOBAL_ENV_FLAGS if kind == "global_environment" else
                AREA_ENV_FLAGS if kind == "area_environment" else
                CLIMATE_OPERATING_FLAGS if kind == "climate_operating" else ()
            )
            if key not in fields and key not in flags:
                raise HomeAssistantError("Unsupported environmental/policy setting")
            if kind.startswith("global") and area is not None:
                raise HomeAssistantError("Global preferences do not target one area")
            data = current.get(section, {})
            data = deepcopy(data) if isinstance(data, dict) else {}
            if area is None:
                room = data
            else:
                if kind == "area_environment" and area not in current.get(CONF_AREAS, []):
                    raise HomeAssistantError("Select the room for environmental monitoring first")
                if kind == "climate_operating" and not (
                    isinstance(data.get(area), dict) and data[area].get("enabled") is True
                ):
                    raise HomeAssistantError("This room's climate manager is not enabled")
                room = deepcopy(data.get(area, {}))
            if key in flags:
                if type(value) is not bool:
                    raise HomeAssistantError("Environmental toggle must be boolean")
                room[key] = value
            else:
                room[key] = _finite(value, fields[key])
            # Enabling a calculation is a preference, not evidence that its
            # scientific inputs exist. room_science reports insufficient inputs
            # until radiant temperature, air speed, MET and CLO are supplied.
            if kind == "global_environment":
                if not room.get("pollen_high_from", 3) <= room.get("pollen_max_scale", 5):
                    raise HomeAssistantError("Pollen high threshold exceeds its declared scale")
            if kind == "climate_operating":
                low = float(room.get("humidity_low_rh", 40))
                high = float(room.get("humidity_high_rh", 60))
                hysteresis = float(room.get("humidity_hysteresis_rh", 3))
                if high-low < 2*hysteresis:
                    raise HomeAssistantError("Humidity deadband must exceed twice hysteresis")
            if area is not None:
                data[area] = room
            options[section] = data

        elif kind == "area_science":
            if area not in current.get(CONF_AREAS, []) or key not in ("radiant_temperature_entity", "air_speed_entity"):
                raise HomeAssistantError("Unknown room science input")
            if value not in science_source_options(manager, area, key):
                raise HomeAssistantError("Select a sensor from this room's configured inputs")
            rooms = deepcopy(current.get("environment_rooms", {}))
            room = rooms.setdefault(area, {})
            room[key] = None if value == "none" else value
            options["environment_rooms"] = rooms

        elif kind in ("aqi_scale", "aqi_limit"):
            from .const import CONF_ENVIRONMENT_GLOBAL
            if area is not None or entity_id not in configured_aqi_entities(manager):
                raise HomeAssistantError("The AQI source must be selected in outdoor data")
            current_global = current.get(CONF_ENVIRONMENT_GLOBAL, {})
            current_global = deepcopy(current_global) if isinstance(current_global, dict) else {}
            scales = deepcopy(current_global.get("aqi_scales", {}))
            scales = scales if isinstance(scales, dict) else {}
            source_cfg = scales.get(entity_id, {})
            source_cfg = dict(source_cfg) if isinstance(source_cfg, dict) else {}
            if kind == "aqi_scale":
                if key != "scale" or value not in AQI_SCALES:
                    raise HomeAssistantError("Invalid AQI classification")
                if value == "not_configured":
                    scales.pop(entity_id, None)
                else:
                    source_cfg["scale"] = value
                    scales[entity_id] = source_cfg
            else:
                if key != "custom_limit" or source_cfg.get("scale") != "custom":
                    raise HomeAssistantError("Select custom AQI scale first")
                source_cfg["custom_limit"] = _finite(value, (0.0, 10000.0))
                scales[entity_id] = source_cfg
            current_global["aqi_scales"] = scales
            options[CONF_ENVIRONMENT_GLOBAL] = current_global

        elif kind == "climate_schedule":
            from datetime import time as ClockTime
            from .climate_schedule import local_interval_active
            if key not in ("sleep_start", "sleep_end"):
                raise HomeAssistantError("Invalid sleep schedule setting")
            if isinstance(value, ClockTime):
                v = value.strftime("%H:%M")
            elif isinstance(value, str):
                try:
                    v = ClockTime.fromisoformat(value).strftime("%H:%M")
                except ValueError as error:
                    raise HomeAssistantError("Invalid clock time") from error
            else:
                raise HomeAssistantError("Invalid clock time")
            room_configs = deepcopy(current.get(CONF_CLIMATE_ROOMS, {}))
            old_cfg = room_configs.get(area) if isinstance(room_configs, dict) else None
            if not isinstance(old_cfg, dict) or old_cfg.get("enabled") is not True:
                raise HomeAssistantError("Room climate management is not configured")
            draft = dict(old_cfg)
            draft[key] = v
            if draft.get("sleep_schedule_enabled") is True:
                if local_interval_active(
                    1704067200, "UTC", draft.get("sleep_start", "22:00"),
                    draft.get("sleep_end", "07:00")
                )[0] is None:
                    raise HomeAssistantError("Invalid sleep interval")
            room_configs[area] = draft
            options[CONF_CLIMATE_ROOMS] = room_configs

        elif kind in ("global_policy", "climate_policy", "device_policy"):
            from .const import CONF_OCCUPANCY_GLOBAL
            if kind == "global_policy":
                if area is not None or key not in GLOBAL_POLICY_OPTIONS or value not in GLOBAL_POLICY_OPTIONS[key]:
                    raise HomeAssistantError("Invalid home-wide occupancy policy")
                saved = deepcopy(current.get(CONF_OCCUPANCY_GLOBAL, {}))
                saved = saved if isinstance(saved, dict) else {}
                saved[key] = value
                options[CONF_OCCUPANCY_GLOBAL] = saved
            else:
                rooms = deepcopy(current.get(CONF_CLIMATE_ROOMS, {}))
                original = rooms.get(area) if isinstance(rooms, dict) else None
                if not isinstance(original, dict) or original.get("enabled") is not True:
                    raise HomeAssistantError("Room climate manager is not enabled")
                if kind == "climate_policy":
                    if key not in CLIMATE_POLICY_OPTIONS or value not in CLIMATE_POLICY_OPTIONS[key]:
                        raise HomeAssistantError("Unsupported room policy")
                    new_room = dict(original)
                    new_room[key] = value
                else:
                    if key not in DEVICE_POLICY_OPTIONS or value not in DEVICE_POLICY_OPTIONS[key]:
                        raise HomeAssistantError("Invalid device policy")
                    if not isinstance(entity_id, str) or entity_id not in original.get("selected_devices", []):
                        raise HomeAssistantError("The device must remain selected in this room")
                    device_profiles = deepcopy(original.get("device_settings", {}))
                    existing = device_profiles.get(entity_id)
                    if not isinstance(existing, dict):
                        raise HomeAssistantError("This device has not been configured")
                    if (key == "presence_requirement" and value == "always" and
                            existing.get("absence_action") == "off"):
                        raise HomeAssistantError("Absence-off requires actual home or room presence")
                    device_profiles[entity_id] = {**existing, key: value}
                    new_room = {**original, "device_settings": device_profiles}
                rooms[area] = new_room
                options[CONF_CLIMATE_ROOMS] = rooms

        elif kind == "direct_tuning":
            if key not in DIRECT_CONTROLLER_NUMBERS:
                raise HomeAssistantError("Invalid direct control tuning")
            all_rooms = deepcopy(current.get(CONF_CLIMATE_ROOMS, {}))
            room = all_rooms.get(area) if isinstance(all_rooms, dict) else None
            if (not isinstance(room, dict) or room.get("enabled") is not True
                    or room.get("controller") not in ("pwm", "proportional")):
                raise HomeAssistantError("The room has no commissioned modulating controller")
            if (key in ("max_demand_change", "min_demand_change")
                    and room.get("controller") != "proportional"):
                raise HomeAssistantError("Output change limits require proportional control")
            task = getattr(manager.direct_climate, "_tasks", {}).get(area)
            if task is not None and not task.done():
                raise HomeAssistantError("A direct controller write is in progress")
            draft = dict(room)
            draft[key] = _finite(value, DIRECT_CONTROLLER_NUMBERS[key])
            if draft.get("controller") == "proportional":
                if float(draft.get("min_demand_change", 2)) > float(
                    draft.get("max_demand_change", 10)
                ):
                    raise HomeAssistantError("Minimum output change exceeds maximum")
            all_rooms[area] = draft
            options[CONF_CLIMATE_ROOMS] = all_rooms

        elif kind == "device_target":
            if key not in DEVICE_TARGET_NUMBERS or not isinstance(entity_id, str):
                raise HomeAssistantError("Invalid device target")
            rooms = deepcopy(current.get(CONF_CLIMATE_ROOMS, {}))
            cfg = rooms.get(area) if isinstance(rooms, dict) else None
            if not isinstance(cfg, dict) or cfg.get("enabled") is not True:
                raise HomeAssistantError("Room must first be configured")
            if entity_id not in cfg.get("selected_devices", []):
                raise HomeAssistantError("This device has been deselected")
            device_profiles = deepcopy(cfg.get("device_settings", {}))
            device_cfg = device_profiles.get(entity_id)
            if not isinstance(device_cfg, dict) or device_cfg.get("auto_control") is not True:
                raise HomeAssistantError("Device auto-control must first be explicitly commissioned")
            domain = entity_id.partition(".")[0]
            if ((domain == "climate" and not key.endswith(("_heat_c", "_cool_c"))) or
                    (domain == "humidifier" and key not in ("humidity_target", "sleep_humidity_target")) or
                    (domain == "fan" and key != "fan_speed_percent") or
                    domain not in ("climate", "humidifier", "fan")):
                raise HomeAssistantError("Device does not support this policy target")
            n = _finite(value, DEVICE_TARGET_NUMBERS[key])
            device_cfg[key] = n
            if domain == "climate":
                for profile in ("home", "unoccupied", "away", "sleep"):
                    heat = float(device_cfg.get(f"{profile}_heat_c", DEVICE_TARGET_NUMBERS[f"{profile}_heat_c"][4]))
                    cool = float(device_cfg.get(f"{profile}_cool_c", DEVICE_TARGET_NUMBERS[f"{profile}_cool_c"][4]))
                    if cool-heat < 1:
                        raise HomeAssistantError("Heat/cool policy targets require at least a 1°C deadband")
            elif domain == "fan":
                purpose = device_cfg.get("fan_purpose")
                role = ("extraction_fan_entity" if purpose == "extraction" else "purifier_fan_entity")
                if cfg.get(role) != entity_id:
                    raise HomeAssistantError("Fan no longer occupies this commissioned role")
                cfg["extraction_speed_percent" if purpose == "extraction"
                    else "purifier_speed_percent"] = n
            elif domain == "humidifier":
                state = manager.hass.states.get(entity_id)
                attrs = state.attributes if state is not None else {}
                if device_cfg.get("method") == "setpoint":
                    low = attrs.get("min_humidity")
                    high = attrs.get("max_humidity")
                    if low is None or high is None:
                        raise HomeAssistantError("Native humidity limits are unknown")
                    if not float(low) <= n <= float(high):
                        raise HomeAssistantError("Outside native humidifier setpoint limits")
            device_profiles[entity_id] = device_cfg
            cfg["device_settings"] = device_profiles
            rooms[area] = cfg
            options[CONF_CLIMATE_ROOMS] = rooms

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
