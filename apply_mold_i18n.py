"""Apply mold indicator option, per-room calibration and localization to all HA flows.

Runs after the reviewed config overrides so existing translated fields stay
intact. Text is maintained in one place; the shipped 38 JSON files are generated
from this function and checked by CI.
"""
from __future__ import annotations

import json
import runpy
from pathlib import Path

from apply_config_i18n import native_languages

ROOT = Path(__file__).resolve().parent / "custom_components" / "air_quality_advisor"
MOLD_NAMES = runpy.run_path(str(ROOT / "mold_text.py"))["MOLD_NAMES"]

FIVE = {
    "en": {
        "enable": "Use mold indication instead of raw room RH",
        "enable_help": "When enabled, humidity recommendations use the estimated relative humidity at each room's coldest surface instead of raw RH. Calibrate each room under the Room settings menu; an uncalibrated room remains unknown rather than safe.",
        "room_title": "Room settings — indoor air and mold",
        "room_desc": "Room: {area_name} ({position}/{total}). Exclude indoor air sensors here. For mold indication, measure the temperature of the coldest surface (for example an exterior corner or window frame) with a thermometer while room and outdoor temperatures are stable. Enter the surface temperature in °C below. Leave it empty to calibrate later.",
        "sensor": "Room temperature sensor for mold calibration",
        "sensor_help": "Choose the ambient room temperature sensor (°C/°F). Only supported temperature sensors assigned to this room are offered. The reading is captured together with the outdoor weather temperature when you save a new calibration.",
        "critical": "Measured coldest surface temperature (°C)",
        "critical_help": "Measure the coldest wall/corner/window-frame surface now, simultaneously with room and outdoor temperature. A difference of at least 3°C between indoors and outdoors is needed. This measurement sets a persistent calibration factor; it is not treated as a fixed surface temperature. Clear to disable mold estimation for this room. See the Home Assistant Mold Indicator documentation.",
        "recal": "Recalibrate with current room and outdoor readings",
        "recal_help": "Check only after measuring the coldest surface again now. Otherwise changing sensor exclusions must not silently overwrite the original calibration.",
        "threshold": "Mold indication triggering ventilation (estimated surface RH, %)",
        "errors": {
            "invalid_mold_temperature_sensor": "Choose a valid temperature sensor assigned to this room.",
            "missing_mold_indoor_temperature": "The room temperature sensor has no valid recent Celsius/Fahrenheit reading. Try again when it is available.",
            "missing_mold_outdoor_temperature": "No selected weather entity supplies a valid recent outdoor temperature. Configure weather first or wait for a valid measurement.",
            "invalid_mold_surface_temperature": "Enter a finite measured surface temperature in °C.",
            "invalid_mold_calibration": "Calibration needs room, outdoor and cold-surface temperatures measured together, with at least 3°C difference between room and outside. Check the three readings."
        }
    },
    "de": {
        "enable": "Schimmelindikator statt relativer Raumluftfeuchte verwenden",
        "enable_help": "Die Lüftungsempfehlung berücksichtigt die geschätzte relative Feuchte an der kältesten Oberfläche statt der normalen Raumluftfeuchte. Pro Raum kalibrieren; ohne Kalibrierung wird der Wert als unbekannt angezeigt.",
        "room_title": "Raumeinstellungen – Innenluft und Schimmel",
        "room_desc": "Raum: {area_name} ({position}/{total}). Hier Luftsensoren ausschließen. Für die Schimmelanzeige die kälteste Oberfläche (z. B. Außenwandecke oder Fensterrahmen) jetzt mit einem Thermometer messen, während Raum- und Außentemperatur stabil sind. Temperatur unten in °C eingeben; leer lassen, um später zu kalibrieren.",
        "sensor": "Raumtemperatursensor für die Schimmelkalibrierung",
        "sensor_help": "Temperatursensor (°C/°F) aus diesem Raum wählen. Beim Kalibrieren werden aktuelle Raum- und Außentemperatur gleichzeitig übernommen.",
        "critical": "Gemessene Temperatur der kältesten Oberfläche (°C)",
        "critical_help": "Kälteste Ecke bzw. Fensterrahmen jetzt messen; Innen- und Außentemperatur müssen gleichzeitig gemessen werden. Mindestens 3°C Unterschied zwischen innen und außen. Daraus wird ein dauerhafter Kalibrierfaktor berechnet, keine feste Oberflächentemperatur. Leeren, um die Kalibrierung zu entfernen.",
        "recal": "Mit aktuellen Temperaturwerten neu kalibrieren",
        "recal_help": "Nur aktivieren, wenn die kälteste Oberfläche erneut gemessen wurde. Änderungen an Sensorausschlüssen dürfen die alte Kalibrierung nicht überschreiben.",
        "threshold": "Schimmelindikator für Lüften (geschätzte Oberflächenfeuchte, %)",
        "errors": {
            "invalid_mold_temperature_sensor": "Wähle einen gültigen Temperatursensor dieses Raums.",
            "missing_mold_indoor_temperature": "Der Raumtemperatursensor liefert keinen gültigen aktuellen Messwert.",
            "missing_mold_outdoor_temperature": "Keine gewählte Wetterentität liefert eine aktuelle Außentemperatur.",
            "invalid_mold_surface_temperature": "Gib eine gültige gemessene Oberflächentemperatur in °C ein.",
            "invalid_mold_calibration": "Raum-, Außen- und Oberflächentemperatur müssen gleichzeitig gemessen werden; innen und außen mindestens 3°C Temperaturunterschied."
        }
    },
    "el": {
        "enable": "Χρήση ένδειξης μούχλας αντί της σχετικής υγρασίας",
        "enable_help": "Οι συστάσεις αερισμού βασίζονται στην εκτιμώμενη υγρασία της πιο κρύας επιφάνειας και όχι μόνο στο RH του δωματίου. Κάθε χώρος χρειάζεται βαθμονόμηση· αλλιώς η ένδειξη παραμένει άγνωστη.",
        "room_title": "Ρυθμίσεις δωματίων — αέρας και μούχλα",
        "room_desc": "Χώρος: {area_name} ({position}/{total}). Επίλεξε αισθητήρες προς εξαίρεση. Για την ένδειξη μούχλας, μέτρησε με θερμόμετρο την πιο κρύα επιφάνεια (γωνία εξωτερικού τοίχου ή πλαίσιο παραθύρου), ενώ οι θερμοκρασίες μέσα και έξω είναι σταθερές. Καταχώρισε °C ή άφησε κενό για αργότερα.",
        "sensor": "Αισθητήρας θερμοκρασίας χώρου για βαθμονόμηση",
        "sensor_help": "Επίλεξε αισθητήρα θερμοκρασίας του δωματίου (°C/°F). Κατά τη νέα βαθμονόμηση καταγράφονται ταυτόχρονα η εσωτερική και η εξωτερική θερμοκρασία.",
        "critical": "Μετρημένη θερμοκρασία πιο κρύας επιφάνειας (°C)",
        "critical_help": "Μέτρησε τώρα την πιο κρύα γωνία ή το πλαίσιο παραθύρου μαζί με την εσωτερική και εξωτερική θερμοκρασία. Χρειάζεται διαφορά τουλάχιστον 3°C μέσα–έξω. Η μέτρηση δημιουργεί συντελεστή βαθμονόμησης, όχι σταθερή θερμοκρασία επιφάνειας. Κενό για κατάργηση.",
        "recal": "Επαναβαθμονόμηση με τις τρέχουσες θερμοκρασίες",
        "recal_help": "Ενεργοποίησέ το μόνο αν μέτρησες ξανά την πιο κρύα επιφάνεια. Η αλλαγή εξαιρέσεων αισθητήρων δεν πρέπει να αλλάζει την παλιά βαθμονόμηση.",
        "threshold": "Όριο ένδειξης μούχλας για αερισμό (εκτιμώμενη υγρασία επιφάνειας, %)",
        "errors": {
            "invalid_mold_temperature_sensor": "Επίλεξε έγκυρο αισθητήρα θερμοκρασίας αυτού του δωματίου.",
            "missing_mold_indoor_temperature": "Ο αισθητήρας θερμοκρασίας δωματίου δεν δίνει πρόσφατη έγκυρη μέτρηση.",
            "missing_mold_outdoor_temperature": "Καμία επιλεγμένη οντότητα καιρού δεν δίνει πρόσφατη εξωτερική θερμοκρασία.",
            "invalid_mold_surface_temperature": "Καταχώρισε έγκυρη μετρημένη θερμοκρασία επιφάνειας σε °C.",
            "invalid_mold_calibration": "Μέτρησε ταυτόχρονα θερμοκρασία χώρου, έξω και κρύας επιφάνειας, με διαφορά τουλάχιστον 3°C μέσα–έξω."
        }
    },
    "fr": {
        "enable": "Utiliser l’indicateur de moisissure au lieu de l’humidité relative",
        "enable_help": "Les conseils d’aération reposent sur l’humidité estimée près de la surface la plus froide plutôt que sur l’humidité ambiante. Calibrez chaque pièce ; sinon l’indicateur reste indisponible.",
        "room_title": "Paramètres des pièces — air et moisissure",
        "room_desc": "Pièce : {area_name} ({position}/{total}). Excluez les capteurs de cette pièce. Pour l’indicateur de moisissure, mesurez maintenant la température du point le plus froid (coin de mur extérieur ou cadre de fenêtre), quand les températures intérieure et extérieure sont stables. Saisissez °C ou laissez vide pour plus tard.",
        "sensor": "Sonde de température intérieure pour l’étalonnage",
        "sensor_help": "Choisissez une sonde de température de cette pièce (°C/°F). Les températures intérieure et extérieure sont relevées au moment de la calibration.",
        "critical": "Température mesurée de la surface la plus froide (°C)",
        "critical_help": "Mesurez simultanément la surface la plus froide, l’intérieur et l’extérieur, avec au moins 3°C de différence. Cette mesure définit un facteur d’étalonnage durable, pas une température de surface fixe. Effacez pour supprimer l’étalonnage.",
        "recal": "Recalibrer avec les températures actuelles",
        "recal_help": "Cochez uniquement après une nouvelle mesure du point froid. Modifier les capteurs exclus ne doit pas recalibrer automatiquement.",
        "threshold": "Seuil de moisissure pour aérer (humidité de surface estimée, %)",
        "errors": {
            "invalid_mold_temperature_sensor": "Choisissez une sonde de température valide de cette pièce.",
            "missing_mold_indoor_temperature": "La sonde intérieure ne fournit aucune température récente et valide.",
            "missing_mold_outdoor_temperature": "Aucune entité météo sélectionnée ne fournit de température extérieure récente.",
            "invalid_mold_surface_temperature": "Saisissez une température de surface mesurée valide en °C.",
            "invalid_mold_calibration": "Mesurez simultanément les températures intérieure, extérieure et de surface, avec au moins 3°C d’écart intérieur/extérieur."
        }
    },
    "es": {
        "enable": "Usar indicador de moho en lugar de humedad relativa",
        "enable_help": "Las recomendaciones se basan en la humedad estimada de la superficie más fría, no en la humedad relativa ambiental. Calibra cada habitación; sin calibración la lectura es desconocida.",
        "room_title": "Configuración por habitación — aire y moho",
        "room_desc": "Habitación: {area_name} ({position}/{total}). Excluye aquí sensores del aire. Para el indicador de moho, mide ahora la superficie más fría (esquina exterior o marco de ventana) con un termómetro, con las temperaturas interior y exterior estables. Introduce los °C o deja vacío para calibrar después.",
        "sensor": "Sensor de temperatura interior para calibración",
        "sensor_help": "Elige un sensor de temperatura de esta habitación (°C/°F). La temperatura interior y exterior se capturan al guardar una calibración nueva.",
        "critical": "Temperatura medida de la superficie más fría (°C)",
        "critical_help": "Mide a la vez la superficie más fría y las temperaturas interior y exterior. Debe haber al menos 3°C de diferencia interior-exterior. Se calcula un factor de calibración persistente, no una temperatura de superficie fija. Borra el valor para eliminar la calibración.",
        "recal": "Recalibrar con las temperaturas actuales",
        "recal_help": "Actívalo solo después de medir de nuevo la superficie más fría. Cambiar sensores excluidos no altera la calibración anterior.",
        "threshold": "Umbral de moho para ventilar (humedad superficial estimada, %)",
        "errors": {
            "invalid_mold_temperature_sensor": "Selecciona un sensor de temperatura válido de esta habitación.",
            "missing_mold_indoor_temperature": "El sensor interior no tiene una medida reciente válida.",
            "missing_mold_outdoor_temperature": "Ninguna entidad meteorológica elegida dispone de temperatura exterior reciente.",
            "invalid_mold_surface_temperature": "Introduce una temperatura superficial medida válida en °C.",
            "invalid_mold_calibration": "Mide simultáneamente interior, exterior y superficie fría, con al menos 3°C de diferencia entre dentro y fuera."
        }
    }
}
ERRORS = ["invalid_mold_temperature_sensor","missing_mold_indoor_temperature","missing_mold_outdoor_temperature","invalid_mold_surface_temperature","invalid_mold_calibration"]


def translated_fields(code: str, doc: dict) -> dict:
    if code in FIVE:
        return FIVE[code]
    room_label = doc["options"]["step"]["init"]["menu_options"]["areas"]
    mold = MOLD_NAMES[code]
    return {
        "enable": f"{mold} · RH (%) → 70%",
        "enable_help": f"🧱 {mold} · RH (%) → ≈70% · 🌡️ 🧊",
        "room_title": f"{room_label} · {mold}",
        "room_desc": (
            f"{room_label}: {{area_name}} ({{position}}/{{total}}). "
            f"🌡️ 🧊 {mold} · °C · ΔT ≥ 3°C. ☑ 🚫 · ☐ ✓"
        ),
        "sensor": f"{room_label} · 🌡️ (°C/°F)",
        "sensor_help": f"{room_label}: 🌡️ °C/°F · {mold}.",
        "critical": f"{mold} · 🧊 °C",
        "critical_help": (
            f"🧊 {mold} · 🌡️ °C · ΔT ≥ 3°C. "
            f"🧊 ↔ 🌡️ · ↻"
        ),
        "recal": f"{mold} · ↻ 🌡️",
        "recal_help": f"↻ {mold} · 🌡️ °C",
        "threshold": f"{mold} · ≥ 70%",
        "errors": {
            ERRORS[0]: f"{room_label} · 🌡️ ⚠",
            ERRORS[1]: f"{room_label} · 🌡️ ∅",
            ERRORS[2]: f"{mold} · 🌤️ 🌡️ ∅",
            ERRORS[3]: f"{mold} · 🧊 °C ⚠",
            ERRORS[4]: f"{mold} · ΔT ≥ 3°C ⚠",
        },
    }


MOLD_WEATHER_HELP = {
    "en": "Mold indication uses the current temperature attribute (°C/°F) of a selected weather entity for outdoor temperature. Choose a source that reports temperature.",
    "de": "Der Schimmelindikator nutzt das aktuelle Attribut temperature (°C/°F) einer ausgewählten Wetterentität als Außentemperatur. Wähle einen Anbieter mit Temperaturwerten.",
    "el": "Η ένδειξη μούχλας χρησιμοποιεί το τρέχον γνώρισμα temperature (°C/°F) μιας επιλεγμένης οντότητας καιρού ως εξωτερική θερμοκρασία. Επίλεξε πηγή που δίνει θερμοκρασία.",
    "fr": "L'indicateur de moisissure utilise l'attribut temperature (°C/°F) d'une entité météo sélectionnée comme température extérieure. Sélectionnez une source qui fournit une température.",
    "es": "El indicador de moho obtiene la temperatura exterior del atributo temperature (°C/°F) de una entidad meteorológica seleccionada. Elige una fuente que proporcione la temperatura.",
}


def apply_mold_i18n(root: Path = ROOT) -> None:
    if set(MOLD_NAMES) != set(native_languages()):
        raise ValueError("Missing mold locale names")
    for code in MOLD_NAMES:
        target = root / "translations" / f"{code}.json"
        doc = json.loads(target.read_text(encoding="utf-8"))
        translations = translated_fields(code, doc)
        for scope in ("config", "options"):
            areas = doc[scope]["step"]["areas"]
            room = doc[scope]["step"]["indoor_sensors"]
            areas["data"]["use_mold_indicator"] = translations["enable"]
            areas["data_description"]["use_mold_indicator"] = translations["enable_help"]
            room["title"] = translations["room_title"]
            room["description"] = translations["room_desc"] + "\\n\\n{mold_room_notice}"
            weather = doc[scope]["step"]["weather"]
            weather["description"] += "\\n\\n{mold_weather_notice}"
            weather["data_description"]["weather_entities"] += (
                " " + MOLD_WEATHER_HELP.get(
                    code,
                    "🌡️ weather.* · temperature (°C/°F) → 🧊",
                )
            )
            for key, value in (
                ("mold_indoor_temperature", translations["sensor"]),
                ("mold_critical_temperature_c", translations["critical"]),
                ("mold_recalibrate", translations["recal"]),
            ):
                room["data"][key] = value
            for key, value in (
                ("mold_indoor_temperature", translations["sensor_help"]),
                ("mold_critical_temperature_c", translations["critical_help"]),
                ("mold_recalibrate", translations["recal_help"]),
            ):
                room["data_description"][key] = value
            doc[scope]["step"]["thresholds"]["data"]["indoor_mold"] = (
                translations["threshold"]
            )
            doc[scope]["error"].update(translations["errors"])

        menu = doc["options"]["step"]["init"]["menu_options"]
        menu["indoor_sensors"] = translations["room_title"]
        doc["options"]["step"]["init"]["menu_options"] = {
            sid: menu[sid]
            for sid in ("areas", "weather", "indoor_sensors",
                        "window_sensors", "outdoor", "delivery", "thresholds")
        }
        content = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
        target.write_text(content, encoding="utf-8")
        if code == "en":
            (root / "strings.json").write_text(content, encoding="utf-8")


if __name__ == "__main__":
    apply_mold_i18n()
