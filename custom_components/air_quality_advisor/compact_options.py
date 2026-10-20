"""Compact Home Environment Manager configuration pages.

Each page saves only its selected section. Device discovery never authorizes
physical actuation: a second, exact-entity per-device opt-in is mandatory.
The legacy advanced controllers and their persisted keys stay compatible.
"""
from __future__ import annotations

import math
from typing import Any

import probatio
from homeassistant.helpers import selector

from .const import (
    CONF_AREAS, CONF_CLIMATE_ROOMS, CONF_ENVIRONMENT_GLOBAL,
    CONF_ENVIRONMENT_ROOMS, CONF_OCCUPANCY_GLOBAL, CONF_OUTDOOR,
)
from .discovery import entity_area, indoor_temperature_choices, supported_metric


def _field(key: str, default: Any = None, *, required: bool = False):
    form = probatio.Required if required else probatio.Optional
    return form(key, default=default) if default is not None else form(key)


def _select(values, *, multi=False, translation_key=None):
    options = dict(options=values, multiple=multi, custom_value=False,
                   mode=selector.SelectSelectorMode.DROPDOWN)
    if translation_key:
        options["translation_key"] = translation_key
    return selector.SelectSelector(selector.SelectSelectorConfig(**options))


def _number(lower: float, upper: float, step: float = 1):
    return selector.NumberSelector(selector.NumberSelectorConfig(
        min=lower, max=upper, step=step,
        mode=selector.NumberSelectorMode.BOX,
    ))


def _device_choices(hass, area: str) -> list[dict[str, str]]:
    """Only real native domains; never autodiscover arbitrary smart plugs."""
    results = []
    for state in hass.states.async_all():
        if state.domain not in ("climate", "humidifier", "fan"):
            continue
        if entity_area(hass, state.entity_id) != area:
            continue
        # Device class can be missing from an otherwise valid Home Assistant
        # humidifier entity. It remains visible for INVENTORY, but must
        # report its actual supported class before automatic device control.
        if state.domain == "climate" and not isinstance(
            state.attributes.get("hvac_modes"), (list, tuple)
        ):
            continue
        results.append({"value": state.entity_id,
                        "label": (state.name or state.entity_id) + " · " + state.entity_id})
    return sorted(results, key=lambda item: item["label"].casefold())


def _sensor_choices(hass, area: str, metric: str) -> list[dict[str, str]]:
    if metric == "temperature":
        return indoor_temperature_choices(hass, area)
    return sorted((
        {"value": s.entity_id, "label": (s.name or s.entity_id)}
        for s in hass.states.async_all("sensor")
        if entity_area(hass, s.entity_id) == area
        and supported_metric(hass, s, outdoor=False) == metric
    ), key=lambda item: item["label"].casefold())


def _device_type(entity: str) -> str:
    return entity.split(".", 1)[0]


def _valid_temperature(value: Any, low=5, high=40) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return f if math.isfinite(f) and low <= f <= high else None


class CompactOptionsMixin:
    """Used by the existing config/options flow; no migrations or broadcasts."""

    async def async_step_outside_data(self, user_input=None):
        return self.async_show_menu(
            step_id="outside_data",
            menu_options=["weather", "outdoor", "outside_aqi", "pollen"],
        )

    async def async_step_area_settings(self, user_input=None):
        return self.async_show_menu(
            step_id="area_settings",
            menu_options=[
                "areas", "indoor_sensors", "window_sensors", "environment_room",
                "climate", "pid", "area_devices",
            ],
        )

    def _general_area_ids(self):
        from homeassistant.helpers import area_registry
        registry = area_registry.async_get(self.hass)
        areas = set(self._values.get(CONF_AREAS, []) or [])
        climates = self._values.get(CONF_CLIMATE_ROOMS, {})
        if isinstance(climates, dict):
            areas.update(climates)
        if hasattr(registry, "async_list_areas"):
            areas.update(area.id for area in registry.async_list_areas()
                         if isinstance(getattr(area, "id", None), str))
        return {area for area in areas if isinstance(area, str) and area}

    async def async_step_general_settings(self, user_input=None):
        """First select usable source ENTITIES; next page selects their fields.

        Home Assistant does not dynamically update dependent selectors while
        a config form is open. A second page safely enumerates actual current
        attribute names only after each entity has been selected.
        """
        from .occupancy_policy import room_list_entities
        saved = self._values.get(CONF_OCCUPANCY_GLOBAL, {})
        saved = dict(saved) if isinstance(saved, dict) else {}
        areas = self._general_area_ids()
        source_choices = room_list_entities(
            self.hass, areas,
            (saved.get("occupied_rooms_entity"), saved.get("sleep_rooms_entity"))
        )
        source_ids = {option["value"] for option in source_choices}
        source_choices = [{"value": "none", "label": "—"}] + source_choices
        room_sensors = sorted([
            {"value": st.entity_id, "label": st.name or st.entity_id}
            for st in self.hass.states.async_all("binary_sensor")
            if str(st.attributes.get("device_class","")).casefold()
               in ("presence","occupancy") and st.state in ("on","off")
        ], key=lambda row: row["label"].casefold())
        tracker_opts = sorted([
            {"value": st.entity_id, "label": st.name or st.entity_id}
            for st in self.hass.states.async_all()
            if (
                st.domain in ("person","device_tracker")
                and isinstance(st.state,str)
                and st.state not in ("unknown","unavailable","none","")
            ) or (
                st.domain == "binary_sensor"
                and str(st.attributes.get("device_class","")).casefold()
                  in ("presence","occupancy") and st.state in ("on","off")
            )
        ], key=lambda row: row["label"].casefold())
        errors = {}
        if user_input is not None:
            selected = user_input.get("general_room_occupancy_sensors",
                                      saved.get("room_occupancy_sensors", []))
            people = user_input.get("general_home_trackers",
                                    saved.get("home_trackers", []))
            occupancy = user_input.get("general_occupied_rooms_entity",
                                       saved.get("occupied_rooms_entity")) or "none"
            sleep = user_input.get("general_sleep_rooms_entity",
                                   saved.get("sleep_rooms_entity")) or "none"
            stale = user_input.get("general_source_stale_minutes",
                                   saved.get("source_stale_minutes", 240))
            policy = user_input.get("general_home_policy",
                                    saved.get("home_policy", "any_home"))
            try:
                age = float(stale)
            except (ValueError, TypeError, OverflowError):
                age = float("nan")
            if (not isinstance(selected, list) or
                any(x not in {s["value"] for s in room_sensors} for x in selected)):
                errors["base"] = "general_invalid_presence"
            elif (not isinstance(people, list) or
                  any(x not in {s["value"] for s in tracker_opts} for x in people)):
                errors["base"] = "general_invalid_trackers"
            elif any(x not in source_ids | {"none"} for x in (occupancy,sleep)):
                errors["base"] = "general_invalid_rooms_entity"
            elif policy not in ("any_home","all_home"):
                errors["base"] = "general_invalid_presence"
            elif not math.isfinite(age) or not 10 <= age <= 1440:
                errors["base"] = "general_invalid_source_age"
            else:
                self._general_pending = {
                    **saved,
                    "room_occupancy_sensors": list(dict.fromkeys(selected)),
                    "home_trackers": list(dict.fromkeys(people)),
                    "occupied_rooms_entity": None if occupancy=="none" else occupancy,
                    "sleep_rooms_entity": None if sleep=="none" else sleep,
                    "home_policy": policy,
                    "source_stale_minutes": age,
                }
                # Always let the user review the extracted State/attribute
                # choices before saving. No old free-text attribute survives
                # a changed source without validation.
                return await self.async_step_general_sources()
        fields = {
            _field("general_room_occupancy_sensors",saved.get("room_occupancy_sensors",[])):
                _select(room_sensors,multi=True),
            _field("general_occupied_rooms_entity",
                   saved.get("occupied_rooms_entity") or "none"):
                _select(source_choices),
            _field("general_home_trackers",saved.get("home_trackers",[])):
                _select(tracker_opts,multi=True),
            _field("general_home_policy",saved.get("home_policy","any_home")):
                _select(["any_home","all_home"],translation_key="general_home_policy"),
            _field("general_sleep_rooms_entity",
                   saved.get("sleep_rooms_entity") or "none"):
                _select(source_choices),
            _field("general_source_stale_minutes",saved.get("source_stale_minutes",240)):
                _number(10,1440),
        }
        return self.async_show_form(step_id="general_settings",
                                    errors=errors,data_schema=probatio.Schema(fields))

    async def async_step_general_sources(self, user_input=None):
        """Show only valid State/attribute choices for each chosen entity."""
        from .occupancy_policy import room_list_fields, ROOM_STATE_VALUE
        pending = getattr(self, "_general_pending", None)
        if not isinstance(pending, dict):
            return await self.async_step_general_settings()
        prior = self._values.get(CONF_OCCUPANCY_GLOBAL,{})
        prior = prior if isinstance(prior,dict) else {}
        areas = self._general_area_ids()
        definitions = (
            ("occupied_rooms_entity","occupied_rooms_attribute",
             "general_occupied_rooms_attribute"),
            ("sleep_rooms_entity","sleep_rooms_attribute",
             "general_sleep_rooms_attribute"),
        )
        options = {}
        errors = {}
        for entity_key, attr_key, field in definitions:
            entity = pending.get(entity_key)
            if not entity:
                pending[attr_key] = ""
                continue
            possible = room_list_fields(self.hass, entity, areas)
            choices = {opt["value"] for opt in possible}
            if not choices:
                errors["base"] = "general_invalid_rooms_entity"
            default = (prior.get(attr_key) if prior.get(entity_key)==entity
                       else None) or ROOM_STATE_VALUE
            if default not in choices and choices:
                default = possible[0]["value"]
            options[field] = (possible, default, choices, attr_key)
        if user_input is not None and not errors:
            for field, (_, default, choices, attr_key) in options.items():
                value = user_input.get(field, default)
                if value not in choices:
                    errors["base"] = "general_invalid_attribute"
                else:
                    pending[attr_key] = "" if value==ROOM_STATE_VALUE else value
            if not errors:
                self._values[CONF_OCCUPANCY_GLOBAL] = pending
                self._general_pending = None
                return await self._finish()
        fields = {
            _field(field, default, required=True): _select(possible)
            for field, (possible, default, _, _) in options.items()
            if possible
        }
        if not fields and not errors:
            # No source entity was selected. Preserve other general settings.
            self._values[CONF_OCCUPANCY_GLOBAL] = pending
            self._general_pending = None
            return await self._finish()
        return self.async_show_form(step_id="general_sources",
                                    data_schema=probatio.Schema(fields),errors=errors)

    async def async_step_pollen(self, user_input=None):
        """Dedicated, robust pollen editor: no dynamic AQI selectors."""
        data = self._values.get(CONF_ENVIRONMENT_GLOBAL, {})
        current = dict(data) if isinstance(data, dict) else {}
        pollen_sources = []
        for st in self.hass.states.async_all("sensor"):
            try:
                value = float(st.state)
            except (ValueError, TypeError, OverflowError):
                continue
            if math.isfinite(value) and 0 <= value <= 100000:
                pollen_sources.append({"value": st.entity_id,
                                       "label": (st.name or st.entity_id) + " · " + st.entity_id})
        pollen_sources = sorted(pollen_sources,key=lambda x:x["label"].casefold())
        errors = {}
        if user_input is not None:
            source = user_input.get("pollen_entity", current.get("pollen_entity"))
            try:
                threshold = float(user_input.get("pollen_high_from", current.get("pollen_high_from", 3)))
                maximum = float(user_input.get("pollen_max_scale", current.get("pollen_max_scale", 5)))
            except (TypeError, ValueError, OverflowError):
                threshold, maximum = float("nan"), float("nan")
            if source and source != "none" and source not in {
                row["value"] for row in pollen_sources
            }:
                errors["base"] = "invalid_environment_scale"
            elif not all(math.isfinite(v) for v in (threshold, maximum)) or not (
                0 <= threshold <= maximum <= 100
            ):
                errors["base"] = "invalid_environment_scale"
            else:
                current.update({
                    "pollen_entity": None if source in (None, "none") else source,
                    "pollen_high_from": threshold,
                    "pollen_max_scale": maximum,
                    "pollen_avoid_ventilation": user_input.get(
                        "pollen_avoid_ventilation",
                        current.get("pollen_avoid_ventilation", False),
                    ) is True,
                })
                self._values[CONF_ENVIRONMENT_GLOBAL] = current
                return await self._finish()
        fields = {
            _field("pollen_entity", current.get("pollen_entity") or "none"):
                _select([{"value":"none","label":"—"}]+pollen_sources),
            _field("pollen_high_from", current.get("pollen_high_from", 3)): _number(0, 100, .1),
            _field("pollen_max_scale", current.get("pollen_max_scale", 5)): _number(1, 100, .1),
            _field("pollen_avoid_ventilation", current.get("pollen_avoid_ventilation", False)):
                selector.BooleanSelector(),
        }
        return self.async_show_form(
            step_id="pollen", errors=errors, data_schema=probatio.Schema(fields)
        )

    async def async_step_outside_aqi(self, user_input=None):
        """One explicit AQI source at a time; no untranslatable indexed keys."""
        current = self._values.get(CONF_ENVIRONMENT_GLOBAL, {})
        current = dict(current) if isinstance(current, dict) else {}
        saved = current.get("aqi_scales", {})
        saved = dict(saved) if isinstance(saved, dict) else {}
        selected = self._values.get(CONF_OUTDOOR, [])
        selected = selected if isinstance(selected, list) else []
        aqis = [
            e for e in selected if isinstance(e, str) and e.startswith("sensor.")
            and (st := self.hass.states.get(e)) is not None and (
                str(st.attributes.get("device_class", "")).casefold() == "aqi"
                or e.endswith(("_aqi", "_air_quality_index"))
            )
        ]
        errors = {}
        chosen = (user_input or {}).get("outside_aqi_entity") or (aqis[0] if aqis else "none")
        details = saved.get(chosen, {})
        details = details if isinstance(details, dict) else {}
        if user_input is not None:
            scale = user_input.get("outside_aqi_scale", details.get("scale", "not_configured"))
            try:
                limit = float(user_input.get("outside_aqi_limit", details.get("custom_limit", 100)))
            except (ValueError, TypeError, OverflowError):
                limit = float("nan")
            if not aqis:
                return await self._finish()
            if chosen not in aqis or scale not in (
                "not_configured", "us_epa", "eea_category", "custom"
            ) or (scale=="custom" and (not math.isfinite(limit) or
                                       not 0 <= limit <= 10000)):
                errors["base"] = "invalid_environment_scale"
            else:
                if scale == "not_configured":
                    saved.pop(chosen, None)
                else:
                    saved[chosen] = {"scale": scale, **(
                        {"custom_limit": limit} if scale == "custom" else {})}
                self._values[CONF_ENVIRONMENT_GLOBAL] = {**current, "aqi_scales": saved}
                return await self._finish()
        fields = {}
        if aqis:
            fields[_field("outside_aqi_entity", chosen, required=True)] = _select([
                {"value":e,"label":e} for e in aqis])
            fields[_field("outside_aqi_scale", details.get("scale","not_configured"))] = _select([
                "not_configured","us_epa","eea_category","custom"],
                translation_key="outside_aqi_scale")
            fields[_field("outside_aqi_limit",details.get("custom_limit",100))] = _number(0,10000)
        else:
            fields[_field("outside_aqi_no_sources", False)] = selector.BooleanSelector()
        return self.async_show_form(
            step_id="outside_aqi", data_schema=probatio.Schema(fields),
            errors=errors, description_placeholders={"aqi_entities":", ".join(aqis) or "—"}
        )

    def _device_areas(self):
        from homeassistant.helpers import area_registry
        registry = area_registry.async_get(self.hass)
        areas = {a for a in self._values.get(CONF_AREAS, []) if isinstance(a, str)}
        old = self._values.get(CONF_CLIMATE_ROOMS, {})
        if isinstance(old, dict):
            areas.update(old)
        for state in self.hass.states.async_all():
            if state.domain in ("climate", "humidifier", "fan"):
                if area := entity_area(self.hass, state.entity_id):
                    areas.add(area)
        return [
            {"value": a, "label": getattr(registry.async_get_area(a), "name", a)}
            for a in sorted(areas)
            if registry.async_get_area(a) is not None
        ]

    async def async_step_area_devices(self, user_input=None):
        """Pick a real HA area before selecting supported native equipment."""
        rooms = self._device_areas()
        if not rooms:
            return await self._finish()
        errors = {}
        if user_input is not None:
            area = user_input.get("area_devices_area")
            if area in {r["value"] for r in rooms}:
                self._climate_area = area
                saved = self._values.get(CONF_CLIMATE_ROOMS, {})
                self._climate_draft = dict(saved.get(area, {})) if isinstance(saved, dict) else {}
                return await self.async_step_select_devices()
            errors["base"] = "invalid_areas"
        return self.async_show_form(step_id="area_devices", errors=errors,
            data_schema=probatio.Schema({
                _field("area_devices_area", rooms[0]["value"], required=True): _select(rooms)
            }))

    async def async_step_select_devices(self, user_input=None):
        """Auto-select ALL supported room devices the first time, without activating any."""
        choices = _device_choices(self.hass, self._climate_area)
        available = {c["value"] for c in choices}
        draft = self._climate_draft
        old = draft.get("selected_devices")
        default = [v for v in old if v in available] if isinstance(old, list) else [
            c["value"] for c in choices
        ]
        errors = {}
        if user_input is not None:
            devices = user_input.get("selected_devices", default)
            if not isinstance(devices, list) or any(d not in available for d in devices):
                errors["base"] = "invalid_selected_devices"
            else:
                draft["selected_devices"] = list(dict.fromkeys(devices))
                # Preserve old preferences, but no unselected actuator may be
                # scheduled from a historic climate role assignment.
                self._climate_draft = draft
                if devices:
                    return await self.async_step_device_choice()
                return await self._save_devices()
        return self.async_show_form(
            step_id="select_devices", errors=errors,
            data_schema=probatio.Schema({
                _field("selected_devices", default): _select(choices, multi=True)
            }), description_placeholders={"area_name":self._climate_area}
        )

    async def async_step_device_choice(self, user_input=None):
        area = self._climate_area
        current = self._climate_draft
        ids = [v for v in current.get("selected_devices", [])
               if self.hass.states.get(v) is not None and entity_area(self.hass,v)==area]
        if not ids:
            return await self._save_devices()
        options = [{"value":e,"label":(self.hass.states.get(e).name or e)+" · "+e}
                   for e in ids]
        errors = {}
        if user_input is not None:
            device = user_input.get("device_choice")
            if device in ids:
                self._device_entity = device
                return await self.async_step_device_menu()
            errors["base"] = "invalid_selected_devices"
        return self.async_show_form(
            step_id="device_choice", errors=errors,
            data_schema=probatio.Schema({
                _field("device_choice", ids[0], required=True): _select(options)
            })
        )

    async def async_step_device_menu(self, user_input=None):
        return self.async_show_menu(
            step_id="device_menu",
            menu_options=["device_settings", "device_choice", "device_done"],
            description_placeholders={"device_name":self._device_entity},
        )

    async def async_step_device_done(self, user_input=None):
        return await self._save_devices()

    async def _save_devices(self):
        rooms = self._values.get(CONF_CLIMATE_ROOMS, {})
        result = dict(rooms) if isinstance(rooms, dict) else {}
        result[self._climate_area] = dict(self._climate_draft)
        self._values[CONF_CLIMATE_ROOMS] = result
        return await self._finish()

    async def async_step_device_settings(self, user_input=None):
        entity = self._device_entity
        area = self._climate_area
        state = self.hass.states.get(entity)
        if (state is None or entity_area(self.hass, entity) != area or
                entity not in self._climate_draft.get("selected_devices", [])):
            return await self.async_step_select_devices()
        draft = self._climate_draft
        options = draft.get("device_settings", {})
        options = dict(options) if isinstance(options, dict) else {}
        old = options.get(entity, {})
        old = dict(old) if isinstance(old, dict) else {}
        domain = _device_type(entity)
        errors = {}
        kind = (old.get("method") or ("setpoint" if domain != "fan" else "speed"))
        if user_input is not None:
            data = {
                **old, "auto_control": user_input.get("device_auto_control", old.get("auto_control", False)) is True,
                "presence_requirement": user_input.get("device_presence_requirement", old.get("presence_requirement", "always")),
                "absence_action": user_input.get("device_absence_action", old.get("absence_action", "hold")),
                "sleep_behavior": user_input.get("device_sleep_behavior", old.get("sleep_behavior", "normal")),
                "method": user_input.get("device_method", kind),
                "hardware_confirmed": user_input.get("device_hardware_confirmed",
                                                      old.get("hardware_confirmed", False)) is True,
            }
            for profile in ("home", "unoccupied", "away", "sleep"):
                for hvac in ("heat", "cool"):
                    key = f"{profile}_{hvac}_c"
                    data[key] = user_input.get("device_"+key, old.get(key, {
                        "home":(20,26), "unoccupied":(18,28),
                        "away":(16,30), "sleep":(18,26),
                    }[profile][0 if hvac == "heat" else 1]))
            for key in ("temperature_entity", "humidity_entity", "co2_entity",
                        "pm25_entity", "fan_purpose"):
                data[key] = user_input.get("device_"+key, old.get(key))
            for key, default in (("humidity_target", 50), ("sleep_humidity_target", 50),
                                 ("min_on_s", 600), ("min_off_s", 600), ("max_on_s", 7200),
                                 ("fan_speed_percent", 60)):
                data[key] = user_input.get("device_"+key, old.get(key, default))
            data["sensor_verified"] = user_input.get(
                "device_sensor_verified", old.get("sensor_verified", False)) is True
            if domain=="humidifier" and data["auto_control"]:
                h=_valid_temperature(data["humidity_target"],20,80)
                sh=_valid_temperature(data["sleep_humidity_target"],20,80)
                if h is None or sh is None:
                    errors["base"]="device_humidity_invalid"
            if (data["presence_requirement"] not in ("always", "room", "home") or
                data["absence_action"] not in ("hold", "off") or
                data["sleep_behavior"] not in ("normal", "pause", "sleep_targets") or
                (data["absence_action"] == "off" and
                 data["presence_requirement"] == "always")):
                errors["base"] = "device_policy_invalid"
            if data["auto_control"]:
                # A discovered entity is not necessarily capable of safely
                # implementing a chosen control mode. Validate actual HA
                # features before turning on the independent driver opt-in.
                if domain=="humidifier" and state.attributes.get("device_class") not in (
                    "humidifier","dehumidifier"
                ):
                    errors["base"]="device_hardware_required"
                elif domain == "climate" and data["method"] not in ("setpoint", "native"):
                    errors["base"] = "device_method_invalid"
                elif domain == "climate" and data["method"] == "native" and (
                     not data["hardware_confirmed"]):
                    errors["base"] = "device_hardware_required"
                elif domain == "climate" and not (set(
                    state.attributes.get("hvac_modes", ())
                    if isinstance(state.attributes.get("hvac_modes"), (tuple,list))
                    else ()
                ) & {"heat","cool","heat_cool"}):
                    # A DRY-only native climate can be monitored and advised
                    # but cannot accept fabricated temperature targets here.
                    # Its compressor-mode driver is separately commissioned.
                    errors["base"]="device_method_invalid"
                elif domain in ("humidifier","fan") and data["method"] not in (
                    "setpoint","power","speed"):
                    errors["base"] = "device_method_invalid"
                elif data["method"] == "power" and not data["hardware_confirmed"]:
                    errors["base"] = "device_hardware_required"
                elif (data["absence_action"] == "off" and domain == "climate"
                      and not data["hardware_confirmed"]):
                    errors["base"] = "device_hardware_required"
                elif (data["absence_action"] == "off" and domain in ("fan", "humidifier")
                      and data["method"] != "power"):
                    errors["base"] = "device_power_required_for_off"
                elif domain == "climate" and (
                    not isinstance(data["temperature_entity"], str) or
                    data["temperature_entity"] not in {
                        s["value"] for s in _sensor_choices(self.hass,area,"temperature")
                    }):
                    from .climate_equipment import classify_hvac
                    capability=classify_hvac(state.attributes,state.state)
                    if capability.get("drying") and not (
                        capability.get("heating") or capability.get("cooling")
                    ):
                        errors["base"] = "device_dry_advisory_only"
                    else:
                        errors["base"] = "device_temperature_required"
                elif domain == "humidifier" and data["humidity_entity"] not in {
                    s["value"] for s in _sensor_choices(self.hass,area,"humidity")
                }:
                    errors["base"] = "device_humidity_required"
                elif domain == "fan" and (
                    data["fan_purpose"] not in ("extraction", "filtration") or
                    data["co2_entity" if data["fan_purpose"]=="extraction" else "pm25_entity"]
                    not in {s["value"] for s in _sensor_choices(
                        self.hass,area,"co2" if data["fan_purpose"]=="extraction" else "pm25"
                    )} or not data["sensor_verified"]
                ):
                    errors["base"] = "device_air_sensor_required"
                if not errors and domain=="climate":
                    for profile in ("home", "unoccupied", "away", "sleep"):
                        heat = _valid_temperature(data[f"{profile}_heat_c"],5,35)
                        cool = _valid_temperature(data[f"{profile}_cool_c"],6,40)
                        if heat is None or cool is None or cool-heat<1:
                            errors["base"] = "device_temperature_band_invalid"
                            break
            # The older fan and humidity power controllers are coordinated
            # by room. Enabling a second independent controller for the same
            # role would silently overwrite the first one's permissions.
            # Require the user to deselect the old automatic owner first.
            if data["auto_control"] and not errors:
                for other_entity,other in options.items():
                    if other_entity==entity or not isinstance(other,dict) or not other.get("auto_control"):
                        continue
                    if _device_type(other_entity)==domain and domain=="humidifier":
                        if (other.get("method")!=data["method"] or
                            other_entity==entity):
                            errors["base"]="device_conflicting_control"
                    if _device_type(other_entity)==domain and domain=="fan":
                        if (other.get("method")!=data["method"]):
                            errors["base"]="device_conflicting_control"
            if not errors and data["auto_control"] and data["method"] == "power":
                minimum = _valid_temperature(data["min_on_s"],60,7200)
                off = _valid_temperature(data["min_off_s"],60,7200)
                maximum = _valid_temperature(data["max_on_s"],300,86400)
                if minimum is None or off is None or maximum is None or maximum < minimum:
                    errors["base"] = "device_runtime_invalid"
            if not errors and data["auto_control"] and domain in ("fan","humidifier"):
                # One controller method per room/device domain. The current
                # native backend cannot simultaneously own fan-power and fan-
                # speed (or humidity-power and humidity-setpoint) in one room.
                for another,configured in options.items():
                    if another==entity or another.split(".",1)[0]!=domain:
                        continue
                    if not isinstance(configured,dict) or configured.get("auto_control") is not True:
                        continue
                    if configured.get("method")!=data["method"] or (
                        domain=="fan" and configured.get("fan_purpose")==data["fan_purpose"]
                    ):
                        errors["base"]="device_policy_invalid"
                        break
            if not errors:
                options[entity] = data
                draft["device_settings"] = options
                # Role assignment is exact, with no implied compressor switching.
                if data["auto_control"]:
                    draft["enabled"] = True
                    draft["allow_actuation"] = True
                    if domain == "climate":
                        from .climate_equipment import classify_hvac
                        modes = classify_hvac(state.attributes, state.state)
                        draft["temperature_entity"] = data["temperature_entity"]
                        if not draft.get("climate_entity") or draft["climate_entity"] == entity:
                            draft["climate_entity"] = entity
                            draft["controller"] = "device"
                            draft["auto_switch_hvac"] = (data["method"] == "native"
                                                          and data["hardware_confirmed"])
                            draft["mode"] = ("auto" if (
                                modes.get("heating") or modes.get("cooling")
                            ) else "dry")
                        elif modes.get("heating"):
                            draft["heat_climate_entity"] = entity
                            draft["secondary_climate_setpoint_auto"] = True
                        elif modes.get("cooling"):
                            draft["cool_climate_entity"] = entity
                            draft["secondary_climate_setpoint_auto"] = True
                        elif modes.get("drying"):
                            draft["dry_climate_entity"] = entity  # Advisory until hardware commissioned
                    elif domain == "humidifier":
                        draft["controller"] = draft.get("controller", "environment")
                        draft["humidity_entity"] = data["humidity_entity"]
                        role = ("dehumidifier_entity" if
                                state.attributes.get("device_class") == "dehumidifier"
                                else "humidifier_entity")
                        draft[role] = entity
                        draft["humidity_setpoint_auto"] = data["method"] == "setpoint"
                        draft["humidity_power_auto"] = data["method"] == "power"
                        draft["humidity_power_hardware_confirmed"] = data["hardware_confirmed"]
                        for dest in ("min_on_s", "min_off_s", "max_on_s"):
                            draft["humidity_power_"+dest] = data[dest]
                    elif domain == "fan":
                        draft["controller"] = draft.get("controller", "environment")
                        role = ("extraction_fan_entity" if data["fan_purpose"]=="extraction"
                                else "purifier_fan_entity")
                        draft[role] = entity
                        draft["fan_speed_auto"] = data["method"] == "speed"
                        draft["fan_power_auto"] = data["method"] == "power"
                        draft["fan_power_hardware_confirmed"] = data["hardware_confirmed"]
                        draft["co2_entity"] = data["co2_entity"]
                        draft["pm25_entity"] = data["pm25_entity"]
                        draft["pm25_sensor_verified"] = data["sensor_verified"]
                        draft[data["fan_purpose"]+"_speed_percent"] = data["fan_speed_percent"]
                        for dest in ("min_on_s", "min_off_s", "max_on_s"):
                            draft["fan_power_"+dest] = data[dest]
                        if data["fan_purpose"]=="extraction":
                            env_rooms = self._values.get(CONF_ENVIRONMENT_ROOMS,{})
                            env_rooms = dict(env_rooms) if isinstance(env_rooms,dict) else {}
                            info = dict(env_rooms.get(area,{}) or {})
                            info["co2_ndir_verified"] = data["sensor_verified"]
                            env_rooms[area] = info
                            self._values[CONF_ENVIRONMENT_ROOMS] = env_rooms
                self._climate_draft = draft
                return await self._save_devices()

        fields = {
            _field("device_auto_control", old.get("auto_control", False)): selector.BooleanSelector(),
            _field("device_method", kind):
                _select(["setpoint", "native"] if domain=="climate" else
                        ["setpoint", "power"] if domain=="humidifier" else
                        ["speed","power"],translation_key="device_method"),
            _field("device_presence_requirement", old.get("presence_requirement","always")):
                _select(["always","room","home"],translation_key="device_presence_requirement"),
            _field("device_absence_action", old.get("absence_action","hold")):
                _select(["hold","off"],translation_key="device_absence_action"),
            _field("device_sleep_behavior", old.get("sleep_behavior","normal")):
                _select(["normal","pause","sleep_targets"],translation_key="device_sleep_behavior"),
            _field("device_hardware_confirmed", old.get("hardware_confirmed",False)):
                selector.BooleanSelector(),
        }
        if domain == "climate":
            temp = _sensor_choices(self.hass,area,"temperature")
            fields[_field("device_temperature_entity",
                          old.get("temperature_entity") or draft.get("temperature_entity"))] = _select(temp)
            for profile in ("home","unoccupied","away","sleep"):
                for mode,initial in (("heat",{"home":20,"unoccupied":18,
                                             "away":16,"sleep":18}[profile]),
                                     ("cool",{"home":26,"unoccupied":28,
                                             "away":30,"sleep":26}[profile])):
                    k=f"{profile}_{mode}_c"
                    fields[_field("device_"+k,old.get(k,initial))]=_number(5,40,.5)
        elif domain == "humidifier":
            fields[_field("device_humidity_entity",
                          old.get("humidity_entity") or draft.get("humidity_entity"))] = _select(
                              _sensor_choices(self.hass,area,"humidity"))
            fields[_field("device_humidity_target",old.get("humidity_target",50))]=_number(20,80)
            fields[_field("device_sleep_humidity_target",old.get("sleep_humidity_target",50))]=_number(20,80)
        else:
            fields[_field("device_fan_purpose",old.get("fan_purpose","extraction"))]=_select(
                ["extraction","filtration"],translation_key="device_fan_purpose")
            fields[_field("device_co2_entity",old.get("co2_entity"))]=_select(
                [{"value":"none","label":"—"}]+_sensor_choices(self.hass,area,"co2"))
            fields[_field("device_pm25_entity",old.get("pm25_entity"))]=_select(
                [{"value":"none","label":"—"}]+_sensor_choices(self.hass,area,"pm25"))
            fields[_field("device_sensor_verified",old.get("sensor_verified",False))]=selector.BooleanSelector()
            fields[_field("device_fan_speed_percent",old.get("fan_speed_percent",60))]=_number(10,100)
        if domain in ("fan","humidifier"):
            for k,d in (("min_on_s",600),("min_off_s",600),("max_on_s",7200)):
                fields[_field("device_"+k,old.get(k,d))]=_number(
                    60 if k!="max_on_s" else 300,
                    7200 if k!="max_on_s" else 86400)
        return self.async_show_form(
            step_id="device_settings", errors=errors, data_schema=probatio.Schema(fields),
            description_placeholders={"device_name":state.name or entity,
                                      "device_entity":entity, "area_name":area},
        )
