"""HA area occupancy and tracking inputs, with conservative sensor handling."""
from custom_components.air_quality_advisor.logic import Room,Window
from test_discovery import FakeHass,MockState,adapter


def home(*,room_occupied=False,second_occupied=False,away=False,unknown=False):
    temp=MockState("sensor.kitchen_temperature",19,device_class="temperature",unit="°C")
    first=MockState("binary_sensor.kitchen_occupancy","on" if room_occupied else "off",device_class="occupancy")
    second=MockState("binary_sensor.kitchen_presence","on" if second_occupied else "off",device_class="presence")
    person=MockState("person.resident","not_home" if away else "home")
    climate=MockState("climate.kitchen","heat")
    climate.attributes.update({"hvac_modes":["off","heat","cool"],"supported_features":1})
    states=[temp,first,second,person,climate]
    if unknown:second.state="unknown"
    areas={s.entity_id:"kitchen" for s in states if s.domain!="person"}
    return FakeHass(states,areas)


def test_auto_discovers_all_room_presence_and_any_on_wins(adapter):
    from custom_components.air_quality_advisor.climate_rooms import gather
    hass=home(room_occupied=False,second_occupied=True)
    room=Room("kitchen","Kitchen",(Window("binary_sensor.win","Window",False),),())
    c={"enabled":True,"controller":"device","mode":"auto",
       "temperature_entity":"sensor.kitchen_temperature","climate_entity":"climate.kitchen",
       "away_entities":["person.resident"]}
    report,tracked=gather(hass,room,c)
    assert report["occupancy"]=="occupied"
    assert len(report["presence_entities"])==2
    assert report["profile"]=="comfort"
    assert report["mode"]=="heat"
    assert report["automatic_actuation_enabled"] is False
    assert "binary_sensor.kitchen_occupancy" in tracked


def test_all_presence_off_selects_home_while_any_unknown_never_claims_away(adapter):
    from custom_components.air_quality_advisor.climate_rooms import gather
    room=Room("kitchen","Kitchen",(Window("binary_sensor.win","Window",False),),())
    cfg={"enabled":True,"controller":"device","mode":"heat",
         "unoccupied_delay_minutes":0,
         "temperature_entity":"sensor.kitchen_temperature","climate_entity":"climate.kitchen"}
    result,_=gather(home(),room,cfg)
    assert result["profile"]=="home"
    result,_=gather(home(unknown=True),room,cfg)
    assert result["profile"]=="home"


def test_person_tracker_away_priority_and_open_window_hold(adapter):
    from custom_components.air_quality_advisor.climate_rooms import gather
    cfg={"enabled":True,"controller":"device","mode":"auto",
         "temperature_entity":"sensor.kitchen_temperature","climate_entity":"climate.kitchen",
         "away_entities":["person.resident"]}
    room=Room("kitchen","Kitchen",(Window("binary_sensor.win","Window",False),),())
    report,_=gather(home(away=True),room,cfg)
    assert report["profile"]=="away"
    room=Room("kitchen","Kitchen",(Window("binary_sensor.win","Window",True),),())
    report,_=gather(home(away=True),room,cfg)
    assert report["status"]=="hold"

def test_new_room_absence_requires_stable_unoccupied_delay(adapter):
    from custom_components.air_quality_advisor.climate_rooms import gather
    home_hass=home(room_occupied=False,second_occupied=False)
    room=Room("kitchen","Kitchen",(Window("binary_sensor.win","Window",False),),())
    conf={"enabled":True,"controller":"device","mode":"heat",
          "unoccupied_delay_minutes":20,
          "temperature_entity":"sensor.kitchen_temperature",
          "climate_entity":"climate.kitchen"}
    status,_=gather(home_hass,room,conf)
    assert status["profile"]=="comfort"
    assert status["occupancy_evidence"]=="awaiting_stable_unoccupied_period"
    # HA state can remain OFF while reporting normally; last_changed (rather
    # than last_reported) establishes the entire quiet period.
    from datetime import datetime,timedelta,timezone
    before=datetime.now(timezone.utc)-timedelta(minutes=25)
    for entity in ("binary_sensor.kitchen_occupancy","binary_sensor.kitchen_presence"):
        home_hass.states.get(entity).last_changed=before
    status,_=gather(home_hass,room,conf)
    assert status["profile"]=="home"


def test_climate_only_room_without_windows_is_not_forced_to_hold(adapter):
    from custom_components.air_quality_advisor.climate_rooms import gather
    house=home(room_occupied=True)
    cfg={"enabled":True,"controller":"device","mode":"heat",
         "temperature_entity":"sensor.kitchen_temperature",
         "climate_entity":"climate.kitchen"}
    room=Room("kitchen","Kitchen",(),())
    autonomous,_=gather(house,room,cfg)
    assert autonomous["status"]=="ready"
    assert autonomous["window_evidence"]=="no_contact_configured"
    monitored,_=gather(house,room,cfg,require_window_contact=True)
    assert monitored["status"]=="hold"
    assert monitored["window_evidence"]=="missing_required_contact"


def test_room_mode_can_plan_secondary_ac_without_claiming_radiator_cooling(adapter):
    from custom_components.air_quality_advisor.climate_rooms import gather
    from custom_components.air_quality_advisor.logic import Room,Window
    air=home(room_occupied=True)
    radiator=air.states.get("climate.kitchen")
    radiator.attributes["hvac_modes"]=["off","heat"]
    radiator.attributes["hvac_action"]="idle"
    ac=MockState("climate.kitchen_ac","cool")
    ac.attributes.update({"hvac_modes":["off","cool","dry","fan_only"],
                          "supported_features":1,"hvac_action":"idle"})
    air._values[ac.entity_id]=ac
    air._entity_areas[ac.entity_id]="kitchen"
    cfg={"enabled":True,"controller":"device","mode":"cool",
        "temperature_entity":"sensor.kitchen_temperature",
        "climate_entity":"climate.kitchen",
        "cool_climate_entity":"climate.kitchen_ac"}
    room=Room("kitchen","Kitchen",(Window("binary_sensor.win","Window",False),),())
    report,tracked=gather(air,room,cfg)
    assert report["status"]=="ready"
    assert report["mode"]=="cool"
    assert report["temperature_target_c"]==26
    assert report["climate_capabilities"]["cool"] is False
    assert report["room_planning_capabilities"]["cool"] is True
    assert report["equipment_plan"]["thermal"]["entity_id"]==ac.entity_id
    assert ac.entity_id in tracked


def test_environment_only_plans_moisture_without_temperature_or_climate_device(adapter):
    from custom_components.air_quality_advisor.climate_rooms import gather
    from custom_components.air_quality_advisor.logic import Reading
    from test_discovery import FakeHass,MockState
    humidity=MockState("sensor.bathroom_humidity",74,
                       device_class="humidity",unit="%")
    dryer=MockState("humidifier.bathroom_dehumidifier","off",
                    device_class="dehumidifier")
    hass=FakeHass([humidity,dryer],{
        humidity.entity_id:"bathroom",dryer.entity_id:"bathroom",
    })
    room=Room("bathroom","Bathroom",(),(
        Reading(humidity.entity_id,"Humidity","humidity",74),
    ))
    config={"enabled":True,"controller":"environment",
            "mode":"auto","humidity_entity":humidity.entity_id,
            "dehumidifier_entity":dryer.entity_id,
            "humidity_low_rh":40,"humidity_high_rh":60}
    result,tracked=gather(hass,room,config,require_window_contact=False)
    assert result["status"]=="advisory"
    assert result["controller"]=="environment"
    assert result["temperature_c"] is None
    assert result["equipment_plan"]["moisture"]["entity_id"]==dryer.entity_id
    assert humidity.entity_id in tracked and dryer.entity_id in tracked
