"""Scheduled reminders are per-room, bounded and cause-aware."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from test_discovery import adapter
from test_hub_manager import delivery_module

from custom_components.enviroment_manager.logic import (
    Plan, Reason, Recommendation, Window,
)


def recommendation(area="living", *, action="open", metric="inside_co2",
                   value="1,250 ppm", condition=None):
    reason = Reason(metric, "CO₂" if metric == "inside_co2" else "PM2.5", value)
    if condition is not None:
        reason = Reason("weather_condition", "weather.home", condition)
    return Recommendation(
        action, area, area.title(),
        (Window(f"binary_sensor.{area}_window", f"{area} window", action == "close"),),
        (reason,),
    )


def state(*recs):
    return Plan(
        "close" if any(rec.action == "close" for rec in recs)
        else "open" if recs else "idle",
        bool(recs), (), tuple(recs), (),
    )


class Clock:
    def __init__(self):
        self.now = 1000.0
        self.events = []

    def schedule(self, _hass, seconds, callback):
        event = {"seconds": seconds, "callback": callback, "cancelled": False,
                 "fired": False}
        self.events.append(event)

        def cancel():
            event["cancelled"] = True
        return cancel

    def outstanding(self, seconds=None):
        return [event for event in self.events
                if not event["cancelled"] and not event["fired"]
                and (seconds is None or event["seconds"] == seconds)]

    async def fire(self, seconds, index=0):
        events = self.outstanding(seconds)
        assert len(events) > index, f"No active timer of {seconds}s: {self.events}"
        event = events[index]
        event["fired"] = True
        self.now += seconds
        event["callback"](None)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return event


def prepare(module, monkeypatch, clock, plan, *, interval=None,
            auto_notify=True, auto_tts=False):
    config = {
        "automatic_notifications": auto_notify,
        "automatic_tts": auto_tts,
    }
    if interval is not None:
        config["announcement_repeat_minutes"] = interval
    hass = SimpleNamespace(async_create_task=asyncio.create_task)
    entry = SimpleNamespace(entry_id="entry", data=config, options={})
    manager = module.AirQualityManager(hass, entry)
    manager._active = True
    source = [plan]
    deliveries = []

    def capture():
        return source[0]

    async def announce(*, channels, areas):
        deliveries.append((channels, tuple(areas), clock.now))
        return {"submitted": 1}

    manager._capture = capture
    manager.async_announce = announce
    monkeypatch.setattr(module, "async_call_later", clock.schedule)
    monkeypatch.setattr(module, "monotonic", lambda: clock.now)
    return manager, source, deliveries


def test_default_10min_repeats_despite_15min_new_open_cooldown(monkeypatch, delivery_module):
    clock = Clock()
    async def scenario():
        manager, plans, deliveries = prepare(
            delivery_module, monkeypatch, clock, state(recommendation()))
        assert manager.repeat_minutes == 10
        manager._recalculate()
        assert len(clock.outstanding(90)) == 1
        await clock.fire(90)
        assert len(deliveries) == 1
        assert len(clock.outstanding(600)) == 1

        # A higher reading from the SAME CO₂ sensor must not restart the timer.
        plans[0] = state(recommendation(value="1,650 ppm"))
        manager._recalculate()
        assert len(clock.outstanding(600)) == 1
        await clock.fire(600)
        assert len(deliveries) == 2
        assert deliveries[1][1] == ("living",)
        # 600s is shorter than the anti-flapping cooldown (900s).
        assert len(clock.outstanding(600)) == 1

        # Recovering indoor air cancels all future reminders.
        plans[0] = state()
        manager._recalculate()
        assert not clock.outstanding()
        await manager.async_stop()
    asyncio.run(scenario())


@pytest.mark.parametrize("interval", [0, 1, 10, 1440])
def test_repeat_setting_controls_next_deadline(monkeypatch, delivery_module, interval):
    clock = Clock()
    async def scenario():
        manager, _, deliveries = prepare(
            delivery_module, monkeypatch, clock, state(recommendation()),
            interval=interval,
        )
        manager._recalculate()
        await clock.fire(90)
        assert len(deliveries) == 1
        if interval == 0:
            assert not clock.outstanding()
        else:
            assert len(clock.outstanding(interval * 60)) == 1
            await clock.fire(interval * 60)
            assert len(deliveries) == 2
        await manager.async_stop()
    asyncio.run(scenario())


def test_urgent_closing_announces_immediately_and_reminds_if_still_open(monkeypatch, delivery_module):
    clock = Clock()
    async def scenario():
        manager, plans, deliveries = prepare(
            delivery_module, monkeypatch, clock,
            state(recommendation(action="close",condition="rainy")),
        )
        manager._recalculate(initial=True)
        assert len(clock.outstanding(0)) == 1
        await clock.fire(0)
        assert len(deliveries) == 1
        await clock.fire(600)
        assert len(deliveries) == 2

        # The window is closed -> no close-window advice or reminder.
        plans[0] = state()
        manager._recalculate()
        assert not clock.outstanding()
        await manager.async_stop()
    asyncio.run(scenario())



@pytest.mark.parametrize("action, delay", [("close", 0), ("open", 90)])
def test_automatic_timer_callbacks_are_event_loop_safe(
    monkeypatch, delivery_module, action, delay,
):
    """Home Assistant sends unmarked timer callbacks to worker threads.

    Mimic the real HA @callback marker to prevent thread-unsafe calls to
    hass.async_create_task in the immediate and repeating timers.
    """
    def ha_callback(function):
        function.__hass_callback = True
        return function

    monkeypatch.setattr(delivery_module, "callback", ha_callback)
    clock = Clock()

    async def scenario():
        condition = "rainy" if action == "close" else None
        manager, _, deliveries = prepare(
            delivery_module, monkeypatch, clock,
            state(recommendation(action=action, condition=condition)),
        )
        manager._recalculate()
        pending = clock.outstanding(delay)
        assert len(pending) == 1
        assert getattr(pending[0]["callback"], "__hass_callback", False)

        await clock.fire(delay)
        assert len(deliveries) == 1

        reminders = clock.outstanding(600)
        assert len(reminders) == 1
        assert getattr(reminders[0]["callback"], "__hass_callback", False)

        await clock.fire(600)
        assert len(deliveries) == 2
        await manager.async_stop()

    asyncio.run(scenario())


def test_preexisting_open_recommendation_waits_for_interval_on_startup(monkeypatch, delivery_module):
    clock = Clock()
    async def scenario():
        manager, _, deliveries = prepare(
            delivery_module, monkeypatch, clock, state(recommendation()))
        manager._recalculate(initial=True)
        assert not clock.outstanding(90)
        assert len(clock.outstanding(600)) == 1
        await clock.fire(600)
        assert len(deliveries) == 1
        await manager.async_stop()
    asyncio.run(scenario())


def test_changed_reason_resets_only_that_rooms_reminder(monkeypatch, delivery_module):
    clock = Clock()
    async def scenario():
        living = recommendation("living")
        kitchen = recommendation("kitchen")
        manager, plans, deliveries = prepare(
            delivery_module, monkeypatch, clock, state(living, kitchen))
        manager._recalculate()
        await clock.fire(90, index=0)
        await clock.fire(90, index=0)
        assert len(clock.outstanding(600)) == 2
        living_timer = clock.outstanding(600)[0]
        kitchen_timer = clock.outstanding(600)[1]

        plans[0] = state(living, recommendation("kitchen", metric="inside_pm25",
                                               value="35 µg/m³"))
        manager._recalculate()
        assert len(clock.outstanding(600)) == 2
        assert living_timer["cancelled"] is False
        assert kitchen_timer["cancelled"] is True

        # An independent reminder in the living room still fires.
        await clock.fire(600)
        assert len(deliveries) == 3
        assert deliveries[-1][1] == ("living",)

        await manager.async_stop()
        assert not clock.outstanding()
    asyncio.run(scenario())


def test_categorical_weather_reason_changed_resets_interval(monkeypatch, delivery_module):
    clock = Clock()
    async def scenario():
        manager, plans, deliveries = prepare(
            delivery_module, monkeypatch, clock,
            state(recommendation(action="close", condition="rainy")),
            interval=2,
        )
        manager._recalculate()
        await clock.fire(0)
        original_timer = clock.outstanding(120)[0]
        plans[0] = state(recommendation(action="close", condition="snowy"))
        manager._recalculate()
        assert original_timer["cancelled"]
        assert len(clock.outstanding(120)) == 1
        await clock.fire(120)
        assert len(deliveries) == 2
        await manager.async_stop()
    asyncio.run(scenario())


def test_disabled_automatic_channels_and_zero_interval_schedule_nothing(monkeypatch, delivery_module):
    clock = Clock()
    async def scenario():
        manager, _, _ = prepare(
            delivery_module, monkeypatch, clock, state(recommendation()),
            auto_notify=False, auto_tts=False,
        )
        manager._recalculate()
        assert not clock.outstanding()
        await manager.async_stop()
    asyncio.run(scenario())


def test_numeric_changes_not_included_in_reason_signature():
    a = recommendation(value="1,250 ppm")
    b = recommendation(value="1,987 ppm")
    c = recommendation(metric="inside_pm25", value="30 µg/m³")
    assert a.action_signature == b.action_signature == c.action_signature
    assert a.reason_signature == b.reason_signature
    assert c.reason_signature != b.reason_signature
    assert recommendation(action="close",condition="rainy").reason_signature != (
        recommendation(action="close",condition="snowy").reason_signature
    )
