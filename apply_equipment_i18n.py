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
    "en": "Choose Automatic, Manual or PID on this controller device; no Configure approval or second power switch is required. Selecting the method authorizes this exact native controller to regulate its supported setpoint/speed and to turn the physical device or supported HVAC mode ON/OFF when demand requires it. Minimum ON/OFF times, maximum runtime, windows, availability and hardware protections remain enforced. Sensor/identity changes require a new method selection. A running manually controlled appliance is not silently adopted; verify OFF before automatic ownership. Fan purpose and verified feedback are also configured here.",
    "el": "Επίλεξε Αυτόματο, Χειροκίνητο ή PID σε αυτή τη συσκευή ελέγχου· δεν απαιτείται δεύτερος διακόπτης ισχύος. Η επιλογή της μεθόδου εξουσιοδοτεί αυτόν ακριβώς τον εγγενή ελεγκτή να ρυθμίζει στόχους/ταχύτητα και να ενεργοποιεί ή να απενεργοποιεί τη φυσική συσκευή ή την υποστηριζόμενη λειτουργία HVAC όταν υπάρχει ζήτηση. Οι ελάχιστοι χρόνοι ON/OFF, η μέγιστη λειτουργία, τα παράθυρα, η διαθεσιμότητα και οι προστασίες υλικού εξακολουθούν να εφαρμόζονται. Αλλαγή αισθητήρων ή ταυτότητας απαιτεί νέα επιλογή μεθόδου.",
    "de": "Automatik, Manuell oder PID direkt an diesem Steuergerät wählen; ein zweiter Leistungsschalter ist nicht erforderlich. Die Methodenwahl autorisiert genau diesen nativen Regler, unterstützte Sollwerte/Drehzahlen zu regeln und das physische Gerät bzw. den unterstützten HLK-Modus bei Bedarf ein- und auszuschalten. Mindest-Ein-/Auszeiten, maximale Laufzeit, Fenster-, Verfügbarkeits- und Geräteschutzregeln bleiben wirksam. Geänderte Messquellen oder Geräteidentität erfordern eine erneute Methodenwahl.",
    "fr": "Choisissez Automatique, Manuel ou PID sur ce contrôleur; aucun second interrupteur de puissance n'est nécessaire. Le choix de la méthode autorise ce contrôleur natif précis à régler ses consignes/vitesses et à démarrer ou arrêter l'appareil physique ou le mode CVC pris en charge lorsque la demande l'exige. Les durées minimales marche/arrêt, la durée maximale, les fenêtres, la disponibilité et les protections matérielles restent appliquées.",
    "es": "Elige Automático, Manual o PID en este controlador; no hace falta un segundo interruptor de potencia. Elegir el método autoriza exactamente a este controlador nativo a regular sus consignas/velocidades y a encender o apagar el dispositivo físico o el modo HVAC compatible cuando exista demanda. Se mantienen los tiempos mínimos de encendido/apagado, el máximo de funcionamiento, las ventanas, la disponibilidad y las protecciones del equipo.",
}
STATUS_NAMES = {
  "ar": "حالة وحدة التحكم",
  "bg": "Състояние на контролера",
  "bn": "কন্ট্রোলারের অবস্থা",
  "cs": "Stav regulátoru",
  "da": "Regulatorstatus",
  "de": "Reglerstatus",
  "el": "Κατάσταση ελεγκτή",
  "en": "Controller status",
  "es": "Estado del controlador",
  "fa": "وضعیت کنترل‌کننده",
  "fi": "Säätimen tila",
  "fr": "État du contrôleur",
  "he": "מצב הבקר",
  "hi": "नियंत्रक की स्थिति",
  "hr": "Stanje regulatora",
  "hu": "Vezérlő állapota",
  "id": "Status pengendali",
  "it": "Stato del controller",
  "ja": "コントローラーの状態",
  "ko": "컨트롤러 상태",
  "nb": "Regulatorstatus",
  "nl": "Status van de regelaar",
  "pl": "Stan sterownika",
  "pt-BR": "Status do controlador",
  "pt": "Estado do controlador",
  "ro": "Starea controlerului",
  "ru": "Состояние контроллера",
  "sk": "Stav regulátora",
  "sr": "Стање контролера",
  "sv": "Regulatorstatus",
  "ta": "கட்டுப்படுத்தி நிலை",
  "th": "สถานะตัวควบคุม",
  "tr": "Denetleyici durumu",
  "uk": "Стан контролера",
  "ur": "کنٹرولر کی حالت",
  "vi": "Trạng thái bộ điều khiển",
  "zh-Hans": "控制器状态",
  "zh-Hant": "控制器狀態"
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
    if set(STATUS_NAMES) != set(labels):
        raise ValueError("Controller status requires a name in all 38 languages")
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
        add("sensor", "control_status", STATUS_NAMES[lang])
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
        add("switch", "sensor_verified", data["device_sensor_verified"])
        for key in ("presence_requirement", "sleep_behavior", "fan_purpose"):
            states = dict(doc["selector"]["device_" + key]["options"])
            if key == "presence_requirement":
                states = {
                    "always": states.get("always", v["automatic"]),
                    "occupied": states.get("room", f"{v['room']} · {v['presence']}"),
                    "absent": f"{v['room']} · {v['presence']} · {v['off']}",
                }
            elif key == "fan_purpose":
                states["auto"] = v["automatic"]
            add("select", key, data["device_" + key], state=states)
        for key, old in (("min_on_seconds", "min_on_s"), ("min_off_seconds", "min_off_s"), ("max_on_seconds", "max_on_s")):
            add("number", key, data["device_" + old])
        room_limits = (
            ("temperature_min_limit", f"{v['room']} · {v['temperature']} · min"),
            ("temperature_max_limit", f"{v['room']} · {v['temperature']} · max"),
            ("humidity_min_limit", f"{v['room']} · {v['humidity']} · min"),
            ("humidity_max_limit", f"{v['room']} · {v['humidity']} · max"),
            ("fan_min_percentage", f"{v['room']} · {v['speed']} · min (%)"),
            ("fan_max_percentage", f"{v['room']} · {v['speed']} · max (%)"),
        )
        for key, label in room_limits:
            entities.setdefault("number", {}).pop("equipment_" + key, None)
            entities["number"]["area_room_equipment_limit_" + key] = {"name": label}
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
