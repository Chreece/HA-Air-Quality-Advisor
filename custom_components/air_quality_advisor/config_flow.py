"""Compact multi-page UI: rooms, outdoors, weather/warnings, announcements."""

from __future__ import annotations

from typing import Any

import probatio

from homeassistant import config_entries
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.config_entries import ConfigFlowResult, OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_AREAS, CONF_AUTO_NOTIFY, CONF_AUTO_TTS, CONF_HUB,
    CONF_LANGUAGE, CONF_MEDIA_PLAYERS, CONF_NOTIFY_TARGETS, CONF_OUTDOOR,
    CONF_THRESHOLDS, CONF_TTS_ENGINE, CONF_WARNINGS, CONF_WEATHER,
    DEFAULT_THRESHOLDS, DOMAIN,
)
from .discovery import outdoor_choices, warning_choices


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

    async def async_step_areas(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get(CONF_AREAS):
                errors["base"] = "no_areas"
            else:
                self._values[CONF_AREAS] = user_input[CONF_AREAS]
                return await self.async_step_outdoor()
        return self.async_show_form(step_id="areas", data_schema=probatio.Schema({
            _marker(CONF_AREAS, self._values.get(CONF_AREAS, []), required=True):
                selector.AreaSelector(selector.AreaSelectorConfig(multiple=True)),
        }), errors=errors)

    async def async_step_outdoor(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        choices = outdoor_choices(self.hass, self._values.get(CONF_AREAS, []))
        errors: dict[str, str] = {}
        if user_input is not None:
            selected = user_input.get(CONF_OUTDOOR, [])
            known = {item["value"] for item in choices}
            if selected and all(value in known for value in selected):
                self._values[CONF_OUTDOOR] = selected
                return await self.async_step_weather()
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
                if getattr(self, "_editing", False):
                    return await self._finish()
                return await self.async_step_delivery()
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
        hub_present = self.hass.services.has_service("notify", "announcement_hub")
        has_notify = bool(self.hass.states.async_all("notify"))
        has_tts = bool(self.hass.states.async_all("tts"))
        player_options = _tts_player_options(self.hass)
        has_players = bool(player_options)
        if user_input is not None:
            selected = dict(self._values)
            selected.update(user_input)
            hub = hub_present and bool(selected.get(CONF_HUB, False))
            if selected.get(CONF_AUTO_NOTIFY) and not hub and not selected.get(CONF_NOTIFY_TARGETS):
                errors = {"base": "missing_notify"}
            elif selected.get(CONF_AUTO_TTS) and not hub and not (
                selected.get(CONF_TTS_ENGINE) and selected.get(CONF_MEDIA_PLAYERS)
            ):
                errors = {"base": "missing_tts"}
            else:
                self._values.update(user_input)
                self._values.setdefault(CONF_HUB, False)
                self._values.setdefault(CONF_AUTO_NOTIFY, False)
                self._values.setdefault(CONF_AUTO_TTS, False)
                self._values.setdefault(CONF_NOTIFY_TARGETS, [])
                self._values.setdefault(CONF_MEDIA_PLAYERS, [])
                return await self._finish()
        else:
            errors = {}
        fields: dict[Any, Any] = {
            _marker(CONF_LANGUAGE, self._values.get(CONF_LANGUAGE, "auto"), required=True):
                selector.SelectSelector(selector.SelectSelectorConfig(
                    options=[
                        {"value": "auto", "label": "Home Assistant default"},
                        {"value": "en", "label": "English"},
                        {"value": "de", "label": "Deutsch"},
                        {"value": "el", "label": "Ελληνικά"},
                        {"value": "fr", "label": "Français"},
                        {"value": "es", "label": "Español"},
                    ], mode=selector.SelectSelectorMode.DROPDOWN,
                )),
            _marker(CONF_AUTO_NOTIFY, self._values.get(CONF_AUTO_NOTIFY, False)):
                selector.BooleanSelector(),
            _marker(CONF_AUTO_TTS, self._values.get(CONF_AUTO_TTS, False)):
                selector.BooleanSelector(),
        }
        if hub_present or self._values.get(CONF_HUB):
            fields[_marker(CONF_HUB, self._values.get(CONF_HUB, hub_present))] = selector.BooleanSelector()
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
    """Reconfigure all selections, with extra thresholds after delivery."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        self._editing = True
        self._values = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_menu(
            step_id="init", menu_options=["areas", "delivery", "thresholds"]
        )

    async def _finish(self) -> ConfigFlowResult:
        return self.async_create_entry(data=self._values)
