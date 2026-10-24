"""Installed Home Assistant 2026.10 late native fan capability smoke test.

Register a real physical climate source in HA's registries without loading
its vendor integration. Validate the Manager's quiet configuration entities
without issuing or enabling any real hardware commands.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import MappingProxyType, SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from homeassistant.config_entries import ConfigEntries, ConfigEntry, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from custom_components.environment_manager.device_hierarchy import async_register_hierarchy
from custom_components.environment_manager.room_hubs import async_sync_room_hubs
from custom_components.environment_manager import select as selector
from custom_components.environment_manager import switch as toggles


def entry(domain, identity, data):
    return ConfigEntry(
        data=data, options={}, domain=domain, entry_id=identity,
        title=identity, source=SOURCE_USER, unique_id=identity, version=1,
        minor_version=1, discovery_keys=MappingProxyType({}), subentries_data=(),
    )


async def main(directory):
    hass=HomeAssistant(directory)
    hass.config_entries=ConfigEntries(hass,{})
    dr.async_setup(hass)
    await ar.async_load(hass)
    await dr.async_load(hass)
    await er.async_load(hass)

    area=ar.async_get(hass).async_create("Native fan room")
    native=entry("demo", "physical-integration", {})
    hass.config_entries._entries[native.entry_id]=native
    physical=dr.async_get(hass).async_get_or_create(
        config_entry_id=native.entry_id,
        identifiers={("demo","physical-controller")},
        name="Generic dehumidifying climate",
    )
    dr.async_get(hass).async_update_device(physical.id,area_id=area.id)
    source=er.async_get(hass).async_get_or_create(
        "climate","demo","physical-climate",config_entry=native,
        device_id=physical.id,original_name="Native device",
    )

    configured=entry("environment_manager","manager-entry",{
        "areas":[area.id],
        "climate_rooms":{area.id:{
            "selected_devices":[source.entity_id],
            "device_settings":{source.entity_id:{"auto_control":False}},
        }},
    })
    hass.config_entries._entries[configured.entry_id]=configured

    class Manager:
        _active=False
        @property
        def settings(self):
            return {**self.entry.data,**self.entry.options}

    manager=Manager()
    manager.hass,manager.entry=hass,configured
    configured.runtime_data=manager
    manager._room_subentries=async_sync_room_hubs(hass,configured)
    async_register_hierarchy(hass,configured)

    all_select,all_switch=[],[]
    def add_select(batch,**kwargs):
        all_select.extend(batch)
    def add_switch(batch,**kwargs):
        all_switch.extend(batch)

    # Real selected physical device but no native state published yet.
    await selector.async_setup_entry(hass,configured,add_select)
    await toggles.async_setup_entry(hass,configured,add_switch)
    assert not any(getattr(s,"_key",None)=="quiet_fan_mode"
                   for s in all_select)
    assert not any(getattr(s,"_key",None) in ("quiet_sleep","quiet_occupied")
                   for s in all_switch)

    hass.states.async_set(source.entity_id,"off",{
        "hvac_modes":["off","dry"],
        "supported_features":8,
        "fan_modes":["low","medium","high"],
        "fan_mode":"high",
        "device_class":"dehumidifier",
    })
    await hass.async_block_till_done()

    selectors=[e for e in all_select if getattr(e,"_key",None)=="quiet_fan_mode"]
    switches=[e for e in all_switch if getattr(e,"_key",None) in ("quiet_sleep","quiet_occupied")]
    assert len(selectors)==1
    assert len(switches)==2
    assert selectors[0].options==["low","medium","high"]
    assert selectors[0].available
    assert all(e.available for e in switches)
    assert len({e.unique_id for e in selectors+switches})==3
    assert all(e.device_info["identifiers"] for e in selectors+switches)
    assert not hass.services.has_service("climate","set_fan_mode")
    # Duplicate physical report must not generate duplicate Manager entities.
    hass.states.async_set(source.entity_id,"off",{
        "hvac_modes":["off","dry"],
        "supported_features":8,
        "fan_modes":["low","medium","high"],
        "fan_mode":"high",
        "device_class":"dehumidifier",
    })
    await hass.async_block_till_done()
    assert len([e for e in all_select if getattr(e,"_key",None)=="quiet_fan_mode"])==1
    assert len([e for e in all_switch if getattr(e,"_key",None) in ("quiet_sleep","quiet_occupied")])==2
    await hass.async_stop(force=True)
    print("HA 2026.10 generic native quiet controls late capability registration: PASS")


if __name__=="__main__":
    with TemporaryDirectory(prefix="hem-beta33-quiet-") as directory:
        asyncio.run(main(directory))
