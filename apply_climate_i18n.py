"""New Climate room setup labels; optional future strategies are clearly disabled."""
from __future__ import annotations
import json
from pathlib import Path

BASE={
 "climate":"Climate — select room",
 "climate_room":"Climate — controller, occupancy and away",
 "climate_profiles":"Climate — temperature bands for each mode",
 "climate_area":"Room to configure",
 "climate_enabled":"Enable climate planning for this room",
 "climate_allow_actuation":"Permit commands to the selected native thermostat (opt in)",
 "climate_auto_switch_hvac":"Automatically switch between supported heat/cool modes (separate opt in)",
 "climate_controller":"Controller method / device capability",
 "climate_mode":"Heat, cool, off or automatic selection",
 "climate_entity":"Explicit room climate device",
 "climate_temperature_entity":"Fresh independent temperature sensor",
 "climate_occupancy_sensors":"Occupancy/presence sensors in this room",
 "climate_away_entities":"People or device trackers for home/away",
 "climate_hysteresis_c":"Mode-switching hysteresis (°C)",
 "climate_actuation_requires_native_device":"Automated control currently supports only the device-native thermostat driver; separate relay/PWM safety validation is still required.",
 "climate_temperature_required":"Select a room temperature sensor.",
 "climate_target_required":"Select a supported climate entity assigned to this room.",
 "climate_direct_actuator_not_ready":"Relay/PWM/proportional drivers are still under safety testing; they cannot be enabled.",
 "climate_controller_invalid":"Choose a supported control method.",
 "climate_mode_invalid":"Choose auto, heat, cool or off.",
 "climate_occupancy_invalid":"An occupancy sensor does not belong to this room.",
 "climate_away_invalid":"Select a valid people/tracker entity.",
 "climate_deadband_invalid":"Cooling target must be at least 1°C above heating target in every profile.",
}
LABELS={
 "de":{"climate":"Klima — Raum auswählen","climate_room":"Klima — Regelung, Anwesenheit und Abwesenheit",
       "climate_profiles":"Klima — Temperaturbereiche je Betriebsart",
       "climate_enabled":"Klimaplaner für diesen Raum aktivieren",
       "climate_allow_actuation":"Thermostat-Sollwertbefehle erlauben (separate Zustimmung)",
       "climate_auto_switch_hvac":"Automatischen Heiz-/Kühlmoduswechsel erlauben",
       "climate_occupancy_sensors":"Präsenzsensoren in diesem Raum",
       "climate_away_entities":"Personen und Tracker für Zuhause/Abwesend"},
 "el":{"climate":"Κλίμα — επιλογή δωματίου","climate_room":"Κλίμα — ελεγκτής, παρουσία και απουσία",
       "climate_profiles":"Κλίμα — όρια θέρμανσης/ψύξης ανά λειτουργία",
       "climate_enabled":"Ενεργοποίηση σχεδίου κλίματος δωματίου",
       "climate_allow_actuation":"Να επιτρέπονται εντολές στον επιλεγμένο θερμοστάτη (ξεχωριστή άδεια)",
       "climate_auto_switch_hvac":"Αυτόματη αλλαγή θέρμανσης/ψύξης (ξεχωριστή άδεια)",
       "climate_occupancy_sensors":"Αισθητήρες παρουσίας αυτού του δωματίου",
       "climate_away_entities":"Άτομα και συσκευές εντοπισμού για σπίτι/απουσία"},
 "fr":{"climate":"Climat — choisir une pièce","climate_room":"Climat — régulation, présence et absence",
       "climate_profiles":"Climat — plages de température par mode"},
 "es":{"climate":"Clima — elegir habitación","climate_room":"Clima — control, ocupación y ausencia",
       "climate_profiles":"Clima — temperaturas por modo"},
}
def apply_climate_i18n(root:Path)->None:
    for path in [root/"strings.json",*sorted((root/"translations").glob("*.json"))]:
        lang="en" if path.name=="strings.json" else path.stem
        vocab={**BASE,**LABELS.get(lang,{})}
        data=json.loads(path.read_text(encoding="utf-8"))
        option=data.setdefault("options",{})
        steps=option.setdefault("step",{})
        steps.setdefault("init",{}).setdefault("menu_options",{})["climate"]=vocab["climate"]
        descriptors={
          "climate":("climate",["climate_area"]),
          "climate_room":("climate_room",["climate_enabled","climate_allow_actuation","climate_auto_switch_hvac","climate_controller",
             "climate_mode","climate_entity","climate_temperature_entity",
             "climate_occupancy_sensors","climate_away_entities","climate_hysteresis_c"]),
          "climate_profiles":("climate_profiles",[f"{p}_{kind}" for p in
              ("home","unoccupied","away","sleep") for kind in ("heat","cool")]),
        }
        for key,(title,fields) in descriptors.items():
            steps[key]={
                "title":vocab[title],
                "description":("Configure each selected room independently. "
                    "A real temperature measurement and explicit supported climate device are required. "
                    "All new direct relay/PWM modes are blocked pending actuator testing. "
                    "Occupied, unoccupied, away and sleep heating/cooling targets are independent."),
                "data":{field:vocab.get(field,
                    field.replace("_"," ").capitalize()) for field in fields},
                "data_description":{field:(
                    "Device/source-specific configuration. No country assumptions; do not substitute estimates for sensor measurements."
                    if field not in ("climate_occupancy_sensors","climate_away_entities") else
                    "Choose explicit Home Assistant entities. Unknown occupancy is not assumed vacant.")
                    for field in fields},
            }
        option.setdefault("error",{}).update({
            key:vocab[key] for key in BASE if key.startswith("climate_")
            and key.endswith(("required","invalid","ready")) or key in (
                "climate_target_required","climate_direct_actuator_not_ready",
                "climate_controller_invalid","climate_mode_invalid",
                "climate_occupancy_invalid","climate_away_invalid","climate_deadband_invalid")
        })
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
