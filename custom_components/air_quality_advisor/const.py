"""Constants and cautious defaults for the Air Quality Advisor integration."""

DOMAIN = "air_quality_advisor"
NAME = "Home Environment Manager"
PLATFORMS = ["sensor", "number", "switch", "select", "button"]

CONF_AREAS = "areas"
CONF_EXCLUDED_WINDOWS = "excluded_window_entities"
CONF_EXCLUDED_INDOOR = "excluded_indoor_entities"
CONF_USE_MOLD = "use_mold_indicator"
CONF_MOLD_ROOMS = "mold_rooms"
CONF_MOLD_ROOM_SENSOR = "mold_indoor_temperature"
CONF_MOLD_CRITICAL_TEMP = "mold_critical_temperature_c"
CONF_MOLD_RECALIBRATE = "mold_recalibrate"  # Map Home Assistant area_id -> entity_id list.
CONF_OUTDOOR = "outdoor_sensors"
CONF_WEATHER = "weather_entities"
CONF_WARNINGS = "weather_warnings"
CONF_HUB = "use_announcement_hub"
CONF_AUTO_TTS = "automatic_tts"
CONF_AUTO_NOTIFY = "automatic_notifications"
CONF_REPEAT_MINUTES = "announcement_repeat_minutes"
DEFAULT_REPEAT_MINUTES = 10
MAX_REPEAT_MINUTES = 1440
CONF_NOTIFY_TARGETS = "notify_entities"
CONF_TTS_ENGINE = "tts_engine"
CONF_MEDIA_PLAYERS = "media_players"
CONF_LANGUAGE = "language"
CONF_AI_REWRITE = "ai_rewrite_announcements"
CONF_AI_AGENT = "ai_conversation_agent"
CONF_THRESHOLDS = "thresholds"
CONF_ENVIRONMENT_GLOBAL = "environment_global"
CONF_ENVIRONMENT_ROOMS = "environment_rooms"
CONF_PID_ROOMS = "pid_rooms"
CONF_CLIMATE_ROOMS = "climate_rooms"
CONF_OCCUPANCY_GLOBAL = "occupancy_global"

from .languages import SUPPORTED_LANGUAGE_TAGS

LANGUAGES = ("auto", *SUPPORTED_LANGUAGE_TAGS)
SUPPORTED_AIR_METRICS = ("aqi", "co2", "pm25", "pm10", "voc", "voc_parts", "no2", "o3", "so2")
INDOOR_METRICS = (*SUPPORTED_AIR_METRICS, "humidity")
WEATHER_CLEAR = frozenset(("sunny", "clear-night", "partlycloudy", "cloudy"))

DEFAULT_THRESHOLDS = {
    # These are configurable *operational screen values* on instantaneous data.
    # WHO 2021 PM guidance applies to 24-hour means, available separately in
    # the derived dashboard; 15 / 45 here must NOT be called WHO compliance.
    "outdoor_aqi": 50.0,  # Assumes US AQI (0–500), see README.
    "outdoor_co2": 800.0,
    "outdoor_pm25": 15.0,     # µg/m³; instantaneous guidance, not daily exposure.
    "outdoor_pm10": 45.0,
    "outdoor_voc": 500.0,     # µg/m³.
    "outdoor_voc_parts": 500.0,  # ppb.
    "outdoor_no2": 25.0,  # Optional operational screening, not WHO 24-hour equivalence.
    "outdoor_o3": 100.0,  # EEA hourly fair/moderate screen, user configurable.
    "outdoor_so2": 40.0,  # EEA hourly fair/moderate screen, user configurable.
    "indoor_aqi": 100.0,
    "indoor_co2": 1000.0,     # ppm.
    "indoor_pm25": 25.0,
    "indoor_pm10": 45.0,
    "indoor_voc": 500.0,
    "indoor_voc_parts": 500.0,
    "indoor_humidity": 65.0,
    "indoor_mold": 70.0,  # Critical-surface relative humidity; risk from ~70%.  # % relative humidity.
    "min_outdoor_temp": 5.0,  # °C.
    "max_outdoor_temp": 32.0,
    "max_outdoor_humidity": 85.0,  # %.
    "max_wind_kmh": 35.0,
    "max_age_minutes": 90.0,
}

UNIT_LABEL = {
    "mold": "%",
    "aqi": "AQI",
    "co2": "ppm",
    "pm25": "µg/m³",
    "pm10": "µg/m³",
    "voc": "µg/m³",
    "voc_parts": "ppb",
    "no2": "µg/m³",
    "o3": "µg/m³",
    "so2": "µg/m³",
    "hcho": "µg/m³",
    "humidity": "%",
}

SIGNAL_UPDATED = f"{DOMAIN}_updated"
ANNOUNCE_OPEN_STABLE_SECONDS = 90
ANNOUNCE_COOLDOWN_SECONDS = 900
