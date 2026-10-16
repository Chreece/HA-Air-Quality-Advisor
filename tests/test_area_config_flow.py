"""Exercise the actual area wizard with minimal Home Assistant/selector stubs."""

import asyncio
import importlib
import sys
import types
from types import SimpleNamespace

from test_discovery import FakeHass, MockState, adapter


def _wizard(monkeypatch, adapter):
    probatio = types.ModuleType("probatio")
    class Field(str):
        def __new__(cls, key, default=None):
            field = str.__new__(cls, key)
            field.default = default
            return field
    probatio.Required = Field
    probatio.Optional = Field
    probatio.Schema = lambda fields: fields
    monkeypatch.setitem(sys.modules, "probatio", probatio)

    config_entries = types.ModuleType("homeassistant.config_entries")

    class ConfigFlow:
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__()

    config_entries.ConfigFlow = ConfigFlow
    config_entries.OptionsFlowWithReload = object
    config_entries.ConfigFlowResult = dict
    monkeypatch.setitem(sys.modules, "homeassistant.config_entries", config_entries)

    mp = types.ModuleType("homeassistant.components.media_player")
    mp.MediaPlayerEntityFeature = SimpleNamespace(PLAY_MEDIA=1)
    monkeypatch.setitem(sys.modules, "homeassistant.components", types.ModuleType("homeassistant.components"))
    monkeypatch.setitem(sys.modules, "homeassistant.components.media_player", mp)

    core = sys.modules["homeassistant.core"]
    core.callback = lambda function: function

    selector = types.ModuleType("homeassistant.helpers.selector")
    class SelectSelectorConfig:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
    class SelectSelector:
        def __init__(self, config):
            self.config = config
    selector.SelectSelectorConfig = SelectSelectorConfig
    selector.SelectSelector = SelectSelector
    selector.SelectSelectorMode = SimpleNamespace(DROPDOWN="dropdown")
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.selector", selector)

    name = "custom_components.air_quality_advisor.config_flow"
    monkeypatch.delitem(sys.modules, name, raising=False)
    module = importlib.import_module(name)

    class Wizard(module._FlowMixin):
        _editing = False
        _values = {}
        def __init__(self, hass, editing=False, existing=None):
            self.hass = hass
            self._editing = editing
            self._values = {"areas": existing or []} if editing else {}
        def async_show_form(self, **kwargs):
            return kwargs
        async def async_step_outdoor(self, user_input=None):
            return {"next_step": "outdoor"}

    return Wizard


def test_wizard_only_offers_areas_with_windows(monkeypatch, adapter):
    Wizard = _wizard(monkeypatch, adapter)
    home = FakeHass([
        MockState("binary_sensor.kitchen_window", "off", device_class="window"),
        MockState("binary_sensor.hallway_door", "off", device_class="door"),
    ], {"binary_sensor.kitchen_window": "kitchen", "binary_sensor.hallway_door": "hallway"})
    form = asyncio.run(Wizard(home).async_step_areas())
    options = form["data_schema"]["areas"].config.options
    assert [option["value"] for option in options] == ["kitchen"]
    assert form["errors"] == {}
    assert next(iter(form["data_schema"])).default == ["kitchen"]


def test_first_setup_preselects_contacts_and_excludes_covers(monkeypatch, adapter):
    Wizard = _wizard(monkeypatch, adapter)
    home = FakeHass([
        MockState("binary_sensor.kitchen", "off", device_class="window"),
        MockState("binary_sensor.living", "on", device_class="window"),
        MockState("cover.bedroom", "closed", device_class="window"),
    ], {
        "binary_sensor.kitchen": "kitchen",
        "binary_sensor.living": "living",
        "cover.bedroom": "bedroom",
    })
    form = asyncio.run(Wizard(home).async_step_areas())
    assert next(iter(form["data_schema"])).default == ["kitchen", "living"]
    assert [o["value"] for o in form["data_schema"]["areas"].config.options] == ["kitchen", "living"]


def test_wizard_rejects_stale_or_unrecognized_area(monkeypatch, adapter):
    Wizard = _wizard(monkeypatch, adapter)
    home = FakeHass([
        MockState("binary_sensor.living_window", "off", device_class="window"),
    ], {"binary_sensor.living_window": "living"})
    form = asyncio.run(Wizard(home).async_step_areas({"areas": ["hallway"]}))
    assert form["errors"] == {"base": "invalid_areas"}
    result = asyncio.run(Wizard(home).async_step_areas({"areas": ["living"]}))
    assert result == {"next_step": "outdoor"}


def test_wizard_keeps_preexisting_area_on_options_edit(monkeypatch, adapter):
    Wizard = _wizard(monkeypatch, adapter)
    home = FakeHass([
        MockState("binary_sensor.kitchen_window", "off", device_class="window")
    ], {"binary_sensor.kitchen_window": "kitchen"})
    form = asyncio.run(Wizard(home, editing=True, existing=["bedroom"]).async_step_areas())
    assert {item["value"] for item in form["data_schema"]["areas"].config.options} == {
        "kitchen", "bedroom"
    }
    assert next(iter(form["data_schema"])).default == ["bedroom"]


def test_empty_discovery_has_actionable_error(monkeypatch, adapter):
    Wizard = _wizard(monkeypatch, adapter)
    form = asyncio.run(Wizard(FakeHass([])).async_step_areas())
    assert form["errors"] == {"base": "no_window_areas"}
