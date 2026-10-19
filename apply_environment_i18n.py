"""Idempotent Home Environment Manager branding and opt-in science form translations.

Called last by generate_translations.py. Core 38 language translations are
preserved; technical science help uses English where not yet translated.
"""
from __future__ import annotations

import json
from pathlib import Path

PRODUCT = "Home Environment Manager"

EN = {
    "global_title": "International air-quality sources and pollen",
    "global_description": "Optional. Declare each AQI provider's scale explicitly: EPA 0–500, European six-category index, or your provider's custom limit. An unknown AQI scale is NEVER treated as the US scale. A pollen forecast can come from any Home Assistant integration and is advisory unless you deliberately enable blocking.",
    "room_title": "Choose a room for environmental science",
    "room_description": "Configure extra sensors and assumptions for one selected room. All are optional. The basic Air Quality Advisor features work without any of them.",
    "air_title": "Room: {area_name} — ventilation and moisture",
    "air_description": "Optional. Choose the room-temperature sensor if multiple are present. Enter measured room volume and your air cleaner's published particle CADR only if known. Confirm real NDIR CO₂ hardware before allowing predictions. Room occupancy and open-window evidence still determine whether air-change estimates are possible.",
    "exposure_title": "Room: {area_name} — optional specialist sensors",
    "exposure_description": "Optional. Select only sensors actually measuring the requested pollutant and units. Confirm independent hardware/calibration; synthetic HCHO, eCO₂ and generic sound-level signals are not acceptable substitutes for validated observations. Radon guidelines need nearly a full year of history.",
    "comfort_title": "Room: {area_name} — full thermal comfort (advanced)",
    "comfort_description": "Optional ISO 7730 PMV/PPD. You MUST provide mean radiant temperature, air speed (measured or supplied), activity in met and clothing insulation in clo. Never interpret estimates as individual comfort or building compliance.",
    "fields": {
        "pollen_entity": "Pollen forecast sensor (any country/provider)",
        "pollen_high_from": "Pollen scale: threshold treated as high",
        "pollen_max_scale": "Pollen provider's maximum scale value",
        "pollen_avoid_ventilation": "Avoid window ventilation when pollen is high (opt in)",
        "environment_area": "Room to configure",
        "temperature_entity": "Room air temperature sensor (optional override)",
        "room_volume_m3": "Measured room air volume (m³)",
        "particle_cadr_m3h": "Air purifier rated particle CADR (m³/h)",
        "purifier_entity": "Air purifier power/fan entity",
        "extractor_entity": "Mechanical extraction fan/switch entity",
        "co2_ndir_verified": "CO₂ sensor has verified real NDIR hardware",
        "co2_target_ppm": "CO₂ ventilation target (ppm)",
        "sleep_room": "This is a sleeping room",
        "radon_entity": "Dedicated radon sensor",
        "radon_sensor_verified": "Radon sensor uses dedicated calibrated hardware",
        "formaldehyde_entity": "Dedicated formaldehyde sensor",
        "formaldehyde_sensor_verified": "Formaldehyde measurement is real and verified",
        "noise_entity": "Calibrated A-weighted sound level (dB(A))",
        "noise_sensor_calibrated": "Sound-level sensor delivers equivalent calibrated readings",
        "illuminance_entity": "Photopic illuminance (lux)",
        "melanopic_edi_entity": "Spectral sensor's melanopic EDI (lx)",
        "melanopic_spectral_verified": "Melanopic EDI comes from a real spectral measurement",
        "enable_pmv": "Calculate full ISO 7730 PMV/PPD (opt in)",
        "radiant_temperature_entity": "Mean radiant temperature sensor (°C)",
        "air_speed_entity": "Measured local air-speed sensor (m/s)",
        "air_speed_m_s": "Otherwise: explicitly estimated air speed (m/s)",
        "met": "Occupant activity rate (met)",
        "clo": "Occupant clothing insulation (clo)",
    },
    "help": {
        "pollen_entity": "Select a current numeric pollen-index entity produced by any local HA integration; nothing is fetched from a fixed national service.",
        "pollen_high_from": "Provider-defined pollen indices are not internationally interchangeable. Check the selected provider's threshold definitions.",
        "pollen_max_scale": "For example 5 for a 0–5 scale. The numerical maximum is specific to your provider.",
        "pollen_avoid_ventilation": "If enabled, a high trusted pollen reading becomes an outside blocker. Leave off unless this is appropriate for your household.",
        "environment_area": "Only the selected room is edited. Return here to configure another room.",
        "temperature_entity": "When multiple temperature sensors are available, explicitly choose the correctly located one. A mold calibration sensor is otherwise reused.",
        "room_volume_m3": "Interior usable volume: room floor area × ceiling height. Required for nominal filter air exchanges.",
        "particle_cadr_m3h": "Use the manufacturer's rated particle CADR at the stated fan speed, not fan airflow or a guessed air-change rate. Does not apply to gases.",
        "purifier_entity": "Power state is used for descriptive suggestions only; Home Environment Manager does not control the device.",
        "extractor_entity": "Enables moisture-event advice about extraction. RH rises alone do not prove a shower or cooking event.",
        "co2_ndir_verified": "Use only independently confirmed true CO₂ hardware, not TVOC-based eCO₂ estimates.",
        "co2_target_ppm": "A configurable operational ventilation goal; reaching it does not prove healthy air or absence of infection risk.",
        "sleep_room": "Adds sleeping-room interpretation of nighttime heat and noise history when adequate data exists.",
        "radon_entity": "Dedicated monitor, Bq/m³ or pCi/L. WHO recommends a national annual reference of 100 Bq/m³ where feasible (not above 300).",
        "radon_sensor_verified": "Acknowledges the device truly measures radon. Annual comparison remains unavailable until enough measured days exist.",
        "formaldehyde_entity": "Dedicated HCHO with µg/m³ or mg/m³ readings. A generic Tuya estimated HCHO signal is unsuitable.",
        "formaldehyde_sensor_verified": "Required before comparing a measured 30-minute average against WHO's 100 µg/m³ guideline.",
        "noise_entity": "A-weighted dB(A). The integration performs logarithmic energy averaging, not arithmetic dB averaging.",
        "noise_sensor_calibrated": "Only enable if your sensor represents sampled equivalent sound levels; peak-only recordings cannot make an LAeq.",
        "illuminance_entity": "Standard lux; daylight exposure only, not circadian or melanopic effectiveness.",
        "melanopic_edi_entity": "Requires actual melanopic equivalent daylight illuminance from a spectral sensor, never an estimated conversion from lux.",
        "melanopic_spectral_verified": "Confirms the selected sensor measures melanopic EDI. The integration does not infer this from correlated color temperature.",
        "enable_pmv": "Off by default to avoid invented clothing, radiant temperature, activity and air speed.",
        "radiant_temperature_entity": "Measured mean radiant temperature, not an ordinary ambient temperature sensor in the same room.",
        "air_speed_entity": "If selected, use an actual m/s sensor; this overrides the static entered air speed.",
        "air_speed_m_s": "Only enter when you can justify an air-speed assumption; the output will be labeled an estimate.",
        "met": "For example approximately 1.0 sitting quietly or 1.2 for desk work; choose the occupant's real activity.",
        "clo": "Clothing insulation chosen for the occupant, e.g. 0.5 light summer clothing and 1.0 winter clothing.",
    },
    "errors": {
        "invalid_environment_scale": "Select a supported AQI/pollen scale and a valid threshold; no scale is guessed automatically.",
        "invalid_environment_measurement": "Check this room's numeric values and allowed units/ranges.",
        "pmv_requires_explicit_inputs": "PMV requires mean radiant temperature, air speed, clothing (clo) and activity (met). Disable it or supply them.",
    },
}
DE = {
 "global_title":"Internationale Luftqualitätsquellen und Pollen",
 "global_description":"Optional. Wähle je AQI-Sensor explizit US EPA (0–500), europäische Kategorien (1–6) oder einen eigenen Grenzwert. Unbekannte AQI-Skalen werden niemals automatisch als US-Skala interpretiert. Pollen stammen aus einer beliebigen Home-Assistant-Integration.",
 "room_title":"Raum für Umweltanalysen wählen","room_description":"Zusätzliche Sensoren und Annahmen für genau einen Raum einstellen. Alles ist optional.",
 "air_title":"Raum: {area_name} — Lüftung und Feuchtigkeit",
 "air_description":"Optional. Raumtemperatursensor, Raumvolumen und veröffentlichten Partikel-CADR nur auswählen, wenn zuverlässig bekannt. Echtes NDIR-CO₂-Gerät bestätigen. Die Integration steuert keine Geräte.",
 "exposure_title":"Raum: {area_name} — zusätzliche Spezialmessungen",
 "exposure_description":"Optional. Nur echte Messgeräte für Radon, Formaldehyd, Schall und Beleuchtung wählen. Für Leitwerte werden geprüfte Sensoren und ausreichend lange Messreihen benötigt.",
 "comfort_title":"Raum: {area_name} — vollständiger thermischer Komfort",
 "comfort_description":"Optionales ISO-7730-Modell. Strahlungstemperatur, Luftgeschwindigkeit, Aktivität (met) und Bekleidung (clo) explizit angeben.",
}
EL = {
 "global_title":"Διεθνείς πηγές ποιότητας αέρα και γύρης",
 "global_description":"Προαιρετικό. Όρισε τη σωστή κλίμακα για κάθε AQI: US EPA (0–500), ευρωπαϊκές κατηγορίες (1–6) ή προσαρμοσμένο όριο. Η εφαρμογή δεν υποθέτει χώρα ή κλίμακα. Τα δεδομένα γύρης μπορούν να προέρχονται από οποιαδήποτε ενσωμάτωση Home Assistant.",
 "room_title":"Επιλογή δωματίου για περιβαλλοντικές μετρήσεις",
 "room_description":"Ρύθμισε προαιρετικούς αισθητήρες και φυσικές παραμέτρους για ένα δωμάτιο κάθε φορά.",
 "air_title":"Δωμάτιο: {area_name} — αερισμός και υγρασία",
 "air_description":"Προαιρετικό. Διάλεξε σωστό αισθητήρα θερμοκρασίας, πραγματικό όγκο δωματίου και πιστοποιημένη απόδοση φίλτρου CADR. Επιβεβαίωσε πραγματικό αισθητήρα NDIR CO₂. Δεν γίνεται αυτόματος έλεγχος συσκευών.",
 "exposure_title":"Δωμάτιο: {area_name} — προαιρετικοί ειδικοί αισθητήρες",
 "exposure_description":"Προαιρετικά δεδομένα ραδονίου, φορμαλδεΰδης, θορύβου και φωτισμού. Οι επιστημονικές συγκρίσεις απαιτούν επαληθευμένο αισθητήρα και επαρκές ιστορικό.",
 "comfort_title":"Δωμάτιο: {area_name} — πλήρης θερμική άνεση",
 "comfort_description":"Προαιρετικό ISO 7730 PMV/PPD. Απαιτεί πραγματική ακτινοβολούμενη θερμοκρασία, ταχύτητα αέρα, δραστηριότητα (met) και ένδυση (clo).",
}
FR = {
 "global_title":"Sources internationales de qualité de l'air et pollen",
 "global_description":"Facultatif. Choisissez l'échelle de chaque capteur AQI : US EPA, catégories européennes ou seuil personnalisé. Aucune échelle n'est déduite du pays.",
 "room_title":"Choisir une pièce pour l'analyse environnementale","room_description":"Paramètres optionnels pour une seule pièce.",
 "air_title":"Pièce : {area_name} — ventilation et humidité","air_description":"Facultatif. Renseignez les capteurs réels, le volume et le CADR mesuré. Confirmez un vrai capteur CO₂ NDIR.",
 "exposure_title":"Pièce : {area_name} — capteurs spécialisés","exposure_description":"Capteurs facultatifs de radon, formaldéhyde, bruit et éclairage. Les comparaisons nécessitent des mesures vérifiées.",
 "comfort_title":"Pièce : {area_name} — confort thermique complet","comfort_description":"ISO 7730 optionnel : température radiante, vitesse de l'air, activité et vêtements obligatoires.",
}
ES = {
 "global_title":"Fuentes internacionales de calidad del aire y polen",
 "global_description":"Opcional. Selecciona la escala de cada AQI: US EPA, categorías europeas o límite personalizado. No se infiere la escala por país.",
 "room_title":"Elegir habitación para análisis ambiental","room_description":"Parámetros opcionales para una habitación.",
 "air_title":"Habitación: {area_name} — ventilación y humedad","air_description":"Opcional. Proporciona sensores correctos, volumen real y CADR de partículas. Confirma que el sensor CO₂ es NDIR real.",
 "exposure_title":"Habitación: {area_name} — sensores especializados","exposure_description":"Sensores opcionales de radón, formaldehído, ruido y luz. Los valores de referencia requieren mediciones verificadas.",
 "comfort_title":"Habitación: {area_name} — confort térmico completo","comfort_description":"ISO 7730 opcional: temperatura radiante, velocidad del aire, actividad y ropa obligatorias.",
}



LOCAL_FIELDS = {
 "de": {
 "pollen_entity":"Pollenprognose-Sensor (beliebiges Land)",
 "pollen_high_from":"Pollenindex ab diesem Wert hoch",
 "pollen_max_scale":"Maximalwert der Pollen-Skala",
 "pollen_avoid_ventilation":"Bei hoher Pollenbelastung Lüften vermeiden",
 "environment_area":"Raum auswählen",
 "temperature_entity":"Temperatursensor im Raum (optional)",
 "room_volume_m3":"Raumluftvolumen (m³)",
 "particle_cadr_m3h":"Reinigungsleistung für Partikel, CADR (m³/h)",
 "purifier_entity":"Luftreiniger: Betriebsstatus",
 "extractor_entity":"Abluftventilator / Schalter",
 "co2_ndir_verified":"Echter NDIR-CO₂-Sensor bestätigt",
 "co2_target_ppm":"CO₂-Zielwert beim Lüften (ppm)",
 "sleep_room":"Schlafzimmer",
 "radon_entity":"Echter Radonmesssensor",
 "radon_sensor_verified":"Radon-Messtechnik bestätigt",
 "formaldehyde_entity":"Formaldehyd-Messsensor (HCHO)",
 "formaldehyde_sensor_verified":"HCHO-Messung unabhängig geprüft",
 "noise_entity":"A-bewerteter Schallpegel (dB(A))",
 "noise_sensor_calibrated":"Geeignete kalibrierte Schallmessung",
 "illuminance_entity":"Beleuchtungsstärke (Lux)",
 "melanopic_edi_entity":"Spektral gemessene melanopische EDI (lx)",
 "melanopic_spectral_verified":"Spektralmessung für EDI bestätigt",
 "enable_pmv":"ISO-7730-Komfort PMV/PPD aktivieren",
 "radiant_temperature_entity":"Mittlere Strahlungstemperatur (°C)",
 "air_speed_entity":"Gemessene Luftgeschwindigkeit (m/s)",
 "air_speed_m_s":"Angenommene Luftgeschwindigkeit (m/s)",
 "met":"Aktivität des Bewohners (met)",
 "clo":"Bekleidungsisolierung des Bewohners (clo)",
 },
 "el": {
 "pollen_entity":"Αισθητήρας πρόγνωσης γύρης (οποιαδήποτε χώρα)",
 "pollen_high_from":"Υψηλή γύρη από αυτή την τιμή",
 "pollen_max_scale":"Μέγιστη τιμή κλίμακας γύρης",
 "pollen_avoid_ventilation":"Αποφυγή αερισμού με υψηλή γύρη",
 "environment_area":"Επιλογή δωματίου",
 "temperature_entity":"Αισθητήρας θερμοκρασίας δωματίου",
 "room_volume_m3":"Πραγματικός όγκος δωματίου (m³)",
 "particle_cadr_m3h":"Ονομαστικό CADR σωματιδίων (m³/h)",
 "purifier_entity":"Οντότητα λειτουργίας καθαριστή αέρα",
 "extractor_entity":"Εξαεριστήρας / διακόπτης",
 "co2_ndir_verified":"Επαληθευμένος πραγματικός αισθητήρας NDIR CO₂",
 "co2_target_ppm":"Στόχος CO₂ αερισμού (ppm)",
 "sleep_room":"Χώρος ύπνου",
 "radon_entity":"Πραγματικός αισθητήρας ραδονίου",
 "radon_sensor_verified":"Επαληθευμένη τεχνολογία ραδονίου",
 "formaldehyde_entity":"Αισθητήρας φορμαλδεΰδης (HCHO)",
 "formaldehyde_sensor_verified":"Επαληθευμένη μέτρηση φορμαλδεΰδης",
 "noise_entity":"Στάθμη θορύβου με στάθμιση Α (dB(A))",
 "noise_sensor_calibrated":"Βαθμονομημένη μέτρηση θορύβου",
 "illuminance_entity":"Φωτισμός (lux)",
 "melanopic_edi_entity":"Φασματικά μετρημένη μελανοπική EDI (lx)",
 "melanopic_spectral_verified":"Επιβεβαίωση φασματικής μέτρησης EDI",
 "enable_pmv":"Ενεργοποίηση θερμικής άνεσης ISO 7730 PMV/PPD",
 "radiant_temperature_entity":"Μέση ακτινοβολούμενη θερμοκρασία (°C)",
 "air_speed_entity":"Μετρούμενη ταχύτητα αέρα (m/s)",
 "air_speed_m_s":"Εκτιμώμενη ταχύτητα αέρα (m/s)",
 "met":"Δραστηριότητα ενοίκου (met)",
 "clo":"Θερμομόνωση ενδυμάτων (clo)",
 },
}
LOCAL_HELP = {
 "de": {
 "room_volume_m3":"Innenfläche × Raumhöhe. Nur bei bekanntem Volumen angeben; nötig für den rechnerischen Luftwechsel des Luftreinigers.",
 "particle_cadr_m3h":"Nur nachgewiesenen Partikel-CADR bei definierter Leistungsstufe verwenden, nicht den Lüftervolumenstrom; gilt nicht für Gase.",
 "co2_ndir_verified":"Nur bei nachweislich echtem CO₂-Sensor markieren. eCO₂ aus VOC-Messungen reicht nicht aus.",
 "radon_entity":"Bq/m³ oder pCi/L; für Jahresmittel sind ausreichend viele gültige Messtage erforderlich.",
 "formaldehyde_entity":"Nur ein tatsächlicher HCHO-Messsensor mit µg/m³ oder mg/m³. Schätzwerte sind ungeeignet.",
 "noise_entity":"Nur kalibrierte dB(A)-Zeitreihen; gemessene Spitzenpegel sind kein LAeq.",
 "enable_pmv":"Nur mit mittlerer Strahlungstemperatur, Luftgeschwindigkeit, Metabolismus (met) und Kleidung (clo).",
 },
 "el": {
 "room_volume_m3":"Εμβαδόν δωματίου × ύψος οροφής. Χρησιμοποιείται μόνο για θεωρητικές ανανεώσεις αέρα φίλτρου.",
 "particle_cadr_m3h":"Χρησιμοποίησε τεκμηριωμένο CADR σωματιδίων για γνωστή σκάλα λειτουργίας, όχι τυχαία παροχή ανεμιστήρα.",
 "co2_ndir_verified":"Μόνο για πραγματικό αισθητήρα CO₂ NDIR, όχι υπολογισμό eCO₂ μέσω VOC.",
 "radon_entity":"Bq/m³ ή pCi/L. Η μακροχρόνια εκτίμηση απαιτεί επαρκείς ημέρες μετρήσεων.",
 "formaldehyde_entity":"Πραγματική μέτρηση HCHO σε µg/m³ ή mg/m³. Οι εκτιμήσεις δεν είναι αξιόπιστες.",
 "noise_entity":"Βαθμονομημένες μετρήσεις dB(A)· οι στιγμιαίες κορυφές δεν είναι LAeq.",
 "enable_pmv":"Απαιτούνται ακτινοβολούμενη θερμοκρασία, ταχύτητα αέρα, δραστηριότητα (met) και ένδυση (clo).",
 },
}

def apply_environment_i18n(root: Path) -> None:
    docs = [root / "strings.json", *sorted((root / "translations").glob("*.json"))]
    for path in docs:
        lang = "en" if path.name == "strings.json" else path.stem
        localized = {"de":DE, "el":EL, "fr":FR, "es":ES}.get(lang, {})
        def label(key: str) -> str:
            return localized.get(key, EN[key])
        data = json.loads(path.read_text(encoding="utf-8"))
        data["title"] = PRODUCT
        config = data.get("config", {})
        if "abort" in config and "already_configured" in config["abort"]:
            config["abort"]["already_configured"] = config["abort"]["already_configured"].replace("Air Quality Advisor", PRODUCT)
        opt = data.setdefault("options", {})
        steps = opt.setdefault("step", {})
        init = steps.setdefault("init", {})
        menu = init.setdefault("menu_options", {})
        menu["environment"] = label("global_title")
        menu["environment_room"] = label("room_title")
        forms = (
            ("environment","global_title","global_description",
             ["pollen_entity","pollen_high_from","pollen_max_scale","pollen_avoid_ventilation"]),
            ("environment_room","room_title","room_description",["environment_area"]),
            ("environment_room_air","air_title","air_description",
             ["temperature_entity","room_volume_m3","particle_cadr_m3h","purifier_entity",
              "extractor_entity","co2_ndir_verified","co2_target_ppm","sleep_room"]),
            ("environment_room_exposure","exposure_title","exposure_description",
             ["radon_entity","radon_sensor_verified","formaldehyde_entity",
              "formaldehyde_sensor_verified","noise_entity","noise_sensor_calibrated",
              "illuminance_entity","melanopic_edi_entity","melanopic_spectral_verified"]),
            ("environment_room_comfort","comfort_title","comfort_description",
             ["enable_pmv","radiant_temperature_entity","air_speed_entity",
              "air_speed_m_s","met","clo"]),
        )
        for step,name,description,keys in forms:
            steps[step] = {
                "title": label(name), "description": label(description),
                "data": {key: LOCAL_FIELDS.get(lang, {}).get(key, EN["fields"][key]) for key in keys},
                "data_description": {key: LOCAL_HELP.get(lang, {}).get(key, EN["help"][key]) for key in keys},
            }
        for i in range(32):
            for name,value in (
                (f"aqi_scale_{i}",f"AQI sensor #{i+1}: source scale"),
                (f"aqi_custom_limit_{i}",f"AQI sensor #{i+1}: custom unsafe threshold"),
            ):
                steps["environment"]["data"][name] = value
                steps["environment"]["data_description"][name] = (
                    "Choose only the scale documented by the sensor's data provider; source entity IDs are shown above."
                    if name.startswith("aqi_scale") else
                    "Used only when the custom provider scale is selected. This is an operational policy, not a health threshold."
                )
        opt.setdefault("error", {}).update(EN["errors"])
        # Preserve compatibility keys, service IDs and entity unique IDs.
        def rebrand(value):
            if isinstance(value,dict):
                return {k:rebrand(v) for k,v in value.items()}
            if isinstance(value,list):
                return [rebrand(v) for v in value]
            return value.replace("Air Quality Advisor", PRODUCT) if isinstance(value,str) else value
        data = rebrand(data)
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
