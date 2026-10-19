"""Pure recommendation logic; independent of Home Assistant or I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import json

from .const import DEFAULT_THRESHOLDS, WEATHER_CLEAR


@dataclass(frozen=True)
class Reading:
    entity_id: str
    name: str
    metric: str
    value: float | None  # Normalized to the units documented in const.py.
    details: dict[str, float | int | str | list[str]] | None = None  # Derived mold data only.


@dataclass(frozen=True)
class Weather:
    entity_id: str
    condition: str | None
    temperature_c: float | None = None
    humidity: float | None = None
    wind_kmh: float | None = None


@dataclass(frozen=True)
class Warning:
    entity_id: str
    name: str
    active: bool | None  # None means unavailable / ambiguous => fail closed.


@dataclass(frozen=True)
class Window:
    entity_id: str
    name: str
    opened: bool | None


@dataclass(frozen=True)
class Room:
    area_id: str
    name: str
    windows: tuple[Window, ...]
    readings: tuple[Reading, ...]


@dataclass(frozen=True)
class Reason:
    code: str
    label: str = ""
    value: str = ""


@dataclass(frozen=True)
class Recommendation:
    action: str  # open | close
    area_id: str
    area_name: str
    windows: tuple[Window, ...]
    reasons: tuple[Reason, ...]

    @property
    def action_signature(self) -> str:
        """Stable identity of the window action, independent of measurements."""
        return json.dumps(
            [self.action, self.area_id, sorted(w.entity_id for w in self.windows)],
            ensure_ascii=False, separators=(",", ":"),
        )

    @property
    def reason_signature(self) -> str:
        """Identity of an ongoing cause, ignoring numeric sensor oscillations.

        A different pollutant or warning starts a fresh reminder interval;
        fluctuating CO₂ or wind values above the same threshold do not.
        Weather-condition text is categorical and therefore significant.
        """
        reasons = sorted(
            [reason.code, reason.label,
             reason.value if reason.code == "weather_condition" else ""]
            for reason in self.reasons
        )
        return json.dumps([self.action_signature, reasons], ensure_ascii=False,
                          separators=(",", ":"))


@dataclass(frozen=True)
class Plan:
    status: str  # open | close | idle | blocked
    outdoor_safe: bool
    outside_reasons: tuple[Reason, ...]
    recommendations: tuple[Recommendation, ...]
    diagnostics: tuple[tuple[str, str], ...]  # area name, missing-input reason
    unavailable_outdoor: tuple[str, ...] = ()  # Non-blocking missing entity IDs.
    rooms: tuple[Room, ...] = ()
    outdoor_readings: tuple[Reading, ...] = ()
    weather: tuple[Weather, ...] = ()
    warnings: tuple[Warning, ...] = ()
    # Informational derived physics; not an additional measured air pollutant.
    environment: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def signature(self) -> str:
        """Only actionable changes cause announcements, not numeric oscillations."""
        items = sorted(
            f"{rec.action}:{rec.area_id}:{','.join(sorted(w.entity_id for w in rec.windows))}"
            for rec in self.recommendations
        )
        return "|".join(items)


def _number(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:,.1f}" if value != int(value) else f"{value:,.0f}"


def _reading_reason(prefix: str, reading: Reading) -> Reason:
    from .const import UNIT_LABEL

    return Reason(
        f"{prefix}_{reading.metric}",
        reading.name,
        f"{_number(reading.value)} {UNIT_LABEL.get(reading.metric, '')}".strip(),
    )


def evaluate(
    outdoor: tuple[Reading, ...],
    weather: tuple[Weather, ...],
    warnings: tuple[Warning, ...],
    rooms: tuple[Room, ...],
    limits: dict[str, float] | None = None,
    environment: dict[str, dict[str, Any]] | None = None,
    extra_outside: tuple[Reason, ...] = (),
) -> Plan:
    """Block on known outdoor hazards; report missing AQ data separately."""
    thresholds = {**DEFAULT_THRESHOLDS, **(limits or {})}
    environmental = environment or {}
    outside: list[Reason] = list(extra_outside)
    unavailable_outdoor: list[str] = []

    # No configured sensors at all is a setup error, distinct from a selected
    # sensor currently reporting unknown/unavailable/stale.
    if not outdoor:
        outside.append(Reason("no_outdoor_data"))
    for reading in outdoor:
        if reading.metric == "aqi" and reading.value is not None:
            classification = (reading.details or {}).get("aqi", {})
            if classification.get("status") != "ready":
                unavailable_outdoor.append(reading.entity_id)
                outside.append(Reason("aqi_scale_unconfigured", reading.name))
                continue
            if classification.get("operational_unsafe"):
                outside.append(_reading_reason("outside", reading))
            continue
        limit = thresholds.get(f"outdoor_{reading.metric}")
        if reading.value is None or limit is None:
            unavailable_outdoor.append(reading.entity_id)
            continue  # Unknown is not unsafe and must not trigger 'close'.
        if reading.value > limit:
            outside.append(_reading_reason("outside", reading))

    if not weather:
        outside.append(Reason("no_weather_data"))
    for item in weather:
        if item.condition is None:
            outside.append(Reason("unavailable_weather", item.entity_id))
            continue
        if item.condition not in WEATHER_CLEAR:
            outside.append(Reason("weather_condition", item.entity_id, item.condition))
        if item.temperature_c is not None and item.temperature_c < thresholds["min_outdoor_temp"]:
            outside.append(Reason("weather_cold", item.entity_id, f"{_number(item.temperature_c)} °C"))
        if item.temperature_c is not None and item.temperature_c > thresholds["max_outdoor_temp"]:
            outside.append(Reason("weather_hot", item.entity_id, f"{_number(item.temperature_c)} °C"))
        if item.humidity is not None and item.humidity > thresholds["max_outdoor_humidity"]:
            outside.append(Reason("weather_humid", item.entity_id, f"{_number(item.humidity)} %"))
        if item.wind_kmh is not None and item.wind_kmh > thresholds["max_wind_kmh"]:
            outside.append(Reason("weather_wind", item.entity_id, f"{_number(item.wind_kmh)} km/h"))

    for warning in warnings:
        if warning.active is None:
            outside.append(Reason("unavailable_warning", warning.name))
        elif warning.active:
            outside.append(Reason("active_warning", warning.name))

    outdoor_safe = not outside
    recommendations: list[Recommendation] = []
    diagnostics: list[tuple[str, str]] = []
    for room in rooms:
        if not room.windows:
            diagnostics.append((room.name, "no_windows"))
            continue
        opened = tuple(win for win in room.windows if win.opened is True)
        closed = tuple(win for win in room.windows if win.opened is False)
        unknown = tuple(win for win in room.windows if win.opened is None)
        if unknown:
            diagnostics.append((room.name, "unknown_window_state"))

        # Input diagnostics must be visible even during rain, storms or
        # unavailable outdoor conditions, when opening is deliberately blocked.
        for item in room.readings:
            if item.metric != "mold" or item.value is not None:
                continue
            diagnostics.append((room.name, "mold_indicator_unavailable"))
            for missing in (item.details or {}).get("missing_inputs", []):
                if missing in (
                    "calibration", "indoor_temperature",
                    "outdoor_temperature", "humidity", "calculation",
                ):
                    diagnostics.append((room.name, f"mold_{missing}_unavailable"))

        if not outdoor_safe:
            if opened:
                recommendations.append(
                    Recommendation("close", room.area_id, room.name, opened, tuple(outside))
                )
            continue

        indoor_reasons: list[Reason] = []
        moisture_status = environmental.get(room.area_id, {}).get("moisture", {}).get("status")
        for reading in room.readings:
            limit = thresholds.get(f"indoor_{reading.metric}")
            if reading.value is None or limit is None:
                continue
            if reading.value >= limit:
                # Never recommend moisture-only airing when measured outdoor
                # vapor mass is clearly higher, even if outdoor RH looks benign.
                # CO2, PM and mold are evaluated independently; without
                # paired, valid temperature/RH data legacy rules still apply.
                if reading.metric == "humidity" and moisture_status == "humidifying":
                    diagnostics.append((room.name, "outdoor_more_humid_than_indoor"))
                    continue
                indoor_reasons.append(_reading_reason("inside", reading))

        if not any(reading.value is not None for reading in room.readings):
            diagnostics.append((room.name, "no_indoor_data"))
        elif indoor_reasons and closed and not opened:
            recommendations.append(
                Recommendation("open", room.area_id, room.name, closed, tuple(indoor_reasons))
            )

    has_open = any(rec.action == "open" for rec in recommendations)
    has_close = any(rec.action == "close" for rec in recommendations)
    status = "close" if has_close else "open" if has_open else "blocked" if not outdoor_safe else "idle"
    return Plan(
        status, outdoor_safe, tuple(outside), tuple(recommendations),
        tuple(diagnostics), tuple(unavailable_outdoor),
        tuple(rooms), tuple(outdoor), tuple(weather), tuple(warnings), environmental,
    )
