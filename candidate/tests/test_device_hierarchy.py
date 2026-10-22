"""Area hubs own logical controllers, not another integration's hardware."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_discovery import adapter

from custom_components.air_quality_advisor.device_hierarchy import (
    async_register_hierarchy, configured_area_ids, configured_sources,
    controller_device_info, hierarchy_attributes, managed_devices,
)


class DeviceRegistry:
    """Faithful identity/parent subset of HA's device registry."""

    def __init__(self):
        self.devices = {}
        self.keys = {}
        self.created = []
        self.updated = []

    def async_get(self, device_id):
        return self.devices.get(device_id)

    def async_get_or_create(self, *, config_entry_id, **info):
        key = (config_entry_id, next(iter(info["identifiers"])))
        parent = info.get("via_device")
        if parent:
            assert (config_entry_id, parent) in self.keys, "Parent must exist first"
        device = self.keys.get(key)
        if device is None:
            device = SimpleNamespace(id=f"logical-{len(self.keys)}", area_id=None,
                                     name_by_user=None)
            self.keys[key] = device
            self.devices[device.id] = device
        for k, v in info.items():
            setattr(device, k, v)
        if parent:
            device.via_device_id = self.keys[(config_entry_id, parent)].id
        self.created.append((config_entry_id, deepcopy(info)))
        return device

    def async_update_device(self, device_id, **info):
        assert device_id.startswith("logical-"), "Never mutate a physical device"
        self.updated.append((device_id, info))
        for key, value in info.items():
            setattr(self.devices[device_id], key, value)


@pytest.fixture
def hierarchy(adapter, monkeypatch):
    from homeassistant.helpers import area_registry as ar
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    registry = DeviceRegistry()
    areas = {a: SimpleNamespace(id=a, name=n) for a, n in
             (("kitchen", "Küche"), ("bedroom", "Bedroom"), ("office", "Office"))}
    entities = {}
    states = {}
    monkeypatch.setattr(ar, "async_get", lambda h: SimpleNamespace(
        async_get_area=areas.get))
    monkeypatch.setattr(dr, "async_get", lambda h: registry)
    monkeypatch.setattr(dr, "DeviceEntryType", SimpleNamespace(SERVICE="service"), raising=False)
    monkeypatch.setattr(er, "async_get", lambda h: SimpleNamespace(async_get=entities.get))
    hass = SimpleNamespace(states=SimpleNamespace(get=states.get),
                           services=SimpleNamespace(async_call=lambda *a, **kw:
                                                    pytest.fail("No actuator call")))

    def source(entity_id, *, device_id="physical-ac", area="kitchen", entity_area=None,
               registry_id=None, platform="native", device_name="Air conditioner"):
        if device_id and device_id not in registry.devices:
            registry.devices[device_id] = SimpleNamespace(
                id=device_id, name=device_name, name_by_user=None, area_id=area,
                identifiers={("native", device_id)}, via_device_id="native-gateway",
            )
        entities[entity_id] = SimpleNamespace(
            id=registry_id or f"registry-{entity_id}", device_id=device_id,
            area_id=entity_area, platform=platform, name=None, original_name=None,
        )
        states[entity_id] = SimpleNamespace(name=entity_id, state="off", attributes={})

    settings = {
        "areas": ["kitchen", "office"],
        "climate_rooms": {
            "kitchen": {"enabled": True, "controller": "device",
                        "climate_entity": "climate.ac", "heat_climate_entity": "climate.ac",
                        "fan_climate_entity": "climate.ac", "purifier_fan_entity": "fan.ac",
                        "selected_devices": ["climate.ac", "fan.ac"],
                        "device_settings": {"climate.ac": {"auto_control": True},
                                            "fan.ac": {"auto_control": True}}},
            "bedroom": {"enabled": True, "controller": "device"},
        },
    }
    entry = SimpleNamespace(entry_id="hem", data=settings, options={})
    manager = SimpleNamespace(settings=settings, entry=entry, hass=hass)
    entry.runtime_data = manager
    return SimpleNamespace(hass=hass, entry=entry, manager=manager, settings=settings,
                           registry=registry, areas=areas, entities=entities,
                           states=states, source=source)


def test_monitoring_and_climate_only_areas_are_hubs_without_hardware(hierarchy):
    h = hierarchy
    h.settings["climate_rooms"]["kitchen"] = {"enabled": True}
    async_register_hierarchy(h.hass, h.entry)
    assert len(h.registry.keys) == 4  # Home, Kitchen, Office, Bedroom.
    assert configured_area_ids(h.settings) == ("kitchen", "office", "bedroom")
    home = h.registry.keys[("hem", ("air_quality_advisor", "hem"))]
    for area in configured_area_ids(h.settings):
        hub = h.registry.keys[("hem", ("air_quality_advisor", f"hem_area_{area}"))]
        assert hub.model == "Area Environment Hub"
        assert hub.entry_type == "service"
        assert hub.area_id == area
        assert hub.via_device_id == home.id


def test_endpoints_and_duplicate_roles_share_one_physical_controller(hierarchy):
    h = hierarchy
    h.source("climate.ac")
    h.source("fan.ac")
    assert configured_sources(h.settings, "kitchen") == ("climate.ac", "fan.ac")
    specs = managed_devices(h.hass, "hem", h.settings)
    assert len(specs) == 1
    assert specs[0].source_entities == ("climate.ac", "fan.ac")
    original = deepcopy(vars(h.registry.devices["physical-ac"]))
    async_register_hierarchy(h.hass, h.entry)
    overview = hierarchy_attributes(h.manager, "kitchen")
    assert len(overview["managed_devices"]) == 1
    child = h.registry.devices[overview["managed_devices"][0]["controller_device_id"]]
    assert child.via_device_id == overview["area_hub_device_id"]
    assert child.area_id == "kitchen"
    assert child.configuration_url.endswith("/physical-ac")
    assert vars(h.registry.devices["physical-ac"]) == original
    assert controller_device_info(h.manager, "kitchen", "fan.ac") == (
        controller_device_info(h.manager, "kitchen", "climate.ac"))


def test_idempotence_preserves_existing_hub_and_user_area_override(hierarchy):
    h = hierarchy
    h.source("climate.ac")
    async_register_hierarchy(h.hass, h.entry)
    snapshot = deepcopy(h.manager._device_hierarchy)
    hub = h.registry.devices[snapshot["areas"]["kitchen"]]
    hub.area_id = "user-selected-area"
    child_id = next(iter(snapshot["controllers"].values()))["device_id"]
    h.registry.devices[child_id].area_id = "another-user-area"
    async_register_hierarchy(h.hass, h.entry)
    assert h.manager._device_hierarchy == snapshot
    assert hub.area_id == "user-selected-area"
    assert h.registry.devices[child_id].area_id == "another-user-area"
    assert len(h.registry.keys) == 5


def test_native_entity_rename_uses_registry_identity_not_display_name(hierarchy):
    h = hierarchy
    h.source("climate.ac", device_id=None, entity_area="kitchen", registry_id="permanent")
    first = managed_devices(h.hass, "hem", h.settings)[0]
    h.entities["climate.renamed"] = h.entities.pop("climate.ac")
    h.states["climate.renamed"] = h.states.pop("climate.ac")
    cfg = h.settings["climate_rooms"]["kitchen"]
    cfg.update(climate_entity="climate.renamed", heat_climate_entity="climate.renamed",
               fan_climate_entity="climate.renamed", selected_devices=["climate.renamed"])
    assert managed_devices(h.hass, "hem", h.settings)[0].identifier == first.identifier


def test_wrong_area_deselected_or_own_entity_does_not_get_a_controller(hierarchy):
    h = hierarchy
    h.source("climate.ac", area="bedroom")
    h.source("fan.ac", platform="air_quality_advisor")
    assert managed_devices(h.hass, "hem", h.settings) == ()
    h.registry.devices["physical-ac"].area_id = "kitchen"
    h.settings["climate_rooms"]["kitchen"]["selected_devices"] = []
    assert managed_devices(h.hass, "hem", h.settings) == ()


def test_deleted_area_and_unrelated_room_device_are_not_adopted(hierarchy):
    h = hierarchy
    h.source("climate.ac")
    h.source("fan.unconfigured", device_id="physical-unrelated")
    del h.areas["kitchen"]
    async_register_hierarchy(h.hass, h.entry)
    assert "kitchen" not in h.manager._device_hierarchy["areas"]
    assert h.manager._device_hierarchy["controllers"] == {}
    assert controller_device_info(h.manager, "kitchen", "fan.unconfigured") is None


def test_enabled_pid_only_and_direct_actuator_sources_are_supported(hierarchy):
    h = hierarchy
    h.settings["pid_rooms"] = {"office": {"enabled": True,
                                           "climate_entities": ["climate.radiator"]}}
    h.source("climate.radiator", device_id="radiator", area="office")
    h.settings["climate_rooms"]["bedroom"].update(
        controller="pwm", heat_actuator="switch.heater")
    h.source("switch.heater", device_id="heater", area="bedroom")
    groups = managed_devices(h.hass, "hem", h.settings)
    assert {item.area_id for item in groups} == {"office", "bedroom"}


def test_unavailable_source_keeps_its_logical_device(hierarchy):
    h = hierarchy
    h.source("climate.ac")
    first = managed_devices(h.hass, "hem", h.settings)
    h.states.clear()
    assert managed_devices(h.hass, "hem", h.settings) == first


def test_current_ha_registry_api_receives_actual_parent_device_id(hierarchy, monkeypatch):
    h = hierarchy
    h.source("climate.ac")
    calls = []
    def modern(*, config_entry_id, device_info):
        info = dict(device_info)
        parent_id = info.pop("via_device_id", None)
        if parent_id:
            parent = h.registry.devices[parent_id]
            info["via_device"] = next(iter(parent.identifiers))
        calls.append(dict(device_info))
        return h.registry.async_get_or_create(config_entry_id=config_entry_id, **info)
    monkeypatch.setattr(h.registry, "async_get_or_create_device", modern, raising=False)
    async_register_hierarchy(h.hass, h.entry)
    assert all("via_device" not in call for call in calls)
    assert calls[-1]["via_device_id"] == h.manager._device_hierarchy["areas"]["kitchen"]


def test_device_setting_entities_move_without_changing_unique_ids(hierarchy, monkeypatch):
    import importlib
    import types
    import sys
    from homeassistant import core

    h = hierarchy
    h.source("climate.ac")
    async_register_hierarchy(h.hass, h.entry)
    modules = {
        "homeassistant.components.number": {"NumberEntity": object,
                                              "NumberMode": SimpleNamespace(BOX="box")},
        "homeassistant.components.select": {"SelectEntity": object},
        "homeassistant.helpers.dispatcher": {"async_dispatcher_connect": lambda *a: None},
        "homeassistant.helpers.entity": {"EntityCategory": SimpleNamespace(CONFIG="config")},
        "homeassistant.exceptions": {"HomeAssistantError": RuntimeError},
    }
    for name, attributes in modules.items():
        module = types.ModuleType(name)
        vars(module).update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(core, "callback", lambda fn: fn, raising=False)
    prefix = "custom_components.air_quality_advisor."
    for name in ("number", "select", "device_controls"):
        monkeypatch.delitem(sys.modules, prefix + name, raising=False)
    numbers = importlib.import_module(prefix + "number")
    selectors = importlib.import_module(prefix + "select")
    target = numbers.ConfigNumber(h.manager, "hem", "kitchen", "device_target",
                                   "home_heat_c", (5, 35, .5, "°C"), entity_id="climate.ac")
    policy = selectors.ConfigSelect(h.manager, "hem", "kitchen", "device_policy",
                                    ("always", "room", "home"),
                                    setting_key="presence_requirement", entity_id="climate.ac")
    expected = controller_device_info(h.manager, "kitchen", "climate.ac")
    assert target._attr_device_info == policy._attr_device_info == expected
    assert target._attr_unique_id == "hem_area_kitchen_device_target_climate_ac_home_heat_c"
    assert policy._attr_unique_id == "hem_area_kitchen_device_policy_climate_ac_presence_requirement"
    room = numbers.ConfigNumber(h.manager, "hem", "kitchen", "pid", "kp", (0, 100, 1, None))
    assert room._attr_device_info == {"identifiers": {("air_quality_advisor", "hem_area_kitchen")}}
    home = selectors.ConfigSelect(h.manager, "hem", None, "aqi_scale", ("custom",),
                                  entity_id="sensor.outside_aqi", setting_key="scale")
    assert home._attr_device_info == {"identifiers": {("air_quality_advisor", "hem")}}
