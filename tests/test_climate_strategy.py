"""Scientific comfort bands and actuator safeguards, no fake climate devices."""
import pytest
from custom_components.air_quality_advisor.climate_strategy import (
    profiles,occupied_evidence,home_away_evidence,select_profile,
    capabilities,auto_mode,policy,relay_demand,guarded_transition,pwm_slot,
)
CFG={"enabled":True,"controller":"device","mode":"auto"}
DEVICE={"kind":"climate","heat":True,"cool":True,"setpoint":True}
def test_default_profiles_keep_heating_and_cooling_separate():
    p,err=profiles({})
    assert err is None and p["home"].heat_c==20 and p["home"].cool_c==26
    assert profiles({"profiles":{"home":{"heat_c":25,"cool_c":25}}})[1]
def test_presence_does_not_invent_vacancy():
    assert occupied_evidence([False,False])[0]=="unoccupied"
    assert occupied_evidence([False,True])[0]=="occupied"
    assert occupied_evidence([False,None])[0]=="occupied"
    assert occupied_evidence([False,None],unknown_policy="hold")[0]=="unknown"
def test_global_away_requires_all_people_away():
    assert home_away_evidence([False,False])[0]=="away"
    assert home_away_evidence([True,False])[0]=="home"
    assert home_away_evidence([False,None])[0]=="home"
    assert home_away_evidence([],mode="all_home")[0]=="home"
def test_profile_priority_away_vs_occupancy_vs_sleep():
    assert select_profile({},at_home="away",occupied="occupied")[0]=="away"
    assert select_profile({},at_home="home",occupied="unoccupied")[0]=="unoccupied"
    assert select_profile({},at_home="home",occupied="occupied",sleeping=True)[0]=="sleep"
    assert select_profile({},at_home="away",occupied="occupied",manual="home")[0]=="home"
def test_auto_mode_schmitt_prevents_short_cycling():
    assert auto_mode(19,20,26,None)[0]=="heat"
    assert auto_mode(20.2,20,26,"heat")[0]=="heat"
    assert auto_mode(23,20,26,"heat")[0]=="off"
    assert auto_mode(27,20,26,None)[0]=="cool"
    assert auto_mode(25.8,20,26,"cool")[0]=="cool"
    assert auto_mode(23,23,23,None)[0] is None
def test_policy_device_is_conservative_and_capability_gated():
    p=policy(CFG,temp_c=19,capability=DEVICE,at_home="home",occupied="occupied")
    assert (p.state,p.desired_hvac_mode,p.temperature_c)==("ready","heat",20)
    assert policy(CFG,temp_c=27,capability=DEVICE,at_home="home",occupied="occupied").desired_hvac_mode=="cool"
    assert policy(CFG,temp_c=23,capability=DEVICE,at_home="home",occupied="unoccupied").profile=="unoccupied"
    assert policy(CFG,temp_c=18,capability=DEVICE,at_home="away",occupied="occupied").profile=="away"
    assert policy(CFG,temp_c=19,capability=DEVICE,at_home="home",occupied="occupied",window_safe=False).state=="hold"
    assert policy(CFG,temp_c=27,capability={**DEVICE,"cool":False},at_home="home",occupied="occupied").state=="hold"
    assert policy({**CFG,"controller":"pwm"},temp_c=19,capability=DEVICE,at_home="home",occupied="occupied").state=="unsupported_device"
    assert policy({**CFG,"controller":"setpoint_pid","native_pid":True},temp_c=19,capability=DEVICE,at_home="home",occupied="occupied").state=="conflicting_controllers"
def test_comfort_ranges_not_a_universal_medical_target():
    res=policy(CFG,temp_c=16,capability=DEVICE,at_home="home",occupied="occupied",manual_profile="sleep")
    assert res.profile=="sleep" and res.temperature_c==18
def test_device_native_feature_detection():
    caps=capabilities({"supported_features":3,"hvac_modes":["off","heat","cool","heat_cool"]},"heat")
    assert caps["heat"] and caps["cool"] and caps["setpoint"] and caps["range"]
def test_onoff_hysteresis_and_minimum_dwell():
    assert relay_demand(19,20,"heat",previous_on=False)
    assert relay_demand(20.2,20,"heat",previous_on=True)
    assert not relay_demand(20.4,20,"heat",previous_on=True)
    assert guarded_transition(demand_on=False,current_on=True,now=120,last_changed=100,min_on_s=60,min_off_s=300)[0]=="minimum_on_hold"
    assert guarded_transition(demand_on=True,current_on=False,now=400,last_changed=100,min_on_s=60,min_off_s=300)[0]=="transition"
    assert guarded_transition(demand_on=True,current_on=True,now=999,last_changed=0,min_on_s=60,min_off_s=60,maximum_on_s=900)[0]=="maximum_runtime_exceeded"
def test_pwm_respects_cycle_and_minimum_pulses():
    assert pwm_slot(50,period_s=900,now_s=110,anchor_s=0,min_on_s=120,min_off_s=120)==("ready",True)
    assert pwm_slot(50,period_s=900,now_s=700,anchor_s=0,min_on_s=120,min_off_s=120)==("ready",False)
    assert pwm_slot(5,period_s=900,now_s=200,anchor_s=0,min_on_s=120,min_off_s=120)[0]=="pulse_too_short"
    assert pwm_slot(100,period_s=900,now_s=200,anchor_s=0,min_on_s=120,min_off_s=120)==("on",True)

def test_native_heat_cool_range_uses_two_device_targets_not_external_pid():
    caps={"kind":"climate","heat":False,"cool":False,"range":True,
          "auto":True,"modes":["off","heat_cool"]}
    result=policy({"enabled":True,"controller":"device","mode":"auto"},
                  temp_c=19,capability=caps,at_home="home",occupied="occupied")
    assert result.state=="ready"
    assert result.desired_hvac_mode=="heat_cool"
    assert result.temperature_c is None
    assert (result.range_low_c,result.range_high_c)==(20,26)
    # PMV may only adjust within explicit bounded homeowner comfort limits.
    pmv=policy({"enabled":True,"controller":"device","mode":"auto",
                "target_source":"pmv","comfort_adjustment_max_c":1.5},
                temp_c=19,capability=caps,at_home="home",occupied="occupied",
                comfort_target_c=24)
    assert pmv.range_low_c==21.5
    assert pmv.range_high_c==24.5  # PMV may lower the cooling threshold by at most 1.5°C
    no_native=policy({"enabled":True,"controller":"device","mode":"auto",
                      "prefer_native_auto":False},
                     temp_c=19,capability=caps,at_home="home",occupied="occupied")
    assert no_native.state=="unsupported_mode"


def test_one_mode_heat_only_cool_only_and_dry_only_are_first_class():
    heat={"kind":"climate","heat":True,"cool":False,"dry":False,
          "setpoint":True,"modes":["heat"]}
    cool={"kind":"climate","heat":False,"cool":True,"dry":False,
          "setpoint":True,"modes":["cool"]}
    dryer={"kind":"climate","heat":False,"cool":False,"dry":True,
           "setpoint":False,"modes":["dry"]}
    base={"enabled":True,"controller":"device","mode":"auto"}
    cold=policy(base,temp_c=18,capability=heat,at_home="home",occupied="occupied")
    assert cold.state=="ready" and cold.desired_hvac_mode=="heat"
    hot=policy(base,temp_c=28,capability=heat,at_home="home",occupied="occupied")
    assert hot.state=="hold" and "no_configured_cool" in hot.reason
    hot=policy(base,temp_c=28,capability=cool,at_home="home",occupied="occupied")
    assert hot.state=="ready" and hot.desired_hvac_mode=="cool"
    cold=policy(base,temp_c=18,capability=cool,at_home="home",occupied="occupied")
    assert cold.state=="hold" and "no_configured_heat" in cold.reason
    only_dry=policy({**base,"mode":"dry"},temp_c=None,
                    capability=dryer,at_home="home",occupied="occupied")
    assert only_dry.state=="advisory"
    assert only_dry.desired_hvac_mode=="dry"
    assert only_dry.temperature_c is None
    assert policy({**base,"mode":"dry"},temp_c=None,capability=heat,
                  at_home="home",occupied="occupied").state=="unsupported_mode"
    assert policy({**base,"mode":"dry","controller":"environment"},
                  temp_c=None,capability=dryer,
                  at_home="home",occupied="occupied").state=="advisory"
