"""Real options-flow bug regressions for menus and per-device permissions.

The tests use Home Assistant boundary doubles; no physical devices are called.
"""
from __future__ import annotations

import asyncio

from test_area_config_flow import _make_options
from test_discovery import MockState, adapter


def _add(opt, *states):
    for state in states:
        opt.hass._values[state.entity_id] = state
        opt.hass._entity_areas[state.entity_id] = "living"


def _start_device(opt, selected, chosen):
    asyncio.run(opt.async_step_init())
    assert asyncio.run(opt.async_step_area_devices({
        "area_devices_area": "living",
    }))["step_id"] == "select_devices"
    assert asyncio.run(opt.async_step_select_devices({
        "selected_devices": selected, "configure_device_sources": True,
    }))["step_id"] == "device_choice"
    assert asyncio.run(opt.async_step_device_choice({
        "device_choice": chosen,
    }))["step_id"] == "device_menu"


def test_unselecting_previous_auto_thermostat_revokes_live_role(monkeypatch, adapter):
    opt = _make_options(monkeypatch, adapter)
    heat = MockState("climate.living_heat", "heat")
    heat.attributes.update({"hvac_modes": ["off", "heat"], "supported_features": 1})
    fan = MockState("fan.living_filter", "off")
    _add(opt, heat, fan)
    opt.config_entry.options["climate_rooms"] = {"living": {
        "enabled": True, "allow_actuation": True, "controller": "device",
        "climate_entity": heat.entity_id, "selected_devices": [heat.entity_id, fan.entity_id],
        "device_settings": {
            heat.entity_id: {"auto_control": True},
            fan.entity_id: {"auto_control": False},
        },
    }}
    asyncio.run(opt.async_step_init())
    asyncio.run(opt.async_step_area_devices({"area_devices_area": "living"}))
    asyncio.run(opt.async_step_select_devices({"selected_devices": [fan.entity_id]}))
    result = asyncio.run(opt.async_step_device_done())
    data = result["completed"]["data"]["climate_rooms"]["living"]
    assert data["selected_devices"] == [fan.entity_id]
    assert data["device_settings"][heat.entity_id]["auto_control"] is False
    assert "climate_entity" not in data
    assert data["controller"] == "environment"
    assert data["allow_actuation"] is False


def test_disabling_selected_thermostat_retires_previous_permission(monkeypatch, adapter):
    opt = _make_options(monkeypatch, adapter)
    heat = MockState("climate.living_heat", "heat")
    heat.attributes.update({"hvac_modes": ["off", "heat"], "supported_features": 1})
    _add(opt, heat)
    opt.config_entry.options["climate_rooms"] = {"living": {
        "enabled": True, "allow_actuation": True, "controller": "device",
        "climate_entity": heat.entity_id, "selected_devices": [heat.entity_id],
        "temperature_entity": "sensor.living_t",
        "device_settings": {heat.entity_id: {"auto_control": True}},
    }}
    _start_device(opt, [heat.entity_id], heat.entity_id)
    result = asyncio.run(opt.async_step_device_settings({"device_auto_control": False}))
    cfg = result["completed"]["data"]["climate_rooms"]["living"]
    assert cfg["device_settings"][heat.entity_id]["auto_control"] is False
    assert "climate_entity" not in cfg
    assert cfg["allow_actuation"] is False


def test_fan_enable_does_not_arm_previous_advisory_thermostat(monkeypatch, adapter):
    opt = _make_options(monkeypatch, adapter)
    heat = MockState("climate.living_heat", "heat")
    heat.attributes.update({"hvac_modes": ["off", "heat"], "supported_features": 1})
    fan = MockState("fan.living_extract", "off")
    fan.attributes["supported_features"] = 1
    _add(opt, heat, fan)
    # A deliberately excluded CO2 source must not be used to drive equipment.
    # This particular scenario explicitly restores the verified NDIR input.
    opt.config_entry.options["excluded_indoor_entities"] = {"living": []}
    opt.config_entry.options["climate_rooms"] = {"living": {
        "enabled": True, "controller": "device", "allow_actuation": False,
        "climate_entity": heat.entity_id,
    }}
    _start_device(opt, [heat.entity_id, fan.entity_id], fan.entity_id)
    result = asyncio.run(opt.async_step_device_settings({
        "device_auto_control": True,
        "device_method": "speed",
        "device_fan_purpose": "extraction",
        "device_co2_entity": "sensor.living_co2",
        "device_sensor_verified": True,
    }))
    cfg = result["completed"]["data"]["climate_rooms"]["living"]
    assert cfg["controller"] == "environment"
    assert cfg["auto_switch_hvac"] is False
    assert cfg["fan_speed_auto"] is True
    assert cfg["allow_actuation"] is True
    assert cfg["climate_entity"] == heat.entity_id  # retained for observation


def test_filtration_speed_target_uses_actual_driver_setting_name(monkeypatch, adapter):
    opt = _make_options(monkeypatch, adapter)
    fan = MockState("fan.living_filter", "off")
    fan.attributes["supported_features"] = 1
    pm = MockState("sensor.living_pm25", 25, device_class="pm25", unit="µg/m³")
    _add(opt, fan, pm)
    _start_device(opt, [fan.entity_id], fan.entity_id)
    result = asyncio.run(opt.async_step_device_settings({
        "device_auto_control": True, "device_method": "speed",
        "device_fan_purpose": "filtration",
        "device_pm25_entity": pm.entity_id, "device_sensor_verified": True,
        "device_fan_speed_percent": 45,
    }))
    cfg = result["completed"]["data"]["climate_rooms"]["living"]
    assert cfg["purifier_fan_entity"] == fan.entity_id
    assert cfg["purifier_speed_percent"] == 45
    assert "filtration_speed_percent" not in cfg
    assert cfg["fan_speed_auto"] is True


def test_heat_only_thermostat_is_not_configured_as_dual_auto(monkeypatch, adapter):
    opt = _make_options(monkeypatch, adapter)
    climate = MockState("climate.living_heat", "heat")
    climate.attributes.update({"hvac_modes": ["off", "heat"], "supported_features": 1})
    t = MockState("sensor.living_temperature", 20, device_class="temperature", unit="°C")
    _add(opt, climate, t)
    _start_device(opt, [climate.entity_id], climate.entity_id)
    result = asyncio.run(opt.async_step_device_settings({
        "device_auto_control": True, "device_method": "setpoint",
        "device_temperature_entity": t.entity_id,
    }))
    cfg = result["completed"]["data"]["climate_rooms"]["living"]
    assert cfg["mode"] == "heat"
    assert cfg["auto_switch_hvac"] is False


def test_auto_target_rejects_climate_without_target_feature(monkeypatch, adapter):
    opt = _make_options(monkeypatch, adapter)
    climate = MockState("climate.living_heat", "heat")
    climate.attributes.update({"hvac_modes": ["off", "heat"], "supported_features": 0})
    temp = MockState("sensor.living_temperature", 20, device_class="temperature", unit="°C")
    _add(opt, climate, temp)
    _start_device(opt, [climate.entity_id], climate.entity_id)
    form = asyncio.run(opt.async_step_device_settings({
        "device_auto_control": True, "device_method": "setpoint",
        "device_temperature_entity": temp.entity_id,
    }))
    assert form["errors"]["base"] == "device_method_invalid"


def test_fan_without_speed_capability_cannot_be_armed_for_speed(monkeypatch, adapter):
    opt = _make_options(monkeypatch, adapter)
    fan = MockState("fan.living_filter", "off")
    fan.attributes["supported_features"] = 0
    pm = MockState("sensor.living_pm25", 35, device_class="pm25", unit="µg/m³")
    _add(opt, fan, pm)
    _start_device(opt, [fan.entity_id], fan.entity_id)
    result = asyncio.run(opt.async_step_device_settings({
        "device_auto_control": True, "device_method": "speed",
        "device_fan_purpose": "filtration",
        "device_pm25_entity": pm.entity_id,
        "device_sensor_verified": True,
    }))
    assert result["errors"]["base"] == "device_method_invalid"


def test_humidifier_with_unknown_setpoint_resolution_is_not_armed(monkeypatch, adapter):
    opt = _make_options(monkeypatch, adapter)
    device = MockState("humidifier.living_humidifier", "on", device_class="humidifier")
    rh = MockState("sensor.living_humidity", 50, device_class="humidity", unit="%")
    _add(opt, device, rh)
    _start_device(opt, [device.entity_id], device.entity_id)
    result = asyncio.run(opt.async_step_device_settings({
        "device_auto_control": True, "device_method": "setpoint",
        "device_humidity_entity": rh.entity_id,
    }))
    assert result["errors"]["base"] == "device_method_invalid"


def test_occupied_room_source_can_be_cleared_explicitly(monkeypatch, adapter):
    opt = _make_options(monkeypatch, adapter)
    src = MockState("sensor.occupied_rooms", '["living"]')
    _add(opt, src)
    opt.config_entry.options["occupancy_global"] = {
        "occupied_rooms_entity": src.entity_id,
        "occupied_rooms_attribute": "",
        "room_occupancy_sensors": [], "home_trackers": [],
    }
    asyncio.run(opt.async_step_init())
    form = asyncio.run(opt.async_step_general_settings())
    ent = next(v for k, v in form["data_schema"].items()
               if k == "general_occupied_rooms_entity")
    assert "none" in [row["value"] for row in ent.config.options]
    finished = asyncio.run(opt.async_step_general_settings({
        "general_occupied_rooms_entity": "none",
    }))
    cfg = finished["completed"]["data"]["occupancy_global"]
    assert cfg["occupied_rooms_entity"] is None
    assert cfg["occupied_rooms_attribute"] == ""


def test_aqi_source_change_refreshes_its_saved_scale_first(monkeypatch, adapter):
    opt = _make_options(monkeypatch, adapter)
    a = MockState("sensor.outdoor_aqi", 48, device_class="aqi")
    b = MockState("sensor.outdoor_air_quality_index", 3, device_class="aqi")
    _add(opt, a, b)
    opt.config_entry.options["outdoor_sensors"] = [a.entity_id, b.entity_id]
    opt.config_entry.options["environment_global"] = {
        "aqi_scales": {
            a.entity_id: {"scale": "us_epa"},
            b.entity_id: {"scale": "eea_category"},
        }
    }
    asyncio.run(opt.async_step_init())
    form = asyncio.run(opt.async_step_outside_aqi())
    assert form["step_id"] == "outside_aqi"
    refreshed = asyncio.run(opt.async_step_outside_aqi({
        "outside_aqi_entity": b.entity_id,
        "outside_aqi_scale": "custom",
        "outside_aqi_limit": 400,
    }))
    assert refreshed["step_id"] == "outside_aqi"
    key = next(k for k in refreshed["data_schema"]
               if k == "outside_aqi_scale")
    assert key.default == "eea_category"
    finished = asyncio.run(opt.async_step_outside_aqi({
        "outside_aqi_entity": b.entity_id,
        "outside_aqi_scale": "eea_category",
    }))
    saved = finished["completed"]["data"]["environment_global"]["aqi_scales"]
    assert saved[a.entity_id]["scale"] == "us_epa"
    assert saved[b.entity_id]["scale"] == "eea_category"


def test_excluded_air_sensor_is_not_offered_or_accepted_for_actuation(monkeypatch, adapter):
    opt = _make_options(monkeypatch, adapter)
    fan = MockState("fan.living_extract", "off")
    fan.attributes["supported_features"] = 1
    _add(opt, fan)
    _start_device(opt, [fan.entity_id], fan.entity_id)
    form = asyncio.run(opt.async_step_device_settings())
    co2_selector = next(value for key, value in form["data_schema"].items()
                        if key == "device_co2_entity")
    assert "sensor.living_co2" not in [
        item["value"] for item in co2_selector.config.options
    ]
    outcome = asyncio.run(opt.async_step_device_settings({
        "device_auto_control": True,
        "device_method": "speed",
        "device_fan_purpose": "extraction",
        "device_co2_entity": "sensor.living_co2",
        "device_sensor_verified": True,
    }))
    assert outcome["errors"]["base"] == "device_air_sensor_required"


def test_device_power_timing_enforces_actual_fan_driver_limits(monkeypatch, adapter):
    opt = _make_options(monkeypatch, adapter)
    fan = MockState("fan.living_filter", "off")
    pm = MockState("sensor.living_pm25", 18, device_class="pm25", unit="µg/m³")
    _add(opt, fan, pm)
    _start_device(opt, [fan.entity_id], fan.entity_id)
    form = asyncio.run(opt.async_step_device_settings({
        "device_auto_control": True, "device_method": "power",
        "device_hardware_confirmed": True, "device_fan_purpose": "filtration",
        "device_pm25_entity": pm.entity_id, "device_sensor_verified": True,
        "device_min_on_s": 60, "device_min_off_s": 120, "device_max_on_s": 7200,
    }))
    assert form["errors"]["base"] == "device_runtime_invalid"


def test_device_power_timing_enforces_real_humidifier_dwell(monkeypatch, adapter):
    opt = _make_options(monkeypatch, adapter)
    device = MockState("humidifier.living_unit", "off", device_class="humidifier")
    rh = MockState("sensor.living_humidity", 46, device_class="humidity", unit="%")
    _add(opt, device, rh)
    _start_device(opt, [device.entity_id], device.entity_id)
    form = asyncio.run(opt.async_step_device_settings({
        "device_auto_control": True, "device_method": "power",
        "device_hardware_confirmed": True, "device_humidity_entity": rh.entity_id,
        "device_min_on_s": 600, "device_min_off_s": 120, "device_max_on_s": 7200,
    }))
    assert form["errors"]["base"] == "device_runtime_invalid"


def test_switching_fan_purpose_removes_its_old_conflicting_role(monkeypatch, adapter):
    opt = _make_options(monkeypatch, adapter)
    fan = MockState("fan.living_unit", "on")
    fan.attributes["supported_features"] = 1
    pm = MockState("sensor.living_pm25", 38, device_class="pm25", unit="µg/m³")
    _add(opt, fan, pm)
    opt.config_entry.options["climate_rooms"] = {"living": {
        "enabled": True, "allow_actuation": True, "controller": "environment",
        "selected_devices": [fan.entity_id],
        "extraction_fan_entity": fan.entity_id, "fan_speed_auto": True,
        "device_settings": {fan.entity_id: {
            "auto_control": True, "method": "speed", "fan_purpose": "extraction",
        }},
    }}
    _start_device(opt, [fan.entity_id], fan.entity_id)
    done = asyncio.run(opt.async_step_device_settings({
        "device_auto_control": True, "device_method": "speed",
        "device_fan_purpose": "filtration",
        "device_pm25_entity": pm.entity_id,
        "device_sensor_verified": True,
    }))
    settings = done["completed"]["data"]["climate_rooms"]["living"]
    assert settings["purifier_fan_entity"] == fan.entity_id
    assert "extraction_fan_entity" not in settings
    assert settings["fan_speed_auto"] is True


def test_replacing_primary_climate_does_not_leave_stale_secondary_role(monkeypatch, adapter):
    opt = _make_options(monkeypatch, adapter)
    old = MockState("climate.old_heat", "heat")
    new = MockState("climate.new_heat", "heat")
    temp = MockState("sensor.living_temperature", 20, device_class="temperature", unit="°C")
    for st in (old, new):
        st.attributes.update({"hvac_modes": ["off", "heat"], "supported_features": 1})
    _add(opt, old, new, temp)
    opt.config_entry.options["climate_rooms"] = {"living": {
        "enabled": True, "allow_actuation": True, "controller": "device",
        "climate_entity": old.entity_id, "selected_devices": [old.entity_id],
        "device_settings": {old.entity_id: {"auto_control": True}},
    }}
    _start_device(opt, [new.entity_id], new.entity_id)
    done = asyncio.run(opt.async_step_device_settings({
        "device_auto_control": True, "device_method": "setpoint",
        "device_temperature_entity": temp.entity_id,
    }))
    settings = done["completed"]["data"]["climate_rooms"]["living"]
    assert settings["climate_entity"] == new.entity_id
    assert "heat_climate_entity" not in settings
    assert settings["controller"] == "device"
    assert settings["device_settings"][old.entity_id]["auto_control"] is False


def test_native_dry_only_is_explicitly_commissioned_without_fake_temperature(monkeypatch, adapter):
    opt = _make_options(monkeypatch, adapter)
    dry = MockState("climate.living_dry", "off")
    dry.attributes.update(hvac_modes=["off", "dry"], supported_features=0)
    rh = MockState("sensor.living_relative", 65, device_class="humidity", unit="%")
    _add(opt, dry, rh)
    _start_device(opt, [dry.entity_id], dry.entity_id)
    form = asyncio.run(opt.async_step_device_settings())
    assert "device_humidity_entity" in form["data_schema"]
    assert "device_temperature_entity" not in form["data_schema"]
    result = asyncio.run(opt.async_step_device_settings({
        "device_auto_control": True, "device_method": "native",
        "device_hardware_confirmed": True, "device_humidity_entity": rh.entity_id,
    }))
    cfg = result["completed"]["data"]["climate_rooms"]["living"]
    assert cfg["dry_climate_entity"] == dry.entity_id
    assert cfg["controller"] == "environment"
    assert cfg.get("auto_switch_hvac") is False
    assert cfg.get("dry_fan_mode_auto") is not True
    assert cfg["device_settings"][dry.entity_id]["hardware_confirmed"] is True


def test_native_air_only_requires_off_capability_hardware_and_verified_feedback(monkeypatch, adapter):
    for missing in ("off", "hardware", "sensor"):
        opt = _make_options(monkeypatch, adapter)
        fan = MockState("climate.living_native_fan", "off")
        fan.attributes.update(hvac_modes=["fan_only"] if missing == "off" else ["off", "fan_only"], supported_features=0)
        _add(opt, fan)
        opt.config_entry.options["excluded_indoor_entities"] = {"living": []}
        _start_device(opt, [fan.entity_id], fan.entity_id)
        result = asyncio.run(opt.async_step_device_settings({
            "device_auto_control": True, "device_method": "native",
            "device_hardware_confirmed": missing != "hardware",
            "device_fan_purpose": "extraction", "device_co2_entity": "sensor.living_co2",
            "device_sensor_verified": missing != "sensor",
        }))
        assert result["errors"], missing


def test_native_climate_cycle_commissioning_minimum_is_not_a_tuning_preference(monkeypatch, adapter):
    opt = _make_options(monkeypatch, adapter)
    heat = MockState("climate.living_binary", "off")
    heat.attributes.update(hvac_modes=["off", "heat"], supported_features=0)
    temp = MockState("sensor.living_t", 20, device_class="temperature", unit="°C")
    _add(opt, heat, temp)
    _start_device(opt, [heat.entity_id], heat.entity_id)
    result = asyncio.run(opt.async_step_device_settings({
        "device_auto_control": True, "device_method": "native",
        "device_hardware_confirmed": True, "device_temperature_entity": "sensor.living_t",
        "device_min_on_s": 5,
    }))
    assert result["errors"]["base"] == "device_runtime_invalid"


def test_manager_climate_entities_are_never_offered_as_native_targets(monkeypatch, adapter):
    from custom_components.air_quality_advisor.compact_options import _device_choices
    from custom_components.air_quality_advisor.climate_entry_ownership import foreign_owner_hold
    opt = _make_options(monkeypatch, adapter)
    proxy = MockState("climate.manager_controller", "heat")
    proxy.attributes.update(hvac_modes=["off", "heat"], supported_features=1)
    native = MockState("climate.native", "heat")
    native.attributes.update(hvac_modes=["off", "heat"], supported_features=1)
    _add(opt, proxy, native)
    opt.hass._entity_details[proxy.entity_id] = {"platform": "air_quality_advisor"}
    ids = {v["value"] for v in _device_choices(opt.hass, "living")}
    assert native.entity_id in ids and proxy.entity_id not in ids
    opt._pid_area = "living"
    assert proxy.entity_id not in {v["value"] for v in opt._pid_climate_choices()}
    assert foreign_owner_hold(opt.hass, "entry", proxy.entity_id) == "managed_entity_cannot_be_physical_target"


def test_removing_unrelated_fan_preserves_commissioned_native_dry_controller(monkeypatch, adapter):
    _make_options(monkeypatch, adapter)
    from custom_components.air_quality_advisor.compact_options import _reconcile_device_selection
    previous = {
        "enabled": True, "allow_actuation": True, "controller": "environment",
        "selected_devices": ["climate.dry", "fan.filter"],
        "purifier_fan_entity": "fan.filter", "fan_power_auto": True,
        "device_settings": {
            "climate.dry": {"auto_control": True, "method": "native", "hardware_confirmed": True},
            "fan.filter": {"auto_control": True, "method": "power", "hardware_confirmed": True},
        },
    }
    result = _reconcile_device_selection(previous, {**previous, "selected_devices": ["climate.dry"]})
    assert result["allow_actuation"] is True
    assert result["device_settings"]["climate.dry"]["auto_control"] is True
    assert result["device_settings"]["fan.filter"]["auto_control"] is False
    assert result["fan_power_auto"] is False
    assert "purifier_fan_entity" not in result
    # This helper may retain a grant, but it must never invent one.
    disabled = _reconcile_device_selection(previous, {**previous, "allow_actuation": False,
        "selected_devices": ["climate.dry"]})
    assert disabled["allow_actuation"] is False
