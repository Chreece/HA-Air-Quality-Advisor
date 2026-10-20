"""Detect duplicated climate actuator ownership between Home Assistant entries.

No device writes, config changes or secret reads. Only configured output
entity IDs (not sensors, tokens or device identifiers) are inspected.
Repeated roles for the same physical device within ONE room/entry remain
valid; only independently *authorized* (not advisory-only) config entries
can claim actuator ownership. A legacy PID with enabled=true is authorized.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from .const import DOMAIN
from .climate_coordination import assigned_entities


def active_output_entities(config: Mapping) -> set[str]:
    """Return all hardware outputs that an enabled room could command."""
    outputs=assigned_entities(config)
    if config.get("controller") in ("on_off","pwm","proportional"):
        for role in ("heat_actuator","cool_actuator"):
            value=config.get(role)
            if isinstance(value,str) and value:
                outputs.add(value)
    return outputs


def _configured_owners(config: Mapping) -> dict[str,set[str]]:
    outputs:dict[str,set[str]]=defaultdict(set)
    rooms=config.get("climate_rooms",{})
    if isinstance(rooms,Mapping):
        for area,room in rooms.items():
            if (not isinstance(area,str) or not isinstance(room,Mapping)
                    or room.get("enabled") is not True
                    or room.get("allow_actuation") is not True):
                continue
            for entity in active_output_entities(room):
                outputs[entity].add(area)
    # The legacy PID is another potentially active native HVAC owner.
    pid_rooms=config.get("pid_rooms",{})
    if isinstance(pid_rooms,Mapping):
        for area,profile in pid_rooms.items():
            if (not isinstance(area,str) or not isinstance(profile,Mapping)
                    or profile.get("enabled") is not True):
                continue
            selected=profile.get("climate_entities")
            if selected is None:
                value=profile.get("climate_entity")
                selected=[value] if isinstance(value,str) else []
            if not isinstance(selected,(tuple,list)):
                selected=[]
            for entity in selected:
                if isinstance(entity,str) and entity.startswith("climate."):
                    outputs[entity].add(area)
    return outputs


def other_entry_output_owners(hass:Any, current_entry_id:str) -> dict[str,set[str]] | None:
    """Map hardware output -> foreign owner label, or None if HA query fails.

    HA always provides hass.config_entries.async_entries. The missing
    attribute is accepted only in the lightweight standalone unit doubles;
    a present but failing HA registry must fail closed in production.
    """
    config_entries=getattr(hass,"config_entries",None)
    lookup=getattr(config_entries,"async_entries",None)
    if lookup is None:
        return {}
    try:
        entries=lookup(DOMAIN)
        if not isinstance(entries,(tuple,list)):
            return None
        owners:dict[str,set[str]]=defaultdict(set)
        for entry in entries:
            entry_id=getattr(entry,"entry_id",None)
            if (not isinstance(entry_id,str) or
                    entry_id==current_entry_id or
                    getattr(entry,"disabled_by",None) is not None):
                continue
            data=getattr(entry,"data",{})
            options=getattr(entry,"options",{})
            if not isinstance(data,Mapping) or not isinstance(options,Mapping):
                return None
            profiles=_configured_owners({**data,**options})
            for entity,areas in profiles.items():
                for area in areas:
                    owners[entity].add(f"{entry_id}:{area}")
        return dict(owners)
    except Exception:
        return None


def foreign_owner_hold(hass:Any, current_entry_id:str, entity:str) -> str | None:
    """No command if the same configured device is owned in another entry."""
    if not isinstance(current_entry_id,str) or not current_entry_id:
        return "entry_identity_unavailable"
    owners=other_entry_output_owners(hass,current_entry_id)
    if owners is None:
        return "other_config_entries_unverifiable"
    if entity in owners:
        return "cross_entry_equipment_owner"
    return None


def cross_entry_collisions(hass:Any, current_entry_id:str,
                           rooms:Mapping) -> dict[str,list[str]]:
    """Collision records compatible with the room equipment planner."""
    other=other_entry_output_owners(hass,current_entry_id)
    if other is None:
        return {
            entity:["other_config_entries_unverifiable"]
            for room in rooms.values()
            if isinstance(room,Mapping) and room.get("enabled") is True
        and room.get("allow_actuation") is True
            and room.get("allow_actuation") is True
            for entity in active_output_entities(room)
        }
    own={
        entity for room in rooms.values()
        if isinstance(room,Mapping) and room.get("enabled") is True
        for entity in active_output_entities(room)
    }
    return {entity:sorted(other[entity])
            for entity in sorted(own)
            if entity in other}
