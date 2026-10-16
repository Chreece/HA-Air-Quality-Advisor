"""Constants and cautious defaults for the Air Quality Advisor integration."""

DOMAIN = "air_quality_advisor"
NAME = "Air Quality Advisor"
PLATFORMS = ["sensor"]

CONF_AREAS = "areas"
CONF_EXCLUDED_WINDOWS = "excluded_window_entities"
CONF_EXCLUDED_INDOOR = "excluded_indoor_entities"  # Map Home Assistant area_id -> entity_id list.
CONF_OUTDOOR = "outdoor_sensors"
CONF_WEATHER = "weather_entities"
CONF_WARNINGS = "weather_warnings"
CONF_HUB = "use_announcement_hub"
CONF_AUTO_TTS = "automatic_tts"
CONF_AUTO_NOTIFY = "automatic_notifications"
CONF_NOTIFY_TARGETS = "notify_entities"
CONF_TTS_ENGINE = "tts_engine"
CONF_MEDIA_PLAYERS = "media_players"
CONF_LANGUAGE = "language"
CONF_THRESHOLDS = "thresholds"

from .languages import SUPPORTED_LANGUAGE_TAGS

LANGUAGES = ("auto", *SUPPORTED_LANGUAGE_TAGS)
SUPPORTED_AIR_METRICS = ("aqi", "co2", "pm25", "pm10", "voc", "voc_parts")
INDOOR_METRICS = (*SUPPORTED_AIR_METRICS, "humidity")
WEATHER_CLEAR = frozenset(("sunny", "clear-night", "partlycloudy", "cloudy"))

DEFAULT_THRESHOLDS = {
    "outdoor_aqi": 50.0,  # Assumes US AQI (0–500), see README.
    "outdoor_co2": 800.0,
    "outdoor_pm25": 15.0,     # µg/m³; instantaneous guidance, not daily exposure.
    "outdoor_pm10": 45.0,
    "outdoor_voc": 500.0,     # µg/m³.
    "outdoor_voc_parts": 500.0,  # ppb.
    "indoor_aqi": 100.0,
    "indoor_co2": 1000.0,     # ppm.
    "indoor_pm25": 25.0,
    "indoor_pm10": 45.0,
    "indoor_voc": 500.0,
    "indoor_voc_parts": 500.0,
    "indoor_humidity": 65.0,  # % relative humidity.
    "min_outdoor_temp": 5.0,  # °C.
    "max_outdoor_temp": 32.0,
    "max_outdoor_humidity": 85.0,  # %.
    "max_wind_kmh": 35.0,
    "max_age_minutes": 90.0,
}

UNIT_LABEL = {
    "aqi": "AQI",
    "co2": "ppm",
    "pm25": "µg/m³",
    "pm10": "µg/m³",
    "voc": "µg/m³",
    "voc_parts": "ppb",
    "humidity": "%",
}

SIGNAL_UPDATED = f"{DOMAIN}_updated"
ANNOUNCE_OPEN_STABLE_SECONDS = 90
ANNOUNCE_COOLDOWN_SECONDS = 900
