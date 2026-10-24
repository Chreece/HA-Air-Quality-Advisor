"""Opt-in Home Environment Manager per-room supervisory PID runtime.

Climate devices retain ownership of their own HVAC mode and compressor cycling.
Writes use only climate.set_temperature on explicitly selected climate entities.
No actuation occurs without positive opt-in and fresh room measurements.
Manual changes, unsupported modes, service failures and missing state fail closed.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
import math
import time
from typing import Any, Callable

from .discovery import entity_area, temperature_sensor_c
from .const import DOMAIN
from .climate_entry_ownership import foreign_owner_hold
from .pid_math import (
    DEFAULT_PID, Memory, bounded_command, finite, setpoint_c, step,
    target_from_unit, validate_settings,
)

_LOGGER = logging.getLogger(__name__)

MANUAL_GRACE_SECONDS = 120
SENSOR_MAX_AGE_MINUTES = 10
# 1 = Home Assistant ClimateEntityFeature.TARGET_TEMPERATURE.
TARGET_TEMPERATURE_FEATURE = 1


def normalized_config(config: Any) -> dict:
    return {**DEFAULT_PID, **config} if isinstance(config, dict) else dict(DEFAULT_PID)


@dataclass
class RoomControl:
    memory: Memory = field(default_factory=Memory)
    last_checked: float | None = None
    last_sent: float | None = None


class ClimatePidCoordinator:
    """Serialized service writes and restart-persistent manual pause latches."""

    def __init__(self, hass: Any, entry_id: str, *, report_changed: Callable[[], None],
                 clock: Callable[[], float] | None = None) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self._report_changed = report_changed
        self._clock = clock or time.time
        self._rooms: dict[str, RoomControl] = {}
        self._paused: dict[str, str] = {}
        self._expected: dict[str, dict[str, dict[str, float]]] = {}
        self.statuses: dict[str, dict] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._store: Any | None = None
        self._store_ready = False
        self._active = False
        self._started_at: float | None = None

    async def async_start(self) -> None:
        """Load previous pause states BEFORE allowing any controller tick."""
        self._active = True
        self._started_at = self._clock()
        try:
            from homeassistant.helpers.storage import Store
            self._store = Store(
                self.hass, 1, f"{DOMAIN}.pid_{self.entry_id}"
            )
            data = await self._store.async_load()
        except ImportError:
            # Only the lightweight testing runtime lacks HA storage; never
            # silently act without storage in a real Home Assistant runtime.
            _LOGGER.warning("Home Assistant PID state storage unavailable; controllers remain inactive")
            self._store_ready = False
            return
        except Exception:
            _LOGGER.exception("PID state could not be loaded; all climate control suspended")
            self._store_ready = False
            return
        if isinstance(data, dict) and data.get("version") == 1:
            pauses = data.get("paused", {})
            if isinstance(pauses, dict):
                self._paused = {area: reason for area, reason in pauses.items()
                                if isinstance(area, str) and isinstance(reason, str)}
            expected = data.get("expected", {})
            if isinstance(expected, dict):
                for area, items in expected.items():
                    if not isinstance(area, str) or not isinstance(items, dict):
                        continue
                    entries = {}
                    for entity, item in items.items():
                        if not isinstance(entity, str) or not entity.startswith("climate.") or not isinstance(item, dict):
                            continue
                        value = finite(item.get("value"), -30, 150)
                        stamp = finite(item.get("when"), 0, 1e13)
                        if value is not None and stamp is not None:
                            entries[entity] = {"value": value, "when": stamp}
                    if entries:
                        self._expected[area] = entries
        self._store_ready = True

    async def async_stop(self) -> None:
        self._active = False
        active = tuple(self._tasks.values())
        for task in active:
            task.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)
        self._tasks.clear()
        if self._store_ready and self._store is not None:
            try:
                await self._store.async_save(self._snapshot())
            except Exception:
                _LOGGER.exception("Could not save PID pause/command state")

    def _snapshot(self) -> dict:
        return {"version": 1, "paused": self._paused, "expected": self._expected}

    def _save(self) -> None:
        if self._store is not None:
            self._store.async_delay_save(self._snapshot, 2)

    def _set_status(self, area: str, state: str, **details: Any) -> None:
        latest = {"status": state, **details}
        if self.statuses.get(area) == latest:
            return
        self.statuses[area] = latest
        if self._active:
            self._report_changed()

    def configured_statuses(self, settings: dict[str, Any]) -> dict[str, dict]:
        result = {}
        for area, item in settings.items():
            config = normalized_config(item)
            if config["enabled"]:
                result[area] = self.statuses.get(area, {
                    "status": "waiting_for_first_control_cycle",
                    "mode": config["mode"], "target_c": config["target_c"],
                })
            else:
                result[area] = {"status": "disabled"}
        return result

    @staticmethod
    def _targets(config: dict) -> tuple[str, ...]:
        source = config.get("climate_entities")
        if source is None:
            source = [config.get("climate_entity")] if config.get("climate_entity") else []
        if not isinstance(source, (list, tuple)):
            return ()
        targets = [s for s in source if isinstance(s, str) and s.startswith("climate.")]
        return tuple(dict.fromkeys(targets))

    def _duplicate_targets(self, settings: dict) -> set[str]:
        seen, duplicates = set(), set()
        for config in settings.values():
            if not isinstance(config, dict) or not config.get("enabled"):
                continue
            for entity in self._targets(config):
                if entity in seen:
                    duplicates.add(entity)
                seen.add(entity)
        return duplicates

    def schedule(self, rooms: tuple, settings: dict[str, Any], *,
                 initial: bool = False) -> None:
        """Called by manager after capture. Never mutate HA state in this method."""
        if not self._active or not isinstance(settings, dict):
            return
        found = {r.area_id: r for r in rooms}
        active = {area: config for area, config in settings.items()
                  if isinstance(config, dict) and config.get("enabled")}
        duplicates = self._duplicate_targets(active)
        for area, config in settings.items():
            if not isinstance(config, dict) or not config.get("enabled"):
                self._set_status(area, "disabled")
                continue
            if not self._store_ready:
                self._set_status(area, "storage_unavailable")
                continue
            if any(e in duplicates for e in self._targets(config)):
                self._set_status(area, "duplicate_target")
                continue
            if area not in found:
                self._set_status(area, "monitored_room_missing")
                continue
            if area in self._paused:
                self._set_status(area, "paused", reason=self._paused[area])
                continue
            if initial:
                self._set_status(area, "startup_warmup")
                continue
            current = self._rooms.setdefault(area, RoomControl())
            now = self._clock()
            conf = normalized_config(config)
            period = finite(conf.get("sample_seconds"), 120, 3600)
            if period is None:
                self._set_status(area, "invalid_sample_seconds")
                continue
            if current.last_checked is not None and now - current.last_checked < period * 0.75:
                continue
            task = self._tasks.get(area)
            if task is not None and not task.done():
                continue
            task = self.hass.async_create_task(self._tick(area, found[area], conf, now))
            self._tasks[area] = task
            def cleanup(finished: asyncio.Task, key: str = area) -> None:
                if self._tasks.get(key) is finished:
                    self._tasks.pop(key, None)
                if not finished.cancelled():
                    try:
                        finished.result()
                    except Exception:
                        _LOGGER.exception("PID control task failed for area %s", key)
                        self._set_status(key, "controller_exception")
            task.add_done_callback(cleanup)

    async def async_prepare_reconfigure(self, area: str) -> None:
        """Reset integral/derivative memory only between safe PID cycles.

        A control task might have sent a thermostat setpoint but not yet
        persisted acknowledgement. Never cancel that task during a write:
        reject the editor request and let the user retry when it completes.
        Durable manual pause and expected-ack state remain unchanged.
        """
        task = self._tasks.get(area)
        if task is not None and not task.done():
            raise RuntimeError("PID command still in progress; retry this setting")
        self._rooms.pop(area, None)
        self._set_status(area, "startup_warmup", reason="tuning_changed")

    async def async_action(self, area: str, action: str,
                           configurations: dict[str, Any]) -> dict:
        """Explicit user actions. A paused PID NEVER resumes just because time passed."""
        if action not in ("pause", "resume", "reset"):
            return {"accepted": False, "reason": "invalid_action"}
        entry = configurations.get(area) if isinstance(configurations, dict) else None
        if not isinstance(entry, dict) or not entry.get("enabled"):
            return {"accepted": False, "reason": "room_controller_not_enabled"}
        if not self._store_ready:
            return {"accepted": False, "reason": "storage_unavailable"}
        task = self._tasks.get(area)
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if action == "pause":
            self._paused[area] = "user_pause"
            self._set_status(area, "paused", reason="user_pause")
        elif action == "reset":
            self._rooms.pop(area, None)
            self._paused[area] = "reset_requires_resume"
            self._expected.pop(area, None)
            self._set_status(area, "paused", reason="reset_requires_resume")
        else:
            self._paused.pop(area, None)
            self._rooms.pop(area, None)
            self._expected.pop(area, None)
            self._set_status(area, "startup_warmup")
        self._save()
        return {"accepted": True, "area": area, "action": action}

    async def _pause(self, area: str, reason: str) -> None:
        self._paused[area] = reason
        self._rooms.pop(area, None)
        self._save()
        self._set_status(area, "paused", reason=reason)

    async def _tick(self, area: str, room: Any, settings: dict, now: float) -> None:
        if not self._active or not self._store_ready or area in self._paused:
            return
        current = self._rooms.setdefault(area, RoomControl())
        ok, why = validate_settings(settings)
        if not ok:
            self._set_status(area, "invalid_configuration", reason=why)
            return
        entities = self._targets(settings)
        sensor = settings.get("temperature_entity")
        if not entities or not isinstance(sensor, str) or not sensor.startswith("sensor."):
            self._set_status(area, "missing_temperature_or_climate")
            return
        sensor_area = entity_area(self.hass, sensor)
        if sensor_area is not None and sensor_area != area:
            self._set_status(area, "temperature_sensor_wrong_area")
            return
        if settings.get("pause_on_window_open", True):
            if not room.windows or any(w.opened is not False for w in room.windows):
                self._set_status(area, "window_open_or_unknown")
                return
        # 10 minutes maximum regardless of the much larger monitoring max_age.
        temp = temperature_sensor_c(self.hass, sensor, SENSOR_MAX_AGE_MINUTES)
        if temp is None or not math.isfinite(temp) or not -10 <= temp <= 50:
            self._set_status(area, "temperature_unavailable_or_stale")
            return
        if self._started_at is not None and now - self._started_at < max(120, settings["sample_seconds"]):
            self._set_status(area, "startup_warmup")
            return
        if not self.hass.services.has_service("climate", "set_temperature"):
            self._set_status(area, "climate_service_unavailable")
            return
        prepared = []
        for entity in entities:
            area_ref = entity_area(self.hass, entity)
            if area_ref is not None and area_ref != area:
                self._set_status(area, "climate_device_wrong_area", entity=entity)
                return
            state = self.hass.states.get(entity)
            if state is None or state.state in ("unknown", "unavailable"):
                self._set_status(area, "climate_unavailable", entity=entity)
                return
            mode = state.state.lower()
            if mode != settings["mode"]:
                if mode in ("off", "heat", "cool", "auto", "heat_cool"):
                    await self._pause(area, "manual_hvac_mode_change")
                else:
                    self._set_status(area, "unsupported_hvac_mode", entity=entity)
                return
            attributes = state.attributes
            try:
                features = int(attributes.get("supported_features", 0))
            except (TypeError, ValueError, OverflowError):
                features = 0
            if not features & TARGET_TEMPERATURE_FEATURE:
                self._set_status(area, "device_does_not_support_single_setpoint", entity=entity)
                return
            preset = str(attributes.get("preset_mode") or "").strip().casefold()
            if preset not in ("", "none", "manual"):
                self._set_status(area, "active_device_preset", entity=entity, preset=preset)
                return
            unit = attributes.get("temperature_unit")
            observed = finite(attributes.get("temperature"), -30, 150)
            minimum = finite(attributes.get("min_temp"), -30, 150)
            maximum = finite(attributes.get("max_temp"), -30, 150)
            device_step = finite(attributes.get("target_temp_step"), 0.1, 10)
            if device_step is None:
                device_step = 0.5 if unit in ("°C", "C") else 1.0 if unit in ("°F", "F") else None
            if (unit not in ("°C", "C", "°F", "F") or observed is None or
                    minimum is None or maximum is None or minimum >= maximum or device_step is None):
                self._set_status(area, "device_limits_or_temperature_unknown", entity=entity)
                return
            expected = self._expected.get(area, {}).get(entity)
            if expected is not None:
                tolerance = max(device_step * 0.51, 0.05)
                if abs(observed - expected["value"]) > tolerance:
                    if now - expected["when"] < MANUAL_GRACE_SECONDS:
                        self._set_status(area, "waiting_for_device_ack", entity=entity)
                    else:
                        await self._pause(area, "manual_temperature_change_or_unacknowledged_write")
                    return
            observed_c = target_from_unit(observed, unit)
            if observed_c is None:
                self._set_status(area, "device_unit_conversion_failed", entity=entity)
                return
            prepared.append((entity, state, unit, observed_c, observed,
                             minimum, maximum, device_step))
        current.last_checked = now
        result = step(temp, settings["target_c"], now, settings["mode"],
                      settings["kp"], settings["ki"], settings["kd"],
                      settings["sample_seconds"], current.memory)
        if result.status != "ready":
            current.memory = result.memory
            self._set_status(area, result.status, temperature_c=round(temp, 2),
                             target_c=settings["target_c"], mode=settings["mode"])
            return
        desired = setpoint_c(settings["target_c"], result.demand_percent,
                             settings["mode"], settings["offset_c"],
                             settings["min_setpoint_c"], settings["max_setpoint_c"])
        if desired is None:
            self._set_status(area, "invalid_setpoint_result")
            return
        planned = []
        for (entity, state, unit, actual_c, _native, minimum, maximum, device_step) in prepared:
            command_state, native = bounded_command(
                desired, actual_c, max_change_c=settings["max_change_c"],
                min_change_c=settings["min_change_c"], unit=unit,
                device_min=minimum, device_max=maximum, device_step=device_step,
            )
            if command_state == "command":
                planned.append((entity, native))
            elif command_state != "no_meaningful_change":
                self._set_status(area, command_state, entity=entity)
                return
        current.memory = result.memory
        if not planned:
            self._set_status(area, "at_device_setpoint", demand_percent=result.demand_percent,
                             measured_c=round(temp, 2), desired_setpoint_c=round(desired, 2))
            return
        for entity, native in planned:
            if not self._active or area in self._paused:
                return
            from .equipment_model import legacy_hold
            if hold := legacy_hold(self.hass, self.entry_id, entity):
                self._set_status(area, hold, entity=entity)
                return
            other_entry=foreign_owner_hold(self.hass,self.entry_id,entity)
            if other_entry is not None:
                self._set_status(
                    area,"cross_entry_control_hold",
                    entity=entity,reason=other_entry,
                )
                return
            try:
                # No hvac_mode field: never power on/off or switch compressor modes.
                await asyncio.wait_for(
                    self.hass.services.async_call(
                        "climate", "set_temperature", {"temperature": native},
                        target={"entity_id": entity}, blocking=True,
                    ),
                    timeout=25,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.exception("PID climate.set_temperature failed for %s", entity)
                await self._pause(area, "climate_service_failure")
                return
            self._expected.setdefault(area, {})[entity] = {"value": native, "when": now}
            self._save()
        current.last_sent = now
        self._set_status(
            area, "controlling", mode=settings["mode"],
            measured_c=round(temp, 2), target_c=settings["target_c"],
            desired_setpoint_c=round(desired, 2),
            demand_percent=result.demand_percent,
            commanded={entity: native for entity, native in planned},
            proportional=result.proportional,
            integral=result.integral, derivative=result.derivative,
            note="supervisory_setpoint_only_no_hvac_mode_switching",
        )
