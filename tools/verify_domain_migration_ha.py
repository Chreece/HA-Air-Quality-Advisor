"""Actual Home Assistant 2026.10 domain-registry migration verification."""
from __future__ import annotations
import asyncio
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import MappingProxyType

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from homeassistant.config_entries import ConfigEntries,ConfigEntry,ConfigSubentryDataWithId,SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant import loader
from homeassistant.helpers import device_registry as dr, entity_registry as er
from custom_components.environment_manager.const import DOMAIN,LEGACY_DOMAIN
from custom_components.environment_manager.domain_migration import async_migrate_legacy_registry


async def check(config_dir:str)->None:
    hass=HomeAssistant(config_dir)
    loader.async_setup(hass)
    hass.config_entries=ConfigEntries(hass,{})
    dr.async_setup(hass)
    await dr.async_load(hass); await er.async_load(hass)
    devices=dr.async_get(hass); entities=er.async_get(hass)

    sub_id="room-subentry-unchanged"
    sub=[{"subentry_id":sub_id,"data":{"area_id":"living"},"subentry_type":"room","title":"Living","unique_id":"living"}]
    old=ConfigEntry(data={"areas":["living"]},options={"saved":True},domain=LEGACY_DOMAIN,
        entry_id="legacy-entry",title="Home Environment Manager",source=SOURCE_USER,
        unique_id="home",version=1,minor_version=1,discovery_keys=MappingProxyType({}),
        subentries_data=sub)
    new=ConfigEntry(data={"areas":["living"],"_legacy_entry_id":old.entry_id},options={"saved":True},
        domain=DOMAIN,entry_id="new-entry",title="Home Environment Manager",source=SOURCE_USER,
        unique_id="home",version=1,minor_version=1,discovery_keys=MappingProxyType({}),
        subentries_data=sub)
    hass.config_entries._entries[old.entry_id]=old
    hass.config_entries._entries[new.entry_id]=new

    device=devices.async_get_or_create(
        config_entry_id=old.entry_id,config_subentry_id=sub_id,
        identifiers={(LEGACY_DOMAIN,"managed-device")},
        name="Managed device",
    )
    devices.async_update_device(device.id,name_by_user="My custom device")
    entity=entities.async_get_or_create(
        "number",LEGACY_DOMAIN,"stable-unique",config_entry=old,
        config_subentry_id=sub_id,device_id=device.id,
        suggested_object_id="stable_entity",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    old_entity_id=entity.entity_id
    old_device_id=device.id

    await async_migrate_legacy_registry(hass,old,new)

    assert hass.config_entries.async_get_entry(old.entry_id) is None
    assert hass.config_entries.async_get_entry(new.entry_id) is new
    migrated=entities.async_get(old_entity_id)
    assert migrated is not None
    assert migrated.entity_id==old_entity_id
    assert migrated.unique_id=="stable-unique"
    assert migrated.platform==DOMAIN
    assert migrated.config_entry_id==new.entry_id
    assert migrated.config_subentry_id==sub_id
    assert migrated.device_id==old_device_id
    assert migrated.disabled_by is er.RegistryEntryDisabler.USER
    moved=devices.async_get(old_device_id)
    assert moved is not None
    assert moved.id==old_device_id
    assert moved.config_entry_id==new.entry_id
    assert moved.config_subentry_id==sub_id
    assert moved.name_by_user=="My custom device"
    assert (DOMAIN,"managed-device") in moved.identifiers
    assert not any(domain==LEGACY_DOMAIN for domain,_ in moved.identifiers)

    await hass.async_block_till_done()
    await hass.async_stop(force=True)
    print("Home Assistant 2026.10 config-entry/entity/device domain migration: PASS")

if __name__=="__main__":
    with TemporaryDirectory(prefix="hem-domain-migration-") as directory:
        asyncio.run(check(directory))
