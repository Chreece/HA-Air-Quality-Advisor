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
    selector.EntitySelectorConfig = SelectSelectorConfig
    selector.EntitySelector = SelectSelector
    selector.BooleanSelector = lambda: SelectSelector(SelectSelectorConfig(type="boolean"))
    selector.NumberSelectorConfig = SelectSelectorConfig
    selector.NumberSelector = SelectSelector
    selector.NumberSelectorMode = SimpleNamespace(BOX="box")
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
    assert result["step_id"] == "window_sensors"


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


def test_exclusion_page_auto_selects_virtuals_after_rooms_and_reviews_only_when_needed(monkeypatch, adapter):
    Wizard = _wizard(monkeypatch, adapter)
    physical = "binary_sensor.kitchen_window"
    virtual = "binary_sensor.bedroom_window_open_detected"
    home = FakeHass([
        MockState(physical, "off", device_class="window"),
        MockState(virtual, "off", device_class="window"),
    ], {physical: "kitchen", virtual: "bedroom"})
    flow = Wizard(home)
    rooms = asyncio.run(flow.async_step_areas())
    assert next(iter(rooms["data_schema"])).default == ["bedroom", "kitchen"]
    exclusion_form = asyncio.run(flow.async_step_areas({"areas": ["kitchen", "bedroom"]}))
    assert exclusion_form["step_id"] == "window_sensors"
    assert next(iter(exclusion_form["data_schema"])).default == [virtual]
    reviewed = asyncio.run(flow.async_step_window_sensors({"excluded_window_entities": [virtual]}))
    assert reviewed["step_id"] == "areas"
    assert reviewed["errors"] == {"base": "review_areas_after_exclusions"}
    assert [item["value"] for item in reviewed["data_schema"]["areas"].config.options] == ["kitchen"]
    assert next(iter(reviewed["data_schema"])).default == ["kitchen"]
    finished_rooms = asyncio.run(flow.async_step_areas({"areas": ["kitchen"]}))
    assert finished_rooms == {"next_step": "outdoor"}
    assert flow._values["excluded_window_entities"] == [virtual]
    assert flow._values["areas"] == ["kitchen"]


def test_unchecked_virtual_contact_is_honored_even_on_options_reopen(monkeypatch, adapter):
    Wizard = _wizard(monkeypatch, adapter)
    entity = "binary_sensor.living_window_open_detected"
    home = FakeHass([MockState(entity, "on", device_class="window")], {entity: "living"})
    wizard = Wizard(home)
    assert asyncio.run(wizard.async_step_areas())["step_id"] == "areas"
    form = asyncio.run(wizard.async_step_areas({"areas": ["living"]}))
    assert form["step_id"] == "window_sensors"
    assert next(iter(form["data_schema"])).default == [entity]
    completed = asyncio.run(wizard.async_step_window_sensors({"excluded_window_entities": []}))
    assert completed == {"next_step": "outdoor"}
    assert wizard._values["excluded_window_entities"] == []
    editing = Wizard(home, editing=True, existing=["living"], excluded=[])
    saved = asyncio.run(editing.async_step_window_sensors())
    assert next(iter(saved["data_schema"])).default == []


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


def test_excluding_every_window_blocks_setup_without_erasing_rooms(monkeypatch, adapter):
    Wizard = _wizard(monkeypatch, adapter)
    virtual = "binary_sensor.thermostat_window_open_detected"
    home = FakeHass([MockState(virtual, "on", device_class="window")], {virtual: "bathroom"})
    wizard = Wizard(home)
    form = asyncio.run(wizard.async_step_areas({"areas": ["bathroom"]}))
    assert form["step_id"] == "window_sensors"
    blocked = asyncio.run(wizard.async_step_window_sensors({"excluded_window_entities": [virtual]}))
    assert blocked["step_id"] == "window_sensors"
    assert blocked["errors"] == {"base": "no_windows_after_exclusions"}
    assert wizard._values["areas"] == ["bathroom"]
    assert "excluded_window_entities" not in wizard._values


def test_indoor_room_page_lists_only_supported_sensors_with_device_and_entity(monkeypatch, adapter):
    Wizard = _wizard(monkeypatch, adapter)
    co2 = "sensor.kitchen_co2"
    humidity = "sensor.kitchen_humidity"
    pm = "sensor.living_pm25"
    home = FakeHass([
        MockState("binary_sensor.kitchen_window", "off", device_class="window"),
        MockState(co2, "1150", device_class="co2", unit="ppm", name="Carbon dioxide"),
        MockState(humidity, 52, device_class="humidity", unit="%", name="Relative humidity"),
        MockState(pm, 14, device_class="pm25", unit="µg/m³"),
        MockState("sensor.kitchen_voltage", 33, unit="V"),
    ], {
        "binary_sensor.kitchen_window": "kitchen", co2:"kitchen",
        humidity:"kitchen", pm:"living", "sensor.kitchen_voltage":"kitchen",
    })
    home._entity_devices[co2] = "env_monitor"
    home._entity_devices[humidity] = "env_monitor"
    home._device_details["env_monitor"] = {"name":"Airthings Wave Plus"}
    wizard = Wizard(home)
    exclusions = asyncio.run(wizard.async_step_areas({"areas": ["kitchen"]}))
    assert exclusions["step_id"] == "window_sensors"
    result = asyncio.run(wizard.async_step_window_sensors({"excluded_window_entities": []}))
    assert result["step_id"] == "indoor_sensors"
    assert result["description_placeholders"] == {"area_name":"kitchen", "position":"1", "total":"1"}
    choices = result["data_schema"]["excluded_indoor_entities"].config.options
    assert {option["value"] for option in choices} == {co2, humidity}
    text = next(option["label"] for option in choices if option["value"] == co2)
    assert "Airthings Wave Plus" in text and "Carbon dioxide" in text and co2 in text
    assert next(iter(result["data_schema"])).default == []
    ignored = asyncio.run(wizard.async_step_indoor_sensors({"excluded_indoor_entities": [humidity]}))
    assert ignored == {"next_step": "outdoor"}
    assert wizard._values["excluded_indoor_entities"] == {"kitchen": [humidity]}


def test_room_filters_are_independent_and_can_be_cleared_in_options(monkeypatch, adapter):
    Wizard = _wizard(monkeypatch, adapter)
    humidity = "sensor.kitchen_humidity"
    bedroom = "sensor.bedroom_aqi"
    home = FakeHass([
        MockState(humidity, 75, device_class="humidity", unit="%"),
        MockState(bedroom, 125, device_class="aqi", unit="index"),
    ], {humidity:"kitchen", bedroom:"bedroom"})
    wizard = Wizard(home, editing=True, existing=["kitchen", "bedroom"])
    wizard._values["excluded_indoor_entities"] = {"kitchen": [humidity], "bedroom": [bedroom]}
    wizard._indoor_index = 0
    form = asyncio.run(wizard.async_step_indoor_sensors())
    assert next(iter(form["data_schema"])).default == [humidity]
    form = asyncio.run(wizard.async_step_indoor_sensors({"excluded_indoor_entities": []}))
    assert form["description_placeholders"]["area_name"] == "bedroom"
    assert next(iter(form["data_schema"])).default == [bedroom]
    form = asyncio.run(wizard.async_step_indoor_sensors({"excluded_indoor_entities": [bedroom]}))
    assert form == {"next_step": "outdoor"}
    assert wizard._values["excluded_indoor_entities"] == {"kitchen": [], "bedroom": [bedroom]}


def test_missing_saved_sensor_kept_removable_invalid_selection_rejected(monkeypatch, adapter):
    Wizard = _wizard(monkeypatch, adapter)
    home = FakeHass([MockState("sensor.office_co2", 800, device_class="co2", unit="ppm")],
                    {"sensor.office_co2":"office"})
    wizard = Wizard(home, editing=True, existing=["office"])
    wizard._values["excluded_indoor_entities"] = {"office": ["sensor.old_humidity"]}
    wizard._indoor_index = 0
    form = asyncio.run(wizard.async_step_indoor_sensors())
    assert next(iter(form["data_schema"])).default == ["sensor.old_humidity"]
    assert {o["value"] for o in form["data_schema"]["excluded_indoor_entities"].config.options} == {
        "sensor.old_humidity", "sensor.office_co2"
    }
    bad = asyncio.run(wizard.async_step_indoor_sensors({"excluded_indoor_entities": ["sensor.rogue"]}))
    assert bad["errors"] == {"base": "invalid_indoor_exclusions"}
    good = asyncio.run(wizard.async_step_indoor_sensors({"excluded_indoor_entities": []}))
    assert good == {"next_step": "outdoor"}
    assert wizard._values["excluded_indoor_entities"]["office"] == []


def _make_options(monkeypatch, adapter, *, two_rooms=False):
    """Build the real options handler with the test Home Assistant doubles."""
    _wizard(monkeypatch, adapter)
    import custom_components.air_quality_advisor.config_flow as flows
    states = [
        MockState("binary_sensor.living_window", "off", device_class="window"),
        MockState("sensor.living_co2", 900, device_class="co2", unit="ppm"),
        MockState("sensor.outdoor_pm25", 8, device_class="pm25", unit="µg/m³"),
        MockState("weather.home", "sunny"),
    ]
    areas = {
        "binary_sensor.living_window":"living",
        "sensor.living_co2":"living",
        "sensor.outdoor_pm25":"outside",
    }
    selected_areas = ["living"]
    exclusions = {"living":["sensor.living_co2"]}
    if two_rooms:
        states.extend([
            MockState("binary_sensor.kitchen_window", "off", device_class="window"),
            MockState("sensor.kitchen_co2", 850, device_class="co2", unit="ppm"),
        ])
        areas.update({
            "binary_sensor.kitchen_window":"kitchen",
            "sensor.kitchen_co2":"kitchen",
        })
        selected_areas.append("kitchen")
        exclusions["kitchen"] = ["sensor.kitchen_co2"]

    home = FakeHass(states, areas)
    home.services = SimpleNamespace(has_service=lambda *args: False)
    options = flows.AirQualityOptionsFlow()
    options.hass = home
    options.config_entry = SimpleNamespace(data={
        "areas":selected_areas,
        "excluded_window_entities":[],
        "excluded_indoor_entities":exclusions,
        "outdoor_sensors":["sensor.outdoor_pm25"],
        "weather_entities":["weather.home"],
        "thresholds":{"indoor_co2":1200},
        "automatic_tts":False,
        "automatic_notifications":False,
        "language":"el",
    }, options={})
    options.async_show_form = lambda **kwargs: kwargs
    options.async_show_menu = lambda **kwargs: kwargs
    options.async_create_entry = lambda **kwargs: {"completed":kwargs}
    return options


def test_reconfigure_opens_menu_with_every_section(monkeypatch, adapter):
    options = _make_options(monkeypatch, adapter)
    menu = asyncio.run(options.async_step_init())
    assert menu["step_id"] == "init"
    assert menu["menu_options"] == [
        "areas", "window_sensors", "indoor_sensors", "outdoor",
        "weather", "delivery", "thresholds",
    ]
    assert options._values["thresholds"] == {"indoor_co2":1200}


def test_reconfigure_window_exclusions_finish_without_full_wizard(monkeypatch, adapter):
    options = _make_options(monkeypatch, adapter)
    asyncio.run(options.async_step_init())
    form = asyncio.run(options.async_step_window_sensors())
    assert form["step_id"] == "window_sensors"
    result = asyncio.run(options.async_step_window_sensors({
        "excluded_window_entities":["binary_sensor.living_window"],
    }))
    assert result["completed"]["data"]["excluded_window_entities"] == ["binary_sensor.living_window"]
    assert result["completed"]["data"]["areas"] == ["living"]
    assert result["completed"]["data"]["excluded_indoor_entities"] == {"living":["sensor.living_co2"]}


def test_reconfigure_areas_outdoor_and_weather_save_only_selected_section(monkeypatch, adapter):
    options = _make_options(monkeypatch, adapter)
    asyncio.run(options.async_step_init())
    result = asyncio.run(options.async_step_areas({"areas":["living"]}))
    assert result["completed"]["data"]["outdoor_sensors"] == ["sensor.outdoor_pm25"]
    assert result["completed"]["data"]["thresholds"] == {"indoor_co2":1200}

    options = _make_options(monkeypatch, adapter)
    asyncio.run(options.async_step_init())
    result = asyncio.run(options.async_step_outdoor({"outdoor_sensors":["sensor.outdoor_pm25"]}))
    assert result["completed"]["data"]["weather_entities"] == ["weather.home"]

    options = _make_options(monkeypatch, adapter)
    asyncio.run(options.async_step_init())
    result = asyncio.run(options.async_step_weather({
        "weather_entities":["weather.home"], "weather_warnings":[],
    }))
    assert result["completed"]["data"]["excluded_indoor_entities"] == {"living":["sensor.living_co2"]}


def test_reconfigure_indoor_sensors_remain_room_by_room(monkeypatch, adapter):
    options = _make_options(monkeypatch, adapter, two_rooms=True)
    asyncio.run(options.async_step_init())
    first = asyncio.run(options.async_step_indoor_sensors())
    assert first["step_id"] == "indoor_sensors"
    assert next(iter(first["data_schema"])).default == ["sensor.living_co2"]
    second = asyncio.run(options.async_step_indoor_sensors({"excluded_indoor_entities":[]}))
    assert second["step_id"] == "indoor_sensors"
    assert next(iter(second["data_schema"])).default == ["sensor.kitchen_co2"]
    saved = asyncio.run(options.async_step_indoor_sensors({
        "excluded_indoor_entities":["sensor.kitchen_co2"],
    }))
    assert saved["completed"]["data"]["excluded_indoor_entities"] == {
        "living":[], "kitchen":["sensor.kitchen_co2"],
    }
    assert saved["completed"]["data"]["weather_entities"] == ["weather.home"]


def test_announcement_editor_has_no_advanced_threshold_toggle(monkeypatch, adapter):
    options = _make_options(monkeypatch, adapter)
    asyncio.run(options.async_step_init())
    form = asyncio.run(options.async_step_delivery())
    assert "edit_thresholds" not in form["data_schema"]
    assert next(k.default for k in form["data_schema"] if k == "language") == "el"
    saved = asyncio.run(options.async_step_delivery({"language":"de"}))
    assert saved["completed"]["data"]["language"] == "de"
    assert saved["completed"]["data"]["thresholds"] == {"indoor_co2":1200}
    assert "edit_thresholds" not in saved["completed"]["data"]


def test_advanced_thresholds_are_editable_directly_from_menu(monkeypatch, adapter):
    from custom_components.air_quality_advisor.const import DEFAULT_THRESHOLDS
    options = _make_options(monkeypatch, adapter)
    asyncio.run(options.async_step_init())
    form = asyncio.run(options.async_step_thresholds())
    assert form["step_id"] == "thresholds"
    assert next(k.default for k in form["data_schema"] if k == "indoor_co2") == 1200
    saved = asyncio.run(options.async_step_thresholds({**DEFAULT_THRESHOLDS,"indoor_co2":1100}))
    assert saved["completed"]["data"]["thresholds"]["indoor_co2"] == 1100
    assert saved["completed"]["data"]["excluded_indoor_entities"] == {"living":["sensor.living_co2"]}



def test_reconfigure_when_no_supported_air_sensors_skips_empty_room_page(monkeypatch, adapter):
    Wizard = _wizard(monkeypatch, adapter)
    home = FakeHass([MockState("binary_sensor.kitchen_window", "off", device_class="window")],
                    {"binary_sensor.kitchen_window":"kitchen"})
    wizard = Wizard(home, editing=True, existing=["kitchen"])
    wizard._values["areas"] = ["kitchen"]
    result = asyncio.run(wizard.async_step_indoor_sensors())
    assert result == {"next_step":"outdoor"}

def test_initial_config_entry_starts_with_rooms(monkeypatch, adapter):
    _wizard(monkeypatch, adapter)
    import custom_components.air_quality_advisor.config_flow as flows
    home = FakeHass([
        MockState("binary_sensor.living_window", "off", device_class="window"),
    ], {"binary_sensor.living_window": "living"})
    initial = flows.AirQualityConfigFlow()
    initial.hass = home

    async def set_unique_id(_value):
        return None

    initial.async_set_unique_id = set_unique_id
    initial._abort_if_unique_id_configured = lambda: None
    initial.async_show_form = lambda **kwargs: kwargs
    form = asyncio.run(initial.async_step_user())
    assert form["step_id"] == "areas"
    assert next(iter(form["data_schema"])).default == ["living"]


def test_initial_no_exclusions_still_moves_to_indoor_then_outdoor(monkeypatch, adapter):
    Wizard = _wizard(monkeypatch, adapter)
    home = FakeHass([
        MockState("binary_sensor.kitchen_window", "off", device_class="window"),
        MockState("sensor.kitchen_co2", 800, device_class="co2", unit="ppm"),
    ], {
        "binary_sensor.kitchen_window": "kitchen",
        "sensor.kitchen_co2": "kitchen",
    })
    wizard = Wizard(home)
    step = asyncio.run(wizard.async_step_areas({"areas": ["kitchen"]}))
    assert step["step_id"] == "window_sensors"
    step = asyncio.run(wizard.async_step_window_sensors({"excluded_window_entities": []}))
    assert step["step_id"] == "indoor_sensors"
    step = asyncio.run(wizard.async_step_indoor_sensors({"excluded_indoor_entities": []}))
    assert step == {"next_step": "outdoor"}


def test_reconfigure_keeps_rooms_first_without_replaying_setup(monkeypatch, adapter):
    options = _make_options(monkeypatch, adapter)
    menu = asyncio.run(options.async_step_init())
    assert menu["menu_options"][0] == "areas"
    result = asyncio.run(options.async_step_areas({"areas": ["living"]}))
    assert "completed" in result
    assert result["completed"]["data"]["areas"] == ["living"]

def test_disappearing_contacts_cannot_silently_finish_initial_setup(monkeypatch, adapter):
    Wizard = _wizard(monkeypatch, adapter)
    contact = "binary_sensor.living_window"
    home = FakeHass([
        MockState(contact, "off", device_class="window"),
    ], {contact: "living"})
    wizard = Wizard(home)
    assert asyncio.run(wizard.async_step_areas({"areas":["living"]}))["step_id"] == "window_sensors"
    home._values.pop(contact)
    form = asyncio.run(wizard.async_step_window_sensors())
    assert form["step_id"] == "window_sensors"
    assert form["errors"] == {"base": "no_windows_after_exclusions"}

def test_only_configured_announcement_hub_is_offered_on_settings_page(monkeypatch, adapter):
    options = _make_options(monkeypatch, adapter)
    # Merely registering notify.announcement_hub is not proof the integration
    # was installed or has a config entry.
    options.hass.services = SimpleNamespace(
        has_service=lambda d, s: (d, s) in (
            ("notify", "announcement_hub"),
            ("persistent_notification", "create"),
        )
    )
    asyncio.run(options.async_step_init())
    without_entry = asyncio.run(options.async_step_delivery())
    assert "use_announcement_hub" not in without_entry["data_schema"]
    assert "ai_rewrite_announcements" in without_entry["data_schema"]
    assert "ai_conversation_agent" in without_entry["data_schema"]

    options.hass.config_entries = SimpleNamespace(
        async_entries=lambda domain: [SimpleNamespace(state="not_loaded")]
        if domain == "announcement_hub" else []
    )
    with_entry = asyncio.run(options.async_step_delivery())
    assert "use_announcement_hub" in with_entry["data_schema"]
    assert next(iter(with_entry["data_schema"][
        "ai_conversation_agent"].config.options))["value"] == "default"


def test_installed_hub_can_use_ai_even_without_local_conversation_service(monkeypatch, adapter):
    options = _make_options(monkeypatch, adapter)
    options.hass.services = SimpleNamespace(
        has_service=lambda domain, service: (
            (domain, service) == ("notify", "announcement_hub")
        )
    )
    options.hass.config_entries = SimpleNamespace(
        async_entries=lambda domain: [SimpleNamespace(state="loaded")]
        if domain == "announcement_hub" else []
    )
    asyncio.run(options.async_step_init())
    done = asyncio.run(options.async_step_delivery({
        "use_announcement_hub": True,
        "ai_rewrite_announcements": True,
        "ai_conversation_agent": "default",
    }))
    assert "completed" in done
    assert done["completed"]["data"]["use_announcement_hub"] is True
    assert done["completed"]["data"]["ai_rewrite_announcements"] is True


def test_direct_notifications_can_use_built_in_persistent_notification(monkeypatch, adapter):
    options = _make_options(monkeypatch, adapter)
    options.hass.services = SimpleNamespace(
        has_service=lambda domain, service: (domain, service) == (
            "persistent_notification", "create"
        )
    )
    asyncio.run(options.async_step_init())
    done = asyncio.run(options.async_step_delivery({
        "automatic_notifications": True, "notify_entities": []
    }))
    assert "completed" in done
    assert done["completed"]["data"]["automatic_notifications"] is True

def test_repeat_interval_defaults_to_ten_minutes_and_uses_number_selector(monkeypatch, adapter):
    options = _make_options(monkeypatch, adapter)
    asyncio.run(options.async_step_init())
    form = asyncio.run(options.async_step_delivery())
    field = next(k for k in form["data_schema"] if k == "announcement_repeat_minutes")
    assert field.default == 10
    selector = form["data_schema"][field]
    assert selector.config.min == 0
    assert selector.config.max == 1440
    assert selector.config.step == 1
    assert selector.config.unit_of_measurement == "min"


def test_repeat_interval_can_be_disabled_or_set_in_minutes(monkeypatch, adapter):
    for minutes in (0, 1, 10, 1440):
        options = _make_options(monkeypatch, adapter)
        asyncio.run(options.async_step_init())
        saved = asyncio.run(options.async_step_delivery({
            "announcement_repeat_minutes": minutes,
        }))
        assert saved["completed"]["data"]["announcement_repeat_minutes"] == minutes
        assert saved["completed"]["data"]["areas"] == ["living"]


def test_invalid_repeat_intervals_are_rejected_without_changing_stored_setting(monkeypatch, adapter):
    for invalid in (-1, 1441, 5.5, "bad", None, float("inf"), float("nan"), True):
        options = _make_options(monkeypatch, adapter)
        asyncio.run(options.async_step_init())
        error = asyncio.run(options.async_step_delivery({
            "announcement_repeat_minutes": invalid,
        }))
        assert error["errors"] == {"base": "invalid_repeat_minutes"}
        assert "announcement_repeat_minutes" not in options._values


def test_existing_repeat_value_is_preserved_on_reconfigure(monkeypatch, adapter):
    options = _make_options(monkeypatch, adapter)
    options.config_entry.data["announcement_repeat_minutes"] = 0
    asyncio.run(options.async_step_init())
    form = asyncio.run(options.async_step_delivery())
    field = next(k for k in form["data_schema"] if k == "announcement_repeat_minutes")
    assert field.default == 0
    saved = asyncio.run(options.async_step_delivery({"language": "el"}))
    assert saved["completed"]["data"]["announcement_repeat_minutes"] == 0
