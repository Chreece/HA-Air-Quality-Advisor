"""Capability-driven managed equipment model; no services or registry mutations.

The logical climate entity represents a Manager controller, not a second
physical appliance. Unsupported HVAC modes and invented measurements are never
advertised. All internal temperatures are Celsius; native endpoints are converted
at the write boundary. Existing room controllers remain selected until the user
explicitly chooses a new per-device owner.
"""
from __future__ import annotations

from .config_data import mutable_copy as deepcopy
from dataclasses import dataclass
import math
import hashlib
from typing import Any

from .const import DOMAIN
from .device_hierarchy import ManagedDevice, configured_sources
from .pid_math import finite, target_from_unit

SETTINGS = "equipment_controllers"
PRESETS = ("none", "home", "comfort", "away", "sleep", "eco")
CONTROL_MODES = ("existing", "automatic", "manual", "off", "pid")
# Native ClimateEntityFeature values, used without importing HA platforms here.
TEMP, RANGE, HUMIDITY, FAN, PRESET, SWING, SWING_H = 1, 2, 4, 8, 16, 32, 512
HVAC_MODES = frozenset(("off", "heat", "cool", "heat_cool", "auto", "dry", "fan_only"))
NUMBER_FIELDS = {
    "kp": (0.001, 100.0, 0.001, None, 10.0),
    "ki": (0.0, 10.0, 0.001, None, 0.1),
    "kd": (0.0, 50.0, 0.01, None, 0.0),
    "sample_seconds": (120.0, 3600.0, 30.0, "s", 300.0),
    "cycle_seconds": (600.0, 86400.0, 60.0, "s", 3600.0),
    "quiet_percentage": (1.0, 100.0, 1.0, "%", 30.0),
    "min_on_seconds": (120.0, 7200.0, 60.0, "s", 600.0),
    "min_off_seconds": (120.0, 14400.0, 60.0, "s", 600.0),
    "max_on_seconds": (900.0, 86400.0, 60.0, "s", 7200.0),
}
QUIET_FLAGS = ("quiet_sleep", "quiet_occupied")
from .pid_calibration import METHODS as PID_CALIBRATION_METHODS, MODEL_FIELDS as PID_MODEL_FIELDS
from .pid_fan_capacity import (
    CAPACITY_FIELDS as PID_FAN_CAPACITY_FIELDS,
    CAPACITY_METHODS as PID_FAN_CAPACITY_METHODS,
    CALIBRATION_DIRECTIONS as PID_FAN_DIRECTIONS,
)
POWER_FIELDS = ("min_on_seconds", "min_off_seconds", "max_on_seconds")
LIMIT_FIELDS = (
    "temperature_min_limit", "temperature_max_limit",
    "humidity_min_limit", "humidity_max_limit",
    "fan_min_percentage", "fan_max_percentage",
)
DEVICE_SELECTS = {"presence_requirement": ("always", "occupied", "absent"),
                  "sleep_behavior": ("normal", "pause", "sleep_targets"),
                  "fan_purpose": ("auto", "extraction", "filtration")}
ROOM_LIMITS_KEY = "equipment_limits"
DEFAULTS = {"control_mode": "existing", "preset": "none", "requested_mode": None,
            "quiet_sleep": False, "quiet_occupied": False,
            "quiet_fan_mode": None, "profile_targets": {}, "profile_fans": {},
            "pid_calibration_method": "manual", "pid_last_calibration": None,
            "pid_fan_capacity_mode": "legacy",
            "pid_fan_capacity_for_mode": "choose",
            "pid_fan_capacity_models": {},
            **{key: item[4] for key, item in NUMBER_FIELDS.items()},
            **{key: 0.0 for key in PID_MODEL_FIELDS},
            **{key: 0.0 for key in PID_FAN_CAPACITY_FIELDS}}


@dataclass(frozen=True, slots=True)
class Capabilities:
    """One controller can combine native HVAC and a same-device fan endpoint."""

    primary: str
    domain: str
    modes: tuple[str, ...]
    temperature: bool = False
    temperature_range: bool = False
    humidity: bool = False
    fan_entity: str | None = None
    fan_modes: tuple[str, ...] = ()
    fan_percentage: bool = False
    swing_modes: tuple[str, ...] = ()
    swing_horizontal_modes: tuple[str, ...] = ()
    humidifying: bool = False
    min_temp: float = 5.0
    max_temp: float = 35.0
    temp_step: float = 0.5
    min_humidity: float = 20.0
    max_humidity: float = 80.0


def room_config(manager: Any, spec: ManagedDevice) -> dict:
    rooms = manager.settings.get("climate_rooms", {})
    value = rooms.get(spec.area_id, {}) if isinstance(rooms, dict) else {}
    return value if isinstance(value, dict) else {}


def device_config(manager: Any, spec: ManagedDevice, entity: str | None = None) -> dict:
    room = room_config(manager, spec)
    profiles = room.get("device_settings", {})
    profile = profiles.get(entity, {}) if isinstance(profiles, dict) else {}
    return profile if isinstance(profile, dict) else {}


def settings(manager: Any, spec: ManagedDevice) -> dict:
    profiles = manager.settings.get(SETTINGS, {})
    raw = profiles.get(spec.identifier, {}) if isinstance(profiles, dict) else {}
    raw = raw if isinstance(raw, dict) else {}
    result = {**DEFAULTS, **raw}
    # Keep previous commissioning values when these controls first appear.
    primary = next((e for e in spec.source_entities if not e.startswith("fan.")), spec.source_entities[0])
    dev = device_config(manager, spec, primary)
    for key, fallback in (("presence_requirement", "always"), ("sleep_behavior", "normal"),
                          ("fan_purpose", "auto"), ("sensor_verified", False)):
        result.setdefault(key, dev.get(key, fallback))
    # Beta17 exposes one strict room-state selector per managed controller.
    # Old "room" means occupied; old "home" is narrowed to occupied rather
    # than broadening an existing installation's physical-control window.
    if result.get("presence_requirement") in ("room", "home"):
        result["presence_requirement"] = "occupied"
    elif result.get("presence_requirement") not in DEVICE_SELECTS["presence_requirement"]:
        result["presence_requirement"] = "always"
    for key, legacy in zip(POWER_FIELDS, ("min_on_s", "min_off_s", "max_on_s")):
        if key not in raw and legacy in dev:
            result[key] = dev[legacy]
    if "kp" not in raw and all(e.startswith("fan.") for e in spec.source_entities):
        result["kp"], result["ki"] = 0.05, 0.001
    return result


@dataclass(frozen=True, slots=True)
class ManagedEndpoint(ManagedDevice):
    """Independent native channels share ONE physical controller child device."""
    physical_identifier: str


def device_identifier(spec: ManagedDevice) -> str:
    return getattr(spec, "physical_identifier", spec.identifier)


def specs(manager: Any) -> tuple[ManagedDevice, ...]:
    result = []
    for item in getattr(manager, "_device_hierarchy", {}).get("controllers", {}).values():
        physical = item["spec"]
        primary = [e for e in physical.source_entities if not e.startswith("fan.")]
        fans = [e for e in physical.source_entities if e.startswith("fan.")]
        if len(primary) <= 1 and len(fans) <= 1:
            result.append(physical)  # A native climate plus its accessory fan.
            continue
        # Never suppress a second independently controlled endpoint merely
        # because it belongs to the same HA physical device (e.g. a dual valve).
        from homeassistant.helpers import entity_registry as er
        registry = er.async_get(manager.hass)
        for entity in physical.source_entities:
            native = registry.async_get(entity)
            identity = getattr(native, "id", None) or entity
            suffix = hashlib.sha256(identity.encode()).hexdigest()[:16]
            observed = manager.hass.states.get(entity)
            name = getattr(observed, "name", None) or entity
            result.append(ManagedEndpoint(physical.identifier + "_channel_" + suffix,
                physical.area_id, name, physical.source_device_id, (entity,), physical.identifier))
    return tuple(result)


def _strings(value: Any) -> tuple[str, ...]:
    return tuple(dict.fromkeys(v for v in value if isinstance(v, str) and v)) if isinstance(value, (tuple, list)) else ()


def features(state: Any) -> int:
    try:
        return int(state.attributes.get("supported_features", 0))
    except (TypeError, ValueError, OverflowError, AttributeError):
        return 0


def capabilities(manager: Any, spec: ManagedDevice) -> Capabilities | None:
    """Use a real configured primary endpoint; never combine opposing HVAC units.

    Multiple endpoints are grouped in one HA device, but the primary endpoint
    is stable and the complete source list remains visible in attributes. A
    dedicated fan endpoint may augment native HVAC fan control.
    """
    candidates = tuple(e for e in spec.source_entities if e in configured_sources(
        manager.settings, spec.area_id))
    if not candidates:
        return None
    primary = min(candidates, key=lambda e: (
        {"climate": 0, "humidifier": 1, "fan": 2, "switch": 3,
         "input_boolean": 3, "number": 4, "input_number": 4}.get(e.partition(".")[0], 9), e))
    state = manager.hass.states.get(primary)
    if state is None:
        return None
    domain = primary.partition(".")[0]
    attrs, supported = state.attributes, features(state)
    room = room_config(manager, spec)
    modes: tuple[str, ...] = ()
    if domain == "climate":
        modes = tuple(v for v in _strings(attrs.get("hvac_modes")) if v in HVAC_MODES)
    elif domain == "humidifier":
        if attrs.get("device_class") == "dehumidifier":
            modes = ("off", "dry")
        elif attrs.get("device_class") == "humidifier":
            modes = ("off", "auto")  # AUTO means this humidity controller's policy.
    elif domain == "fan":
        modes = ("off", "fan_only")
    elif domain in ("switch", "input_boolean", "number", "input_number"):
        role = "heat" if room.get("heat_actuator") == primary else (
            "cool" if room.get("cool_actuator") == primary else None)
        if role:
            modes = ("off", role)
    if not modes:
        return None
    fan_entity, fan_modes, percentage = None, (), False
    if domain == "climate" and supported & FAN:
        fan_entity, fan_modes = primary, _strings(attrs.get("fan_modes"))
    if not fan_modes:
        for entity in candidates:
            fan = manager.hass.states.get(entity)
            if entity.startswith("fan.") and fan is not None:
                if features(fan) & 1:
                    # percentages are real HA SET_SPEED values, not guessed labels.
                    step = finite(fan.attributes.get("percentage_step", 1), 1, 100) or 1
                    count = max(1, round(100 / step))
                    fan_modes = tuple(str(round(100 * i / count)) for i in range(1, count + 1))
                    fan_entity, percentage = entity, True
                    break
                presets = _strings(fan.attributes.get("preset_modes"))
                if features(fan) & 8 and presets:
                    fan_entity, fan_modes = entity, presets
                    break
    unit = attrs.get("temperature_unit", "°C")
    lo = target_from_unit(attrs.get("min_temp", 5 if unit == "°C" else 41), unit)
    hi = target_from_unit(attrs.get("max_temp", 35 if unit == "°C" else 95), unit)
    if lo is None or hi is None or lo >= hi:
        lo, hi = 5.0, 35.0
    temp_step = finite(attrs.get("target_temp_step", .5), .1, 10) or .5
    if unit in ("°F", "F"):
        temp_step *= 5 / 9
    direct = domain in ("switch", "input_boolean", "number", "input_number")
    return Capabilities(
        primary, domain, modes,
        temperature=direct or (domain == "climate" and (
            bool(supported & TEMP) or not (supported & RANGE) and bool(set(modes) & {"heat", "cool"}))),
        temperature_range=domain == "climate" and bool(supported & RANGE),
        humidity=domain == "humidifier" or (domain == "climate" and (
            bool(supported & HUMIDITY) or "dry" in modes and not (supported & (TEMP | RANGE)))),
        fan_entity=fan_entity, fan_modes=fan_modes, fan_percentage=percentage,
        swing_modes=_strings(attrs.get("swing_modes")) if domain == "climate" and supported & SWING else (),
        swing_horizontal_modes=_strings(attrs.get("swing_horizontal_modes")) if domain == "climate" and supported & SWING_H else (),
        humidifying=domain == "humidifier" and attrs.get("device_class") == "humidifier",
        min_temp=lo, max_temp=hi, temp_step=temp_step,
        min_humidity=finite(attrs.get("min_humidity", 20), 0, 100) or 20,
        max_humidity=finite(attrs.get("max_humidity", 80), 1, 100) or 80,
    )


def sources_available(manager: Any, spec: ManagedDevice) -> bool:
    """Pure readiness gate: no policy, target, PID or environmental calculation."""
    configured = set(configured_sources(manager.settings, spec.area_id))
    sources = [entity for entity in spec.source_entities if entity in configured]
    if not sources:
        return False
    return all((state := manager.hass.states.get(entity)) is not None
               and state.state not in ("unknown", "unavailable")
               for entity in sources)


def _fan_bounds(cap: Capabilities) -> tuple[float, float, float]:
    values = sorted({float(value) for value in cap.fan_modes
                     if cap.fan_percentage and finite(value, 0, 100) is not None})
    if not values:
        return 1.0, 100.0, 1.0
    step = min((b-a for a,b in zip(values, values[1:]) if b > a), default=1.0)
    return values[0], values[-1], step


def room_limit_bounds(manager: Any, area: str, key: str) -> tuple[float, float, float, str | None] | None:
    """Common safe editable range from the selected physical devices in one room."""
    caps = [cap for spec in specs(manager) if spec.area_id == area
            if (cap := capabilities(manager, spec)) is not None]
    if key in ("temperature_min_limit", "temperature_max_limit"):
        relevant = [cap for cap in caps if cap.temperature or cap.temperature_range]
        if not relevant:
            return None
        low = max(cap.min_temp for cap in relevant)
        high = min(cap.max_temp for cap in relevant)
        if high <= low:
            return None
        step = min(max(cap.temp_step, 0.1) for cap in relevant)
        return float(low), float(high), float(step), "°C"
    if key in ("humidity_min_limit", "humidity_max_limit"):
        relevant = [cap for cap in caps if cap.humidity]
        if not relevant:
            return None
        low = max(cap.min_humidity for cap in relevant)
        high = min(cap.max_humidity for cap in relevant)
        if high <= low:
            return None
        return float(low), float(high), 1.0, "%"
    if key in ("fan_min_percentage", "fan_max_percentage"):
        relevant = [_fan_bounds(cap) for cap in caps if cap.fan_percentage]
        if not relevant:
            return None
        low = max(item[0] for item in relevant)
        high = min(item[1] for item in relevant)
        if high < low:
            return None
        return float(low), float(high), 1.0, "%"
    return None


def available_room_limit_fields(manager: Any, area: str) -> tuple[str, ...]:
    return tuple(key for key in LIMIT_FIELDS if room_limit_bounds(manager, area, key) is not None)


def _legacy_room_limit(manager: Any, area: str, key: str, bounds: tuple[float, float, float, str | None]) -> float | None:
    """Conservatively merge beta17 per-device limits into one room value."""
    profiles = manager.settings.get(SETTINGS, {})
    if not isinstance(profiles, dict):
        return None
    values = []
    for spec in specs(manager):
        if spec.area_id != area:
            continue
        raw = profiles.get(spec.identifier, {})
        value = raw.get(key) if isinstance(raw, dict) else None
        parsed = finite(value, bounds[0], bounds[1]) if value is not None else None
        if parsed is not None:
            values.append(float(parsed))
    if not values:
        return None
    return max(values) if "_min_" in key else min(values)


def room_limit_values(manager: Any, area: str) -> dict[str, float]:
    """Room Environment limits, with conservative beta17 migration fallback."""
    env_rooms = manager.settings.get("environment_rooms", {})
    env = env_rooms.get(area, {}) if isinstance(env_rooms, dict) else {}
    saved = env.get(ROOM_LIMITS_KEY, {}) if isinstance(env, dict) else {}
    saved = saved if isinstance(saved, dict) else {}
    result: dict[str, float] = {}
    for key in LIMIT_FIELDS:
        bounds = room_limit_bounds(manager, area, key)
        if bounds is None:
            continue
        default = bounds[0] if "_min_" in key else bounds[1]
        raw = saved.get(key)
        parsed = finite(raw, bounds[0], bounds[1]) if raw is not None else None
        if parsed is None:
            parsed = _legacy_room_limit(manager, area, key, bounds)
        result[key] = float(default if parsed is None else parsed)
    for low_key, high_key in (
        ("temperature_min_limit", "temperature_max_limit"),
        ("humidity_min_limit", "humidity_max_limit"),
        ("fan_min_percentage", "fan_max_percentage"),
    ):
        if low_key in result and high_key in result and result[low_key] > result[high_key]:
            low_bounds = room_limit_bounds(manager, area, low_key)
            high_bounds = room_limit_bounds(manager, area, high_key)
            result[low_key] = float(low_bounds[0])
            result[high_key] = float(high_bounds[1])
    return result


def device_limits(manager: Any, spec: ManagedDevice, cap: Capabilities) -> dict[str, float]:
    """Apply room-wide limits while retaining this device's stricter native bounds."""
    room = room_limit_values(manager, spec.area_id)
    fan_lo, fan_hi, _ = _fan_bounds(cap)
    return {
        "temperature_min_limit": max(cap.min_temp, room.get("temperature_min_limit", cap.min_temp)),
        "temperature_max_limit": min(cap.max_temp, room.get("temperature_max_limit", cap.max_temp)),
        "humidity_min_limit": max(cap.min_humidity, room.get("humidity_min_limit", cap.min_humidity)),
        "humidity_max_limit": min(cap.max_humidity, room.get("humidity_max_limit", cap.max_humidity)),
        "fan_min_percentage": max(fan_lo, room.get("fan_min_percentage", fan_lo)),
        "fan_max_percentage": min(fan_hi, room.get("fan_max_percentage", fan_hi)),
    }


def number_bounds(cap: Capabilities, key: str) -> tuple[float, float, float, str | None]:
    """Per-controller numeric bounds for algorithm/quiet settings only."""
    if key in NUMBER_FIELDS:
        return NUMBER_FIELDS[key][:4]
    if key in ("fan_min_percentage", "fan_max_percentage"):
        low, high, step = _fan_bounds(cap)
        return low, high, step, "%"
    raise KeyError(key)


def applicable_limit_fields(cap: Capabilities) -> tuple[str, ...]:
    """Capability classification retained for migration/tests; UI limits are room-owned."""
    result = []
    if cap.temperature or cap.temperature_range:
        result.extend(("temperature_min_limit", "temperature_max_limit"))
    if cap.humidity:
        result.extend(("humidity_min_limit", "humidity_max_limit"))
    if cap.fan_percentage:
        result.extend(("fan_min_percentage", "fan_max_percentage"))
    return tuple(result)


def permission(manager: Any, spec: ManagedDevice, cap: Capabilities) -> tuple[bool, bool]:
    """Independent grants for ongoing setpoint/speed and power/mode changes."""
    room = room_config(manager, spec)
    device = device_config(manager, spec, cap.primary)
    enabled = room.get("enabled") is True and room.get("allow_actuation") is True
    cfg = settings(manager, spec)
    if "_native_authorization" in cfg:
        from .device_activation import authorized
        valid = cap.domain in ("climate", "fan", "humidifier") and authorized(manager, spec)
        # Automatic/PID/Manual is the explicit permission for this exact native
        # controller. There is no second power/HVAC-mode switch.
        active = cfg.get("control_mode") in ("automatic", "pid", "manual", "off")
        return valid and active, valid and active and "off" in cap.modes
    if device:
        enabled = enabled and device.get("auto_control") is True
        power = enabled and device.get("hardware_confirmed") is True and device.get("method") in ("power", "native")
        return enabled, power
    if cap.domain == "climate":
        pid = manager.settings.get("pid_rooms", {}).get(spec.area_id, {})
        supervisor = pid.get("enabled") is True and cap.primary in pid.get("climate_entities", [])
        # Prior room native mode consent is not generic compressor-cycle consent.
        return enabled or supervisor, False
    if cap.domain == "humidifier":
        return (enabled and (room.get("humidity_setpoint_auto") is True or room.get("humidity_power_auto") is True),
                enabled and room.get("humidity_power_auto") is True and room.get("humidity_power_hardware_confirmed") is True)
    if cap.domain == "fan":
        return (enabled and (room.get("fan_speed_auto") is True or room.get("fan_power_auto") is True),
                enabled and room.get("fan_power_auto") is True and room.get("fan_power_hardware_confirmed") is True)
    direct = enabled and room.get("direct_hardware_confirmed") is True
    return direct, direct


def timing(manager: Any, spec: ManagedDevice, cap: Capabilities, config: dict | None = None) -> tuple[float, float, float]:
    """Hardware minimums cannot be shortened by switching control strategies."""
    room, dev = room_config(manager, spec), device_config(manager, spec, cap.primary)
    prefix = "fan_power_" if cap.domain == "fan" else "humidity_power_" if cap.domain == "humidifier" else ""
    minimum = 120 if cap.domain == "fan" else 600
    values = []
    cfg = config if config is not None else settings(manager, spec)
    raw_saved = manager.settings.get(SETTINGS, {}).get(spec.identifier, {})
    for key, new_key, fallback in (("min_on_s", "min_on_seconds", 600),
                                   ("min_off_s", "min_off_seconds", 600),
                                   ("max_on_s", "max_on_seconds", 7200)):
        raw = dev.get(key, room.get(prefix + key, fallback))
        if config is not None or new_key in raw_saved:
            proposed = cfg[new_key]
            # Preserve previously commissioned minimum dwell; runtime tuning
            # cannot shorten the original physical protection.
            raw = max(float(raw), proposed) if key != "max_on_s" else proposed
        n = finite(raw, 120 if key != "max_on_s" else 900, 86400)
        if n is None:
            raise ValueError("invalid_hardware_timing")
        values.append(max(minimum, n) if key != "max_on_s" else n)
    if values[2] <= values[0]:
        raise ValueError("maximum_runtime_must_exceed_minimum_on")
    return tuple(values)


def control_modes(manager: Any, spec: ManagedDevice) -> tuple[str, ...]:
    cap = capabilities(manager, spec)
    result = ("existing", "automatic", "manual", "off")
    if cap and (cap.temperature and bool(set(cap.modes) & {"heat", "cool"})
                or cap.humidity and (cap.domain == "humidifier" or "dry" in cap.modes)
                or cap.domain == "fan" or set(cap.modes) == {"off", "fan_only"}):
        result += ("pid",)
    return result


def plan_for(manager: Any, spec: ManagedDevice) -> dict:
    environment = getattr(getattr(manager, "plan", None), "environment", {}) or {}
    item = environment.get(spec.area_id, {})
    plan = item.get("climate_plan", {}) if isinstance(item, dict) else {}
    if isinstance(plan, dict) and plan:
        return plan
    # Legacy PID-only rooms have no climate profile plan. Derive live contacts
    # and presence without pretending that absent contacts are verified closed.
    from .discovery import entity_area
    from .occupancy_policy import room_presence, home_presence, sleep_presence
    contacts = [state for state in manager.hass.states.async_all("binary_sensor")
                if entity_area(manager.hass, state.entity_id) == spec.area_id
                and state.attributes.get("device_class") == "window"]
    from .room_sources import selected
    chosen_contacts = selected(manager.settings, spec.area_id, "windows")
    if chosen_contacts is not None:
        contacts = [hass_state for e in chosen_contacts
                    if (hass_state := manager.hass.states.get(e)) is not None
                    and entity_area(manager.hass, e) == spec.area_id
                    and hass_state.attributes.get("device_class") == "window"]
    shared = manager.settings.get("occupancy_global", {})
    room = room_config(manager, spec)
    known = {item.area_id for item in specs(manager)}
    occupancy, evidence, sensors = room_presence(manager.hass, spec.area_id, room, shared, known_areas=known)
    home, home_evidence, trackers = home_presence(manager.hass, shared)
    sleeping, sleep_evidence = sleep_presence(manager.hass, spec.area_id, shared, known)
    return {"window_safe": (chosen_contacts is None or len(contacts) == len(chosen_contacts)) and all(s.state == "off" for s in contacts),
            "window_contacts": [s.entity_id for s in contacts],
            "occupancy": occupancy, "occupancy_evidence": evidence,
            "away": home, "away_evidence": home_evidence, "sleeping": sleeping,
            "presence_entities": sensors, "tracker_entities": trackers,
            "global_presence": shared, "known_presence_areas": sorted(known)}


def profile_name(config: dict, plan: dict) -> str:
    requested = config.get("preset", "none")
    if requested != "none" and requested in PRESETS:
        return requested
    if config.get("control_mode") == "manual":
        return "manual"  # Manual None keeps its independent explicit targets.
    if plan.get("away") == "away":
        return "away"
    if plan.get("sleeping") is True:
        return "sleep"
    if plan.get("occupancy") == "occupied":
        return "comfort"
    # A verified home with an empty room, and incomplete occupancy evidence,
    # both use Home. Unknown evidence must never imply Away.
    return "home"


def targets(manager: Any, spec: ManagedDevice, cap: Capabilities, config: dict,
            plan: dict) -> dict[str, float]:
    room = room_config(manager, spec)
    profile = profile_name(config, plan)
    limits = device_limits(manager, spec, cap)

    raw_profiles = room.get("profiles", {}) if isinstance(room, dict) else {}
    bands = raw_profiles if isinstance(raw_profiles, dict) else {}
    defaults={
        "comfort":{"heat_c":20.0,"cool_c":26.0,"humidity":50.0},
        "home":{"heat_c":18.0,"cool_c":28.0,"humidity":50.0},
        "away":{"heat_c":16.0,"cool_c":30.0,"humidity":50.0},
        "sleep":{"heat_c":18.0,"cool_c":26.0,"humidity":50.0},
        "eco":{"heat_c":17.0,"cool_c":29.0,"humidity":50.0},
    }

    if profile == "manual":
        band=bands.get("comfort",defaults["comfort"])
        fallback=defaults["comfort"]
    else:
        fallback=defaults.get(profile,defaults["home"])
        band=bands.get(profile,fallback)
    band = band if isinstance(band,dict) else fallback
    heat=float(band.get("heat_c",fallback["heat_c"]))
    cool=float(band.get("cool_c",fallback["cool_c"]))
    legacy_humidity = room.get(
        "sleep_humidity_target" if profile == "sleep" else "humidity_target"
    )
    humidity = band.get(
        "humidity",
        legacy_humidity if legacy_humidity is not None else fallback["humidity"],
    )
    result={"heat":float(heat),"cool":float(cool),"humidity":float(humidity)}

    if profile == "manual":
        override=config.get("profile_targets",{}).get("manual",{})
        if isinstance(override,dict):
            result.update({k:v for k,v in override.items() if k in result})

    result["heat"]=max(limits["temperature_min_limit"],
                       min(limits["temperature_max_limit"],float(result["heat"])))
    result["cool"]=max(limits["temperature_min_limit"],
                       min(limits["temperature_max_limit"],float(result["cool"])))
    result["humidity"]=max(limits["humidity_min_limit"],
                           min(limits["humidity_max_limit"],float(result["humidity"])))
    return result


@dataclass(frozen=True, slots=True)
class PIDMemory:
    integral: float = 0.
    measured: float | None = None
    stamp: float | None = None
    derivative: float = 0.
    demand: float = 0.


def pid_step(measured: float, target: float, now: float, *, increasing: bool,
             kp: float, ki: float, kd: float, sample: float,
             memory: PIDMemory | None = None) -> PIDMemory:
    """Dimension-independent PID: °C, RH points, ppm or µg/m³ are never mixed.

    Derivative on measurement, conditional-integration anti-windup and sample
    hold. Reset on invalid timestamps/gaps; no integral carried across profiles.
    """
    old = memory or PIDMemory()
    if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v)
           for v in (measured, target, now, kp, ki, kd, sample)) or min(kp, ki, kd) < 0 or sample < 120:
        return PIDMemory()
    direction = 1 if increasing else -1
    error = direction * (target - measured)
    if old.stamp is None or old.measured is None or now < old.stamp or now-old.stamp > max(3*sample, 1800):
        return PIDMemory(measured=measured, stamp=now, demand=max(0., min(100., kp*error)))
    dt = now-old.stamp
    if dt < sample:
        return old
    minutes = dt/60
    derivative = .25*(measured-old.measured)/minutes + .75*old.derivative
    p, d = kp*error, -direction*kd*derivative
    trial = max(-100., min(100., old.integral+ki*error*minutes))
    raw = p+trial+d
    integral = old.integral if (raw >= 100 and error > 0) or (raw <= 0 and error < 0) else trial
    return PIDMemory(integral, measured, now, derivative, max(0., min(100., p+integral+d)))


def duty_on(demand: float, elapsed: float, cycle: float, min_on: float, min_off: float,
            *, starting: bool = False) -> bool:
    """Slow time-proportioning. Never fabricate a pulse shorter than a dwell.

    Sub-minimum demand is skipped; near-full demand is bounded by min-OFF.
    The runtime separately enforces actual observed transitions and max-ON.
    """
    if any(not math.isfinite(v) for v in (demand, elapsed, cycle, min_on, min_off)) or cycle < min_on+min_off or elapsed < 0:
        return False
    if demand >= 100:
        return True
    duration = cycle * max(0., demand) / 100
    if duration < min_on:
        return False
    duration = min(duration, cycle-min_off)
    phase = elapsed % cycle
    return phase < duration and (not starting or duration-phase >= min_on)


def claimed_sources(manager: Any) -> set[str]:
    active = {e for spec in specs(manager) if settings(manager, spec)["control_mode"] != "existing"
              for e in spec.source_entities}
    for record in getattr(getattr(manager, "equipment", None), "records", {}).values():
        active.update(record.get("power", {}))
        if isinstance(record.get("pending"), dict):
            active.add(record["pending"]["entity"])
    return active


def legacy_settings(manager: Any) -> tuple[dict, dict]:
    """Remove only claimed endpoints, keeping other devices/areas independent."""
    rooms = deepcopy(manager.settings.get("climate_rooms", {}))
    pids = deepcopy(manager.settings.get("pid_rooms", {}))
    claimed = claimed_sources(manager)
    if not claimed:
        return rooms, pids
    for cfg in rooms.values() if isinstance(rooms, dict) else ():
        if not isinstance(cfg, dict):
            continue
        for key in ("climate_entity", "heat_climate_entity", "cool_climate_entity", "dry_climate_entity",
                    "fan_climate_entity", "humidifier_entity", "dehumidifier_entity",
                    "extraction_fan_entity", "purifier_fan_entity", "heat_actuator", "cool_actuator"):
            if cfg.get(key) in claimed:
                cfg.pop(key, None)
        if isinstance(cfg.get("selected_devices"), list):
            cfg["selected_devices"] = [e for e in cfg["selected_devices"] if e not in claimed]
    for cfg in pids.values() if isinstance(pids, dict) else ():
        if isinstance(cfg, dict) and isinstance(cfg.get("climate_entities"), list):
            cfg["climate_entities"] = [e for e in cfg["climate_entities"] if e not in claimed]
            if not cfg["climate_entities"]:
                cfg["enabled"] = False
    return rooms, pids


def legacy_hold(hass: Any, entry_id: str | None, entity: str) -> str | None:
    manager = getattr(hass, "data", {}).get(DOMAIN, {}).get(entry_id)
    if manager is not None and entity in claimed_sources(manager):
        return "per_device_controller_owns_source"
    return None
