"""Reported beta14 failures: real read-only data shapes and device-first UI."""
from __future__ import annotations

import asyncio
import copy
from types import MappingProxyType, SimpleNamespace
from datetime import datetime, timedelta, timezone

import pytest

from test_discovery import adapter, FakeHass, MockState
from test_equipment_control import runtime_module, home, tick
from test_device_controls import controls, manager
from test_room_setup import build, advance_to_general, defaults
from custom_components.air_quality_advisor.config_data import mutable_copy
from custom_components.air_quality_advisor import equipment_model as m


def test_mutable_copy_handles_nested_readonly_options_without_mutation():
    nested = {"rooms": MappingProxyType({"living": MappingProxyType({"sleep": False, "values": [1, 2]})})}
    frozen = MappingProxyType(nested)
    with pytest.raises(TypeError, match="mappingproxy"):
        copy.deepcopy(frozen)  # Reproduces the reported beta14 failure.
    result = mutable_copy(frozen)
    result["rooms"]["living"]["values"].append(3)
    result["rooms"]["living"]["sleep"] = True
    assert nested["rooms"]["living"]["values"] == [1, 2]
    assert not nested["rooms"]["living"]["sleep"]


@pytest.mark.parametrize("flag", ["sleep_room", "enable_pmv"])
def test_room_switch_saves_real_mappingproxy_options_even_before_inputs(controls, flag):
    impl, _ = controls
    obj, writes, _ = manager()
    obj._active = False
    obj.entry.data["areas"] = ["living"]
    obj.entry.options = MappingProxyType({"environment_rooms": MappingProxyType({
        "living": MappingProxyType({"other": [1, 2]})})})
    before = obj.entry.options
    asyncio.run(impl.update_device_setting(obj, "area_environment", flag, True, area="living"))
    assert obj.entry.options["environment_rooms"]["living"][flag] is True
    assert flag not in before["environment_rooms"]["living"]
    asyncio.run(impl.update_device_setting(obj, "area_environment", flag, False, area="living"))
    assert obj.entry.options["environment_rooms"]["living"][flag] is False
    assert len(writes) == 2


@pytest.mark.parametrize("domain", ["climate", "humidifier", "fan"])
@pytest.mark.parametrize("method", ["automatic", "pid", "manual", "off"])
def test_fresh_device_can_choose_method_without_legacy_configure(runtime_module, domain, method):
    async def run():
        h = home(runtime_module, domain=domain, mode="existing", power=False)
        h.room.update(enabled=False, allow_actuation=False)
        h.dev["auto_control"] = False
        h.manager.entry.options = MappingProxyType({})
        await h.runtime.async_update(h.spec, {"control_mode": method})
        assert m.settings(h.manager, h.spec)["control_mode"] == method
        assert h.dev["auto_control"] is False and h.room["allow_actuation"] is False
        assert not h.hass.services.calls  # Choosing settings does not dispatch hardware.
        if method in ("automatic", "pid", "manual"):
            assert m.permission(h.manager, h.spec, h.cap) == (True, False)
    asyncio.run(run())


def test_selected_method_actually_regulates_native_setpoint_not_only_saves(runtime_module):
    async def run():
        h = home(runtime_module, domain="climate", state="heat", mode="existing", power=False)
        h.room.update(enabled=False, allow_actuation=False)
        h.dev["auto_control"] = False
        h.state.attributes["temperature"] = 18
        await h.runtime.async_update(h.spec, {"control_mode": "automatic"})
        await tick(h, advance=601)
        assert h.hass.services.calls == [("climate", "set_temperature", {"temperature": 18.5}, h.entity)]
        assert not h.room["enabled"] and not h.room["allow_actuation"]
    asyncio.run(run())


def test_binary_pid_uses_device_power_switch_not_an_old_config_menu(runtime_module):
    async def run():
        h = home(runtime_module, domain="fan", mode="existing", speed=False, power=False)
        h.room.update(enabled=False, allow_actuation=False)
        h.dev["auto_control"] = False
        await h.runtime.async_update(h.spec, {"control_mode": "pid", "kp": 20})
        await tick(h, advance=601)
        assert not h.hass.services.calls
        await h.runtime.async_update(h.spec, {"allow_power": True})
        await tick(h, advance=1)
        assert h.hass.services.calls[-1][1] == "turn_on"
        await tick(h, advance=1)
        await h.runtime.async_update(h.spec, {"allow_power": False})
        await tick(h, advance=20)
        assert h.state.state == "on"  # Hardware minimum ON remains in force.
        await tick(h, advance=600)
        assert h.state.state == "off"
    asyncio.run(run())


def test_authorizing_one_device_does_not_enable_other_legacy_outputs(runtime_module):
    async def run():
        h = home(runtime_module, domain="climate", mode="existing", power=False)
        h.room.update(enabled=False, allow_actuation=False, dehumidifier_entity="humidifier.other")
        h.room["selected_devices"].append("humidifier.other")
        h.dev["auto_control"] = False
        await h.runtime.async_update(h.spec, {"control_mode": "automatic"})
        rooms, _ = m.legacy_settings(h.manager)
        assert not rooms["room"]["enabled"] and not rooms["room"]["allow_actuation"]
        from custom_components.air_quality_advisor.device_activation import planning_rooms
        planned = planning_rooms(h.manager)["room"]
        assert planned["enabled"] and planned["controller"] == "environment"
        assert not planned["allow_actuation"]
    asyncio.run(run())


def test_source_changes_revoke_device_authorization_without_blocking_off(runtime_module):
    async def run():
        h = home(runtime_module, domain="climate", mode="existing", power=False)
        await h.runtime.async_update(h.spec, {"control_mode": "automatic"})
        h.dev["temperature_entity"] = "sensor.another"
        assert m.permission(h.manager, h.spec, h.cap) == (False, False)
        await h.runtime.async_update(h.spec, {"control_mode": "off"})
        assert m.settings(h.manager, h.spec)["control_mode"] == "off"
        assert not h.hass.services.calls
    asyncio.run(run())


def test_invalidated_selection_cannot_recover_permission_by_deselect_reselect(runtime_module, monkeypatch, adapter):
    build(monkeypatch, adapter)
    async def run():
        from custom_components.air_quality_advisor.room_sources import store_selection, GROUPS
        h = home(runtime_module, domain="climate", mode="existing", power=False)
        inputs = {key: [] for key in GROUPS}
        inputs.update(windows=["binary_sensor.window"], temperature=["sensor.temp"],
                      humidity=["sensor.rh"], climate_devices=[h.entity])
        store_selection(h.hass, h.manager.entry.data, "room", inputs)
        await h.runtime.async_update(h.spec, {"control_mode": "automatic"})
        assert m.permission(h.manager, h.spec, h.cap)[0]
        store_selection(h.hass, h.manager.entry.data, "room", {**inputs, "climate_devices": []})
        store_selection(h.hass, h.manager.entry.data, "room", inputs)
        assert not m.permission(h.manager, h.spec, h.cap)[0]
        await h.runtime.async_update(h.spec, {"control_mode": "automatic"})
        assert m.permission(h.manager, h.spec, h.cap)[0]
    asyncio.run(run())


def test_activation_rechecks_source_identity_after_storage_await(runtime_module):
    async def run():
        h = home(runtime_module, mode="existing", power=False)
        h.store.hook = lambda: h.hass._entity_devices.update({h.entity: "replacement"})
        with pytest.raises(Exception, match="sources changed"):
            await h.runtime.async_update(h.spec, {"control_mode": "automatic"})
        assert h.manager.entry.options == {}
        assert not h.hass.services.calls
    asyncio.run(run())


def test_template_sources_are_selectable_even_when_current_value_empty_or_unknown(monkeypatch, adapter):
    flow = build(monkeypatch, adapter)
    for entity, value in (("sensor.occupied", "unavailable"), ("sensor.multi_room_presence", "2"),
                          ("sensor.sleeprooms", "")):
        state = MockState(entity, value, name=entity.split(".")[1])
        flow.hass._values[entity] = state
        flow.hass._entity_details[entity] = {"platform": "template"}
    flow.hass.states.get("sensor.multi_room_presence").attributes["rooms"] = ["living", "kitchen"]
    form = advance_to_general(flow)
    expected = {"sensor.occupied", "sensor.multi_room_presence", "sensor.sleeprooms"}
    for key in ("general_occupied_rooms_entity", "general_sleep_rooms_entity"):
        assert expected <= {item["value"] for item in form["data_schema"][key].config.options}
    answer = defaults(form)
    answer.update(general_occupied_rooms_entity="sensor.multi_room_presence", general_occupied_rooms_attribute="rooms",
                  general_sleep_rooms_entity="sensor.sleeprooms", general_sleep_rooms_attribute="__state__")
    form = asyncio.run(flow.async_step_setup_general(answer))
    assert not form["errors"]
    assert {"__state__", "rooms"} <= {v["value"] for v in form["data_schema"]["general_occupied_rooms_attribute"].config.options}
    data = asyncio.run(flow.async_step_setup_general(defaults(form)))["completed"]["data"]
    assert data["occupancy_global"]["occupied_rooms_attribute"] == "rooms"
    assert data["occupancy_global"]["sleep_rooms_attribute"] == ""


@pytest.mark.parametrize("state,expected", [
    ("Kitchen, Bedroom", {"kitchen", "bedroom"}),
    ("['Kitchen', 'Bedroom']", {"kitchen", "bedroom"}),
    ('["Kitchen", "Bedroom"]', {"kitchen", "bedroom"}),
    ("{'kitchen': 2, 'bedroom': 0}", {"kitchen"}),
    ("Kitchen; Bedroom", {"kitchen", "bedroom"}),
    ("Kitchen\nBedroom", {"kitchen", "bedroom"}),
    ("", set()), ("[]", set()), ("none", set()),
    ("unknown", None), ("unavailable", None), ("not a room", None),
    ("[__import__('os').system('bad')]", None),
])
def test_template_room_states_are_parsed_without_executing_or_guessing(adapter, state, expected):
    from custom_components.air_quality_advisor.occupancy_policy import configured_rooms
    hass = FakeHass([MockState("sensor.sleeprooms", state)])
    hass._area_entries = {key: SimpleNamespace(id=key, name=key.title(), aliases=set()) for key in ("kitchen", "bedroom")}
    value, _ = configured_rooms(hass, "sensor.sleeprooms", "", set(hass._area_entries))
    assert value == expected


def test_room_aliases_and_attribute_count_state_resolve_without_room_assignment(adapter):
    from custom_components.air_quality_advisor.occupancy_policy import configured_rooms
    st = MockState("sensor.multi_room_presence", "1")
    st.attributes["rooms"] = ["Κουζίνα"]
    hass = FakeHass([st])
    hass._area_entries = {"kitchen": SimpleNamespace(id="kitchen", name="Küche", aliases={"Κουζίνα"})}
    assert configured_rooms(hass, st.entity_id, "rooms", {"kitchen"})[0] == {"kitchen"}
    st.last_reported = datetime.now(timezone.utc) - timedelta(days=1)
    assert configured_rooms(hass, st.entity_id, "rooms", {"kitchen"})[0] is None


@pytest.mark.parametrize("device,name,value,expected", [
    ("Monitor", "Temperature", "21.5", "Monitor - Temperature (21.5)"),
    ("", "Sleep rooms", "", "Sleep rooms"),
    (None, "Occupied", "0", "Occupied (0)"),
    ("Monitor", "Temperature", "unavailable", "Monitor - Temperature (unavailable)"),
    ("Monitor", "", "", "Monitor"),
])
def test_selector_labels_skip_empty_components_and_use_plain_hyphen(adapter, device, name, value, expected):
    from custom_components.air_quality_advisor.room_sources import label
    st = MockState("sensor.test", value, name=name)
    st.name = name
    hass = FakeHass([st], {st.entity_id: "living"})
    hass._entity_devices[st.entity_id] = "monitor"
    hass._device_details["monitor"] = {"name": device}
    assert label(hass, st.entity_id) == expected


def test_general_entity_selectors_use_the_same_requested_label(monkeypatch, adapter):
    flow = build(monkeypatch, adapter)
    st = MockState("weather.test", "sunny", name="Weather")
    flow.hass._values[st.entity_id] = st
    flow.hass._entity_devices[st.entity_id] = "monitor"
    form = advance_to_general(flow)
    option = next(item for item in form["data_schema"]["weather_entities"].config.options if item["value"] == st.entity_id)
    assert option["label"] == "Room monitor - Weather (sunny)"


def test_native_device_approval_is_detected_by_other_entries(runtime_module):
    async def run():
        from custom_components.air_quality_advisor.climate_entry_ownership import foreign_owner_hold
        h = home(runtime_module, mode="existing", power=False)
        h.room.update(enabled=False, allow_actuation=False)
        h.dev["auto_control"] = False
        await h.runtime.async_update(h.spec, {"control_mode": "automatic"})
        assert foreign_owner_hold(h.hass, "different-entry", h.entity) == "cross_entry_equipment_owner"
    asyncio.run(run())


def test_science_source_selectors_accept_only_this_rooms_selected_sources(controls, adapter):
    impl, _ = controls
    obj, writes, _ = manager()
    obj._active = False
    obj.entry.data.update(areas=["living"], room_sources={"living": {
        "temperature": ["sensor.radiant"], "air_quality": ["sensor.local_air_speed"]}})
    obj.hass._values = {"sensor.local_air_speed": MockState("sensor.local_air_speed", .1, unit="m/s")}
    obj.hass.states = SimpleNamespace(get=obj.hass._values.get)
    async def run():
        await impl.update_device_setting(obj, "area_science", "radiant_temperature_entity", "sensor.radiant", area="living")
        await impl.update_device_setting(obj, "area_science", "air_speed_entity", "sensor.local_air_speed", area="living")
        with pytest.raises(Exception, match="configured inputs"):
            await impl.update_device_setting(obj, "area_science", "radiant_temperature_entity", "sensor.other_room", area="living")
        await impl.update_device_setting(obj, "area_science", "radiant_temperature_entity", "none", area="living")
        assert obj.entry.options["environment_rooms"]["living"]["radiant_temperature_entity"] is None
        assert not obj.entry.options.get("climate_rooms", {}).get("living", {}).get("allow_actuation")
    asyncio.run(run())
