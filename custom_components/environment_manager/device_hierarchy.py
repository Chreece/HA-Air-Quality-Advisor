"""Home -> Area hub -> managed equipment, without taking over native devices.

Area hubs keep their existing identifiers. Manager-created equipment devices
are *logical controllers*: the source integration's physical device, its area,
connections, identifiers and original gateway are never edited. Only explicitly
configured, same-area controller sources are eligible for a child device.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

from .const import CONF_AREAS, CONF_CLIMATE_ROOMS, CONF_PID_ROOMS, DOMAIN

# Importing this small model must not import HA entity platforms. It is used
# before platform forwarding and by all configuration-entity platforms.
NATIVE_DOMAINS = frozenset(("climate", "fan", "humidifier"))
DIRECT_DOMAINS = frozenset(("switch", "input_boolean", "number", "input_number"))
ROLES = (
    "climate_entity", "heat_climate_entity", "cool_climate_entity",
    "dry_climate_entity", "fan_climate_entity", "humidifier_entity",
    "dehumidifier_entity", "extraction_fan_entity", "purifier_fan_entity",
)


@dataclass(frozen=True, slots=True)
class ManagedDevice:
    """One logical controller device for one physical product in one area."""

    identifier: str
    area_id: str
    name: str
    source_device_id: str | None
    source_entities: tuple[str, ...]


def native_source(hass: Any, entity_id: str) -> bool:
    """A logical Manager entity must never be selected as physical equipment."""
    from homeassistant.helpers import entity_registry as er
    try:
        entity = er.async_get(hass).async_get(entity_id)
        return entity is None or getattr(entity, "platform", None) != DOMAIN
    except Exception:
        return False


def configured_area_ids(settings: dict[str, Any]) -> tuple[str, ...]:
    """Monitoring areas plus enabled climate/PID-only areas, not every HA area."""
    selected = settings.get(CONF_AREAS, [])
    result = list(selected) if isinstance(selected, (list, tuple)) else []
    for key in (CONF_CLIMATE_ROOMS, CONF_PID_ROOMS):
        rooms = settings.get(key, {})
        if isinstance(rooms, dict):
            result.extend(area for area, cfg in rooms.items()
                          if isinstance(cfg, dict) and (cfg.get("enabled") is True
                              or key == CONF_CLIMATE_ROOMS
                              and isinstance(cfg.get("selected_devices"), list)
                              and any(isinstance(e, str) and e.partition(".")[0] in NATIVE_DOMAINS
                                      for e in cfg["selected_devices"])))
    return tuple(dict.fromkeys(area for area in result
                               if isinstance(area, str) and area))


def area_identifier(entry_id: str, area_id: str) -> str:
    """Never change beta 6-10's identifiers or its room entity unique IDs."""
    return f"{entry_id}_area_{area_id}"


def configured_sources(settings: dict, area_id: str) -> tuple[str, ...]:
    """Do not turn arbitrary devices found in a room into controlled devices."""
    found: set[str] = set()
    rooms = settings.get(CONF_CLIMATE_ROOMS, {})
    cfg = rooms.get(area_id) if isinstance(rooms, dict) else None
    if isinstance(cfg, dict):
        selected = cfg.get("selected_devices")
        # Inventory membership is not an actuation grant. A selected physical
        # device needs its controller/settings even while automation is OFF.
        if isinstance(selected, list):
            found.update(entity for entity in selected
                         if isinstance(entity, str) and entity.partition(".")[0] in NATIVE_DOMAINS)
    if isinstance(cfg, dict) and cfg.get("enabled") is True:
        selected = cfg.get("selected_devices")
        for key in ROLES:
            entity = cfg.get(key)
            if (isinstance(entity, str) and entity.partition(".")[0] in NATIVE_DOMAINS
                    and (not isinstance(selected, list) or entity in selected)):
                found.add(entity)
        profiles = cfg.get("device_settings", {})
        if isinstance(selected, list) and isinstance(profiles, dict):
            for entity in selected:
                profile = profiles.get(entity) if isinstance(entity, str) else None
                if (isinstance(profile, dict) and profile.get("auto_control") is True
                        and entity.partition(".")[0] in NATIVE_DOMAINS):
                    found.add(entity)
        if cfg.get("controller") in ("on_off", "pwm", "proportional"):
            for key in ("heat_actuator", "cool_actuator"):
                entity = cfg.get(key)
                if (isinstance(entity, str)
                        and entity.partition(".")[0] in DIRECT_DOMAINS):
                    found.add(entity)
    rooms = settings.get(CONF_PID_ROOMS, {})
    cfg = rooms.get(area_id) if isinstance(rooms, dict) else None
    if isinstance(cfg, dict) and cfg.get("enabled") is True:
        sources = cfg.get("climate_entities", [])
        if isinstance(sources, list):
            found.update(entity for entity in sources
                         if isinstance(entity, str) and entity.startswith("climate."))
    return tuple(sorted(found))


def managed_devices(hass: Any, entry_id: str, settings: dict) -> tuple[ManagedDevice, ...]:
    """Group endpoints by real HA device, not by display names or HVAC roles.

    A multi-endpoint physical product can have controllers in separate HA
    areas. Its area-specific logical devices remain separate, while duplicate
    heat/cool/fan roles for the SAME source do not create duplicates.
    """
    sources = {area: configured_sources(settings, area)
               for area in configured_area_ids(settings)}
    if not any(sources.values()):
        return ()
    from homeassistant.helpers import area_registry as ar
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    areas, devices, entities = ar.async_get(hass), dr.async_get(hass), er.async_get(hass)
    groups: dict[tuple[str, str], dict] = {}
    for area_id, configured in sources.items():
        if areas.async_get_area(area_id) is None:
            continue
        for entity_id in configured:
            entity = entities.async_get(entity_id)
            if entity is not None and getattr(entity, "platform", None) == DOMAIN:
                continue  # Never wrap our own controllers recursively.
            source_id = getattr(entity, "device_id", None)
            source = devices.async_get(source_id) if source_id else None
            effective_area = (getattr(entity, "area_id", None)
                              or getattr(source, "area_id", None))
            if effective_area != area_id:
                continue  # Missing/ambiguous/cross-room assignments fail closed.
            state = hass.states.get(entity_id)
            if source_id and source is not None:
                identity = f"device:{source_id}"
                name = (getattr(source, "name_by_user", None)
                        or getattr(source, "name", None))
            else:
                # Registry IDs survive source entity_id renames. A disabled
                # entity still has its registry identity while unavailable.
                identity = f"entity:{getattr(entity, 'id', None) or entity_id}"
                name = (getattr(entity, "name", None)
                        or getattr(entity, "original_name", None))
                source_id = None
            if not isinstance(name, str) or not name:
                name = (getattr(state, "name", None) or entity_id)
            key = (area_id, identity)
            group = groups.setdefault(key, {
                "area_id": area_id, "name": name,
                "source_device_id": source_id, "sources": [],
            })
            group["sources"].append(entity_id)
    result = []
    for (area_id, identity), group in sorted(groups.items()):
        digest = hashlib.sha256(f"{area_id}\0{identity}".encode()).hexdigest()[:24]
        result.append(ManagedDevice(
            identifier=f"{entry_id}_controller_{digest}",
            area_id=area_id, name=group["name"],
            source_device_id=group["source_device_id"],
            source_entities=tuple(sorted(set(group["sources"]))),
        ))
    return tuple(result)


def _register(registry: Any, entry_id: str, info: dict, *,
              hass: Any, subentry_id: str | None = None,
              parent: Any = None) -> Any:
    """Ordinary device registration, including beta11 SERVICE migration."""
    from .room_hubs import async_migrate_device_group

    async_migrate_device_group(hass, registry, entry_id, info["identifiers"], subentry_id)
    # Explicit None is essential: omitting entry_type leaves old SERVICE flags.
    values = {**info, "entry_type": None}
    if parent is not None:
        values["via_device_id"] = parent.id
    return registry.async_get_or_create(
        config_entry_id=entry_id, config_subentry_id=subentry_id, **values
    )


def async_register_hierarchy(hass: Any, entry: Any) -> None:
    """Register parents before children and before *any* platform is forwarded.

    This is registry-only setup. It makes no service call and never writes a
    source device. Re-running it is idempotent and respects user area overrides.
    """
    from homeassistant.helpers import area_registry as ar
    from homeassistant.helpers import device_registry as dr

    manager = entry.runtime_data
    settings = {**entry.data, **entry.options}
    registry, areas = dr.async_get(hass), ar.async_get(hass)
    from .room_hubs import home_subentry_id
    home_subentry = getattr(manager, "_home_subentry", None) or home_subentry_id(entry)
    manager._home_subentry = home_subentry
    home = _register(registry, entry.entry_id, {
        "identifiers": {(DOMAIN, entry.entry_id)},
        "name": "Home",
        "manufacturer": "Home Environment Manager",
        "model": "Home Environment Hub",
    }, hass=hass, subentry_id=home_subentry)
    subentries = getattr(manager, "_room_subentries", {})
    device_subentries = {entry.entry_id: home_subentry}
    area_devices = {}
    for area_id in configured_area_ids(settings):
        area = areas.async_get_area(area_id)
        if area is None:
            continue
        device = _register(registry, entry.entry_id, {
            "identifiers": {(DOMAIN, area_identifier(entry.entry_id, area_id))},
            "name": f"{area.name} Environment",
            "manufacturer": "Home Environment Manager",
            "model": "Area Environment Hub",
        }, hass=hass, subentry_id=subentries.get(area_id), parent=home)
        if device.area_id is None:
            registry.async_update_device(device.id, area_id=area_id)
        area_devices[area_id] = device
        device_subentries[area_identifier(entry.entry_id, area_id)] = subentries.get(area_id)
    specs = managed_devices(hass, entry.entry_id, settings)
    controllers, by_source = {}, {}
    for spec in specs:
        parent = area_devices.get(spec.area_id)
        if parent is None:
            continue
        info = {
            "identifiers": {(DOMAIN, spec.identifier)},
            "name": f"{spec.name} Controller",
            "manufacturer": "Home Environment Manager",
            "model": "Managed Environment Controller",
        }
        if spec.source_device_id:
            info["configuration_url"] = (
                f"homeassistant://config/devices/device/{spec.source_device_id}"
            )
        child = _register(registry, entry.entry_id, info, hass=hass, parent=parent,
                          subentry_id=subentries.get(spec.area_id))
        device_subentries[spec.identifier] = subentries.get(spec.area_id)
        if child.area_id is None:
            registry.async_update_device(child.id, area_id=spec.area_id)
        controllers[spec.identifier] = {"spec": spec, "device_id": child.id}
        for entity_id in spec.source_entities:
            by_source[(spec.area_id, entity_id)] = spec.identifier
    manager._device_hierarchy = {
        "home_device_id": home.id,
        "room_subentries": dict(subentries),
        "device_subentries": device_subentries,
        "areas": {area: device.id for area, device in area_devices.items()},
        "controllers": controllers,
        "by_source": by_source,
    }


def controller_device_info(manager: Any, area_id: str, entity_id: str) -> dict | None:
    """Attach only explicitly registered source-specific controls to a child."""
    state = getattr(manager, "_device_hierarchy", {})
    identifier = state.get("by_source", {}).get((area_id, entity_id))
    return {"identifiers": {(DOMAIN, identifier)}} if identifier else None


def hierarchy_attributes(manager: Any, area_id: str) -> dict[str, Any]:
    """Trace logical controllers back to physical sources without duplicating data."""
    state = getattr(manager, "_device_hierarchy", {})
    return {
        "area_hub_device_id": state.get("areas", {}).get(area_id),
        "room_hub_subentry_id": state.get("room_subentries", {}).get(area_id),
        "managed_devices": [
            {"controller_device_id": item["device_id"],
             "source_device_id": item["spec"].source_device_id,
             "source_entity_ids": list(item["spec"].source_entities)}
            for item in state.get("controllers", {}).values()
            if item["spec"].area_id == area_id
        ],
    }
