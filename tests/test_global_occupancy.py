"""Conservative evidence for shared room/home/sleep sources and device gating."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from test_discovery import FakeHass,MockState,adapter


def test_room_list_in_state_attribute_and_unknown_names(adapter):
    from custom_components.environment_manager.occupancy_policy import configured_rooms
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
    from custom_components.environment_manager.occupancy_policy import room_presence
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
    from custom_components.environment_manager.occupancy_policy import (
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
    from custom_components.environment_manager.climate_rooms import gather
    from custom_components.environment_manager.logic import Room, Window
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
    from custom_components.environment_manager.climate_arbitration import new_command_gate
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
    from custom_components.environment_manager.occupancy_policy import (
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
    from custom_components.environment_manager.occupancy_policy import device_permission
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


def test_empty_occupied_rooms_means_away_only_after_cooldown(adapter):
    from custom_components.environment_manager.occupancy_policy import home_presence
    empty = MockState("sensor.occupied_rooms", "[]")
    empty.last_changed = datetime.now(timezone.utc) - timedelta(minutes=5)
    empty.last_updated = empty.last_changed
    resident = MockState("person.resident", "home")
    h = FakeHass([empty, resident])
    cfg = {"occupied_rooms_entity": empty.entity_id,
           "home_trackers": [resident.entity_id],
           "away_cooldown_minutes": 10}
    status, reason, sources = home_presence(h, cfg)
    assert status == "home" and reason == "no_occupied_rooms_cooldown"
    assert sources == [empty.entity_id]
    empty.last_changed = datetime.now(timezone.utc) - timedelta(minutes=11)
    empty.last_updated = empty.last_changed
    assert home_presence(h, cfg)[:2] == ("away", "occupied_rooms_empty")
    empty.state = "unavailable"
    assert home_presence(h, cfg)[0] == "unknown"


def test_all_room_presence_sensors_empty_override_home_tracker_after_cooldown(adapter):
    from custom_components.environment_manager.occupancy_policy import home_presence
    a = MockState("binary_sensor.a_presence", "off", device_class="presence")
    b = MockState("binary_sensor.b_presence", "off", device_class="presence")
    resident = MockState("person.resident", "home")
    stamp = datetime.now(timezone.utc) - timedelta(minutes=20)
    a.last_changed = b.last_changed = stamp
    h = FakeHass([a, b, resident])
    cfg = {"room_occupancy_sensors": [a.entity_id, b.entity_id],
           "home_trackers": [resident.entity_id], "away_cooldown_minutes": 10}
    assert home_presence(h, cfg)[0] == "away"
    b.state = "on"
    assert home_presence(h, cfg)[0] == "home"
