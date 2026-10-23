"""Beta19 domain migration and room preset semantics."""
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

def test_room_profile_migration_and_eco():
    parsed,problem=profiles({"profiles":{
        "home":{"heat_c":20,"cool_c":26},
        "unoccupied":{"heat_c":18,"cool_c":28},
    }})
    assert problem is None
    assert parsed["comfort"].heat_c==20
    assert parsed["home"].heat_c==18
    assert parsed["eco"].heat_c==17

def test_new_domain_and_legacy_constant():
    from custom_components.environment_manager.const import DOMAIN,LEGACY_DOMAIN
    assert DOMAIN=="environment_manager"
    assert LEGACY_DOMAIN=="air_quality_advisor"
