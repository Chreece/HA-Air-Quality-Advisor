"""Window alternatives require actual device activity and measured outdoor benefit."""
import pytest

from custom_components.enviroment_manager.logic import Reading, Room, Window, Weather
from test_discovery import FakeHass, MockState, adapter


WINDOWS=(Window("binary_sensor.room_window","Room window",False),)
OUTDOOR=(Reading("sensor.out_pm25","PM2.5","pm25",8),)


@pytest.fixture
def model(adapter):
    from custom_components.enviroment_manager import climate_window
    return climate_window


def home(mode="cool",action="cooling"):
    device=MockState("climate.one_mode",mode)
    device.attributes.update({
        "hvac_modes": ["off",mode], "supported_features": 1 if mode!="dry" else 0,
        "hvac_action": action,
    })
    contact=MockState("binary_sensor.room_window","off",device_class="window")
    room=Room("room","Room",WINDOWS,())
    h=FakeHass([device,contact],{device.entity_id:"room",contact.entity_id:"room"})
    return h,room


def plan(temperature=27,target=20):
    return {"temperature_c":temperature,"temperature_target_c":target,
            "away":"home","occupancy":"occupied",
            "humidity_management":{"status":"advisory","action":"dry",
                                   "measured_rh":75}}


def test_cooling_only_device_can_offer_measured_free_cooling(model):
    h,room=home()
    result=model.window_substitution(
        h,room,{"enabled":True,"climate_entity":"climate.one_mode"},
        plan(temperature=28),
        {},(Weather("weather.home","sunny",20,45),),OUTDOOR,
        outside_safe=True)
    assert result["status"]=="opportunity"
    assert result["effect"]=="cool"
    assert result["evidence"]["temperature_difference_c"]==8
    assert model.window_reason(result).code=="climate_window_cool"
    assert result["automatic_control"] is False


def test_heating_only_needs_outdoor_air_to_reach_target(model):
    h,room=home("heat","heating")
    args=dict(hass=h,room=room,
              settings={"enabled":True,"climate_entity":"climate.one_mode"},
              plan=plan(temperature=18,target=20),science={},
              outdoor=OUTDOOR,outside_safe=True)
    yes=model.window_substitution(weather=(Weather("weather.home","sunny",21,40),),**args)
    assert yes["status"]=="opportunity"
    assert yes["effect"]=="heat"
    no=model.window_substitution(weather=(Weather("weather.home","sunny",19,40),),**args)
    assert no["status"]=="insufficient_free_warming"


def test_dry_only_without_fan_only_is_recognized(model):
    from custom_components.enviroment_manager.building_physics import moisture_potential
    h,room=home("dry","drying")
    condition=moisture_potential(23,75,14,45)
    assert condition["status"]=="drying"
    result=model.window_substitution(
        h,room,{"enabled":True,"dry_climate_entity":"climate.one_mode",
                 "humidity_high_rh":60},
        plan(temperature=23),{"moisture":condition},
        (Weather("weather.home","sunny",14,45),),OUTDOOR,
        outside_safe=True)
    assert result["status"]=="opportunity"
    assert result["effect"]=="dry"
    assert result["evidence"]["humidity_ratio_advantage_g_kg"]>=1.5
    assert model.window_reason(result).code=="climate_window_dry"


def test_dedicated_dehumidifier_window_airing_is_measured(model):
    from custom_components.enviroment_manager.building_physics import moisture_potential
    dryer=MockState("humidifier.dehum","on",device_class="dehumidifier")
    contact=MockState("binary_sensor.room_window","off",device_class="window")
    h=FakeHass([dryer,contact],{dryer.entity_id:"room",contact.entity_id:"room"})
    room=Room("room","Room",WINDOWS,())
    result=model.window_substitution(
        h,room,{"enabled":True,"dehumidifier_entity":dryer.entity_id},
        plan(temperature=23),{"moisture":moisture_potential(23,75,14,45)},
        (Weather("weather.home","sunny",14,45),),OUTDOOR,
        outside_safe=True)
    assert result["status"]=="opportunity" and result["effect"]=="dry"


def test_outdoor_hazards_missing_measurements_and_open_window_fail_closed(model):
    h,room=home()
    cfg={"enabled":True,"climate_entity":"climate.one_mode"}
    args=dict(hass=h,room=room,settings=cfg,plan=plan(28),science={},
              weather=(Weather("weather.home","sunny",18,40),),
              outdoor=OUTDOOR,outside_safe=True)
    assert model.window_substitution(**{**args,"outside_safe":False})["status"]=="outside_conditions_not_safe"
    assert model.window_substitution(**{**args,"outdoor":()})["status"]=="outdoor_pollutants_not_verified"
    assert model.window_substitution(**{**args,"outdoor":(Reading("e","e","pm25",None),)})["status"]=="outdoor_pollutants_not_verified"
    assert model.window_substitution(**{**args,"weather":()})["status"]=="weather_source_missing_or_ambiguous"
    assert model.window_substitution(**{**args,"room":Room("room","Room",(),())})["status"]=="window_contact_not_configured"
    assert model.window_substitution(**{**args,"room":Room("room","Room",(Window("id","Window",None),),())})["status"]=="window_state_unknown"
    assert model.window_substitution(**{**args,"room":Room("room","Room",(Window("id","Window",True),),())})["status"]=="window_already_open"


def test_idle_device_and_unverified_dry_action_do_not_raise_efficiency_message(model):
    h,room=home()
    h.states.get("climate.one_mode").attributes["hvac_action"]="idle"
    cfg={"enabled":True,"climate_entity":"climate.one_mode"}
    args=dict(hass=h,room=room,settings=cfg,plan=plan(28),science={},
              weather=(Weather("weather.home","sunny",20,40),),
              outdoor=OUTDOOR,outside_safe=True)
    assert model.window_substitution(**args)["status"]=="no_active_verified_equipment"
    dry,_=home("dry",None)
    args["hass"]=dry
    args["settings"]={"enabled":True,"dry_climate_entity":"climate.one_mode"}
    assert model.window_substitution(**args)["status"]=="no_active_verified_equipment"


def test_not_present_and_simultaneous_competing_needs_do_not_advise(model):
    h,room=home()
    other=MockState("climate.heater","heat")
    other.attributes.update({"hvac_modes":["heat"],"supported_features":1,
                             "hvac_action":"heating"})
    h._values[other.entity_id]=other
    h._entity_areas[other.entity_id]="room"
    config={"enabled":True,"climate_entity":"climate.one_mode",
            "heat_climate_entity":"climate.heater"}
    args=dict(hass=h,room=room,settings=config,plan=plan(28),science={},
              weather=(Weather("weather.home","sunny",20,40),),
              outdoor=OUTDOOR,outside_safe=True)
    assert model.window_substitution(**args)["status"]=="multiple_mechanical_needs"
    args["plan"]={**plan(28),"away":"away"}
    assert model.window_substitution(**args)["status"]=="nobody_available_to_open_window"


def test_drying_not_equivalent_when_outdoor_moisture_inadequate_or_heating_loss_large(model):
    from custom_components.enviroment_manager.building_physics import moisture_potential
    h,room=home("dry","drying")
    cfg={"enabled":True,"dry_climate_entity":"climate.one_mode"}
    args=dict(hass=h,room=room,settings=cfg,plan=plan(temperature=23),
              weather=(Weather("weather.home","sunny",22,75),),
              outdoor=OUTDOOR,outside_safe=True)
    result=model.window_substitution(
        **{**args,"science":{"moisture":moisture_potential(23,70,22,75)}})
    assert result["status"] in ("drying_effect_insufficient","measured_outdoor_drying_not_verified")
    cold=model.window_substitution(
        **{**args,"weather":(Weather("weather.home","sunny",1,45),),
           "science":{"moisture":moisture_potential(23,75,1,45)}})
    assert cold["status"]=="excessive_heat_loss_for_drying"
    missing={**args,"plan":{**plan(23),"humidity_management":{"status":"insufficient_data"}}}
    assert model.window_substitution(
        **{**missing,"science":{"moisture":moisture_potential(23,75,14,45)}}
    )["status"]=="no_verified_drying_demand"
