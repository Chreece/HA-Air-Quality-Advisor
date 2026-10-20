"""Event-driven observations and optional, rate-limited action delivery."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from datetime import timedelta
from time import monotonic, time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_time_interval

from .const import (
    ANNOUNCE_COOLDOWN_SECONDS, ANNOUNCE_OPEN_STABLE_SECONDS, CONF_AREAS,
    CONF_EXCLUDED_WINDOWS, CONF_EXCLUDED_INDOOR,
    CONF_AUTO_NOTIFY, CONF_AUTO_TTS, CONF_HUB, CONF_LANGUAGE,
    CONF_REPEAT_MINUTES, DEFAULT_REPEAT_MINUTES, MAX_REPEAT_MINUTES,
    CONF_MEDIA_PLAYERS, CONF_NOTIFY_TARGETS, CONF_OUTDOOR,
    CONF_AI_AGENT,
    CONF_THRESHOLDS, CONF_TTS_ENGINE, CONF_WARNINGS, CONF_WEATHER,
    DEFAULT_THRESHOLDS, DOMAIN, SIGNAL_UPDATED, CONF_USE_MOLD, CONF_MOLD_ROOMS,
    CONF_ENVIRONMENT_GLOBAL, CONF_ENVIRONMENT_ROOMS, CONF_PID_ROOMS, CONF_CLIMATE_ROOMS,
)
from .ai_rewrite import DEFAULT_AGENT, ai_effectively_enabled, async_rewrite_announcement
from .hub_delivery import hub_available, make_hub_payload, async_submit_hub, async_system_notification
from .discovery import entity_area, reading, rooms, warning, weather, temperature_sensor_c
from .mold import estimate_mold_for_room, rh_fallback_for_room
from .environment import build_environment
from .environment_history import EnvironmentHistory
from .climate_pid import ClimatePidCoordinator
from .climate_rooms import gather as climate_room_plan
from .climate_coordination import duplicate_owners, native_plan_hold_reason
from .climate_arbitration import room_coordination
from .climate_native import NativeClimateControl
from .climate_direct import DirectClimateControl
from .climate_humidity_native import HumiditySetpointControl
from .climate_humidity_power import HumidityPowerControl
from .climate_secondary_native import SecondaryClimateSetpoint
from .climate_air_actions import air_treatment_plan
from .climate_hvac_modes import native_air_mode_advice
from .climate_air_mode_native import NativeAirModeControl
from .climate_commissioning import report as climate_commissioning_report
from .climate_window import window_substitution, window_reason
from .climate_fan_native import RunningFanSpeedControl
from .climate_fan_power import FanPowerControl
from .building_physics import moisture_potential
from .environment_extended import global_pollen, global_aqi
from .logic import Reading, Reason, Recommendation
from .logic import Plan, evaluate
from .messages import announcement, language_code

_LOGGER = logging.getLogger(__name__)


class AirQualityManager:
    """One Home Assistant instance-wide decision engine."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.plan = Plan("blocked", False, (), (), ())
        self._tracked: set[str] = set()
        self._unsubs: list[Any] = []
        # Timers are per room; unrelated sensor changes must not postpone
        # reminders in another room. Values are (action key, reason key).
        self._active_actions: dict[str, tuple[str, str]] = {}
        self._pending_unsubs: dict[str, Any] = {}
        self._repeat_unsubs: dict[str, Any] = {}
        self._last_sent: dict[str, float] = {}
        self._active = False
        self._tasks: set[asyncio.Task[Any]] = set()
        self._environment_history = EnvironmentHistory()
        self._environment_store: Any | None = None
        self.pid = ClimatePidCoordinator(self.hass, self.entry.entry_id, report_changed=self._pid_updated)
        self.native_climate = NativeClimateControl(self.hass, self.entry.entry_id)
        self.direct_climate = DirectClimateControl(
            self.hass, self.entry.entry_id, changed=self._direct_climate_updated,
        )
        self.native_humidity = HumiditySetpointControl(
            self.hass,self.entry.entry_id,changed=self._humidity_updated,
        )
        self.humidity_power = HumidityPowerControl(
            self.hass,self.entry.entry_id,changed=self._humidity_power_updated,
        )
        self.secondary_climate = SecondaryClimateSetpoint(
            self.hass,self.entry.entry_id,changed=self._secondary_updated,
        )
        self.running_fans = RunningFanSpeedControl(
            self.hass,self.entry.entry_id,changed=self._fan_updated,
        )
        self.fan_power = FanPowerControl(
            self.hass,self.entry.entry_id,changed=self._fan_power_updated,
        )
        self.native_air_mode = NativeAirModeControl(
            self.hass,self.entry.entry_id,changed=self._air_mode_updated,
        )

    @property
    def settings(self) -> dict[str, Any]:
        return {**self.entry.data, **self.entry.options}

    @property
    def thresholds(self) -> dict[str, float]:
        overrides = self.settings.get(CONF_THRESHOLDS, {})
        return {**DEFAULT_THRESHOLDS, **overrides}

    @property
    def hub_available(self) -> bool:
        return hub_available(self.hass)

    def get_language(self, language: str | None) -> str:
        selected = language or self.settings.get(CONF_LANGUAGE, "auto")
        if selected == "auto":
            selected = self.hass.config.language
        return language_code(selected)

    @callback
    def _capture(self) -> Plan:
        config = self.settings
        max_age = self.thresholds["max_age_minutes"]
        selected_outdoor = set(config.get(CONF_OUTDOOR, []))
        monitored_areas = config.get(CONF_AREAS, [])
        by_area = config.get(CONF_EXCLUDED_INDOOR, {})
        if not isinstance(by_area, dict):
            by_area = {}
        excluded_indoor = {
            entity_id
            for area_id in monitored_areas
            for entity_id in by_area.get(area_id, [])
            if isinstance(entity_id, str) and entity_area(self.hass, entity_id) == area_id
        }
        selected_rooms = rooms(
            self.hass, monitored_areas, max_age,
            excluded_entities=(
                selected_outdoor
                | set(config.get(CONF_EXCLUDED_WINDOWS, []))
                | excluded_indoor
            ),
        )
        current_weather = tuple(
            weather(self.hass, ent, max_age) for ent in config.get(CONF_WEATHER, [])
        )
        raw_rooms = selected_rooms  # Keep source RH before optional mold substitution.
        mold_temperature_entities: set[str] = set()
        # Preserve the exact set of supported, included humidity sensors
        # before replacing them with the derived room mold indicator.
        humidity_entities = {
            item.entity_id for room in selected_rooms for item in room.readings
            if item.metric == "humidity"
        } if config.get(CONF_USE_MOLD, False) else set()
        if config.get(CONF_USE_MOLD, False):
            calibrations = config.get(CONF_MOLD_ROOMS, {})
            if not isinstance(calibrations, dict):
                calibrations = {}
            updated_rooms = []
            for room in selected_rooms:
                calibration = calibrations.get(room.area_id, {})
                if not isinstance(calibration, dict):
                    calibration = {}
                sensor_id = calibration.get("indoor_temperature_entity")
                if isinstance(sensor_id, str):
                    mold_temperature_entities.add(sensor_id)
                indoor_c = (
                    temperature_sensor_c(self.hass, sensor_id, max_age)
                    if isinstance(sensor_id, str) else None
                )
                mold_reading = estimate_mold_for_room(
                    room, indoor_c, current_weather, calibration,
                )
                # Prefer surface mold RH when calculable. If unavailable,
                # substitute exactly ONE averaged valid RH reading per room
                # (legacy indoor_humidity threshold). Keep the unavailable
                # mold reading for explicit calibration/source warnings. Put
                # RH fallback first so it is visible in compact room cards.
                fallback = rh_fallback_for_room(room, mold_reading)
                updated_rooms.append(replace(
                    room,
                    readings=(
                        ((fallback,) if fallback else ())
                        + tuple(r for r in room.readings if r.metric != "humidity")
                        + (mold_reading,)
                    ),
                ))
            selected_rooms = tuple(updated_rooms)
        self._tracked = (
            selected_outdoor
            | set(config.get(CONF_WEATHER, []))
            | set(config.get(CONF_WARNINGS, []))
            | mold_temperature_entities
            | humidity_entities
            | {window.entity_id for room in selected_rooms for window in room.windows}
            | {item.entity_id for room in selected_rooms for item in room.readings
               if item.metric != "mold"
               and not (item.details or {}).get("fallback_for_mold")}
        )
        environment_global = config.get(CONF_ENVIRONMENT_GLOBAL, {})
        if not isinstance(environment_global, dict):
            environment_global = {}
        environment_rooms = config.get(CONF_ENVIRONMENT_ROOMS, {})
        if not isinstance(environment_rooms, dict):
            environment_rooms = {}
        normalized_outdoor = []
        for ent in sorted(selected_outdoor):
            item = reading(self.hass, ent, max_age, outdoor=True)
            if item.metric == "aqi" and item.value is not None:
                aqi = global_aqi(item, environment_global)
                item = Reading(item.entity_id, item.name, item.metric, item.value,
                               {"aqi": aqi})
            normalized_outdoor.append(item)
        outdoor_readings = tuple(normalized_outdoor)
        pollen, pollen_sources = global_pollen(self.hass, environment_global, max_age)
        self._tracked.update(pollen_sources)
        extra_outside = ()
        if pollen.get("avoid_ventilation"):
            extra_outside = (Reason("outside_pollen", "Pollen forecast",
                                    f'{pollen["value"]:g} / {pollen["max_scale"]:g}'),)
        warnings = tuple(warning(self.hass, ent, max_age) for ent in config.get(CONF_WARNINGS, []))
        base_plan = evaluate(outdoor_readings, current_weather, warnings, selected_rooms,
                             self.thresholds, extra_outside=extra_outside)
        environment, changed = build_environment(
            self.hass, raw_rooms, selected_rooms, current_weather, outdoor_readings,
            history=self._environment_history, max_age_minutes=max_age,
            mold_calibrations=config.get(CONF_MOLD_ROOMS, {}),
            room_profiles=environment_rooms,
            outside_safe=base_plan.outdoor_safe,
        )
        environment["__outside__"] = {"pollen": pollen}
        room_climate_configs=config.get(CONF_CLIMATE_ROOMS,{})
        climate_only=()
        if isinstance(room_climate_configs,dict):
            # Climate may be configured in any real HA area; window monitoring
            # remains scoped to CONF_AREAS so notification routes never widen.
            extra_areas=[area for area in room_climate_configs
                         if isinstance(area,str) and area not in monitored_areas]
            climate_only=rooms(
                self.hass,extra_areas,max_age,
                excluded_entities=(selected_outdoor |
                                   set(config.get(CONF_EXCLUDED_WINDOWS,[]))),
            ) if extra_areas else ()
            raw_for_climate={r.area_id:r for r in raw_rooms}
            raw_for_climate.update({r.area_id:r for r in climate_only})
            duplicate_devices=duplicate_owners(room_climate_configs)
            for monitored in (*selected_rooms,*climate_only):
                settings=room_climate_configs.get(monitored.area_id,{})
                prior = (
                    self.direct_climate._rooms.get(monitored.area_id).mode
                    if monitored.area_id in self.direct_climate._rooms else
                    self.native_climate.expected_hvac.get(monitored.area_id)
                )
                pmv_air=environment.get(monitored.area_id,{}).get(
                    "international",{}).get("pmv_air_target",{}
                )
                comfort=pmv_air.get("air_temperature_target_c") if (
                    pmv_air.get("status")=="estimate") else None
                state,tracked=climate_room_plan(
                    self.hass,raw_for_climate[monitored.area_id],settings,
                    prior_mode=prior,comfort_target_c=comfort,
                    outdoor_safe=base_plan.outdoor_safe,
                    duplicate_equipment=duplicate_devices,
                    require_window_contact=monitored.area_id in monitored_areas,
                )
                state["target_source"]=settings.get("target_source","temperature")
                state["comfort_target_evidence"]=pmv_air.get("status","not_configured")
                # Independent air-quality responses never command hardware.
                # Use physical moisture-ratio evidence, not outdoor RH alone.
                profile=environment_rooms.get(monitored.area_id,{})
                if not isinstance(profile,dict):
                    profile={}
                moist=environment.get(monitored.area_id,{}).get("moisture")
                if not isinstance(moist,dict) or moist.get("status")=="unavailable":
                    station=current_weather[0] if len(current_weather)==1 else None
                    moist=moisture_potential(
                        state.get("temperature_c"),
                        state.get("humidity_management",{}).get("measured_rh"),
                        getattr(station,"temperature_c",None),
                        getattr(station,"humidity",None),
                    )
                state["air_actions"]=air_treatment_plan(
                    raw_for_climate[monitored.area_id].readings,
                    state,state.get("equipment_plan",{}),moist,
                    outside_safe=base_plan.outdoor_safe,
                    science_profile=profile,settings=settings,
                )
                # Fast fan polling may reuse this plan; record when its
                # outdoor-air and sensor evidence was actually evaluated.
                state["air_evidence_at"]=time()
                valid_outside=[r for r in outdoor_readings
                               if r.metric in ("pm25","pm10","no2","o3","so2","aqi")]
                state["air_actions"]["outdoor_air_verified"]=(
                    base_plan.outdoor_safe is True and bool(valid_outside)
                    and all(r.value is not None for r in valid_outside)
                    and all(
                        (r.details or {}).get("aqi",{}).get("status")=="ready"
                        if r.metric=="aqi" else True for r in valid_outside
                    )
                )
                substitute=window_substitution(
                    self.hass, raw_for_climate[monitored.area_id],
                    settings, state,
                    environment.get(monitored.area_id,{}),
                    current_weather, outdoor_readings,
                    outside_safe=base_plan.outdoor_safe,
                )
                substitute["notify_enabled"]=(
                    settings.get("window_efficiency_notify") is True
                    if isinstance(settings,dict) else False
                )
                state["window_efficiency"]=substitute
                # Previously the DRY/FAN_ONLY advisor existed only in tests:
                # attach its real live plan to the dashboard for heat-pump,
                # AC, and native DRY-only equipment, even without actuation.
                state["native_air_mode_advice"]=native_air_mode_advice(
                    self.hass,monitored.area_id,settings,
                    state.get("equipment_plan",{}),time(),
                )
                if isinstance(settings,dict) and settings.get("enabled"):
                    equipment=state.get("equipment_plan",{})
                    thermal=equipment.get("thermal",{})
                    # Never issue commands for an unowned, shared or competing
                    # appliance. Secondary equipment needs a dedicated driver.
                    if settings.get("controller")=="device":
                        hold=native_plan_hold_reason(
                            settings.get("climate_entity"),equipment,state.get("mode"))
                        if hold is not None:
                            state["status"]="hold"
                            state["reason"]=hold
                    elif equipment.get("status")=="duplicate_equipment_owner":
                        state["status"]="hold"
                        state["reason"]="duplicate_equipment_owner"
                    state["automatic_actuation_enabled"] = (
                        settings.get("allow_actuation") is True and
                        (settings.get("controller") == "device" or
                         settings.get("humidity_setpoint_auto") is True or
                         settings.get("humidity_power_auto") is True or
                         settings.get("fan_speed_auto") is True or
                         settings.get("fan_power_auto") is True or
                         settings.get("dry_fan_mode_auto") is True)
                    )
                    driver = (self.direct_climate if settings.get("controller") in
                              ("on_off","pwm","proportional") else self.native_climate)
                    state["actuation"] = driver.statuses.get(
                        monitored.area_id,{"status":"advisory_only"}
                    )
                    state["humidity_actuation"] = self.native_humidity.statuses.get(
                        monitored.area_id,{"status":"advisory_only"}
                    )
                    state["humidity_power_actuation"] = self.humidity_power.statuses.get(
                        monitored.area_id,{"status":"advisory_only"}
                    )
                    state["secondary_actuation"] = self.secondary_climate.statuses.get(
                        monitored.area_id,{"status":"advisory_only"}
                    )
                    state["fan_actuation"] = self.running_fans.statuses.get(
                        monitored.area_id,{"status":"advisory_only"}
                    )
                    state["fan_power_actuation"] = self.fan_power.statuses.get(
                        monitored.area_id,{"status":"advisory_only"}
                    )
                    state["native_air_mode_actuation"] = self.native_air_mode.statuses.get(
                        monitored.area_id,{"status":"advisory_only"}
                    )
                    # All independent device drivers consume ONE per-room
                    # priority/exclusivity decision. They still recheck the
                    # physical state immediately before a device write.
                    state["coordination"]=room_coordination(
                        self.hass,monitored.area_id,settings,state,now=time(),
                    )
                    environment.setdefault(monitored.area_id,{})["climate_plan"]=state
                    self._tracked.update(tracked)
                    self._tracked.update(w.entity_id for w in monitored.windows)
                    self._tracked.update(r.entity_id for r in raw_for_climate[
                        monitored.area_id].readings)
        pid_configs = config.get(CONF_PID_ROOMS, {})
        if not isinstance(pid_configs, dict):
            pid_configs = {}
        pid_statuses = self.pid.configured_statuses(pid_configs)
        for room in selected_rooms:
            if room.area_id in pid_statuses:
                environment.setdefault(room.area_id, {})["climate_pid"] = pid_statuses[room.area_id]
        for pid_config in pid_configs.values():
            if not isinstance(pid_config, dict) or not pid_config.get("enabled"):
                continue
            temperature_entity = pid_config.get("temperature_entity")
            if isinstance(temperature_entity, str):
                self._tracked.add(temperature_entity)
            for entity_id in self.pid._targets(pid_config):
                self._tracked.add(entity_id)
        for profile in environment_rooms.values():
            if not isinstance(profile, dict):
                continue
            for key, entity in profile.items():
                if key.endswith("_entity") and isinstance(entity, str):
                    self._tracked.add(entity)
        for report in environment.values():
            source = report.get("sources", {}).get("indoor_temperature_entity")
            if isinstance(source, str):
                self._tracked.add(source)
        # Observe occupancy changes for conditional CO2 decay, but never
        # treat motion activity as reliable evidence of an unoccupied room.
        for state in self.hass.states.async_all("binary_sensor"):
            if (str(state.attributes.get("device_class", "")).casefold() in ("occupancy", "presence")
                    and entity_area(self.hass, state.entity_id) in monitored_areas):
                self._tracked.add(state.entity_id)
        if changed and self._environment_store is not None:
            self._environment_store.async_delay_save(
                self._environment_history.snapshot, 300,
            )
        air_plan=evaluate(
            outdoor_readings, current_weather, warnings, selected_rooms,
            self.thresholds, environment=environment,
            extra_outside=extra_outside,
        )
        extra=tuple(room for room in climate_only if
                    isinstance(room_climate_configs.get(room.area_id),dict) and
                    room_climate_configs[room.area_id].get("enabled") is True)
        extra_notices=[]
        if base_plan.outdoor_safe is True:
            for room in extra:
                report=environment.get(room.area_id,{}).get("climate_plan",{})
                option=report.get("window_efficiency",{})
                if (option.get("status") != "opportunity" or
                        option.get("notify_enabled") is not True):
                    continue
                # No synthetic window; this includes only true HA window
                # contacts in the explicitly selected climate room.
                closed=tuple(w for w in room.windows if w.opened is False)
                if not closed or len(closed)!=len(room.windows):
                    continue
                extra_notices.append(Recommendation(
                    "open",room.area_id,room.name,closed,(window_reason(option),),
                ))
        return replace(
            air_plan,climate_rooms=extra,
            climate_recommendations=tuple(extra_notices),
        )

    async def async_start(self) -> None:
        """Track sensor changes and periodically recheck freshness and new entities."""
        # Home Assistant Store keeps bounded sensor samples through restart.
        # Pure-logic tests may stub HA without its storage package.
        try:
            from homeassistant.helpers.storage import Store
            self._environment_store = Store(
                self.hass, 1, f"{DOMAIN}.environment_history_{self.entry.entry_id}",
            )
            stored = await self._environment_store.async_load()
            self._environment_history = EnvironmentHistory.restore(stored)
        except ImportError:
            _LOGGER.debug("Home Assistant storage not available in test runtime")
        except Exception:
            _LOGGER.exception("Environment history could not be restored; starting empty")
        # Load latching PID manual overrides and expected targets first.
        # If its storage fails, the PID controller remains fail-closed.
        await self.pid.async_start()
        await self.native_climate.async_start()
        await self.direct_climate.async_start()
        await self.native_humidity.async_start()
        await self.humidity_power.async_start()
        await self.secondary_climate.async_start()
        await self.running_fans.async_start()
        await self.fan_power.async_start()
        await self.native_air_mode.async_start()
        self._active = True
        self._unsubs.extend((
            self.hass.bus.async_listen(EVENT_STATE_CHANGED, self._on_state_changed),
            self.hass.bus.async_listen("entity_registry_updated", self._on_registry_changed),
            self.hass.bus.async_listen("device_registry_updated", self._on_registry_changed),
            self.hass.bus.async_listen("area_registry_updated", self._on_registry_changed),
            async_track_time_interval(self.hass, self._on_interval, timedelta(minutes=5)),
            async_track_time_interval(self.hass, self._on_fast_climate_interval, timedelta(seconds=30)),
        ))
        self._recalculate(initial=True)

    @callback
    def _pid_updated(self) -> None:
        """Update existing single sensor dashboard without creating PID entities."""
        if not self._active:
            return
        saved = self.settings.get(CONF_PID_ROOMS, {})
        if not isinstance(saved, dict):
            return
        environment = {key: dict(val) for key, val in self.plan.environment.items()}
        for area, status in self.pid.configured_statuses(saved).items():
            environment.setdefault(area, {})["climate_pid"] = status
        self.plan = replace(self.plan, environment=environment)
        async_dispatcher_send(self.hass, f"{SIGNAL_UPDATED}_{self.entry.entry_id}")

    def climate_diagnostics(self, area:str|None=None) -> dict[str,Any]:
        """Read-only commissioning evidence for the explicitly configured rooms."""
        configured=self.settings.get(CONF_CLIMATE_ROOMS,{})
        plans={key:value.get("climate_plan",{})
               for key,value in self.plan.environment.items()
               if isinstance(value,dict)}
        return climate_commissioning_report(
            self.hass,configured,plans,area=area,
        )

    async def async_climate_control(self, area:str, action:str) -> dict[str, Any]:
        configured=self.settings.get(CONF_CLIMATE_ROOMS,{})
        if not isinstance(configured,dict) or not isinstance(configured.get(area),dict):
            return {"accepted":False,"reason":"room_not_configured"}
        profile=configured[area]
        if profile.get("enabled") is not True or profile.get("allow_actuation") is not True:
            return {"accepted":False,"reason":"climate_control_not_enabled"}
        if profile.get("controller") in ("on_off","pwm","proportional"):
            primary=await self.direct_climate.command(area,action,configured)
        elif profile.get("controller")=="environment":
            primary={"accepted":True,"reason":"environment_only_no_primary_hvac"}
        elif profile.get("controller")=="device" and profile.get("mode")=="dry":
            primary={"accepted":True,"reason":"dry_only_no_temperature_controller"}
        else:
            primary=await self.native_climate.command(area,action)
        results={"primary":primary}
        if profile.get("humidity_setpoint_auto") is True:
            results["humidity_setpoint"]=await self.native_humidity.command(area,action)
        if profile.get("humidity_power_auto") is True:
            results["humidity_power"]=await self.humidity_power.command(area,action)
        if profile.get("secondary_climate_setpoint_auto") is True:
            results["secondary_climate"]=await self.secondary_climate.command(area,action)
        if profile.get("fan_speed_auto") is True:
            results["fan_speed"]=await self.running_fans.command(area,action)
        if profile.get("fan_power_auto") is True:
            results["fan_power"]=await self.fan_power.command(area,action)
        if profile.get("dry_fan_mode_auto") is True:
            results["native_air_mode"]=await self.native_air_mode.command(area,action)
        if len(results)==1:
            return primary
        return {**primary,**results,
                "accepted":all(r.get("accepted") is True for r in results.values())}

    @callback
    def _air_mode_updated(self) -> None:
        if not self._active:
            return
        environment={key:dict(value) for key,value in self.plan.environment.items()}
        for area,status in self.native_air_mode.statuses.items():
            if area in environment and "climate_plan" in environment[area]:
                plan={**environment[area]["climate_plan"],
                      "native_air_mode_actuation":status}
                environment[area]["climate_plan"]=plan
        self.plan=replace(self.plan,environment=environment)
        async_dispatcher_send(self.hass,f"{SIGNAL_UPDATED}_{self.entry.entry_id}")

    @callback
    def _fan_power_updated(self) -> None:
        if not self._active:
            return
        environment={key:dict(value) for key,value in self.plan.environment.items()}
        for area,status in self.fan_power.statuses.items():
            if area in environment and "climate_plan" in environment[area]:
                plan={**environment[area]["climate_plan"],
                      "fan_power_actuation":status}
                environment[area]["climate_plan"]=plan
        self.plan=replace(self.plan,environment=environment)
        async_dispatcher_send(self.hass,f"{SIGNAL_UPDATED}_{self.entry.entry_id}")

    @callback
    def _fan_updated(self) -> None:
        if not self._active:
            return
        environment={key:dict(value) for key,value in self.plan.environment.items()}
        for area,status in self.running_fans.statuses.items():
            if area in environment and "climate_plan" in environment[area]:
                plan={**environment[area]["climate_plan"],
                      "fan_actuation":status}
                environment[area]["climate_plan"]=plan
        self.plan=replace(self.plan,environment=environment)
        async_dispatcher_send(self.hass,f"{SIGNAL_UPDATED}_{self.entry.entry_id}")

    @callback
    def _secondary_updated(self) -> None:
        if not self._active:
            return
        environment={key:dict(value) for key,value in self.plan.environment.items()}
        for area,status in self.secondary_climate.statuses.items():
            if area in environment and "climate_plan" in environment[area]:
                plan={**environment[area]["climate_plan"],
                      "secondary_actuation":status}
                environment[area]["climate_plan"]=plan
        self.plan=replace(self.plan,environment=environment)
        async_dispatcher_send(self.hass,f"{SIGNAL_UPDATED}_{self.entry.entry_id}")

    @callback
    def _humidity_power_updated(self) -> None:
        if not self._active:
            return
        environment={key:dict(value) for key,value in self.plan.environment.items()}
        for area,status in self.humidity_power.statuses.items():
            if area in environment and "climate_plan" in environment[area]:
                plan={**environment[area]["climate_plan"],
                      "humidity_power_actuation":status}
                environment[area]["climate_plan"]=plan
        self.plan=replace(self.plan,environment=environment)
        async_dispatcher_send(self.hass,f"{SIGNAL_UPDATED}_{self.entry.entry_id}")

    @callback
    def _humidity_updated(self) -> None:
        if not self._active:
            return
        environment={key:dict(value) for key,value in self.plan.environment.items()}
        for area,status in self.native_humidity.statuses.items():
            if area in environment and "climate_plan" in environment[area]:
                plan={**environment[area]["climate_plan"],
                      "humidity_actuation":status}
                environment[area]["climate_plan"]=plan
        self.plan=replace(self.plan,environment=environment)
        async_dispatcher_send(self.hass,f"{SIGNAL_UPDATED}_{self.entry.entry_id}")

    @callback
    def _direct_climate_updated(self) -> None:
        if not self._active:
            return
        environment={key:dict(val) for key,val in self.plan.environment.items()}
        for area,status in self.direct_climate.statuses.items():
            if area in environment and "climate_plan" in environment[area]:
                plan={**environment[area]["climate_plan"],"actuation":status}
                environment[area]["climate_plan"]=plan
        self.plan=replace(self.plan,environment=environment)
        async_dispatcher_send(self.hass,f"{SIGNAL_UPDATED}_{self.entry.entry_id}")

    async def async_pid_control(self, area: str, action: str) -> dict[str, Any]:
        configs = self.settings.get(CONF_PID_ROOMS, {})
        return await self.pid.async_action(area, action, configs)

    @callback
    def _on_registry_changed(self, _event: Event) -> None:
        self._recalculate()

    @callback
    def _on_interval(self, _now: Any) -> None:
        self._recalculate()

    @callback
    def _on_fast_climate_interval(self, _now: Any) -> None:
        # PWM edges require faster scheduling than the 5-minute air-quality
        # refresh. Use the last validated plan; _tick rechecks sensor freshness.
        if not self._active:
            return
        settings=self.settings.get(CONF_CLIMATE_ROOMS,{})
        if not isinstance(settings,dict) or not settings:
            return
        plans={area:item.get("climate_plan",{})
               for area,item in self.plan.environment.items()
               if isinstance(item,dict) and "climate_plan" in item}
        # Fan power/speed checks use a strict 120-second outdoor-air evidence
        # lifetime. Refresh the *whole* scientific/environmental plan before
        # it expires, not only every five minutes. This recalculation also
        # recomputes unified arbitration and dispatches all controllers once.
        now=time()
        active_air_rooms=[
            area for area,conf in settings.items()
            if isinstance(conf,dict) and conf.get("enabled") is True
            and (conf.get("fan_speed_auto") is True or
                 conf.get("fan_power_auto") is True)
        ]
        if active_air_rooms and any(
            isinstance(plans.get(area),dict) and bool(plans[area])
            and (
                not isinstance(plans[area].get("air_evidence_at"),(int,float))
                or not 0 <= now-plans[area]["air_evidence_at"] < 90
            )
            for area in active_air_rooms
        ):
            self._recalculate()
            return
        pid_settings=self.settings.get(CONF_PID_ROOMS,{})
        self.direct_climate.schedule(settings,plans,pid_rooms=pid_settings,native_rooms=settings)
        self.native_humidity.schedule(settings,plans)
        self.humidity_power.schedule(settings,plans)
        self.secondary_climate.schedule(settings,plans,pid_rooms=pid_settings)
        self.running_fans.schedule(settings,plans)
        self.fan_power.schedule(settings,plans)
        self.native_air_mode.schedule(settings,plans)

    @callback
    def _on_state_changed(self, event: Event) -> None:
        if event.data.get("entity_id") in self._tracked:
            self._recalculate()

    def _automatic_channels_enabled(self) -> bool:
        """Automatic announcements are independent from AI/Hub selection."""
        settings = self.settings
        return bool(settings.get(CONF_AUTO_NOTIFY) or settings.get(CONF_AUTO_TTS))

    @property
    def repeat_minutes(self) -> int:
        """Missing options from older installs inherit ten minutes."""
        raw = self.settings.get(CONF_REPEAT_MINUTES, DEFAULT_REPEAT_MINUTES)
        try:
            value = int(raw)
        except (TypeError, ValueError, OverflowError):
            return DEFAULT_REPEAT_MINUTES
        return value if 0 <= value <= MAX_REPEAT_MINUTES else DEFAULT_REPEAT_MINUTES

    @callback
    def _recalculate(self, *, initial: bool = False) -> None:
        if not self._active:
            return
        new_plan = self._capture()
        if new_plan != self.plan:
            self.plan = new_plan
            async_dispatcher_send(self.hass, f"{SIGNAL_UPDATED}_{self.entry.entry_id}")

        configured_pid = self.settings.get(CONF_PID_ROOMS, {})
        self.pid.schedule(new_plan.rooms, configured_pid, initial=initial)
        native_configs=self.settings.get(CONF_CLIMATE_ROOMS,{})
        plans={area:data.get("climate_plan",{})
               for area,data in new_plan.environment.items()
               if isinstance(data,dict)}
        self.native_climate.schedule(
            native_configs, plans, pid_rooms=configured_pid,
        )
        self.direct_climate.schedule(
            native_configs, plans, pid_rooms=configured_pid,
            native_rooms=native_configs,
        )
        self.native_humidity.schedule(native_configs, plans)
        self.humidity_power.schedule(native_configs, plans)
        self.secondary_climate.schedule(native_configs, plans,
                                        pid_rooms=configured_pid)
        self.running_fans.schedule(native_configs,plans)
        self.fan_power.schedule(native_configs,plans)
        self.native_air_mode.schedule(native_configs,plans)

        previous = self._active_actions
        notices=(*new_plan.recommendations,*new_plan.climate_recommendations)
        current = {
            rec.area_id: (rec.action_signature, rec.reason_signature)
            for rec in notices
        }
        for area_id in previous.keys() - current.keys():
            self._cancel_pending(area_id)
            self._cancel_repeat(area_id)
        # Install the current keys before arming timers, so callbacks always
        # recheck the latest action and cause.
        self._active_actions = current
        for rec in notices:
            area_id = rec.area_id
            new_keys = current[area_id]
            old_keys = previous.get(area_id)
            if old_keys is None or old_keys[0] != new_keys[0]:
                self._cancel_pending(area_id)
                self._cancel_repeat(area_id)
                if not initial or rec.action == "close":
                    # Urgent close is immediate; opening needs 90 seconds
                    # of stable conditions (same as before).
                    self._queue_automatic(area_id, *new_keys, action=rec.action)
                else:
                    # A pre-existing open recommendation at HA startup should
                    # not announce immediately, but it can remind later.
                    self._schedule_repeat(area_id, *new_keys)
            elif old_keys[1] != new_keys[1]:
                # A different cause must persist for a *new* full interval.
                self._cancel_repeat(area_id)
                if area_id in self._pending_unsubs:
                    self._cancel_pending(area_id)
                    self._queue_automatic(area_id, *new_keys, action=rec.action)
                else:
                    self._schedule_repeat(area_id, *new_keys)

    @callback
    def _queue_automatic(
        self, area_id: str, action_key: str, reason_key: str, *, action: str
    ) -> None:
        if not self._automatic_channels_enabled():
            return
        delay = 0 if action == "close" else ANNOUNCE_OPEN_STABLE_SECONDS
        self._pending_unsubs[area_id] = async_call_later(
            self.hass, delay,
            callback(lambda _now: self._execute_automatic(area_id, action_key, reason_key)),
        )

    @callback
    def _schedule_repeat(
        self, area_id: str, action_key: str, reason_key: str
    ) -> None:
        minutes = self.repeat_minutes
        if (
            minutes == 0 or not self._active
            or not self._automatic_channels_enabled()
            or self._active_actions.get(area_id) != (action_key, reason_key)
            or area_id in self._repeat_unsubs
        ):
            return
        self._repeat_unsubs[area_id] = async_call_later(
            self.hass, minutes * 60,
            callback(lambda _now: self._execute_automatic(
                area_id, action_key, reason_key, repeat=True
            )),
        )

    @callback
    def _execute_automatic(
        self, area_id: str, action_key: str, reason_key: str,
        *, repeat: bool = False,
    ) -> None:
        """Re-evaluate at the deadline before announcing a persistent cause."""
        (self._repeat_unsubs if repeat else self._pending_unsubs).pop(area_id, None)
        if not self._active:
            return
        self._recalculate()
        if (
            self._active_actions.get(area_id) != (action_key, reason_key)
            or not self._automatic_channels_enabled()
        ):
            return
        rec = next(
            (rec for rec in
             (*self.plan.recommendations,*self.plan.climate_recommendations)
             if rec.area_id == area_id),
            None,
        )
        if rec is None:
            return
        if (
            not repeat and rec.action == "open"
            and monotonic() - self._last_sent.get(action_key, float("-inf"))
            < ANNOUNCE_COOLDOWN_SECONDS
        ):
            # Keep the existing anti-flapping cooldown for *new* open events.
            # Timed reminders deliberately bypass it (10 < 15 minutes).
            self._schedule_repeat(area_id, action_key, reason_key)
            return
        task = self.hass.async_create_task(
            self._send_automatic(area_id, action_key, reason_key)
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _send_automatic(
        self, area_id: str, action_key: str, reason_key: str
    ) -> None:
        """Serialize each room's reminder relative to completed submission."""
        try:
            if self._active_actions.get(area_id) != (action_key, reason_key):
                return
            result = await self.async_announce(channels="auto", areas=[area_id])
            if result.get("submitted", 0):
                self._last_sent[action_key] = monotonic()
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.exception("Air quality announcement failed for room %s", area_id)
        finally:
            # No overlapping sends, and no delayed reminders for resolved or
            # changed causes. Failed outputs are retried at most once/interval.
            self._schedule_repeat(area_id, action_key, reason_key)

    @callback
    def _cancel_pending(self, area_id: str | None = None) -> None:
        selected = (
            list(self._pending_unsubs)
            if area_id is None else [area_id]
        )
        for key in selected:
            unsubscribe = self._pending_unsubs.pop(key, None)
            if unsubscribe is not None:
                try:
                    unsubscribe()
                except Exception:
                    _LOGGER.exception("Could not cancel pending announcement for %s",key)

    @callback
    def _cancel_repeat(self, area_id: str | None = None) -> None:
        selected = (
            list(self._repeat_unsubs)
            if area_id is None else [area_id]
        )
        for key in selected:
            unsubscribe = self._repeat_unsubs.pop(key, None)
            if unsubscribe is not None:
                try:
                    unsubscribe()
                except Exception:
                    _LOGGER.exception("Could not cancel repeating announcement for %s",key)

    async def async_stop(self) -> None:
        """Unload every controller and HA listener, even after one failure.

        A failed Store flush in one native HVAC controller must not prevent
        unrelated fan, humidity, PID or sensor listeners from stopping. Never
        convert a teardown failure into permission to re-energize equipment.
        """
        self._active = False
        controllers = (
            ("pid",self.pid),("native_climate",self.native_climate),
            ("direct_climate",self.direct_climate),
            ("native_humidity",self.native_humidity),
            ("humidity_power",self.humidity_power),
            ("secondary_climate",self.secondary_climate),
            ("running_fans",self.running_fans),
            ("fan_power",self.fan_power),
            ("native_air_mode",self.native_air_mode),
        )
        try:
            outcomes = await asyncio.gather(
                *(controller.async_stop() for _,controller in controllers),
                return_exceptions=True,
            )
            for (name,_),outcome in zip(controllers,outcomes):
                if isinstance(outcome,BaseException):
                    _LOGGER.error(
                        "Controller %s failed while unloading: %r",
                        name,outcome,
                    )
        finally:
            # Always release timers/listeners and cancel outstanding manager
            # tasks, including if HA cancelled an in-progress unload.
            self._cancel_pending()
            self._cancel_repeat()
            self._active_actions.clear()
            for unsubscribe in tuple(self._unsubs):
                try:
                    unsubscribe()
                except Exception:
                    _LOGGER.exception("Could not release Home Assistant listener")
            self._unsubs.clear()
            pending=tuple(self._tasks)
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending,return_exceptions=True)
            self._tasks.clear()
            if self._environment_store is not None:
                try:
                    await self._environment_store.async_save(
                        self._environment_history.snapshot()
                    )
                except Exception:
                    _LOGGER.exception(
                        "Could not flush bounded environment history"
                    )

    def _targets_in_room(self, configured: list[str], area_id: str) -> list[str]:
        """Only configured room outputs or explicitly unassigned/general ones."""
        return [
            entity_id for entity_id in configured
            if (area := entity_area(self.hass, entity_id)) is None or area == area_id
        ]

    async def async_announce(
        self, *, language: str | None = None, channels: str = "both",
        areas: list[str] | None = None,
    ) -> dict[str, Any]:
        """Deliver current recommendations, never operate motorized windows."""
        config = self.settings
        speech = (channels in ("tts", "both")) if channels != "auto" else bool(config.get(CONF_AUTO_TTS))
        visual = (channels in ("notification", "both")) if channels != "auto" else bool(config.get(CONF_AUTO_NOTIFY))
        if not speech and not visual:
            return {"submitted": 0, "reason": "Both automatic channels are disabled"}
        all_notices=(*self.plan.recommendations,*self.plan.climate_recommendations)
        if not all_notices:
            return {"submitted": 0, "reason": "No actionable window recommendations"}

        localized = self.get_language(language)
        requested_language = language or config.get(CONF_LANGUAGE, "auto")
        sent = 0
        errors: list[str] = []
        for rec in all_notices:
            if areas is not None and rec.area_id not in areas:
                continue
            title, message = announcement(rec, localized)
            prefer_hub = bool(config.get(CONF_HUB, False))
            use_ai = ai_effectively_enabled(config)
            agent = str(config.get(CONF_AI_AGENT, DEFAULT_AGENT) or DEFAULT_AGENT)

            # Hub performs its own optional AI rewrite. An explicit boolean
            # makes this single setting authoritative over Hub defaults.
            if prefer_hub:
                hub_payload = make_hub_payload(
                    rec, title, message, speech=speech, visual=visual,
                    language=requested_language, use_ai=use_ai, agent_id=agent,
                )
                if hub_available(self.hass):
                    # Hub is the delivery authority while running, including
                    # its own routing failures and queue rejections. Never send
                    # duplicate or unwanted HA notifications in these cases.
                    if await async_submit_hub(self.hass, hub_payload):
                        sent += 1
                    else:
                        errors.append(
                            f"Announcement Hub did not queue the announcement for "
                            f"{rec.area_name}; routing and recovery belong to Hub"
                        )
                    continue

            # Only an unavailable or disabled Hub allows local HA delivery.
            # If Hub was running but rejected the job, we already continued.
            notify_targets = (
                self._targets_in_room(config.get(CONF_NOTIFY_TARGETS, []), rec.area_id)
                if visual else []
            )
            tts_engine = config.get(CONF_TTS_ENGINE) if speech else None
            tts_players = (
                self._targets_in_room(config.get(CONF_MEDIA_PLAYERS, []), rec.area_id)
                if speech and tts_engine else []
            )
            can_notify = bool(
                notify_targets and self.hass.services.has_service("notify", "send_message")
            )
            can_speak = bool(
                tts_engine and tts_players and self.hass.services.has_service("tts", "speak")
            )
            # HA persistent notifications are the final visual fallback only
            # when Hub is not configured/running for this call.
            system_available = bool(
                self.hass.services.has_service("persistent_notification", "create")
            )
            if use_ai and (can_notify or can_speak or (prefer_hub and system_available)):
                message = await async_rewrite_announcement(
                    self.hass, rec, message, localized, agent,
                )

            dispatched = False
            if can_notify:
                try:
                    await self.hass.services.async_call(
                        "notify", "send_message", {"message": message, "title": title},
                        target={"entity_id": notify_targets}, blocking=True,
                    )
                    sent += 1
                    dispatched = True
                except Exception as ex:
                    _LOGGER.warning("Direct notification failed: %s", ex)
                    errors.append(str(ex))

            if can_speak:
                data: dict[str, Any] = {
                    "media_player_entity_id": tts_players, "message": message
                }
                if requested_language != "auto":
                    state = self.hass.states.get(tts_engine)
                    supported = (
                        state.attributes.get("supported_languages", []) if state else []
                    )
                    if isinstance(supported, list) and supported:
                        canonical = lambda value: str(value).replace("_", "-").casefold()
                        base = canonical(localized).split("-", 1)[0]
                        exact = next(
                            (s for s in supported if canonical(s) == canonical(requested_language)),
                            None,
                        )
                        compatible = next(
                            (s for s in supported if canonical(s).split("-", 1)[0] == base),
                            None,
                        )
                        if exact or compatible:
                            data["language"] = exact or compatible
                        else:
                            _LOGGER.warning(
                                "TTS engine %s does not advertise language %s",
                                tts_engine, requested_language,
                            )
                    else:
                        data["language"] = requested_language
                try:
                    await self.hass.services.async_call(
                        "tts", "speak", data,
                        target={"entity_id": tts_engine}, blocking=True,
                    )
                    sent += 1
                    dispatched = True
                except Exception as ex:
                    _LOGGER.warning("Direct TTS failed: %s", ex)
                    errors.append(str(ex))

            if not dispatched and (prefer_hub or visual):
                # Update one notification per room rather than stacking alerts.
                if await async_system_notification(
                    self.hass, title, message, rec.area_id
                ):
                    sent += 1
                    dispatched = True
            if not dispatched:
                errors.append(
                    f"No available Home Assistant fallback output for {rec.area_name}"
                )
        return {"submitted": sent, "errors": errors}
