"""One public device picker: physical grouping, exact grants and legacy cleanup."""
from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from pathlib import Path

import pytest

from test_area_config_flow import _make_options
from test_discovery import MockState, adapter


def build(monkeypatch, adapter):
    opt = _make_options(monkeypatch, adapter, two_rooms=True)
    for entity_id, device, area in (("climate.ac", "ac", "living"),
                                   ("fan.ac", "ac", "living"),
                                   ("humidifier.dryer", "dryer", "living"),
                                   ("climate.zone2", "ac", "kitchen"),
                                   ("climate.manager", "managed", "living")):
        state = MockState(entity_id, "off")
        if state.domain == "climate":
            state.attributes["hvac_modes"] = ["off", "heat", "cool"]
        if state.domain == "humidifier":
            state.attributes["device_class"] = "dehumidifier"
        opt.hass._values[entity_id] = state
        opt.hass._entity_areas[entity_id] = area
        opt.hass._entity_devices[entity_id] = device
        opt.hass._device_areas[device] = area
        opt.hass._device_details[device] = {"name": "Product " + device}
    opt.hass._entity_details["climate.manager"] = {"platform": "air_quality_advisor"}
    return opt


def start(opt):
    asyncio.run(opt.async_step_init())
    return asyncio.run(opt.async_step_area_devices({"area_devices_area": "living"}))


def selected_default(form):
    return next(field.default for field in form["data_schema"] if field == "selected_devices")


def save(opt, values, **extra):
    return asyncio.run(opt.async_step_select_devices({"selected_devices": values, **extra}))


def test_only_one_public_climate_device_menu(monkeypatch, adapter):
    opt = build(monkeypatch, adapter)
    menu = asyncio.run(opt.async_step_area_settings())["menu_options"]
    assert "area_devices" in menu
    assert "climate" not in menu and "pid" not in menu
    assert "window_sensors" in menu and "environment_room" in menu


def test_physical_product_option_contains_only_this_room_endpoints(monkeypatch, adapter):
    opt = build(monkeypatch, adapter)
    form = start(opt)
    assert set(selected_default(form)) == {"device:ac", "device:dryer"}
    options = form["data_schema"]["selected_devices"].config.options
    ac = next(item for item in options if item["value"] == "device:ac")
    assert "climate.ac" in ac["label"] and "fan.ac" in ac["label"]
    assert "zone2" not in ac["label"]
    assert all("manager" not in item["label"] for item in options)


def test_save_finishes_and_does_not_grant_any_automatic_control(monkeypatch, adapter):
    opt = build(monkeypatch, adapter)
    start(opt)
    done = save(opt, ["device:ac", "device:dryer"])
    data = done["completed"]["data"]
    room = data["climate_rooms"]["living"]
    assert set(room["selected_devices"]) == {"climate.ac", "fan.ac", "humidifier.dryer"}
    assert room.get("enabled") is not True and room.get("allow_actuation") is not True
    assert all(p["auto_control"] is False for p in room["device_settings"].values())
    assert data["thresholds"] == {"indoor_co2": 1200}


def test_commissioning_is_explicit_optional_and_remains_same_path(monkeypatch, adapter):
    opt = build(monkeypatch, adapter)
    start(opt)
    result = save(opt, ["device:ac"], configure_device_sources=True)
    assert result["step_id"] == "device_choice"
    assert set(opt._climate_draft["selected_devices"]) == {"climate.ac", "fan.ac"}
    assert all(p["auto_control"] is False for p in opt._climate_draft["device_settings"].values())


@pytest.mark.parametrize("bad", [["device:managed"], ["device:foreign"], [None], [["device:ac"]], "device:ac"])
def test_rejects_unknown_or_malformed_selection(monkeypatch, adapter, bad):
    opt = build(monkeypatch, adapter)
    start(opt)
    assert save(opt, bad)["errors"]["base"] == "invalid_selected_devices"


def test_removing_device_revokes_legacy_pid_but_preserves_other_room_and_tuning(monkeypatch, adapter):
    opt = build(monkeypatch, adapter)
    opt.config_entry.options["pid_rooms"] = {
        "living": {"enabled": True, "climate_entities": ["climate.ac"], "kp": 12, "ki": .2},
        "kitchen": {"enabled": True, "climate_entities": ["climate.zone2"], "kp": 4},
    }
    opt.config_entry.options["climate_rooms"] = {"living": {
        "enabled": True, "allow_actuation": True, "controller": "device",
        "selected_devices": ["climate.ac", "fan.ac"], "climate_entity": "climate.ac",
        "device_settings": {"climate.ac": {"auto_control": True, "home_heat_c": 21}},
    }}
    start(opt)
    data = save(opt, ["device:dryer"])["completed"]["data"]
    assert data["pid_rooms"]["living"] == {
        "enabled": False, "climate_entities": [], "kp": 12, "ki": .2}
    assert data["pid_rooms"]["kitchen"] == opt.config_entry.options["pid_rooms"]["kitchen"]
    assert data["climate_rooms"]["living"]["device_settings"]["climate.ac"] == {
        "auto_control": False, "home_heat_c": 21}


def test_reselection_cannot_inherit_old_or_other_device_permission(monkeypatch, adapter):
    opt = build(monkeypatch, adapter)
    opt.config_entry.options["climate_rooms"] = {"living": {
        "enabled": True, "allow_actuation": True, "controller": "device",
        "selected_devices": ["climate.ac"], "climate_entity": "climate.ac",
        "device_settings": {
            "climate.ac": {"auto_control": True, "hardware_confirmed": True},
            "humidifier.dryer": {"auto_control": True, "hardware_confirmed": True},
        },
    }}
    start(opt)
    room = save(opt, ["device:ac", "device:dryer"])["completed"]["data"]["climate_rooms"]["living"]
    assert room["device_settings"]["climate.ac"]["auto_control"] is True
    assert room["device_settings"]["fan.ac"]["auto_control"] is False
    assert room["device_settings"]["humidifier.dryer"]["auto_control"] is False
    assert room["device_settings"]["humidifier.dryer"]["hardware_confirmed"] is True


def test_cancelling_optional_setup_cannot_mutate_saved_configuration(monkeypatch, adapter):
    opt = build(monkeypatch, adapter)
    opt.config_entry.options["climate_rooms"] = {"living": {
        "selected_devices": ["climate.ac"], "device_settings": {"climate.ac": {"auto_control": False}}}}
    before = deepcopy(opt.config_entry.options)
    start(opt)
    save(opt, ["device:dryer"], configure_device_sources=True)
    assert opt.config_entry.options == before


def test_unavailable_selected_endpoint_is_not_silently_dropped(monkeypatch, adapter):
    opt = build(monkeypatch, adapter)
    from custom_components.air_quality_advisor.room_device_picker import physical_device_choices
    opt.hass._values.pop("climate.ac")
    opt.hass._values.pop("fan.ac")
    options, mapping = physical_device_choices(opt.hass, "living", ("climate.ac", "fan.ac"))
    assert mapping["device:ac"] == ("climate.ac", "fan.ac")
    assert "device:ac" in {item["value"] for item in options}


def test_clear_selection_finishes_without_any_mandatory_followup(monkeypatch, adapter):
    opt = build(monkeypatch, adapter)
    start(opt)
    room = save(opt, [], configure_device_sources=True)["completed"]["data"]["climate_rooms"]["living"]
    assert room["selected_devices"] == []


def test_all_locales_have_one_device_menu_and_specific_instructions():
    root = Path(__file__).resolve().parents[1] / "custom_components/air_quality_advisor"
    docs = list((root / "translations").glob("*.json"))
    assert len(docs) == 38
    for path in docs:
        steps = json.loads(path.read_text())["options"]["step"]
        menu = steps["area_settings"]["menu_options"]
        assert "area_devices" in menu and "climate" not in menu and "pid" not in menu
        picker = steps["select_devices"]
        assert "{area_name}" in picker["description"]
        assert picker["data"]["configure_device_sources"]
        assert picker["data_description"]["configure_device_sources"]
        if path.stem != "en":
            assert menu["area_devices"] != "Climate devices"
    greek = json.loads((root / "translations/el.json").read_text())["options"]["step"]
    assert greek["area_settings"]["menu_options"]["area_devices"] == "Κλιματικές συσκευές"


def test_preexisting_pid_selection_is_visible_without_another_setup_menu(monkeypatch, adapter):
    opt = build(monkeypatch, adapter)
    opt.config_entry.options["climate_rooms"] = {"living": {"selected_devices": ["humidifier.dryer"]}}
    opt.config_entry.options["pid_rooms"] = {"living": {"enabled": True, "climate_entities": ["climate.ac"], "kp": 8}}
    form = start(opt)
    assert set(selected_default(form)) == {"device:ac", "device:dryer"}
    data = save(opt, selected_default(form))["completed"]["data"]
    assert data["pid_rooms"]["living"] == opt.config_entry.options["pid_rooms"]["living"]
