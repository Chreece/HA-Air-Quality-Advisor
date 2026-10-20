"""Native AC DRY/FAN_ONLY advice never starts or switches a compressor."""
from datetime import datetime,timedelta,timezone

from custom_components.air_quality_advisor.logic import Reading
from test_discovery import adapter
from test_climate_coordination import home,config


def setup(adapter,*,mode="fan_only",rh=75,thermal="off",age_minutes=40):
    from custom_components.air_quality_advisor.climate_coordination import (
        room_equipment_plan,
    )
    from custom_components.air_quality_advisor.climate_hvac_modes import (
        native_air_mode_advice,
    )
    h=home()
    device=h.states.get("climate.ac")
    device.state=mode
    device.last_changed=datetime.now(timezone.utc)-timedelta(minutes=age_minutes)
    cfg={**config(),"enabled":True}
    cfg.pop("dehumidifier_entity",None)
    now=datetime.now(timezone.utc).timestamp()
    report=room_equipment_plan(h,"bedroom",cfg,
        {"status":"ready","mode":thermal,"window_safe":True},
        (Reading("sensor.rh","Humidity","humidity",rh),))
    return native_air_mode_advice(h,"bedroom",cfg,report,now)


def test_ac_dry_mode_is_only_recommended_not_commanded(adapter):
    result=setup(adapter,rh=76)
    assert result["status"]=="manual_mode_transition_suggested"
    assert result["current_mode"]=="fan_only"
    assert result["recommended_mode"]=="dry"
    assert result["requires_device_commissioning"] is True
    assert result["automatic_control"] is False


def test_rh_recovery_recommends_only_native_fan_mode(adapter):
    result=setup(adapter,mode="dry",rh=56)
    assert result["status"]=="manual_mode_transition_suggested"
    assert result["recommended_mode"]=="fan_only"
    assert not result["automatic_control"]
    correct=setup(adapter,mode="dry",rh=76)
    assert correct["status"]=="already_in_suitable_mode"


def test_thermostat_priority_does_not_assume_ac_dry_is_safe(adapter):
    active=setup(adapter,thermal="heat",rh=77)
    assert active["status"]=="thermal_regulation_has_priority"
    assert not active["automatic_control"]


def test_native_mode_stability_dwell_and_manual_off(adapter):
    insufficient=setup(adapter,age_minutes=6)
    assert insufficient["status"]=="mode_dwell_not_met"
    assert insufficient["dwell_remaining_minutes"]>20
    turned_off=setup(adapter,mode="off")
    assert turned_off["status"]=="air_conditioner_off_or_unavailable"
    different=setup(adapter,mode="cool")
    assert different["status"]=="another_native_mode_active"


def test_hvac_capability_unknown_and_missing_measurement_hold(adapter):
    from custom_components.air_quality_advisor.climate_coordination import room_equipment_plan
    from custom_components.air_quality_advisor.climate_hvac_modes import native_air_mode_advice
    h=home()
    h.states.get("climate.ac").attributes["hvac_modes"]=["off","cool"]
    cfg={**config(),"enabled":True}
    cfg.pop("dehumidifier_entity",None)
    item=room_equipment_plan(h,"bedroom",cfg,
        {"status":"ready","mode":"off","window_safe":True},
        (Reading("sensor.rh","Humidity","humidity",75),))
    t=datetime.now(timezone.utc).timestamp()
    assert native_air_mode_advice(h,"bedroom",cfg,item,t)["status"]=="native_dry_mode_required"
    h.states.get("climate.ac").attributes["hvac_modes"]=["off","cool","dry","fan_only"]
    item=room_equipment_plan(h,"bedroom",cfg,
        {"status":"ready","mode":"off","window_safe":True},())
    assert native_air_mode_advice(h,"bedroom",cfg,item,t)["status"]=="humidity_evidence_insufficient"


def test_dry_only_climate_does_not_invent_a_fan_mode(adapter):
    from custom_components.air_quality_advisor.climate_hvac_modes import native_air_mode_advice
    from custom_components.air_quality_advisor.climate_coordination import room_equipment_plan
    h=home()
    dry=h.states.get("climate.ac")
    dry.state="dry"
    dry.attributes["hvac_modes"]=["dry"]
    dry.last_changed=datetime.now(timezone.utc)-timedelta(minutes=40)
    config_={**config(),"enabled":True}
    config_.pop("dehumidifier_entity",None)
    item=room_equipment_plan(h,"bedroom",config_,
        {"status":"ready","mode":"off","window_safe":True},
        (Reading("sensor.rh","RH","humidity",56),))
    result=native_air_mode_advice(
        h,"bedroom",config_,item,datetime.now(timezone.utc).timestamp())
    assert result["status"]=="manual_stop_dry_suggested"
    assert result["recommended_mode"]=="off"
    assert result["automatic_control"] is False
    item=room_equipment_plan(h,"bedroom",config_,
        {"status":"ready","mode":"off","window_safe":True},
        (Reading("sensor.rh","RH","humidity",76),))
    result=native_air_mode_advice(h,"bedroom",config_,item,
        datetime.now(timezone.utc).timestamp())
    assert result["status"]=="already_in_suitable_mode"
    assert result["recommended_mode"]=="dry"
