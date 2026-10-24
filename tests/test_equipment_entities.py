"""Home Assistant platform boundaries for per-device climate controls (mocked)."""
from __future__ import annotations

import asyncio
from enum import IntFlag, StrEnum
import importlib
import sys
import types
from types import SimpleNamespace

import pytest

from test_equipment_control import home, runtime_module
from test_discovery import adapter
from custom_components.environment_manager import equipment_model as model


@pytest.fixture
def platforms(monkeypatch, runtime_module):
    core = sys.modules["homeassistant.core"]
    core.callback = lambda f: f
    const = types.ModuleType("homeassistant.const")
    const.UnitOfTemperature = SimpleNamespace(CELSIUS="°C", FAHRENHEIT="°F")
    monkeypatch.setitem(sys.modules, const.__name__, const)
    class HVACMode(StrEnum):
        OFF="off"
        HEAT="heat"
        COOL="cool"
        HEAT_COOL="heat_cool"
        AUTO="auto"
        DRY="dry"
        FAN_ONLY="fan_only"
    class HVACAction(StrEnum):
        OFF="off"
        IDLE="idle"
        HEATING="heating"
        COOLING="cooling"
        DRYING="drying"
        FAN="fan"
        DEFROSTING="defrosting"
        PREHEATING="preheating"
    class ClimateEntityFeature(IntFlag):
        TARGET_TEMPERATURE=1
        TARGET_TEMPERATURE_RANGE=2
        TARGET_HUMIDITY=4
        FAN_MODE=8
        PRESET_MODE=16
        SWING_MODE=32
        TURN_OFF=128
        TURN_ON=256
        SWING_HORIZONTAL_MODE=512
    class Entity:
        async def async_added_to_hass(self):
            pass
        def async_on_remove(self, callback):
            pass
        def async_write_ha_state(self):
            pass
    entities = types.ModuleType("homeassistant.helpers.entity")
    entities.EntityCategory = SimpleNamespace(CONFIG="config", DIAGNOSTIC="diagnostic")
    monkeypatch.setitem(sys.modules, entities.__name__, entities)
    monkeypatch.setitem(sys.modules, "homeassistant.components", types.ModuleType("homeassistant.components"))
    for domain in ("climate", "number", "select", "switch", "button", "sensor"):
        native = types.ModuleType(f"homeassistant.components.{domain}")
        setattr(native, domain.title()+"Entity", Entity)
        if domain == "climate":
            native.HVACMode, native.HVACAction, native.ClimateEntityFeature = HVACMode, HVACAction, ClimateEntityFeature
        elif domain == "number":
            native.NumberMode = SimpleNamespace(BOX="box")
        elif domain == "sensor":
            native.SensorDeviceClass = SimpleNamespace(ENUM="enum")
        monkeypatch.setitem(sys.modules, native.__name__, native)
    monkeypatch.delitem(sys.modules, "custom_components.environment_manager.equipment_entity", raising=False)
    result = {}
    for domain in ("climate", "number", "select", "switch", "button"):
        name=f"custom_components.environment_manager.{domain}"
        monkeypatch.delitem(sys.modules, name, raising=False)
        result[domain]=importlib.import_module(name)
    name="custom_components.environment_manager.equipment_status"
    monkeypatch.delitem(sys.modules, name, raising=False)
    result["equipment_status"]=importlib.import_module(name)
    return SimpleNamespace(**result, runtime=runtime_module, Features=ClimateEntityFeature)


@pytest.mark.parametrize("domain,expected,has_temp,has_humidity", [
    ("climate", {"off","heat","cool","dry","fan_only"}, True, False),
    ("fan", {"off","fan_only"}, False, False),
    ("humidifier", {"off","dry"}, False, True),
    ("switch", {"off","heat"}, True, False),
])
def test_native_climate_facade_matches_actual_capabilities(platforms, domain, expected, has_temp, has_humidity):
    h=home(platforms.runtime, domain=domain)
    entity=platforms.climate.ManagedClimate(h.manager,h.spec)
    assert set(entity.hvac_modes)==expected
    assert bool(entity.supported_features & platforms.Features.TARGET_TEMPERATURE)==has_temp
    assert bool(entity.supported_features & platforms.Features.TARGET_HUMIDITY)==has_humidity
    assert entity.current_temperature==15
    assert entity.current_humidity==70
    assert entity.hvac_mode=="off" and entity.hvac_action=="off"
    assert entity._attr_device_info["identifiers"]=={("environment_manager",h.spec.identifier)}
    assert entity._attr_native_temperature_unit=="°C"
    assert set(entity.preset_modes)==set(model.PRESETS)


def test_climate_reports_observed_state_not_optimistic_desired_state(platforms):
    async def run():
        h=home(platforms.runtime,domain="climate",mode="existing")
        entity=platforms.climate.ManagedClimate(h.manager,h.spec)
        h.state.last_changed = __import__("datetime").datetime.fromtimestamp(
            h.clock[0] - 900, tz=__import__("datetime").timezone.utc
        )
        await entity.async_set_hvac_mode("heat")
        assert entity.hvac_mode=="off"
        assert entity.extra_state_attributes["requested_hvac_mode"]=="heat"
        assert h.hass.services.calls==[]
        await h.runtime.tick(h.spec)
        # The physical OFF age already satisfies the dwell, so control starts.
        assert entity.hvac_mode=="heat"
    asyncio.run(run())


def test_facade_temperature_and_preset_edit_effective_targets(platforms):
    async def run():
        h=home(platforms.runtime,domain="climate",state="heat",mode="existing",power=False)
        h.manager.entry.data["environment_rooms"]={"room":{"equipment_limits":{
            "temperature_min_limit":16,"temperature_max_limit":30}}}
        entity=platforms.climate.ManagedClimate(h.manager,h.spec)
        await entity.async_set_preset_mode("sleep")
        assert entity.target_temperature==18
        await entity.async_set_temperature(temperature=19, hvac_mode="heat")
        assert entity.target_temperature==19
        await entity.async_set_preset_mode("away")
        assert entity.target_temperature==16  # Room Environment minimum.
        await entity.async_set_preset_mode("sleep")
        assert entity.target_temperature==19
    asyncio.run(run())


def test_facade_refuses_unsupported_modes_temperature_and_native_choices(platforms):
    async def run():
        h=home(platforms.runtime,domain="fan",speed=False)
        entity=platforms.climate.ManagedClimate(h.manager,h.spec)
        for invoke in (lambda: entity.async_set_hvac_mode("heat"),
                       lambda: entity.async_set_temperature(temperature=20),
                       lambda: entity.async_set_humidity(55),
                       lambda: entity.async_set_fan_mode("low")):
            with pytest.raises(Exception):
                await invoke()
        assert h.manager.entry.options=={}
    asyncio.run(run())


def test_facade_native_swing_horizontal_bit_and_range(platforms):
    h=home(platforms.runtime,domain="climate",state="heat_cool")
    h.state.attributes.update(supported_features=2|512|8,hvac_modes=["off","heat_cool"],
                              target_temp_low=18,target_temp_high=27)
    entity=platforms.climate.ManagedClimate(h.manager,h.spec)
    assert entity.supported_features & platforms.Features.SWING_HORIZONTAL_MODE
    assert entity.supported_features & platforms.Features.TARGET_TEMPERATURE_RANGE
    assert not entity.supported_features & platforms.Features.TARGET_TEMPERATURE
    assert entity.target_temperature_low==20 and entity.target_temperature_high==26


def test_quiet_entities_and_control_selection_persist_device_only(platforms):
    async def run():
        h=home(platforms.runtime,state="on",power=False)
        select=platforms.select.EquipmentSelect(h.manager,h.spec,"control_mode")
        quiet=platforms.switch.EquipmentQuietSwitch(h.manager,h.spec,"quiet_sleep")
        gain=platforms.number.EquipmentNumber(h.manager,h.spec,"kp")
        assert set(select.options)==set(model.CONTROL_MODES)
        await quiet.async_turn_on()
        await gain.async_set_native_value(0.08)
        assert quiet.is_on and gain.native_value==.08
        assert h.manager.settings[model.SETTINGS][h.spec.identifier]["quiet_sleep"] is True
        assert h.dev["hardware_confirmed"] is False
        assert h.hass.services.calls==[]
        await select.async_select_option("manual")
        assert select.current_option=="manual"
    asyncio.run(run())


def test_dry_only_facade_has_real_humidity_controller_without_temperature(platforms):
    async def run():
        h=home(platforms.runtime,domain="climate")
        h.state.attributes.update(hvac_modes=["off","dry"],supported_features=0)
        entity=platforms.climate.ManagedClimate(h.manager,h.spec)
        assert not entity.supported_features & platforms.Features.TARGET_TEMPERATURE
        assert entity.supported_features & platforms.Features.TARGET_HUMIDITY
        await entity.async_set_humidity(55)
        saved = h.manager.entry.options["climate_rooms"]["room"]["profiles"]
        assert saved["comfort"]["humidity"] == 55
        target = model.targets(
            h.manager, h.spec, entity._caps, entity.controller_settings,
            model.plan_for(h.manager, h.spec),
        )
        assert target["humidity"] == 55
        assert entity.target_humidity==55
        assert h.hass.services.calls==[]
    asyncio.run(run())


def test_unavailable_or_wrong_room_source_facade_not_available(platforms):
    h=home(platforms.runtime,domain="climate")
    entity=platforms.climate.ManagedClimate(h.manager,h.spec)
    assert entity.available
    h.state.state="unavailable"
    assert not entity.available
    h.state.state="heat"
    h.hass._entity_areas[h.entity]="wrong-room"
    assert not entity.available


@pytest.mark.parametrize("algorithm", ["existing", "manual", "automatic", "pid"])
@pytest.mark.parametrize("method,key,value", [
    ("async_set_preset_mode", "preset", "sleep"),
    ("async_set_swing_mode", "swing_mode", "on"),
    ("async_set_swing_horizontal_mode", "swing_horizontal_mode", "on"),
])
def test_native_choices_without_preset_preserve_selected_algorithm(
    platforms, algorithm, method, key, value
):
    """Manual + None must never enter target-only variable lookup."""
    async def run():
        h = home(platforms.runtime, domain="climate", state="heat",
                 mode=algorithm, power=False)
        entity = platforms.climate.ManagedClimate(h.manager, h.spec)
        assert entity.controller_settings["preset"] == "none"
        await getattr(entity, method)(value)
        settings = entity.controller_settings
        assert settings[key] == value
        assert settings["control_mode"] == (
            "manual" if algorithm == "existing" else algorithm
        )
        assert h.hass.services.calls == []
    asyncio.run(run())



def test_presence_selector_is_per_controller_and_has_only_requested_modes(platforms):
    h=home(platforms.runtime,state="on",power=False)
    entity=platforms.select.EquipmentSelect(h.manager,h.spec,"presence_requirement")
    assert entity.options==["always","occupied","absent"]
    assert entity.current_option=="always"


def test_room_profile_targets_exist_before_automation_and_include_humidity(platforms):
    from custom_components.environment_manager.device_controls import (
        PROFILE_DEFAULTS, PROFILE_NUMBERS, room_profile_number_fields,
    )

    thermal = home(platforms.runtime, domain="climate", state="off", power=False)
    thermal.room["enabled"] = False
    fields = set(room_profile_number_fields(thermal.manager, "room"))
    assert {f"{profile}_heat" for profile in PROFILE_DEFAULTS} <= fields
    assert {f"{profile}_cool" for profile in PROFILE_DEFAULTS} <= fields

    humidity = home(platforms.runtime, domain="humidifier", state="off", power=False)
    humidity.room["enabled"] = False
    hfields = set(room_profile_number_fields(humidity.manager, "room"))
    assert {f"{profile}_humidity" for profile in PROFILE_DEFAULTS} <= hfields

    entity = platforms.number.ConfigNumber(
        humidity.manager, "entry", "room", "climate_profile",
        "away_humidity", PROFILE_NUMBERS["away_humidity"],
    )
    assert entity._attr_device_info["identifiers"] == {
        ("environment_manager", "entry_area_room")
    }

    async def edit():
        await entity.async_set_native_value(45)
    asyncio.run(edit())
    assert entity.native_value == 45
    saved = humidity.manager.entry.options["climate_rooms"]["room"]["profiles"]
    assert saved["away"]["humidity"] == 45
    target = model.targets(
        humidity.manager, humidity.spec, humidity.cap,
        model.settings(humidity.manager, humidity.spec),
        {**humidity.plan, "away": "away"},
    )
    assert target["humidity"] == 45


def test_room_limit_numbers_attach_to_room_environment_device(platforms):
    climate=home(platforms.runtime,domain="climate",state="heat",power=False)
    bounds=model.room_limit_bounds(climate.manager,"room","temperature_min_limit")
    tmin=platforms.number.ConfigNumber(
        climate.manager,"entry","room","room_equipment_limit",
        "temperature_min_limit",bounds)
    assert tmin._attr_device_info["identifiers"] == {
        ("environment_manager","entry_area_room")}
    assert (tmin._attr_native_min_value,tmin._attr_native_max_value)==(5,35)
    assert tmin.native_value==5

    fan=home(platforms.runtime,state="on",power=False)
    fbounds=model.room_limit_bounds(fan.manager,"room","fan_min_percentage")
    fmin=platforms.number.ConfigNumber(
        fan.manager,"entry","room","room_equipment_limit",
        "fan_min_percentage",fbounds)
    assert fmin.native_value==10

    humidity=home(platforms.runtime,domain="humidifier",state="on",power=False)
    hbounds=model.room_limit_bounds(humidity.manager,"room","humidity_max_limit")
    hmax=platforms.number.ConfigNumber(
        humidity.manager,"entry","room","room_equipment_limit",
        "humidity_max_limit",hbounds)
    assert hmax.native_value==80


def test_climate_facade_exposes_room_limits(platforms):
    h=home(platforms.runtime,domain="climate",state="heat",power=False)
    h.manager.entry.data["environment_rooms"]={"room":{"equipment_limits":{
        "temperature_min_limit":18,"temperature_max_limit":24}}}
    entity=platforms.climate.ManagedClimate(h.manager,h.spec)
    assert entity.min_temp==18 and entity.max_temp==24

    humidity=home(platforms.runtime,domain="humidifier",state="on",power=False)
    humidity.manager.entry.data["environment_rooms"]={"room":{"equipment_limits":{
        "humidity_min_limit":35,"humidity_max_limit":60}}}
    hentity=platforms.climate.ManagedClimate(humidity.manager,humidity.spec)
    assert hentity.min_humidity==35 and hentity.max_humidity==60



def test_room_limit_number_persists_under_environment_room(platforms):
    async def run():
        h=home(platforms.runtime,domain="climate",state="heat",power=False)
        bounds=model.room_limit_bounds(h.manager,"room","temperature_min_limit")
        entity=platforms.number.ConfigNumber(
            h.manager,"entry","room","room_equipment_limit",
            "temperature_min_limit",bounds)
        await entity.async_set_native_value(18)
        saved=h.manager.entry.options["environment_rooms"]["room"]["equipment_limits"]
        assert saved["temperature_min_limit"]==18
        assert model.room_limit_values(h.manager,"room")["temperature_min_limit"]==18
    asyncio.run(run())


def test_controller_status_reports_runtime_hold_not_fake_physical_hvac_mode(platforms):
    """A PID-selected controller may be held while the physical unit is OFF."""
    h=home(platforms.runtime,domain="climate",mode="pid",state="off")
    sensor=platforms.equipment_status.ControllerStatusSensor(h.manager,h.spec)
    assert sensor._attr_unique_id == h.spec.identifier + "_control_status"
    assert sensor._attr_device_info["identifiers"] == {
        ("environment_manager",h.spec.identifier)
    }
    assert sensor.native_value == "awaiting_evaluation"
    h.runtime._status(h.spec,"minimum_off_hold")
    assert sensor.native_value == "minimum_off_hold"
    assert h.state.state == "off"
    attrs=sensor.extra_state_attributes
    assert attrs["control_method"] == "pid"
    assert attrs["physical_entity_states"] == {h.entity:"off"}
    assert attrs["controller_owns_power"] is False
    assert attrs["command_pending"] is False
    assert h.hass.services.calls == []

    record=h.runtime._record(h.spec)
    record["paused"]="physical_manual_override"
    h.runtime._status(h.spec,"paused",reason=record["paused"])
    assert sensor.native_value == "paused"
    assert sensor.extra_state_attributes["paused_reason"] == "physical_manual_override"
    assert sensor.extra_state_attributes["status_reason"] == "physical_manual_override"


def test_controller_status_distinguishes_disabled_legacy_and_missing_runtime(platforms):
    h=home(platforms.runtime,domain="humidifier",mode="existing")
    sensor=platforms.equipment_status.ControllerStatusSensor(h.manager,h.spec)
    assert sensor.native_value == "existing"
    h.runtime._active=False
    h.manager.entry.data["equipment_controllers"][h.spec.identifier]["control_mode"]="automatic"
    assert sensor.native_value == "inactive"
    h.runtime._active=True
    h.runtime._ready=False
    assert sensor.native_value == "storage_unavailable"
    h.runtime._ready=True
    h.state.state="unavailable"
    assert sensor.extra_state_attributes["physical_entity_states"][h.entity] == "unavailable"
