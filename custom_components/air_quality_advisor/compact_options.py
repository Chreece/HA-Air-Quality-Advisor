"""Compact Home Environment Manager configuration pages.

Each page saves only its selected section. Device discovery never authorizes
physical actuation: a second, exact-entity per-device opt-in is mandatory.
The legacy advanced controllers and their persisted keys stay compatible.
"""
from __future__ import annotations

from .config_data import mutable_copy as deepcopy
import math
from typing import Any

import probatio
from homeassistant.helpers import selector

from .const import (
    CONF_AREAS, CONF_CLIMATE_ROOMS, CONF_PID_ROOMS, CONF_EXCLUDED_INDOOR, CONF_ENVIRONMENT_GLOBAL,
    CONF_ENVIRONMENT_ROOMS, CONF_OCCUPANCY_GLOBAL, CONF_OUTDOOR,
)
from .discovery import entity_area, indoor_temperature_choices, supported_metric
from .device_hierarchy import configured_sources, native_source


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
        if entity_area(hass, state.entity_id) != area or not native_source(hass, state.entity_id):
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


# A device unselected in the area menu must not remain in the room's
# actuator roles. These names are also the ones used by the live drivers.
_MANAGED_DEVICE_ROLES = (
    "climate_entity", "heat_climate_entity", "cool_climate_entity",
    "dry_climate_entity", "fan_climate_entity",
    "humidifier_entity", "dehumidifier_entity",
    "extraction_fan_entity", "purifier_fan_entity",
)


def _reconcile_device_selection(previous: dict, updated: dict) -> dict:
    """Revoke abandoned per-device grants without changing unrelated options.

    Retain a device's saved preferences for later re-selection, but never keep
    its live auto_control flag or room-wide actuator assignment after it has
    been explicitly removed or disabled. Existing advanced-only settings stay
    untouched when the selection has not changed.
    """
    old = previous if isinstance(previous, dict) else {}
    result = dict(updated)
    raw = result.get("selected_devices", [])
    selected = set(raw) if isinstance(raw, list) else set()
    prior = old.get("device_settings", {})
    prior = prior if isinstance(prior, dict) else {}
    saved = result.get("device_settings", {})
    saved = saved if isinstance(saved, dict) else {}
    devices = {name: dict(cfg) for name, cfg in saved.items()
               if isinstance(name, str) and isinstance(cfg, dict)}

    previously_selected = old.get("selected_devices")
    if isinstance(previously_selected, list):
        revoked = set(previously_selected) - selected
    elif "selected_devices" in result:
        # First use of the picker: omitting an existing room actuator is an
        # explicit de-selection even for advanced configurations.
        revoked = {old.get(key) for key in _MANAGED_DEVICE_ROLES
                   if isinstance(old.get(key), str) and old[key] not in selected}
    else:
        revoked = set()

    for entity, cfg in prior.items():
        if not isinstance(cfg, dict) or cfg.get("auto_control") is not True:
            continue
        current = devices.get(entity, {})
        if entity not in selected or current.get("auto_control") is not True:
            revoked.add(entity)
    for entity, cfg in devices.items():
        if entity not in selected:
            cfg["auto_control"] = False
    result["device_settings"] = devices

    if not revoked:
        return result
    for entity in revoked:
        devices.setdefault(entity, {})["auto_control"] = False
    for role in _MANAGED_DEVICE_ROLES:
        if result.get(role) in revoked:
            result.pop(role, None)
    if result.get("controller") == "device" and not result.get("climate_entity"):
        result["controller"] = "environment"
        result["auto_switch_hvac"] = False
    if not any(result.get(role) for role in
               ("heat_climate_entity", "cool_climate_entity")):
        result["secondary_climate_setpoint_auto"] = False
    if not any(result.get(role) for role in
               ("humidifier_entity", "dehumidifier_entity")):
        result["humidity_setpoint_auto"] = False
        result["humidity_power_auto"] = False
    if not any(result.get(role) for role in
               ("extraction_fan_entity", "purifier_fan_entity")):
        result["fan_speed_auto"] = False
        result["fan_power_auto"] = False

    native_primary = (result.get("controller") == "device" and
                      isinstance(result.get("climate_entity"), str))
    direct_primary = (result.get("controller") in ("on_off", "pwm", "proportional")
                      and result.get("direct_hardware_confirmed") is True
                      and any(result.get(k) for k in
                              ("heat_actuator", "cool_actuator")))
    secondary = any(result.get(k) is True for k in (
        "humidity_setpoint_auto", "humidity_power_auto",
        "secondary_climate_setpoint_auto", "fan_speed_auto",
        "fan_power_auto", "dry_fan_mode_auto",
    ))
    # A native DRY/FAN_ONLY controller deliberately does not arm a legacy
    # temperature or DRY/FAN driver. Removing unrelated equipment must not
    # revoke its already granted room permission; never create a new grant.
    managed_native = any(
        entity in selected and entity.startswith("climate.")
        and cfg.get("auto_control") is True
        and cfg.get("hardware_confirmed") is True
        and cfg.get("method") == "native"
        for entity, cfg in devices.items()
    )
    if not (native_primary or direct_primary or secondary or managed_native):
        result["allow_actuation"] = False
    return result


class CompactOptionsMixin:
    """Used by the existing config/options flow; no migrations or broadcasts."""

    async def async_step_outside_data(self, user_input=None):
        return self.async_show_menu(
            step_id="outside_data",
            menu_options=["weather", "outdoor", "pollen"],
        )

    async def async_step_area_settings(self, user_input=None):
        return self.async_show_menu(
            step_id="area_settings",
            menu_options=[
                "areas", "indoor_sensors", "window_sensors", "environment_room",
                "area_devices",
            ],
        )

    @staticmethod
    def _room_source_options(hass):
        from homeassistant.helpers import entity_registry as er
        from .room_sources import label, native
        from .occupancy_policy import _tokens, _area_aliases, _room_key
        from homeassistant.helpers import area_registry
        registry = area_registry.async_get(hass)
        known = set(getattr(registry, "areas", {})) or {
            entity_area(hass, s.entity_id) for s in hass.states.async_all()
            if entity_area(hass, s.entity_id)}
        aliases = _area_aliases(hass, known)
        def usable(value):
            parsed = _tokens(value)
            return parsed is not None and all(_room_key(v) in aliases for v in parsed)
        result = []
        for state in hass.states.async_all():
            if state.domain not in ("sensor", "binary_sensor", "input_text", "input_select") or not native(hass, state.entity_id):
                continue
            entry = er.async_get(hass).async_get(state.entity_id)
            template = getattr(entry, "platform", None) == "template"
            room_attribute = any(key in state.attributes for key in (
                "rooms", "areas", "occupied_rooms", "sleep_rooms", "sleeping_areas"))
            if not (template or room_attribute or state.domain in ("input_text", "input_select")
                    or any(usable(v) for v in (state.state, *state.attributes.values()))):
                continue
            result.append({"value": state.entity_id, "label": label(hass, state.entity_id)})
        return sorted(result, key=lambda item: (item["label"].casefold(), item["value"]))

    @staticmethod
    def _room_attribute_options(hass, entity):
        from homeassistant.helpers import area_registry, entity_registry as er
        from .occupancy_policy import _tokens, _area_aliases, _room_key
        state = hass.states.get(entity) if isinstance(entity, str) else None
        entry = er.async_get(hass).async_get(entity) if isinstance(entity, str) and "." in entity else None
        template = getattr(entry, "platform", None) == "template"
        registry = area_registry.async_get(hass)
        known = set(getattr(registry, "areas", {})) or {
            entity_area(hass, s.entity_id) for s in hass.states.async_all() if entity_area(hass, s.entity_id)}
        aliases = _area_aliases(hass, known)
        def usable(value):
            parsed = _tokens(value)
            return parsed is not None and all(_room_key(v) in aliases for v in parsed)
        language = str(getattr(getattr(hass, "config", None), "language", "en")).split("-")[0]
        state_name = {"el": "Κατάσταση", "de": "Zustand", "fr": "État", "es": "Estado"}.get(language, "State")
        values = []
        if state is None or template or usable(state.state):
            values.append({"value": "__state__", "label": state_name})
        ignored = {"friendly_name", "icon", "device_class", "unit_of_measurement", "state_class", "attribution"}
        for key, value in state.attributes.items() if state else ():
            if key.startswith("_") or key in ignored:
                continue
            if usable(value) or template or key in ("rooms", "areas", "occupied_rooms", "sleep_rooms", "sleeping_areas"):
                values.append({"value": key, "label": key})
        return values or [{"value": "__state__", "label": state_name}]

    async def async_step_general_settings(self, user_input=None):
        """Shared presence and sleep sources, independent of any HVAC device."""
        old = self._values.get(CONF_OCCUPANCY_GLOBAL, {})
        old = dict(old) if isinstance(old, dict) else {}
        old.update(getattr(self, "_general_source_draft", {}))
        room_sensors = sorted(
            [{"value": s.entity_id, "label": s.name or s.entity_id}
             for s in self.hass.states.async_all("binary_sensor")
             if str(s.attributes.get("device_class", "")).casefold()
                in ("occupancy", "presence")],
            key=lambda x: x["label"].casefold(),
        )
        trackers = sorted(
            [{"value": s.entity_id, "label": s.name or s.entity_id}
             for s in self.hass.states.async_all()
             if s.domain in ("person", "device_tracker") or
                (s.domain == "binary_sensor" and
                 str(s.attributes.get("device_class", "")).casefold()
                 in ("occupancy", "presence"))],
            key=lambda x: x["label"].casefold(),
        )
        source_options=[{"value":"none","label":"—"},
                        *self._room_source_options(self.hass)]
        source_ids={v["value"] for v in source_options if v["value"]!="none"}
        errors = {}
        if user_input is not None:
            selected = user_input.get("general_room_occupancy_sensors", old.get("room_occupancy_sensors", []))
            at_home = user_input.get("general_home_trackers", old.get("home_trackers", []))
            occupied_entity = user_input.get("general_occupied_rooms_entity", old.get("occupied_rooms_entity"))
            sleep_entity = user_input.get("general_sleep_rooms_entity", old.get("sleep_rooms_entity"))
            # The select supports explicit clearing, which HA's optional
            # SelectSelector cannot otherwise express reliably.
            if occupied_entity in (None, "", "none"):
                occupied_entity = None
            if sleep_entity in (None, "", "none"):
                sleep_entity = None
            occupancy_attr = (user_input.get("general_occupied_rooms_attribute",
                              old.get("occupied_rooms_attribute", "__state__")) or "__state__")
            sleep_attr = (user_input.get("general_sleep_rooms_attribute",
                         old.get("sleep_rooms_attribute", "__state__")) or "__state__")
            stale = user_input.get("general_source_stale_minutes", old.get("source_stale_minutes", 240))
            try:
                age = float(stale)
            except (TypeError, ValueError, OverflowError):
                age = float("nan")
            known = {s.entity_id for s in self.hass.states.async_all()}
            if (not isinstance(selected, list) or
                    any(v not in {s["value"] for s in room_sensors} for v in selected)):
                errors["base"] = "general_invalid_presence"
            elif (not isinstance(at_home, list) or
                  any(v not in {s["value"] for s in trackers} for v in at_home)):
                errors["base"] = "general_invalid_trackers"
            elif any(e and (e not in known or e not in source_ids)
                     for e in (occupied_entity, sleep_entity)):
                errors["base"] = "general_invalid_rooms_entity"
            elif any(attr not in {v["value"] for v in self._room_attribute_options(self.hass,entity)}
                     for entity,attr in ((occupied_entity,occupancy_attr),(sleep_entity,sleep_attr))
                     if entity and entity in (old.get("occupied_rooms_entity"),old.get("sleep_rooms_entity"))):
                errors["base"] = "general_invalid_attribute"
            elif not math.isfinite(age) or not 10 <= age <= 1440:
                errors["base"] = "general_invalid_source_age"
            elif ((occupied_entity and occupied_entity != old.get("occupied_rooms_entity")) or
                  (sleep_entity and sleep_entity != old.get("sleep_rooms_entity"))):
                # HA has no live cross-field refresh. Re-open the form after
                # a source change so only the *new* entity's parseable
                # attributes and its State option are offered.
                self._general_source_draft={
                    **old,"occupied_rooms_entity":occupied_entity,
                    "sleep_rooms_entity":sleep_entity,
                    "occupied_rooms_attribute":"",
                    "sleep_rooms_attribute":"",
                    "room_occupancy_sensors":selected,
                    "home_trackers":at_home,
                    "source_stale_minutes":age,
                }
                return await self.async_step_general_settings()
            else:
                self._general_source_draft={}
                self._values[CONF_OCCUPANCY_GLOBAL] = {
                    **old,
                    "room_occupancy_sensors": list(dict.fromkeys(selected)),
                    "occupied_rooms_entity": occupied_entity or None,
                    "occupied_rooms_attribute": "" if occupancy_attr=="__state__" else occupancy_attr,
                    "sleep_rooms_entity": sleep_entity or None,
                    "sleep_rooms_attribute": "" if sleep_attr=="__state__" else sleep_attr,
                    "home_trackers": list(dict.fromkeys(at_home)),
                    "home_policy": user_input.get(
                        "general_home_policy", old.get("home_policy", "any_home")
                    ) if user_input.get("general_home_policy",
                                        old.get("home_policy", "any_home")) in (
                                            "any_home", "all_home") else "any_home",
                    "source_stale_minutes": age,
                }
                return await self._finish()
        fields = {
            _field("general_room_occupancy_sensors", old.get("room_occupancy_sensors", [])):
                _select(room_sensors, multi=True),
            _field("general_occupied_rooms_entity", old.get("occupied_rooms_entity") or "none"):
                _select(source_options),
            _field("general_occupied_rooms_attribute", (
                old.get("occupied_rooms_attribute") or "__state__"
                if any(o["value"]=="__state__" for o in self._room_attribute_options(
                    self.hass,old.get("occupied_rooms_entity"))) else
                self._room_attribute_options(self.hass,old.get("occupied_rooms_entity"))[0]["value"]
            )):
                _select(self._room_attribute_options(self.hass,old.get("occupied_rooms_entity"))),
            _field("general_home_trackers", old.get("home_trackers", [])):
                _select(trackers, multi=True),
            _field("general_sleep_rooms_entity", old.get("sleep_rooms_entity") or "none"):
                _select(source_options),
            _field("general_sleep_rooms_attribute", (
                old.get("sleep_rooms_attribute") or "__state__"
                if any(o["value"]=="__state__" for o in self._room_attribute_options(
                    self.hass,old.get("sleep_rooms_entity"))) else
                self._room_attribute_options(self.hass,old.get("sleep_rooms_entity"))[0]["value"]
            )):
                _select(self._room_attribute_options(self.hass,old.get("sleep_rooms_entity"))),
        }
        return self.async_show_form(
            step_id="general_settings", data_schema=probatio.Schema(fields), errors=errors
        )

    async def async_step_pollen(self, user_input=None):
        """Dedicated, robust pollen editor: no dynamic AQI selectors."""
        data = self._values.get(CONF_ENVIRONMENT_GLOBAL, {})
        current = dict(data) if isinstance(data, dict) else {}
        errors = {}
        if user_input is not None:
            source = user_input.get("pollen_entity", current.get("pollen_entity"))
            try:
                threshold = float(user_input.get("pollen_high_from", current.get("pollen_high_from", 3)))
                maximum = float(user_input.get("pollen_max_scale", current.get("pollen_max_scale", 5)))
            except (TypeError, ValueError, OverflowError):
                threshold, maximum = float("nan"), float("nan")
            if source and (not isinstance(source, str) or
                           not source.startswith("sensor.") or
                           self.hass.states.get(source) is None):
                errors["base"] = "invalid_environment_scale"
            elif not all(math.isfinite(v) for v in (threshold, maximum)) or not (
                0 <= threshold <= maximum <= 100
            ):
                errors["base"] = "invalid_environment_scale"
            else:
                current.update({
                    "pollen_entity": source or None,
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
            _field("pollen_entity", current.get("pollen_entity")):
                selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
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
        shown = getattr(self, "_outside_aqi_selected", aqis[0] if aqis else "none")
        chosen = (user_input or {}).get("outside_aqi_entity") or shown
        if user_input is not None and chosen in aqis and chosen != shown:
            # One form can't dynamically replace the scale/limit defaults.
            # Re-render for the newly selected source rather than apply the
            # previous source's scale to another sensor without confirmation.
            self._outside_aqi_selected = chosen
            return await self.async_step_outside_aqi()
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
        for section in (CONF_CLIMATE_ROOMS, CONF_PID_ROOMS):
            old = self._values.get(section, {})
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
                self._climate_draft = deepcopy(saved.get(area, {})) if isinstance(saved, dict) else {}
                return await self.async_step_select_devices()
            errors["base"] = "invalid_areas"
        return self.async_show_form(step_id="area_devices", errors=errors,
            data_schema=probatio.Schema({
                _field("area_devices_area", rooms[0]["value"], required=True): _select(rooms)
            }))

    async def async_step_select_devices(self, user_input=None):
        """One room inventory picker; saving does not require a setup wizard."""
        from .room_device_picker import physical_device_choices
        area = self._climate_area
        prior = configured_sources(self._values, area)
        choices, sources = physical_device_choices(self.hass, area, prior)
        draft = self._climate_draft
        old = draft.get("selected_devices")
        # Bring an existing supervisory PID selection into the same visible
        # inventory without dropping its established permission on upgrade.
        selected_before = set(old) | set(prior) if isinstance(old, list) else set(prior)
        default = [item["value"] for item in choices if not isinstance(old, list)
                   or set(sources[item["value"]]).intersection(selected_before)]
        errors = {}
        if user_input is not None:
            selected = user_input.get("selected_devices", default)
            configure = user_input.get("configure_device_sources", False)
            if (not isinstance(selected, list)
                    or any(not isinstance(key, str) or key not in sources for key in selected)
                    or type(configure) is not bool):
                errors["base"] = "invalid_selected_devices"
            else:
                devices = list(dict.fromkeys(entity for key in selected for entity in sources[key]))
                # The inventory is physical-device based, but grants and native
                # commands remain exact-entity based. A new endpoint must never
                # inherit another endpoint's room-wide automation permission.
                before = selected_before
                profiles = deepcopy(draft.get("device_settings", {}))
                profiles = profiles if isinstance(profiles, dict) else {}
                for entity in devices:
                    if entity not in before:
                        cfg = profiles.get(entity, {})
                        profiles[entity] = {**(cfg if isinstance(cfg, dict) else {}),
                                            "auto_control": False}
                draft["selected_devices"] = devices
                draft["device_settings"] = profiles
                self._climate_draft = draft
                # Optional sensor/hardware commissioning is kept in this ONE
                # path. Targets, presets, algorithms and quiet controls remain
                # on the managed device; there is no separate PID device list.
                if configure and devices:
                    return await self.async_step_device_choice()
                return await self._save_devices()
        from homeassistant.helpers import area_registry
        room = area_registry.async_get(self.hass).async_get_area(area)
        return self.async_show_form(
            step_id="select_devices", errors=errors,
            data_schema=probatio.Schema({
                _field("selected_devices", default): _select(choices, multi=True),
                _field("configure_device_sources", False): selector.BooleanSelector(),
            }), description_placeholders={"area_name": room.name if room else area}
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
        before = result.get(self._climate_area, {})
        reconciled = _reconcile_device_selection(before, self._climate_draft)
        result[self._climate_area] = reconciled
        self._values[CONF_CLIMATE_ROOMS] = result
        # Legacy supervisory PID uses a second persisted list. It is now
        # constrained by this same picker, never a competing setup route.
        pid_rooms = self._values.get(CONF_PID_ROOMS, {})
        pid = pid_rooms.get(self._climate_area) if isinstance(pid_rooms, dict) else None
        if isinstance(pid, dict) and isinstance(pid.get("climate_entities"), list):
            selected = set(reconciled.get("selected_devices", []))
            retained = [entity for entity in pid["climate_entities"] if entity in selected]
            if retained != pid["climate_entities"]:
                pid_rooms = deepcopy(pid_rooms)
                pid_rooms[self._climate_area]["climate_entities"] = retained
                if not retained:
                    pid_rooms[self._climate_area]["enabled"] = False
                self._values[CONF_PID_ROOMS] = pid_rooms
                profiles = reconciled.setdefault("device_settings", {})
                for entity in set(pid["climate_entities"]) - selected:
                    profiles.setdefault(entity, {})["auto_control"] = False
        self._climate_draft = reconciled
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
        excluded_by_area = self._values.get(CONF_EXCLUDED_INDOOR, {})
        raw_exclusions = (excluded_by_area.get(area, [])
                          if isinstance(excluded_by_area, dict) else [])
        excluded = set(raw_exclusions) if isinstance(raw_exclusions, list) else set()

        def eligible_sensor(metric: str) -> list[dict[str, str]]:
            # Excluded readings are not trustworthy enough for physical
            # control, even if HA still provides a numeric live value.
            return [candidate for candidate in _sensor_choices(self.hass, area, metric)
                    if candidate["value"] not in excluded]

        native_modes = state.attributes.get("hvac_modes", [])
        native_modes = set(native_modes) if isinstance(native_modes, (list, tuple)) else set()
        thermal = bool(native_modes & {"heat", "cool", "heat_cool", "auto"})
        native_dry = domain == "climate" and not thermal and "dry" in native_modes
        native_fan = domain == "climate" and not thermal and not native_dry and "fan_only" in native_modes
        kind = (old.get("method") or ("native" if native_dry or native_fan else
                                     "setpoint" if domain != "fan" else "speed"))
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
                elif domain == "climate" and (not (thermal or native_dry or native_fan)
                        or (native_dry or native_fan) and data["method"] != "native"
                        or data["method"] == "native" and "off" not in native_modes):
                    errors["base"] = "device_method_invalid"
                elif domain in ("humidifier","fan") and data["method"] not in (
                    ("setpoint", "power") if domain == "humidifier" else ("speed", "power")
                ):
                    errors["base"] = "device_method_invalid"
                elif data["method"] == "power" and not data["hardware_confirmed"]:
                    errors["base"] = "device_hardware_required"
                elif (data["absence_action"] == "off" and domain == "climate"
                      and not data["hardware_confirmed"]):
                    errors["base"] = "device_hardware_required"
                elif (data["absence_action"] == "off" and domain in ("fan", "humidifier")
                      and data["method"] != "power"):
                    errors["base"] = "device_power_required_for_off"
                elif domain == "climate" and thermal and (
                    not isinstance(data["temperature_entity"], str) or
                    data["temperature_entity"] not in {
                        s["value"] for s in eligible_sensor("temperature")
                    }):
                    from .climate_equipment import classify_hvac
                    capability=classify_hvac(state.attributes,state.state)
                    if capability.get("drying") and not (
                        capability.get("heating") or capability.get("cooling")
                    ):
                        errors["base"] = "device_dry_advisory_only"
                    else:
                        errors["base"] = "device_temperature_required"
                elif (domain == "humidifier" or native_dry) and data["humidity_entity"] not in {
                    s["value"] for s in eligible_sensor("humidity")
                }:
                    errors["base"] = "device_humidity_required"
                elif (domain == "fan" or native_fan) and (
                    data["fan_purpose"] not in ("extraction", "filtration") or
                    data["co2_entity" if data["fan_purpose"]=="extraction" else "pm25_entity"]
                    not in {s["value"] for s in eligible_sensor(
                        "co2" if data["fan_purpose"]=="extraction" else "pm25"
                    )} or not data["sensor_verified"]
                ):
                    errors["base"] = "device_air_sensor_required"
                # Independent capability verification must run AFTER the
                # hardware/presence/absence policy chain. Nesting in its elif
                # sequence would bypass the absence-OFF attestation check.
                if not errors and domain == "climate" and data["method"] == "setpoint":
                    from .climate_equipment import classify_hvac
                    features = classify_hvac(state.attributes, state.state)
                    if not (features.get("temperature_setpoint") is True or
                            (features.get("native_heat_cool") is True and
                             features.get("temperature_range") is True)):
                        errors["base"] = "device_method_invalid"
                if not errors and domain == "humidifier" and data["method"] == "setpoint":
                    from .climate_humidity_native import _target, _bounded_setpoint
                    attrs = state.attributes
                    measured = _target(attrs)
                    if measured is None or _bounded_setpoint(
                        attrs, measured, measured
                    )[0] not in ("at_setpoint", "command"):
                        errors["base"] = "device_method_invalid"
                if not errors and domain == "fan" and data["method"] == "speed":
                    try:
                        features = int(state.attributes.get("supported_features", 0))
                    except (ValueError, TypeError, OverflowError):
                        features = 0
                    if features & 1 == 0:
                        errors["base"] = "device_method_invalid"
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
            if not errors and data["auto_control"] and data["method"] in ("power", "native"):
                if domain == "climate":
                    values = [_valid_temperature(data[key], low, high) for key, low, high in (
                        ("min_on_s", 600, 7200), ("min_off_s", 600, 14400), ("max_on_s", 900, 28800))]
                    if any(v is None for v in values) or values[2] <= values[0]:
                        errors["base"] = "device_runtime_invalid"
            if not errors and data["auto_control"] and data["method"] == "power":
                # Match the exact selected driver's compressor/fan dwell and
                # watchdog constraints. The old form accepted combinations
                # that were guaranteed to be rejected at runtime.
                if domain == "humidifier":
                    from .climate_humidity_power import timings
                    checked = timings({
                        "humidity_power_min_on_s": data["min_on_s"],
                        "humidity_power_min_off_s": data["min_off_s"],
                        "humidity_power_max_on_s": data["max_on_s"],
                    })
                else:
                    from .climate_fan_power import dwell_settings
                    checked = dwell_settings({
                        "fan_power_min_on_s": data["min_on_s"],
                        "fan_power_min_off_s": data["min_off_s"],
                        "fan_power_max_on_s": data["max_on_s"],
                    })
                if checked is None:
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
                # Role assignment is exact, with no implied compressor
                # switching. Enabling a fan/humidifier must not implicitly
                # arm a previously advisory-only thermostat in the same room.
                if data["auto_control"]:
                    was_authorized = draft.get("allow_actuation") is True
                    if (domain in ("fan", "humidifier") and not was_authorized
                            and draft.get("controller", "device") == "device"):
                        draft["controller"] = "environment"
                        draft["auto_switch_hvac"] = False
                    draft["enabled"] = True
                    draft["allow_actuation"] = True
                    if native_dry or native_fan:
                        # Inventory/configuration only: the new per-device selector
                        # must explicitly transfer ownership before any new control.
                        # Never arm the old temperature or DRY/FAN-only driver here.
                        if not was_authorized:
                            draft["controller"] = "environment"
                            draft["auto_switch_hvac"] = False
                        draft["dry_climate_entity" if native_dry else "fan_climate_entity"] = entity
                        if native_dry:
                            draft["humidity_entity"] = data["humidity_entity"]
                        else:
                            for key in ("co2_entity", "pm25_entity"):
                                if data.get(key):
                                    draft[key] = data[key]
                    elif domain == "climate":
                        from .climate_equipment import classify_hvac
                        modes = classify_hvac(state.attributes, state.state)
                        draft["temperature_entity"] = data["temperature_entity"]
                        if (not draft.get("climate_entity") or
                                draft["climate_entity"] == entity or
                                draft["climate_entity"] not in draft.get("selected_devices", [])):
                            # Promoting a newly selected thermostat must not
                            # leave it as a secondary to an excluded old owner.
                            draft["climate_entity"] = entity
                            draft["controller"] = "device"
                            draft["auto_switch_hvac"] = (data["method"] == "native"
                                                          and data["hardware_confirmed"])
                            # A heat-only or cool-only thermostat cannot
                            # implement a fabricated automatic dual mode.
                            # Preserve the live mode for devices with both
                            # capabilities but no commissioned switching.
                            draft["mode"] = (
                                "heat" if modes.get("heating") and not modes.get("cooling")
                                else "cool" if modes.get("cooling") and not modes.get("heating")
                                else "auto" if modes.get("native_heat_cool")
                                else state.state if state.state in ("heat", "cool")
                                else "auto"
                            )
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
                        previous_role = ("purifier_fan_entity"
                                         if role=="extraction_fan_entity" else
                                         "extraction_fan_entity")
                        if draft.get(previous_role)==entity:
                            # A change of purpose moves the same physical fan;
                            # it must never occupy two conflicting roles.
                            draft.pop(previous_role, None)
                        draft[role] = entity
                        draft["fan_speed_auto"] = data["method"] == "speed"
                        draft["fan_power_auto"] = data["method"] == "power"
                        draft["fan_power_hardware_confirmed"] = data["hardware_confirmed"]
                        draft["co2_entity"] = data["co2_entity"]
                        draft["pm25_entity"] = data["pm25_entity"]
                        draft["pm25_sensor_verified"] = data["sensor_verified"]
                        draft[("extraction_speed_percent" if
                               data["fan_purpose"]=="extraction" else
                               "purifier_speed_percent")] = data["fan_speed_percent"]
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
            _field("device_absence_action", old.get("absence_action","hold")):
                _select(["hold","off"],translation_key="device_absence_action"),
            _field("device_hardware_confirmed", old.get("hardware_confirmed",False)):
                selector.BooleanSelector(),
        }
        if domain == "climate" and not (native_dry or native_fan):
            temp = eligible_sensor("temperature")
            fields[_field("device_temperature_entity",
                          old.get("temperature_entity") or draft.get("temperature_entity"))] = _select(temp)
            # Per-device home/away/sleep policy targets are now editable
            # on the room's Config Number entities.
        elif domain == "humidifier" or native_dry:
            fields[_field("device_humidity_entity",
                          old.get("humidity_entity") or draft.get("humidity_entity"))] = _select(
                              eligible_sensor("humidity"))
        else:
            fields[_field("device_fan_purpose",old.get("fan_purpose","extraction"))]=_select(
                ["extraction","filtration"],translation_key="device_fan_purpose")
            fields[_field("device_co2_entity",old.get("co2_entity"))]=_select(
                [{"value":"none","label":"—"}]+eligible_sensor("co2"))
            fields[_field("device_pm25_entity",old.get("pm25_entity"))]=_select(
                [{"value":"none","label":"—"}]+eligible_sensor("pm25"))
            fields[_field("device_sensor_verified",old.get("sensor_verified",False))]=selector.BooleanSelector()
        if domain in ("fan", "humidifier", "climate"):
            permitted = ({
                "min_on_s": (300, 7200, 600),
                "min_off_s": (600, 14400, 600),
                "max_on_s": (900, 28800, 7200),
            } if domain in ("humidifier", "climate") else {
                "min_on_s": (120, 3600, 300),
                "min_off_s": (120, 7200, 300),
                "max_on_s": (900, 86400, 14400),
            })
            if domain == "climate":
                permitted["min_on_s"] = (600, 7200, 600)
            for name, (minimum, maximum, default) in permitted.items():
                fields[_field("device_"+name, old.get(name, default))] = _number(
                    minimum, maximum,
                )
        return self.async_show_form(
            step_id="device_settings", errors=errors, data_schema=probatio.Schema(fields),
            description_placeholders={"device_name":state.name or entity,
                                      "device_entity":entity, "area_name":area},
        )
