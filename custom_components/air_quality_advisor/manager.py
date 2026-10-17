"""Event-driven observations and optional, rate-limited action delivery."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from time import monotonic
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
    DEFAULT_THRESHOLDS, DOMAIN, SIGNAL_UPDATED,
)
from .ai_rewrite import DEFAULT_AGENT, ai_effectively_enabled, async_rewrite_announcement
from .hub_delivery import hub_available, make_hub_payload, async_submit_hub, async_system_notification
from .discovery import entity_area, reading, rooms, warning, weather
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
        self._tracked = (
            selected_outdoor
            | set(config.get(CONF_WEATHER, []))
            | set(config.get(CONF_WARNINGS, []))
            | {s.entity_id for room in selected_rooms for s in (*room.windows, *room.readings)}
        )
        return evaluate(
            tuple(reading(self.hass, ent, max_age, outdoor=True) for ent in sorted(selected_outdoor)),
            tuple(weather(self.hass, ent, max_age) for ent in config.get(CONF_WEATHER, [])),
            tuple(warning(self.hass, ent, max_age) for ent in config.get(CONF_WARNINGS, [])),
            selected_rooms,
            self.thresholds,
        )

    async def async_start(self) -> None:
        """Track sensor changes and periodically recheck freshness and new entities."""
        self._active = True
        self._unsubs.extend((
            self.hass.bus.async_listen(EVENT_STATE_CHANGED, self._on_state_changed),
            self.hass.bus.async_listen("entity_registry_updated", self._on_registry_changed),
            self.hass.bus.async_listen("device_registry_updated", self._on_registry_changed),
            self.hass.bus.async_listen("area_registry_updated", self._on_registry_changed),
            async_track_time_interval(self.hass, self._on_interval, timedelta(minutes=5)),
        ))
        self._recalculate(initial=True)

    @callback
    def _on_registry_changed(self, _event: Event) -> None:
        self._recalculate()

    @callback
    def _on_interval(self, _now: Any) -> None:
        self._recalculate()

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

        previous = self._active_actions
        current = {
            rec.area_id: (rec.action_signature, rec.reason_signature)
            for rec in new_plan.recommendations
        }
        for area_id in previous.keys() - current.keys():
            self._cancel_pending(area_id)
            self._cancel_repeat(area_id)
        # Install the current keys before arming timers, so callbacks always
        # recheck the latest action and cause.
        self._active_actions = current
        for rec in new_plan.recommendations:
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
            lambda _now: self._execute_automatic(area_id, action_key, reason_key),
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
            lambda _now: self._execute_automatic(
                area_id, action_key, reason_key, repeat=True
            ),
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
            (rec for rec in self.plan.recommendations if rec.area_id == area_id),
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
                unsubscribe()

    @callback
    def _cancel_repeat(self, area_id: str | None = None) -> None:
        selected = (
            list(self._repeat_unsubs)
            if area_id is None else [area_id]
        )
        for key in selected:
            unsubscribe = self._repeat_unsubs.pop(key, None)
            if unsubscribe is not None:
                unsubscribe()

    async def async_stop(self) -> None:
        self._active = False
        self._cancel_pending()
        self._cancel_repeat()
        self._active_actions.clear()
        for unsubscribe in self._unsubs:
            unsubscribe()
        self._unsubs.clear()
        # Do not leave work running across an options reload or HA shutdown.
        pending = tuple(self._tasks)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self._tasks.clear()

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
        if not self.plan.recommendations:
            return {"submitted": 0, "reason": "No actionable window recommendations"}

        localized = self.get_language(language)
        requested_language = language or config.get(CONF_LANGUAGE, "auto")
        sent = 0
        errors: list[str] = []
        for rec in self.plan.recommendations:
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
                if await async_submit_hub(self.hass, hub_payload):
                    sent += 1
                    continue

            # No Hub, stopped Hub, failed enqueue, or no routed Hub outputs:
            # deliver using regular Home Assistant services.
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
            # HA persistent notifications are the final visual fallback even
            # when no custom direct outputs are configured.
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
