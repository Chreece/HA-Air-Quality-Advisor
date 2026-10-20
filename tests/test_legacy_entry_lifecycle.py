"""Legacy v0.5.1 entry lifecycle against minimal Home Assistant boundary stubs.

Exercises the real integration's setup/forwarding/services/unload paths, not
a guess about a config migration. No device service is connected or invoked.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_discovery import adapter

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "air_quality_advisor"


class ServiceRegistry:
    def __init__(self):
        self.callbacks={}
        self.registered=[]
        self.removed=[]

    def has_service(self,domain,action):
        return (domain,action) in self.callbacks

    def async_register(self,domain,action,fn,**kwargs):
        key=(domain,action)
        if key in self.callbacks:
            raise AssertionError("Duplicate service registration")
        self.callbacks[key]=fn
        self.registered.append(key)

    def async_remove(self,domain,action):
        self.callbacks.pop((domain,action),None)
        self.removed.append((domain,action))


class ConfigEntries:
    def __init__(self):
        self.updated=[]
        self.forwarded=[]
        self.unloaded=[]
        self.fail_forward=False

    def async_update_entry(self,entry,**values):
        self.updated.append((entry,values))
        for name,value in values.items():
            setattr(entry,name,value)

    async def async_forward_entry_setups(self,entry,platforms):
        self.forwarded.append((entry.entry_id,list(platforms)))
        if self.fail_forward:
            raise RuntimeError("Simulated sensor platform setup failure")

    async def async_unload_platforms(self,entry,platforms):
        self.unloaded.append((entry.entry_id,list(platforms)))
        return True


class FakeHttp:
    def __init__(self):
        self.static_paths=[]

    async def async_register_static_paths(self,paths):
        self.static_paths.extend(paths)


class FakeManager:
    instances=[]
    fail_start=False

    def __init__(self,hass,entry):
        self.hass=hass
        self.entry=entry
        self.started=False
        self.stopped=False
        self.calls=[]
        self.instances.append(self)

    async def async_start(self):
        self.started=True
        if self.fail_start:
            raise RuntimeError("Simulated manager startup failure")

    async def async_stop(self):
        self.stopped=True

    async def async_announce(self,**params):
        self.calls.append(("announce",params))
        return {"submitted":1}

    async def async_pid_control(self,**params):
        self.calls.append(("pid",params))
        return {"accepted":True}

    async def async_climate_control(self,area,action):
        self.calls.append(("climate",{"area":area,"action":action}))
        return {"accepted":True}


@pytest.fixture
def integration(adapter,monkeypatch):
    pkg="homeassistant"
    comps=types.ModuleType(pkg+".components")
    frontend=types.ModuleType(pkg+".components.frontend")
    http=types.ModuleType(pkg+".components.http")
    entries=types.ModuleType(pkg+".config_entries")
    helpers=types.ModuleType(pkg+".helpers.config_validation")
    probatio=types.ModuleType("probatio")
    native=types.ModuleType("custom_components.air_quality_advisor.manager")
    extras=[]
    frontend.add_extra_js_url=lambda hass,url: extras.append((hass,url))
    http.StaticPathConfig=lambda url,path,cache: SimpleNamespace(
        url=url,path=path,cache=cache,
    )
    entries.ConfigEntry=object
    helpers.config_entry_only_config_schema=lambda domain: {"domain":domain}
    helpers.string=str
    probatio.Schema=lambda x:x
    probatio.Required=lambda key:key
    probatio.Optional=lambda key,**kwargs:key
    probatio.In=lambda values:tuple(values)
    probatio.EnsureList=lambda:list
    probatio.All=lambda *parts:parts
    native.AirQualityManager=FakeManager
    for name,obj in {
        pkg+".components":comps,
        pkg+".components.frontend":frontend,
        pkg+".components.http":http,
        pkg+".config_entries":entries,
        pkg+".helpers.config_validation":helpers,
        "probatio":probatio,
        "custom_components.air_quality_advisor.manager":native,
    }.items():
        monkeypatch.setitem(sys.modules,name,obj)
    from homeassistant import core
    monkeypatch.setattr(core,"ServiceCall",object,raising=False)
    monkeypatch.setattr(core,"ServiceResponse",dict,raising=False)
    monkeypatch.setattr(core,"SupportsResponse",
                        SimpleNamespace(OPTIONAL="optional"),raising=False)
    FakeManager.instances=[]
    FakeManager.fail_start=False
    name="custom_components.air_quality_advisor._lifecycle_under_test"
    spec=importlib.util.spec_from_file_location(name,COMPONENT/"__init__.py")
    module=importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules,name,module)
    spec.loader.exec_module(module)
    return module,extras


def make_hass():
    return SimpleNamespace(data={},services=ServiceRegistry(),
                           config_entries=ConfigEntries(),http=FakeHttp())


def legacy_entry(number=1,title="Air Quality Advisor"):
    original={"areas":["living"],
              "excluded_window_entities":[],
              "excluded_indoor_entities":{"living":["sensor.legacy_co2"]},
              "weather_entities":["weather.home"],
              "outdoor_sensors":["sensor.outside_pm25"],
              "thresholds":{"indoor_co2":1200},
              "automatic_tts":False,
              "automatic_notifications":False,
              "language":"el"}
    return SimpleNamespace(entry_id=f"legacy-{number}",title=title,
                           data=original,options={})


def test_v05_entry_sets_up_without_schema_or_identity_migration(integration):
    module,js=integration
    h=make_hass()
    entry=legacy_entry()
    before=json.dumps(entry.data,sort_keys=True)
    assert asyncio.run(module.async_setup(h,{})) is True
    manifest=json.loads((COMPONENT/"manifest.json").read_text())
    assert js[0][1].endswith("?v="+manifest["version"])
    assert h.http.static_paths[0].url.startswith("/air_quality_advisor/")
    assert asyncio.run(module.async_setup_entry(h,entry)) is True
    assert entry.title=="Home Environment Manager"
    assert json.dumps(entry.data,sort_keys=True)==before
    assert entry.options=={}
    assert h.config_entries.forwarded==[("legacy-1",["sensor"])]
    assert set(h.services.callbacks)=={
        ("air_quality_advisor","announce"),
        ("home_environment_manager","announce"),
        ("air_quality_advisor","pid_control"),
        ("home_environment_manager","pid_control"),
        ("air_quality_advisor","climate_control"),
        ("home_environment_manager","climate_control"),
    }
    # No climate permission is implicitly created for a legacy entry.
    assert "climate_rooms" not in entry.data
    assert FakeManager.instances[0].started
    assert FakeManager.instances[0].calls==[]
    assert asyncio.run(module.async_unload_entry(h,entry)) is True
    assert FakeManager.instances[0].stopped
    assert h.services.callbacks=={}


def test_multiple_config_entries_register_once_and_unload_cleanly(integration):
    module,_=integration
    h=make_hass()
    first=legacy_entry(number=1)
    second=legacy_entry(number=2,title="Home Environment Advisor")
    asyncio.run(module.async_setup_entry(h,first))
    asyncio.run(module.async_setup_entry(h,second))
    assert len(h.services.registered)==6
    assert sorted(h.data["air_quality_advisor"])==["legacy-1","legacy-2"]
    assert asyncio.run(module.async_unload_entry(h,first))
    assert len(h.services.callbacks)==6
    assert not FakeManager.instances[1].stopped
    assert asyncio.run(module.async_unload_entry(h,second))
    assert len(h.services.callbacks)==0
    assert all(x.stopped for x in FakeManager.instances)


def test_setup_forwarding_and_partial_controller_start_failures_stop_manager(integration):
    module,_=integration
    h=make_hass()
    entry=legacy_entry()
    h.config_entries.fail_forward=True
    with pytest.raises(RuntimeError,match="platform setup"):
        asyncio.run(module.async_setup_entry(h,entry))
    assert FakeManager.instances[0].stopped
    assert "air_quality_advisor" not in h.data
    assert h.services.registered==[]
    h.config_entries.fail_forward=False
    FakeManager.fail_start=True
    with pytest.raises(RuntimeError,match="manager startup"):
        asyncio.run(module.async_setup_entry(h,entry))
    assert FakeManager.instances[-1].stopped
    assert h.services.registered==[]
