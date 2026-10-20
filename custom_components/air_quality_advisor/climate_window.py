"""Advisory substitution of verified mechanical conditioning with window airing.

A window can sometimes provide sensible cooling, limited warming or moisture
removal. This is a conditional *opportunity*, NOT a guaranteed equivalent
energy saving, room temperature forecast, or power-control command.

No external service calls. Outdoor AQ/weather and indoor measurements must be
qualified, a matching actual HVAC/dehumidifier mode must be active, and a real
closed window must exist in the selected Home Assistant area.
"""
from __future__ import annotations

from math import isfinite
from typing import Any

from .climate_coordination import device_inventory


AIR_POLLUTANTS = frozenset(("aqi", "pm25", "pm10", "no2", "o3", "so2"))
RUNNING_ACTIONS = {"heating": "heat", "cooling": "cool", "drying": "dry"}


def _number(value: Any, low: float, high: float) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return x if isfinite(x) and low <= x <= high else None


def _running_effects(hass: Any, area: str, config: dict) -> list[tuple[str, str]]:
    """Require native HVAC action or known dedicated dehumidifier power."""
    from .discovery import entity_area

    inventory = device_inventory(hass, area, config)
    active: dict[str, str] = {}
    for item in inventory.values():
        if item.get("status") != "ready":
            continue
        entity = item.get("entity_id")
        if not isinstance(entity, str) or entity_area(hass, entity) != area:
            continue
        state = hass.states.get(entity)
        if state is None:
            continue
        if item.get("domain") == "climate":
            caps = item.get("capabilities", {})
            mode = state.state
            action = state.attributes.get("hvac_action")
            effect = RUNNING_ACTIONS.get(action)
            # A device exposing only one mode remains eligible. DRY selected
            # without hvac_action does NOT prove compressor operation.
            if (effect == "heat" and mode in ("heat", "auto", "heat_cool")
                    and caps.get("heating")):
                active[entity] = effect
            elif (effect == "cool" and mode in ("cool", "auto", "heat_cool")
                  and caps.get("cooling")):
                active[entity] = effect
            elif (effect == "dry" and mode == "dry" and caps.get("drying")):
                active[entity] = effect
        elif (item.get("domain") == "humidifier"
              and item.get("device_class") == "dehumidifier"
              and state.state == "on"):
            active[entity] = "dry"
    return [(entity, effect) for entity, effect in active.items()]


def window_substitution(
    hass: Any, room: Any, settings: dict, plan: dict, science: dict,
    weather: tuple, outdoor: tuple, *,
    outside_safe: bool | None,
) -> dict:
    """Choose a single well-supported window alternative, never operate it."""
    base = {"automatic_control": False, "type": "window_efficiency_advice"}
    if not isinstance(settings, dict) or settings.get("enabled") is not True:
        return {**base, "status": "disabled"}
    windows = getattr(room, "windows", ())
    if not windows:
        return {**base, "status": "window_contact_not_configured"}
    if any(w.opened is None for w in windows):
        return {**base, "status": "window_state_unknown"}
    if any(w.opened is True for w in windows):
        return {**base, "status": "window_already_open"}
    if outside_safe is not True:
        return {**base, "status": "outside_conditions_not_safe"}
    # An empty or stale AQ sensor is not proof that outdoor air is harmless.
    measured = [r for r in outdoor if r.metric in AIR_POLLUTANTS]
    if not measured or any(r.value is None for r in measured):
        return {**base, "status": "outdoor_pollutants_not_verified"}
    if any(r.metric == "aqi" and (r.details or {}).get("aqi", {}).get("status") != "ready"
           for r in measured):
        return {**base, "status": "outdoor_aqi_scale_unverified"}
    if len(weather) != 1:
        return {**base, "status": "weather_source_missing_or_ambiguous"}
    outdoor_c = _number(getattr(weather[0], "temperature_c", None), -40, 55)
    if outdoor_c is None:
        return {**base, "status": "outdoor_temperature_unknown"}
    if plan.get("away") == "away" or plan.get("occupancy") == "unoccupied":
        return {**base, "status": "nobody_available_to_open_window"}

    effects = _running_effects(hass, room.area_id, settings)
    kinds = {kind for _, kind in effects}
    if not effects:
        return {**base, "status": "no_active_verified_equipment"}
    if len(kinds) != 1:
        return {**base, "status": "multiple_mechanical_needs"}
    effect = next(iter(kinds))
    device = effects[0][0]
    indoor_c = _number(plan.get("temperature_c"), -10, 50)
    evidence: dict[str, Any] = {}
    code = ""
    if effect == "cool":
        if indoor_c is None:
            return {**base, "status": "indoor_temperature_missing"}
        difference = indoor_c - outdoor_c
        if difference < 2:
            return {**base, "status": "insufficient_free_cooling"}
        code = "climate_window_cool"
        evidence = {"temperature_difference_c": round(difference, 1),
                    "indoor_temperature_c": indoor_c, "outdoor_temperature_c": outdoor_c}
    elif effect == "heat":
        if indoor_c is None:
            return {**base, "status": "indoor_temperature_missing"}
        difference = outdoor_c - indoor_c
        # The outside air must be able to reach the desired indoor heating
        # target; merely being slightly warmer would overpromise substitution.
        desired = _number(plan.get("temperature_target_c"), 5, 36)
        if desired is None or difference < 2 or outdoor_c < desired - 0.25:
            return {**base, "status": "insufficient_free_warming"}
        code = "climate_window_heat"
        evidence = {"temperature_difference_c": round(difference, 1),
                    "indoor_temperature_c": indoor_c, "outdoor_temperature_c": outdoor_c}
    else:
        humidity = plan.get("humidity_management", {})
        if (not isinstance(humidity, dict) or
                humidity.get("status") != "advisory" or
                humidity.get("action") != "dry"):
            return {**base, "status": "no_verified_drying_demand"}
        if indoor_c is None:
            return {**base, "status": "indoor_temperature_missing_for_moisture"}
        moisture = science.get("moisture", {}) if isinstance(science, dict) else {}
        if not isinstance(moisture, dict) or moisture.get("status") != "drying":
            return {**base, "status": "measured_outdoor_drying_not_verified"}
        advantage = _number(moisture.get("drying_potential_g_kg"), 0, 30)
        target_rh = _number(settings.get("humidity_high_rh", 60), 30, 80)
        projected = _number(moisture.get("outside_air_rh_when_warmed_percent"), 0, 100)
        # Prefer shorter airing if outside air would create a large heating
        # burden. Do not equate a window to dehumidifier performance.
        if (advantage is None or advantage < 1.5 or target_rh is None
                or projected is None or projected > target_rh - 2):
            return {**base, "status": "drying_effect_insufficient"}
        if indoor_c - outdoor_c > 12:
            return {**base, "status": "excessive_heat_loss_for_drying"}
        code = "climate_window_dry"
        evidence = {"humidity_ratio_advantage_g_kg": round(advantage, 1),
                    "outside_rh_when_warmed_percent": round(projected, 1),
                    "indoor_temperature_c": indoor_c, "outdoor_temperature_c": outdoor_c}
    return {**base, "status": "opportunity", "code": code,
            "effect": effect, "active_device": device, "evidence": evidence,
            "reason": "measured_outdoor_air_may_reduce_mechanical_conditioning",
            "note": "Opening a window is a manual, conditional opportunity; do not automatically turn off HVAC equipment."}


def window_reason(opportunity: dict):
    """Build stable, localized reason codes; keep numbers out of dedup keys."""
    from .logic import Reason

    effect = opportunity.get("effect")
    data = opportunity.get("evidence", {})
    if effect in ("heat", "cool"):
        value = _number(data.get("temperature_difference_c"), 0, 50)
        unit = "°C"
    elif effect == "dry":
        value = _number(data.get("humidity_ratio_advantage_g_kg"), 0, 30)
        unit = "g/kg"
    else:
        raise ValueError("Unsupported window opportunity")
    if value is None:
        raise ValueError("Window opportunity must provide physical evidence")
    return Reason("climate_window_" + effect,
                  str(opportunity.get("active_device") or ""),
                  f"{value:g} {unit}")
