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
COMPONENT = ROOT / "custom_components" / "enviroment_manager"
CANONICAL_DOMAIN = "enviroment_manager"
LEGACY_DOMAIN = "air" + "_quality_advisor"
PUBLIC_ACTION_DOMAIN = "home_environment_manager"


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


from test_room_hubs import ConfigEntries as RoomConfigEntries, Subentry


class ConfigEntries(RoomConfigEntries):
    def __init__(self):
        super().__init__()
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

    def climate_diagnostics(self,area=None):
        return {"read_only":True,"rooms":(
            [{"area_id":"living","devices":[]}] if area in (None,"living") else []
        )}


@pytest.fixture
def integration(adapter,monkeypatch):
    pkg="homeassistant"
    comps=types.ModuleType(pkg+".components")
    frontend=types.ModuleType(pkg+".components.frontend")
    http=types.ModuleType(pkg+".components.http")
    entries=types.ModuleType(pkg+".config_entries")
    helpers=types.ModuleType(pkg+".helpers.config_validation")
    probatio=types.ModuleType("probatio")
    native=types.ModuleType("custom_components.enviroment_manager.manager")
    extras=[]
    frontend.add_extra_js_url=lambda hass,url: extras.append((hass,url))
    http.StaticPathConfig=lambda url,path,cache: SimpleNamespace(
        url=url,path=path,cache=cache,
    )
    entries.ConfigEntry=object
    entries.ConfigSubentry=Subentry
    entries.ConfigEntryChange=SimpleNamespace(UPDATED="updated")
    entries.SIGNAL_CONFIG_ENTRY_CHANGED="config_entry_changed"
    dispatcher=types.ModuleType("homeassistant.helpers.dispatcher")
    dispatcher.async_dispatcher_connect=lambda *args: lambda: None
    monkeypatch.setitem(sys.modules,dispatcher.__name__,dispatcher)
    helpers.config_entry_only_config_schema=lambda domain: {"domain":domain}
    helpers.string=str
    probatio.Schema=lambda x:x
    probatio.Required=lambda key:key
    probatio.Optional=lambda key,**kwargs:key
    probatio.In=lambda values:tuple(values)
    probatio.EnsureList=lambda:list
    probatio.All=lambda *parts:parts
    native.AirQualityManager=FakeManager
    # Earlier tests may have cached the concrete manager as a package
    # attribute even after its sys.modules entry was temporarily replaced.
    parent=sys.modules["custom_components.enviroment_manager"]
    monkeypatch.setattr(parent,"manager",native,raising=False)
    for name,obj in {
        pkg+".components":comps,
        pkg+".components.frontend":frontend,
        pkg+".components.http":http,
        pkg+".config_entries":entries,
        pkg+".helpers.config_validation":helpers,
        "probatio":probatio,
        "custom_components.enviroment_manager.manager":native,
    }.items():
        monkeypatch.setitem(sys.modules,name,obj)
    from homeassistant import core
    monkeypatch.setattr(core,"callback",lambda f:f,raising=False)
    monkeypatch.setattr(core,"ServiceCall",object,raising=False)
    monkeypatch.setattr(core,"ServiceResponse",dict,raising=False)
    monkeypatch.setattr(core,"SupportsResponse",
                        SimpleNamespace(OPTIONAL="optional"),raising=False)
    from homeassistant.helpers import device_registry as dr
    from test_device_hierarchy import DeviceRegistry
    registry = DeviceRegistry()
    monkeypatch.setattr(dr, "DeviceEntryType", SimpleNamespace(SERVICE="service"), raising=False)
    monkeypatch.setattr(dr, "async_get", lambda hass: registry)
    FakeManager.instances=[]
    FakeManager.fail_start=False
    name="custom_components.enviroment_manager._lifecycle_under_test"
    spec=importlib.util.spec_from_file_location(name,COMPONENT/"__init__.py")
    module=importlib.util.module_from_spec(spec)
    # spec_from_file_location sees "__init__.py" and otherwise treats the
    # test alias as a brand-new nested package. Preserve the real parent
    # for relative imports without altering the installed HA package.
    module.__package__="custom_components.enviroment_manager"
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
                           data=original,options={},subentries={},
                           async_on_unload=lambda callback:None)


def test_v05_entry_sets_up_without_schema_or_identity_migration(integration):
    module,js=integration
    h=make_hass()
    entry=legacy_entry()
    before=json.dumps(entry.data,sort_keys=True)
    assert asyncio.run(module.async_setup(h,{})) is True
    manifest=json.loads((COMPONENT/"manifest.json").read_text())
    assert js[0][1].endswith("?v="+manifest["version"])
    assert {item.url for item in h.http.static_paths} == {
        f"/{CANONICAL_DOMAIN}/air-quality-advisor-card.js",
        f"/{LEGACY_DOMAIN}/air-quality-advisor-card.js",
    }
    assert asyncio.run(module.async_setup_entry(h,entry)) is True
    assert entry.title=="Home Environment Manager"
    assert json.dumps(entry.data,sort_keys=True)==before
    assert set(entry.options)=={"room_hub_subentry_ids"}
    assert set(entry.options["room_hub_subentry_ids"])=={"living"}
    from custom_components.enviroment_manager.const import PLATFORMS
    assert h.config_entries.forwarded==[("legacy-1", PLATFORMS)]
    assert set(h.services.callbacks)=={
        (domain,action)
        for domain in (CANONICAL_DOMAIN,PUBLIC_ACTION_DOMAIN,LEGACY_DOMAIN)
        for action in ("announce","pid_control","climate_control","climate_diagnostics")
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
    assert len(h.services.registered)==12
    assert sorted(h.data[CANONICAL_DOMAIN])==["legacy-1","legacy-2"]
    assert asyncio.run(module.async_unload_entry(h,first))
    assert len(h.services.callbacks)==12
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
    assert CANONICAL_DOMAIN not in h.data
    assert h.services.registered==[]
    h.config_entries.fail_forward=False
    FakeManager.fail_start=True
    with pytest.raises(RuntimeError,match="manager startup"):
        asyncio.run(module.async_setup_entry(h,entry))
    assert FakeManager.instances[-1].stopped
    assert h.services.registered==[]


def test_read_only_climate_diagnostics_registers_both_aliases_and_never_calls_hvac(
    integration,
):
    module,_=integration
    hass=make_hass()
    entry=legacy_entry()
    asyncio.run(module.async_setup_entry(hass,entry))
    call=SimpleNamespace(data={"area":"living"},return_response=True)
    service=hass.services.callbacks[
        ("home_environment_manager","climate_diagnostics")
    ]
    result=asyncio.run(service(call))
    assert result["status"]=="ok"
    assert result["read_only"] is True
    assert result["no_commands_sent"] is True
    assert result["physical_hardware_safety_verified"] is False
    assert result["rooms"]==[{"area_id":"living","devices":[]}]
    assert FakeManager.instances[0].calls==[]
    missing=asyncio.run(service(SimpleNamespace(
        data={"area":"unknown"},return_response=True,
    )))
    assert missing["status"]=="area_not_configured"
    assert missing["rooms"]==[]
    assert asyncio.run(module.async_unload_entry(hass,entry))
    assert not hass.services.callbacks



def test_climate_and_pid_controls_route_only_to_unique_configured_entry(
    integration,
):
    module,_=integration
    hass=make_hass()
    first=legacy_entry(number=1)
    second=legacy_entry(number=2)
    first.data["climate_rooms"]={
        "bedroom":{"enabled":True,"allow_actuation":True},
    }
    second.data["climate_rooms"]={
        "kitchen":{"enabled":True,"allow_actuation":True},
    }
    first.data["pid_rooms"]={
        "bedroom":{"enabled":True},
    }
    second.data["pid_rooms"]={
        "kitchen":{"enabled":True},
    }
    asyncio.run(module.async_setup_entry(hass,first))
    asyncio.run(module.async_setup_entry(hass,second))
    def request(area,action="pause"):
        return SimpleNamespace(
            data={"area":area,"action":action},return_response=True,
        )
    routed=asyncio.run(
        hass.services.callbacks[("home_environment_manager","climate_control")](
            request("kitchen")
        )
    )
    assert routed["accepted"] is True
    assert FakeManager.instances[0].calls==[]
    assert FakeManager.instances[1].calls==[
        ("climate",{"area":"kitchen","action":"pause"}),
    ]
    pid=asyncio.run(
        hass.services.callbacks[("enviroment_manager","pid_control")](
            request("bedroom","resume")
        )
    )
    assert pid["accepted"] is True
    assert FakeManager.instances[0].calls==[
        ("pid",{"area":"bedroom","action":"resume"}),
    ]
    assert len(FakeManager.instances[1].calls)==1
    # A second entry that gains the same room must never be a broadcast.
    first.data["climate_rooms"]["kitchen"]={"enabled":True}
    unsafe=asyncio.run(
        hass.services.callbacks[("enviroment_manager","climate_control")](
            request("kitchen")
        )
    )
    assert unsafe["accepted"] is False
    assert unsafe["reason"]=="ambiguous_room_across_config_entries"
    assert len(FakeManager.instances[1].calls)==1
    # An unknown room is not accidentally routed to the first entry.
    unknown=asyncio.run(
        hass.services.callbacks[("home_environment_manager","climate_control")](
            request("office")
        )
    )
    assert unknown=={
        "accepted":False,"reason":"room_not_configured_or_disabled",
    }
    asyncio.run(module.async_unload_entry(hass,first))
    asyncio.run(module.async_unload_entry(hass,second))



def test_announce_routes_only_actionable_rooms_to_exact_entries(integration):
    module,_=integration
    hass=make_hass()
    first,second=legacy_entry(1),legacy_entry(2)
    asyncio.run(module.async_setup_entry(hass,first))
    asyncio.run(module.async_setup_entry(hass,second))
    a,b=FakeManager.instances
    def rec(area):
        return SimpleNamespace(area_id=area)
    a.plan=SimpleNamespace(recommendations=(rec("bedroom"),),
                           climate_recommendations=())
    b.plan=SimpleNamespace(recommendations=(),
                           climate_recommendations=(rec("kitchen"),))
    def req(areas=None):
        return SimpleNamespace(data=({} if areas is None else {"areas":areas}),
                               return_response=True)
    service=hass.services.callbacks[("enviroment_manager","announce")]
    assert asyncio.run(service(req(["kitchen"])))["submitted"]==1
    assert a.calls==[]
    assert b.calls==[("announce",{
        "language":None,"channels":"both","areas":["kitchen"],
    })]
    a.calls.clear()
    b.calls.clear()
    assert asyncio.run(service(req()))["submitted"]==2
    assert [v[1]["areas"] for v in a.calls]==[["bedroom"]]
    assert [v[1]["areas"] for v in b.calls]==[["kitchen"]]
    a.calls.clear()
    b.calls.clear()
    # One room with two eligible recommenders is an ownership conflict,
    # not permission for duplicate announcements.
    b.plan.climate_recommendations=(rec("kitchen"),rec("bedroom"))
    result=asyncio.run(service(req()))
    assert result["submitted"]==0
    assert result["reason"]=="ambiguous_room_across_config_entries"
    assert a.calls==b.calls==[]
    assert asyncio.run(service(req(["unknown"])))["submitted"]==0
    assert a.calls==b.calls==[]
    asyncio.run(module.async_unload_entry(hass,first))
    asyncio.run(module.async_unload_entry(hass,second))
