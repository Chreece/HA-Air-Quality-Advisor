"""Human-readable recommendations; action language is independent of HA UI."""

from __future__ import annotations

from .logic import Reason, Recommendation
from .languages import EXTRA_LOCALES, resolve_language


TEXT = {
    "en": {
        "open": "Open {windows} in {area}: {reasons}. Outdoor conditions are suitable.",
        "close": "Close {windows} in {area}: {reasons}.",
        "title_open": "Air quality — open windows",
        "title_close": "Air quality — close windows",
        "inside": "{name} is high ({value})",
        "outside": "outdoor {name} is high ({value})",
        "no_outdoor_data": "no outdoor air-quality sensor is available",
        "unavailable_outdoor": "outdoor reading unavailable: {name}",
        "no_weather_data": "no weather entity is available",
        "unavailable_weather": "weather information is unavailable",
        "weather_condition": "weather conditions: {value}",
        "weather_cold": "low outside temperature ({value})",
        "weather_hot": "high outside temperature ({value})",
        "weather_humid": "very humid outside ({value})",
        "weather_wind": "strong wind outside ({value})",
        "active_warning": "active weather warning: {name}",
        "unavailable_warning": "weather warning status unavailable: {name}",
    },
    "de": {
        "open": "Öffne {windows} in {area}: {reasons}. Die Außenbedingungen sind geeignet.",
        "close": "Schließe {windows} in {area}: {reasons}.",
        "title_open": "Luftqualität — Fenster öffnen",
        "title_close": "Luftqualität — Fenster schließen",
        "inside": "{name} ist erhöht ({value})",
        "outside": "{name} draußen ist erhöht ({value})",
        "no_outdoor_data": "kein Außenluftsensor verfügbar",
        "unavailable_outdoor": "Außenmesswert nicht verfügbar: {name}",
        "no_weather_data": "keine Wetterentität verfügbar",
        "unavailable_weather": "Wetterdaten nicht verfügbar",
        "weather_condition": "Wetterbedingungen: {value}",
        "weather_cold": "niedrige Außentemperatur ({value})",
        "weather_hot": "hohe Außentemperatur ({value})",
        "weather_humid": "hohe Luftfeuchte draußen ({value})",
        "weather_wind": "starker Wind draußen ({value})",
        "active_warning": "aktive Wetterwarnung: {name}",
        "unavailable_warning": "Status der Wetterwarnung unbekannt: {name}",
    },
    "el": {
        "open": "Άνοιξε {windows} στο {area}: {reasons}. Οι εξωτερικές συνθήκες είναι κατάλληλες.",
        "close": "Κλείσε {windows} στο {area}: {reasons}.",
        "title_open": "Ποιότητα αέρα — άνοιγμα παραθύρων",
        "title_close": "Ποιότητα αέρα — κλείσιμο παραθύρων",
        "inside": "Αυξημένο {name} ({value})",
        "outside": "Αυξημένο {name} έξω ({value})",
        "no_outdoor_data": "δεν υπάρχει διαθέσιμος αισθητήρας εξωτερικού αέρα",
        "unavailable_outdoor": "μη διαθέσιμη εξωτερική μέτρηση: {name}",
        "no_weather_data": "δεν υπάρχουν διαθέσιμα δεδομένα καιρού",
        "unavailable_weather": "μη διαθέσιμα δεδομένα καιρού",
        "weather_condition": "καιρικές συνθήκες: {value}",
        "weather_cold": "χαμηλή εξωτερική θερμοκρασία ({value})",
        "weather_hot": "υψηλή εξωτερική θερμοκρασία ({value})",
        "weather_humid": "υψηλή εξωτερική υγρασία ({value})",
        "weather_wind": "ισχυρός εξωτερικός άνεμος ({value})",
        "active_warning": "ενεργή προειδοποίηση καιρού: {name}",
        "unavailable_warning": "άγνωστη κατάσταση προειδοποίησης καιρού: {name}",
    },
    "fr": {
        "open": "Ouvrez {windows} dans {area} : {reasons}. Les conditions extérieures conviennent.",
        "close": "Fermez {windows} dans {area} : {reasons}.",
        "title_open": "Qualité de l'air — ouvrir les fenêtres",
        "title_close": "Qualité de l'air — fermer les fenêtres",
        "inside": "{name} intérieur est élevé ({value})",
        "outside": "{name} extérieur est élevé ({value})",
        "no_outdoor_data": "aucune mesure de la qualité de l'air extérieur",
        "unavailable_outdoor": "mesure extérieure indisponible : {name}",
        "no_weather_data": "aucune entité météo disponible",
        "unavailable_weather": "données météo indisponibles",
        "weather_condition": "conditions météo : {value}",
        "weather_cold": "température extérieure basse ({value})",
        "weather_hot": "température extérieure élevée ({value})",
        "weather_humid": "humidité extérieure élevée ({value})",
        "weather_wind": "vent fort ({value})",
        "active_warning": "alerte météo active : {name}",
        "unavailable_warning": "alerte météo indisponible : {name}",
    },
    "es": {
        "open": "Abre {windows} en {area}: {reasons}. Las condiciones exteriores son adecuadas.",
        "close": "Cierra {windows} en {area}: {reasons}.",
        "title_open": "Calidad del aire — abrir ventanas",
        "title_close": "Calidad del aire — cerrar ventanas",
        "inside": "{name} interior elevado ({value})",
        "outside": "{name} exterior elevado ({value})",
        "no_outdoor_data": "no hay sensores de aire exterior disponibles",
        "unavailable_outdoor": "medición exterior no disponible: {name}",
        "no_weather_data": "no hay entidad meteorológica disponible",
        "unavailable_weather": "datos meteorológicos no disponibles",
        "weather_condition": "condiciones meteorológicas: {value}",
        "weather_cold": "baja temperatura exterior ({value})",
        "weather_hot": "alta temperatura exterior ({value})",
        "weather_humid": "humedad exterior alta ({value})",
        "weather_wind": "viento fuerte ({value})",
        "active_warning": "alerta meteorológica activa: {name}",
        "unavailable_warning": "estado de alerta meteorológica desconocido: {name}",
    },
}


def _extra_messages(entry: dict) -> dict[str, str]:
    ui = entry["ui"]
    say = entry["speech"]
    missing = entry["card"][5]
    return {
        "open": say[0],
        "close": say[1],
        "title_open": f"{ui[7]} — {ui[14]} {ui[12]}",
        "title_close": f"{ui[7]} — {ui[15]} {ui[12]}",
        "inside": say[2],
        "outside": say[3],
        "no_outdoor_data": f"{ui[3]} — {missing}",
        "unavailable_outdoor": f"{ui[3]} — {missing}: {{name}}",
        "no_weather_data": f"{ui[4]} — {missing}",
        "unavailable_weather": f"{ui[4]} — {missing}",
        "weather_condition": f"{ui[4]}: {{value}}",
        "weather_cold": f"{ui[18]} — {{value}}",
        "weather_hot": f"{ui[18]} — {{value}}",
        "weather_humid": f"{ui[18]} — {{value}}",
        "weather_wind": f"{ui[4]} — {{value}}",
        "active_warning": f"{ui[4]}: {{name}}",
        "unavailable_warning": f"{ui[4]} — {missing}: {{name}}",
    }


TEXT.update({tag: _extra_messages(locale) for tag, locale in EXTRA_LOCALES.items()})


def language_code(language: str | None) -> str:
    return resolve_language(language)


def explain(reason: Reason, language: str) -> str:
    dictionary = TEXT[language_code(language)]
    template = dictionary.get(reason.code)
    if template is None:
        if reason.code.startswith("inside_"):
            template = dictionary["inside"]
        elif reason.code.startswith("outside_"):
            template = dictionary["outside"]
        else:
            template = reason.code.replace("_", " ")
    return template.format(name=reason.label, value=reason.value)


def announcement(rec: Recommendation, language: str) -> tuple[str, str]:
    t = TEXT[language_code(language)]
    windows = ", ".join(window.name for window in rec.windows)
    # A few causes are sufficient for TTS; all causes remain in sensor attributes.
    reasons = "; ".join(explain(reason, language) for reason in rec.reasons[:3])
    title = t[f"title_{rec.action}"]
    return title, t[rec.action].format(windows=windows, area=rec.area_name, reasons=reasons)
