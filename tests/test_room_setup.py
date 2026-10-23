"""Rooms-first public setup and positive-input runtime contracts."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from test_area_config_flow import _make_options
from test_discovery import MockState, adapter


def build(monkeypatch, adapter):
    flow = _make_options(monkeypatch, adapter, two_rooms=True)
    flow.async_abort = lambda **kw: {"abort": kw["reason"]}
    flow.hass._area_entries = {a: SimpleNamespace(id=a, name=a.title())
                               for a in ("living", "kitchen", "empty", "outside")}
    values = [
        MockState("sensor.temp1", 20, device_class="temperature", unit="°C", name="Temperature"),
        MockState("sensor.temp2", 72, device_class="temperature", unit="°F"),
        MockState("sensor.humidity", 55, device_class="humidity", unit="%"),
        MockState("sensor.pressure", 100800, device_class="atmospheric_pressure", unit="Pa"),
        MockState("sensor.wrong_pressure", 12, device_class="pressure", unit="V"),
        MockState("climate.aircon", "off"), MockState("fan.aircon", "off"),
        MockState("humidifier.dryer", "off", device_class="dehumidifier"),
        MockState("cover.window", "closed", device_class="window"),
        MockState("sensor.manager", 22, device_class="temperature", unit="°C"),
    ]
    values[5].attributes.update(hvac_modes=["off", "heat", "cool"])
    for state in values:
        flow.hass._values[state.entity_id] = state
        flow.hass._entity_areas[state.entity_id] = "living"
    flow.hass._entity_devices.update({"sensor.temp1": "monitor", "climate.aircon": "aircon", "fan.aircon": "aircon"})
    flow.hass._device_areas.update({"monitor": "living", "aircon": "living"})
    flow.hass._device_details.update({"monitor": {"name": "Room monitor"}, "aircon": {"name": "Air conditioner"}})
    flow.hass._entity_details["sensor.manager"] = {"platform": "air_quality_advisor"}
    return flow


def defaults(form):
    return {str(key): key.default for key in form["data_schema"]}


def advance_to_general(flow, rooms=("living",)):
    asyncio.run(flow.async_step_init())
    form = asyncio.run(flow.async_step_setup_rooms({"areas": list(rooms)}))
    for room in rooms:
        assert form["step_id"] == "setup_room_sources"
        assert form["description_placeholders"]["area_name"] == room.title()
        form = asyncio.run(flow.async_step_setup_room_sources(defaults(form)))
    assert form["step_id"] == "setup_general"
    return form


def test_exact_public_order_and_all_registered_rooms(monkeypatch, adapter):
    flow = build(monkeypatch, adapter)
    form = asyncio.run(flow.async_step_init())
    assert form["step_id"] == "setup_rooms" and "menu_options" not in form
    assert {v["value"] for v in form["data_schema"]["areas"].config.options} == {"living", "kitchen", "empty", "outside"}
    final = advance_to_general(flow, ("living", "empty", "kitchen"))
    done = asyncio.run(flow.async_step_setup_general(defaults(final)))
    data = done["completed"]["data"]
    assert data["areas"] == ["living", "empty", "kitchen"]
    assert list(data["room_sources"]) == ["living", "empty", "kitchen"]
    assert data["room_sources"]["empty"] == {k: [] for k in flow._values["room_sources"]["empty"]}


def test_six_separate_multiselects_correct_type_and_labels(monkeypatch, adapter):
    flow = build(monkeypatch, adapter)
    asyncio.run(flow.async_step_init())
    form = asyncio.run(flow.async_step_setup_rooms({"areas": ["living"]}))
    assert list(form["data_schema"]) == ["windows", "air_quality", "temperature", "humidity", "pressure", "climate_devices"]
    for value in form["data_schema"].values():
        assert value.config.multiple is True and value.config.custom_value is False
    choices = lambda group: {v["value"]: v["label"] for v in form["data_schema"][group].config.options}
    assert choices("temperature")["sensor.temp1"] == "Room monitor - Temperature (20)"
    assert "sensor.manager" not in choices("temperature")
    assert "cover.window" not in choices("windows")
    assert set(choices("pressure")) == {"sensor.pressure"}
    assert "sensor.kitchen_co2" not in choices("air_quality")
    assert set(choices("climate_devices")) == {"climate.aircon", "fan.aircon", "humidifier.dryer"}


@pytest.mark.parametrize("bad", ["sensor.temp1", [None], [["sensor.temp1"]], ["sensor.kitchen_co2"], ["sensor.manager"]])
def test_reject_malformed_wrong_group_or_foreign_room_sources(monkeypatch, adapter, bad):
    flow = build(monkeypatch, adapter)
    asyncio.run(flow.async_step_init())
    form = asyncio.run(flow.async_step_setup_rooms({"areas": ["living"]}))
    answer = defaults(form); answer["temperature"] = bad
    result = asyncio.run(flow.async_step_setup_room_sources(answer))
    assert result["errors"]["temperature"] == "invalid_room_source"
    assert flow._setup_index == 0
    assert "room_sources" not in flow.config_entry.options


def test_cancellation_keeps_original_nested_data_and_grants(monkeypatch, adapter):
    flow = build(monkeypatch, adapter)
    flow.config_entry.options["climate_rooms"] = {"living": {"selected_devices": ["climate.aircon"],
        "device_settings": {"climate.aircon": {"auto_control": True, "hardware_confirmed": True}}}}
    before = deepcopy((flow.config_entry.data, flow.config_entry.options))
    advance_to_general(flow)
    assert (flow.config_entry.data, flow.config_entry.options) == before


def test_new_device_selection_does_not_authorize_automatic_control(monkeypatch, adapter):
    flow = build(monkeypatch, adapter)
    final = advance_to_general(flow)
    data = asyncio.run(flow.async_step_setup_general(defaults(final)))["completed"]["data"]
    room = data["climate_rooms"]["living"]
    assert set(room["selected_devices"]) == {"climate.aircon", "fan.aircon", "humidifier.dryer"}
    assert all(cfg["auto_control"] is False for cfg in room["device_settings"].values())
    assert room.get("allow_actuation") is not True
    assert data["thresholds"] == {"indoor_co2": 1200}


def test_removed_room_does_not_survive_as_hidden_climate_or_pid_hub(monkeypatch, adapter):
    flow = build(monkeypatch, adapter)
    flow.config_entry.options.update(climate_rooms={"kitchen": {"enabled": True, "allow_actuation": True,
        "selected_devices": ["climate.old"], "device_settings": {"climate.old": {"auto_control": True, "target_c": 21}}}},
        pid_rooms={"kitchen": {"enabled": True, "climate_entities": ["climate.old"], "kp": 5}})
    final = advance_to_general(flow)
    data = asyncio.run(flow.async_step_setup_general(defaults(final)))["completed"]["data"]
    assert data["climate_rooms"]["kitchen"]["selected_devices"] == []
    assert data["climate_rooms"]["kitchen"]["device_settings"]["climate.old"] == {"auto_control": False, "target_c": 21}
    assert data["pid_rooms"]["kitchen"] == {"enabled": False, "climate_entities": [], "kp": 5}


def test_general_last_merges_unrelated_concurrent_device_edits(monkeypatch, adapter):
    flow = build(monkeypatch, adapter)
    final = advance_to_general(flow)
    flow.config_entry.options["thresholds"] = {"indoor_co2": 1350}
    data = asyncio.run(flow.async_step_setup_general(defaults(final)))["completed"]["data"]
    assert data["thresholds"]["indoor_co2"] == 1350


def test_conflicting_concurrent_selection_aborts_without_overwrite(monkeypatch, adapter):
    flow = build(monkeypatch, adapter)
    final = advance_to_general(flow)
    flow.config_entry.options["areas"] = ["empty"]
    assert asyncio.run(flow.async_step_setup_general(defaults(final)))["abort"] == "setup_changed"
    assert flow.config_entry.options["areas"] == ["empty"]


def test_empty_lists_are_authoritative_not_autodiscovery(monkeypatch, adapter):
    flow = build(monkeypatch, adapter)
    from custom_components.air_quality_advisor.room_sources import GROUPS
    explicit = {"living": {g: [] for g in GROUPS}}
    room = adapter.rooms(flow.hass, ["living"], 90, source_selections=explicit)[0]
    assert room.windows == () and room.readings == ()
    flow.hass._values["sensor.new_co2"] = MockState("sensor.new_co2", 1800, device_class="co2", unit="ppm")
    flow.hass._entity_areas["sensor.new_co2"] = "living"
    room = adapter.rooms(flow.hass, ["living"], 90, source_selections=explicit)[0]
    assert room.readings == ()
    legacy = adapter.rooms(flow.hass, ["living"], 90)[0]
    assert legacy.windows and any(r.entity_id == "sensor.new_co2" for r in legacy.readings)


def test_missing_selected_window_remains_unknown(monkeypatch, adapter):
    flow = build(monkeypatch, adapter)
    explicit = {"living": {"windows": ["binary_sensor.living_window", "binary_sensor.missing"]}}
    room = adapter.rooms(flow.hass, ["living"], 90, source_selections=explicit)[0]
    assert {w.entity_id: w.opened for w in room.windows} == {"binary_sensor.living_window": False, "binary_sensor.missing": None}


def test_selected_temperatures_average_after_unit_conversion_and_no_fallback(monkeypatch, adapter):
    flow = build(monkeypatch, adapter)
    from custom_components.air_quality_advisor.environment import _room_temperature
    result = _room_temperature(flow.hass, "living", {}, 90, selected_entities=["sensor.temp1", "sensor.temp2"])
    assert result[0] == pytest.approx((20+(72-32)*5/9)/2)
    assert result[2] == "selected_mean"
    assert _room_temperature(flow.hass, "living", {}, 90, selected_entities=[])[0] is None
    flow.hass.states.get("sensor.temp2").state = "unavailable"
    assert _room_temperature(flow.hass, "living", {}, 90, selected_entities=["sensor.temp1", "sensor.temp2"])[0] is None


def test_pressure_is_normalized_and_retained_as_room_input(monkeypatch, adapter):
    flow = build(monkeypatch, adapter)
    from custom_components.air_quality_advisor.room_sources import numeric, source_overview
    assert numeric(flow.hass, "sensor.pressure", "living", "pressure", 90) == 1008
    manager = SimpleNamespace(hass=flow.hass, settings={"room_sources": {"living": {"pressure": ["sensor.pressure"]}}})
    summary = source_overview(manager, "living")
    assert summary["pressure"][0]["entity_id"] == "sensor.pressure"
    assert summary["pressure_summary"]["value_hpa"] == 1008


def test_selected_source_removal_withdraws_existing_feedback_grants(monkeypatch, adapter):
    flow = build(monkeypatch, adapter)
    from custom_components.air_quality_advisor.room_sources import store_selection, GROUPS
    data = {"climate_rooms": {"living": {"enabled": True, "allow_actuation": True,
        "selected_devices": ["climate.aircon"], "temperature_entity": "sensor.temp1",
        "device_settings": {"climate.aircon": {"auto_control": True, "temperature_entity": "sensor.temp1"}}}},
        "mold_rooms": {"living": {"indoor_temperature_entity": "sensor.temp1", "calibration_factor": 1.5}}}
    inputs = {g: [] for g in GROUPS};inputs.update(climate_devices=["climate.aircon"], temperature=["sensor.temp2"])
    store_selection(flow.hass, data, "living", inputs)
    assert data["climate_rooms"]["living"]["allow_actuation"] is False
    assert data["climate_rooms"]["living"]["device_settings"]["climate.aircon"]["auto_control"] is False
    assert "calibration_factor" not in data["mold_rooms"]["living"]


def test_room_setup_catalogs_have_all_six_groups_and_specific_general_fields():
    import json
    from pathlib import Path
    from custom_components.air_quality_advisor.room_sources import GROUPS
    component = Path(__file__).parents[1] / "custom_components/air_quality_advisor"
    docs = list((component / "translations").glob("*.json"))
    assert len(docs) == 38
    for path in docs:
        doc = json.loads(path.read_text())
        for scope in ("config", "options"):
            steps = doc[scope]["step"]
            assert list(steps["setup_room_sources"]["data"]) == list(GROUPS)
            assert "general_home_trackers" in steps["setup_general"]["data"]
            assert "weather_entities" in steps["setup_general"]["data"]
            assert "notify_entities" in steps["setup_general"]["data"]
            assert len(steps["setup_rooms"]["data_description"]["areas"]) > 35


def test_room_setup_translation_generator_reproduces_every_catalog(tmp_path, monkeypatch):
    import shutil
    from pathlib import Path
    root = Path(__file__).parents[1]
    monkeypatch.syspath_prepend(str(root))
    from apply_room_setup_i18n import apply_room_setup_i18n
    component = root / "custom_components/air_quality_advisor"
    for name in ("strings.json", "compact_locales.json"):
        shutil.copy(component / name, tmp_path / name)
    shutil.copytree(component / "translations", tmp_path / "translations")
    paths = [tmp_path / "strings.json", *sorted((tmp_path / "translations").glob("*.json"))]
    original = {p: p.read_bytes() for p in paths}
    apply_room_setup_i18n(tmp_path)
    assert {p: p.read_bytes() for p in paths} == original
