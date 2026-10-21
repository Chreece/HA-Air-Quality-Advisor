"""Final localization pass for native Home/Area config entities."""
from __future__ import annotations

import json
from pathlib import Path

PID_FIELDS = (
    "target_c", "kp", "ki", "kd", "offset_c", "min_setpoint_c",
    "max_setpoint_c", "sample_seconds", "max_change_c", "min_change_c",
)
THRESHOLD_KEYS = (
    "outdoor_aqi", "outdoor_co2", "outdoor_pm25", "outdoor_pm10",
    "outdoor_voc", "outdoor_voc_parts", "outdoor_no2", "outdoor_o3",
    "outdoor_so2", "indoor_aqi", "indoor_co2", "indoor_pm25",
    "indoor_pm10", "indoor_voc", "indoor_voc_parts",
    "indoor_humidity", "indoor_mold",
    "min_outdoor_temp", "max_outdoor_temp", "max_outdoor_humidity",
    "max_wind_kmh", "max_age_minutes",
)
WORDS = {
    "en": ("Heating", "Cooling", "Gain source", "Defaults", "Manual", "Supervisory target"),
    "el": ("Θέρμανση", "Ψύξη", "Πηγή κερδών PID", "Προεπιλογές", "Χειροκίνητα", "Στόχος ελέγχου PID"),
    "de": ("Heizen", "Kühlen", "PID-Verstärkung", "Standardwerte", "Manuell", "PID-Raumziel"),
    "fr": ("Chauffage", "Refroidissement", "Source des gains PID", "Valeurs par défaut", "Manuel", "Cible du PID"),
    "es": ("Calefacción", "Refrigeración", "Origen de ganancias PID", "Valores iniciales", "Manual", "Objetivo PID"),
}
FALLBACK = WORDS["en"]


def apply_device_controls_i18n(root: Path) -> None:
    for path in (root / "strings.json", *sorted((root / "translations").glob("*.json"))):
        locale = "en" if path.name == "strings.json" else path.stem
        doc = json.loads(path.read_text(encoding="utf-8"))
        settings = doc.get("options", {}).get("step", {})
        delivery = settings.get("delivery", {}).get("data", {})
        threshold = settings.get("thresholds", {}).get("data", {})
        pid = settings.get("pid_tuning", {}).get("data", {})
        setup_pid = settings.get("pid_room", {}).get("data", {})
        profiles = settings.get("climate_profiles", {}).get("data", {})
        room = settings.get("climate_presence", {}).get("data", {})
        words = WORDS.get(locale, FALLBACK)
        entities = doc.setdefault("entity", {})
        number = entities.setdefault("number", {})
        switches = entities.setdefault("switch", {})
        selects = entities.setdefault("select", {})
        for key in THRESHOLD_KEYS:
            number["global_threshold_" + key] = {"name": threshold.get(key, key.replace("_", " ").title())}
        number["global_setting_announcement_repeat_minutes"] = {
            "name": delivery.get("announcement_repeat_minutes", "Announcement repeat interval")
        }
        for key in PID_FIELDS:
            caption = (setup_pid.get("pid_target_c") if key == "target_c" else
                       pid.get("pid_" + key))
            number["area_pid_" + key] = {
                "name": caption or (words[5] if key == "target_c" else "PID " + key)
            }
        for kind in ("home", "unoccupied", "away", "sleep"):
            for mode in ("heat", "cool"):
                key = kind + "_" + mode
                prefix = words[0] if mode == "heat" else words[1]
                number["area_climate_profile_" + key] = {
                    "name": prefix + " · " + profiles.get(key, kind.capitalize())
                }
        for key in ("automatic_notifications", "automatic_tts",
                    "use_announcement_hub", "ai_rewrite_announcements"):
            switches["home_" + key] = {
                "name": delivery.get(key, key.replace("_", " ").capitalize())
            }
        selects["home_language"] = {
            "name": delivery.get("language", "Output language")
        }
        selects["area_manual_profile"] = {
            "name": room.get("climate_manual_profile", "Room occupancy profile")
        }
        selects["area_pid_gain_source"] = {
            "name": words[2], "state": {"defaults": words[3], "manual": words[4]}
        }
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
