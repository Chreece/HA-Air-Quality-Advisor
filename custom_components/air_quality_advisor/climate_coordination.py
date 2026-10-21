"""Evidence-aware room equipment inventory and exclusive HVAC intent planning.

Every device is explicitly configured and verified against Home Assistant's
area registry and its live capabilities. This module never calls services.
Secondary equipment remains advisory until a verified driver owns it.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from .climate_equipment import classify_hvac, humidity_advice
from .discovery import entity_area

ROLE_KINDS = {
    "climate_entity": "climate",
    "heat_climate_entity": "climate",
    "cool_climate_entity": "climate",
    "dry_climate_entity": "climate",
    "fan_climate_entity": "climate",
    "humidifier_entity": "humidifier",
    "dehumidifier_entity": "humidifier",
    "extraction_fan_entity": "fan",
    "purifier_fan_entity": "fan",
}
THERMAL_ROLES = {
    "heat": "heat_climate_entity",
    "cool": "cool_climate_entity",
    "heat_cool": "climate_entity",
}
ACTIVE_HVAC_ACTIONS = frozenset(("heating", "cooling", "drying", "preheating"))


def assigned_entities(config: dict) -> set[str]:
    """All explicitly configured equipment, including inactive role options."""
    if not isinstance(config, dict):
        return set()
    return {
        config[key] for key in ROLE_KINDS
        if isinstance(config.get(key), str) and config[key]
    }


def duplicate_owners(rooms: dict) -> dict[str, list[str]]:
    """A real device may have multiple roles in ONE room, never multiple rooms."""
    mapping: dict[str, set[str]] = {}
    for area, config in rooms.items() if isinstance(rooms, dict) else ():
        if not isinstance(area, str):
            continue
        for entity in assigned_entities(config):
            mapping.setdefault(entity, set()).add(area)
    return {entity: sorted(areas) for entity, areas in mapping.items()
            if len(areas) > 1}


def device_inventory(hass: Any, area: str, config: dict) -> dict[str, dict]:
    """Reject missing, cross-room, unknown-class or unsupported entities."""
    result: dict[str, dict] = {}
    if not isinstance(config, dict):
        return result
    for role, domain in ROLE_KINDS.items():
        entity = config.get(role)
        if not isinstance(entity, str) or not entity:
            continue
        item: dict[str, Any] = {"entity_id": entity, "domain": domain}
        if not entity.startswith(domain + "."):
            item["status"] = "wrong_domain"
        elif entity_area(hass, entity) != area:
            item["status"] = "wrong_room_or_unassigned"
        else:
            state = hass.states.get(entity)
            if state is None or str(state.state).lower() in ("unknown", "unavailable"):
                item["status"] = "unavailable"
            elif domain == "climate":
                features = classify_hvac(state.attributes, str(state.state))
                item.update({"status": features["status"],
                             "capabilities": features,
                             "hvac_action": state.attributes.get("hvac_action")})
            elif domain == "humidifier":
                device_class = state.attributes.get("device_class")
                expected = ("humidifier" if role == "humidifier_entity"
                            else "dehumidifier")
                if device_class != expected:
                    item["status"] = "device_class_not_verified"
                elif state.state not in ("on", "off"):
                    item["status"] = "unknown_power_state"
                else:
                    item.update({"status": "ready",
                                 "active": state.state == "on",
                                 "device_class": device_class})
            else:
                if state.state not in ("on", "off"):
                    item["status"] = "unknown_power_state"
                else:
                    item.update({"status": "ready",
                                 "active": state.state == "on"})
        result[role] = item
    return result


def _usable(inventory: dict, role: str, ability: str | None = None) -> bool:
    item = inventory.get(role, {})
    if item.get("status") != "ready":
        return False
    if ability is not None and not item.get("capabilities", {}).get(ability):
        return False
    return True


def _pick_thermal(inventory: dict, mode: str | None) -> dict:
    if mode not in THERMAL_ROLES:
        return {"status": "no_thermal_demand", "mode": mode}
    role = THERMAL_ROLES[mode]
    # An explicit role override must not silently fall back to another
    # device if it is unavailable. Never misroute a heating/cooling command.
    if role in inventory:
        candidate = role
    else:
        candidate = "climate_entity"
    if not _usable(inventory, candidate, {
        "heat": "heating", "cool": "cooling",
        "heat_cool": "native_heat_cool"}[mode]):
        return {"status": "no_verified_device", "mode": mode,
                "role": candidate}
    selected = inventory[candidate]["entity_id"]
    # Do not run cooling while another selected appliance is already heating,
    # or heat while a selected compressor is drying/cooling.
    opposing = {
        "heat": {"cooling", "drying"},
        "cool": {"heating", "preheating"},
        "heat_cool": set(ACTIVE_HVAC_ACTIONS),
    }[mode]
    for item in inventory.values():
        if (item.get("status") == "ready" and item.get("domain") == "climate"
                and item.get("entity_id") != selected
                and item.get("hvac_action") in opposing):
            return {"status": "opposing_equipment_active",
                    "mode": mode, "entity_id": selected}
    return {"status": "selected", "mode": mode, "entity_id": selected,
            "role": candidate,
            "control": ("existing_native_controller" if candidate == "climate_entity"
                        else "advisory_secondary_driver_pending")}


def _pick_moisture(inventory: dict, advice: dict, thermal: dict) -> dict:
    if advice.get("status") != "advisory":
        return {"status": advice.get("status", "unavailable")}
    action = advice["action"]
    if action == "idle":
        return {"status": "within_band", "action": "idle"}
    if action == "humidify":
        role, ability = "humidifier_entity", None
    else:
        role, ability = "dehumidifier_entity", None
    if _usable(inventory, role, ability):
        chosen = inventory[role]["entity_id"]
        other = ("dehumidifier_entity" if action == "humidify"
                 else "humidifier_entity")
        if inventory.get(other, {}).get("active") is True:
            return {"status": "opposing_moisture_device_running",
                    "action": action}
        return {"status": "selected", "action": action,
                "entity_id": chosen, "role": role,
                "control": "advisory_secondary_driver_pending"}
    if action == "dry" and _usable(inventory, "dry_climate_entity", "drying"):
        chosen = inventory["dry_climate_entity"]["entity_id"]
        if thermal.get("status") == "selected":
            return {"status": "thermal_priority_defer_dry", "action": action}
        return {"status": "selected", "action": action,
                "entity_id": chosen, "role": "dry_climate_entity",
                "control": "advisory_secondary_driver_pending"}
    if action == "dry" and _usable(inventory, "climate_entity", "drying"):
        if thermal.get("status") == "selected":
            return {"status": "thermal_priority_defer_dry", "action": action}
        return {"status": "selected", "action": action,
                "entity_id": inventory["climate_entity"]["entity_id"],
                "role": "climate_entity",
                "control": "advisory_dry_mode_not_temperature_driver"}
    return {"status": "no_verified_device", "action": action}


def room_equipment_plan(hass: Any, area: str, config: dict,
                        temperature_plan: dict, readings: tuple,
                        *, outdoor_safe: bool | None = None,
                        duplicates: dict | None = None) -> dict:
    """Plan *exclusive* thermal and moisture intentions without device writes."""
    inventory = device_inventory(hass, area, config)
    chosen = assigned_entities(config)
    if config.get("controller") in ("on_off","pwm","proportional"):
        chosen.update(
            entity for entity in (
                config.get("heat_actuator"),config.get("cool_actuator"),
            )
            if isinstance(entity,str) and entity
        )
    collision = sorted(chosen.intersection(duplicates or {}))
    if collision:
        return {"status": "duplicate_equipment_owner", "entities": collision,
                "inventory": inventory, "automatic_secondary_actuation": False}
    values = [(r.entity_id, r.value) for r in readings
              if getattr(r, "metric", None) == "humidity"
              and isinstance(r.value, (int, float)) and
              not isinstance(r.value, bool)]
    selected_sensor = config.get("humidity_entity")
    if selected_sensor:
        matching = [v for name, v in values if name == selected_sensor]
        moisture_value = matching[0] if len(matching) == 1 else None
        moisture_evidence = ("selected_sensor" if matching else
                             "selected_sensor_unavailable")
    elif len(values) == 1:
        moisture_value = values[0][1]
        moisture_evidence = "single_verified_room_sensor"
    else:
        moisture_value = None
        moisture_evidence = ("multiple_sensors_choose_one" if values
                             else "no_fresh_room_humidity")
    moisture_advice = humidity_advice(
        moisture_value, low_rh=config.get("humidity_low_rh", 40),
        high_rh=config.get("humidity_high_rh", 60),
        hysteresis=config.get("humidity_hysteresis_rh", 3),
        drying_available=any(_usable(inventory, k) for k in
                              ("dehumidifier_entity", "dry_climate_entity")),
        humidifying_available=_usable(inventory, "humidifier_entity"),
    )
    mode = (temperature_plan.get("mode")
            if temperature_plan.get("status") == "ready" else None)
    thermal = _pick_thermal(inventory, mode)
    moisture = _pick_moisture(inventory, moisture_advice, thermal)
    # A verified open/unknown window holds automatic thermal/humidity control;
    # advisory advice remains visible. A room with no contacts is explicitly
    # labelled but is not automatically considered to have an open window.
    if temperature_plan.get("window_safe") is not True:
        thermal = {"status": "window_interlock"}
        moisture = {"status": "window_interlock"}
    extraction = inventory.get("extraction_fan_entity", {})
    ventilation = {
        "status": ("available_if_outdoor_evidence_supports" if
                   extraction.get("status") == "ready" and outdoor_safe is True
                   else "outdoor_air_unverified_or_fan_unavailable"),
        "outdoor_safe": outdoor_safe,
        "entity_id": extraction.get("entity_id"),
        "control": "advisory_only",
    }
    return {
        "status": "ready",
        "inventory": inventory,
        "thermal": thermal,
        "moisture": moisture,
        "humidity": moisture_advice,
        "humidity_evidence": moisture_evidence,
        "ventilation": ventilation,
        "purification": inventory.get("purifier_fan_entity", {"status": "not_configured"}),
        "automatic_secondary_actuation": False,
        "method": "capability_verified_exclusive_device_advisory",
    }


def planning_capabilities(primary: dict, inventory: dict) -> dict:
    """Advertise *room-wide* heat/cool planning without mislabeling primary.

    Only a verified, live, single-setpoint climate in the configured room
    contributes a secondary heat/cool capability. No new permission is granted
    to send commands; the secondary driver has an independent safety gate.
    """
    merged = dict(primary) if isinstance(primary, dict) else {}
    if merged.get("kind") != "climate":
        merged = {"kind": "unavailable"}
    for role, ability, demand in (
        ("heat_climate_entity", "heating", "heat"),
        ("cool_climate_entity", "cooling", "cool"),
    ):
        candidate = inventory.get(role, {})
        caps = candidate.get("capabilities", {})
        if (candidate.get("status") == "ready"
                and caps.get("temperature_setpoint") is True
                and caps.get(ability) is True):
            merged["kind"] = "climate"
            merged[demand] = True
    return merged


def native_plan_hold_reason(primary: str | None, equipment: dict,
                            mode: str | None) -> str | None:
    """Never silently fall back to a primary thermostat after a role override."""
    if equipment.get("status") == "duplicate_equipment_owner":
        return "duplicate_equipment_owner"
    if mode not in ("heat", "cool", "heat_cool"):
        return None
    thermal = equipment.get("thermal", {})
    status = thermal.get("status")
    if status != "selected":
        return status if status in (
            "no_verified_device", "opposing_equipment_active",
            "window_interlock") else "incomplete_equipment_plan"
    selected = thermal.get("entity_id")
    if not isinstance(selected, str) or not selected.startswith("climate."):
        return "unverified_thermal_target"
    if selected != primary:
        return "secondary_thermal_driver_pending"
    return None
