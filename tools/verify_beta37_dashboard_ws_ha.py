"""Real Home Assistant 2026.10 Recorder-safe sensor and dashboard WS check.

Exercise actual HA 2026.10 entity registries, a recommendation state and the
registered command handler. Nothing performs a hardware service call.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import MappingProxyType, SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.config_entries import ConfigEntry, ConfigEntries, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.components import websocket_api
from custom_components.environment_manager.const import DEFAULT_THRESHOLDS, DOMAIN
from custom_components.environment_manager.dashboard_api import (
    COMMAND, websocket_dashboard, async_register_dashboard_api,
)
from custom_components.environment_manager.logic import Plan, Room, Reading, Window
from custom_components.environment_manager.sensor import AirQualityRecommendation


def entry(domain, identity):
    return ConfigEntry(
        data={},options={},domain=domain,entry_id=identity,title=identity,
        source=SOURCE_USER,unique_id=identity,version=1,minor_version=1,
        discovery_keys=MappingProxyType({}),subentries_data=(),
    )


class Connection:
    def __init__(self, allowed):
        self.results=[]
        self.errors=[]
        self.user=SimpleNamespace(
            is_admin=False,
            permissions=SimpleNamespace(check_entity=lambda entity_id,policy:
                allowed and entity_id.startswith("sensor.") and policy==POLICY_READ),
        )

    def send_result(self, ident, data):
        self.results.append((ident,data))

    def send_error(self, ident, code, message):
        self.errors.append((ident,code,message))


async def verify(directory):
    hass=HomeAssistant(directory)
    hass.config_entries=ConfigEntries(hass,{})
    dr.async_setup(hass)
    await ar.async_load(hass)
    await dr.async_load(hass)
    await er.async_load(hass)

    conf=entry(DOMAIN,"recorder-budget-entry")
    hass.config_entries._entries[conf.entry_id]=conf
    registry=er.async_get(hass)
    reg=registry.async_get_or_create(
        "sensor",DOMAIN,f"{conf.entry_id}_recommendation",
        config_entry=conf,suggested_object_id="window_recommendations",
    )
    # Dozens of valid room readouts yield a WS snapshot well beyond 16 KiB.
    # None of these records are written into the sensor's Recorder attributes.
    rooms=tuple(
        Room(
            f"area_{i}",f"Monitored room {i}",
            (Window(f"binary_sensor.window_{i}",f"Window {i}",False),),
            tuple(Reading(f"sensor.air_{i}_{j}",f"Reading {j}","co2",
                          600+j*30) for j in range(12)),
        ) for i in range(60)
    )
    plan=Plan("idle",True,(),(),(),rooms=rooms)
    manager=SimpleNamespace(
        plan=plan,thresholds=dict(DEFAULT_THRESHOLDS),entry=conf,
        settings={"language":"en"},
        get_language=lambda value:"en",hub_available=False,
        repeat_minutes=10,
    )
    hass.data.setdefault(DOMAIN,{})[conf.entry_id]=manager

    recommendation=AirQualityRecommendation(manager,conf.entry_id)
    attributes=recommendation.extra_state_attributes
    encoded=json.dumps(attributes,ensure_ascii=True,separators=(",",":")).encode()
    assert len(encoded)<16384,len(encoded)
    assert "dashboard" not in attributes
    assert attributes["dashboard_api"]==COMMAND
    assert attributes["dashboard_revision"]==0
    assert attributes["dashboard_version"]==1
    hass.states.async_set(reg.entity_id,recommendation.native_value,attributes)

    async_register_dashboard_api(hass)
    assert websocket_dashboard._ws_command==COMMAND
    approved=Connection(allowed=True)
    websocket_dashboard(hass,approved,{"id":1,"entity_id":reg.entity_id})
    assert approved.errors==[]
    assert len(approved.results)==1
    snapshot=approved.results[0][1]
    assert snapshot["version"]==1
    assert len(snapshot["rooms"])==60
    assert len(snapshot["rooms"][0]["readings"])==12
    assert len(json.dumps(snapshot,ensure_ascii=True).encode())>16384

    rejected=Connection(allowed=False)
    websocket_dashboard(hass,rejected,{"id":2,"entity_id":reg.entity_id})
    assert rejected.results==[]
    assert rejected.errors[0][1]==websocket_api.ERR_UNAUTHORIZED

    missing=Connection(allowed=True)
    websocket_dashboard(hass,missing,{
        "id":3,"entity_id":"sensor.unrelated_recommendation",
    })
    assert missing.results==[]
    assert missing.errors[0][1]==websocket_api.ERR_NOT_FOUND

    conf2=entry(DOMAIN,"different-installation")
    hass.config_entries._entries[conf2.entry_id]=conf2
    wrong=registry.async_get_or_create(
        "sensor",DOMAIN,"mismatched_recommendation_unique_id",
        config_entry=conf2,suggested_object_id="mismatch",
    )
    spoof=Connection(allowed=True)
    websocket_dashboard(hass,spoof,{"id":4,"entity_id":wrong.entity_id})
    assert spoof.errors[0][1]==websocket_api.ERR_NOT_FOUND
    assert spoof.results==[]
    assert not hass.services.has_service("climate","set_hvac_mode")
    await hass.async_block_till_done()
    await hass.async_stop(force=True)
    print("HA 2026.10: Recorder < 16KiB, full authenticated dashboard WS, denied cross-entry reads: PASS")


if __name__=="__main__":
    with TemporaryDirectory(prefix="hem-recorder-ws-") as directory:
        asyncio.run(verify(directory))
