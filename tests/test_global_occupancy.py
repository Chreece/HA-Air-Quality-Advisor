"""Conservative evidence for shared room/home/sleep sources and device gating."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from test_discovery import FakeHass,MockState,adapter


def test_room_list_in_state_attribute_and_unknown_names(adapter):
    from custom_components.air_quality_advisor.occupancy_policy import configured_rooms
    state=MockState("sensor.rooms",'["living","kitchen"]')
    attr=MockState("sensor.sleep","ready")
    attr.attributes["sleeping_rooms"]=["kitchen"]
    h=FakeHass([state,attr])
    valid={"living","kitchen"}
    rooms,why=configured_rooms(h,"sensor.rooms","",valid)
    assert rooms=={"living","kitchen"} and why=="verified_rooms_list"
    rooms,why=configured_rooms(h,"sensor.sleep","sleeping_rooms",valid)
    assert rooms=={"kitchen"}
    state.state='["unknown_room"]'
    assert configured_rooms(h,"sensor.rooms","",valid)[0] is None
    state.state="[]"
    assert configured_rooms(h,"sensor.rooms","",valid)[0]==set()
    state.state="unknown"
    assert configured_rooms(h,"sensor.rooms","",valid)[0] is None
    state.state="[]"
    state.last_reported=datetime.now(timezone.utc)-timedelta(hours=9)
    assert configured_rooms(h,"sensor.rooms","",valid)[0] is None


def test_global_room_occupancy_positive_wins_unknown_never_off(adapter):
    from custom_components.air_quality_advisor.occupancy_policy import room_presence
    sensor=MockState("binary_sensor.kitchen_presence","on",device_class="presence")
    roomlist=MockState("sensor.occupied_rooms","[]")
    h=FakeHass([sensor,roomlist],{sensor.entity_id:"kitchen"})
    cfg={"occupied_rooms_entity":roomlist.entity_id,
         "room_occupancy_sensors":[sensor.entity_id]}
    status,reason,sources=room_presence(h,"kitchen",{},cfg,known_areas={"kitchen"})
    assert status=="occupied" and sources==[sensor.entity_id]
    sensor.state="off"
    status,reason,_=room_presence(h,"kitchen",{},cfg,known_areas={"kitchen"})
    assert status=="unoccupied"
    roomlist.state="unavailable"
    assert room_presence(h,"kitchen",{},cfg,known_areas={"kitchen"})[0]=="unknown"
    sensor.state="on"
    assert room_presence(h,"kitchen",{},cfg,known_areas={"kitchen"})[0]=="occupied"


def test_shared_home_trackers_sleep_room_list_and_device_policy(adapter):
    from custom_components.air_quality_advisor.occupancy_policy import (
        home_presence,sleep_presence,device_permission
    )
    resident=MockState("person.resident","not_home")
    sleepers=MockState("sensor.sleepers",'{"sleep_rooms":["kitchen"]}')
    h=FakeHass([resident,sleepers])
    config={"home_trackers":["person.resident"],"sleep_rooms_entity":"sensor.sleepers"}
    status,reason,sources=home_presence(h,config)
    assert status=="away" and sources==["person.resident"]
    assert sleep_presence(h,"kitchen",config,{"kitchen"})[0] is True
    device={"auto_control":True,"presence_requirement":"home",
            "absence_action":"off","sleep_behavior":"normal"}
    assert device_permission(device,"occupied","away",False)[0]=="absent"
    assert device_permission(device,"occupied","home",False)[0]=="eligible"
    device["presence_requirement"]="room"
    assert device_permission(device,"unknown","home",False)[0]=="held"
    assert device_permission(device,"unoccupied","home",False)[0]=="absent"
    device["presence_requirement"]="always"
    device["sleep_behavior"]="pause"
    assert device_permission(device,"occupied","home",True)[0]=="held"
    assert device_permission(device,"occupied","home",None)[0]=="held"
    device["auto_control"]=False
    assert device_permission(device,"occupied","home",False)[0]=="held"


def test_gather_global_occupied_rooms_and_sleep_profile(adapter):
    from custom_components.air_quality_advisor.climate_rooms import gather
    from custom_components.air_quality_advisor.logic import Room, Window
    co2=MockState("sensor.kitchen_temperature",19,device_class="temperature",unit="°C")
    thermo=MockState("climate.kitchen","heat")
    thermo.attributes.update({"hvac_modes":["off","heat"],"supported_features":1})
    occupied=MockState("sensor.occupied_rooms",'["kitchen"]')
    sleeping=MockState("sensor.sleep_rooms",'["kitchen"]')
    h=FakeHass([co2,thermo,occupied,sleeping],{
        co2.entity_id:"kitchen",thermo.entity_id:"kitchen"})
    room=Room("kitchen","Kitchen",(Window("binary_sensor.kitchen_window","Window",False),),())
    cfg={"enabled":True,"controller":"device","mode":"heat",
         "temperature_entity":co2.entity_id,"climate_entity":thermo.entity_id}
    global_cfg={"occupied_rooms_entity":occupied.entity_id,
                "sleep_rooms_entity":sleeping.entity_id}
    plan,tracked=gather(h,room,cfg,global_presence=global_cfg,known_areas={"kitchen"})
    assert plan["profile"]=="sleep"
    assert plan["occupancy"]=="occupied"
    assert plan["sleeping"] is True
    assert plan["sleep_schedule_evidence"]=="verified_rooms_list"
    assert plan["mode"]=="heat"


def test_device_policy_blocks_new_thermal_commands_when_unoccupied(adapter):
    from custom_components.air_quality_advisor.climate_arbitration import new_command_gate
    cfg={"selected_devices":["climate.kitchen"],"device_settings":{
        "climate.kitchen":{"auto_control":True,"presence_requirement":"room"}}}
    plan={"occupancy":"unoccupied","away":"home","sleeping":False}
    assert new_command_gate(FakeHass([]),"kitchen",cfg,plan,
                            "thermal","climate.kitchen")=="room_unoccupied"
    plan["occupancy"]="occupied"
    assert new_command_gate(FakeHass([]),"kitchen",cfg,plan,
                            "thermal","climate.kitchen") is None
    cfg["selected_devices"]=[]
    assert new_command_gate(FakeHass([]),"kitchen",cfg,plan,
                            "thermal","climate.kitchen")=="device_not_selected"



def test_live_gate_rejects_entered_room_and_invalidated_sleep_after_planning(adapter):
    from custom_components.air_quality_advisor.occupancy_policy import (
        live_device_permission,
    )
    sensor=MockState("binary_sensor.living_presence","off",device_class="presence")
    occupied=MockState("sensor.rooms",'[]')
    sleep=MockState("sensor.sleep_rooms",'[]')
    h=FakeHass([sensor,occupied,sleep],{sensor.entity_id:"living"})
    global_cfg={"occupied_rooms_entity":occupied.entity_id,
                "room_occupancy_sensors":[sensor.entity_id],
                "sleep_rooms_entity":sleep.entity_id}
    room_config={"occupancy_sensors":[sensor.entity_id]}
    plan={"occupancy":"unoccupied","away":"home","sleeping":False,
          "global_presence":global_cfg,"known_presence_areas":["living"]}
    device={"auto_control":True,"presence_requirement":"room",
            "sleep_behavior":"normal"}
    assert live_device_permission(h,"living",room_config,plan,device)[0]=="absent"
    sensor.state="on"
    assert live_device_permission(h,"living",room_config,plan,device)[0]=="eligible"
    device["sleep_behavior"]="pause"
    sleep.state="unavailable"
    assert live_device_permission(h,"living",room_config,plan,device)[0]=="held"
    device["sleep_behavior"]="sleep_targets"
    assert live_device_permission(h,"living",room_config,plan,device)[0]=="held"



def test_sleep_pause_takes_priority_over_absence_off(adapter):
    from custom_components.air_quality_advisor.occupancy_policy import device_permission
    device={"auto_control":True,"presence_requirement":"home",
            "absence_action":"off","sleep_behavior":"pause"}
    assert device_permission(device,"unoccupied","away",True)==(
        "held","sleep_room_control_paused"
    )
    assert device_permission(device,"unoccupied","away",None)==(
        "held","sleep_room_evidence_unknown"
    )
    assert device_permission(device,"unoccupied","away",False)[0]=="absent"
    device["sleep_behavior"]="sleep_targets"
    assert device_permission(device,"unoccupied","away",None)[0]=="held"


def test_filtered_room_list_sources_offer_state_and_valid_attributes(adapter):
    from custom_components.air_quality_advisor.occupancy_policy import (
        ROOM_STATE_VALUE, room_list_fields, room_list_entities, configured_rooms
    )
    valid = MockState("sensor.list_source", '["kitchen"]')
    valid.attributes["sleeping_rooms"]=["kitchen"]
    valid.attributes["temperature"]=20.3
    invalid = MockState("sensor.unsuitable_source","sleeprooms")
    invalid.attributes["battery"]=78
    h=FakeHass([valid,invalid])
    fields=room_list_fields(h, valid.entity_id, {"kitchen"})
    assert {r["value"] for r in fields}=={ROOM_STATE_VALUE,"sleeping_rooms"}
    assert room_list_fields(h, invalid.entity_id, {"kitchen"})==[]
    options=room_list_entities(h,{"kitchen"})
    assert valid.entity_id in {r["value"] for r in options}
    assert invalid.entity_id not in {r["value"] for r in options}
    names, reason=configured_rooms(h, valid.entity_id,"sleeping_rooms",{"kitchen"})
    assert names=={"kitchen"} and reason=="verified_rooms_list"
    names, reason=configured_rooms(h, valid.entity_id,"",{"kitchen"})
    assert names=={"kitchen"} and reason=="verified_rooms_list"


def test_invalid_mixed_rooms_list_never_authorizes_empty_home(adapter):
    from custom_components.air_quality_advisor.occupancy_policy import room_list_fields
    item=MockState("sensor.mixed_rooms",'["kitchen","unknown_room"]')
    h=FakeHass([item])
    assert room_list_fields(h,item.entity_id,{"kitchen"})==[]
    item.state="[]"
    assert room_list_fields(h,item.entity_id,{"kitchen"})==[
        {"value":"__state__","label":"State"}
    ]
