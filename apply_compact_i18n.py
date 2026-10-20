"""Translate compact options in all 38 supported HA locales.

Read-only locale vocabulary lives in compact_locales.json. This script runs
after the historical flow generators to preserve their existing translations.
HA selector option values are machine-readable; translated labels are shipped
separately under selector.<translation_key>.options.
"""
from __future__ import annotations

import json
from pathlib import Path


STEPS = {
    "general_settings": (
        "general_room_occupancy_sensors",
        "general_occupied_rooms_entity", "general_occupied_rooms_attribute",
        "general_home_trackers", "general_home_policy",
        "general_sleep_rooms_entity", "general_sleep_rooms_attribute",
        "general_source_stale_minutes",
    ),
    "pollen": (
        "pollen_entity", "pollen_high_from", "pollen_max_scale",
        "pollen_avoid_ventilation",
    ),
    "outside_aqi": (
        "outside_aqi_entity", "outside_aqi_scale", "outside_aqi_limit",
        "outside_aqi_no_sources",
    ),
    "area_devices": ("area_devices_area",),
    "select_devices": ("selected_devices",),
    "device_choice": ("device_choice",),
    "device_settings": (
        "device_auto_control", "device_method", "device_presence_requirement",
        "device_absence_action", "device_sleep_behavior", "device_hardware_confirmed",
        "device_temperature_entity", "device_humidity_entity",
        "device_co2_entity", "device_pm25_entity", "device_fan_purpose",
        "device_sensor_verified", "device_fan_speed_percent",
        "device_humidity_target", "device_sleep_humidity_target",
        "device_min_on_s", "device_min_off_s", "device_max_on_s",
        *(f"device_{p}_{kind}_c" for p in ("home","unoccupied","away","sleep")
          for kind in ("heat","cool")),
    ),
}

ERROR_FIELDS = {
    "general_invalid_presence":"presence","general_invalid_trackers":"home",
    "general_invalid_rooms_entity":"room","general_invalid_attribute":"source",
    "general_invalid_source_age":"source","invalid_selected_devices":"devices",
    "device_policy_invalid":"presence","device_method_invalid":"control",
    "device_hardware_required":"required","device_power_required_for_off":"power",
    "device_temperature_required":"temperature","device_humidity_required":"humidity",
    "device_air_sensor_required":"sensor","device_temperature_band_invalid":"temperature",
    "device_humidity_invalid":"humidity","device_runtime_invalid":"power",
}

# Carefully checked prominent Greek/German UI strings and explanations.
PRIMARY = {
    "en": {
        "menu": ("Outside data","General settings","Area settings"),
        "descriptions": {
            "outside_data":"Weather, warnings, outdoor pollution, AQI provider scales and pollen. Choose a subsection.",
            "general_settings":"Choose shared presence sensors, home trackers, and entities listing occupied or sleeping rooms. The source can hold a JSON list in its state or in a named attribute. Stale or unknown evidence NEVER means nobody is home.",
            "area_settings":"Choose room monitoring, window exclusions, optional environmental measurements and device-by-device climate control.",
            "pollen":"Select a pollen-index sensor from any Home Assistant provider; declare its published scale and whether high pollen should prevent window advice.",
            "outside_aqi":"Assign a documented AQI provider scale to one sensor at a time. Unknown scales never mean safe outdoor air.",
            "select_devices":"All supported native devices assigned to this HA area are preselected for monitoring. Selecting does NOT authorize any device commands.",
            "device_choice":"Choose exactly one selected device to configure.",
            "device_menu":"Adjust this device's automation, targets and occupancy/sleep settings, or select a different device.",
            "device_settings":"Separate per-device consent. Unknown occupancy only HOLDS control; OFF needs explicit protection confirmation. Native climate OFF is never automatically restarted.",
        },
    },
    "de": {
        "menu": ("Außendaten","Allgemeine Einstellungen","Bereichseinstellungen"),
        "descriptions": {
            "outside_data":"Wetter, Warnungen, Außenluftqualität, AQI-Skalen und Pollen. Wähle einen Unterpunkt.",
            "general_settings":"Präsenzsensoren, Anwesenheitstracker und Sensoren für belegte oder schlafende Räume festlegen. Raumlisten im Zustand oder einem benannten Attribut (z. B. JSON). Fehlende oder alte Werte bedeuten NIEMALS, dass das Haus leer ist.",
            "area_settings":"Raumüberwachung, Fensterausschlüsse, Messungen und Geräte einzeln einstellen.",
            "pollen":"Pollenindex aus einer beliebigen Home-Assistant-Quelle wählen. Skala und optionale Lüftungssperre bei hoher Belastung festlegen.",
            "outside_aqi":"Jedem AQI-Sensor seine dokumentierte Skala zuordnen. Unbekannte Skalen beweisen keine sichere Außenluft.",
            "select_devices":"Alle kompatiblen Geräte dieses HA-Raums werden zur Überwachung vorausgewählt. Die Auswahl erlaubt KEINE Gerätesteuerung.",
            "device_choice":"Genau ein ausgewähltes Gerät konfigurieren.",
            "device_menu":"Automatik, Sollwerte, Anwesenheit und Schlaf für dieses Gerät einstellen.",
            "device_settings":"Gerätefreigabe erfolgt separat. Unbekannte Anwesenheit sperrt Befehle; Ausschalten erfordert geprüften Hardware-Schutz. HVAC startet nicht automatisch neu.",
        },
    },
    "el": {
        "menu": ("Εξωτερικά δεδομένα","Γενικές ρυθμίσεις","Ρυθμίσεις χώρων"),
        "descriptions": {
            "outside_data":"Καιρός, προειδοποιήσεις, εξωτερική ατμοσφαιρική ποιότητα, κλίμακες AQI και γύρη. Επίλεξε υπομενού.",
            "general_settings":"Επίλεξε αισθητήρες παρουσίας, συσκευές εντοπισμού κατοίκων και οντότητες που περιέχουν τα κατειλημμένα ή τα δωμάτια ύπνου. Η λίστα μπορεί να βρίσκεται στην κατάσταση ή σε ένα συγκεκριμένο χαρακτηριστικό. Άγνωστα ή παλιά δεδομένα ΔΕΝ σημαίνουν άδειο σπίτι.",
            "area_settings":"Επίλεξε χώρους, εξαιρέσεις παραθύρων, περιβαλλοντικές μετρήσεις και ξεχωριστή ρύθμιση κάθε κλιματικής συσκευής.",
            "pollen":"Επίλεξε αισθητήρα πρόγνωσης γύρης από οποιαδήποτε ενσωμάτωση του Home Assistant. Δήλωσε την κλίμακα και αν η υψηλή γύρη θα εμποδίζει τον αερισμό.",
            "outside_aqi":"Δήλωσε την πραγματική κλίμακα κάθε εξωτερικού αισθητήρα AQI. Άγνωστη κλίμακα δεν θεωρείται ασφαλής.",
            "select_devices":"Οι συμβατές συσκευές του χώρου επιλέγονται αρχικά όλες για παρακολούθηση. Η επιλογή ΔΕΝ ενεργοποιεί αυτόματο έλεγχο.",
            "device_choice":"Επίλεξε μία συσκευή για μεμονωμένη ρύθμιση.",
            "device_menu":"Ρύθμισε αυτόματο έλεγχο, στόχους, παρουσία και συμπεριφορά ύπνου για τη συσκευή ή άλλαξε συσκευή.",
            "device_settings":"Κάθε συσκευή χρειάζεται ξεχωριστή άδεια. Άγνωστη παρουσία σημαίνει παύση, όχι άδειο σπίτι. Για απενεργοποίηση απαιτείται επιβεβαίωση φυσικής προστασίας. Η κλιματική συσκευή δεν επανεκκινείται αυτόματα.",
        },
    },
}


def _build_labels(v: dict, old_step: dict) -> dict[str,str]:
    room, house, sleep = v["room"],v["house"],v["sleep"]
    sensor, source, target = v["sensor"],v["source"],v["target"]
    labels = {
        "general_room_occupancy_sensors":f"{room} · {v['presence']} · {sensor}",
        "general_occupied_rooms_entity":f"{v['presence']} · {room} · {source} (state)",
        "general_occupied_rooms_attribute":f"{v['presence']} · {room} · {source} (attribute)",
        "general_home_trackers":f"{house} · {v['presence']} · {v['devices']}",
        "general_home_policy":f"{house} · {v['presence']} · {v['control']}",
        "general_sleep_rooms_entity":f"{sleep} · {room} · {source} (state)",
        "general_sleep_rooms_attribute":f"{sleep} · {room} · {source} (attribute)",
        "general_source_stale_minutes":f"{source} · {v['required']} (min)",
        "outside_aqi_entity":f"AQI · {sensor}",
        "outside_aqi_scale":f"AQI · {source}",
        "outside_aqi_limit":f"AQI · {target}",
        "outside_aqi_no_sources":f"AQI · {sensor} · {v['required']}",
        "area_devices_area":f"{v['select']} · {v['area']}",
        "selected_devices":f"{v['select']} · {v['devices']}",
        "device_choice":f"{v['select']} · {v['devices']}",
        "device_auto_control":f"{v['automatic']} {v['control']}",
        "device_method":f"{v['control']} · {v['source']}",
        "device_presence_requirement":f"{v['control']} · {v['presence']}",
        "device_absence_action":f"{v['off']} · {v['presence']}",
        "device_sleep_behavior":f"{sleep} · {v['control']}",
        "device_hardware_confirmed":f"{v['required']} · {v['devices']} · {v['power']}",
        "device_temperature_entity":f"{v['temperature']} · {sensor}",
        "device_humidity_entity":f"{v['humidity']} · {sensor}",
        "device_co2_entity":f"CO₂ · {sensor}",
        "device_pm25_entity":f"PM2.5 · {sensor}",
        "device_fan_purpose":f"{v['control']} · {v['devices']}",
        "device_sensor_verified":f"{sensor} · {v['required']}",
        "device_fan_speed_percent":f"{v['speed']} (%)",
        "device_humidity_target":f"{v['humidity']} · {target} (%)",
        "device_sleep_humidity_target":f"{sleep} · {v['humidity']} · {target} (%)",
        "device_min_on_s":f"{v['power']} · min ON (s)",
        "device_min_off_s":f"{v['power']} · min OFF (s)",
        "device_max_on_s":f"{v['power']} · max ON (s)",
    }
    for profile,name in (("home",house),("unoccupied",room+" · "+v["off"]),
                         ("away",house+" · "+v["off"]),("sleep",sleep)):
        for mode,part in (("heat",v["temperature"]+" +"),
                          ("cool",v["temperature"]+" −")):
            labels[f"device_{profile}_{mode}_c"]=f"{name} · {part} · {target} (°C)"
    pollen = old_step.get("data",{})
    for key in STEPS["pollen"]:
        labels[key]=pollen.get(key,f"{v['pollen']} · {target}")
    return labels


def apply_compact_i18n(root: Path) -> None:
    locales=json.loads((root/"compact_locales.json").read_text(encoding="utf-8"))
    existing = sorted((root/"translations").glob("*.json"))
    actual = {p.stem for p in existing}
    if set(locales) != actual or len(locales)!=38:
        raise ValueError(f"Compact flow locale mismatch {set(locales)^actual}")
    for path in existing:
        lang=path.stem
        vocab=locales[lang]
        if len(vocab)!=24:
            raise ValueError(f"Incomplete compact locale {lang}")
        data=json.loads(path.read_text(encoding="utf-8"))
        options=data.setdefault("options",{})
        steps=options.setdefault("step",{})
        before=dict(steps["init"]["menu_options"])
        old_pollen=steps["environment"]
        headline=PRIMARY.get(lang,{}).get("menu",(
            f"{vocab['outside']} · {vocab['source']}",
            f"{vocab['general']} · {vocab['settings']}",
            f"{vocab['area']} · {vocab['settings']}",
        ))
        options["step"]["init"]["menu_options"]={
            "outside_data":headline[0],"general_settings":headline[1],
            "area_settings":headline[2],
            "delivery":before["delivery"],"thresholds":before["thresholds"],
        }
        names = {
            "outside_data":headline[0],"general_settings":headline[1],
            "area_settings":headline[2],"pollen":vocab["pollen"],
            "outside_aqi":f"{vocab['outside']} · AQI",
            "area_devices":f"{vocab['area']} · {vocab['devices']}",
            "select_devices":f"{vocab['select']} · {vocab['devices']}",
            "device_choice":f"{vocab['select']} · {vocab['devices']}",
            "device_menu":f"{vocab['devices']} · {vocab['settings']}",
            "device_done":f"{vocab['settings']} · ✓",
            "device_settings":f"{vocab['devices']} · {vocab['control']}",
        }
        primary=PRIMARY.get(lang,{})
        guidance=primary.get("descriptions",{})
        def desc(key):
            return guidance.get(key,(
                f"{names[key]}: {vocab['select']} {vocab['source']}, "
                f"{vocab['sensor']} / {vocab['devices']} · {vocab['control']}."
            ))
        steps["outside_data"]={
            "title":names["outside_data"],"description":desc("outside_data"),
            "menu_options":{
                "weather":before["weather"],"outdoor":before["outdoor"],
                "outside_aqi":names["outside_aqi"],"pollen":names["pollen"],
            },
        }
        steps["area_settings"]={
            "title":names["area_settings"],"description":desc("area_settings"),
            "menu_options":{
                "areas":before["areas"],"indoor_sensors":before["indoor_sensors"],
                "window_sensors":before["window_sensors"],
                "environment_room":before["environment_room"],
                "climate":before["climate"],"pid":before["pid"],
                "area_devices":names["area_devices"],
            },
        }
        steps["device_menu"]={
            "title":names["device_menu"],"description":desc("device_menu"),
            "menu_options":{
                "device_settings":names["device_settings"],
                "device_choice":names["device_choice"],
                "device_done":names["device_done"],
            },
        }
        labels=_build_labels(vocab,old_pollen)
        for key,fields in STEPS.items():
            steps[key]={
                "title":names[key],
                "description":desc(key),
                "data":{field:labels[field] for field in fields},
                "data_description":{
                    field:(
                        old_pollen.get("data_description",{}).get(field,"")
                        if key=="pollen" and lang=="en" else
                        (f"{vocab['select']} {vocab['source']}; "
                         f"{vocab['required']} · {vocab['control']} · "
                         f"{vocab['sensor']} / {vocab['devices']}.")
                    )
                    for field in fields
                },
            }
        # Greek/German pollen descriptions were previously English-only.
        if lang=="el":
            steps["pollen"]["data_description"]={
                "pollen_entity":"Αισθητήρας αριθμητικού δείκτη γύρης από οποιονδήποτε πάροχο του Home Assistant.",
                "pollen_high_from":"Το όριο υψηλής γύρης εξαρτάται από την κλίμακα του παρόχου.",
                "pollen_max_scale":"Η ανώτατη τιμή της κλίμακας του παρόχου, π.χ. 5.",
                "pollen_avoid_ventilation":"Όταν ενεργοποιηθεί, η υψηλή γύρη εμποδίζει τις συστάσεις ανοίγματος παραθύρων.",
            }
        if lang=="de":
            steps["pollen"]["data_description"]={
                "pollen_entity":"Numerischen Pollenindex eines beliebigen Home-Assistant-Anbieters wählen.",
                "pollen_high_from":"Die Pollen-Warnschwelle hängt von der Skala des Anbieters ab.",
                "pollen_max_scale":"Oberster Zahlenwert der Anbieterskala, z. B. 5.",
                "pollen_avoid_ventilation":"Hohe Pollenwerte können die Empfehlung zum Fensteröffnen optional sperren.",
            }
        opts=options.setdefault("error",{})
        opts.update({
            error:f"{vocab['invalid']} · {vocab[field]} · {vocab['settings']}"
            for error,field in ERROR_FIELDS.items()
        })
        selectors=data.setdefault("selector",{})
        selectors["general_home_policy"]={"options":{
            "any_home":f"{vocab['house']} · {vocab['presence']}",
            "all_home":f"{vocab['house']} · {vocab['devices']} · {vocab['presence']}",
        }}
        selectors["device_method"]={"options":{
            "setpoint":f"{vocab['target']} · {vocab['control']}",
            "native":f"{vocab['devices']} · {vocab['control']}",
            "power":vocab["power"],"speed":vocab["speed"],
        }}
        selectors["device_presence_requirement"]={"options":{
            "always":vocab["automatic"],
            "room":f"{vocab['room']} · {vocab['presence']}",
            "home":f"{vocab['house']} · {vocab['presence']}",
        }}
        selectors["device_absence_action"]={"options":{
            "hold":vocab["hold"],"off":vocab["off"],
        }}
        selectors["device_sleep_behavior"]={"options":{
            "normal":vocab["automatic"],
            "pause":vocab["hold"],
            "sleep_targets":f"{vocab['sleep']} · {vocab['target']}",
        }}
        selectors["device_fan_purpose"]={"options":{
            "extraction":f"{vocab['outside']} · {vocab['air']}" if "air" in vocab else
                         f"{vocab['outside']} · {vocab['control']}",
            "filtration":f"PM2.5 · {vocab['control']}",
        }}
        selectors["outside_aqi_scale"]={"options":{
            "not_configured":f"{vocab['source']} · {vocab['invalid']}",
            "us_epa":"US EPA AQI (0–500)","eea_category":"EEA AQI (1–6)",
            "custom":f"{vocab['target']} · {vocab['settings']}",
        }}
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",
                        encoding="utf-8")
        if lang=="en":
            (root/"strings.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",
                                            encoding="utf-8")
