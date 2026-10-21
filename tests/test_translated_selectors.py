"""All Home Assistant fixed-choice climate selectors must be translated.

The stored keys stay identical to earlier releases. The frontend uses
selector.translation_key to show the current user's language, not a hardcoded
English backend label. Runtime options may still be dynamic for actual
HA entities, which are displayed by their device names.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from custom_components.air_quality_advisor.languages import SUPPORTED_LANGUAGE_TAGS
from test_area_config_flow import _make_options
from test_discovery import adapter

ROOT=Path(__file__).resolve().parents[1]
LOCALES=ROOT/"custom_components"/"air_quality_advisor"/"translations"
ENUMS={
    "environment_aqi_scale":("not_configured","us_epa","eea_category","custom"),
    "climate_controller":("device","environment","setpoint_pid","on_off","pwm","proportional"),
    "climate_mode":("auto","heat","cool","dry","off"),
    "climate_unknown_occupancy":("occupied","hold"),
    "climate_away_policy":("any_home","all_home"),
    "climate_manual_profile":("auto","home","unoccupied","away","sleep"),
    "climate_target_source":("temperature","pmv"),
    "pid_mode":("heat","cool"),
}

def test_all_38_locales_have_complete_fixed_choice_translations():
    assert len(SUPPORTED_LANGUAGE_TAGS)==38
    for lang in SUPPORTED_LANGUAGE_TAGS:
        data=json.loads((LOCALES/f"{lang}.json").read_text(encoding="utf-8"))
        for key,values in ENUMS.items():
            choices=data["selector"][key]["options"]
            assert set(choices)==set(values),(lang,key)
            assert all(isinstance(v,str) and v.strip() for v in choices.values())
            assert all(len(v)<110 for v in choices.values()),(lang,key)
    greek=json.loads((LOCALES/"el.json").read_text(encoding="utf-8"))
    assert greek["selector"]["climate_mode"]["options"]["heat"]=="Θέρμανση"
    assert greek["selector"]["climate_mode"]["options"]["cool"]=="Ψύξη"
    assert "συμπιεστή" in greek["selector"]["climate_controller"]["options"]["pwm"]
    assert greek["selector"]["climate_manual_profile"]["options"]["unoccupied"]=="Άδειος χώρος"
    assert greek["selector"]["climate_manual_profile"]["options"]["away"]=="Απουσία από το σπίτι"
    assert greek["selector"]["environment_aqi_scale"]["options"]["not_configured"]=="Δεν έχει οριστεί κλίμακα"
    assert greek["selector"]["pid_mode"]["options"]["heat"]=="Θέρμανση"


def test_climate_and_pid_forms_use_native_translated_selectors(monkeypatch,adapter):
    options=_make_options(monkeypatch,adapter)
    asyncio.run(options.async_step_init())
    asyncio.run(options.async_step_climate({"climate_area":"living"}))
    form=asyncio.run(options.async_step_climate_room())
    for field,key in (("climate_controller","climate_controller"),
                      ("climate_mode","climate_mode")):
        select=form["data_schema"][field].config
        assert select.translation_key==key
        assert all(isinstance(item,str) for item in select.options)
    second=asyncio.run(options.async_step_climate_room({"climate_enabled":False}))
    assert second["step_id"]=="climate_presence"
    for field in ("climate_unknown_occupancy","climate_away_policy",
                  "climate_manual_profile","climate_target_source"):
        assert second["data_schema"][field].config.translation_key==field
    asyncio.run(options.async_step_pid({"pid_area":"living"}))
    pid=asyncio.run(options.async_step_pid_room())
    mode=pid["data_schema"]["pid_mode"].config
    assert mode.translation_key=="pid_mode"
    assert mode.options==["heat","cool"]


def test_fixed_selector_values_remain_backward_compatible():
    manifest=json.loads((ROOT/"custom_components"/"air_quality_advisor"/"manifest.json").read_text())
    assert manifest["domain"]=="air_quality_advisor"
    assert ENUMS["climate_mode"]==("auto","heat","cool","dry","off")
    assert ENUMS["climate_controller"]==(
        "device","environment","setpoint_pid","on_off","pwm","proportional"
    )
