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

from .languages import SUPPORTED_LANGUAGE_TAGS

from .ai_rewrite import DEFAULT_AGENT, conversation_agent_choices
from .hub_delivery import hub_installed
from .const import (
    CONF_AREAS, CONF_EXCLUDED_WINDOWS, CONF_EXCLUDED_INDOOR, CONF_AUTO_NOTIFY, CONF_AUTO_TTS, CONF_HUB,
    CONF_LANGUAGE, CONF_MEDIA_PLAYERS, CONF_NOTIFY_TARGETS, CONF_OUTDOOR,
    CONF_REPEAT_MINUTES, DEFAULT_REPEAT_MINUTES, MAX_REPEAT_MINUTES,
    CONF_AI_REWRITE, CONF_AI_AGENT,
    CONF_THRESHOLDS, CONF_TTS_ENGINE, CONF_WARNINGS, CONF_WEATHER,
    DEFAULT_THRESHOLDS, DOMAIN,
)
from .discovery import (
    indoor_sensor_exclusion_choices, outdoor_choices, suggested_window_exclusions, warning_choices,
    window_area_choices, window_exclusion_choices,
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


class _FlowMixin:
    """Use the same pages in initial setup and reconfiguration."""

    _values: dict[str, Any]

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
                    return await self._advance("indoor_sensors")
        elif not choices:
            if not getattr(self, "_menu_mode", False) and self._values.get(CONF_AREAS):
                # Contacts vanished between the Rooms and Exclusions pages.
                # Do not silently continue with unusable selected rooms.
                errors["base"] = "no_windows_after_exclusions"
            else:
                self._values.setdefault(CONF_EXCLUDED_WINDOWS, [])
                return await self._advance("indoor_sensors")
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
                self._indoor_index = 0
                if reviewing:
                    self._review_areas_after_exclusions = False
                    return await self._advance("indoor_sensors")
                return await self._advance("window_sensors")
        elif not choices:
            errors["base"] = "no_window_areas"
        elif reviewing:
            errors["base"] = "review_areas_after_exclusions"
        return self.async_show_form(step_id="areas", data_schema=probatio.Schema({
            _marker(CONF_AREAS, user_input.get(CONF_AREAS, []) if user_input is not None
                    else default_areas, required=True): _multi(choices),
        }), errors=errors)

    async def async_step_indoor_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Review all supported air sensors (including humidity), one area at a time.

        Missing selected sensors are retained and removable during reconfigure.
        Skipping rooms with no candidates avoids presenting an empty selector.
        """
        area_ids = list(self._values.get(CONF_AREAS, []))
        previous = self._values.get(CONF_EXCLUDED_INDOOR, {})
        if not isinstance(previous, dict):
            previous = {}
        index = getattr(self, "_indoor_index", 0)
        while index < len(area_ids):
            area_id = area_ids[index]
            choices = indoor_sensor_exclusion_choices(
                self.hass, area_id, previous.get(area_id, [])
            )
            if choices:
                break
            index += 1
        self._indoor_index = index
        if index >= len(area_ids):
            return await self._advance("outdoor")

        known = {choice["value"] for choice in choices}
        errors: dict[str, str] = {}
        if user_input is not None:
            selected = list(dict.fromkeys(user_input.get(CONF_EXCLUDED_INDOOR, [])))
            if any(entity_id not in known for entity_id in selected):
                errors["base"] = "invalid_indoor_exclusions"
            else:
                # An empty list is a deliberate choice, never a signal to
                # restore previous exclusions or auto-select humidity.
                per_area = dict(previous)
                per_area[area_id] = selected
                self._values[CONF_EXCLUDED_INDOOR] = per_area
                self._indoor_index += 1
                return await self.async_step_indoor_sensors()

        from homeassistant.helpers import area_registry as ar
        registered_area = ar.async_get(self.hass).async_get_area(area_id)
        area_name = registered_area.name if registered_area else area_id
        return self.async_show_form(
            step_id="indoor_sensors",
            description_placeholders={
                "area_name": area_name,
                "position": str(index + 1),
                "total": str(len(area_ids)),
            },
            data_schema=probatio.Schema({
                _marker(
                    CONF_EXCLUDED_INDOOR,
                    user_input.get(CONF_EXCLUDED_INDOOR, [])
                    if user_input is not None else list(previous.get(area_id, [])),
                ): _multi(choices),
            }),
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
                return await self._advance("delivery")
        schema: dict[Any, Any] = {
            _marker(CONF_WEATHER, self._values.get(CONF_WEATHER, []), required=True):
                selector.EntitySelector(selector.EntitySelectorConfig(domain="weather", multiple=True)),
        }
        if alerts:
            schema[_marker(CONF_WARNINGS, [
                w for w in self._values.get(CONF_WARNINGS, []) if w in known_alerts
            ])] = _multi(alerts)
        return self.async_show_form(step_id="weather", data_schema=probatio.Schema(schema), errors=errors)

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
            _marker(CONF_LANGUAGE, self._values.get(CONF_LANGUAGE, "auto"), required=True):
                selector.SelectSelector(selector.SelectSelectorConfig(
                    # translation_key uses the current HA UI locale, not the
                    # server's configured language, unlike hardcoded labels.
                    options=["auto", *SUPPORTED_LANGUAGE_TAGS],
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
                    max=100000 if key == "max_age_minutes" else 10000,
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
        return self.async_create_entry(title="Air Quality Advisor", data=self._values)

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
                "areas", "window_sensors", "indoor_sensors", "outdoor",
                "weather", "delivery", "thresholds",
            ],
        )

    async def _finish(self) -> ConfigFlowResult:
        return self.async_create_entry(data=self._values)
