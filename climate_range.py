"""Native heat/cool range control with independent thermostat regulation.

This supports ClimateEntityFeature.TARGET_TEMPERATURE_RANGE (bit 2). It never
switches on an OFF HVAC device, time-proportions compressor power or fabricates
a missing low/high device target.
"""
from __future__ import annotations
import asyncio
import logging
from typing import Any

from .pid_math import bounded_command, finite, target_from_unit

_LOGGER=logging.getLogger(__name__)
WRITE_TIMEOUT_SECONDS=20
ACK_GRACE_SECONDS=120


async def async_apply_native_range(controller: Any, area: str,
                                   settings: dict, report: dict,
                                   now: float) -> None:
    entity=settings.get("climate_entity")
    state=controller.hass.states.get(entity)
    if state is None or state.state in ("unknown","unavailable"):
        controller.statuses[area]={"status":"unavailable"}
        return
    if state.state=="off":
        controller.paused[area]="thermostat_turned_off"
        controller._save()
        controller.statuses[area]={"status":"paused","reason":controller.paused[area]}
        return
    # An unexpected mode change after this manager commanded a different
    # HVAC mode is treated as a manual intervention, not silently adopted.
    previous_mode=controller.expected_hvac.get(area)
    if previous_mode is not None and previous_mode!=state.state:
        controller.paused[area]="manual_hvac_mode_change"
        controller._save()
        controller.statuses[area]={"status":"paused","reason":"manual_hvac_mode_change"}
        return
    # The device's own heat/cool mode must already be in operation. A
    # transition to heat_cool is not inferred from a partial capability list.
    if state.state!="heat_cool":
        controller.statuses[area]={"status":"native_heat_cool_mode_required"}
        return
    attrs=state.attributes
    modes=attrs.get("hvac_modes",[])
    try:features=int(attrs.get("supported_features",0))
    except (ValueError,TypeError,OverflowError):features=0
    if (not isinstance(modes,list) or "heat_cool" not in modes or not features&2):
        controller.statuses[area]={"status":"native_range_not_supported"}
        return
    preset=str(attrs.get("preset_mode") or "").casefold()
    if preset not in ("","none","manual"):
        controller.statuses[area]={"status":"native_preset_active","preset":preset}
        return
    unit=str(attrs.get("temperature_unit") or "")
    if unit not in ("°C","C","°F","F"):
        controller.statuses[area]={"status":"unsupported_unit"}
        return
    device_min=finite(attrs.get("min_temp"),-30,140)
    device_max=finite(attrs.get("max_temp"),-29,150)
    device_step=finite(attrs.get("target_temp_step"),0.1,10)
    original_low=finite(attrs.get("target_temp_low"),-30,150)
    original_high=finite(attrs.get("target_temp_high"),-30,150)
    desired_low=finite(report.get("low_target_c"),5,35)
    desired_high=finite(report.get("high_target_c"),6,40)
    if None in (device_min,device_max,device_step,original_low,original_high,
                desired_low,desired_high):
        controller.statuses[area]={"status":"range_measurements_or_limits_unknown"}
        return
    old_low=target_from_unit(original_low,unit)
    old_high=target_from_unit(original_high,unit)
    if (None in (old_low,old_high) or old_high-old_low<0.5 or
            desired_high-desired_low<1.0):
        controller.statuses[area]={"status":"invalid_native_range"}
        return
    previous=controller.expected.get(area)
    if previous is not None:
        sent=finite(previous.get("when"),0,1e13)
        confirmed_low=finite(previous.get("low"),-30,150)
        confirmed_high=finite(previous.get("high"),-30,150)
        if None in (sent,confirmed_low,confirmed_high):
            controller.paused[area]="native_setpoint_mode_changed"
        elif (abs(original_low-confirmed_low)>max(0.05,device_step*.51)
              or abs(original_high-confirmed_high)>max(0.05,device_step*.51)):
            if now-sent<ACK_GRACE_SECONDS:
                controller.statuses[area]={"status":"waiting_for_native_range_ack"}
                return
            controller.paused[area]="manual_native_range_change"
        if area in controller.paused:
            controller._save()
            controller.statuses[area]={"status":"paused","reason":controller.paused[area]}
            return
    low_state,low_native=bounded_command(
        desired_low,old_low,max_change_c=.5,min_change_c=.15,unit=unit,
        device_min=device_min,device_max=device_max,device_step=device_step,
    )
    high_state,high_native=bounded_command(
        desired_high,old_high,max_change_c=.5,min_change_c=.15,unit=unit,
        device_min=device_min,device_max=device_max,device_step=device_step,
    )
    if low_state=="no_meaningful_change":low_native=original_low
    if high_state=="no_meaningful_change":high_native=original_high
    if low_state not in ("command","no_meaningful_change") or high_state not in (
        "command","no_meaningful_change"
    ):
        controller.statuses[area]={"status":"range_rate_limit_or_device_step"}
        return
    if low_state==high_state=="no_meaningful_change":
        controller.statuses[area]={"status":"native_range_at_setpoint",
                                  "low_c":desired_low,"high_c":desired_high}
        return
    new_low=target_from_unit(low_native,unit)
    new_high=target_from_unit(high_native,unit)
    if new_low is None or new_high is None or new_high-new_low<1.0:
        controller.statuses[area]={"status":"range_setpoints_too_close"}
        return
    if not controller.hass.services.has_service("climate","set_temperature"):
        controller.statuses[area]={"status":"temperature_service_unavailable"}
        return
    try:
        await asyncio.wait_for(controller.hass.services.async_call(
            "climate","set_temperature",
            {"target_temp_low":low_native,"target_temp_high":high_native},
            target={"entity_id":entity},blocking=True,
        ),WRITE_TIMEOUT_SECONDS)
    except asyncio.CancelledError:
        raise
    except Exception:
        _LOGGER.exception("Native range write failed for %s",entity)
        controller.paused[area]="native_range_service_failure"
        controller._save()
        controller.statuses[area]={"status":"paused","reason":controller.paused[area]}
        return
    controller.expected[area]={"low":low_native,"high":high_native,"when":now}
    controller.last_write[area]=now
    controller._save()
    controller.statuses[area]={"status":"native_range_commanded",
        "low_c":desired_low,"high_c":desired_high,
        "native_low":low_native,"native_high":high_native,
        "note":"device_internal_heat_cool_regulation"}
