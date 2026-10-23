"""Localized per-device climate/algorithm/PID/quiet controls, after flow labels."""
from __future__ import annotations

import json
from pathlib import Path

HELP = {
    "en": "Existing keeps the previous room controller. Manual follows only your explicit targets and native choices, not occupancy changes. Automatic follows room/preset policy; PID uses verified feedback and slow duty cycles for commissioned on/off equipment. Off stops this controller and requests owned equipment OFF after its minimum run time. Power changes require the exact device's hardware commissioning; a running manual device must first be turned off before automatic power ownership. Low-noise switches limit a supported native fan, not measured sound pressure, and never start an appliance. Restart or manual-override pauses require explicit reconciliation; changing a preset cannot clear them.",
    "el": "Η υφιστάμενη ρύθμιση διατηρεί τον προηγούμενο ελεγκτή χώρου. Η χειροκίνητη λειτουργία ακολουθεί μόνο τους στόχους και τις επιλογές σου, όχι αλλαγές παρουσίας. Η αυτόματη λειτουργία ακολουθεί το προφίλ χώρου· το PID χρησιμοποιεί επαληθευμένες μετρήσεις και αργούς κύκλους για εγκεκριμένες συσκευές on/off. Η απενεργοποίηση ζητά διακοπή του ελεγχόμενου εξοπλισμού μετά τον ελάχιστο χρόνο λειτουργίας. Απαιτείται έλεγχος ασφαλείας της συγκεκριμένης συσκευής· μια χειροκίνητα ενεργή συσκευή πρέπει πρώτα να κλείσει πριν παραδοθεί στον αυτόματο έλεγχο ισχύος. Οι επιλογές χαμηλού θορύβου περιορίζουν την εγγενή ταχύτητα ανεμιστήρα, όχι μετρημένα ντεσιμπέλ, και δεν ενεργοποιούν συσκευές. Παύσεις λόγω επανεκκίνησης ή χειροκίνητης παρέμβασης απαιτούν ρητή επαλήθευση και συνέχιση.",
    "de": "Die bisherige Einstellung behält die Raumregelung bei. Manuell folgt nur ausdrücklich gesetzten Sollwerten und Geräteoptionen, nicht wechselnder Anwesenheit. Automatik nutzt Raumprofile; PID verwendet geprüfte Messwerte und langsame Taktung für freigegebene Ein/Aus-Geräte. Aus fordert für selbst eingeschaltete Geräte erst nach der Mindestlaufzeit ein Abschalten an. Leistungsschaltungen erfordern die Inbetriebnahme genau dieses Geräts; ein manuell laufendes Gerät muss vor der automatischen Leistungsübernahme ausgeschaltet werden. Leiser Betrieb begrenzt eine unterstützte Lüfterstufe, keine gemessenen Dezibel, und schaltet Geräte niemals ein. Neustart- oder Eingriffspausen benötigen einen ausdrücklichen Abgleich; ein Profilwechsel hebt sie nicht auf.",
    "fr": "Le réglage existant conserve le régulateur de pièce. Le mode manuel suit uniquement vos consignes et choix natifs, sans suivre la présence. Le mode automatique applique les profils; le PID utilise des mesures vérifiées et des cycles lents pour les équipements marche/arrêt autorisés. Arrêt demande l'extinction des équipements démarrés par le contrôleur après leur durée minimale. La commutation exige la mise en service de cet appareil; un appareil déjà actif manuellement doit être arrêté avant transfert automatique. Le mode silencieux limite une vitesse native, pas des décibels mesurés, et ne démarre jamais l'appareil. Les pauses après redémarrage ou intervention manuelle exigent une vérification explicite.",
    "es": "La opción existente conserva el controlador de la estancia. Manual sigue solo las consignas y opciones nativas elegidas, no los cambios de presencia. Automático aplica perfiles; PID usa mediciones verificadas y ciclos lentos para equipos de encendido/apagado autorizados. Apagado solicita detener los equipos que controla después del tiempo mínimo de marcha. La conmutación requiere verificar ese dispositivo; un equipo activo manualmente debe apagarse antes de transferir el control automático de potencia. El modo silencioso limita una velocidad nativa, no decibelios medidos, y nunca enciende un aparato. Las pausas por reinicio o intervención manual requieren verificación explícita.",
}


DEVICE_APPROVAL_HELP = {
    "en": "Choose Automatic, Manual or PID on this controller device; no Configure approval is required. Selecting a method authorizes only this device's native setpoint/speed path. Allow power and HVAC mode control is a separate switch here: enable it only after checking the actual equipment protections. Minimum ON/OFF times and maximum runtime remain enforced. Sensor/identity changes require a new method selection. A running manually controlled appliance is not silently adopted; verify OFF before automatic power ownership. Fan purpose and verified feedback are also configured here. No preset clears a restart or manual-override pause.",
    "el": "Επίλεξε Αυτόματο, Χειροκίνητο ή PID σε αυτή τη συσκευή ελέγχου, χωρίς έγκριση από τη Ρύθμιση της ενσωμάτωσης. Η επιλογή μεθόδου επιτρέπει μόνο τους εγγενείς στόχους και την ταχύτητα αυτής της συσκευής. Ο ξεχωριστός διακόπτης εδώ επιτρέπει έλεγχο ισχύος και λειτουργίας κλιματισμού, αφού ελέγξεις τις προστασίες του εξοπλισμού. Διατηρούνται οι ελάχιστοι χρόνοι ON/OFF και η μέγιστη συνεχής λειτουργία. Αλλαγή αισθητήρων ή ταυτότητας απαιτεί νέα επιλογή μεθόδου. Συσκευή που λειτουργεί χειροκίνητα δεν αναλαμβάνεται αυτόματα. Ο σκοπός ανεμιστήρα και η επαλήθευση μέτρησης ρυθμίζονται επίσης εδώ. Τα προφίλ δεν αναιρούν παύση λόγω επανεκκίνησης ή χειροκίνητης παρέμβασης.",
    "de": "Automatik, Manuell oder PID direkt an diesem Steuergerät wählen; eine Freigabe im Konfigurationsdialog ist nicht erforderlich. Die Auswahl erlaubt nur die nativen Sollwert-/Drehzahlbefehle dieses Geräts. Leistung und HLK-Moduswechsel werden hier separat freigegeben, nachdem die realen Geräteschutzfunktionen geprüft wurden. Mindest-Ein-/Auszeiten und maximale Laufzeit bleiben wirksam. Geänderte Messquellen oder Geräteidentität erfordern eine erneute Verfahrenswahl. Manuell laufende Geräte werden nicht automatisch übernommen. Lüfterzweck und bestätigte Messquelle sind ebenfalls hier einstellbar. Profile lösen keine Neustart- oder Eingriffspause auf.",
    "fr": "Choisissez Automatique, Manuel ou PID sur ce contrôleur sans passer par Configurer. Le choix autorise uniquement ses consignes et vitesses natives. Un interrupteur séparé permet les changements de puissance et de mode après vérification des protections réelles. Les durées minimales marche/arrêt et la durée maximale restent actives. Un changement de capteur ou d'identité exige une nouvelle sélection de méthode. Un appareil actif manuellement n'est pas adopté automatiquement. Le rôle du ventilateur et la vérification du capteur se règlent ici. Les profils n'annulent pas les pauses de sécurité.",
    "es": "Elige Automático, Manual o PID en este controlador sin pasar por Configurar. La elección autoriza solo sus consignas y velocidades nativas. Un interruptor separado permite cambios de potencia y modo tras comprobar las protecciones reales. Se conservan los tiempos mínimos de encendido/apagado y el máximo de funcionamiento. Cambiar sensores o identidad requiere volver a elegir el método. No se toma el control de un aparato activado manualmente. La función del ventilador y la verificación del sensor se ajustan aquí. Los perfiles no cancelan las pausas de seguridad.",
}
POWER_NAMES = {"en": "Allow power and HVAC mode control", "el": "Να επιτρέπεται έλεγχος ισχύος και λειτουργίας",
    "de": "Leistung und HLK-Moduswechsel erlauben", "fr": "Autoriser puissance et modes climatiques",
    "es": "Permitir control de potencia y modos"}


def apply_equipment_i18n(root: Path) -> None:
    labels = json.loads((root / "equipment_labels.json").read_text(encoding="utf-8"))
    vocabulary = json.loads((root / "compact_locales.json").read_text(encoding="utf-8"))
    paths = sorted((root / "translations").glob("*.json"))
    if set(labels) != {p.stem for p in paths} or len(labels) != 38:
        raise ValueError("Every supported locale needs equipment controller labels")
    help_by_locale = {}
    for path in [root / "strings.json", *paths]:
        lang = "en" if path.name == "strings.json" else path.stem
        words, v = labels[lang], vocabulary[lang]
        doc = json.loads(path.read_text(encoding="utf-8"))
        steps = doc["options"]["step"]
        pid = steps["pid_tuning"]["data"]
        actuator = steps["climate_actuators"]["data"]
        previous_help = steps["device_settings"]["data_description"]
        help_text = DEVICE_APPROVAL_HELP.get(lang) or " ".join(previous_help[key] for key in (
            "device_method", "device_hardware_confirmed", "device_min_on_s", "device_min_off_s",
            "device_sleep_behavior", "device_fan_speed_percent"))
        help_by_locale[lang] = help_text
        steps["device_settings"]["description"] = help_text + "\n\n{device_name} · {device_entity} · {area_name}"
        # Existing localized per-field safety descriptions remain unchanged.
        entities = doc.setdefault("entity", {})
        def add(domain, key, name, **extra):
            entities.setdefault(domain, {})["equipment_" + key] = {"name": "{channel}" + name, **extra}
        add("climate", "climate", words["climate"])
        add("select", "control_mode", words["control_mode"], state={
            "existing": words["existing"], "automatic": v["automatic"],
            "manual": words["manual"], "off": v["off"], "pid": "PID",
        })
        add("select", "quiet_fan_mode", words["quiet_fan_mode"])
        add("button", "resume", words["resume"])
        for key in ("quiet_sleep", "quiet_occupied"):
            add("switch", key, words[key])
        for key in ("kp", "ki", "kd", "sample_seconds"):
            add("number", key, pid["pid_" + key])
        add("number", "cycle_seconds", actuator.get("pwm_period_s") or
            (v["power"] + " · PID · " + pid["pid_sample_seconds"]))
        add("number", "quiet_percentage", words["quiet_percentage"] + " (%)")
        data = steps["device_settings"]["data"]
        add("switch", "allow_power", POWER_NAMES.get(lang) or (v["power"] + " · " + v["control"]))
        add("switch", "sensor_verified", data["device_sensor_verified"])
        for key in ("presence_requirement", "sleep_behavior", "fan_purpose"):
            states = dict(doc["selector"]["device_" + key]["options"])
            if key == "fan_purpose":
                states["auto"] = v["automatic"]
            add("select", key, data["device_" + key], state=states)
        for key, old in (("min_on_seconds", "min_on_s"), ("min_off_seconds", "min_off_s"), ("max_on_seconds", "max_on_s")):
            add("number", key, data["device_" + old])
        comfort = steps["environment_room_comfort"]["data"]
        for key in ("radiant_temperature_entity", "air_speed_entity"):
            entities.setdefault("select", {})["area_area_science_" + key] = {"name": comfort[key]}
        from apply_device_picker_i18n import apply_device_picker_document
        apply_device_picker_document(doc, lang)
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "equipment_text.py").write_text(
        '"""Generated device-controller help. Edit apply_equipment_i18n.py, not this file."""\n'
        + 'DEVICE_HELP = ' + json.dumps(help_by_locale, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
        encoding="utf-8")
