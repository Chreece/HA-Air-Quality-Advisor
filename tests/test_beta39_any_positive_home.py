"""House Home means ANY fresh configured device tracker or binary sensor ON.

These regressions protect global presence, old room trackers and the live
write-boundary evaluation. A negative/unknown source is never allowed to veto
a verified positive. Negative inputs alone retain legacy cooldown behavior.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from test_discovery import FakeHass, MockState, adapter


def _old(value):
    return datetime.now(timezone.utc) - timedelta(minutes=value)


def test_any_person_or_device_tracker_home_wins_over_all_negative_and_unknown(adapter):
    from custom_components.environment_manager.occupancy_policy import home_presence

    phone = MockState("device_tracker.phone", "home")
    watch = MockState("device_tracker.watch", "not_home")
    absent = MockState("person.other", "not_home")
    broken = MockState("device_tracker.unavailable", "unavailable")
    hass = FakeHass([phone, watch, absent, broken])
    config = {"home_trackers": [phone.entity_id, watch.entity_id,
                                absent.entity_id, broken.entity_id],
              "home_policy": "all_home"}
    status, reason, sources = home_presence(hass, config)
    assert status == "home" and reason == "any_home_policy"
    assert set(sources) == set(config["home_trackers"])
    phone.state = "not_home"
    watch.state = "home"
    assert home_presence(hass,config)[0] == "home"
    phone.state = "home"
    watch.state = "not_home"
    assert home_presence(hass,config)[0] == "home"


def test_binary_sensor_on_from_either_general_selector_means_home(adapter):
    from custom_components.environment_manager.occupancy_policy import home_presence

    global_presence = MockState("binary_sensor.home_presence", "on")
    room_a = MockState("binary_sensor.kitchen_presence", "off", device_class="presence")
    room_b = MockState("binary_sensor.bedroom_presence", "on", device_class="occupancy")
    tracker = MockState("device_tracker.resident", "not_home")
    hass=FakeHass([global_presence,room_a,room_b,tracker])
    config={"home_trackers":[tracker.entity_id,global_presence.entity_id],
            "room_occupancy_sensors":[room_a.entity_id,room_b.entity_id]}
    assert home_presence(hass,config)[0]=="home"
    global_presence.state="off"
    assert home_presence(hass,config)[:2]==("home","room_sensor_occupied")
    room_b.state="off"
    global_presence.state="on"
    assert home_presence(hass,config)[0]=="home"


def test_empty_or_broken_room_list_never_vetoes_any_home_positive(adapter):
    from custom_components.environment_manager.occupancy_policy import home_presence

    roomlist = MockState("sensor.occupied_rooms","[]")
    roomlist.last_changed = roomlist.last_updated = _old(35)
    present = MockState("device_tracker.resident","home")
    room_sensor = MockState("binary_sensor.entry_occupancy","off")
    hass = FakeHass([roomlist,present,room_sensor])
    config = {"occupied_rooms_entity":roomlist.entity_id,
              "room_occupancy_sensors":[room_sensor.entity_id],
              "home_trackers":[present.entity_id],
              "away_cooldown_minutes":10}
    assert home_presence(hass,config)[0]=="home"
    roomlist.state="unavailable"
    assert home_presence(hass,config)[0]=="home"
    present.state="not_home"
    room_sensor.state="on"
    assert home_presence(hass,config)[0]=="home"
    room_sensor.state="off"
    assert home_presence(hass,config)[0]=="unknown"


def test_positive_local_fallback_is_not_ignored_when_general_tracker_is_away(adapter):
    from custom_components.environment_manager.occupancy_policy import home_presence

    configured=MockState("person.household","not_home")
    local=MockState("device_tracker.legacy_phone","home")
    hass=FakeHass([configured,local])
    cfg={"home_trackers":[configured.entity_id]}
    status,reason,sources=home_presence(hass,cfg,[local.entity_id])
    assert (status,reason)==("home","any_home_policy")
    assert sources==[configured.entity_id,local.entity_id]
    configured.state="unavailable"
    assert home_presence(hass,cfg,[local.entity_id])[0]=="home"
    # Duplicate names across two settings must not multiply evidence.
    assert home_presence(hass,{"home_trackers":[local.entity_id]},
                         [local.entity_id])[2]==[local.entity_id]


def test_without_positive_negative_and_unknown_are_still_conservative(adapter):
    from custom_components.environment_manager.occupancy_policy import home_presence

    first=MockState("device_tracker.a","not_home")
    second=MockState("device_tracker.b","not_home")
    unknown=MockState("binary_sensor.home","unavailable")
    hass=FakeHass([first,second,unknown])
    cfg={"home_trackers":[first.entity_id,second.entity_id]}
    assert home_presence(hass,cfg)[0]=="away"
    cfg["home_trackers"].append(unknown.entity_id)
    assert home_presence(hass,cfg)[0]=="unknown"
    first.state="home"
    first.last_reported=_old(500)
    # Stale states are not affirmative; a historical home signal cannot
    # defeat current negative evidence or create electrical consent.
    assert home_presence(hass,cfg)[0]=="unknown"
    first.last_reported=datetime.now(timezone.utc)
    assert home_presence(hass,cfg)[0]=="home"


def test_legacy_room_climate_away_policy_never_vetoes_positive_home(adapter):
    from custom_components.environment_manager.climate_strategy import home_away_evidence
    for mode in ("all_home","any_home"):
        assert home_away_evidence([True,False],mode=mode)[0]=="home"
        assert home_away_evidence([True,None],mode=mode)[0]=="home"
        assert home_away_evidence([False,False],mode=mode)[0]=="away"
    assert home_away_evidence([None,False])[0]=="home"
    assert home_away_evidence([],mode="all_home")[0]=="home"


def test_live_device_home_gate_uses_any_positive_source_not_stale_plan(adapter):
    from custom_components.environment_manager.occupancy_policy import live_device_permission

    configured=MockState("person.member","home")
    roomlist=MockState("sensor.empty_rooms","[]")
    roomlist.last_changed=roomlist.last_updated=_old(35)
    hass=FakeHass([configured,roomlist])
    plan={
        "global_presence":{
            "occupied_rooms_entity":roomlist.entity_id,
            "home_trackers":[configured.entity_id],
            "away_cooldown_minutes":0,
        },
        "known_presence_areas":["living"],
        "sleeping":False,
        "occupancy":"unknown",
        "away":"away",
    }
    device={"auto_control":True,"presence_requirement":"home",
            "sleep_behavior":"normal"}
    assert live_device_permission(hass,"living",{},plan,device)[0]=="eligible"
    configured.state="not_home"
    assert live_device_permission(hass,"living",{},plan,device)[0]=="absent"
