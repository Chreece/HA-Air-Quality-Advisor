"""Regressions for HA event-loop blocking and room feedback floods.

The test exercises actual Manager callbacks without any native actuator
services. A timestamp-only plan refresh may update safety freshness, but it
must not rebroadcast all Home/Room/Controller entities.
"""
from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import pytest

from test_discovery import adapter
from test_hub_manager import delivery_module
from test_legacy_entry_lifecycle import integration, make_hass
from custom_components.environment_manager.logic import Plan


def _snapshot(clock, status="ready"):
    return Plan(
        "idle", False, (), (), (),
        environment={"bath": {
            "climate_plan": {
                "status": status,
                "air_evidence_at": float(clock),
                "profile": "home",
            },
        }},
    )


def _manager(module, monkeypatch):
    manager = module.AirQualityManager(
        SimpleNamespace(),
        SimpleNamespace(entry_id="entry", data={}, options={}),
    )
    manager._active = True
    for name in (
        "pid", "native_climate", "direct_climate", "native_humidity",
        "humidity_power", "secondary_climate", "running_fans",
        "fan_power", "native_air_mode", "equipment",
    ):
        setattr(getattr(manager, name), "schedule", lambda *a, **kw: None)
    monkeypatch.setattr(module, "equipment_legacy_settings", lambda m: ({}, {}))
    return manager


def test_timestamp_only_recalculations_do_not_broadcast(delivery_module, monkeypatch):
    module = delivery_module
    manager = _manager(module, monkeypatch)
    reports = []
    monkeypatch.setattr(module, "async_dispatcher_send", lambda *args: reports.append(args))
    manager.plan = _snapshot(100.0)
    source = [_snapshot(101.0)]
    manager._capture = lambda: source[0]

    for clock in range(101, 220):
        source[0] = _snapshot(clock)
        manager._recalculate()
        assert manager.plan.environment["bath"]["climate_plan"]["air_evidence_at"] == clock
    assert reports == [], "No fan evidence clock is a public state change"

    source[0] = _snapshot(220, status="blocked")
    manager._recalculate()
    assert len(reports) == 1, "A genuine controller change is published once"
    source[0] = _snapshot(221, status="blocked")
    manager._recalculate()
    assert len(reports) == 1


def test_self_originated_and_unchanged_sensor_events_do_not_recalculate(
    delivery_module, monkeypatch,
):
    manager = _manager(delivery_module, monkeypatch)
    manager._tracked = {"sensor.native", "sensor.manager_derived"}
    from custom_components.environment_manager import room_sources

    monkeypatch.setattr(room_sources, "native",
                        lambda hass, eid: eid == "sensor.native")
    calls = []
    manager._recalculate = lambda *args, **kwargs: calls.append(1)

    def state(value):
        return SimpleNamespace(state=value, attributes={"unit_of_measurement": "°C"})

    def event(eid, old, new):
        return SimpleNamespace(data={
            "entity_id": eid, "old_state": old, "new_state": new,
        })

    manager._on_state_changed(
        event("sensor.manager_derived", state("20"), state("21"))
    )
    manager._on_state_changed(event("sensor.native", state("20"), state("20")))
    assert calls == []
    manager._on_state_changed(event("sensor.native", state("20"), state("21")))
    assert calls == [1]


def test_manifest_read_occurs_in_executor_not_on_event_loop(integration, monkeypatch):
    module, extra_urls = integration
    hass = make_hass()
    reads = []
    executed = []
    original = Path.read_text

    def checked_read(self, *args, **kwargs):
        if self.name == "manifest.json":
            reads.append(str(self))
            with pytest.raises(RuntimeError, match="no running event loop"):
                asyncio.get_running_loop()
        return original(self, *args, **kwargs)

    async def executor(callback, *args):
        executed.append(True)
        return await asyncio.to_thread(callback, *args)

    monkeypatch.setattr(Path, "read_text", checked_read)
    hass.async_add_executor_job = executor

    assert asyncio.run(module.async_setup(hass, {})) is True
    assert len(reads) == 1
    assert len(executed) == 1
    assert extra_urls[0][1].startswith("/environment_manager/")
