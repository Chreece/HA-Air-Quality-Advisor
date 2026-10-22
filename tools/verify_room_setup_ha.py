"""Exercise the rooms-first wizard with actual HA selectors and registries.

This isolated test does not start the integration or call equipment services.
The flow harness captures its forms, while source discovery, selectors, storage
shapes and the generated Home/room/controller hierarchy use production code.
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
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from custom_components.air_quality_advisor.const import DOMAIN
from custom_components.air_quality_advisor.compact_options import CompactOptionsMixin
from custom_components.air_quality_advisor.room_setup import RoomSetupMixin
from custom_components.air_quality_advisor.room_sources import GROUPS
from custom_components.air_quality_advisor.device_hierarchy import async_register_hierarchy
from custom_components.air_quality_advisor.room_hubs import async_sync_room_hubs


class Wizard(RoomSetupMixin, CompactOptionsMixin):
    def __init__(self, hass):
        self.hass = hass
        self._values = {}
        self._editing = False

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_abort(self, **kwargs):
        raise AssertionError(kwargs)

    async def _finish(self):
        return {"type": "create_entry", "data": self._values}


def entry(domain, identity, data):
    return ConfigEntry(data=data, options={}, domain=domain, entry_id=identity,
        title=identity, source=SOURCE_USER, unique_id=identity, version=1,
        minor_version=1, discovery_keys=MappingProxyType({}), subentries_data=())


async def check(config_dir):
    hass = HomeAssistant(config_dir)
    hass.config_entries = ConfigEntries(hass, {})
    dr.async_setup(hass)
    await ar.async_load(hass)
    await dr.async_load(hass)
    await er.async_load(hass)
    areas, devices, entities = ar.async_get(hass), dr.async_get(hass), er.async_get(hass)
    living, office = areas.async_create("Living room"), areas.async_create("Office")
    native = entry("demo", "native-test-equipment", {})
    hass.config_entries._entries[native.entry_id] = native
    physical = devices.async_get_or_create(config_entry_id=native.entry_id,
        identifiers={("demo", "physical-device")}, name="Multisensor and HVAC")
    devices.async_update_device(physical.id, area_id=living.id)
    source_ids = {}
    definitions = {
        "windows": ("binary_sensor", "window", "off", {}),
        "air_quality": ("sensor", "co2", "700", {"unit_of_measurement": "ppm"}),
        "temperature": ("sensor", "temperature", "21", {"unit_of_measurement": "°C"}),
        "humidity": ("sensor", "humidity", "45", {"unit_of_measurement": "%"}),
        "pressure": ("sensor", "atmospheric_pressure", "1012", {"unit_of_measurement": "hPa"}),
        "climate_devices": ("climate", None, "off", {"hvac_modes": ["off", "heat"], "supported_features": 1}),
    }
    for group, (domain, device_class, state, attributes) in definitions.items():
        item = entities.async_get_or_create(domain, "demo", "source_"+group,
            config_entry=native, device_id=physical.id, original_name="Source "+group,
            original_device_class=device_class)
        attrs = {**attributes, "friendly_name": "Source "+group}
        if device_class:
            attrs["device_class"] = device_class
        hass.states.async_set(item.entity_id, state, attrs)
        source_ids[group] = item.entity_id
    wizard = Wizard(hass)
    first = await wizard.async_step_setup_rooms()
    first["data_schema"]({"areas": [living.id, office.id]})
    room = await wizard.async_step_setup_rooms({"areas": [living.id, office.id]})
    assert room["step_id"] == "setup_room_sources"
    assert list(map(str, room["data_schema"].schema)) == list(GROUPS)
    inputs = {group: [entity_id] for group, entity_id in source_ids.items()}
    room["data_schema"](inputs)
    for selector in room["data_schema"].schema.values():
        labels = [option["label"] for option in selector.config["options"]]
        assert any("Multisensor and HVAC — Source " in text for text in labels)
    empty = await wizard.async_step_setup_room_sources(inputs)
    assert empty["step_id"] == "setup_room_sources"
    assert empty["description_placeholders"]["area_name"] == "Office"
    general = await wizard.async_step_setup_room_sources({key: [] for key in GROUPS})
    assert general["step_id"] == "setup_general"
    defaults = general["data_schema"]({})
    done = await wizard.async_step_setup_general(defaults)
    assert done["type"] == "create_entry"
    data = done["data"]
    assert data["room_sources"][living.id] == inputs
    assert all(not values for values in data["room_sources"][office.id].values())
    assert data["climate_rooms"][living.id].get("allow_actuation") is not True
    manager_entry = entry(DOMAIN, "room-setup-test", data)
    hass.config_entries._entries[manager_entry.entry_id] = manager_entry
    manager = SimpleNamespace(hass=hass, entry=manager_entry, settings=data)
    manager_entry.runtime_data = manager
    manager._room_subentries = async_sync_room_hubs(hass, manager_entry)
    async_register_hierarchy(hass, manager_entry)
    assert len(manager_entry.subentries) == 2
    assert len(manager._device_hierarchy["controllers"]) == 1
    assert devices.async_get(physical.id).config_entry_id == native.entry_id
    assert len(manager._device_hierarchy["areas"]) == 2
    await hass.async_block_till_done()
    await hass.async_stop(force=True)
    print("Actual HA rooms-first selectors, empty room, final save and Home/room/controller hierarchy: PASS")


if __name__ == "__main__":
    with TemporaryDirectory(prefix="hem-room-setup-") as directory:
        asyncio.run(check(directory))
