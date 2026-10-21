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
                # Climate profile labels are now completely localized in
                # all 38 languages. Avoid prepending an English "Heating"/
                # "Cooling" label a second time (or duplicating it in Greek).
                number["area_climate_profile_" + key] = {
                    "name": profiles.get(key) or (
                        prefix + " · " + kind.capitalize()
                    )
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
        # Device-first setup: reuse the existing localized options labels
        # rather than duplicating a second translation catalog.
        sections = {
            name: settings.get(name, {}).get("data", {})
            for name in (
                "indoor_sensors", "pollen", "general_settings",
                "environment_room_air", "environment_room_exposure",
                "environment_room_comfort", "climate_presence",
                "climate_equipment", "climate_air_strategy", "climate_actuators",
            )
        }
        mold_labels = {
            "el": "Εξωτερική πηγή θερμοκρασίας για μούχλα",
            "de": "Außentemperaturquelle für Schimmelindikator",
            "fr": "Source de température extérieure pour moisissure",
            "es": "Fuente de temperatura exterior para moho",
            "en": "Outdoor temperature source for mold calibration",
        }
        for scope in ("config", "options"):
            step = doc.get(scope, {}).get("step", {}).get("indoor_sensors", {})
            if isinstance(step, dict):
                fields = step.setdefault("data", {})
                fields["mold_outdoor_weather_entity"] = mold_labels.get(
                    locale, mold_labels["en"]
                )
                hints = step.setdefault("data_description", {})
                hints["mold_outdoor_weather_entity"] = fields[
                    "mold_outdoor_weather_entity"
                ]

        env_air = sections["environment_room_air"]
        env_exposure = sections["environment_room_exposure"]
        env_comfort = sections["environment_room_comfort"]
        general = sections["general_settings"]
        pollen = sections["pollen"]
        climate_presence = sections["climate_presence"]
        climate_equipment = sections["climate_equipment"]
        climate_air = sections["climate_air_strategy"]
        direct = sections["climate_actuators"]
        mold = sections["indoor_sensors"]

        for key in ("pollen_high_from", "pollen_max_scale"):
            number["global_environment_" + key] = {"name": pollen.get(key, key)}
        number["global_occupancy_source_stale_minutes"] = {
            "name": general.get("general_source_stale_minutes", "Source freshness (min)")
        }
        for key in (
            "room_volume_m3", "particle_cadr_m3h", "co2_target_ppm",
        ):
            number["area_area_environment_" + key] = {"name": env_air.get(key, key)}
        number["area_area_environment_radon_reference_bq_m3"] = {
            "name": env_exposure.get("radon_reference_bq_m3", "Radon reference")
        }
        for key in ("air_speed_m_s", "met", "clo"):
            number["area_area_environment_" + key] = {"name": env_comfort.get(key, key)}
        for key in ("unoccupied_delay_minutes", "occupancy_stale_minutes",
                    "comfort_adjustment_max_c"):
            number["area_climate_operating_" + key] = {
                "name": climate_presence.get("climate_" + key, key)
            }
        for key in ("humidity_low_rh", "humidity_high_rh",
                    "humidity_hysteresis_rh", "cooling_dry_deferral_rh_points"):
            number["area_climate_operating_" + key] = {
                "name": climate_equipment.get("climate_" + key, key)
            }
        for key in ("pm25_action_ug_m3", "extraction_speed_percent",
                    "purifier_speed_percent"):
            number["area_climate_operating_" + key] = {
                "name": climate_air.get("climate_" + key, key)
            }
        for key in ("kp", "ki", "kd", "sample_seconds",
                    "max_demand_change", "min_demand_change"):
            number["area_direct_tuning_" + key] = {"name": direct.get(key, key)}
        number["area_mold_surface_critical_temperature_c"] = {
            "name": mold.get("mold_critical_temperature_c", "Measured coldest surface °C")
        }

        switches["home_global_environment_pollen_avoid_ventilation"] = {
            "name": pollen.get("pollen_avoid_ventilation", "Avoid ventilation when pollen high")
        }
        for key in ("sleep_room",):
            switches["area_area_environment_" + key] = {"name": env_air.get(key, key)}
        switches["area_area_environment_enable_pmv"] = {
            "name": env_comfort.get("enable_pmv", "Enable PMV/PPD calculation")
        }
        for key in ("sleep_active", "sleep_schedule_enabled"):
            switches["area_climate_operating_" + key] = {
                "name": climate_presence.get("climate_" + key, key)
            }
        switches["area_climate_operating_window_efficiency_notify"] = {
            "name": climate_equipment.get("climate_window_efficiency_notify",
                                          "Window efficiency notifications")
        }

        selects["home_global_policy_home_policy"] = {
            "name": general.get("general_home_policy", "Presence combination policy")
        }
        for key in ("unknown_occupancy", "away_policy", "target_source"):
            selects["area_climate_policy_" + key] = {
                "name": climate_presence.get("climate_" + key, key)
            }
        entity_time = doc.setdefault("entity", {}).setdefault("time", {})
        for key in ("sleep_start", "sleep_end"):
            entity_time["area_climate_" + key] = {
                "name": climate_presence.get("climate_" + key, key)
            }
        doc.setdefault("entity", {}).setdefault("button", {})[
            "area_recalculate_mold"
        ] = {"name": mold.get("mold_recalibrate", "Recalculate mold factor")}

        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
