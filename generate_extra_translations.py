"""Generate installed Home Assistant translations for additional languages.

Preserves the five native, longer-form translations. The additional locales use
native labels and compact, stable descriptions based on one canonical catalog.
Technical units / comparison directions are intentionally language-independent.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parent / "custom_components" / "enviroment_manager"
PACKS = ("locale_pack_europe.py", "locale_pack_europe2.py", "locale_pack_global.py")
STEPS = ("areas", "window_sensors", "indoor_sensors", "outdoor",
         "weather", "delivery", "thresholds")
LIMIT_NAMES = {
    "aqi": "AQI", "co2": "CO₂ (ppm)", "pm25": "PM2.5 (µg/m³)",
    "pm10": "PM10 (µg/m³)", "voc": "VOC (µg/m³)",
    "voc_parts": "VOC (ppb)", "humidity": "RH (%)",
}


def locale_catalog() -> dict:
    result = {}
    for filename in PACKS:
        data = runpy.run_path(str(ROOT / filename))["LOCALES"]
        overlap = set(result).intersection(data)
        if overlap:
            raise ValueError(f"Duplicate locale tags: {sorted(overlap)}")
        result.update(data)
    return result


def generate_extended(root: Path = ROOT) -> None:
    english = json.loads((root / "translations/en.json").read_text(encoding="utf-8"))
    for locale, entry in locale_catalog().items():
        ui, card = entry["ui"], entry["card"]
        obj = copy.deepcopy(english)
        titles = dict(zip(STEPS, ui[:7]))
        metric_names = dict(LIMIT_NAMES)
        labels = {
            "areas": {"areas": ui[0]},
            "window_sensors": {"excluded_window_entities": ui[1]},
            "indoor_sensors": {"excluded_indoor_entities": ui[2]},
            "outdoor": {"outdoor_sensors": ui[3]},
            "weather": {"weather_entities": ui[4], "weather_warnings": card[8]},
            "delivery": {
                "language": ui[17], "automatic_tts": ui[16],
                "automatic_notifications": ui[15],
                "announcement_repeat_minutes": f"{ui[5]} · 0–1440 min",
                "use_announcement_hub": "Announcement Hub",
                "notify_entities": ui[15], "tts_engine": ui[16],
                "media_players": ui[16],
                "ai_rewrite_announcements": f"AI · {ui[5]}",
                "ai_conversation_agent": f"AI · {ui[17]}",
            },
        }
        threshold_labels = {}
        for key in english["config"]["step"]["thresholds"]["data"]:
            if key.startswith("outdoor_"):
                metric = key.removeprefix("outdoor_")
                threshold_labels[key] = f"{ui[18]} · {metric_names.get(metric, metric)} (≤)"
            elif key.startswith("indoor_"):
                metric = key.removeprefix("indoor_")
                threshold_labels[key] = f"{ui[7]} · {metric_names.get(metric, metric)} (≥)"
            elif key == "min_outdoor_temp":
                threshold_labels[key] = f"{ui[18]} · °C (≥)"
            elif key == "max_outdoor_temp":
                threshold_labels[key] = f"{ui[18]} · °C (≤)"
            elif key == "max_outdoor_humidity":
                threshold_labels[key] = f"{ui[18]} · RH (%) (≤)"
            elif key == "max_wind_kmh":
                threshold_labels[key] = f"{ui[4]} · km/h (≤)"
            elif key == "max_age_minutes":
                threshold_labels[key] = f"⏱ · {ui[13]} (min, ≤)"
            else:
                threshold_labels[key] = english["config"]["step"]["thresholds"]["data"][key]
        descriptions = {
            "areas": f"1 · 🪟 {ui[0]}. binary_sensor (device_class: window).",
            "window_sensors": f"2 · {ui[1]}. ☑ 🚫 · ☐ ✓. binary_sensor (window).",
            "indoor_sensors": f"{ui[0]}: {{area_name}} ({{position}}/{{total}}). {ui[2]}. ☑ 🚫 · ☐ ✓. CO₂, AQI, PM2.5, PM10, VOC, RH.",
            "outdoor": f"{ui[3]}. AQI, CO₂, PM2.5, PM10, VOC.",
            "weather": f"{ui[4]}. weather.*",
            "delivery": f"{ui[5]}. {ui[15]} · {ui[16]}. Announcement Hub.",
            "thresholds": f"{ui[6]}. AQI (US: 0–500), CO₂, PM2.5, PM10, VOC, RH.",
        }
        for scope in ("config", "options"):
            for step in STEPS:
                item = obj[scope]["step"][step]
                item["title"] = titles[step]
                item["description"] = descriptions[step]
                if step == "thresholds":
                    item["data"] = threshold_labels.copy()
                else:
                    item["data"] = labels[step].copy()
                    item["data_description"] = {
                        field: (
                            f"{ui[1]} · ☑ 🚫 · ☐ ✓" if step == "window_sensors" else
                            f"{ui[2]} · ☑ 🚫 · ☐ ✓" if step == "indoor_sensors" else
                            descriptions[step]
                        )
                        for field in labels[step]
                    }
                    if step == "delivery":
                        item["data_description"]["announcement_repeat_minutes"] = (
                            "Default: 10 minutes. 0 = never repeat. Repeat only if the "
                            "same window action and cause persist; each room is independent."
                        )
                        item["data_description"]["ai_rewrite_announcements"] = (
                            f"AI · {ui[5]} → Announcement Hub use_ai / Home Assistant TTS."
                        )
                        item["data_description"]["ai_conversation_agent"] = (
                            "Home Assistant default · conversation.*"
                        )
                        item["data_description"]["use_announcement_hub"] = (
                            "Available only with configured Announcement Hub. "
                            "Unavailable Hub → Home Assistant fallback."
                        )
            # Keep English fallback for complex error messages rather than
            # accidentally changing their precise safety meaning.
        for scope in ("config", "options"):
            obj[scope]["error"]["invalid_repeat_minutes"] = (
                "Enter a whole number from 0 to 1440 minutes; 0 disables reminders."
            )
        obj["options"]["step"]["init"]["title"] = ui[6]
        obj["options"]["step"]["init"]["description"] = " · ".join(ui[:7])
        obj["options"]["step"]["init"]["menu_options"] = titles.copy()
        obj["entity"]["sensor"]["recommendation"]["name"] = ui[7]
        obj["entity"]["sensor"]["recommendation"]["state"] = {
            "open": f"{ui[14]} · {ui[12]}",
            "close": f"{ui[15]} · {ui[12]}",
            "idle": ui[8],
            "blocked": card[1],
        }
        service = obj["services"]["announce"]
        service["name"] = f"{ui[5]} — Home Environment Manager"
        service["description"] = f"{ui[5]} · {ui[0]}"
        for key, value in (
            ("language", ui[17]), ("channels", ui[5]), ("areas", ui[0])
        ):
            service["fields"][key] = {"name": value, "description": value}
        target = root / "translations" / f"{locale}.json"
        target.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    generate_extended()
