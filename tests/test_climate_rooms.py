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
    assert report["profile"]=="home"
    assert report["mode"]=="heat"
    assert report["automatic_actuation_enabled"] is False
    assert "binary_sensor.kitchen_occupancy" in tracked


def test_all_presence_off_selects_eco_while_any_unknown_does_not_claim_vacancy(adapter):
    from custom_components.air_quality_advisor.climate_rooms import gather
    room=Room("kitchen","Kitchen",(Window("binary_sensor.win","Window",False),),())
    cfg={"enabled":True,"controller":"device","mode":"heat",
         "temperature_entity":"sensor.kitchen_temperature","climate_entity":"climate.kitchen"}
    result,_=gather(home(),room,cfg)
    assert result["profile"]=="unoccupied"
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
