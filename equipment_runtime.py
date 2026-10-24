"""One serialized, durable command owner per managed physical device.

All new control is opt-in through the controller-mode selector. Existing room
owners are never silently replaced. Power commands require the original
commissioning grant, native capabilities, dwell and live room evidence. PID
uses slow time proportioning for binary outputs, percentages for modulating
outputs, or bounded native setpoint trim when only setpoint control is granted.
"""
from __future__ import annotations

import asyncio
from .config_data import mutable_copy as deepcopy
from dataclasses import asdict
import logging
import time
from typing import Any, Callable

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, SIGNAL_UPDATED, CONF_EXCLUDED_INDOOR
from .device_hierarchy import configured_sources
from .discovery import entity_area, reading, temperature_sensor_c
from .climate_arbitration import _contact_interlock, _physical_climate_conflict
from .climate_entry_ownership import foreign_owner_hold
from .occupancy_policy import live_device_permission, room_presence, sleep_presence
from .pid_math import finite, target_from_unit, target_to_unit, quantize_target
from .pid_output_allocator import fan_speed_for_pid, ordered_fan_stages, percentage_output_requested
from .pid_fan_capacity import (
    allocate as allocate_fan_capacity,
    build_model as build_fan_capacity_model,
    model_is_valid as fan_capacity_model_is_valid,
)
from .pid_calibration import tune as tune_pid
from . import equipment_model as model

_LOGGER = logging.getLogger(__name__)
ACK_SECONDS = 120
STARTUP_SECONDS = 300
MONITORED = ("temperature", "target_temp_low", "target_temp_high", "humidity",
             "fan_mode", "percentage", "preset_mode", "swing_mode", "swing_horizontal_mode",
             "supported_features", "temperature_unit", "target_temp_step", "min_temp", "max_temp",
             "hvac_modes", "fan_modes", "swing_modes", "swing_horizontal_modes", "preset_modes",
             "min_humidity", "max_humidity", "percentage_step", "min", "max", "step", "unit_of_measurement")
LEGACY_DRIVERS = ("pid", "native_climate", "direct_climate", "native_humidity",
                  "humidity_power", "secondary_climate", "running_fans", "fan_power", "native_air_mode")


def output_off(state: Any) -> bool:
    if state is None:
        return False
    if getattr(state, "domain", "") in ("number", "input_number"):
        return finite(state.state, 0, 100) == 0
    return state.state == "off"


def snapshot(state: Any) -> dict | None:
    if state is None or state.state in ("unknown", "unavailable"):
        return None
    return {"state": state.state, "attributes": {
        k: state.attributes[k] for k in MONITORED if k in state.attributes}}


def matches(state: Any, expected: dict) -> bool:
    if state is None:
        return False
    if "state" in expected and state.state != expected["state"]:
        if getattr(state, "domain", "") not in ("number", "input_number") or (
            finite(state.state, 0, 100) is None or finite(expected["state"], 0, 100) is None
            or abs(float(state.state)-float(expected["state"])) > .05
        ):
            return False
    for key, value in expected.get("attributes", {}).items():
        actual = state.attributes.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if finite(actual, -1e8, 1e8) is None or abs(float(actual)-value) > (.5 if key == "percentage" else .05):
                return False
        elif actual != value:
            return False
    return True


class EquipmentRuntime:
    """Independent tasks for independent devices; one pending command each."""

    def __init__(self, manager: Any, *, clock: Callable[[], float] | None = None) -> None:
        self.manager, self.hass = manager, manager.hass
        self.clock = clock or time.time
        self.records: dict[str, dict] = {}
        self.statuses: dict[str, dict] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._memory: dict[str, tuple[Any, model.PIDMemory, float]] = {}
        self._fan_allocations: dict[str, dict] = {}
        self._store = None
        self._ready = False
        self._active = False
        self._started = self.clock()
        self._save_lock = asyncio.Lock()
        self._commands = asyncio.Semaphore(8)
        self._invalidated: set[str] = set()

    def _status(self, spec: Any, status: str, **data: Any) -> None:
        key = spec if isinstance(spec, str) else spec.identifier
        value = {"status": status, **data}
        if key in self._fan_allocations:
            value["pid_fan_capacity"] = self._fan_allocations[key]
        if self.statuses.get(key) == value:
            return
        self.statuses[key] = value
        if self._active:
            from homeassistant.helpers.dispatcher import async_dispatcher_send
            async_dispatcher_send(self.hass, f"{SIGNAL_UPDATED}_{self.manager.entry.entry_id}")

    async def _save(self) -> None:
        if self._store is None or not self._ready:
            raise HomeAssistantError("Controller storage is unavailable")
        async with self._save_lock:
            try:
                await self._store.async_save({"version": 1, "records": deepcopy(self.records)})
            except Exception as error:
                self._ready = False
                raise HomeAssistantError("Controller state could not be persisted; no command sent") from error

    async def async_start(self) -> None:
        self._active = True
        self._started = self.clock()
        try:
            from homeassistant.helpers.storage import Store
            self._store = Store(
                self.hass, 1, f"{DOMAIN}.equipment_{self.manager.entry.entry_id}"
            )
            saved = await self._store.async_load()
            if saved is not None and (not isinstance(saved, dict) or saved.get("version") != 1
                                      or not isinstance(saved.get("records"), dict)):
                raise ValueError("Unknown equipment state schema")
            self.records = deepcopy(saved["records"]) if saved else {}
            for key, record in self.records.items():
                if (not isinstance(key, str) or not isinstance(record, dict)
                    or not isinstance(record.get("area"), str)
                    or not isinstance(record.get("sources"), list)
                    or not all(isinstance(e, str) for e in record["sources"])
                    or not isinstance(record.get("baseline"), dict)
                    or not isinstance(record.get("power"), dict)
                    or not isinstance(record.get("off_at"), dict)):
                    raise ValueError("Invalid equipment recovery records")
                for entity, owned in record["power"].items():
                    if (entity not in record["sources"] or not isinstance(owned, dict)
                        or any(finite(owned.get(k), 0, 1e13) is None for k in ("since", "min_on", "max_on"))
                        or owned["max_on"] <= owned["min_on"]):
                        raise ValueError("Invalid power recovery history")
            self._ready = True
            for record in self.records.values():
                if record.get("pending") or record.get("power"):
                    record["paused"] = "restart_reconciliation_required"
            await self._save()
        except Exception:
            self._ready = False
            _LOGGER.exception("Equipment controller storage unavailable; new control stays inactive")

    async def async_stop(self) -> None:
        self._active = False
        tasks = tuple(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        if self._ready:
            await self._save()

    def _record(self, spec: model.ManagedDevice) -> dict:
        return self.records.setdefault(spec.identifier, {"area": spec.area_id,
            "sources": list(spec.source_entities), "source_device_id": spec.source_device_id,
            "baseline": {}, "power": {}, "off_at": {}})

    def _observed_off_since(self, entity: str, now: float | None = None) -> float:
        """Best known physical OFF timestamp, not the selector-click time."""
        now = self.clock() if now is None else now
        state = self.hass.states.get(entity)
        changed = getattr(state, "last_changed", None) if state is not None else None
        try:
            stamp = changed.timestamp() if changed is not None else None
        except (AttributeError, TypeError, ValueError, OverflowError):
            stamp = None
        stamp = finite(stamp, 0, 1e13)
        return stamp if stamp is not None and stamp <= now else now

    def _lock(self, key: str) -> asyncio.Lock:
        record = self.records.get(key)
        if record:
            group = (record["area"], record.get("source_device_id") or key)
        else:
            spec = next((s for s in model.specs(self.manager) if s.identifier == key), None)
            group = (spec.area_id, spec.source_device_id or key) if spec else key
        return self._locks.setdefault(group, asyncio.Lock())

    async def _pause(self, spec: Any, reason: str) -> None:
        self._record(spec)["paused"] = reason
        self._status(spec, "paused", reason=reason)
        await self._save()

    def _identity_ok(self, spec: model.ManagedDevice) -> bool:
        from homeassistant.helpers import entity_registry as er
        registry = er.async_get(self.hass)
        for entity in spec.source_entities:
            item = registry.async_get(entity)
            if item is None or getattr(item, "platform", None) == DOMAIN:
                return False
            if getattr(item, "device_id", None) != spec.source_device_id:
                return False
        return bool(spec.source_entities)

    def _current_spec(self, spec: model.ManagedDevice) -> bool:
        active = set(configured_sources(self.manager.settings, spec.area_id))
        return self._identity_ok(spec) and all(
            e in active and entity_area(self.hass, e) == spec.area_id
            for e in spec.source_entities)

    def _legacy_busy(self, spec: model.ManagedDevice) -> str | None:
        for key, record in self.records.items():
            if key != spec.identifier and set(record.get("sources", ())).intersection(spec.source_entities):
                if record.get("power") or record.get("pending"):
                    return "Prior device controller must reconcile this source OFF before transfer"
        for name in LEGACY_DRIVERS:
            driver = getattr(self.manager, name, None)
            task = getattr(driver, "_tasks", {}).get(spec.area_id)
            if task is not None and not task.done():
                return "Existing room controller has a write in progress"
            paused = getattr(driver, "paused", {})
            if isinstance(paused, dict) and spec.area_id in paused:
                return "Existing controller is paused; reconcile it before transferring ownership"
            for attr in ("owned", "_owned"):
                owned = getattr(driver, attr, {})
                if isinstance(owned, dict) and any(e in owned for e in spec.source_entities):
                    return "Existing power owner must reconcile this device OFF before transfer"
        return None

    async def async_update(self, spec: model.ManagedDevice, changes: dict) -> None:
        """Validate all requested edits atomically; no hidden hardware permission."""
        async with self._lock(spec.identifier):
            if not self._ready:
                raise HomeAssistantError("Controller state storage is unavailable")
            if not self._current_spec(spec):
                raise HomeAssistantError("Controller sources are no longer assigned to this area")
            cap = model.capabilities(self.manager, spec)
            if cap is None:
                raise HomeAssistantError("Device capabilities are unavailable")
            old = model.settings(self.manager, spec)
            new = {**old, **deepcopy(changes)}
            allowed = set(model.DEFAULTS) | {"fan_mode", "swing_mode", "swing_horizontal_mode",
                "sensor_verified", *model.DEVICE_SELECTS}
            if set(changes) - allowed:
                raise HomeAssistantError("Unsupported controller setting")
            if new["control_mode"] not in model.control_modes(self.manager, spec):
                raise HomeAssistantError("Unsupported control method")
            if new["pid_calibration_method"] not in model.PID_CALIBRATION_METHODS:
                raise HomeAssistantError("Unsupported deterministic PID tuning method")
            # Model fields are inert commissioning inputs. A zero means "not
            # measured yet"; it is never interpreted as a physical response.
            for key, limits in model.PID_MODEL_FIELDS.items():
                value = finite(new[key], 0, limits[1])
                if value is None or (value > 0 and value < limits[0]):
                    raise HomeAssistantError(f"Invalid PID response parameter: {key}")
                new[key] = value
            if new["pid_fan_capacity_mode"] not in model.PID_FAN_CAPACITY_METHODS:
                raise HomeAssistantError("Unsupported PID fan capacity strategy")
            direction = new["pid_fan_capacity_for_mode"]
            if direction not in ("choose", *model.PID_FAN_DIRECTIONS):
                raise HomeAssistantError("Unsupported calibrated HVAC direction")
            if direction != "choose" and direction not in cap.modes:
                raise HomeAssistantError("Fan capacity calibration direction is not a native HVAC mode")
            for key, limits in model.PID_FAN_CAPACITY_FIELDS.items():
                value = finite(new[key], 0, limits[1])
                if value is None:
                    raise HomeAssistantError(f"Invalid measured fan capacity input: {key}")
                new[key] = value
            maps = new.get("pid_fan_capacity_models")
            if not isinstance(maps, dict) or set(maps) - set(model.PID_FAN_DIRECTIONS):
                raise HomeAssistantError("Invalid per-mode PID capacity models")
            # The apply button is the sole writer of calibrated model maps.
            if "pid_fan_capacity_models" in changes and not isinstance(
                changes["pid_fan_capacity_models"], dict
            ):
                raise HomeAssistantError("Invalid calibrated fan model data")
            if (new["pid_fan_capacity_mode"] == "measured"
                    and new["control_mode"] == "pid"
                    and "pid_fan_capacity_mode" in changes):
                # Changing the *calibration edit direction* must not disable an
                # existing measured model for another HVAC mode. Only entering
                # Measured strategy or Apply requires an existing valid model.
                saved = maps.get(direction)
                if (not cap.fan_entity
                        or not fan_capacity_model_is_valid(
                            saved, mode=direction, physical_entity=cap.primary,
                            fan_entity=cap.fan_entity, percentage=cap.fan_percentage,
                            advertised_modes=cap.fan_modes)):
                    raise HomeAssistantError(
                        "Measured PID fan capacity requires a valid saved model for this exact HVAC direction"
                    )
            if new["preset"] not in model.PRESETS:
                raise HomeAssistantError("Unsupported comfort preset")
            if new["requested_mode"] is not None and new["requested_mode"] not in cap.modes:
                raise HomeAssistantError("The physical device does not support this HVAC mode")
            for key, bounds in model.NUMBER_FIELDS.items():
                number = finite(new[key], bounds[0], bounds[1])
                if number is None:
                    raise HomeAssistantError(f"Invalid controller value: {key}")
                new[key] = number
            for key in model.QUIET_FLAGS:
                if type(new[key]) is not bool or new[key] and not cap.fan_modes:
                    raise HomeAssistantError("Quiet control requires an adjustable native fan")
            if (any(new[k] for k in model.QUIET_FLAGS) and not cap.fan_percentage
                    and "low" not in cap.fan_modes and new.get("quiet_fan_mode") is None):
                raise HomeAssistantError("Select an advertised quiet fan mode before enabling quiet control")
            for key, choices in (("fan_mode", cap.fan_modes), ("quiet_fan_mode", cap.fan_modes),
                                 ("swing_mode", cap.swing_modes), ("swing_horizontal_mode", cap.swing_horizontal_modes)):
                if new.get(key) is not None and str(new[key]) not in choices:
                    raise HomeAssistantError(f"Unsupported native choice: {key}")
            table = new.get("profile_targets")
            if not isinstance(table, dict) or set(table) - {"manual"}:
                raise HomeAssistantError("Invalid profile target table")
            for profile, values in table.items():
                if not isinstance(values, dict) or set(values) - {"heat", "cool", "humidity"}:
                    raise HomeAssistantError("Invalid profile targets")
                for key, value in values.items():
                    low, high = (cap.min_humidity, cap.max_humidity) if key == "humidity" else (cap.min_temp, cap.max_temp)
                    if finite(value, low, high) is None:
                        raise HomeAssistantError("Target outside physical device limits")
                profile_config = {**new, "preset": "eco" if profile == "unoccupied" else profile}
                if profile == "manual":
                    profile_config.update(control_mode="manual", preset="none")
                band = model.targets(self.manager, spec, cap, profile_config, {})
                if band["cool"]-band["heat"] < 1:
                    raise HomeAssistantError("Heating and cooling targets must be at least 1°C apart")
            fan_table = new.get("profile_fans")
            if not isinstance(fan_table, dict) or set(fan_table) - {"manual", "home", "comfort", "away", "sleep", "eco"}:
                raise HomeAssistantError("Invalid fan profile table")
            if any(str(v) not in cap.fan_modes for v in fan_table.values()):
                raise HomeAssistantError("Unsupported native fan choice for profile")
            from .device_activation import authority_context
            soft, power = model.permission(self.manager, spec, cap)
            for key, choices in model.DEVICE_SELECTS.items():
                if new.get(key) not in choices:
                    raise HomeAssistantError(f"Unsupported device policy: {key}")
            if "sensor_verified" in changes and type(changes["sensor_verified"]) is not bool:
                raise HomeAssistantError("Sensor verification must be a boolean")
            # The selector itself authorizes only this selected native endpoint.
            # No old room-wide driver or sibling device acquires permission.
            authorizing = ("control_mode" in changes and new["control_mode"] in ("automatic", "pid", "manual")
                           and cap.domain in ("climate", "fan", "humidifier"))
            if authorizing:
                new["_native_authorization"] = authority_context(self.manager, spec)
                soft = True
                power = "off" in cap.modes
            elif "_native_authorization" in new:
                soft = new["_native_authorization"] == authority_context(self.manager, spec)
                power = soft and new.get("control_mode") in ("automatic", "pid", "manual", "off") and "off" in cap.modes
            on, off, maximum = model.timing(self.manager, spec, cap, config=new)
            if cap.domain != "fan" and maximum > 28800:
                raise HomeAssistantError("Maximum continuous runtime for this device cannot exceed 28800 seconds")
            if "requested_mode" in changes and new["requested_mode"] is not None:
                state = self.hass.states.get(cap.primary)
                requested = new["requested_mode"]
                change_power = state is not None and ((cap.domain == "climate" and state.state != requested)
                    or cap.domain != "climate" and output_off(state) != (requested == "off"))
                if change_power and not power and not (requested == "off" and self._record(spec).get("power")):
                    raise HomeAssistantError("This controller is not authorized to change the physical mode")
            # Methods remain selectable with incomplete feedback. Execution,
            # rather than this preference edit, reports the exact missing input.
            if new["control_mode"] == "pid":
                if cap.domain == "climate" and new.get("requested_mode") in ("auto", "heat_cool"):
                    raise HomeAssistantError("PID requires an explicit single thermal, drying or fan direction")
                if not (cap.temperature or cap.humidity or cap.domain == "fan"
                        or set(cap.modes) == {"off", "fan_only"}):
                    raise HomeAssistantError("No qualified feedback loop exists for this device")
                if power:
                    if new["cycle_seconds"] < on+off:
                        raise HomeAssistantError("PID cycle must include the full minimum ON and OFF intervals")
            if old["control_mode"] == "existing" and new["control_mode"] != "existing":
                if why := self._legacy_busy(spec):
                    raise HomeAssistantError(why)
                # Already-running manual equipment is not adopted here. The
                # runtime retains its OFF/reconciliation hold without rejecting
                # the requested method or resetting its ownership protection.
            record = self._record(spec)
            if record.get("pending") and not record.get("paused"):
                await self._reconcile(spec)
            if record.get("pending"):
                raise HomeAssistantError("Wait for the current physical-device acknowledgement before editing")
            if new["control_mode"] == "existing" and record.get("power"):
                raise HomeAssistantError("Reconcile managed power OFF before returning to the room controller")
            method_selected = "control_mode" in changes
            if method_selected or old["control_mode"] != new["control_mode"]:
                # Explicitly selecting a controller method is the user's
                # acknowledgement/re-arm after a previous software pause. A
                # still-running unowned appliance is handled separately below
                # and is never silently adopted.
                if method_selected and new["control_mode"] in (
                    "automatic", "pid", "manual", "off"
                ):
                    record.pop("paused", None)
                record["baseline"] = {
                    e: snapshot(self.hass.states.get(e)) for e in spec.source_entities
                }
                now = self.clock()
                record.setdefault("off_at", {}).update({
                    e: self._observed_off_since(e, now)
                    for e in spec.source_entities
                    if output_off(self.hass.states.get(e))
                })
                await self._save()
            # Use the shared options lock to preserve simultaneous room/mold edits.
            lock = getattr(self.manager, "_device_settings_write_lock", None)
            if lock is None:
                lock = self.manager._device_settings_write_lock = asyncio.Lock()
            async with lock:
                options = deepcopy(self.manager.entry.options)
                saved = deepcopy(self.manager.settings.get(model.SETTINGS, {}))
                saved = saved if isinstance(saved, dict) else {}
                saved[spec.identifier] = new
                options[model.SETTINGS] = saved
                # Storage awaited above: refuse a stale approval if the source
                # selection or identity changed while the preference was saved.
                if authorizing and (not self._current_spec(spec) or
                        new["_native_authorization"] != authority_context(self.manager, spec)):
                    raise HomeAssistantError("Device sources changed; select the control method again")
                self.hass.config_entries.async_update_entry(self.manager.entry, options=options)
            self._memory.pop(spec.identifier, None)
            self._fan_allocations.pop(spec.identifier, None)
            self._status(spec, "settings_updated", control_mode=new["control_mode"])
        if getattr(self.manager, "_active", False):
            self.manager._recalculate(initial=True)

    async def async_apply_pid_calibration(self, spec: model.ManagedDevice) -> None:
        """Apply a deterministic measured-model tune, never perform a step test.

        This is an explicit user action on the selected physical controller.
        No physical service is called; refuse recalibration while power is
        being cycled or its acknowledgement is pending. Saved manual gains
        remain untouched on every failed/incomplete model.
        """
        cfg = model.settings(self.manager, spec)
        if cfg["control_mode"] != "pid":
            raise HomeAssistantError("Select PID before applying calibration")
        method = cfg["pid_calibration_method"]
        if method == "manual":
            raise HomeAssistantError("Manual PID uses the editable Kp/Ki/Kd directly")
        cap = model.capabilities(self.manager, spec)
        if cap is None or not self._current_spec(spec):
            raise HomeAssistantError("Native controller unavailable for calibration")
        record = self._record(spec)
        if record.get("pending") or record.get("power"):
            raise HomeAssistantError("Stop and reconcile physical output before changing PID gains")
        state = self.hass.states.get(cap.primary)
        if state is None or not output_off(state):
            raise HomeAssistantError("Physical device must be OFF when applying new PID gains")
        try:
            result = tune_pid(method, cfg, sample_seconds=cfg["sample_seconds"],
                              constraints=model.NUMBER_FIELDS)
        except ValueError as error:
            raise HomeAssistantError(f"PID calibration requires valid measured model: {error}") from error
        model_evidence = {
            "method": method,
            "process_gain": result.process_gain,
            "time_constant_minutes": result.time_constant_minutes,
            "dead_time_minutes": result.dead_time_minutes,
            "lambda_minutes": result.lambda_minutes,
            "observed_sources": list(spec.source_entities),
        }
        await self.async_update(spec, {
            "kp": result.kp, "ki": result.ki, "kd": result.kd,
            "pid_last_calibration": model_evidence,
        })

    async def async_apply_fan_capacity(self, spec: model.ManagedDevice) -> None:
        """Apply a measured fan/output capacity curve while safely OFF.

        This does not measure capacity, switch the fan, run a relay step test,
        reset existing PID gains, or issue a physical Home Assistant service.
        """
        cfg = model.settings(self.manager, spec)
        if cfg["control_mode"] != "pid":
            raise HomeAssistantError("Select PID before applying measured fan capacity")
        cap = model.capabilities(self.manager, spec)
        if cap is None or not self._current_spec(spec) or not cap.fan_entity:
            raise HomeAssistantError("Native fan capabilities unavailable")
        if cap.domain not in ("climate", "humidifier"):
            raise HomeAssistantError("Capacity compensation is for ON/OFF equipment with a fan")
        direction = cfg["pid_fan_capacity_for_mode"]
        if direction not in model.PID_FAN_DIRECTIONS or direction not in cap.modes:
            raise HomeAssistantError("Select the specific native heating/cooling/drying direction")
        record = self._record(spec)
        source = self.hass.states.get(cap.primary)
        if (source is None or not output_off(source) or record.get("pending")
                or record.get("power") or record.get("paused")):
            raise HomeAssistantError("Physical device must be safely OFF, idle and reconciled")
        fan_min = model.device_limits(self.manager, spec, cap)["fan_min_percentage"]
        try:
            curve = build_fan_capacity_model(
                percentage=cap.fan_percentage,
                advertised_modes=cap.fan_modes, measured=cfg,
                min_speed=fan_min,
            )
        except ValueError as error:
            raise HomeAssistantError(f"Invalid measured fan capacities: {error}") from error
        saved = {
            **curve, "direction": direction,
            "physical_entity": cap.primary, "fan_entity": cap.fan_entity,
            "sources": list(spec.source_entities),
        }
        maps = deepcopy(cfg["pid_fan_capacity_models"])
        maps[direction] = saved
        await self.async_update(spec, {
            "pid_fan_capacity_models": maps,
            "pid_fan_capacity_mode": "measured",
        })

    async def async_set_targets(self, spec: model.ManagedDevice, values: dict,
                                *, mode: str | None = None) -> None:
        cap = model.capabilities(self.manager, spec)
        if cap is None:
            raise HomeAssistantError("Native capabilities unavailable")
        cfg = model.settings(self.manager, spec)
        changes = {}
        if cfg["control_mode"] == "existing" or mode is not None:
            changes["control_mode"] = "off" if mode == "off" else "manual"
        effective={**cfg,**changes}
        profile=model.profile_name(effective,model.plan_for(self.manager,spec))

        if effective["control_mode"]=="manual" and effective.get("preset","none")=="none":
            table=deepcopy(cfg["profile_targets"])
            table["manual"]={**table.get("manual",{}),**values}
            changes["profile_targets"]=table
            if mode is not None:
                changes["requested_mode"]=mode
            await self.async_update(spec,changes)
            return

        if set(values)-{"heat","cool","humidity"}:
            raise HomeAssistantError("Unsupported room target")
        if not values:
            raise HomeAssistantError("No supported room target supplied")

        limits=model.device_limits(self.manager,spec,cap)
        lock=getattr(self.manager,"_device_settings_write_lock",None)
        if lock is None:
            lock=self.manager._device_settings_write_lock=asyncio.Lock()
        async with lock:
            options=deepcopy(self.manager.entry.options)
            rooms=deepcopy(self.manager.settings.get("climate_rooms",{}))
            room=deepcopy(rooms.get(spec.area_id,{}))

            if profile not in ("comfort","home","away","sleep","eco"):
                raise HomeAssistantError("Select a Room Environment profile before editing its target")

            defaults={
                "comfort":{"heat_c":20.0,"cool_c":26.0,"humidity":50.0},
                "home":{"heat_c":18.0,"cool_c":28.0,"humidity":50.0},
                "away":{"heat_c":16.0,"cool_c":30.0,"humidity":50.0},
                "sleep":{"heat_c":18.0,"cool_c":26.0,"humidity":50.0},
                "eco":{"heat_c":17.0,"cool_c":29.0,"humidity":50.0},
            }
            raw_profiles=deepcopy(room.get("profiles",{}))
            raw_profiles=raw_profiles if isinstance(raw_profiles,dict) else {}
            fallback=defaults[profile]
            existing=raw_profiles.get(profile,{})
            band={**fallback,**(existing if isinstance(existing,dict) else {})}

            if "humidity" in values:
                humidity=finite(
                    values["humidity"],
                    limits["humidity_min_limit"],
                    limits["humidity_max_limit"],
                )
                if humidity is None:
                    raise HomeAssistantError("Humidity target outside Room Environment limits")
                band["humidity"]=humidity

            for key,value in values.items():
                if key not in ("heat","cool"):
                    continue
                number=finite(
                    value,
                    limits["temperature_min_limit"],
                    limits["temperature_max_limit"],
                )
                if number is None:
                    raise HomeAssistantError("Target outside Room Environment limits")
                band["heat_c" if key=="heat" else "cool_c"]=number

            heat=float(band["heat_c"])
            cool=float(band["cool_c"])
            if cool-heat<1.0:
                raise HomeAssistantError("Heating and cooling targets must be at least 1°C apart")
            raw_profiles[profile]=band
            room["profiles"]=raw_profiles

            rooms[spec.area_id]=room
            options["climate_rooms"]=rooms
            self.hass.config_entries.async_update_entry(self.manager.entry,options=options)
        if getattr(self.manager,"_active",False):
            self.manager._recalculate(initial=True)


    async def async_set_fan(self, spec: model.ManagedDevice, value: str) -> None:
        cfg = model.settings(self.manager, spec)
        changes = {"control_mode": "manual"} if cfg["control_mode"] == "existing" else {}
        profile = model.profile_name({**cfg, **changes}, model.plan_for(self.manager, spec))
        table = deepcopy(cfg["profile_fans"])
        table[profile] = str(value)
        await self.async_update(spec, {**changes, "profile_fans": table})

    async def async_resume(self, spec: model.ManagedDevice) -> None:
        """Explicitly reconcile actual OFF; changing presets never clears a pause."""
        async with self._lock(spec.identifier):
            if not self._ready or not self._current_spec(spec):
                raise HomeAssistantError("Controller or its source identity is unavailable")
            record = self._record(spec)
            power = record.get("power", {})
            pending = record.get("pending")
            for entity in power:
                state = self.hass.states.get(entity)
                if not output_off(state):
                    raise HomeAssistantError("Turn the owned physical equipment OFF before reconciliation")
            if pending and pending.get("power") and (self.hass.states.get(pending["entity"]) is None
                    or not output_off(self.hass.states.get(pending["entity"]))):
                raise HomeAssistantError("Interrupted power command requires verified physical OFF")
            record.update(paused=None, pending=None, power={},
                          baseline={e: snapshot(self.hass.states.get(e)) for e in spec.source_entities},
                          off_at={e: self.clock() for e in spec.source_entities})
            self._memory.pop(spec.identifier, None)
            self._started = self.clock()
            await self._save()
            self._status(spec, "reconciled_waiting_minimum_off")

    def schedule(self) -> None:
        if not self._active or not self._ready:
            return
        known = {spec.identifier: spec for spec in model.specs(self.manager)}
        for key, spec in known.items():
            cfg = model.settings(self.manager, spec)
            if cfg["control_mode"] == "existing" and not (self.records.get(key, {}).get("power") or self.records.get(key, {}).get("pending")):
                continue
            task = self._tasks.get(key)
            if task is not None and not task.done():
                continue
            self._tasks[key] = self.hass.async_create_task(self._run(spec))
        for key, record in tuple(self.records.items()):
            if key not in known and (record.get("power") or record.get("pending")):
                task = self._tasks.get(key)
                if task is None or task.done():
                    spec = model.ManagedDevice(key, record["area"], "Retired controller",
                        record.get("source_device_id"), tuple(record["sources"]))
                    self._tasks[key] = self.hass.async_create_task(self._run(spec))

    async def _run(self, spec: model.ManagedDevice) -> None:
        try:
            async with self._lock(spec.identifier):
                await self.tick(spec)
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.exception("Managed controller failed for %s", spec.identifier)
            if self._ready:
                await self._pause(spec, "controller_exception")
        finally:
            if self._tasks.get(spec.identifier) is asyncio.current_task():
                self._tasks.pop(spec.identifier, None)

    def measurements(self, spec: model.ManagedDevice, cap: model.Capabilities) -> dict:
        room, dev = model.room_config(self.manager, spec), model.device_config(self.manager, spec, cap.primary)
        values = {}
        for metric, key in (("temperature", "temperature_entity"), ("humidity", "humidity_entity"),
                            ("co2", "co2_entity"), ("pm25", "pm25_entity")):
            from .room_sources import selected, aggregate
            group = metric if metric in ("temperature", "humidity") else "air_quality"
            chosen = selected(self.manager.settings, spec.area_id, group)
            if chosen is not None:
                if group == "air_quality":
                    from .discovery import supported_metric
                    chosen = tuple(
                        entity for entity in chosen
                        if (state := self.hass.states.get(entity)) is not None
                        and supported_metric(self.hass, state, outdoor=False) == metric
                    )
                value, _ = aggregate(self.hass, chosen, spec.area_id, group, 10)
                values[metric] = value
                values[key] = None
                values[metric + "_selected_entities"] = list(chosen)
                values[metric + "_source"] = "room_selected_mean"
                continue

            # Legacy fallback only when this room has never been given an
            # explicit source selection for this metric.
            source = dev.get(key) or room.get(key)
            if metric == "temperature" and not source:
                source = self.manager.settings.get("pid_rooms", {}).get(spec.area_id, {}).get("temperature_entity")
            excluded = self.manager.settings.get(CONF_EXCLUDED_INDOOR, {}).get(spec.area_id, [])
            if not source and metric in ("temperature", "humidity"):
                candidates = []
                for observed in self.hass.states.async_all("sensor"):
                    if observed.entity_id in excluded or entity_area(self.hass, observed.entity_id) != spec.area_id:
                        continue
                    if metric == "temperature":
                        if observed.attributes.get("device_class") != "temperature":
                            continue
                        valid = temperature_sensor_c(self.hass, observed.entity_id, 10)
                    else:
                        sample = reading(self.hass, observed.entity_id, 10, outdoor=False)
                        valid = sample.value if sample.metric == metric else None
                    if valid is not None:
                        candidates.append(observed.entity_id)
                source = candidates[0] if len(candidates) == 1 else None
            value = None
            if isinstance(source, str) and source not in excluded and entity_area(self.hass, source) == spec.area_id:
                if metric == "temperature":
                    value = temperature_sensor_c(self.hass, source, 10)
                else:
                    observed = reading(self.hass, source, 10, outdoor=False)
                    value = observed.value if observed.metric == metric else None
            values[metric] = value
            values[key] = source
            values[metric + "_source"] = "legacy_fallback" if source else "unavailable"
        return values

    def _quiet_context(self, spec: model.ManagedDevice, cfg: dict, plan: dict) -> bool:
        """Do not raise fan speed on missing sleep/presence evidence."""
        room = model.room_config(self.manager, spec)
        shared = plan.get("global_presence", {})
        known = set(plan.get("known_presence_areas", [spec.area_id]))
        occupied = plan.get("occupancy", "unknown")
        sleeping = plan.get("sleeping")
        if shared:
            occupied, _, _ = room_presence(self.hass, spec.area_id, room, shared,
                                            known_areas=known or {spec.area_id})
            if shared.get("sleep_rooms_entity"):
                value, _ = sleep_presence(self.hass, spec.area_id, shared, known or {spec.area_id})
                # The configured live sleep-room source is authoritative.
                sleeping = value
        else:
            sensors = plan.get("presence_entities", [])
            if sensors:
                states = [self.hass.states.get(e) for e in sensors]
                if any(st is not None and st.state == "on" for st in states):
                    occupied = "occupied"
                elif any(st is None or st.state != "off" for st in states):
                    occupied = "unknown"
                else:
                    occupied = "unoccupied"
        # Quiet automation is tri-state. Positive evidence enables it,
        # negative evidence disables it, and unknown evidence must not cause
        # either a speed reduction or a speed restoration.
        uncertain = False
        if cfg["quiet_sleep"]:
            if sleeping is True:
                return True
            if sleeping is None:
                uncertain = True
        if cfg["quiet_occupied"]:
            if occupied == "occupied":
                return True
            if occupied not in ("occupied", "unoccupied"):
                uncertain = True
        return None if uncertain else False

    def _shutdown_allowed(self, spec: model.ManagedDevice, entity: str, expected: dict) -> bool:
        """Only an already-owned OFF can survive deselection or removed rooms."""
        from homeassistant.helpers import entity_registry as er
        record = self._record(spec)
        item = er.async_get(self.hass).async_get(entity)
        state = self.hass.states.get(entity)
        is_off = expected.get("state") == "off" or entity.startswith(("number.", "input_number.")) and finite(expected.get("state"), 0, 100) == 0
        owned = record.get("power", {}).get(entity)
        return bool(is_off and owned and entity in record["sources"] and item is not None
                    and getattr(item, "platform", None) != DOMAIN
                    and getattr(item, "device_id", None) == record.get("source_device_id")
                    and entity_area(self.hass, entity) == record["area"]
                    and not foreign_owner_hold(self.hass, self.manager.entry.entry_id, entity)
                    and state is not None and state.state not in ("unknown", "unavailable")
                    and state.attributes.get("hvac_action") != "defrosting"
                    and self.clock()-owned["since"] >= owned["min_on"])

    async def _retired(self, spec: model.ManagedDevice) -> None:
        """Drain acknowledged owned outputs using their original physical limits.

        Deleted/reassigned physical identities and interrupted restart ownership
        remain latched for manual reconciliation. No permission for a new ON is
        inferred from an old record.
        """
        record = self._record(spec)
        if record.get("paused"):
            self._status(spec, "retired_requires_manual_reconciliation", reason=record["paused"])
            return
        raw = record.get("capabilities")
        if not isinstance(raw, dict):
            self._status(spec, "retired_requires_manual_reconciliation")
            return
        try:
            cap = model.Capabilities(**raw)
        except (TypeError, ValueError):
            self._status(spec, "retired_requires_manual_reconciliation")
            return
        if not await self._reconcile(spec):
            return
        for entity in tuple(record["power"]):
            if entity != cap.primary:
                self._status(spec, "retired_identity_requires_manual_reconciliation")
                continue
            if await self._power(spec, cap, "off", automatic=False, shutdown=True):
                return
        if not record["power"] and not record.get("pending"):
            self._status(spec, "retired_outputs_reconciled")

    def _gate(self, spec: model.ManagedDevice, cap: model.Capabilities, cfg: dict, plan: dict,
              mode: str, *, automatic: bool = True) -> str | None:
        if not self._active or not self._ready:
            return "controller_inactive"
        if not self._current_spec(spec):
            return "source_deselected_or_moved"
        for entity in spec.source_entities:
            if snapshot(self.hass.states.get(entity)) is None:
                return "physical_device_unavailable"
            if other := foreign_owner_hold(self.hass, self.manager.entry.entry_id, entity):
                return other
        for key, record in self.records.items():
            if (key != spec.identifier and record.get("source_device_id") is not None
                    and record.get("source_device_id") == spec.source_device_id
                    and record.get("area") == spec.area_id and record.get("pending")):
                return "other_endpoint_acknowledgement_pending"
        if self._record(spec).get("paused"):
            return "controller_paused"
        if cfg["control_mode"] == "existing":
            return "existing_controller_selected"
        room = model.room_config(self.manager, spec)
        native = self.hass.states.get(cap.primary)
        if native is not None and native.attributes.get("hvac_action") == "defrosting":
            return "native_defrost_protection"
        if mode != "off" and cap.domain != "fan" and not _contact_interlock(self.hass, spec.area_id, plan):
            return "open_or_unknown_window"
        if mode in ("heat", "cool", "heat_cool"):
            if conflict := _physical_climate_conflict(self.hass, spec.area_id, room, cap.primary, mode):
                return conflict
        if automatic:
            soft, _ = model.permission(self.manager, spec, cap)
            if not soft:
                return "select_control_method_to_authorize_current_device_sources"
            if self.clock()-self._started < STARTUP_SECONDS:
                return "startup_warmup"
            from .device_activation import effective_device
            device = effective_device(self.manager, spec, cap.primary)
            if device:
                allowed, reason = live_device_permission(self.hass, spec.area_id, room, plan, device)
                if allowed != "eligible":
                    return reason
            if cap.domain == "fan" or set(cap.modes) == {"off", "fan_only"}:
                dev = effective_device(self.manager, spec, cap.primary)
                purpose = dev.get("fan_purpose") or ("extraction" if room.get("extraction_fan_entity") == cap.primary else None)
                if purpose not in ("extraction", "filtration"):
                    return "select_fan_purpose_on_controller_device"
                stamp = finite(plan.get("air_evidence_at"), 0, 1e13)
                if stamp is None or not 0 <= self.clock()-stamp <= 120:
                    return "air_quality_decision_expired"
                if purpose == "extraction":
                    if plan.get("air_actions", {}).get("outdoor_air_verified") is not True:
                        return "outside_air_not_verified"
                    if not _contact_interlock(self.hass, spec.area_id, plan):
                        return "window_already_open_or_unknown"
                elif not (dev.get("sensor_verified") is True or room.get("pm25_sensor_verified") is True):
                    return "particle_sensor_not_verified"
            if cap.domain == "humidifier" or mode == "dry":
                opposite = room.get("dehumidifier_entity" if cap.humidifying else "humidifier_entity")
                if opposite:
                    other = self.hass.states.get(opposite)
                    if other is None or other.state != "off":
                        return "opposing_humidity_device_active_or_unknown"
                for role in ("climate_entity", "heat_climate_entity", "cool_climate_entity", "dry_climate_entity"):
                    other_id = room.get(role)
                    if not other_id or other_id == cap.primary:
                        continue
                    other = self.hass.states.get(other_id)
                    if other is None or other.state in ("unknown", "unavailable"):
                        return "other_climate_unavailable"
                    if cap.humidifying and other.state in ("cool", "dry", "heat_cool", "auto"):
                        return "opposing_humidity_climate_active"
                    if mode == "dry" and cap.domain == "climate" and other.state not in ("off", "fan_only"):
                        return "thermal_priority_defer_dry"
                    if not cap.humidifying and other.state in ("cool", "heat_cool", "auto"):
                        humidity = self.measurements(spec, cap)["humidity"]
                        target = model.targets(self.manager, spec, cap, cfg, plan)["humidity"]
                        if humidity is None or humidity < target + float(room.get("cooling_dry_deferral_rh_points", 10)):
                            return "cooling_priority_defer_dehumidifier"
        return None

    async def _reconcile(self, spec: model.ManagedDevice) -> bool:
        record, now = self._record(spec), self.clock()
        pending = record.get("pending")
        if pending:
            if not self._identity_ok(spec):
                await self._pause(spec, "physical_source_identity_changed")
                return False
            state = self.hass.states.get(pending["entity"])
            if matches(state, pending["expected"]):
                record["baseline"][pending["entity"]] = snapshot(state)
                record["pending"] = None
                if pending.get("power"):
                    entity = pending["entity"]
                    if pending.get("output_on") is False or pending["expected"].get("state") == "off":
                        record["power"].pop(entity, None)
                        record["off_at"][entity] = now
                    else:
                        record["power"].setdefault(entity, {"since": now,
                            "min_on": pending["min_on"], "max_on": pending["max_on"]})
                await self._save()
            elif now < pending["when"] or now-pending["when"] > ACK_SECONDS:
                await self._pause(spec, "physical_acknowledgement_missing")
                return False
            else:
                self._status(spec, "awaiting_physical_acknowledgement")
                return False
        for entity, baseline in record.get("baseline", {}).items():
            if baseline is None:
                continue
            observed = snapshot(self.hass.states.get(entity))
            if observed is not None and observed != baseline:
                await self._pause(spec, "physical_manual_override")
                return False
        return True

    async def _send(self, spec: model.ManagedDevice, cap: model.Capabilities, entity: str,
                    service: str, data: dict, expected: dict, *, power: bool = False,
                    mode: str | None = None, automatic: bool = True,
                    shutdown: bool = False) -> bool:
        """Durable intent, exact target, live rechecks after *every* yield."""
        record = self._record(spec)
        if record.get("pending") or record.get("paused"):
            return False
        primary = self.hass.states.get(cap.primary)
        if primary is None:
            return False
        cfg = model.settings(self.manager, spec)
        plan = model.plan_for(self.manager, spec)
        action_mode = mode or primary.state
        if shutdown:
            if not self._shutdown_allowed(spec, entity, expected):
                self._status(spec, "owned_shutdown_identity_or_dwell_hold")
                return False
        elif why := self._gate(spec, cap, cfg, plan, action_mode, automatic=automatic):
            self._status(spec, why)
            return False
        if entity not in spec.source_entities or entity_area(self.hass, entity) != spec.area_id:
            return False
        domain = entity.partition(".")[0]
        if not self.hass.services.has_service(domain, service):
            self._status(spec, "native_service_unavailable", service=f"{domain}.{service}")
            return False
        before_settings = deepcopy(self.manager.settings)
        before_plan = deepcopy(plan)
        before_sources = {e: snapshot(self.hass.states.get(e)) for e in spec.source_entities}
        before_feedback = self.measurements(spec, cap) if automatic else None
        before_quiet = self._quiet_context(spec, cfg, plan)
        if shutdown:
            owned = record["power"][entity]
            min_on, max_on = owned["min_on"], owned["max_on"]
        else:
            min_on, _, max_on = model.timing(self.manager, spec, cap)
        record["baseline"].setdefault(entity, before_sources[entity])
        record["capabilities"] = asdict(cap)
        pending = {"entity": entity, "service": service, "data": data,
                   "expected": expected, "power": power, "output_on": not (
                       expected.get("state") == "off" or service == "set_value" and data.get("value") == 0),
                   "phase": "intent", "when": self.clock(), "min_on": min_on, "max_on": max_on}
        record["pending"] = pending
        await self._save()

        def current() -> bool:
            if not self._active or not self._ready or record.get("paused"):
                return False
            if any(snapshot(self.hass.states.get(e)) != previous for e, previous in before_sources.items()):
                return False
            if shutdown:
                return self._shutdown_allowed(spec, entity, expected)
            latest = model.settings(self.manager, spec)
            latest_plan = model.plan_for(self.manager, spec)
            return bool(self._current_spec(spec) and self.manager.settings == before_settings
                and model.capabilities(self.manager, spec) == cap and latest_plan == before_plan
                and (not automatic or self.measurements(spec, cap) == before_feedback)
                and self._quiet_context(spec, latest, latest_plan) == before_quiet
                and not self._gate(spec, cap, latest, latest_plan, action_mode, automatic=automatic))

        async def abort() -> bool:
            self._invalidated.add(spec.identifier)
            record["pending"] = None  # Dispatch has NOT happened; no uncertainty.
            await self._save()
            self._status(spec, "authority_or_evidence_changed_before_dispatch")
            return False

        if not current():
            return await abort()
        try:
            async with self._commands:
                if not current():
                    return await abort()
                await asyncio.wait_for(self.hass.services.async_call(domain, service, data,
                    target={"entity_id": entity}, blocking=True), timeout=20)
            pending["phase"] = "commanded"
            await self._save()
            self._status(spec, "command_sent", entity_id=entity, service=service)
            return True
        except asyncio.CancelledError:
            raise  # Persisted intent is deliberately retained.
        except Exception:
            if self._ready:
                await self._pause(spec, "native_command_failed_or_uncertain")
            return False

    async def _power(self, spec: model.ManagedDevice, cap: model.Capabilities,
                     desired: str, *, automatic: bool, shutdown: bool = False) -> bool:
        state = self.hass.states.get(cap.primary)
        if state is None or state.state in ("unknown", "unavailable"):
            return False
        if desired not in cap.modes or "off" not in cap.modes:
            self._status(spec, "native_power_mode_unsupported")
            return False
        _, granted = model.permission(self.manager, spec, cap)
        record, now = self._record(spec), self.clock()
        owned = record.get("power", {}).get(cap.primary)
        if not granted and not (shutdown and owned):
            self._status(spec, "power_control_not_commissioned")
            return False
        proportional = cap.domain in ("number", "input_number")
        target_state = ("0.0" if desired == "off" else "100.0") if proportional else (
            desired if cap.domain == "climate" else "off" if desired == "off" else "on")
        if matches(state, {"state": target_state}):
            return False
        if state.attributes.get("hvac_action") == "defrosting":
            self._status(spec, "native_defrost_protection")
            return False
        if shutdown and owned:
            on_min, off_min, maximum = owned["min_on"], 600, owned["max_on"]
        else:
            on_min, off_min, maximum = model.timing(self.manager, spec, cap)
            if owned:
                on_min = max(on_min, owned["min_on"])
        if not output_off(state):
            if desired != "off":
                # Heat->cool is ALWAYS OFF, full dwell, then new mode.
                desired, target_state = "off", "0.0" if proportional else "off"
            stamp = owned.get("since") if owned else None
            if stamp is None:
                changed = getattr(state, "last_changed", None)
                stamp = changed.timestamp() if changed is not None else record.setdefault("on_seen", {}).setdefault(cap.primary, now)
            if not 0 <= now-stamp or now-stamp < on_min:
                self._status(spec, "minimum_on_hold")
                return False
        else:
            changed = getattr(state, "last_changed", None)
            try:
                observed = changed.timestamp() if changed is not None else None
            except (AttributeError, TypeError, ValueError, OverflowError):
                observed = None
            observed = finite(observed, 0, 1e13)
            stamp = record["off_at"].get(cap.primary)
            if stamp is None:
                stamp = observed if observed is not None and observed <= now else now
            elif observed is not None and stamp < observed <= now:
                # A newer HA state transition proves a later physical OFF.
                stamp = observed
            record["off_at"][cap.primary] = stamp
            if not 0 <= now-stamp or now-stamp < off_min:
                self._status(spec, "minimum_off_hold")
                return False
        if proportional:
            attrs = state.attributes
            if attrs.get("unit_of_measurement") != "%" or attrs.get("min") != 0 or attrs.get("max") != 100:
                self._status(spec, "proportional_output_not_verified")
                return False
            service, data = "set_value", {"value": float(target_state)}
        else:
            service = "set_hvac_mode" if cap.domain == "climate" else "turn_off" if desired == "off" else "turn_on"
            data = {"hvac_mode": desired} if cap.domain == "climate" else {}
        return await self._send(spec, cap, cap.primary, service, data, {"state": target_state},
                                power=True, mode=desired, automatic=automatic, shutdown=shutdown)

    async def _native_target(self, spec: model.ManagedDevice, cap: model.Capabilities,
                             mode: str, targets: dict, demand: float | None, automatic: bool) -> bool:
        state = self.hass.states.get(cap.primary)
        if state is None or state.state == "off":
            return False
        config = model.settings(self.manager, spec)
        limits = model.device_limits(self.manager, spec, cap)
        profile = model.profile_name(config, model.plan_for(self.manager, spec))
        manual_humidity = not automatic and "humidity" in config.get("profile_targets", {}).get(profile, {})
        if cap.domain == "humidifier" or cap.humidity and (mode == "dry" or manual_humidity):
            if cap.domain == "climate" and not (model.features(state) & model.HUMIDITY):
                return False
            value = round(max(limits["humidity_min_limit"],
                              min(limits["humidity_max_limit"], targets["humidity"])))
            if automatic:
                actual = finite(state.attributes.get("humidity"), 0, 100)
                if actual is None:
                    return False
                outside_soft_limit = not limits["humidity_min_limit"] <= actual <= limits["humidity_max_limit"]
                if not outside_soft_limit:
                    value = round(max(actual-5, min(actual+5, value)))
                value = round(max(limits["humidity_min_limit"],
                                  min(limits["humidity_max_limit"], value)))
                if self.clock()-self._record(spec).get("target_at", 0) < model.settings(self.manager, spec)["sample_seconds"]:
                    return False
            if not cap.min_humidity <= value <= cap.max_humidity:
                self._status(spec, "target_outside_native_limits")
                return False
            if finite(state.attributes.get("humidity"), 0, 100) == value:
                return False
            sent = await self._send(spec, cap, cap.primary, "set_humidity", {"humidity": value},
                {"attributes": {"humidity": value}}, automatic=automatic)
            if sent:
                self._record(spec)["target_at"] = self.clock()
            return sent
        if cap.domain != "climate" or mode not in ("heat", "cool", "heat_cool", "auto"):
            return False
        unit = state.attributes.get("temperature_unit")
        if mode == "heat_cool" and cap.temperature_range:
            data = {"target_temp_low": target_to_unit(targets["heat"], unit),
                    "target_temp_high": target_to_unit(targets["cool"], unit)}
        elif cap.temperature and model.features(state) & model.TEMP:
            target = targets["cool" if mode == "cool" else "heat"]
            if demand is not None:
                # Setpoint-only PID never gains compressor-cycle permissions.
                target += (1 if mode == "heat" else -1) * 1.5 * demand / 100
            target = max(limits["temperature_min_limit"],
                         min(limits["temperature_max_limit"], target))
            data = {"temperature": target_to_unit(target, unit)}
        else:
            return False
        for key, value in data.items():
            if value is None:
                self._status(spec, "unsupported_temperature_unit")
                return False
            actual = finite(state.attributes.get(key), -50, 150)
            if actual is None:
                self._status(spec, "native_setpoint_unavailable")
                return False
            desired_c = target_from_unit(value, unit)
            actual_c = target_from_unit(actual, unit)
            if desired_c is None or actual_c is None:
                self._status(spec, "unsupported_temperature_unit")
                return False
            soft_min, soft_max = limits["temperature_min_limit"], limits["temperature_max_limit"]
            desired_c = max(soft_min, min(soft_max, desired_c))
            value = target_to_unit(desired_c, unit)
            outside_soft_limit = not soft_min <= actual_c <= soft_max
            if automatic and not outside_soft_limit:
                delta = .5 if unit in ("°C", "C") else .9
                value = max(actual-delta, min(actual+delta, value))
            native_min = target_to_unit(soft_min, unit)
            native_max = target_to_unit(soft_max, unit)
            if native_min is None or native_max is None:
                return False
            try:
                physical_min = float(state.attributes.get("min_temp", native_min))
                physical_max = float(state.attributes.get("max_temp", native_max))
            except (TypeError, ValueError):
                physical_min, physical_max = native_min, native_max
            value = quantize_target(
                value, state.attributes.get("target_temp_step", .5),
                max(physical_min, native_min), min(physical_max, native_max))
            if value is None:
                return False
            final_c = target_from_unit(value, unit)
            if final_c is None or not soft_min-1e-6 <= final_c <= soft_max+1e-6:
                self._status(spec, "target_outside_device_limits")
                return False
            if automatic and not outside_soft_limit and abs(final_c-actual_c) > .500001:
                self._status(spec, "native_step_exceeds_setpoint_rate_limit")
                return False
            data[key] = value
        if all(abs(float(state.attributes.get(k))-v) < .05 for k, v in data.items()):
            return False
        record = self._record(spec)
        # Sampling applies to trim/setpoint writes too, not merely PID math.
        if automatic and self.clock()-record.get("target_at", 0) < model.settings(self.manager, spec)["sample_seconds"]:
            return False
        sent = await self._send(spec, cap, cap.primary, "set_temperature", data,
                                {"attributes": data}, automatic=automatic)
        if sent:
            record["target_at"] = self.clock()
        return sent

    async def _fan(self, spec: model.ManagedDevice, cap: model.Capabilities,
                   cfg: dict, plan: dict, demand: float | None, automatic: bool,
                   measured_capacity_speed: str | int | None = None) -> bool:
        if not cap.fan_entity or not cap.fan_modes:
            return False
        state = self.hass.states.get(cap.fan_entity)
        if state is None or state.state == "off":
            return False  # Quiet mode never powers an appliance on.
        record = self._record(spec)
        attribute = "percentage" if cap.fan_percentage else "fan_mode" if cap.fan_entity.startswith("climate.") else "preset_mode"
        observed = state.attributes.get(attribute)
        if observed is None:
            return False
        record.setdefault("normal_fan", observed)
        selected_fan = cfg.get("profile_fans", {}).get(model.profile_name(cfg, plan)) or cfg.get("fan_mode")
        normal = selected_fan or str(record["normal_fan"])
        if cap.fan_percentage:
            dev = model.device_config(self.manager, spec, cap.primary)
            normal = selected_fan or dev.get("fan_speed_percent") or normal
            if measured_capacity_speed is not None:
                normal = measured_capacity_speed
            elif demand is not None and automatic and cfg["control_mode"] == "pid":
                planned = fan_speed_for_pid(
                    demand, modes=cap.fan_modes, percentage=True,
                    min_percentage=model.device_limits(self.manager, spec, cap)["fan_min_percentage"],
                    max_percentage=model.device_limits(self.manager, spec, cap)["fan_max_percentage"],
                )
                if planned is not None:
                    normal = planned
            quiet_state = self._quiet_context(spec, cfg, plan) if automatic else False
            if quiet_state is None:
                self._status(spec, "quiet_context_unknown")
                return True  # handled hold: do not overwrite status or change speed
            quiet = quiet_state is True
            limits = model.device_limits(self.manager, spec, cap)
            value = max(limits["fan_min_percentage"],
                        min(limits["fan_max_percentage"], float(normal)))
            if quiet:
                quiet_value = max(limits["fan_min_percentage"],
                                  min(limits["fan_max_percentage"], cfg["quiet_percentage"]))
                value = min(value, quiet_value)
            valid = [int(v) for v in cap.fan_modes
                     if limits["fan_min_percentage"] <= int(v) <= limits["fan_max_percentage"]]
            if not valid:
                self._status(spec, "fan_limits_have_no_supported_step")
                return False
            if quiet:
                lower = [v for v in valid if v <= value]
                value = max(lower) if lower else min(valid)
            else:
                value = min(valid, key=lambda v: abs(v-value))
            service, data, expected = "set_percentage", {"percentage": value}, {"attributes": {attribute: value}}
        else:
            quiet_state = self._quiet_context(spec, cfg, plan) if automatic else False
            if quiet_state is None:
                self._status(spec, "quiet_context_unknown")
                return True  # handled hold: do not overwrite status or change speed
            quiet = quiet_state is True
            low = cfg.get("quiet_fan_mode") or ("low" if "low" in cap.fan_modes else None)
            value = low if quiet and low is not None else normal
            if measured_capacity_speed is not None and measured_capacity_speed in cap.fan_modes:
                value = measured_capacity_speed
            # Map the same PID demand to Low/Medium/High ONLY where the
            # physical source advertises an unambiguous ordered speed set.
            # Arbitrary native presets keep their saved profile/normal speed.
            if (measured_capacity_speed is None and automatic and cfg["control_mode"] == "pid"
                    and demand is not None and demand > 0):
                chosen = fan_speed_for_pid(
                    demand, modes=cap.fan_modes, percentage=False,
                    quiet=quiet, quiet_mode=low,
                )
                if chosen is not None:
                    value = chosen
            if value not in cap.fan_modes:
                return False
            service = "set_fan_mode" if cap.fan_entity.startswith("climate.") else "set_preset_mode"
            key = "fan_mode" if service == "set_fan_mode" else "preset_mode"
            data, expected = {key: value}, {"attributes": {attribute: value}}
        if observed == value:
            return False
        return await self._send(spec, cap, cap.fan_entity, service, data, expected, automatic=automatic)

    async def tick(self, spec: model.ManagedDevice) -> None:
        if not self._active or not self._ready:
            return
        self._invalidated.discard(spec.identifier)
        record = self._record(spec)
        if record.get("paused"):
            self._status(spec, "paused", reason=record["paused"])
            return
        if not self._current_spec(spec):
            await self._retired(spec)
            return
        # The physical device must be available before ANY capability,
        # occupancy, target, measurement or PID calculation is performed.
        if not model.sources_available(self.manager, spec):
            self._status(spec, "waiting_for_physical_device")
            return
        cfg = model.settings(self.manager, spec)
        cap = model.capabilities(self.manager, spec)
        if cap is None:
            self._status(spec, "physical_capabilities_unavailable")
            return
        if not await self._reconcile(spec):
            return
        state = self.hass.states.get(cap.primary)
        if state is None or state.state in ("unknown", "unavailable"):
            self._status(spec, "waiting_for_physical_device")
            return
        record["baseline"].setdefault(cap.primary, snapshot(state))
        plan = model.plan_for(self.manager, spec)
        target = model.targets(self.manager, spec, cap, cfg, plan)
        mode = cfg.get("requested_mode")
        auto = cfg["control_mode"] in ("automatic", "pid")
        measured = self.measurements(spec, cap)
        soft, power = model.permission(self.manager, spec, cap)
        owned = record["power"].get(cap.primary)
        if auto and power and not owned and not output_off(state):
            self._status(spec, "running_device_requires_off_before_automatic_power_ownership")
            return
        if owned and not power:
            await self._power(spec, cap, "off", automatic=auto, shutdown=True)
            return
        if owned and self.clock()-owned["since"] >= owned["max_on"]:
            await self._power(spec, cap, "off", automatic=auto, shutdown=True)
            return
        if cfg["control_mode"] == "off":
            if not output_off(state):
                await self._power(spec, cap, "off", automatic=False, shutdown=bool(owned))
            else:
                self._status(spec, "off")
            return
        if cfg["control_mode"] == "existing":
            return
        if cfg["control_mode"] == "manual" and not (
            cfg.get("requested_mode") or cfg.get("profile_targets") or cfg.get("profile_fans")
            or cfg["preset"] != "none" or cfg.get("fan_mode")
            or cfg.get("swing_mode") or cfg.get("swing_horizontal_mode")
        ):
            self._status(spec, "manual_no_request")
            return
        if auto and not (cfg["control_mode"] == "pid" and mode in cap.modes and mode != "off"):
            mode = None  # Full automatic chooses only verified native modes.
            if cap.domain == "humidifier":
                mode = "auto" if cap.humidifying else "dry"
            elif cap.domain == "fan" or set(cap.modes) == {"off", "fan_only"}:
                mode = "fan_only"
            elif cap.temperature or cap.temperature_range:
                t = measured["temperature"]
                if t is not None:
                    if "auto" in cap.modes and not (set(cap.modes) & {"heat", "cool", "heat_cool"}):
                        mode = "auto"
                    elif t < target["heat"]-.3 and "heat" in cap.modes:
                        mode = "heat"
                    elif t > target["cool"]+.3 and "cool" in cap.modes:
                        mode = "cool"
                    elif "heat_cool" in cap.modes and cfg["control_mode"] != "pid":
                        mode = "heat_cool"
                    elif state.state in ("heat", "cool"):
                        mode = state.state  # Native thermostat retains regulation.
                    elif set(cap.modes) & {"heat", "cool"}:
                        mode = "heat" if "heat" in cap.modes else "cool"
            elif "dry" in cap.modes:
                mode = "dry"
        if mode is None:
            mode = state.state if cap.domain == "climate" else next((v for v in cap.modes if v != "off"), "off")
        if why := self._gate(spec, cap, cfg, plan, mode, automatic=auto):
            self._status(spec, why)
            if owned and state.state != "off":
                await self._power(spec, cap, "off", automatic=auto, shutdown=True)
            return
        demand, metric, increasing, goal, wanted = None, None, False, None, None
        measured_fan_allocation = None
        self._fan_allocations.pop(spec.identifier, None)
        if cap.domain == "fan" or set(cap.modes) == {"off", "fan_only"}:
            from .device_activation import effective_device
            dev = effective_device(self.manager, spec, cap.primary)
            room = model.room_config(self.manager, spec)
            extraction = dev.get("fan_purpose") == "extraction" or room.get("extraction_fan_entity") == cap.primary
            metric = "co2" if extraction else "pm25"
            goal = plan.get("air_actions", {}).get("thresholds", {}).get(
                "co2_operational_ppm" if extraction else "pm25_short_term_action_ug_m3")
        elif cap.domain == "humidifier" or mode == "dry":
            metric, goal, increasing = "humidity", target["humidity"], cap.humidifying
        elif mode in ("heat", "cool"):
            metric, goal, increasing = "temperature", target[mode], mode == "heat"
        elif mode in ("heat_cool", "auto") and (cap.temperature or cap.temperature_range):
            # Native range/AUTO owns its thermal direction. We only qualify
            # an outside-band ON; never implement simultaneous heating/cooling.
            value = measured["temperature"]
            metric, increasing = "temperature", value is not None and value < target["heat"]
            goal = target["heat"] if increasing else target["cool"]
        if auto and metric:
            value = measured[metric]
            if value is None or finite(goal, 0, 20000) is None:
                self._status(spec, "control_measurement_missing_or_stale")
                if owned:
                    await self._power(spec, cap, "off", automatic=True, shutdown=True)
                return
            error = (goal-value) if increasing else (value-goal)
            if cfg["control_mode"] == "pid" and mode in ("heat_cool", "auto") and cap.domain == "climate":
                self._status(spec, "select_single_direction_for_pid")
                return
            if cfg["control_mode"] == "pid":
                signature = (metric, goal, increasing, cfg["preset"], cfg["kp"], cfg["ki"], cfg["kd"])
                previous, memory, anchor = self._memory.get(spec.identifier, (None, None, self.clock()))
                if previous != signature:
                    memory, anchor = None, self.clock()
                memory = model.pid_step(value, goal, self.clock(), increasing=increasing,
                    kp=cfg["kp"], ki=cfg["ki"], kd=cfg["kd"], sample=cfg["sample_seconds"], memory=memory)
                self._memory[spec.identifier] = (signature, memory, anchor)
                demand = memory.demand
                on_min, off_min, _ = model.timing(self.manager, spec, cap)
                if (cfg.get("pid_fan_capacity_mode") == "measured"
                        and cap.domain in ("climate", "humidifier")
                        and cap.fan_entity and cap.fan_modes and demand > 0):
                    # Only the calibrated HVAC direction and the *exact*
                    # same physical endpoint and fan may use the model.
                    # A separate accessory fan that is currently OFF cannot
                    # be assumed to produce the measured capacity.
                    saved_models = cfg.get("pid_fan_capacity_models") or {}
                    saved_curve = saved_models.get(mode) if isinstance(saved_models, dict) else None
                    fan_state = self.hass.states.get(cap.fan_entity)
                    native_ready = (cap.fan_entity == cap.primary or
                                    fan_state is not None and
                                    fan_state.state not in ("off", "unknown", "unavailable"))
                    valid = (native_ready and isinstance(saved_curve, dict)
                             and saved_curve.get("sources") == list(spec.source_entities)
                             and fan_capacity_model_is_valid(
                                 saved_curve, mode=mode,
                                 physical_entity=cap.primary,
                                 fan_entity=cap.fan_entity,
                                 percentage=cap.fan_percentage,
                                 advertised_modes=cap.fan_modes))
                    if valid:
                        quiet_context = self._quiet_context(spec, cfg, plan)
                        if quiet_context is not None:
                            limits = model.device_limits(self.manager, spec, cap)
                            measured_fan_allocation = allocate_fan_capacity(
                                demand, saved_curve, quiet=quiet_context,
                                quiet_mode=cfg.get("quiet_fan_mode"),
                                quiet_percentage=cfg["quiet_percentage"],
                                fan_min_percentage=limits["fan_min_percentage"],
                                fan_max_percentage=limits["fan_max_percentage"],
                            )
                            if measured_fan_allocation:
                                self._fan_allocations[spec.identifier] = {
                                    "status": "capacity_limited" if
                                        measured_fan_allocation.unmet_demand_percent > 0
                                        else "capacity_compensated",
                                    **measured_fan_allocation.snapshot(),
                                    "direction": mode,
                                }
                        else:
                            self._fan_allocations[spec.identifier] = {
                                "status": "quiet_context_unknown",
                                "direction": mode,
                            }
                    else:
                        self._fan_allocations[spec.identifier] = {
                            "status": "model_source_or_mode_not_ready",
                            "direction": mode,
                        }
                # Use ONE modulation dimension for continuously adjustable
                # standalone fans. Never multiply a PID percentage by a
                # second PWM duty. Binary valves/heaters retain safe slow PWM.
                if cap.domain == "fan" and cap.fan_percentage:
                    min_speed = model.device_limits(self.manager, spec, cap)["fan_min_percentage"]
                    wanted = percentage_output_requested(demand, min_percentage=min_speed)
                elif cap.domain == "fan" and ordered_fan_stages(cap.fan_modes):
                    wanted = demand > 0
                else:
                    duty_demand = (
                        measured_fan_allocation.compensated_duty_percent
                        if measured_fan_allocation else demand
                    )
                    wanted = model.duty_on(
                        duty_demand, self.clock()-anchor, cfg["cycle_seconds"],
                        on_min, off_min, starting=output_off(state),
                    )
            else:
                # Hysteresis preserves current output until the opposite boundary.
                band = .3 if metric == "temperature" else 2 if metric == "humidity" else 50 if metric == "co2" else 2
                wanted = error > band or not output_off(state) and error > -band
            if power and (cap.domain != "number" and cap.domain != "input_number"):
                desired = mode if wanted else "off"
                if wanted and output_off(state) and cap.fan_modes and (
                    cfg.get("quiet_sleep") or cfg.get("quiet_occupied")
                ) and self._quiet_context(spec, cfg, plan) is None:
                    self._status(spec, "quiet_context_unknown")
                    return  # Never power on into an unknown quiet context.
                if (state.state == "off") != (desired == "off") or cap.domain == "climate" and state.state != desired:
                    await self._power(spec, cap, desired, automatic=True)
                    return
        elif not auto and mode != state.state and (cap.domain == "climate" or (mode == "off") != (state.state == "off")):
            await self._power(spec, cap, mode, automatic=False)
            return
        if cap.domain in ("number", "input_number") and auto:
            if not power or metric is None:
                self._status(spec, "proportional_output_not_commissioned")
                return
            value = 100. if demand is None and wanted else demand or 0.
            attrs = state.attributes
            current = finite(state.state, 0, 100)
            if attrs.get("unit_of_measurement") != "%" or attrs.get("min") != 0 or attrs.get("max") != 100 or current is None:
                self._status(spec, "proportional_output_not_verified")
                return
            on_min, off_min, _ = model.timing(self.manager, spec, cap)
            if current == 0 and value > 0:
                stamp = record["off_at"].setdefault(cap.primary, self.clock())
                if self.clock()-stamp < off_min:
                    self._status(spec, "minimum_off_hold")
                    return
            if value == 0 and current > 0:
                await self._power(spec, cap, "off", automatic=True, shutdown=bool(owned))
                return
            if self.clock()-record.get("output_at", 0) < cfg["sample_seconds"]:
                return
            value = round(max(current-10, min(current+10, value)), 1)
            step = finite(attrs.get("step", 1), .01, 10)
            if step is None:
                return
            value = max(0., min(100., round(value/step)*step))
            if abs(value-current) >= step:
                if await self._send(spec, cap, cap.primary, "set_value", {"value": value},
                                    {"state": str(value)}, power=True, mode=mode, automatic=True):
                    record["output_at"] = self.clock()
                return
        if auto and output_off(state) and not power:
            self._status(spec, "native_off_no_power_permission")
            return
        if auto or cfg.get("profile_targets", {}).get(model.profile_name(cfg, plan)) or cfg["preset"] != "none":
            if await self._native_target(spec, cap, mode, target, demand if not power else None, auto):
                return
            if spec.identifier in self._invalidated:
                return
        if await self._fan(spec, cap, cfg, plan,
                           demand if auto and cfg["control_mode"] == "pid" else None,
                           auto, measured_fan_allocation.speed
                           if measured_fan_allocation else None):
            return
        if spec.identifier in self._invalidated:
            return
        for key, service in (("swing_mode", "set_swing_mode"), ("swing_horizontal_mode", "set_swing_horizontal_mode")):
            if cfg.get(key) is not None and state.attributes.get(key) != cfg[key]:
                if await self._send(spec, cap, cap.primary, service, {key: cfg[key]}, {"attributes": {key: cfg[key]}}, automatic=auto):
                    return
        status = "controlling" if auto else "manual"
        if auto and wanted is False and output_off(state):
            # A selected PID method is not necessarily energizing the device:
            # expose duty-cycle idle vs ordinary deadband, without changing a
            # single actuator command, timer, protection, or ownership decision.
            status = ("pid_output_inactive" if cfg["control_mode"] == "pid"
                      and demand is not None and demand > 0
                      else "within_target_band")
        self._status(spec, status, demand_percent=demand,
                     profile=model.profile_name(cfg, plan), mode=mode, temperature=measured["temperature"],
                     humidity=measured["humidity"])
