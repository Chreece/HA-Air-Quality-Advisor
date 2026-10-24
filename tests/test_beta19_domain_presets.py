"""Room preset semantics and canonical domain."""
from types import SimpleNamespace
from custom_components.environment_manager import equipment_model as model
from custom_components.environment_manager.climate_strategy import select_profile, profiles

def test_automatic_profile_semantics():
    assert select_profile({},at_home="home",occupied="occupied")[0]=="comfort"
    assert select_profile({},at_home="home",occupied="unoccupied")[0]=="home"
    assert select_profile({},at_home="away",occupied="unoccupied")[0]=="away"
    assert select_profile({},at_home="home",occupied="occupied",sleeping=True)[0]=="sleep"
    assert select_profile({},at_home="unknown",occupied="unknown")[0]=="home"
    assert select_profile({},at_home="home",occupied="occupied",manual="eco")[0]=="eco"

def test_canonical_room_profiles_and_eco_defaults():
    parsed,problem=profiles({"profiles":{
        "comfort":{"heat_c":21,"cool_c":25},
        "home":{"heat_c":19,"cool_c":27},
    }})
    assert problem is None
    assert parsed["comfort"].heat_c==21
    assert parsed["home"].heat_c==19
    assert parsed["away"].heat_c==16
    assert parsed["eco"].heat_c==17

def test_canonical_domain_only():
    from custom_components.environment_manager.const import DOMAIN
    assert DOMAIN=="environment_manager"
