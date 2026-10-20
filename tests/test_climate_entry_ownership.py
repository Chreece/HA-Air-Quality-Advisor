"""Cross-config-entry equipment ownership cannot race two HA managers.

Pure, fake Home Assistant registry tests. No service writes or real hardware.
"""
from types import SimpleNamespace

import pytest

from test_discovery import FakeHass,MockState,adapter


@pytest.fixture
def guard(adapter):
    from custom_components.air_quality_advisor import climate_entry_ownership
    return climate_entry_ownership


def entry(entry_id,*,climate=None,pid=None,disabled=False):
    return SimpleNamespace(
        entry_id=entry_id,
        disabled_by="user" if disabled else None,
        data={"climate_rooms":climate or {},
              "pid_rooms":pid or {}},
        options={},
    )


def home(*profiles):
    actual=MockState("climate.living","heat")
    actual.attributes.update({"hvac_modes":["off","heat"],
                              "hvac_action":"idle","supported_features":1})
    h=FakeHass([actual],{actual.entity_id:"living"})
    h.config_entries=SimpleNamespace(async_entries=lambda domain: list(profiles))
    return h


def test_multiple_roles_in_one_entry_are_not_a_collision(guard):
    cfg={"enabled":True,"allow_actuation":True,"controller":"device",
         "climate_entity":"climate.living",
         "heat_climate_entity":"climate.living"}
    h=home(entry("first",climate={"living":cfg}))
    assert guard.other_entry_output_owners(h,"first")=={}
    assert guard.cross_entry_collisions(h,"first",{"living":cfg})=={}
    assert guard.foreign_owner_hold(h,"first","climate.living") is None


def test_second_active_entry_claim_blocks_both_controllers(guard):
    original={"enabled":True,"allow_actuation":True,"controller":"device",
              "climate_entity":"climate.living"}
    foreign={"enabled":True,"allow_actuation":True,"controller":"device",
             "heat_climate_entity":"climate.living"}
    h=home(entry("alpha",climate={"living":original}),
           entry("beta",climate={"living":foreign}))
    assert guard.foreign_owner_hold(h,"alpha","climate.living")=="cross_entry_equipment_owner"
    assert guard.foreign_owner_hold(h,"beta","climate.living")=="cross_entry_equipment_owner"
    conflict=guard.cross_entry_collisions(h,"alpha",{"living":original})
    assert conflict=={"climate.living":["beta:living"]}
    assert guard.cross_entry_collisions(h,"beta",{"living":foreign})=={
        "climate.living":["alpha:living"],
    }


def test_disabled_entries_and_disabled_room_do_not_block(guard):
    cfg={"enabled":True,"allow_actuation":True,"climate_entity":"climate.living"}
    h=home(entry("alpha",climate={"living":cfg}),
           entry("beta",climate={"living":cfg},disabled=True),
           entry("gamma",climate={"living":{**cfg,"enabled":False}}))
    assert guard.foreign_owner_hold(h,"alpha","climate.living") is None


def test_cross_entry_pid_and_native_cannot_share_target(guard):
    cfg={"enabled":True,"allow_actuation":True,"climate_entity":"climate.living"}
    h=home(entry("alpha",climate={"living":cfg}),
           entry("beta",pid={"living":{
               "enabled":True,"climate_entities":["climate.living"],
           }}))
    assert guard.foreign_owner_hold(h,"alpha","climate.living")=="cross_entry_equipment_owner"
    assert guard.foreign_owner_hold(h,"beta","climate.living")=="cross_entry_equipment_owner"
    h.config_entries=SimpleNamespace(async_entries=lambda domain:[
        entry("alpha",climate={"living":cfg}),
        entry("beta",pid={"living":{
            "enabled":True,"allow_actuation":True,"climate_entity":"climate.living",
        }}),
    ])
    assert guard.foreign_owner_hold(h,"alpha","climate.living")=="cross_entry_equipment_owner"


def test_cross_entry_direct_output_is_never_owned_twice(guard):
    cfg={"enabled":True,"allow_actuation":True,"controller":"on_off",
         "heat_actuator":"switch.living_heat"}
    foreign={"enabled":True,"allow_actuation":True,"controller":"on_off",
             "heat_actuator":"switch.living_heat"}
    h=home(entry("alpha",climate={"living":cfg}),
           entry("beta",climate={"kitchen":foreign}))
    assert guard.active_output_entities(cfg)=={"switch.living_heat"}
    assert guard.cross_entry_collisions(h,"alpha",{"living":cfg})=={
        "switch.living_heat":["beta:kitchen"],
    }


def test_live_gate_revokes_cached_thermal_permission_after_new_entry_claim(guard):
    from custom_components.air_quality_advisor.climate_arbitration import (
        new_command_gate,room_coordination,
    )
    from test_climate_arbitration import report,config
    # Use a real selected primary thermostat from the shared pure tests.
    primary=MockState("climate.radiator","heat")
    primary.attributes.update({"hvac_modes":["off","heat"],
                               "hvac_action":"idle","supported_features":1})
    ac=MockState("climate.ac","off")
    ac.attributes.update({"hvac_modes":["off","cool"],
                          "hvac_action":"idle","supported_features":1})
    window=MockState("binary_sensor.window","off",device_class="window")
    h=FakeHass([primary,ac,window],{
        primary.entity_id:"room",ac.entity_id:"room",
        window.entity_id:"room",
    })
    current={"enabled":True,"allow_actuation":True,"controller":"device",
             "climate_entity":"climate.radiator",
             "cool_climate_entity":"climate.ac"}
    foreign={"enabled":True,"allow_actuation":True,"controller":"device",
             "climate_entity":"climate.radiator"}
    h.config_entries=SimpleNamespace(async_entries=lambda _: [
        entry("alpha",climate={"room":current}),
    ])
    plan=report()
    approved=room_coordination(h,"room",current,plan,now=1040)
    assert approved["channels"]["thermal"]["status"]=="eligible"
    plan["coordination"]=approved
    assert new_command_gate(h,"room",current,plan,"thermal",
                            "climate.radiator",now=1040,
                            entry_id="alpha") is None
    # No re-plan was performed after a second config entry loaded.
    h.config_entries=SimpleNamespace(async_entries=lambda _: [
        entry("alpha",climate={"room":current}),
        entry("beta",climate={"room":foreign}),
    ])
    assert new_command_gate(h,"room",current,plan,"thermal",
                            "climate.radiator",now=1040,
                            entry_id="alpha")=="cross_entry_equipment_owner"


def test_broken_home_assistant_entry_registry_fails_closed(guard):
    h=home()
    h.config_entries=SimpleNamespace(
        async_entries=lambda _domain: (_ for _ in ()).throw(RuntimeError("offline"))
    )
    assert guard.foreign_owner_hold(h,"alpha","climate.living")==(
        "other_config_entries_unverifiable"
    )
    cfg={"enabled":True,"allow_actuation":True,"climate_entity":"climate.living"}
    assert guard.cross_entry_collisions(h,"alpha",{"living":cfg})=={
        "climate.living":["other_config_entries_unverifiable"],
    }


def test_loaded_entry_options_override_old_config_data(guard):
    old={"enabled":True,"allow_actuation":True,"climate_entity":"climate.living"}
    no={"enabled":False,"climate_entity":"climate.living"}
    other=entry("beta",climate={"living":old})
    other.options={"climate_rooms":{"living":no}}
    h=home(entry("alpha"),other)
    assert guard.other_entry_output_owners(h,"alpha")=={}



def test_advisory_only_other_entry_does_not_claim_controlled_hardware(guard):
    controlled={"enabled":True,"allow_actuation":True,
                "climate_entity":"climate.living"}
    advisory={"enabled":True,"allow_actuation":False,
              "climate_entity":"climate.living"}
    h=home(entry("main",climate={"living":controlled}),
           entry("monitor",climate={"living":advisory}))
    assert guard.foreign_owner_hold(h,"main","climate.living") is None
    assert guard.cross_entry_collisions(h,"main",{"living":controlled})=={}
    assert guard.cross_entry_collisions(h,"monitor",{"living":advisory})=={}
