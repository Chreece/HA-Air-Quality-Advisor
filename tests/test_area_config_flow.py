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
            item = str.__new__(cls, key)
            item.default = default
            return item
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
        def __init__(self, hass, editing=False, existing=None, excluded=None):
            self.hass = hass
            self._editing = editing
            self._values = {"areas": existing or []} if editing else {}
            if excluded is not None:
                self._values["excluded_window_entities"] = excluded
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


def test_initial_flow_preselects_all_supported_window_areas_not_covers(monkeypatch, adapter):
    Wizard = _wizard(monkeypatch, adapter)
    home = FakeHass([
        MockState("binary_sensor.kitchen_window", "off", device_class="window"),
        MockState("binary_sensor.living_window", "on", device_class="window"),
        MockState("cover.bedroom_window", "closed", device_class="window"),
    ], {
        "binary_sensor.kitchen_window": "kitchen",
        "binary_sensor.living_window": "living",
        "cover.bedroom_window": "bedroom",
    })
    form = asyncio.run(Wizard(home).async_step_areas())
    assert next(iter(form["data_schema"])).default == ["kitchen", "living"]
    assert [choice["value"] for choice in form["data_schema"]["areas"].config.options] == ["kitchen", "living"]


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


def test_exclusion_page_auto_selects_virtuals_before_suggesting_areas(monkeypatch, adapter):
    Wizard = _wizard(monkeypatch, adapter)
    physical = "binary_sensor.kitchen_window"
    virtual = "binary_sensor.bedroom_window_open_detected"
    home = FakeHass([
        MockState(physical, "off", device_class="window"),
        MockState(virtual, "off", device_class="window"),
    ], {physical: "kitchen", virtual: "bedroom"})
    flow = Wizard(home)
    form = asyncio.run(flow.async_step_window_sensors())
    selector = form["data_schema"]["excluded_window_entities"]
    assert {item["value"] for item in selector.config.options} == {physical, virtual}
    assert next(iter(form["data_schema"])).default == [virtual]
    next_form = asyncio.run(flow.async_step_window_sensors({"excluded_window_entities": [virtual]}))
    assert flow._values["excluded_window_entities"] == [virtual]
    assert [item["value"] for item in next_form["data_schema"]["areas"].config.options] == ["kitchen"]
    assert next(iter(next_form["data_schema"])).default == ["kitchen"]


def test_unchecked_virtual_contact_is_honored_even_on_options_reopen(monkeypatch, adapter):
    Wizard = _wizard(monkeypatch, adapter)
    entity = "binary_sensor.living_window_open_detected"
    home = FakeHass([MockState(entity, "on", device_class="window")], {entity: "living"})
    wizard = Wizard(home)
    first = asyncio.run(wizard.async_step_window_sensors())
    assert next(iter(first["data_schema"])).default == [entity]
    rooms_form = asyncio.run(wizard.async_step_window_sensors({"excluded_window_entities": []}))
    assert wizard._values["excluded_window_entities"] == []
    assert [item["value"] for item in rooms_form["data_schema"]["areas"].config.options] == ["living"]
    editing = Wizard(home, editing=True, existing=["living"], excluded=[])
    saved = asyncio.run(editing.async_step_window_sensors())
    assert next(iter(saved["data_schema"])).default == []  # no heuristic re-insertion
    assert [item["value"] for item in saved["data_schema"]["excluded_window_entities"].config.options] == [entity]


def test_existing_exclusions_remain_selected_on_reconfigure(monkeypatch, adapter):
    Wizard = _wizard(monkeypatch, adapter)
    old = "binary_sensor.no_longer_available"
    real = "binary_sensor.kitchen_window"
    home = FakeHass([MockState(real, "off", device_class="window")], {real: "kitchen"})
    editing = Wizard(home, editing=True, existing=["kitchen"], excluded=[old])
    form = asyncio.run(editing.async_step_window_sensors())
    assert next(iter(form["data_schema"])).default == [old]
    assert {opt["value"] for opt in form["data_schema"]["excluded_window_entities"].config.options} == {old, real}


def test_excluded_sensor_validation_prevents_arbitrary_targets(monkeypatch, adapter):
    Wizard = _wizard(monkeypatch, adapter)
    home = FakeHass([MockState("binary_sensor.window", "off", device_class="window")])
    invalid = asyncio.run(Wizard(home).async_step_window_sensors({
        "excluded_window_entities": ["switch.ventilation"]
    }))
    assert invalid["errors"] == {"base": "invalid_window_exclusions"}


def test_every_discovered_window_excluded_stops_false_area_suggestions(monkeypatch, adapter):
    Wizard = _wizard(monkeypatch, adapter)
    virtual = "binary_sensor.thermostat_window_open_detected"
    home = FakeHass([MockState(virtual, "on", device_class="window")], {virtual: "bathroom"})
    next_form = asyncio.run(Wizard(home).async_step_window_sensors({"excluded_window_entities": [virtual]}))
    assert next_form["errors"] == {"base": "no_window_areas"}
    assert next_form["data_schema"]["areas"].config.options == []
