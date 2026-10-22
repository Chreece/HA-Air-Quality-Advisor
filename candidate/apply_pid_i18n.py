"""Consistent, optional PID climate-control setup strings for all existing locales.

The five primary languages have reviewed PID terminology; remaining languages
retain the legacy translations and English fallback for only the new PID fields.
This does not change or translate internal Home Assistant entity identifiers.
"""
from __future__ import annotations

import json
from pathlib import Path

TEXT = {
    "en": {
        "select": "Climate PID — select a room",
        "select_help": "Optional and disabled by default. Choose exactly one monitored room. A room's PID never controls climate devices in a different assigned Home Assistant area.",
        "setup": "Climate PID in {area_name} — devices and comfort target",
        "setup_help": "Enable PID only after selecting real room temperature measurements and the climate devices you authorize. The existing thermostat must already be in heat or cool mode. Windows with open or unknown contacts stop PID commands. No HVAC mode or compressor switching is performed.",
        "tuning": "Climate PID in {area_name} — advanced safety and tuning",
        "tuning_help": "Kp in %/°C, Ki in %/(°C·minute), Kd in %·minute/°C. The output only trims the existing thermostat setpoint within a bounded range, at limited intervals. Start with defaults; tune gradually after reviewing room trends. Manual setpoint changes pause PID until you explicitly resume it.",
    },
    "de": {
        "select": "Klima-PID — Raum wählen",
        "select_help": "Optional und standardmäßig ausgeschaltet. Wähle einen überwachten Raum; fremde Räume werden nicht angesteuert.",
        "setup": "Klima-PID in {area_name} — Geräte und Sollwert",
        "setup_help": "Aktiviere PID nur mit geeignetem Raumtemperatursensor und ausdrücklich gewählten Klimageräten. Der Heiz-/Kühlmodus muss bereits eingestellt sein. Geöffnete oder unbekannte Fenster halten die Regelung an. Kein Ein-/Ausschalten des Kompressors.",
        "tuning": "Klima-PID in {area_name} — Regelparameter und Sicherheit",
        "tuning_help": "Kp: %/°C; Ki: %/(°C·min), Kd: %·min/°C. Die Regelung verändert nur den begrenzten Sollwert. Standardwerte zunächst beibehalten; manuelle Änderungen pausieren den PID bis zum ausdrücklichen Fortsetzen.",
    },
    "el": {
        "select": "Κλιματικός PID — επιλογή δωματίου",
        "select_help": "Προαιρετικό, αρχικά απενεργοποιημένο. Επίλεξε ένα δωμάτιο. Δεν ελέγχονται συσκευές άλλων χώρων.",
        "setup": "Κλιματικός PID στο {area_name} — συσκευές και στόχος",
        "setup_help": "Ενεργοποίησε μόνο με πραγματικό αισθητήρα θερμοκρασίας και ρητά επιλεγμένες συσκευές climate. Η θέρμανση/ψύξη πρέπει να είναι ήδη ενεργή. Με ανοιχτά ή άγνωστα παράθυρα ο PID αναστέλλεται. Δεν αλλάζει τρόπους HVAC ή συμπιεστές.",
        "tuning": "Κλιματικός PID στο {area_name} — προηγμένες ρυθμίσεις και ασφάλεια",
        "tuning_help": "Kp: %/°C, Ki: %/(°C·λεπτό), Kd: %·λεπτό/°C. Ελεγχόμενη αλλαγή μόνο του setpoint. Ξεκίνησε με τις προεπιλογές. Χειροκίνητη αλλαγή του θερμοστάτη διακόπτει τον PID μέχρι ρητή συνέχιση.",
    },
    "fr": {
        "select": "PID climatique — choisir une pièce",
        "select_help": "Facultatif et désactivé par défaut. Choisir une seule pièce et ses propres appareils.",
        "setup": "PID climatique dans {area_name} — appareils et température",
        "setup_help": "Activer seulement avec un vrai capteur de température et des appareils autorisés. Le mode chauffage/refroidissement doit déjà être actif. Une fenêtre ouverte ou inconnue suspend les commandes. Aucun changement de mode HVAC.",
        "tuning": "PID climatique dans {area_name} — réglages avancés et sécurité",
        "tuning_help": "Kp en %/°C, Ki en %/(°C·min) et Kd en %·min/°C. La consigne reste limitée. Les changements manuels suspendent le PID jusqu'à la reprise explicite.",
    },
    "es": {
        "select": "PID climático — elegir habitación",
        "select_help": "Opcional y desactivado por defecto. Selecciona una habitación y sus dispositivos.",
        "setup": "PID climático en {area_name} — dispositivos y objetivo",
        "setup_help": "Activa solo con un sensor de temperatura real y los dispositivos autorizados. El equipo debe estar ya en calefacción o refrigeración. Ventanas abiertas o desconocidas suspenden el control. No cambia el modo HVAC.",
        "tuning": "PID climático en {area_name} — parámetros avanzados y seguridad",
        "tuning_help": "Kp en %/°C, Ki en %/(°C·min), Kd en %·min/°C. La consigna se limita. Los cambios manuales pausan el PID hasta reanudarlo explícitamente.",
    },
}

EN = {
    "pid_area": ("Monitored room to configure", "Only that room's explicitly selected climate entities may be controlled."),
    "pid_enabled": ("Enable supervisory climate PID for this room", "Off by default. Enable only after verifying the temperature sensor, climate devices and safe setpoint range."),
    "pid_climate_entities": ("Authorized climate devices", "Select the exact thermostats in this room. This controller will not broadcast to a device, area or entire integration."),
    "pid_temperature_entity": ("Independent room temperature sensor", "Required. Fresh reading no older than 10 minutes; unavailable or stale values stop control. °C/°F supported."),
    "pid_mode": ("Existing thermostat mode", "Choose heat or cool to match the device's current mode. PID never powers on HVAC or changes modes."),
    "pid_target_c": ("Desired room temperature (°C)", "The requested room temperature, not a compressor duty cycle or proof of thermal comfort."),
    "pid_pause_on_window_open": ("Pause when any room window is open or unknown", "Strongly recommended. No thermostat commands while the selected room's window contacts are open or unavailable."),
    "pid_kp": ("Proportional gain Kp (% per °C)", "Start with default 22. High values may cause undesirable thermostat setpoint hunting."),
    "pid_ki": ("Integral gain Ki (% per °C-minute)", "Start with 0.25. Conditional anti-windup stops integration at saturated limits."),
    "pid_kd": ("Derivative gain Kd (%·minute per °C)", "Default 0. Derivative is based on the filtered measured temperature, avoiding a setpoint kick."),
    "pid_offset_c": ("Maximum thermostat setpoint trim (°C)", "Full PID demand moves heating setpoint up by this offset or cooling setpoint down by this offset; no HVAC mode switching."),
    "pid_min_setpoint_c": ("Lowest permitted setpoint (°C)", "Hard operational floor; device min/max are additional hard limits."),
    "pid_max_setpoint_c": ("Highest permitted setpoint (°C)", "Hard operational ceiling; device min/max are additional hard limits."),
    "pid_sample_seconds": ("PID measurement cycle (seconds)", "At least 120 seconds. A 300-second cycle is the conservative default; no repeated commands on every sensor event."),
    "pid_max_change_c": ("Maximum setpoint change per cycle (°C)", "Setpoint rate limiter. Defaults to 0.5 °C per control cycle and cannot be bypassed by a large error."),
    "pid_min_change_c": ("Minimum meaningful setpoint change (°C)", "Avoids needless chatter from small temperature differences or device quantization."),
}
DE = {
    "pid_area":"Zu konfigurierender Raum","pid_enabled":"Klima-PID für diesen Raum aktivieren",
    "pid_climate_entities":"Ausdrücklich zugelassene Klimageräte",
    "pid_temperature_entity":"Raumtemperatursensor (maximal 10 Minuten alt)",
    "pid_mode":"Aktueller Heiz-/Kühlmodus","pid_target_c":"Raum-Solltemperatur (°C)",
    "pid_pause_on_window_open":"Bei offenem oder unbekanntem Fenster pausieren",
    "pid_kp":"Proportionalverstärkung Kp (%/°C)",
    "pid_ki":"Integralverstärkung Ki (%/(°C·min))",
    "pid_kd":"Differentialverstärkung Kd (%·min/°C)",
    "pid_offset_c":"Maximale Sollwertabweichung (°C)",
    "pid_min_setpoint_c":"Niedrigster zulässiger Sollwert (°C)",
    "pid_max_setpoint_c":"Höchster zulässiger Sollwert (°C)",
    "pid_sample_seconds":"PID-Abtastintervall (Sekunden)",
    "pid_max_change_c":"Maximale Sollwertänderung je Intervall (°C)",
    "pid_min_change_c":"Minimale sinnvolle Sollwertänderung (°C)",
}
EL = {
    "pid_area":"Δωμάτιο προς ρύθμιση","pid_enabled":"Ενεργοποίηση κλιματικού PID σε αυτό το δωμάτιο",
    "pid_climate_entities":"Ρητά επιτρεπόμενες συσκευές climate",
    "pid_temperature_entity":"Αισθητήρας θερμοκρασίας (έως 10 λεπτά παλαιός)",
    "pid_mode":"Τρέχουσα λειτουργία θέρμανσης/ψύξης",
    "pid_target_c":"Επιθυμητή θερμοκρασία δωματίου (°C)",
    "pid_pause_on_window_open":"Παύση όταν παράθυρο είναι ανοιχτό ή άγνωστο",
    "pid_kp":"Αναλογικός συντελεστής Kp (%/°C)",
    "pid_ki":"Ολοκληρωτικός συντελεστής Ki (%/(°C·λεπτό))",
    "pid_kd":"Διαφορικός συντελεστής Kd (%·λεπτό/°C)",
    "pid_offset_c":"Μέγιστη μεταβολή επιθυμητής θερμοκρασίας (°C)",
    "pid_min_setpoint_c":"Κατώτατο επιτρεπόμενο setpoint (°C)",
    "pid_max_setpoint_c":"Ανώτατο επιτρεπόμενο setpoint (°C)",
    "pid_sample_seconds":"Διάστημα δειγματοληψίας PID (δευτ.)",
    "pid_max_change_c":"Μέγιστη αλλαγή ανά κύκλο (°C)",
    "pid_min_change_c":"Ελάχιστη ουσιαστική αλλαγή (°C)",
}
FR = {
    "pid_area":"Pièce à configurer","pid_enabled":"Activer le PID climatique",
    "pid_climate_entities":"Appareils climatiques autorisés",
    "pid_temperature_entity":"Capteur de température de la pièce",
    "pid_mode":"Mode chauffage/refroidissement existant",
    "pid_target_c":"Température souhaitée de la pièce (°C)",
    "pid_pause_on_window_open":"Suspendre si une fenêtre est ouverte ou inconnue",
}
ES = {
    "pid_area":"Habitación a configurar","pid_enabled":"Activar PID climático",
    "pid_climate_entities":"Equipos climáticos autorizados",
    "pid_temperature_entity":"Sensor de temperatura de la habitación",
    "pid_mode":"Modo actual de calefacción/refrigeración",
    "pid_target_c":"Objetivo de temperatura (°C)",
    "pid_pause_on_window_open":"Pausar si una ventana está abierta o desconocida",
}
ERRORS = {
    "pid_climate_required":"Select at least one supported, explicitly authorized climate entity for this room.",
    "pid_temperature_required":"Select a valid room temperature sensor before enabling PID.",
    "pid_invalid_target":"Heat/cool mode and target temperature must be valid.",
    "pid_duplicate_climate":"A selected climate device is already controlled by another room.",
    "pid_invalid_parameters":"Review gain settings, target limits, sample interval and setpoint rate limits.",
}

def apply_pid_i18n(root: Path) -> None:
    paths = [root / "strings.json", *sorted((root / "translations").glob("*.json"))]
    for path in paths:
        lang = "en" if path.name == "strings.json" else path.stem.lower().replace("-","_")
        local = TEXT.get(lang, TEXT["en"])
        labels = {"de":DE, "el":EL, "fr":FR, "es":ES}.get(lang,{})
        data = json.loads(path.read_text(encoding="utf-8"))
        options = data.setdefault("options", {})
        steps = options.setdefault("step", {})
        init = steps.setdefault("init", {})
        init.setdefault("menu_options", {})["pid"] = local["select"]
        steps["pid"] = {
            "title": local["select"],"description": local["select_help"],
            "data": {"pid_area":labels.get("pid_area",EN["pid_area"][0])},
            "data_description":{"pid_area":EN["pid_area"][1]},
        }
        for step, title, help_key, names in [
            ("pid_room","setup","setup_help",
             ["pid_enabled","pid_climate_entities","pid_temperature_entity",
              "pid_mode","pid_target_c","pid_pause_on_window_open"]),
            ("pid_tuning","tuning","tuning_help",
             ["pid_kp","pid_ki","pid_kd","pid_offset_c","pid_min_setpoint_c",
              "pid_max_setpoint_c","pid_sample_seconds","pid_max_change_c",
              "pid_min_change_c"]),
        ]:
            steps[step] = {
                "title": local[title],"description":local[help_key],
                "data":{key:labels.get(key,EN[key][0]) for key in names},
                "data_description":{key:EN[key][1] for key in names},
            }
        options.setdefault("error", {}).update(ERRORS)
        data.setdefault("services", {})["pid_control"] = {
            "name": "PID climate control",
            "description": "Explicitly pause, resume or reset a room controller. Climate modes are never switched.",
            "fields": {
                "area":{"name": "Room", "description":"Explicit Home Assistant room ID"},
                "action":{"name":"Action","description":"Pause, resume, or reset (reset stays paused)"},
            },
        }
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
