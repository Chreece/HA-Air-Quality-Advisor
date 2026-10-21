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
