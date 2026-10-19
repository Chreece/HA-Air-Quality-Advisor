"""Air quality treatment evidence and conservative fan supervision eligibility."""
from custom_components.air_quality_advisor.climate_air_actions import (
    unique_measurement, air_treatment_plan,
)
from custom_components.air_quality_advisor.building_physics import moisture_potential
from custom_components.air_quality_advisor.logic import Reading


def sample(metric,value,entity=None):
    return Reading(entity or "sensor."+metric,metric,metric,value)


DEVICES={"inventory":{
    "extraction_fan_entity":{"status":"ready","entity_id":"fan.extractor"},
    "purifier_fan_entity":{"status":"ready","entity_id":"fan.filter"},
}}
BASE={"humidity_management":{"status":"advisory","measured_rh":68}}
CFG={"humidity_entity":"sensor.humidity","pm25_entity":"sensor.pm25",
     "pm25_sensor_verified":True,"co2_entity":"sensor.co2"}


def test_air_quality_filtering_available_when_windows_unsafe():
    result=air_treatment_plan(
        (sample("pm25",64),sample("co2",1750)),
        BASE,DEVICES,{"status":"humidifying"},
        outside_safe=False,science_profile={"co2_ndir_verified":True},
        settings=CFG)
    assert result["filtration"]["status"]=="recommended"
    assert result["filtration"]["speed_control_eligible"]
    assert result["extraction"]["status"]=="blocked_outdoor_evidence"
    assert not result["extraction"]["speed_control_eligible"]
    assert result["thresholds"]["pm25_short_term_action_ug_m3"]==35
    assert "not_exposure" in result["method"]


def test_true_winter_drying_requires_absolute_moisture_not_outdoor_rh():
    cold=moisture_potential(22,68,4,90)
    assert cold["status"]=="drying"
    result=air_treatment_plan(
        (sample("humidity",68),),BASE,DEVICES,cold,
        outside_safe=True,settings=CFG)
    assert result["extraction"]["status"]=="recommended"
    assert "high_rh_and_measured_outdoor_drying" in result["extraction"]["reasons"]
    assert result["extraction"]["speed_control_eligible"] is True
    wet=moisture_potential(22,68,30,85)
    assert wet["status"]=="humidifying"
    result=air_treatment_plan((sample("humidity",68),),BASE,DEVICES,wet,
        outside_safe=True,settings=CFG)
    assert result["extraction"]["status"]=="no_drying_advantage"


def test_co2_requires_verified_ndir_for_operating_fan():
    samples=(sample("co2",1600),)
    r=air_treatment_plan(samples,BASE,DEVICES,{"status":"neutral"},
        outside_safe=True,science_profile={"co2_ndir_verified":False},
        settings={**CFG,"humidity_high_rh":75})
    assert r["extraction"]["status"]=="recommended"
    assert not r["extraction"]["speed_control_eligible"]
    r=air_treatment_plan(samples,BASE,DEVICES,{"status":"neutral"},
        outside_safe=True,science_profile={"co2_ndir_verified":True},
        settings={**CFG,"humidity_high_rh":75})
    assert r["extraction"]["speed_control_eligible"]


def test_ambiguous_stale_sensors_and_calibration_never_earn_speed_control():
    a=(sample("pm25",65,"sensor.first"),sample("pm25",12,"sensor.second"))
    assert unique_measurement(a,"pm25")== (None,"ambiguous_sensor")
    r=air_treatment_plan(a,BASE,DEVICES,{"status":"neutral"},
        outside_safe=False,settings={"pm25_sensor_verified":True})
    assert r["filtration"]["status"]=="no_particle_demand"
    assert not r["filtration"]["speed_control_eligible"]
    r=air_treatment_plan(a,BASE,DEVICES,{"status":"neutral"},
        outside_safe=False,settings={"pm25_entity":"sensor.first","pm25_sensor_verified":True})
    assert r["filtration"]["speed_control_eligible"]
    r=air_treatment_plan((sample("pm25",None),),BASE,DEVICES,
        {"status":"neutral"},outside_safe=True,settings=CFG)
    assert r["measurements"]["pm25_quality"]=="invalid_or_stale_reading"
    assert r["filtration"]["status"]=="no_particle_demand"


def test_invalid_threshold_and_device_unavailable_cannot_drive_fans():
    invalid=air_treatment_plan((),BASE,DEVICES,{"status":"unavailable"},
        outside_safe=False,settings={"pm25_action_ug_m3":-12})
    assert invalid["status"]=="invalid_settings"
    absent=air_treatment_plan((sample("pm25",90),),BASE,
        {"inventory":{"purifier_fan_entity":{"status":"unavailable","entity_id":"fan.filter"}}},
        {"status":"neutral"},outside_safe=False,settings=CFG)
    assert absent["filtration"]["status"]=="recommended"
    assert not absent["filtration"]["speed_control_eligible"]
