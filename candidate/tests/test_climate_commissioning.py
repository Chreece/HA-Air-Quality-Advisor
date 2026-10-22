"""Read-only climate commissioning never operates or reveals unrelated devices."""
from datetime import datetime,timezone

from test_discovery import FakeHass, MockState,adapter


def sample():
    ac=MockState("climate.bathroom_ac","fan_only")
    ac.attributes.update({
        "hvac_modes":["dry","off","fan_only"],
        "supported_features":0,"hvac_action":"fan",
        "token":"never exported","device_serial":"never exported",
    })
    ac.last_changed=datetime.fromtimestamp(1000,timezone.utc)
    rh=MockState("sensor.bathroom_humidity",72,
                 device_class="humidity",unit="%")
    window=MockState("binary_sensor.bathroom_window","off",
                     device_class="window")
    unrelated=MockState("sensor.private_token","secret")
    h=FakeHass(
        [ac,rh,window,unrelated],
        {ac.entity_id:"bathroom",rh.entity_id:"bathroom",
         window.entity_id:"bathroom",unrelated.entity_id:"office"},
    )
    conf={
        "enabled":True,"controller":"environment",
        "allow_actuation":True,"dry_fan_mode_auto":True,
        "dry_fan_hardware_confirmed":True,
        "dry_fan_mode_dwell_s":1800,
        "humidity_entity":rh.entity_id,
        "dry_climate_entity":ac.entity_id,
    }
    return h,conf


def test_one_room_snapshot_is_read_only_and_reports_exact_native_modes(adapter):
    from custom_components.air_quality_advisor.climate_commissioning import report
    hass,cfg=sample()
    class NoServices:
        def __getattr__(self,name):
            raise AssertionError("Commissioning must never access HA services")
    hass.services=NoServices()
    output=report(hass,{"bathroom":cfg},area="bathroom",now=5000)
    assert output["status"]=="ok"
    assert output["no_commands_sent"] is True
    assert output["physical_hardware_safety_verified"] is False
    room=output["rooms"][0]
    assert room["devices"][0]["role"]=="dry_climate_entity"
    assert room["devices"][0]["reported_modes"]==["dry","fan_only","off"]
    assert room["devices"][0]["state_changed_age_seconds"]==4000
    assert room["sensors"][0]["value"]==72
    assert room["windows"][0]["closed_verified"] is True
    assert room["native_dry_fan"]["software_preflight_ready"] is True
    assert room["native_dry_fan"]["real_hardware_commissioned_by_integration"] is False
    serialized=repr(output)
    for secret in ("never exported","private_token","device_serial","token"):
        assert secret not in serialized


def test_missing_or_wrong_room_sensors_and_unknown_dry_capability_are_blocked(adapter):
    from custom_components.air_quality_advisor.climate_commissioning import report
    hass,cfg=sample()
    hass._entity_areas["sensor.bathroom_humidity"]="office"
    hass.states.get("climate.bathroom_ac").attributes["hvac_modes"]=["dry"]
    result=report(hass,{"bathroom":cfg},area="bathroom",now=5000)
    row=result["rooms"][0]
    assert row["sensors"][0]["status"]=="unavailable_or_unverified"
    assert row["native_dry_fan"]["software_preflight_ready"] is False
    assert row["native_dry_fan"]["blockers"]
    hass.states.get("binary_sensor.bathroom_window").state="unknown"
    assert "window_open_or_unknown" in report(
        hass,{"bathroom":cfg},area="bathroom",now=5000
    )["rooms"][0]["native_dry_fan"]["blockers"]


def test_commissioning_scope_never_returns_unconfigured_areas(adapter):
    from custom_components.air_quality_advisor.climate_commissioning import report
    hass,cfg=sample()
    absent=report(hass,{"bathroom":cfg},area="office",now=5000)
    assert absent=={
        "status":"area_not_configured",
        "requested_area":"office",
        "read_only":True,
        "rooms":[],
    }
    all_rooms=report(hass,{"bathroom":cfg},now=5000)
    assert [v["area_id"] for v in all_rooms["rooms"]]==["bathroom"]


def test_duplicate_configured_native_device_is_flagged_for_hardware_testing(adapter):
    from custom_components.air_quality_advisor.climate_commissioning import report
    hass,cfg=sample()
    duplicate={
        "bedroom":{"enabled":True,
                   "dry_climate_entity":"climate.bathroom_ac"},
        "bathroom":cfg,
    }
    result=report(hass,duplicate,area="bathroom",now=5000)
    item=result["rooms"][0]["native_dry_fan"]
    assert not item["software_preflight_ready"]
    assert "equipment_assigned_to_multiple_rooms" in item["blockers"]


def test_default_legacy_climate_configuration_never_attests_hardware(adapter):
    from custom_components.air_quality_advisor.climate_commissioning import report
    hass,cfg=sample()
    result=report(hass,{"bathroom":{
        "enabled":True,"controller":"environment",
        "dry_climate_entity":"climate.bathroom_ac",
        "humidity_entity":"sensor.bathroom_humidity",
    }},area="bathroom",now=5000)
    detail=result["rooms"][0]["native_dry_fan"]
    assert not detail["requested"]
    assert not detail["hardware_confirmed_by_user"]
    assert not detail["software_preflight_ready"]
    assert detail["real_hardware_commissioned_by_integration"] is False



def test_commissioning_flags_device_shared_by_separate_entry_without_exposing_id(
    adapter,
):
    from types import SimpleNamespace
    from custom_components.air_quality_advisor.climate_commissioning import report
    hass,cfg=sample()
    foreign=SimpleNamespace(
        entry_id="another-private-config-id",disabled_by=None,
        data={"climate_rooms":{"bathroom":{"enabled":True,"allow_actuation":True,
            "dry_climate_entity":"climate.bathroom_ac"}}},
        options={},
    )
    own=SimpleNamespace(
        entry_id="mine",disabled_by=None,
        data={"climate_rooms":{"bathroom":cfg}},
        options={},
    )
    hass.config_entries=SimpleNamespace(
        async_entries=lambda domain:[own,foreign],
    )
    result=report(hass,{"bathroom":cfg},entry_id="mine",
                  area="bathroom",now=5000)
    item=result["rooms"][0]["native_dry_fan"]
    assert item["software_preflight_ready"] is False
    assert "equipment_assigned_to_multiple_rooms" in item["blockers"]
    assert "another-private-config-id" not in repr(result)
