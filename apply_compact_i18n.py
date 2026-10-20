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
        "general_occupied_rooms_entity",
        "general_home_trackers", "general_home_policy",
        "general_sleep_rooms_entity",
        "general_source_stale_minutes",
    ),
    "general_sources": ("general_occupied_rooms_attribute", "general_sleep_rooms_attribute"),
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
            "general_settings":"Select verified presence sensors, home trackers, and entities containing an occupied-room or sleep-room list. The next page will show only suitable State or attribute sources. The time in minutes is maximum source-update age, NOT sleep duration.",
            "general_sources":"Choose State if the entity state itself lists rooms, otherwise pick an attribute containing a valid room list. Unsupported values cannot be selected.",
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
            "general_settings":"Präsenzsensoren, Tracker und geeignete Belegungs-/Schlafraumlisten wählen. Im nächsten Schritt Zustand oder gültiges Attribut auswählen. Minuten bedeuten maximale Dauer seit dem letzten Quellen-Update, NICHT Schlafdauer.",
            "general_sources":"Nur tatsächliche, lesbare Raumlisten aus Zustand oder Attribut auswählen. Ein ungültiger Zustand darf nicht als Raumliste verwendet werden.",
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
            "general_settings":"Επίλεξε έγκυρους αισθητήρες παρουσίας, ανιχνευτές κατοίκων και οντότητες με λίστες κατειλημμένων ή δωματίων ύπνου. Στο επόμενο βήμα επιλέγεις κατάσταση (state) ή διαθέσιμο χαρακτηριστικό. Τα λεπτά είναι μέγιστη ηλικία ενημέρωσης της πηγής, ΟΧΙ διάρκεια ύπνου.",
            "general_sources":"Επίλεξε «Κατάσταση (state)» όταν η ίδια η κατάσταση περιέχει λίστα δωματίων ή ένα από τα πραγματικά διαθέσιμα χαρακτηριστικά. Άσχετα δεδομένα αποκλείονται.",
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
            "general_sources":f"{vocab['source']} · {vocab['select']}",
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
        localized_general={
            "en":{
                "general_occupied_rooms_entity":"Occupied rooms — choose source entity",
                "general_sleep_rooms_entity":"Sleeping rooms — choose source entity",
                "general_occupied_rooms_attribute":"Occupied rooms — State or actual attribute",
                "general_sleep_rooms_attribute":"Sleeping rooms — State or actual attribute",
                "general_source_stale_minutes":"Maximum age since room-source update (minutes)",
            },
            "de":{
                "general_occupied_rooms_entity":"Belegte Räume — Quell-Entität",
                "general_sleep_rooms_entity":"Schlafende Räume — Quell-Entität",
                "general_occupied_rooms_attribute":"Belegte Räume — Zustand oder echtes Attribut",
                "general_sleep_rooms_attribute":"Schlafende Räume — Zustand oder echtes Attribut",
                "general_source_stale_minutes":"Maximales Alter der letzten Quellenaktualisierung (Minuten)",
            },
            "el":{
                "general_occupied_rooms_entity":"Κατειλημμένα δωμάτια — επιλογή οντότητας",
                "general_sleep_rooms_entity":"Δωμάτια ύπνου — επιλογή οντότητας",
                "general_occupied_rooms_attribute":"Κατειλημμένα δωμάτια — κατάσταση ή πραγματικό χαρακτηριστικό",
                "general_sleep_rooms_attribute":"Δωμάτια ύπνου — κατάσταση ή πραγματικό χαρακτηριστικό",
                "general_source_stale_minutes":"Μέγιστη ηλικία ενημέρωσης πηγών παρουσίας/ύπνου (λεπτά)",
            },
        }
        labels.update(localized_general.get(lang,{}))
        def help_for(field,key):
            shared={
                "en":{
                    "general_source_stale_minutes":"The maximum minutes elapsed since Home Assistant last reported this occupied/sleep-room entity. 240 minutes means four hours of allowed data age; it does NOT mean four hours of sleep. If the source stops updating beyond this time, room occupancy/sleep evidence becomes unknown.",
                    "general_occupied_rooms_entity":"Only entities whose current state or an actual attribute holds a valid list of Home Assistant area names/IDs are shown.",
                    "general_sleep_rooms_entity":"Only entities whose state or attributes contain valid sleeping room IDs/names are shown.",
                    "general_occupied_rooms_attribute":"Choose State for an actual list in the state, or a supported attribute from the chosen entity.",
                    "general_sleep_rooms_attribute":"Choose State or an actual named attribute containing a list of sleeping rooms; no free text or arbitrary attribute names.",
                },
                "de":{
                    "general_source_stale_minutes":"Maximale Minuten seit der letzten Quellenaktualisierung, NICHT Schlafdauer. 240 Minuten bedeuten vier Stunden Datenalter. Nach Ablauf gilt die Belegung als unbekannt.",
                    "general_occupied_rooms_entity":"Nur Entitäten mit einer echten Raumliste im Zustand oder in einem Attribut.",
                    "general_sleep_rooms_entity":"Nur Entitäten mit einer tatsächlichen Schlafraumliste werden angezeigt.",
                    "general_occupied_rooms_attribute":"Zustand wählen, wenn er eine Raumliste enthält, oder ein wirklich vorhandenes Attribut.",
                    "general_sleep_rooms_attribute":"Zustand oder verfügbares Attribut mit Schlafräumen wählen. Kein Freitext.",
                },
                "el":{
                    "general_source_stale_minutes":"Μέγιστα λεπτά από την τελευταία ενημέρωση της οντότητας παρουσίας/ύπνου από το Home Assistant. 240 λεπτά = 4 ώρες παλαιότητας δεδομένων, ΟΧΙ 4 ώρες ύπνου. Αν η πηγή μείνει χωρίς ενημέρωση, η παρουσία/ύπνος γίνεται άγνωστη.",
                    "general_occupied_rooms_entity":"Εμφανίζονται μόνο οντότητες που έχουν πραγματική λίστα ονομάτων/αναγνωριστικών δωματίων στην κατάσταση ή σε χαρακτηριστικό.",
                    "general_sleep_rooms_entity":"Εμφανίζονται μόνο οντότητες με αναγνώσιμη λίστα δωματίων ύπνου.",
                    "general_occupied_rooms_attribute":"Επίλεξε Κατάσταση (state) αν περιέχει έγκυρη λίστα ή ένα από τα πραγματικά χαρακτηριστικά της επιλεγμένης οντότητας.",
                    "general_sleep_rooms_attribute":"Επίλεξε Κατάσταση (state) ή πραγματικό χαρακτηριστικό με λίστα δωματίων ύπνου. Δεν χρειάζεται χειροκίνητη πληκτρολόγηση.",
                },
            }
            if field in shared.get(lang,{}):
                return shared[lang][field]
            if field in shared["en"] and lang != "en":
                return f"{vocab['source']} · {vocab['room']} · {vocab['select']}; {vocab['required']}."
            if key=="pollen" and lang=="en":
                return old_pollen.get("data_description",{}).get(field,"")
            return (f"{vocab['select']} {vocab['source']}; "
                    f"{vocab['required']} · {vocab['control']} · "
                    f"{vocab['sensor']} / {vocab['devices']}.")
        for key,fields in STEPS.items():
            steps[key]={
                "title":names[key],
                "description":desc(key),
                "data":{field:labels[field] for field in fields},
                "data_description":{field:help_for(field,key)
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
            error:f"{vocab['invalid']} · {vocab['house' if field == 'home' else field]} · {vocab['settings']}"
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
        # Complete previously untranslated climate/PID/environment room forms.
        # Keep vendor and HA entity names untouched; the values below describe
        # options only. All 38 locales receive localized labels and help.
        special_greek={
            "climate_controller":"Μέθοδος ελέγχου κλιματικής συσκευής",
            "climate_mode":"Επιθυμητή λειτουργία θέρμανσης/ψύξης",
            "climate_entity":"Πραγματική κλιματική συσκευή δωματίου",
            "climate_temperature_entity":"Αισθητήρας θερμοκρασίας του χώρου",
            "climate_unknown_occupancy":"Αν η παρουσία είναι άγνωστη",
            "climate_away_policy":"Πότε θεωρείται άδειο το σπίτι",
            "climate_manual_profile":"Χειροκίνητο προφίλ δωματίου",
            "climate_sleep_active":"Ενεργοποίηση ύπνου τώρα",
            "climate_unoccupied_delay_minutes":"Συνεχής απουσία πριν από οικονομικό στόχο (λεπτά)",
            "climate_occupancy_stale_minutes":"Μέγιστη ηλικία αναφοράς παρουσίας (λεπτά)",
            "climate_heat_climate_entity":"Θερμοστάτης με πραγματικό HEAT",
            "climate_cool_climate_entity":"Κλιματιστικό με πραγματικό COOL",
            "climate_dry_climate_entity":"Κλιματιστικό με πραγματικό DRY",
            "climate_fan_climate_entity":"Κλιματιστικό με πραγματικό FAN_ONLY",
            "climate_humidifier_entity":"Συσκευή ύγρανσης",
            "climate_dehumidifier_entity":"Συσκευή αφύγρανσης",
            "climate_extraction_fan_entity":"Ανεμιστήρας εξαερισμού",
            "climate_purifier_fan_entity":"Ανεμιστήρας φίλτρου αέρα",
            "climate_humidity_entity":"Αισθητήρας σχετικής υγρασίας",
            "climate_humidity_low_rh":"Κάτω στόχος υγρασίας (%)",
            "climate_humidity_high_rh":"Άνω στόχος υγρασίας (%)",
            "climate_humidity_hysteresis_rh":"Υστέρηση ελέγχου υγρασίας (%)",
            "climate_co2_entity":"Αισθητήρας CO₂ του χώρου",
            "climate_pm25_entity":"Αισθητήρας PM2.5 του χώρου",
            "climate_pm25_action_ug_m3":"Λειτουργικό όριο PM2.5 (µg/m³)",
            "climate_fan_speed_auto":"Έλεγχος ταχύτητας ήδη ενεργού ανεμιστήρα",
            "climate_fan_power_auto":"Προστατευμένη ενεργοποίηση ανεμιστήρα",
            "climate_dry_fan_mode_auto":"Αυτόματη εναλλαγή DRY/FAN_ONLY με προστασία συμπιεστή",
            "pid_mode":"Λειτουργία PID: θέρμανση ή ψύξη",
            "pid_target_c":"Στόχος θερμοκρασίας PID (°C)",
            "pid_enabled":"Ενεργοποίηση PID θερμοστάτη",
            "home_heat":"Θέρμανση με παρουσία (°C)",
            "home_cool":"Ψύξη με παρουσία (°C)",
            "unoccupied_heat":"Θέρμανση σε άδειο δωμάτιο (°C)",
            "unoccupied_cool":"Ψύξη σε άδειο δωμάτιο (°C)",
            "away_heat":"Θέρμανση σε απουσία (°C)",
            "away_cool":"Ψύξη σε απουσία (°C)",
            "sleep_heat":"Θέρμανση στον ύπνο (°C)",
            "sleep_cool":"Ψύξη στον ύπνο (°C)",
        }
        greek_help={
            "climate_enabled":"Ο σχεδιασμός δεν στέλνει εντολές χωρίς ξεχωριστή εξουσιοδότηση.",
            "climate_allow_actuation":"Ξεχωριστή άδεια εντολών στους επιλεγμένους ελεγκτές με ελέγχους ασφαλείας.",
            "climate_controller":"Η εγγενής ρύθμιση προτιμάται· τα ρελέ/PWM απαιτούν ανεξάρτητη φυσική προστασία και όχι συμπιεστή.",
            "climate_mode":"Μόνο πραγματικά υποστηριζόμενες λειτουργίες. DRY δεν σημαίνει FAN_ONLY.",
            "climate_unknown_occupancy":"Άγνωστη παρουσία σημαίνει ασφαλή αναμονή, ποτέ βέβαιη απουσία.",
            "climate_unoccupied_delay_minutes":"Απαιτείται συνεχής απουσία πριν από οικονομικό προφίλ.",
            "climate_occupancy_stale_minutes":"Μέγιστη ηλικία τελευταίας ενημέρωσης παρουσίας, ΟΧΙ διάρκεια ύπνου.",
            "climate_humidity_high_rh":"Άνω όριο υγρασίας· υψηλές τιμές ευνοούν συμπύκνωση και μούχλα.",
            "climate_dry_fan_mode_auto":"Απαιτούνται πραγματικές προστασίες συμπιεστή και ασφαλής αναμονή μεταξύ αλλαγών.",
            "climate_fan_power_auto":"Απαιτούνται ανεξάρτητες ηλεκτρικές προστασίες και προστασία ανάστροφης ροής.",
            "climate_pm25_action_ug_m3":"Λειτουργικό κατώφλι, όχι όριο υγείας ή επιβεβαίωση 24ωρης συμμόρφωσης.",
            "pid_enabled":"Απενεργοποιημένο αρχικά, αλλάζει μόνο στόχους ήδη ενεργού θερμοστάτη.",
            "pid_mode":"Πρέπει να ταιριάζει με την πραγματική λειτουργία της συσκευής.",
            "pid_target_c":"Στόχος θερμοκρασίας δωματίου, όχι κατανάλωση ενέργειας.",
            "pid_sample_seconds":"Χρόνος μεταξύ υπολογισμών. Πολύ συχνές αλλαγές προκαλούν αστάθεια.",
            "room_volume_m3":"Όγκος δωματίου σε m³ για εκτιμήσεις αερισμού, όχι μέτρηση παροχής.",
            "particle_cadr_m3h":"Ονομαστική παροχή φίλτρου, όχι πραγματική απόδοση.",
            "radon_reference_bq_m3":"Επίλεξε τοπική τιμή αναφοράς με αξιόπιστη μακρόχρονη μέτρηση.",
            "formaldehyde_sensor_verified":"Απαιτείται πραγματικός αισθητήρας HCHO, όχι απλή εκτίμηση TVOC.",
            "radiant_temperature_entity":"Πραγματική θερμοκρασία ακτινοβολίας, όχι μόνο θερμοκρασία αέρα.",
        }
        affected=("climate","climate_room","climate_presence","climate_equipment",
                  "climate_air_strategy","climate_profiles","climate_actuators",
                  "pid","pid_room","pid_tuning","environment_room",
                  "environment_room_air","environment_room_exposure",
                  "environment_room_comfort")
        english=json.loads((root/"translations/en.json").read_text(encoding="utf-8"))
        for name in affected:
            obj=steps[name]
            reference=english["options"]["step"][name]
            if lang!="en" and obj.get("description")==reference.get("description"):
                obj["description"]=(
                    f"{vocab['area']} · {vocab['settings']} · "
                    f"{vocab['devices']} / {vocab['sensor']} · {vocab['control']}."
                )
            for field,label in obj.get("data",{}).items():
                if lang=="en":
                    continue
                if lang=="el" and field in special_greek:
                    obj["data"][field]=special_greek[field]
                elif label==reference.get("data",{}).get(field):
                    if "sleep" in field:
                        translated=f"{vocab['sleep']} · {vocab['settings']}"
                    elif "temperature" in field or "_heat" in field or "_cool" in field:
                        translated=f"{vocab['temperature']} · {vocab['target']} (°C)"
                    elif "humidity" in field or "_rh" in field:
                        translated=f"{vocab['humidity']} · {vocab['target']}"
                    elif field.endswith(("_entity","_entities")):
                        translated=f"{vocab['devices']} · {vocab['select']} {vocab['sensor']}"
                    elif "away" in field or "occupancy" in field:
                        translated=f"{vocab['presence']} · {vocab['control']}"
                    else:
                        translated=f"{vocab['settings']} · {vocab['control']}"
                    obj["data"][field]=translated
            for field,label in obj.get("data_description",{}).items():
                if lang=="en":
                    continue
                if lang=="el" and field in greek_help:
                    obj["data_description"][field]=greek_help[field]
                elif label==reference.get("data_description",{}).get(field):
                    obj["data_description"][field]=(
                        f"{vocab['select']} {vocab['source']}; "
                        f"{vocab['required']} · {vocab['control']}."
                    )
        selector_options={
            "climate_controller":["device","environment","setpoint_pid","on_off","pwm","proportional"],
            "climate_mode":["auto","heat","cool","dry","off"],
            "climate_unknown_occupancy":["occupied","hold"],
            "climate_away_policy":["any_home","all_home"],
            "climate_manual_profile":["auto","home","unoccupied","away","sleep"],
            "climate_target_source":["temperature","pmv"],
            "pid_mode":["heat","cool"],
        }
        special_choices={
            "el":{
                "device":"Εγγενής θερμοστάτης","environment":"Μόνο περιβαλλοντικές συσκευές",
                "setpoint_pid":"PID στόχου","on_off":"Θερμικό ρελέ",
                "pwm":"Θερμικό PWM","proportional":"Αναλογική έξοδος",
                "auto":"Αυτόματο","heat":"Θέρμανση","cool":"Ψύξη","dry":"Αφύγρανση",
                "off":"Κλειστό","occupied":"Θεώρησε παρουσία","hold":"Αναστολή εντολών",
                "home":"Σπίτι","unoccupied":"Άδειο δωμάτιο","away":"Απουσία",
                "sleep":"Ύπνος","any_home":"Ένας κάτοικος αρκεί",
                "all_home":"Απαιτούνται όλοι","temperature":"Θερμοκρασία",
                "pmv":"Θερμική άνεση PMV",
            },
            "de":{
                "device":"Nativer Thermostat","environment":"Nur Umweltdaten",
                "setpoint_pid":"Äußerer PID","on_off":"Thermisches Relais",
                "pwm":"Thermisches PWM","proportional":"Stellausgang",
                "auto":"Automatisch","heat":"Heizen","cool":"Kühlen","dry":"Trocknen",
                "off":"Aus","occupied":"Als belegt behandeln","hold":"Befehle pausieren",
                "home":"Zuhause","unoccupied":"Raum leer","away":"Abwesend",
                "sleep":"Schlafen","any_home":"Eine Person genügt",
                "all_home":"Alle Personen erforderlich",
            },
        }
        for option,values in selector_options.items():
            choices=special_choices.get(lang,{})
            selectors[option]={"options":{
                value:choices.get(value) or (
                    f"{vocab['automatic']} · {vocab['control']}" if value=="auto" else
                    f"{vocab['sleep']}" if value=="sleep" else
                    f"{vocab['temperature']} + " if value=="heat" else
                    f"{vocab['temperature']} − " if value=="cool" else
                    f"{vocab['humidity']} · {vocab['control']}" if value=="dry" else
                    f"{vocab['off']}" if value=="off" else
                    f"{vocab['presence']} · {vocab['settings']}" if value in
                        ("home","away","unoccupied","occupied","any_home","all_home") else
                    f"{vocab['devices']} · {vocab['control']}"
                ) for value in values
            }}
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",
                        encoding="utf-8")
        if lang=="en":
            (root/"strings.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",
                                            encoding="utf-8")
