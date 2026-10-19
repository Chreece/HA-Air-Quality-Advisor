"""Compact multi-page UI: rooms, outdoors, weather/warnings, announcements."""

from __future__ import annotations

from typing import Any
import math

import probatio

from homeassistant import config_entries
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.config_entries import ConfigFlowResult, OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers import selector

from .languages import SUPPORTED_LANGUAGE_TAGS, resolve_language

from .ai_rewrite import DEFAULT_AGENT, conversation_agent_choices
from .hub_delivery import hub_installed
from .const import (
    CONF_AREAS, CONF_EXCLUDED_WINDOWS, CONF_EXCLUDED_INDOOR, CONF_AUTO_NOTIFY, CONF_AUTO_TTS, CONF_HUB,
    CONF_LANGUAGE, CONF_MEDIA_PLAYERS, CONF_NOTIFY_TARGETS, CONF_OUTDOOR,
    CONF_REPEAT_MINUTES, DEFAULT_REPEAT_MINUTES, MAX_REPEAT_MINUTES,
    CONF_AI_REWRITE, CONF_AI_AGENT,
    CONF_THRESHOLDS, CONF_TTS_ENGINE, CONF_WARNINGS, CONF_WEATHER,
    DEFAULT_THRESHOLDS, DOMAIN, CONF_USE_MOLD, CONF_MOLD_ROOMS,
    CONF_MOLD_ROOM_SENSOR, CONF_MOLD_CRITICAL_TEMP, CONF_MOLD_RECALIBRATE,
    CONF_ENVIRONMENT_GLOBAL, CONF_ENVIRONMENT_ROOMS,
)
from .mold import calibration_factor, estimate_mold_for_room

from .discovery import (
    indoor_sensor_exclusion_choices, outdoor_choices, suggested_window_exclusions, warning_choices,
    window_area_choices, window_exclusion_choices,
    indoor_temperature_choices, temperature_sensor_c, weather as current_weather,
    rooms as discover_rooms,
)


def _marker(name: str, default: Any = None, *, required: bool = False) -> probatio.Marker:
    factory = probatio.Required if required else probatio.Optional
    return factory(name, default=default) if default is not None else factory(name)


def _multi(options: list[dict[str, str]]) -> selector.SelectSelector:
    return selector.SelectSelector(selector.SelectSelectorConfig(
        options=options, multiple=True, custom_value=False,
        mode=selector.SelectSelectorMode.DROPDOWN,
    ))


def _tts_player_options(hass: Any) -> list[dict[str, str]]:
    """Only media players actually advertising playback are selectable."""
    result = []
    for state in hass.states.async_all("media_player"):
        features = int(state.attributes.get("supported_features", 0) or 0)
        if features & int(MediaPlayerEntityFeature.PLAY_MEDIA):
            result.append({"value": state.entity_id, "label": state.name or state.entity_id})
    return sorted(result, key=lambda item: item["label"].casefold())


ENV_AQI_SCALES = [
    {"value": "not_configured", "label": "Unknown — disable comparison until identified"},
    {"value": "us_epa", "label": "United States EPA AQI (0–500)"},
    {"value": "eea_category", "label": "European Air Quality Index category (1–6)"},
    {"value": "custom", "label": "Other international/provider scale (choose limit)"},
]


def _optional_sensor() -> selector.EntitySelector:
    return selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))


def _entity_any() -> selector.EntitySelector:
    return selector.EntitySelector(selector.EntitySelectorConfig())


def _real_number(low: float, high: float, unit: str | None = None) -> selector.NumberSelector:
    return selector.NumberSelector(selector.NumberSelectorConfig(
        min=low, max=high, step=0.1, unit_of_measurement=unit,
        mode=selector.NumberSelectorMode.BOX,
    ))


class _FlowMixin:
    """Use the same pages in initial setup and reconfiguration."""

    _values: dict[str, Any]

    def _mold_source_age(self) -> float:
        """Use the normal configured freshness threshold for calibration previews."""
        thresholds = self._values.get(CONF_THRESHOLDS, {})
        if not isinstance(thresholds, dict):
            thresholds = {}
        return {**DEFAULT_THRESHOLDS, **thresholds}["max_age_minutes"]

    def _mold_weather_notice(self, entity_ids: list[str]) -> str:
        """Non-blocking, live weather-temperature source status in the UI."""
        if not self._values.get(CONF_USE_MOLD, False):
            return ""
        sources = [
            current_weather(self.hass, entity, self._mold_source_age())
            for entity in entity_ids
        ]
        valid = [
            item for item in sources
            if item.temperature_c is not None
            and math.isfinite(item.temperature_c)
            and -60 <= item.temperature_c <= 85
        ]
        if valid:
            return "✓ 🌡️ " + " · ".join(
                f"{item.entity_id}: {item.temperature_c:.1f} °C"
                for item in valid
            )
        return "⚠️ 🌤️ 🌡️ °C ∅ : " + (
            ", ".join(entity_ids) if entity_ids else "weather.*"
        )

    def _mold_room_notice(
        self, area_id: str, calibration: dict[str, Any],
        excluded: list[str],
    ) -> str:
        """Show every missing mold input without preventing later calibration."""
        if not self._values.get(CONF_USE_MOLD, False):
            return ""
        room = discover_rooms(
            self.hass, [area_id], self._mold_source_age(),
            excluded_entities=set(excluded) |
                set(self._values.get(CONF_EXCLUDED_WINDOWS, [])),
        )[0]
        indoor_sensor = calibration.get("indoor_temperature_entity")
        indoor_c = (
            temperature_sensor_c(self.hass, indoor_sensor, self._mold_source_age())
            if isinstance(indoor_sensor, str) else None
        )
        current = tuple(
            current_weather(self.hass, entity, self._mold_source_age())
            for entity in self._values.get(CONF_WEATHER, [])
        )
        estimate = estimate_mold_for_room(room, indoor_c, current, calibration)
        missing = (estimate.details or {}).get("missing_inputs", [])
        names = {
            "calibration": "🧊 °C",
            "indoor_temperature": "🏠 🌡️ °C",
            "outdoor_temperature": "🌤️ 🌡️ °C",
            "humidity": "RH (%)",
            "calculation": "∑ RH (%)",
        }
        if not missing:
            return "✓ 🌡️ °C · RH (%)"
        return "⚠️ " + " · ".join(names.get(code, code) for code in missing)

    async def _advance(self, next_step: str) -> ConfigFlowResult:
        """Finish a selected options section; initial setup continues normally."""
        if getattr(self, "_menu_mode", False):
            return await self._finish()
        return await getattr(self, f"async_step_{next_step}")()

    async def async_step_window_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Review likely virtual window signals after selecting rooms.

        An explicit empty saved exclusion list must override all heuristics.
        Initial setup reviews the area choice again only if exclusions remove
        the last usable window contact from a selected room.
        """
        existing = self._values.get(CONF_EXCLUDED_WINDOWS)
        choices = window_exclusion_choices(self.hass, existing)
        allowed = {item["value"] for item in choices}
        if existing is None:
            defaults = [choice["value"] for choice in choices
                        if choice["value"] in suggested_window_exclusions(self.hass)]
        else:
            defaults = list(existing)
        errors: dict[str, str] = {}
        if user_input is not None:
            selected = list(dict.fromkeys(user_input.get(CONF_EXCLUDED_WINDOWS, [])))
            if any(entity_id not in allowed for entity_id in selected):
                errors["base"] = "invalid_window_exclusions"
            else:
                # Rooms are the *first* initial-setup step. Exclusions are
                # chosen afterwards, so make sure selected rooms still have
                # usable contacts before continuing to indoor air sensors.
                if not getattr(self, "_menu_mode", False):
                    selected_areas = self._values.get(CONF_AREAS, [])
                    eligible_areas = {
                        item["value"] for item in window_area_choices(
                            self.hass, excluded_entities=set(selected)
                        )
                    }
                    if selected_areas and not eligible_areas:
                        errors["base"] = "no_windows_after_exclusions"
                    elif any(area not in eligible_areas for area in selected_areas):
                        self._values[CONF_EXCLUDED_WINDOWS] = selected
                        self._review_areas_after_exclusions = True
                        return await self.async_step_areas()
                if not errors:
                    self._values[CONF_EXCLUDED_WINDOWS] = selected
                    return await self._advance("outdoor" if self._values.get(CONF_USE_MOLD) else "indoor_sensors")
        elif not choices:
            if not getattr(self, "_menu_mode", False) and self._values.get(CONF_AREAS):
                # Contacts vanished between the Rooms and Exclusions pages.
                # Do not silently continue with unusable selected rooms.
                errors["base"] = "no_windows_after_exclusions"
            else:
                self._values.setdefault(CONF_EXCLUDED_WINDOWS, [])
                return await self._advance("outdoor" if self._values.get(CONF_USE_MOLD) else "indoor_sensors")
        return self.async_show_form(
            step_id="window_sensors",
            data_schema=probatio.Schema({
                _marker(
                    CONF_EXCLUDED_WINDOWS,
                    user_input.get(CONF_EXCLUDED_WINDOWS, []) if user_input is not None else defaults,
                ): _multi(choices),
            }),
            errors=errors,
        )

    async def async_step_areas(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        # On first setup suggest *and preselect* every area with a window
        # contact. Reconfiguration must honour the user's stored choices,
        # otherwise previously deselected rooms would be reintroduced.
        editing = getattr(self, "_editing", False)
        reviewing = getattr(self, "_review_areas_after_exclusions", False)
        previous = self._values.get(CONF_AREAS, []) if editing else []
        choices = window_area_choices(
            self.hass, previous, set(self._values.get(CONF_EXCLUDED_WINDOWS, []))
        )
        known = {choice["value"] for choice in choices}
        if reviewing:
            # Keep the user's initial selections, excluding only rooms which
            # lost their last window contact after explicit exclusions.
            default_areas = [area for area in self._values.get(CONF_AREAS, []) if area in known]
        else:
            default_areas = list(previous) if editing else [choice["value"] for choice in choices]
        errors: dict[str, str] = {}
        if user_input is not None:
            selected = list(dict.fromkeys(user_input.get(CONF_AREAS, [])))
            if not selected:
                errors["base"] = "no_areas"
            elif any(area not in known for area in selected):
                errors["base"] = "invalid_areas"
            else:
                self._values[CONF_AREAS] = selected
                self._values[CONF_USE_MOLD] = bool(
                    user_input.get(CONF_USE_MOLD, self._values.get(CONF_USE_MOLD, False))
                )
                self._indoor_index = 0
                if reviewing:
                    self._review_areas_after_exclusions = False
                    return await self._advance("outdoor" if self._values.get(CONF_USE_MOLD) else "indoor_sensors")
                return await self._advance("window_sensors")
        elif not choices:
            errors["base"] = "no_window_areas"
        elif reviewing:
            errors["base"] = "review_areas_after_exclusions"
        return self.async_show_form(step_id="areas", data_schema=probatio.Schema({
            _marker(CONF_AREAS, user_input.get(CONF_AREAS, []) if user_input is not None
                    else default_areas, required=True): _multi(choices),
            _marker(CONF_USE_MOLD, (
                user_input.get(CONF_USE_MOLD, self._values.get(CONF_USE_MOLD, False))
                if user_input is not None else self._values.get(CONF_USE_MOLD, False)
            )): selector.BooleanSelector(),
        }), errors=errors)

    async def async_step_indoor_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Room settings: per-room air exclusions and optional mold calibration."""
        area_ids = list(self._values.get(CONF_AREAS, []))
        previous = self._values.get(CONF_EXCLUDED_INDOOR, {})
        if not isinstance(previous, dict):
            previous = {}
        mold_on = bool(self._values.get(CONF_USE_MOLD, False))
        saved_rooms = self._values.get(CONF_MOLD_ROOMS, {})
        if not isinstance(saved_rooms, dict):
            saved_rooms = {}
        index = getattr(self, "_indoor_index", 0)
        while index < len(area_ids):
            area_id = area_ids[index]
            choices = indoor_sensor_exclusion_choices(
                self.hass, area_id, previous.get(area_id, [])
            )
            if choices or mold_on:
                break
            index += 1
        self._indoor_index = index
        if index >= len(area_ids):
            return await self._advance("delivery" if mold_on else "outdoor")

        known = {choice["value"] for choice in choices}
        current = saved_rooms.get(area_id, {})
        if not isinstance(current, dict):
            current = {}
        room_sensors = (
            indoor_temperature_choices(
                self.hass, area_id, current.get("indoor_temperature_entity"),
            ) if mold_on else []
        )
        sensor_ids = {item["value"] for item in room_sensors}
        errors: dict[str, str] = {}

        if user_input is not None:
            selected = list(dict.fromkeys(user_input.get(CONF_EXCLUDED_INDOOR, [])))
            if any(entity_id not in known for entity_id in selected):
                errors["base"] = "invalid_indoor_exclusions"

            updated_calibration: dict[str, Any] | None = None
            if mold_on and not errors:
                indoor_entity = user_input.get(
                    CONF_MOLD_ROOM_SENSOR, current.get("indoor_temperature_entity"),
                )
                raw_surface = user_input.get(
                    CONF_MOLD_CRITICAL_TEMP, current.get("critical_temperature_c"),
                )
                if raw_surface is None or raw_surface == "":
                    updated_calibration = {}
                elif indoor_entity not in sensor_ids:
                    errors["base"] = "invalid_mold_temperature_sensor"
                else:
                    try:
                        surface = float(raw_surface)
                    except (TypeError, ValueError, OverflowError):
                        surface = float("nan")
                    if not math.isfinite(surface) or not -60 <= surface <= 85:
                        errors["base"] = "invalid_mold_surface_temperature"
                    elif (
                        current.get("indoor_temperature_entity") == indoor_entity
                        and current.get("critical_temperature_c") == surface
                        and current.get("calibration_factor") is not None
                        and not user_input.get(CONF_MOLD_RECALIBRATE, False)
                    ):
                        # Editing exclusions must never re-calibrate an old
                        # measurement under different weather conditions.
                        updated_calibration = dict(current)
                    else:
                        max_age = {
                            **DEFAULT_THRESHOLDS,
                            **self._values.get(CONF_THRESHOLDS, {}),
                        }["max_age_minutes"]
                        indoor_c = temperature_sensor_c(self.hass, indoor_entity, max_age)
                        if indoor_c is None:
                            errors["base"] = "missing_mold_indoor_temperature"
                        else:
                            outdoor = next(
                                (
                                    wx for entity_id in self._values.get(CONF_WEATHER, [])
                                    if (wx := current_weather(self.hass, entity_id, max_age)).temperature_c
                                    is not None
                                ),
                                None,
                            )
                            if outdoor is None:
                                errors["base"] = "missing_mold_outdoor_temperature"
                            else:
                                factor = calibration_factor(
                                    indoor_c, outdoor.temperature_c, surface
                                )
                                if factor is None:
                                    errors["base"] = "invalid_mold_calibration"
                                else:
                                    updated_calibration = {
                                        "indoor_temperature_entity": indoor_entity,
                                        "outdoor_weather_entity": outdoor.entity_id,
                                        "critical_temperature_c": surface,
                                        "calibration_factor": factor,
                                        "calibrated_indoor_c": indoor_c,
                                        "calibrated_outdoor_c": outdoor.temperature_c,
                                    }

            if not errors:
                per_area = dict(previous)
                per_area[area_id] = selected
                self._values[CONF_EXCLUDED_INDOOR] = per_area
                if mold_on and updated_calibration is not None:
                    all_calibrations = dict(saved_rooms)
                    if updated_calibration:
                        all_calibrations[area_id] = updated_calibration
                    else:
                        all_calibrations.pop(area_id, None)
                    self._values[CONF_MOLD_ROOMS] = all_calibrations
                self._indoor_index += 1
                return await self.async_step_indoor_sensors()

        from homeassistant.helpers import area_registry as ar
        registered_area = ar.async_get(self.hass).async_get_area(area_id)
        area_name = registered_area.name if registered_area else area_id
        fields: dict[Any, Any] = {
            _marker(
                CONF_EXCLUDED_INDOOR,
                user_input.get(CONF_EXCLUDED_INDOOR, []) if user_input is not None
                else list(previous.get(area_id, [])),
            ): _multi(choices),
        }
        if mold_on:
            selected_sensor = current.get("indoor_temperature_entity")
            if room_sensors:
                fields[_marker(
                    CONF_MOLD_ROOM_SENSOR,
                    user_input.get(CONF_MOLD_ROOM_SENSOR, selected_sensor or room_sensors[0]["value"])
                    if user_input is not None else selected_sensor or room_sensors[0]["value"],
                )] = selector.SelectSelector(selector.SelectSelectorConfig(
                    options=room_sensors, multiple=False, custom_value=False,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                ))
            fields[_marker(
                CONF_MOLD_CRITICAL_TEMP,
                user_input.get(CONF_MOLD_CRITICAL_TEMP, current.get("critical_temperature_c"))
                if user_input is not None else current.get("critical_temperature_c"),
            )] = selector.NumberSelector(selector.NumberSelectorConfig(
                min=-60, max=85, step=0.1, unit_of_measurement="°C",
                mode=selector.NumberSelectorMode.BOX,
            ))
            if current:
                fields[_marker(CONF_MOLD_RECALIBRATE, False)] = selector.BooleanSelector()

        return self.async_show_form(
            step_id="indoor_sensors",
            description_placeholders={
                "area_name": area_name,
                "position": str(index + 1),
                "total": str(len(area_ids)),
                "mold_room_notice": self._mold_room_notice(
                    area_id, current,
                    user_input.get(CONF_EXCLUDED_INDOOR, [])
                    if user_input is not None else previous.get(area_id, []),
                ),
            },
            data_schema=probatio.Schema(fields),
            errors=errors,
        )

    async def async_step_outdoor(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        choices = outdoor_choices(self.hass, self._values.get(CONF_AREAS, []))
        errors: dict[str, str] = {}
        if user_input is not None:
            selected = user_input.get(CONF_OUTDOOR, [])
            known = {item["value"] for item in choices}
            if selected and all(value in known for value in selected):
                self._values[CONF_OUTDOOR] = selected
                return await self._advance("weather")
            errors["base"] = "invalid_outdoor"
        elif not choices:
            errors["base"] = "no_outdoor"
        return self.async_show_form(
            step_id="outdoor",
            data_schema=probatio.Schema({
                _marker(CONF_OUTDOOR, self._values.get(CONF_OUTDOOR, []), required=True): _multi(choices),
            }), errors=errors,
        )

    async def async_step_weather(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        alerts = warning_choices(self.hass)
        known_alerts = {choice["value"] for choice in alerts}
        errors: dict[str, str] = {}
        if user_input is not None:
            weather_entities = user_input.get(CONF_WEATHER, [])
            warnings = user_input.get(CONF_WARNINGS, [])
            if not weather_entities or not all(e.startswith("weather.") for e in weather_entities):
                errors["base"] = "invalid_weather"
            elif not all(e in known_alerts for e in warnings):
                errors["base"] = "invalid_warning"
            else:
                self._values[CONF_WEATHER] = weather_entities
                self._values[CONF_WARNINGS] = warnings
                if self._values.get(CONF_USE_MOLD, False):
                    self._indoor_index = 0
                    return await self._advance("indoor_sensors")
                return await self._advance("delivery")
        schema: dict[Any, Any] = {
            _marker(CONF_WEATHER, self._values.get(CONF_WEATHER, []), required=True):
                selector.EntitySelector(selector.EntitySelectorConfig(domain="weather", multiple=True)),
        }
        if alerts:
            schema[_marker(CONF_WARNINGS, [
                w for w in self._values.get(CONF_WARNINGS, []) if w in known_alerts
            ])] = _multi(alerts)
        return self.async_show_form(
            step_id="weather", data_schema=probatio.Schema(schema), errors=errors,
            description_placeholders={
                "mold_weather_notice": self._mold_weather_notice(
                    user_input.get(CONF_WEATHER, [])
                    if user_input is not None else self._values.get(CONF_WEATHER, []),
                ),
            },
        )

    async def async_step_delivery(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        # A notify action can be registered without a loaded/configured Hub.
        # Only an actual Announcement Hub config entry enables this choice.
        hub_present = hub_installed(self.hass)
        ai_service_available = self.hass.services.has_service("conversation", "process")
        ai_agents = conversation_agent_choices(self.hass, self._values.get(CONF_AI_AGENT))
        valid_ai_agents = {choice["value"] for choice in ai_agents}
        has_notify = bool(self.hass.states.async_all("notify"))
        has_tts = bool(self.hass.states.async_all("tts"))
        player_options = _tts_player_options(self.hass)
        has_players = bool(player_options)
        if user_input is not None:
            selected = dict(self._values)
            selected.update(user_input)
            hub = hub_present and bool(selected.get(CONF_HUB, False))
            raw_repeat = selected.get(CONF_REPEAT_MINUTES, DEFAULT_REPEAT_MINUTES)
            try:
                minutes = float(raw_repeat)
            except (TypeError, ValueError, OverflowError):
                minutes = float("nan")
            if (isinstance(raw_repeat, bool) or not math.isfinite(minutes)
                    or minutes != int(minutes)
                    or not 0 <= minutes <= MAX_REPEAT_MINUTES):
                errors = {"base": "invalid_repeat_minutes"}
            elif (selected.get(CONF_AUTO_NOTIFY) and not hub
                and not selected.get(CONF_NOTIFY_TARGETS)
                and not self.hass.services.has_service("persistent_notification", "create")):
                errors = {"base": "missing_notify"}
            elif selected.get(CONF_AUTO_TTS) and not hub and not (
                selected.get(CONF_TTS_ENGINE) and selected.get(CONF_MEDIA_PLAYERS)
            ):
                errors = {"base": "missing_tts"}
            elif selected.get(CONF_AI_REWRITE) and not hub and not ai_service_available:
                errors = {"base": "missing_ai_service"}
            elif selected.get(CONF_AI_REWRITE) and not hub and (
                selected.get(CONF_AI_AGENT, DEFAULT_AGENT) not in valid_ai_agents
            ):
                errors = {"base": "invalid_ai_agent"}
            else:
                self._values.update(user_input)
                if CONF_LANGUAGE in user_input:
                    # The translated selector keys must be lowercase for
                    # Hassfest; restore the canonical BCP47 value on save.
                    locale = str(user_input[CONF_LANGUAGE]).strip()
                    self._values[CONF_LANGUAGE] = (
                        "auto" if locale.lower() == "auto"
                        else resolve_language(locale)
                    )
                self._values[CONF_REPEAT_MINUTES] = int(minutes)
                self._values.setdefault(CONF_HUB, False)
                self._values.setdefault(CONF_AUTO_NOTIFY, False)
                self._values.setdefault(CONF_AUTO_TTS, False)
                self._values.setdefault(CONF_NOTIFY_TARGETS, [])
                self._values.setdefault(CONF_MEDIA_PLAYERS, [])
                self._values.setdefault(CONF_AI_REWRITE, False)
                self._values.setdefault(CONF_AI_AGENT, DEFAULT_AGENT)
                return await self._finish()
        else:
            errors = {}
        fields: dict[Any, Any] = {
            _marker(
                CONF_LANGUAGE,
                str(self._values.get(CONF_LANGUAGE) or "auto").lower(),
                required=True,
            ):
                selector.SelectSelector(selector.SelectSelectorConfig(
                    # Translation keys are lowercase, even for regional/
                    # script tags. Existing saved canonical tags remain valid.
                    options=["auto", *(tag.lower() for tag in SUPPORTED_LANGUAGE_TAGS)],
                    translation_key="output_language",
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )),
            _marker(CONF_AUTO_NOTIFY, self._values.get(CONF_AUTO_NOTIFY, False)):
                selector.BooleanSelector(),
            _marker(CONF_AUTO_TTS, self._values.get(CONF_AUTO_TTS, False)):
                selector.BooleanSelector(),
            _marker(
                CONF_REPEAT_MINUTES,
                self._values.get(CONF_REPEAT_MINUTES, DEFAULT_REPEAT_MINUTES),
                required=True,
            ): selector.NumberSelector(selector.NumberSelectorConfig(
                min=0, max=MAX_REPEAT_MINUTES, step=1,
                unit_of_measurement="min",
                mode=selector.NumberSelectorMode.BOX,
            )),
            _marker(CONF_AI_REWRITE, self._values.get(CONF_AI_REWRITE, False)):
                selector.BooleanSelector(),
        }
        if hub_present:
            fields[_marker(CONF_HUB, self._values.get(CONF_HUB, True))] = selector.BooleanSelector()
        # Keep the agent selector visible alongside the general AI checkbox.
        # With no provider it still defaults to HA; choosing AI then raises
        # the existing missing_ai_service validation rather than failing later.
        fields[_marker(CONF_AI_AGENT, self._values.get(CONF_AI_AGENT, DEFAULT_AGENT), required=True)] = (
            selector.SelectSelector(selector.SelectSelectorConfig(
                options=ai_agents, multiple=False, custom_value=False,
                mode=selector.SelectSelectorMode.DROPDOWN,
            ))
        )
        if has_notify:
            fields[_marker(CONF_NOTIFY_TARGETS, self._values.get(CONF_NOTIFY_TARGETS, []))] = (
                selector.EntitySelector(selector.EntitySelectorConfig(domain="notify", multiple=True))
            )
        if has_tts:
            fields[_marker(CONF_TTS_ENGINE, self._values.get(CONF_TTS_ENGINE))] = (
                selector.EntitySelector(selector.EntitySelectorConfig(domain="tts"))
            )
        if has_players:
            fields[_marker(CONF_MEDIA_PLAYERS, self._values.get(CONF_MEDIA_PLAYERS, []))] = _multi(
                player_options
            )
        return self.async_show_form(step_id="delivery", data_schema=probatio.Schema(fields), errors=errors)


    async def async_step_environment(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Global provider-driven configuration; never infer country from HA locale."""
        current = self._values.get(CONF_ENVIRONMENT_GLOBAL, {})
        if not isinstance(current, dict):
            current = {}
        aqis = [value for value in self._values.get(CONF_OUTDOOR, [])
                if value.startswith("sensor.") and
                (state := self.hass.states.get(value)) is not None and
                (str(state.attributes.get("device_class", "")).casefold() == "aqi"
                 or value.endswith("_aqi") or value.endswith("_air_quality_index"))]
        data = dict(current)
        errors = {}
        if user_input is not None:
            scales = {}
            for i, entity in enumerate(aqis):
                scale = str(user_input.get(f"aqi_scale_{i}", "not_configured"))
                raw_limit = user_input.get(f"aqi_custom_limit_{i}")
                limit = None
                if scale == "custom":
                    try:
                        limit = float(raw_limit)
                    except (ValueError, TypeError, OverflowError):
                        limit = float("nan")
                if scale not in {row["value"] for row in ENV_AQI_SCALES} or (
                    scale == "custom" and (not math.isfinite(limit) or not 0 <= limit <= 10000)
                ):
                    errors["base"] = "invalid_environment_scale"
                    break
                if scale != "not_configured":
                    scales[entity] = {"scale": scale, **({"custom_limit": limit} if scale=="custom" else {})}
            entity = user_input.get("pollen_entity")
            try:
                high, maximum = (float(user_input.get("pollen_high_from", 3)),
                                 float(user_input.get("pollen_max_scale", 5)))
            except (TypeError, ValueError, OverflowError):
                high, maximum = float("nan"), float("nan")
            if (entity and (not isinstance(entity, str) or not entity.startswith("sensor."))
                    or not all(math.isfinite(v) for v in (high, maximum))
                    or not 0 <= high <= maximum <= 100):
                errors["base"] = "invalid_environment_scale"
            if not errors:
                data.update({
                    "aqi_scales": scales, "pollen_entity": entity or None,
                    "pollen_high_from": high, "pollen_max_scale": maximum,
                    "pollen_avoid_ventilation": bool(user_input.get("pollen_avoid_ventilation", False)),
                })
                self._values[CONF_ENVIRONMENT_GLOBAL] = data
                return await self._finish()
        fields = {
            _marker("pollen_entity", current.get("pollen_entity")): _optional_sensor(),
            _marker("pollen_high_from", current.get("pollen_high_from", 3.0)): _real_number(0, 100),
            _marker("pollen_max_scale", current.get("pollen_max_scale", 5.0)): _real_number(1, 100),
            _marker("pollen_avoid_ventilation", current.get("pollen_avoid_ventilation", False)): selector.BooleanSelector(),
        }
        configured = current.get("aqi_scales", {})
        if not isinstance(configured, dict):
            configured = {}
        for i, entity in enumerate(aqis):
            details = configured.get(entity, {})
            if not isinstance(details, dict):
                details = {}
            fields[_marker(f"aqi_scale_{i}", details.get("scale","not_configured"))] = (
                selector.SelectSelector(selector.SelectSelectorConfig(
                    options=ENV_AQI_SCALES, multiple=False, custom_value=False,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                ))
            )
            fields[_marker(f"aqi_custom_limit_{i}", details.get("custom_limit", 100))] = _real_number(0,10000)
        return self.async_show_form(
            step_id="environment", data_schema=probatio.Schema(fields), errors=errors,
            description_placeholders={"aqi_entities": ", ".join(aqis) if aqis else "No AQI sensors selected"},
        )

    def _environment_area_name(self) -> str:
        from homeassistant.helpers import area_registry as ar
        area = ar.async_get(self.hass).async_get_area(self._environment_area)
        return area.name if area else self._environment_area

    async def async_step_environment_room(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick exactly one room rather than making users repeat a huge wizard."""
        ids = list(self._values.get(CONF_AREAS, []))
        if not ids:
            return await self._finish()
        from homeassistant.helpers import area_registry as ar
        registry = ar.async_get(self.hass)
        choices = [
            {"value": key, "label": getattr(registry.async_get_area(key), "name", key)}
            for key in ids
        ]
        if user_input is not None:
            area = user_input.get("environment_area")
            if area in ids:
                self._environment_area = area
                saved = self._values.get(CONF_ENVIRONMENT_ROOMS, {})
                self._environment_room_data = dict(saved.get(area, {})) if isinstance(saved, dict) else {}
                return await self.async_step_environment_room_air()
            errors = {"base": "invalid_areas"}
        else:
            errors = {}
        return self.async_show_form(step_id="environment_room",
            data_schema=probatio.Schema({
                _marker("environment_area", ids[0], required=True):
                    selector.SelectSelector(selector.SelectSelectorConfig(
                        options=choices, custom_value=False,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ))
            }), errors=errors)

    async def async_step_environment_room_air(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Measured ventilation, occupant-supplied room volume and rated CADR."""
        current = self._environment_room_data
        if user_input is not None:
            for field in ("room_volume_m3", "particle_cadr_m3h", "co2_target_ppm"):
                if user_input.get(field) is not None:
                    try:
                        number = float(user_input[field])
                    except (TypeError, ValueError, OverflowError):
                        number = float("nan")
                    low, high = {"room_volume_m3":(1,30000),
                                 "particle_cadr_m3h":(0.1,100000),
                                 "co2_target_ppm":(400,3000)}[field]
                    if not math.isfinite(number) or not low <= number <= high:
                        return self.async_show_form(step_id="environment_room_air",
                            data_schema=self._environment_room_air_schema(current),
                            errors={"base":"invalid_environment_measurement"},
                            description_placeholders={"area_name":self._environment_area_name()})
            current.update(user_input)
            return await self.async_step_environment_room_exposure()
        return self.async_show_form(step_id="environment_room_air",
            data_schema=self._environment_room_air_schema(current),
            description_placeholders={"area_name":self._environment_area_name()})

    def _environment_room_air_schema(self, current: dict) -> probatio.Schema:
        return probatio.Schema({
            _marker("temperature_entity", current.get("temperature_entity")): _optional_sensor(),
            _marker("room_volume_m3", current.get("room_volume_m3")): _real_number(1,30000,"m³"),
            _marker("particle_cadr_m3h", current.get("particle_cadr_m3h")): _real_number(0.1,100000,"m³/h"),
            _marker("purifier_entity", current.get("purifier_entity")): _entity_any(),
            _marker("extractor_entity", current.get("extractor_entity")): _entity_any(),
            _marker("co2_ndir_verified", current.get("co2_ndir_verified", False)): selector.BooleanSelector(),
            _marker("co2_target_ppm", current.get("co2_target_ppm", 1000)): _real_number(400,3000,"ppm"),
            _marker("sleep_room", current.get("sleep_room", False)): selector.BooleanSelector(),
        })

    async def async_step_environment_room_exposure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Optional specialist sensors; none are required for installation."""
        current = self._environment_room_data
        if user_input is not None:
            current.update(user_input)
            return await self.async_step_environment_room_comfort()
        fields = {
            _marker("radon_entity",current.get("radon_entity")): _optional_sensor(),
            _marker("radon_sensor_verified",current.get("radon_sensor_verified",False)):selector.BooleanSelector(),
            _marker("formaldehyde_entity",current.get("formaldehyde_entity")): _optional_sensor(),
            _marker("formaldehyde_sensor_verified",current.get("formaldehyde_sensor_verified",False)):selector.BooleanSelector(),
            _marker("noise_entity",current.get("noise_entity")): _optional_sensor(),
            _marker("noise_sensor_calibrated",current.get("noise_sensor_calibrated",False)):selector.BooleanSelector(),
            _marker("illuminance_entity",current.get("illuminance_entity")): _optional_sensor(),
            _marker("melanopic_edi_entity",current.get("melanopic_edi_entity")): _optional_sensor(),
            _marker("melanopic_spectral_verified",current.get("melanopic_spectral_verified",False)):selector.BooleanSelector(),
        }
        return self.async_show_form(step_id="environment_room_exposure",
            data_schema=probatio.Schema(fields),
            description_placeholders={"area_name":self._environment_area_name()})

    async def async_step_environment_room_comfort(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """ISO 7730 requests explicit MRT, air velocity, MET and CLO assumptions."""
        current = self._environment_room_data
        fields = {
            _marker("enable_pmv",current.get("enable_pmv",False)): selector.BooleanSelector(),
            _marker("radiant_temperature_entity",current.get("radiant_temperature_entity")): _optional_sensor(),
            _marker("air_speed_entity",current.get("air_speed_entity")): _optional_sensor(),
            _marker("air_speed_m_s",current.get("air_speed_m_s")): _real_number(0.01,0.99,"m/s"),
            _marker("met",current.get("met")): _real_number(0.81,3.99,"met"),
            _marker("clo",current.get("clo")): _real_number(0.01,1.99,"clo"),
        }
        if user_input is not None:
            selected = {**current, **user_input}
            if selected.get("enable_pmv") and (
                not selected.get("radiant_temperature_entity")
                or not (selected.get("air_speed_entity") or selected.get("air_speed_m_s") is not None)
                or selected.get("met") is None or selected.get("clo") is None
            ):
                errors = {"base":"pmv_requires_explicit_inputs"}
            elif any(
                value is not None and (not isinstance(value,(int,float)) or not math.isfinite(value)
                    or not low <= value <= high)
                for key,low,high in (("air_speed_m_s",0.01,0.99),("met",0.81,3.99),("clo",0.01,1.99))
                if (value := selected.get(key)) is not None
            ):
                errors = {"base":"invalid_environment_measurement"}
            else:
                saved = self._values.get(CONF_ENVIRONMENT_ROOMS, {})
                saved = dict(saved) if isinstance(saved,dict) else {}
                saved[self._environment_area] = selected
                self._values[CONF_ENVIRONMENT_ROOMS] = saved
                return await self._finish()
        else:
            errors = {}
        return self.async_show_form(step_id="environment_room_comfort",
            data_schema=probatio.Schema(fields), errors=errors,
            description_placeholders={"area_name":self._environment_area_name()})

    async def async_step_thresholds(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            if user_input["min_outdoor_temp"] >= user_input["max_outdoor_temp"]:
                errors = {"base": "temperature_range"}
            else:
                self._values[CONF_THRESHOLDS] = user_input
                return await self._finish()
        else:
            errors = {}
        previous = {**DEFAULT_THRESHOLDS, **self._values.get(CONF_THRESHOLDS, {})}
        schema = {}
        for key, default in previous.items():
            is_temp = key in ("min_outdoor_temp", "max_outdoor_temp")
            schema[_marker(key, default, required=True)] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-40 if is_temp else 1,
                    max=100 if key in ("indoor_mold", "indoor_humidity") else (
                        100000 if key == "max_age_minutes" else 10000
                    ),
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                )
            )
        return self.async_show_form(step_id="thresholds", data_schema=probatio.Schema(schema), errors=errors)


class AirQualityConfigFlow(_FlowMixin, config_entries.ConfigFlow, domain=DOMAIN):
    """One advisor instance covering all selected HA areas."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id("home")
        self._abort_if_unique_id_configured()
        self._editing = False
        self._values = {}
        return await self.async_step_areas()

    async def _finish(self) -> ConfigFlowResult:
        return self.async_create_entry(title="Home Environment Manager", data=self._values)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> AirQualityOptionsFlow:
        return AirQualityOptionsFlow()


class AirQualityOptionsFlow(_FlowMixin, OptionsFlowWithReload):
    """Choose exactly one section of saved settings to modify."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        self._editing = True
        self._menu_mode = True
        self._values = {**self.config_entry.data, **self.config_entry.options}
        self._indoor_index = 0
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "areas", "weather", "indoor_sensors", "window_sensors",
                "outdoor", "delivery", "thresholds", "environment", "environment_room",
            ],
        )

    async def _finish(self) -> ConfigFlowResult:
        return self.async_create_entry(data=self._values)
