"""Room temperature control follows exact verified Room Setup sensor selection.

Selected room temperature inputs must feed planning and mold observation when
no legacy single pin exists. No missing/old/cross-area data is fabricated.
"""
from __future__ import annotations

import pytest
from test_discovery import FakeHass, MockState, adapter
from custom_components.environment_manager.room_sources import room_temperature_evidence
from custom_components.environment_manager.logic import Room


@pytest.fixture
def evidence(adapter):
    first=MockState("sensor.room_temperature",21,device_class="temperature",unit="°C")
    second=MockState("sensor.room_second_temp",23,device_class="temperature",unit="°C")
    foreign=MockState("sensor.other_temp",18,device_class="temperature",unit="°C")
    states=[first,second,foreign]
    hass=FakeHass(states,{
        first.entity_id:"room",second.entity_id:"room",foreign.entity_id:"elsewhere"
    })
    settings={"room_sources":{"room":{"temperature":[first.entity_id,second.entity_id]}}}
    return hass,settings,first,second,foreign


def test_multiple_explicit_room_temperatures_give_verified_mean(evidence):
    from custom_components.environment_manager.climate_rooms import gather
    hass, settings, first, second, _ = evidence
    value, why = room_temperature_evidence(hass, settings, "room")
    assert value==22
    assert why["status"]=="ready"
    assert why["selected_count"]==2
    assert why["source"]=="room_selected_mean"
    assert why["entity_ids"]==[first.entity_id,second.entity_id]
    room=Room("room","Room",(),())
    plan, watched=gather(hass,room,{"enabled":True,"controller":"environment"},
                         selected_temperature_c=value,temperature_evidence=why)
    assert plan["temperature_c"]==22
    assert plan["temperature_evidence"]==why
    assert plan["reason"]=="environment_only_no_hvac"
    assert plan["status"]=="advisory"
    assert not plan["automatic_actuation_enabled"]


def test_explicit_pin_is_never_replaced_by_other_selected_temperature(evidence):
    from custom_components.environment_manager.climate_rooms import gather
    hass, settings, first, second, foreign = evidence
    temp, why = room_temperature_evidence(
        hass,settings,"room",pinned=second.entity_id,
    )
    assert temp==23 and why["source"]=="pinned_sensor"
    temp, invalid = room_temperature_evidence(
        hass,settings,"room",pinned=foreign.entity_id,
    )
    assert temp is None and invalid["status"]=="pinned_sensor_not_selected"
    room=Room("room","Room",(),())
    report,_=gather(hass,room,{
        "enabled":True,"controller":"environment","temperature_entity":foreign.entity_id,
    },selected_temperature_c=temp,temperature_evidence=invalid)
    assert report["temperature_c"] is None
    assert report["temperature_evidence"]["status"]=="pinned_sensor_not_selected"


def test_selected_unavailable_and_wrong_room_temperature_never_fallback(evidence):
    hass, settings, first, second, foreign = evidence
    second.state="unavailable"
    temp, metadata=room_temperature_evidence(hass,settings,"room")
    assert temp is None
    assert metadata["status"]=="selected_temperature_invalid"
    assert metadata["invalid_sources"]==[
        {"entity_id":second.entity_id,"reason":"sensor_unavailable"}
    ]
    second.state="23"
    settings["room_sources"]["room"]["temperature"].append(foreign.entity_id)
    temp, metadata=room_temperature_evidence(hass,settings,"room")
    assert temp is None
    assert metadata["invalid_sources"]==[
        {"entity_id":foreign.entity_id,"reason":"sensor_wrong_area"}
    ]


def test_no_selected_temperature_stays_unavailable(evidence):
    hass, _, *_ = evidence
    temp, metadata=room_temperature_evidence(
        hass,{"room_sources":{"room":{"temperature":[]}}},"room"
    )
    assert temp is None and metadata["status"]=="no_selected_room_temperature"
