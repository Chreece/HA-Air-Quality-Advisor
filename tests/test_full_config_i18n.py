"""Audit EVERY visible Home Assistant options/configuration field.

The generator must ship both a translated field name and a useful per-field
data_description. Earlier releases had 22 thresholds without *any* help and
many climate fields inherited vague English placeholders even in Greek.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from custom_components.air_quality_advisor.languages import SUPPORTED_LANGUAGE_TAGS

ROOT=Path(__file__).resolve().parents[1]
COMP=ROOT/"custom_components"/"air_quality_advisor"
LOCALES=COMP/"translations"
NEUTRAL=("AQI","CO₂","PM2.5","PM10","VOC","HCHO","NO₂","SO₂","O₃")
GENERIC=("Device/source-specific configuration.",
         "Select source; Required", "Choose explicit Home Assistant entities.")
CRITICAL={
    "options": {
        "thresholds":("outdoor_aqi","outdoor_pm25","outdoor_no2",
                      "indoor_co2","indoor_humidity","max_age_minutes"),
        "climate_presence":("climate_occupancy_stale_minutes",
                            "climate_unoccupied_delay_minutes","climate_sleep_start"),
        "climate_equipment":("climate_dry_fan_mode_auto",
                             "climate_humidity_power_hardware_confirmed"),
        "climate_actuators":("kp","min_off_s","pwm_period_s"),
        "pid_tuning":("pid_kp","pid_ki","pid_sample_seconds"),
        "device_settings":("device_auto_control","device_absence_action",
                           "device_min_off_s","device_sleep_heat_c"),
    },
    "config":{"thresholds":("indoor_co2","outdoor_pm25","max_age_minutes")}
}

def _docs():
    return {
        lang:json.loads((LOCALES/f"{lang}.json").read_text(encoding="utf-8"))
        for lang in SUPPORTED_LANGUAGE_TAGS
    }

def test_all_38_languages_explain_every_visible_field():
    docs=_docs()
    assert len(docs)==38
    expected=docs["en"]
    total=0
    for lang,doc in docs.items():
        for scope in ("config","options"):
            assert set(doc[scope]["step"])==set(expected[scope]["step"]),lang
            for step,eng in expected[scope]["step"].items():
                locale=doc[scope]["step"][step]
                fields=eng.get("data",{})
                if not fields:
                    continue
                assert set(locale.get("data",{}))==set(fields),(lang,scope,step)
                helps=locale.get("data_description",{})
                assert set(fields)<=set(helps),(lang,scope,step,
                                                set(fields)-set(helps))
                for key in fields:
                    title=locale["data"][key]
                    help_text=helps[key]
                    assert isinstance(title,str) and title.strip(),(
                        lang,scope,step,key,"no field label")
                    minimum=18 if lang in ("ja","ko","zh-Hans","zh-Hant","th") else 35
                    assert isinstance(help_text,str) and len(help_text.strip())>=minimum,(
                        lang,scope,step,key,"no useful explanation")
                    assert not help_text.startswith(GENERIC),(
                        lang,scope,step,key,"placeholder help")
                    total+=1
    assert total>=38*300  # every one of ~321 fields in config/options

def test_no_english_or_placeholder_help_for_critical_greek_fields():
    docs=_docs()
    greek=docs["el"]
    english=docs["en"]
    for scope,sections in CRITICAL.items():
        for step,names in sections.items():
            el=greek[scope]["step"][step]
            en=english[scope]["step"][step]
            for name in names:
                help_text=el["data_description"][name]
                assert help_text!=en["data_description"][name],(scope,step,name)
                assert re.search(r"[α-ωά-ώ]",help_text,re.IGNORECASE),(
                    scope,step,name,help_text)
                assert "Επιλογή πηγή" not in help_text
                assert "Device/source-specific" not in help_text
    assert "λεπτά" in greek["options"]["step"]["thresholds"]["data_description"]["max_age_minutes"]

def test_detailed_bilingual_help_and_generic_locales_have_correct_sources():
    for name in ("full_config_help_core.json",
                 "full_config_help_climate.json",
                 "full_config_help_science.json"):
        spec=json.loads((COMP/name).read_text(encoding="utf-8"))
        assert spec
        for key,record in spec.items():
            assert set(record)=={"en","el"},key
            assert min(map(len,record.values()))>=60,key
    locale=json.loads((COMP/"full_config_help_templates.json").read_text(encoding="utf-8"))
    assert set(locale)==set(SUPPORTED_LANGUAGE_TAGS)
    for lang,templates in locale.items():
        assert set(templates)=={"source","threshold","control","timing",
                                "profile","science","generic","error"},lang
        assert all("{label}" in t for t in templates.values()),lang

def test_generator_runs_full_audit_after_all_legacy_generators():
    generator=(ROOT/"generate_translations.py").read_text(encoding="utf-8")
    assert generator.index("apply_full_config_i18n(root)") > generator.index(
        "apply_compact_i18n(root)")
    layer=(ROOT/"apply_full_config_i18n.py").read_text(encoding="utf-8")
    assert 'original_help = original.get("data_description", {})' in layer
    assert '"full_config_help_climate.json"' in layer



def test_no_english_field_copy_in_localized_configuration_forms():
    """Catch translations that have all the right keys but show English UI."""
    docs=_docs()
    english=docs["en"]
    for lang, doc in docs.items():
        if lang=="en":
            continue
        for scope in ("config","options"):
            for step,en_step in english[scope]["step"].items():
                localized=doc[scope]["step"][step]
                for key,english_name in en_step.get("data",{}).items():
                    if english_name in NEUTRAL:
                        continue
                    assert localized["data"][key]!=english_name,(
                        lang,scope,step,key,"untranslated label")
                    assert localized["data_description"][key]!=(
                        english[scope]["step"][step]["data_description"][key]
                    ),(lang,scope,step,key,"untranslated help")


def test_shipped_english_catalog_equals_home_assistant_strings():
    strings=json.loads((COMP/"strings.json").read_text(encoding="utf-8"))
    english=json.loads((LOCALES/"en.json").read_text(encoding="utf-8"))
    assert strings==english


def test_all_22_advanced_limits_explain_direction_units_and_operational_purpose():
    docs=_docs()
    english=docs["en"]
    greek=docs["el"]
    for scope in ("config","options"):
        en=english[scope]["step"]["thresholds"]
        el=greek[scope]["step"]["thresholds"]
        assert len(en["data"])==22
        assert set(en["data_description"])==set(en["data"])
        assert set(el["data_description"])==set(el["data"])
        for key,help_text in en["data_description"].items():
            assert len(help_text)>=75,key
            greek_text=el["data_description"][key]
            assert len(greek_text)>=70,key
            assert re.search(r"[α-ωά-ώ]",greek_text,re.IGNORECASE),key
    # The freshness limit is a data-age bound, not a sleep duration or
    # proof of safe outdoor air.
    assert "λεπτά" in greek["options"]["step"]["thresholds"]["data_description"]["max_age_minutes"]


def test_climate_safety_descriptions_do_not_look_like_translation_placeholders():
    el=_docs()["el"]["options"]["step"]
    for section,field,word in (
        ("climate_equipment","climate_dry_fan_hardware_confirmed","συμπιεστή"),
        ("climate_equipment","climate_window_efficiency_notify","παραθύρων"),
        ("climate_air_strategy","climate_fan_power_auto","ON/OFF"),
        ("climate_actuators","direct_hardware_confirmed","συμπιεστή"),
        ("climate_presence","climate_sleep_schedule_enabled","ύπνου"),
        ("device_settings","device_absence_action","ΑΠΕΝΕΡΓΟΠΟΙΗΣΗ"),
    ):
        desc=el[section]["data_description"][field]
        assert word.lower() in desc.lower(),(section,field,desc)


def test_device_and_climate_fields_are_unambiguous_in_all_38_locales():
    """Distinct HVAC targets, source and PID buttons must never share a label."""
    docs=_docs()
    for lang,doc in docs.items():
        for scope in ("config","options"):
            for step,values in doc[scope]["step"].items():
                fields=values.get("data",{})
                shown=list(fields.values())
                assert len(shown)==len(set(shown)),(
                    lang,scope,step,"ambiguous labels",
                    {caption:[k for k,v in fields.items() if v==caption]
                     for caption in shown if shown.count(caption)>1}
                )
        room=doc["options"]["step"]["climate_profiles"]["data"]
        assert room["home_heat"]!=room["home_cool"],lang
        assert room["away_heat"]!=room["home_heat"],lang
        assert room["sleep_heat"]!=room["sleep_cool"],lang
        pid=doc["options"]["step"]["pid_tuning"]["data"]
        assert len({pid["pid_kp"],pid["pid_ki"],pid["pid_kd"]})==3,lang
