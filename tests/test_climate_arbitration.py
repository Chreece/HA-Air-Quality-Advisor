"""Unified purpose-based arbitration: decision AND live write-time authority."""
import pytest

from test_discovery import FakeHass, MockState, adapter


@pytest.fixture
def arbi(adapter):
    from custom_components.environment_manager import climate_arbitration
    return climate_arbitration


def environment(*, ac="off", action="idle", rh=65,
                humidifier="off", dehumidifier="off",
                extractor="off", purifier="off"):
    heat=MockState("climate.radiator","heat")
    heat.attributes.update({"hvac_modes":["off","heat"],"supported_features":1,
                            "hvac_action":"idle"})
    cooling=MockState("climate.ac",ac)
    cooling.attributes.update({"hvac_modes":["off","cool","dry"],"supported_features":1,
                               "hvac_action":action})
    dry=MockState("humidifier.dry",dehumidifier,device_class="dehumidifier")
    humid=MockState("humidifier.hum",humidifier,device_class="humidifier")
    extract=MockState("fan.extract",extractor)
    filter_=MockState("fan.filter",purifier)
    windows=MockState("binary_sensor.window","off",device_class="window")
    rh_sensor=MockState("sensor.rh",rh,device_class="humidity",unit="%")
    items=[heat,cooling,dry,humid,extract,filter_,windows,rh_sensor]
    return FakeHass(items,{x.entity_id:"room" for x in items})


def config(**more):
    return {
        "enabled":True,"controller":"device","climate_entity":"climate.radiator",
        "cool_climate_entity":"climate.ac",
        "dehumidifier_entity":"humidifier.dry",
        "humidifier_entity":"humidifier.hum",
        "humidity_entity":"sensor.rh",
        "humidity_high_rh":60,
        "extraction_fan_entity":"fan.extract",
        "purifier_fan_entity":"fan.filter",
        **more,
    }


def report(*, mode="heat", rh=65, thermal_role="climate_entity",
           moisture_action="dry", extraction=True, filtration=True,
           time=1000):
    owner="climate.ac" if mode=="cool" else "climate.radiator"
    return {
        "status":"ready", "mode":mode, "window_safe":True,
        "window_contacts":["binary_sensor.window"],
        "equipment_plan":{
            "status":"ready",
            "thermal":{"status":"selected","entity_id":owner,"role":thermal_role,
                       "mode":mode},
            "humidity":{"status":"advisory","action":moisture_action,
                        "measured_rh":rh},
            "moisture":{"status":"selected","action":moisture_action,
                        "role":("dehumidifier_entity" if moisture_action=="dry"
                                else "humidifier_entity"),
                        "entity_id":("humidifier.dry" if moisture_action=="dry"
                                     else "humidifier.hum")},
        },
        "air_evidence_at":time,
        "air_actions":{
            "status":"advisory","outdoor_air_verified":True,
            "extraction":{
                "status":"recommended" if extraction else "no_ventilation_demand",
                "entity_id":"fan.extract",
                "speed_control_eligible":extraction,
            },
            "filtration":{
                "status":"recommended" if filtration else "no_particle_demand",
                "entity_id":"fan.filter",
                "speed_control_eligible":filtration,
            },
        },
        "window_efficiency":{"status":"opportunity","effect":"cool"},
    }


def test_heat_only_primary_and_co2_extraction_have_separate_permissions(arbi):
    h=environment()
    plan=report()
    result=arbi.room_coordination(h,"room",config(),plan,now=1030)
    assert result["status"]=="ready"
    assert result["priority"]=="measured_co2_ventilation"
    assert result["channels"]["thermal"] == {
        "status":"eligible","entity_id":"climate.radiator",
        "purpose":"heat","controller":"climate",
    }
    assert result["channels"]["extraction"]["status"]=="eligible"
    assert result["channels"]["filtration"]["status"]=="eligible"
    assert result["mechanical_mode_changes_allowed"] is False


def test_armed_opposing_ac_blocks_heat_even_while_idle(arbi):
    h=environment(ac="cool",action="idle")
    result=arbi.room_coordination(h,"room",config(),report(),now=1050)
    assert result["channels"]["thermal"]["reason"]=="opposing_native_mode_armed"
    h.states.get("climate.ac").state="off"
    assert arbi.room_coordination(
        h,"room",config(),report(),now=1050)["channels"]["thermal"]["status"]=="eligible"


def test_cooling_defers_noncritical_drying_but_does_not_misrepresent_critical_rh(arbi):
    h=environment(ac="cool",rh=66)
    proposal=report(mode="cool",thermal_role="cool_climate_entity",rh=66,
                    extraction=False,filtration=False)
    decision=arbi.room_coordination(h,"room",config(),proposal,now=1010)
    assert decision["channels"]["humidity"]["reason"]=="cooling_priority_observe_rh"
    severe=arbi.room_coordination(h,"room",config(),{
        **proposal,
        "equipment_plan":{**proposal["equipment_plan"],
                          "humidity":{"status":"advisory","action":"dry",
                                      "measured_rh":79}},
    },now=1010)
    assert severe["channels"]["humidity"]["status"]=="eligible"
    assert severe["channels"]["humidity"]["purpose"]=="dry"


def test_drying_climate_armed_prevents_separate_dehumidifier_authority(arbi):
    h=environment(ac="dry",action="idle")
    res=arbi.room_coordination(h,"room",config(),report(),now=1010)
    assert res["channels"]["humidity"]["reason"]=="native_ac_drying_armed"


def test_cooling_prevents_humidifier_or_opposing_device(arbi):
    h=environment(ac="cool")
    p=report(mode="cool",rh=25,thermal_role="cool_climate_entity",
             moisture_action="humidify")
    res=arbi.room_coordination(h,"room",config(),p,now=1010)
    assert res["channels"]["humidity"]["reason"]=="cooling_conflicts_with_humidification"
    h.states.get("humidifier.dry").state="on"
    res=arbi.room_coordination(h,"room",config(),p,now=1010)
    assert res["channels"]["humidity"]["reason"]=="opposing_humidity_device"


def test_air_quality_extraction_requires_safety_but_filtering_independent(arbi):
    h=environment()
    p=report()
    p["air_actions"]["outdoor_air_verified"]=False
    results=arbi.room_coordination(h,"room",config(),p,now=1050)["channels"]
    assert results["extraction"]["reason"]=="outdoor_air_not_verified"
    assert results["filtration"]["status"]=="eligible"
    h.states.get("binary_sensor.window").state="on"
    results=arbi.room_coordination(h,"room",config(),p,now=1050)["channels"]
    assert results["extraction"]["reason"]=="window_open_or_unknown"
    assert results["thermal"]["reason"]=="open_or_unknown_window"
    assert results["filtration"]["status"]=="eligible"


def test_automatic_power_blocked_for_expired_air_plan(arbi):
    h=environment()
    p=report()
    res=arbi.room_coordination(h,"room",config(),p,now=1201)
    assert res["channels"]["extraction"]["reason"]=="air_policy_expired"
    assert res["channels"]["filtration"]["reason"]=="air_policy_expired"


def test_cached_grant_not_authority_after_live_climate_or_window_change(arbi):
    h=environment()
    cfg=config()
    p=report()
    p["coordination"]=arbi.room_coordination(h,"room",cfg,p,now=1030)
    assert arbi.new_command_gate(
        h,"room",cfg,p,"thermal","climate.radiator",now=1030
    ) is None
    h.states.get("climate.ac").state="cool"
    assert arbi.new_command_gate(
        h,"room",cfg,p,"thermal","climate.radiator",now=1040
    )=="opposing_native_mode_armed"
    h.states.get("climate.ac").state="off"
    h.states.get("binary_sensor.window").state="on"
    assert arbi.new_command_gate(
        h,"room",cfg,p,"thermal","climate.radiator",now=1040
    )=="open_or_unknown_window"


def test_grant_never_authorizes_another_entity_or_unplanned_channel(arbi):
    h=environment()
    cfg=config()
    p=report()
    p["coordination"]=arbi.room_coordination(h,"room",cfg,p,now=1030)
    assert arbi.new_command_gate(h,"room",cfg,p,
                                "humidity","humidifier.hum",now=1030
    )=="coordination_plan_not_authorized"
    assert arbi.new_command_gate(h,"room",cfg,p,
                                "nonsense","climate.radiator",now=1030
    )=="invalid_coordination_request"
    # Older unit controller tests deliberately pass a minimal plan.
    assert arbi.new_command_gate(h,"room",cfg,report(),
                                "thermal","climate.radiator",now=1030) is None


def test_ambiguous_global_ownership_holds_every_new_room_function(arbi):
    h=environment()
    p=report()
    p["equipment_plan"]["status"]="duplicate_equipment_owner"
    result=arbi.room_coordination(h,"room",config(),p)
    assert all(v["status"]=="held" for v in result["channels"].values())
    assert result["priority"]=="safety"


def test_direct_slow_load_is_not_confused_with_a_native_climate(arbi):
    h=environment()
    active=MockState("switch.radiator","off")
    h._values[active.entity_id]=active
    h._entity_areas[active.entity_id]="room"
    cfg=config(controller="on_off",heat_actuator=active.entity_id,
               climate_entity=None,cool_climate_entity=None)
    p=report()
    p["equipment_plan"]["thermal"]={"status":"no_thermal_demand"}
    decision=arbi.room_coordination(h,"room",cfg,p,now=1020)
    assert decision["channels"]["thermal"]["status"]=="eligible"
    assert decision["channels"]["thermal"]["entity_id"]=="switch.radiator"


def test_window_savings_remains_advice_not_power_permission(arbi):
    h=environment()
    p=report(mode="off")
    p["equipment_plan"]["thermal"]={"status":"no_thermal_demand"}
    p["equipment_plan"]["moisture"]={"status":"within_band"}
    p["air_actions"]["extraction"]["status"]="no_ventilation_demand"
    p["air_actions"]["filtration"]["status"]="no_particle_demand"
    result=arbi.room_coordination(h,"room",config(),p,now=1050)
    assert result["status"]=="idle"
    assert result["window_efficiency"]=="opportunity"
    assert result["mechanical_mode_changes_allowed"] is False


def test_cooling_dehumidifier_preference_is_explicit_and_bounded(arbi):
    h=environment(ac="cool",rh=66)
    p=report(mode="cool",thermal_role="cool_climate_entity",rh=66,
             extraction=False,filtration=False)
    no_deferral=arbi.room_coordination(h,"room",config(
        cooling_dry_deferral_rh_points=0),p)
    assert no_deferral["channels"]["humidity"]["status"]=="eligible"
    defer=arbi.room_coordination(h,"room",config(
        cooling_dry_deferral_rh_points=15),p)
    assert defer["channels"]["humidity"]["reason"]=="cooling_priority_observe_rh"
    broken=arbi.room_coordination(h,"room",config(
        cooling_dry_deferral_rh_points=-1),p)
    assert broken["channels"]["humidity"]["reason"]=="invalid_cooling_dry_margin"
