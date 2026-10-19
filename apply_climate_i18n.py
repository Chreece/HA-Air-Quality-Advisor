"""International optional Climate setup; preserve all pre-existing translations.

Existing 38 HA locale files keep their translated legacy text. New controller
fields ship with reviewed English, Greek, German, French and Spanish labels,
and explicit English technical fallback elsewhere until human-reviewed.
No geographic defaults, external APIs or vendor-only terminology.
"""
from __future__ import annotations
import json
from pathlib import Path

TEXT={
"en":{
"menu":"Climate — room automation",
"select":"Choose a room for climate control",
"select_help":"Configure a single existing monitored room. Climate control is OFF until explicitly enabled. The legacy PID setup remains compatible but does not share outputs with this controller.",
"devices":"Room {area_name} — devices and control method",
"devices_help":"Select the measured room temperature, device-native thermostat, internal setpoint PID, safe on/off hysteresis, PWM (confirmed switch hardware only) or proportional number/fan. Select exact authorized entities. 'Auto heat/cool' requires an explicit permission; never assume equipment supports mode switching.",
"targets":"Room {area_name} — normal and comfort temperature bands",
"targets_help":"Set independent lower heating and upper cooling targets with a nonzero deadband. Comfort mode uses your explicit comfort band; it does NOT infer ASHRAE compliance from a basic thermometer.",
"setbacks":"Room {area_name} — energy setbacks and sleep",
"setbacks_help":"Separate targets for unoccupied room, whole-house away and sleep. Avoid extreme setbacks with heat pumps or equipment not designed for them. All values are local °C, independent of country.",
"presence":"Room {area_name} — occupancy and home/away",
"presence_help":"Automatically find all Home Assistant binary sensors of occupancy/presence class assigned to this room, or select them explicitly. Choose person, device tracker and optional binary home indicators. Any detected person means present; all verified absent can trigger a setback only after the configured delay. Missing/unknown never counts as absent.",
"safety":"Room {area_name} — safety and controller tuning",
"safety_help":"Control never bypasses physical frost, overheat, compressor or boiler safety. PWM is ONLY for specifically verified cycle-tolerant switch/input_boolean hardware. Configure minimum ON/OFF, maximum uninterrupted ON and PWM period. Internal PID gains and setpoint limits are adjustable; device-native strategy retains its own built-in PID.",
},
"de":{
"menu":"Klima — Raumautomatik","select":"Raum für die Klimaregelung wählen",
"select_help":"Optional. Genau einen überwachten Raum auswählen. Klimaregelung bleibt aus, bis du sie aktivierst.",
"devices":"Raum {area_name} — Geräte und Regelverfahren",
"devices_help":"Wähle tatsächlichen Temperatursensor und Geräte; Geräte-PID, interner PID, Ein/Aus, PWM oder proportionale Ausgabe. Automatische Heiz-/Kühlumschaltung nur mit ausdrücklicher Freigabe.",
"targets":"Raum {area_name} — Solltemperaturen und Komfort",
"targets_help":"Heiz- und Kühl-Sollwerte mit Sicherheitsabstand einstellen. Komfort bedeutet deinen eigenen Temperaturbereich, keine Norm-Zertifizierung.",
"setbacks":"Raum {area_name} — Absenkung und Schlafmodus",
"setbacks_help":"Separate Temperaturen bei Raum-Abwesenheit, Haus-Abwesenheit und Schlaf. Wärmepumpen benötigen geeignete Absenkungsstrategien.",
"presence":"Raum {area_name} — Präsenz und Zuhause/Abwesend",
"presence_help":"Alle passenden Präsenzsensoren im Raum werden automatisch erkannt oder einzeln ausgewählt. Personen/Gerätetracker optional. Unbekannt bedeutet niemals abwesend.",
"safety":"Raum {area_name} — Sicherheit und PID-Parameter",
"safety_help":"Mindestein-/ausschaltzeiten, Maximal-Laufzeit und PWM nur mit bestätigter Hardware. Unabhängige Frost-/Überhitzungssicherung bleibt erforderlich.",
},
"el":{
"menu":"Κλίμα — αυτοματισμός δωματίου","select":"Επιλογή δωματίου για κλιματισμό",
"select_help":"Προαιρετικό. Επίλεξε ένα δωμάτιο. Δεν γίνεται καμία ενέργεια ώσπου να ενεργοποιηθεί ρητά ο έλεγχος.",
"devices":"Δωμάτιο {area_name} — συσκευές και μέθοδος ελέγχου",
"devices_help":"Επίλεξε πραγματικό αισθητήρα και ρητά επιτρεπόμενες συσκευές. Έλεγχος από τη συσκευή, PID, on/off, PWM ή αναλογική έξοδος. Η εναλλαγή θέρμανσης/ψύξης απαιτεί άδεια.",
"targets":"Δωμάτιο {area_name} — θερμοκρασίες και άνεση",
"targets_help":"Επίλεξε κατώτερο στόχο θέρμανσης και ανώτερο ψύξης, με νεκρή ζώνη. Η άνεση βασίζεται στη δική σου επιλεγμένη ζώνη, όχι σε αυθαίρετη πιστοποίηση.",
"setbacks":"Δωμάτιο {area_name} — απουσία και ύπνος",
"setbacks_help":"Διαφορετικοί στόχοι για άδειο δωμάτιο, απουσία από το σπίτι και ύπνο. Απέφυγε ακραίες μεταβολές στις αντλίες θερμότητας.",
"presence":"Δωμάτιο {area_name} — παρουσία και απουσία",
"presence_help":"Αυτόματη ανίχνευση όλων των αισθητήρων παρουσίας HA στο δωμάτιο ή ρητή επιλογή. Προαιρετικά person/device_tracker. Άγνωστη παρουσία ΔΕΝ σημαίνει απουσία.",
"safety":"Δωμάτιο {area_name} — ασφάλεια και PID",
"safety_help":"Ελάχιστοι χρόνοι ενεργοποίησης/απενεργοποίησης, μέγιστη συνεχής λειτουργία και PWM μόνο με κατάλληλη συσκευή. Απαραίτητες ανεξάρτητες προστασίες.",
},
"fr":{
"menu":"Climat — automatisation des pièces","select":"Choisir la pièce à climatiser",
"select_help":"Facultatif. Sélectionnez une pièce; les appareils restent inactifs avant activation explicite.",
"devices":"Pièce {area_name} — appareils et commande",
"devices_help":"Thermostat natif, PID, marche/arrêt, PWM compatible ou commande proportionnelle. Le changement chauffage/froid doit être autorisé.",
"targets":"Pièce {area_name} — confort et températures",
"targets_help":"Sélectionnez des cibles de chauffage et de refroidissement séparées par une zone neutre.",
"setbacks":"Pièce {area_name} — absence et sommeil",
"setbacks_help":"Consignes indépendantes selon l'occupation, l'absence du domicile et le sommeil.",
"presence":"Pièce {area_name} — occupation et domicile",
"presence_help":"Capteurs de présence Home Assistant, personnes et trackers au choix. Une donnée indisponible n'est pas une absence.",
"safety":"Pièce {area_name} — sécurité et PID",
"safety_help":"Cycles minimaux et PWM seulement si compatible avec le matériel. Conserver les protections indépendantes.",
},
"es":{
"menu":"Clima — automatización por habitación","select":"Elegir habitación para clima",
"select_help":"Opcional. El control permanece desactivado hasta habilitarlo expresamente.",
"devices":"Habitación {area_name} — equipos y control",
"devices_help":"Termostato del equipo, PID, on/off, PWM compatible o proporcional. Cambio calor/frío solamente con autorización.",
"targets":"Habitación {area_name} — temperatura y confort",
"targets_help":"Crea objetivos de calefacción y refrigeración independientes con banda neutra.",
"setbacks":"Habitación {area_name} — ausente y sueño",
"setbacks_help":"Objetivos distintos para habitación vacía, hogar ausente o modo dormir.",
"presence":"Habitación {area_name} — ocupación y presencia",
"presence_help":"Todos los sensores compatibles de Home Assistant o selección explícita. Desconocido nunca significa ausente.",
"safety":"Habitación {area_name} — seguridad y PID",
"safety_help":"Mínimos de encendido/apagado y PWM únicamente con hardware confirmado, protección independiente necesaria.",
}
}
FIELDS={
"climate_area":"Room to configure",
"climate_enabled":"Enable automatic climate control for this room",
"climate_strategy":"Control strategy for authorized devices",
"climate_operation":"Heating, cooling or explicitly allowed automatic switching",
"climate_temperature_entity":"Independent, fresh room temperature sensor",
"climate_allow_hvac_mode_change":"Allow changing a compatible device's heat/cool/off mode",
"climate_allow_turn_off":"Allow switching the selected device to off when comfortable",
"climate_climate_entity":"Device-native or PID climate thermostat",
"climate_heat_entity":"Heating actuator (exact entity)",
"climate_cool_entity":"Cooling actuator (exact entity)",
"climate_target_source":"Choose explicit targets or a custom comfort band",
"climate_occupied_uses_comfort":"Use comfort band when room is occupied",
"climate_heat_cool_deadband_c":"Minimum separation of heat/cool targets (°C)",
"climate_auto_discover_occupancy":"Discover ALL room occupancy/presence binary sensors in HA",
"climate_occupancy_entities":"Specific room occupancy sensors (optional override)",
"climate_home_entities":"People, device trackers or home/away binary sensors",
"climate_vacancy_delay_seconds":"Wait before applying empty-room setback (seconds)",
"climate_away_delay_seconds":"Wait before applying whole-home away setback (seconds)",
"climate_sleep_enabled":"Use scheduled sleep targets",
"climate_sleep_start":"Local sleep start (HH:MM)",
"climate_sleep_end":"Local sleep end (HH:MM)",
"climate_pause_on_window_open":"Stop control on open OR unknown window contacts",
"climate_turn_relay_off_on_bad_data":"Safely de-energize owned relays when input fails",
"climate_min_mode_seconds":"Minimum dwell before switching heating and cooling (seconds)",
"climate_hysteresis_c":"On/off hysteresis around targets (°C)",
"climate_sample_seconds":"Controller measurement interval (seconds)",
"climate_relay_hardware_confirmed":"I verified the actuator has independent safety protections",
"climate_min_on_seconds":"Minimum ON time (seconds)",
"climate_min_off_seconds":"Minimum OFF time / cooldown (seconds)",
"climate_max_on_seconds":"Maximum uninterrupted ON time (seconds)",
"climate_pwm_hardware_confirmed":"Actuator manufacturer permits relay PWM; NOT a compressor",
"climate_pwm_period_seconds":"PWM time-proportioning period (seconds)",
"climate_pwm_min_pulse_seconds":"Minimum permitted PWM pulse (seconds)",
}
for profile in ("home","occupied","unoccupied","away","sleep","comfort"):
    for mode in ("heat","cool"):
        FIELDS["climate_"+profile+"_"+mode+"_c"]=profile.title()+" "+mode+" target (°C)"
for key in ("kp","ki","kd","output_min","output_max","offset_c","min_setpoint_c",
            "max_setpoint_c","max_change_c","min_change_c"):
    FIELDS["climate_"+key]=key.replace("_"," ").upper()+" — PID/actuator limit"

DESCRIPTIONS={
"climate_area":"Select only one monitored Home Assistant area. A device cannot belong to two enabled room controllers.",
"climate_enabled":"Default OFF. Existing thermostats remain under their own control until explicitly enabled.",
"climate_strategy":"Device = own thermostat PID; setpoint PID = our bounded outer loop; on/off = hysteresis; PWM = certified cycling-safe switch only; proportional = number/fan.",
"climate_operation":"Auto chooses heating or cooling with explicit mode-switch permission, deadband and minimum dwell. It is not equivalent to HA's climate AUTO schedule.",
"climate_temperature_entity":"Must be room assigned and report recent temperature (°C or °F). Missing/stale data blocks new commands.",
"climate_allow_hvac_mode_change":"Requires manual opt-in. The device must advertise the exact requested HVAC mode. Switching is never assumed safe.",
"climate_allow_turn_off":"When within the deadband, allow an authorized thermostat to be set off; other modes remain unchanged.",
"climate_climate_entity":"Only a single explicitly selected climate.* thermostat with compatible target/mode support.",
"climate_heat_entity":"Required for heating with direct on/off/PWM/analog strategies. Only selected entity IDs are actuated.",
"climate_cool_entity":"Required for cooling with direct on/off/PWM/analog strategies. Heating and cooling cannot activate simultaneously.",
"climate_occupancy_entities":"Choose room occupancy/presence class binary sensors; any on means occupied, all fresh off permits vacancy after hold. Unknown never implies vacancy.",
"climate_home_entities":"Person, device_tracker or explicitly identified binary home signals. Every selected entity must reliably report at-home/away.",
"climate_auto_discover_occupancy":"When selected room sensors are empty, all HA binary_sensor entities with presence/occupancy device class and matching area are monitored.",
"climate_heat_cool_deadband_c":"Heating target must remain sufficiently below cooling target. Changing modes also requires a minimum off period.",
"climate_relay_hardware_confirmed":"User confirms suitability, including independent high-temperature/freeze/overcurrent/boiler safety. HA is not a safety-rated controller.",
"climate_pwm_hardware_confirmed":"PWM is refused for ordinary climate.* devices and any hardware requiring compressor minimum-off protection.",
"climate_turn_relay_off_on_bad_data":"If enabled, only relays owned by this controller are switched off on stale data/window openings. No commands to unowned devices.",
}
ERRORS={
"invalid_climate_strategy":"Choose an allowed control strategy and heat/cool operation.",
"invalid_climate_temperature":"Select a real room temperature sensor.",
"invalid_climate_actuator":"Choose valid, compatible devices for the requested strategy.",
"climate_auto_requires_optin":"Automatic heating/cooling switching requires explicit HVAC-mode permission.",
"climate_duplicate_actuator":"Another enabled room already controls that device.",
"invalid_climate_targets":"Choose valid heating and cooling targets with an appropriate deadband.",
"invalid_climate_sleep_window":"Use local clock times in HH:MM format.",
"invalid_climate_presence_delay":"Presence hold times must be valid seconds.",
"invalid_climate_safety":"Review hardware confirmation, minimum cycles, PID limits and PWM operating bounds.",
}
FORMS=[
("climate","select","select_help",["climate_area"]),
("climate_device","devices","devices_help",
["climate_enabled","climate_strategy","climate_operation","climate_temperature_entity",
 "climate_allow_hvac_mode_change","climate_allow_turn_off",
 "climate_climate_entity","climate_heat_entity","climate_cool_entity"]),
("climate_targets","targets","targets_help",
["climate_target_source","climate_occupied_uses_comfort","climate_heat_cool_deadband_c",
 *["climate_"+p+"_"+m+"_c" for p in ("home","occupied","comfort") for m in ("heat","cool")]]),
("climate_setbacks","setbacks","setbacks_help",
["climate_"+p+"_"+m+"_c" for p in ("unoccupied","away","sleep") for m in ("heat","cool")]),
("climate_presence","presence","presence_help",
["climate_auto_discover_occupancy","climate_occupancy_entities","climate_home_entities",
 "climate_vacancy_delay_seconds","climate_away_delay_seconds",
 "climate_sleep_enabled","climate_sleep_start","climate_sleep_end"]),
("climate_safety","safety","safety_help",
["climate_pause_on_window_open","climate_turn_relay_off_on_bad_data",
 "climate_min_mode_seconds","climate_hysteresis_c","climate_sample_seconds",
 "climate_relay_hardware_confirmed","climate_min_on_seconds",
 "climate_min_off_seconds","climate_max_on_seconds",
 "climate_pwm_hardware_confirmed","climate_pwm_period_seconds",
 "climate_pwm_min_pulse_seconds",
 *["climate_"+k for k in ("kp","ki","kd","output_min","output_max",
                          "offset_c","min_setpoint_c","max_setpoint_c",
                          "max_change_c","min_change_c")]]),
]
def apply_climate_i18n(root: Path) -> None:
    for path in (root / "strings.json",*sorted((root / "translations").glob("*.json"))):
        locale="en" if path.name=="strings.json" else path.stem.lower().split("-")[0]
        localized=TEXT.get(locale,TEXT["en"])
        doc=json.loads(path.read_text(encoding="utf-8"))
        steps=doc["options"]["step"]
        menu=steps["init"]["menu_options"]
        reordered={}
        for key,value in menu.items():
            if key=="pid":
                reordered["climate"]=localized["menu"]
            reordered[key]=value
        if "climate" not in reordered:
            reordered["climate"]=localized["menu"]
        steps["init"]["menu_options"]=reordered
        for name,title,description,fields in FORMS:
            steps[name]={
                "title":localized[title],"description":localized[description],
                "data":{key:FIELDS[key] for key in fields},
                "data_description":{key:DESCRIPTIONS.get(key,FIELDS[key]+"; optional and source-qualified.") for key in fields},
            }
        doc["options"].setdefault("error",{}).update(ERRORS)
        doc.setdefault("services",{})["climate_control"]={
            "name":"Climate automation",
            "description":"Pause, resume, reset, or override the selected room climate profile. Controller must be explicitly enabled.",
            "fields":{
                "area":{"name":"Room","description":"Explicit Home Assistant area ID"},
                "action":{"name":"Action","description":"pause | resume | reset | profile"},
                "profile":{"name":"Override profile","description":"auto | home | occupied | unoccupied | away | sleep"},
            }
        }
        path.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
