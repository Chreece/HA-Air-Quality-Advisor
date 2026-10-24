"""Rooms -> one six-input page per selected room -> general sources -> done.

Drafts are isolated until the final submit. The same route handles initial
setup and Options; operating parameters remain on Home/Room/controller devices.
"""
from __future__ import annotations

from .config_data import mutable_copy as deepcopy
from typing import Any

import probatio
from homeassistant.helpers import area_registry as ar, selector

from .const import (
    CONF_AREAS, CONF_WEATHER, CONF_OUTDOOR, CONF_WARNINGS, CONF_LANGUAGE,
    CONF_NOTIFY_TARGETS, CONF_MEDIA_PLAYERS, CONF_TTS_ENGINE, CONF_AI_AGENT, CONF_HUB,
    CONF_OCCUPANCY_GLOBAL, CONF_ENVIRONMENT_GLOBAL, CONF_USE_MOLD,
)
from . import room_sources as sources


def field(name: str, default: Any):
    return probatio.Optional(name, default=default)


def select(options, multiple=False, translation_key=None):
    config = dict(options=options, multiple=multiple, custom_value=False,
                  mode=selector.SelectSelectorMode.DROPDOWN)
    if translation_key:
        config["translation_key"] = translation_key
    return selector.SelectSelector(selector.SelectSelectorConfig(**config))


def areas(hass: Any) -> list[dict]:
    registry = ar.async_get(hass)
    return sorted(({"value": area.id, "label": area.name}
                   for area in registry.areas.values()), key=lambda item: item["label"].casefold())


def _merge(base, edited, current):
    """Three-way merge: retain unrelated device edits made during this wizard."""
    if base == edited:
        return deepcopy(current)
    if current == base or current == edited:
        return deepcopy(edited)
    if all(isinstance(v, dict) for v in (base, edited, current)):
        out = deepcopy(current)
        absent = object()
        for key in base.keys() | edited.keys():
            b, e, c = base.get(key, absent), edited.get(key, absent), current.get(key, absent)
            if b == e:
                continue
            if e is absent:
                if c != b and c is not absent:
                    raise ValueError("setup_changed")
                out.pop(key, None)
            elif b is absent:
                if c is not absent and c != e:
                    raise ValueError("setup_changed")
                out[key] = deepcopy(e)
            elif c is absent:
                raise ValueError("setup_changed")
            else:
                out[key] = _merge(b, e, c)
        return out
    raise ValueError("setup_changed")


class RoomSetupMixin:
    """Source selection, never hardware operations or control-method menus."""

    def _start_room_setup(self):
        self._values = deepcopy(self._values)
        self._setup_base = deepcopy(self._values)
        self._setup_order = []
        self._setup_index = 0

    async def async_step_setup_rooms(self, user_input=None):
        if not hasattr(self, "_setup_base"):
            self._start_room_setup()
        options = areas(self.hass)
        known = {item["value"] for item in options}
        old = self._values.get(CONF_AREAS, [v["value"] for v in options])
        default = [v for v in old if v in known]
        errors = {}
        if user_input is not None:
            value = user_input.get(CONF_AREAS, [])
            if (not isinstance(value, list) or not value
                    or any(not isinstance(v, str) or v not in known for v in value)):
                errors["base"] = "invalid_setup_rooms"
            else:
                self._setup_order = list(dict.fromkeys(value))
                self._setup_index = 0
                sources.restrict_rooms(self._values, self._setup_order)
                return await self.async_step_setup_room_sources()
        return self.async_show_form(step_id="setup_rooms", errors=errors,
            data_schema=probatio.Schema({probatio.Required(CONF_AREAS, default=default):
                                         select(options, multiple=True)}))

    async def async_step_setup_room_sources(self, user_input=None):
        if not self._setup_order or self._setup_index >= len(self._setup_order):
            return await self.async_step_setup_general()
        area = self._setup_order[self._setup_index]
        room = ar.async_get(self.hass).async_get_area(area)
        if room is None:
            return self.async_abort(reason="setup_area_removed")
        saved = sources.defaults(self.hass, self._values, area)
        options = sources.choices(self.hass, area, saved)
        defaults = {group: [e for e in saved[group] if e in {c["value"] for c in options[group]}]
                    for group in sources.GROUPS}
        errors = {}
        if user_input is not None:
            data = {}
            for group in sources.GROUPS:
                value = user_input.get(group, defaults[group])
                allowed = {v["value"] for v in options[group]}
                if (not isinstance(value, list)
                        or any(not isinstance(e, str) or e not in allowed for e in value)):
                    errors[group] = "invalid_room_source"
                else:
                    data[group] = list(dict.fromkeys(value))
            if not errors:
                sources.store_selection(self.hass, self._values, area, data)
                self._setup_index += 1
                if self._setup_index == len(self._setup_order):
                    return await self.async_step_setup_general()
                return await self.async_step_setup_room_sources()
        return self.async_show_form(step_id="setup_room_sources", errors=errors,
            description_placeholders={"area_name": room.name,
                "room_index": str(self._setup_index+1), "room_count": str(len(self._setup_order))},
            data_schema=probatio.Schema({field(group, (user_input or {}).get(group, defaults[group])):
                select(options[group], multiple=True) for group in sources.GROUPS}))

    def _general_options(self):
        from .discovery import outdoor_choices, warning_choices, _device_class
        from .ai_rewrite import conversation_agent_choices
        from .config_flow import _tts_player_options
        state_options = lambda domain: [{"value": s.entity_id, "label": sources.label(self.hass, s.entity_id)}
            for s in self.hass.states.async_all(domain) if sources.native(self.hass, s.entity_id)]
        pres = [{"value": s.entity_id, "label": sources.label(self.hass, s.entity_id)}
                for s in self.hass.states.async_all("binary_sensor")
                if _device_class(self.hass, s) in ("occupancy", "presence")]
        room_entities = [{"value": "none", "label": "-"}, *self._room_source_options(self.hass)]
        env = self._values.get(CONF_ENVIRONMENT_GLOBAL, {})
        saved_pollen = set(env.get("pollen_entities", [])) if isinstance(env, dict) else set()
        if isinstance(env, dict) and isinstance(env.get("pollen_entity"), str):
            saved_pollen.add(env["pollen_entity"])
        pollen = [{"value": s.entity_id, "label": sources.label(self.hass, s.entity_id)}
                  for s in self.hass.states.async_all("sensor")
                  if "pollen" in s.entity_id.casefold() or s.entity_id in saved_pollen]
        result = {
            CONF_WEATHER: state_options("weather"),
            CONF_OUTDOOR: outdoor_choices(self.hass, self._values.get(CONF_AREAS, [])),
            CONF_WARNINGS: warning_choices(self.hass),
            "general_room_occupancy_sensors": pres,
            "general_home_trackers": [*state_options("person"), *state_options("device_tracker"), *pres],
            "general_occupied_rooms_entity": room_entities,
            "general_sleep_rooms_entity": room_entities,
            "pollen_entities": pollen,
            CONF_NOTIFY_TARGETS: state_options("notify"),
            CONF_MEDIA_PLAYERS: _tts_player_options(self.hass),
            CONF_TTS_ENGINE: [{"value": "none", "label": "-"}, *state_options("tts")],
            CONF_AI_AGENT: conversation_agent_choices(self.hass, self._values.get(CONF_AI_AGENT)),
        }
        for items in result.values():
            for item in items:
                entity = item["value"]
                if self.hass.states.get(entity) is not None:
                    item["label"] = sources.label(self.hass, entity)
        return result

    async def async_step_setup_general(self, user_input=None):
        from .languages import SUPPORTED_LANGUAGE_TAGS, resolve_language
        from .ai_rewrite import DEFAULT_AGENT
        if self._setup_index < len(self._setup_order):
            return await self.async_step_setup_room_sources()
        old = self._values.get(CONF_OCCUPANCY_GLOBAL, {})
        options = self._general_options()
        env = self._values.get(CONF_ENVIRONMENT_GLOBAL, {})
        saved_pollen = env.get("pollen_entities") if isinstance(env, dict) else None
        if not isinstance(saved_pollen, list):
            legacy = env.get("pollen_entity") if isinstance(env, dict) else None
            saved_pollen = [legacy] if isinstance(legacy, str) and legacy else None
        defaults = {
            CONF_WEATHER: self._values.get(CONF_WEATHER, [x["value"] for x in options[CONF_WEATHER]]),
            CONF_OUTDOOR: self._values.get(CONF_OUTDOOR, [x["value"] for x in options[CONF_OUTDOOR]]),
            CONF_WARNINGS: self._values.get(CONF_WARNINGS, []),
            CONF_NOTIFY_TARGETS: self._values.get(CONF_NOTIFY_TARGETS, []),
            CONF_MEDIA_PLAYERS: self._values.get(CONF_MEDIA_PLAYERS, []),
            CONF_TTS_ENGINE: self._values.get(CONF_TTS_ENGINE) or "none",
            CONF_AI_AGENT: self._values.get(CONF_AI_AGENT) or DEFAULT_AGENT,
            CONF_LANGUAGE: str(self._values.get(CONF_LANGUAGE, "auto")).lower(),
            CONF_USE_MOLD: self._values.get(CONF_USE_MOLD, False),
            "pollen_entities": saved_pollen if saved_pollen is not None else [x["value"] for x in options["pollen_entities"]],
            CONF_HUB: bool(self._values.get(CONF_HUB, False)),
            "general_room_occupancy_sensors": old.get("room_occupancy_sensors", []),
            "general_home_trackers": old.get("home_trackers", []),
            "general_away_cooldown_minutes": old.get("away_cooldown_minutes", 10),
            **{f"general_{prefix}_rooms_entity": old.get(f"{prefix}_rooms_entity") or "none"
               for prefix in ("occupied", "sleep")},
            **{f"general_{prefix}_rooms_attribute": old.get(f"{prefix}_rooms_attribute") or "__state__"
               for prefix in ("occupied", "sleep")},
        }
        multi = {CONF_WEATHER, CONF_OUTDOOR, CONF_WARNINGS, CONF_NOTIFY_TARGETS, CONF_MEDIA_PLAYERS,
                 "general_room_occupancy_sensors", "general_home_trackers", "pollen_entities"}
        errors = {}
        value = {**defaults, **(user_input or {})}
        from .tts_languages import language_options, preferred_language
        language_choices = language_options(self.hass, None if value[CONF_TTS_ENGINE] == "none" else value[CONF_TTS_ENGINE])
        language_values = {item["value"] for item in language_choices}
        value[CONF_LANGUAGE] = preferred_language(
            self.hass, None if value[CONF_TTS_ENGINE] == "none" else value[CONF_TTS_ENGINE],
            value[CONF_LANGUAGE])
        if user_input is not None:
            for key, items in options.items():
                allowed = {i["value"] for i in items}
                vals = value[key] if key in multi else [value[key]]
                if (not isinstance(vals, list) or any(not isinstance(v, str) or v not in allowed for v in vals)):
                    errors[key] = "invalid_room_source"
            if value[CONF_LANGUAGE] not in language_values:
                errors[CONF_LANGUAGE] = "invalid_room_source"
            if type(value[CONF_USE_MOLD]) is not bool:
                errors[CONF_USE_MOLD] = "invalid_room_source"
            try:
                away_cooldown = float(value["general_away_cooldown_minutes"])
            except (TypeError, ValueError, OverflowError):
                errors["general_away_cooldown_minutes"] = "invalid_room_source"
            else:
                if not 0 <= away_cooldown <= 240:
                    errors["general_away_cooldown_minutes"] = "invalid_room_source"
            from .hub_delivery import hub_installed
            if CONF_HUB in user_input and (type(value[CONF_HUB]) is not bool
                    or value[CONF_HUB] and not hub_installed(self.hass)):
                errors[CONF_HUB] = "invalid_room_source"
            # General settings is a single page. Dependent values are normalized
            # on submit instead of showing the exact same page a second time.
            for prefix in ("occupied", "sleep"):
                entity_key, attr_key = f"general_{prefix}_rooms_entity", f"general_{prefix}_rooms_attribute"
                entity = value[entity_key]
                if entity == "none":
                    value[attr_key] = "__state__"
                    continue
                attrs = self._room_attribute_options(self.hass, entity)
                allowed = {a["value"] for a in attrs}
                if value[attr_key] not in allowed:
                    value[attr_key] = "__state__"
            if not errors:
                # No implicit activation; preserve previously configured policies.
                for key in (CONF_WEATHER, CONF_OUTDOOR, CONF_WARNINGS, CONF_NOTIFY_TARGETS, CONF_MEDIA_PLAYERS):
                    self._values[key] = list(dict.fromkeys(value[key]))
                self._values[CONF_TTS_ENGINE] = None if value[CONF_TTS_ENGINE] == "none" else value[CONF_TTS_ENGINE]
                self._values[CONF_AI_AGENT] = value[CONF_AI_AGENT]
                from .hub_delivery import hub_installed
                self._values[CONF_HUB] = bool(value.get(CONF_HUB, False) and hub_installed(self.hass))
                self._values[CONF_LANGUAGE] = "auto" if value[CONF_LANGUAGE] == "auto" else resolve_language(value[CONF_LANGUAGE])
                self._values[CONF_USE_MOLD] = value[CONF_USE_MOLD]
                for area in self._setup_order:
                    calibration = self._values.setdefault("mold_rooms", {}).setdefault(area, {})
                    previous_weather = calibration.get("outdoor_weather_entity")
                    if previous_weather not in self._values[CONF_WEATHER]:
                        calibration["outdoor_weather_entity"] = (self._values[CONF_WEATHER][0]
                            if len(self._values[CONF_WEATHER]) == 1 else None)
                        if previous_weather:
                            for key in ("calibration_factor", "calibrated_at"):
                                calibration.pop(key, None)
                global_env = self._values.setdefault(CONF_ENVIRONMENT_GLOBAL, {})
                global_env["pollen_entities"] = list(dict.fromkeys(value["pollen_entities"]))
                global_env["pollen_entity"] = (
                    global_env["pollen_entities"][0] if global_env["pollen_entities"] else None)
                occupancy = deepcopy(old)
                for name in ("room_occupancy_sensors", "home_trackers"):
                    occupancy[name] = list(dict.fromkeys(value["general_"+name]))
                occupancy["away_cooldown_minutes"] = float(value["general_away_cooldown_minutes"])
                for prefix in ("occupied", "sleep"):
                    entity = value[f"general_{prefix}_rooms_entity"]
                    attr = value[f"general_{prefix}_rooms_attribute"]
                    occupancy[prefix+"_rooms_entity"] = None if entity == "none" else entity
                    occupancy[prefix+"_rooms_attribute"] = "" if attr == "__state__" else attr
                self._values[CONF_OCCUPANCY_GLOBAL] = occupancy
                # Last-page commit only: a cancelled or invalid setup writes nothing.
                if getattr(self, "_editing", False):
                    current = {**self.config_entry.data, **self.config_entry.options}
                    try:
                        self._values = _merge(self._setup_base, self._values, current)
                    except ValueError:
                        return self.async_abort(reason="setup_changed")
                return await self._finish()
        fields = {}
        for key in (CONF_WEATHER, CONF_OUTDOOR, CONF_WARNINGS, "general_room_occupancy_sensors",
                    "general_home_trackers", "general_occupied_rooms_entity", "general_sleep_rooms_entity",
                    "pollen_entities", CONF_NOTIFY_TARGETS, CONF_MEDIA_PLAYERS, CONF_TTS_ENGINE, CONF_AI_AGENT):
            fields[field(key, value[key])] = select(options[key], multiple=key in multi)
            if key in ("general_occupied_rooms_entity", "general_sleep_rooms_entity"):
                attr_key = key.removesuffix("entity") + "attribute"
                # Offer the union of relevant attributes from all room-list
                # candidates so entity + attribute can be chosen on this one page.
                attrs_by_value = {"__state__": {"value": "__state__", "label": "State"}}
                for candidate in options[key]:
                    entity_id = candidate["value"]
                    if entity_id == "none":
                        continue
                    for option in self._room_attribute_options(self.hass, entity_id):
                        attrs_by_value.setdefault(option["value"], option)
                attrs = list(attrs_by_value.values())
                chosen = value[attr_key] if value[attr_key] in attrs_by_value else "__state__"
                fields[field(attr_key, chosen)] = select(attrs)
        fields[field("general_away_cooldown_minutes", value["general_away_cooldown_minutes"])] = (
            selector.NumberSelector(selector.NumberSelectorConfig(
                min=0, max=240, step=1, unit_of_measurement="min",
                mode=selector.NumberSelectorMode.BOX)))
        fields[field(CONF_LANGUAGE, value[CONF_LANGUAGE])] = select(language_choices)
        from .hub_delivery import hub_installed
        if hub_installed(self.hass):
            fields[field(CONF_HUB, value.get(CONF_HUB, False))] = selector.BooleanSelector()
        fields[field(CONF_USE_MOLD, value[CONF_USE_MOLD])] = selector.BooleanSelector()
        return self.async_show_form(step_id="setup_general", errors=errors, data_schema=probatio.Schema(fields))
