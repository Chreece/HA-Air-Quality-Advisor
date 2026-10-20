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
    selector.TextSelector = lambda: SelectSelector(SelectSelectorConfig(type="text"))
    selector.TimeSelector = lambda: SelectSelector(SelectSelectorConfig(type="time"))
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
    assert all(result["description_placeholders"][key] == expected for key, expected in {
        "area_name":"kitchen", "position":"1", "total":"1",
    }.items())
    assert result["description_placeholders"]["mold_room_notice"] == ""
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
        "outside_data", "general_settings", "area_settings",
        "delivery", "thresholds",
    ]
    assert asyncio.run(options.async_step_outside_data())["menu_options"] == [
        "weather", "outdoor", "outside_aqi", "pollen",
    ]
    assert asyncio.run(options.async_step_area_settings())["menu_options"] == [
        "areas", "indoor_sensors", "window_sensors", "environment_room",
        "climate", "pid", "area_devices",
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
    assert menu["menu_options"][0] == "outside_data"
    assert "areas" in asyncio.run(options.async_step_area_settings())["menu_options"]
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


def test_first_page_offers_mold_instead_of_raw_humidity(monkeypatch, adapter):
    Wizard = _wizard(monkeypatch, adapter)
    home = FakeHass([
        MockState("binary_sensor.living_window", "off", device_class="window")
    ], {"binary_sensor.living_window": "living"})
    wizard = Wizard(home)
    page = asyncio.run(wizard.async_step_areas())
    assert next(k.default for k in page["data_schema"] if k == "use_mold_indicator") is False
    next_page = asyncio.run(wizard.async_step_areas({
        "areas": ["living"], "use_mold_indicator": True,
    }))
    assert next_page["step_id"] == "window_sensors"
    assert wizard._values["use_mold_indicator"] is True


def _calibratable_options(monkeypatch, adapter):
    options = _make_options(monkeypatch, adapter)
    home = options.hass
    home._values["sensor.living_temperature"] = MockState(
        "sensor.living_temperature", 21, device_class="temperature", unit="°C",
    )
    home._values["sensor.living_humidity"] = MockState(
        "sensor.living_humidity", 65, device_class="humidity", unit="%",
    )
    home._entity_areas["sensor.living_temperature"] = "living"
    home._entity_areas["sensor.living_humidity"] = "living"
    home._values["weather.home"].attributes["temperature"] = 6
    home._values["weather.home"].attributes["temperature_unit"] = "°C"
    asyncio.run(options.async_step_init())
    options._values["use_mold_indicator"] = True
    return options


def test_calibration_saves_live_temperatures_and_is_stable_on_room_edits(monkeypatch, adapter):
    options = _calibratable_options(monkeypatch, adapter)
    first = asyncio.run(options.async_step_indoor_sensors())
    assert first["step_id"] == "indoor_sensors"
    assert "mold_critical_temperature_c" in first["data_schema"]
    assert "mold_indoor_temperature" in first["data_schema"]
    saved = asyncio.run(options.async_step_indoor_sensors({
        "excluded_indoor_entities": [],
        "mold_indoor_temperature": "sensor.living_temperature",
        "mold_critical_temperature_c": 13.5,
    }))
    calib = saved["completed"]["data"]["mold_rooms"]["living"]
    assert calib["calibration_factor"] == 2.0
    assert calib["outdoor_weather_entity"] == "weather.home"
    # Changing weather later must NOT reinterpret the old measurement.
    options.hass._values["weather.home"].attributes["temperature"] = 10
    options.config_entry.options = saved["completed"]["data"]
    asyncio.run(options.async_step_init())
    options._values["use_mold_indicator"] = True
    edited = asyncio.run(options.async_step_indoor_sensors({
        "excluded_indoor_entities": ["sensor.living_co2"],
        "mold_indoor_temperature": "sensor.living_temperature",
        "mold_critical_temperature_c": 13.5,
    }))
    assert edited["completed"]["data"]["mold_rooms"]["living"] == calib


def test_calibration_rejects_unavailable_outdoor_and_unstable_readings(monkeypatch, adapter):
    options = _calibratable_options(monkeypatch, adapter)
    options.hass._values["weather.home"].attributes.pop("temperature")
    invalid = asyncio.run(options.async_step_indoor_sensors({
        "excluded_indoor_entities": [],
        "mold_indoor_temperature": "sensor.living_temperature",
        "mold_critical_temperature_c": 13.5,
    }))
    assert invalid["errors"] == {"base": "missing_mold_outdoor_temperature"}
    assert "mold_rooms" not in options._values
    options.hass._values["weather.home"].attributes["temperature"] = 20
    unstable = asyncio.run(options.async_step_indoor_sensors({
        "excluded_indoor_entities": [],
        "mold_indoor_temperature": "sensor.living_temperature",
        "mold_critical_temperature_c": 13.5,
    }))
    assert unstable["errors"] == {"base": "invalid_mold_calibration"}


def test_initial_wizard_mold_weather_precedes_room_calibration(monkeypatch, adapter):
    Wizard = _wizard(monkeypatch, adapter)
    home = FakeHass([
        MockState("binary_sensor.living_window", "off", device_class="window"),
    ], {"binary_sensor.living_window": "living"})
    wizard = Wizard(home)
    asyncio.run(wizard.async_step_areas({
        "areas": ["living"], "use_mold_indicator": True,
    }))
    result = asyncio.run(wizard.async_step_window_sensors({"excluded_window_entities": []}))
    assert result == {"next_step": "outdoor"}


def test_weather_options_second_and_source_status_before_room_measurements(
    monkeypatch, adapter,
):
    options = _calibratable_options(monkeypatch, adapter)
    # Reopening Configure must read the saved opt-in, not just the transient
    # values of the previous edit.
    options.config_entry.options["use_mold_indicator"] = True
    menu = asyncio.run(options.async_step_init())
    assert menu["menu_options"][:3] == [
        "outside_data", "general_settings", "area_settings"
    ]
    assert "weather" in asyncio.run(options.async_step_outside_data())["menu_options"]
    assert "indoor_sensors" in asyncio.run(options.async_step_area_settings())["menu_options"]
    weather = asyncio.run(options.async_step_weather())
    assert weather["step_id"] == "weather"
    assert "weather.home" in weather["description_placeholders"]["mold_weather_notice"]
    assert "6.0 °C" in weather["description_placeholders"]["mold_weather_notice"]
    room = asyncio.run(options.async_step_indoor_sensors())
    notice = room["description_placeholders"]["mold_room_notice"]
    assert "⚠️" in notice and "🧊" in notice

    options.hass._values["weather.home"].attributes.pop("temperature")
    weather_unavailable = asyncio.run(options.async_step_weather())
    notice = weather_unavailable["description_placeholders"]["mold_weather_notice"]
    assert "⚠️" in notice and "weather.home" in notice
    room_unavailable = asyncio.run(options.async_step_indoor_sensors())
    assert "🌤️" in room_unavailable["description_placeholders"]["mold_room_notice"]


def test_weather_status_preview_hidden_when_mold_option_is_off(monkeypatch, adapter):
    options = _make_options(monkeypatch, adapter)
    asyncio.run(options.async_step_init())
    result = asyncio.run(options.async_step_weather())
    assert result["description_placeholders"]["mold_weather_notice"] == ""


def test_out_of_range_weather_temperature_shows_warning_in_options(monkeypatch, adapter):
    options = _calibratable_options(monkeypatch, adapter)
    options.hass._values["weather.home"].attributes["temperature"] = 1000
    form = asyncio.run(options.async_step_weather())
    note = form["description_placeholders"]["mold_weather_notice"]
    assert "⚠️" in note
    assert "weather.home" in note

def test_international_environment_options_keep_all_other_configuration(monkeypatch, adapter):
    options = _make_options(monkeypatch, adapter)
    asyncio.run(options.async_step_init())
    form = asyncio.run(options.async_step_environment())
    assert form["step_id"] == "environment"
    assert "pollen_entity" in form["data_schema"]
    done = asyncio.run(options.async_step_environment({
        "pollen_entity": None, "pollen_high_from": 3,
        "pollen_max_scale": 5, "pollen_avoid_ventilation": False,
    }))
    assert done["completed"]["data"]["environment_global"]["pollen_max_scale"] == 5
    assert done["completed"]["data"]["thresholds"]["indoor_co2"] == 1200


def test_room_environment_uses_explicit_sensor_verification(monkeypatch, adapter):
    options = _make_options(monkeypatch, adapter)
    asyncio.run(options.async_step_init())
    chosen = asyncio.run(options.async_step_environment_room({"environment_area":"living"}))
    assert chosen["step_id"] == "environment_room_air"
    next_page = asyncio.run(options.async_step_environment_room_air({
        "co2_ndir_verified": True,"co2_target_ppm": 1000,
        "sleep_room": True,
    }))
    assert next_page["step_id"] == "environment_room_exposure"
    next_page = asyncio.run(options.async_step_environment_room_exposure({
        "formaldehyde_sensor_verified": False,"radon_sensor_verified": False,
    }))
    assert next_page["step_id"] == "environment_room_comfort"
    bad = asyncio.run(options.async_step_environment_room_comfort({"enable_pmv":True}))
    assert bad["errors"]["base"] == "pmv_requires_explicit_inputs"
    done = asyncio.run(options.async_step_environment_room_comfort({"enable_pmv":False}))
    saved = done["completed"]["data"]["environment_rooms"]["living"]
    assert saved["co2_ndir_verified"] is True
    assert saved["formaldehyde_sensor_verified"] is False
    assert saved["sleep_room"] is True

def test_pid_controller_is_off_by_default_and_saved_without_climate_devices(monkeypatch,adapter):
    options=_make_options(monkeypatch,adapter)
    asyncio.run(options.async_step_init())
    assert asyncio.run(options.async_step_pid({"pid_area":"living"}))["step_id"]=="pid_room"
    disabled=asyncio.run(options.async_step_pid_room({"pid_enabled":False}))
    assert disabled["completed"]["data"]["pid_rooms"]["living"]["enabled"] is False
    assert disabled["completed"]["data"]["thresholds"]["indoor_co2"] == 1200


def test_pid_controller_rejects_enabled_room_without_climate_or_temperature(monkeypatch,adapter):
    options=_make_options(monkeypatch,adapter)
    asyncio.run(options.async_step_init())
    asyncio.run(options.async_step_pid({"pid_area":"living"}))
    invalid=asyncio.run(options.async_step_pid_room({
        "pid_enabled":True,"pid_climate_entities":[],
        "pid_temperature_entity":None,"pid_mode":"heat","pid_target_c":21,
    }))
    assert invalid["errors"]["base"]=="pid_climate_required"

def test_climate_room_profiles_are_optional_and_keep_existing_settings(monkeypatch, adapter):
    options = _make_options(monkeypatch, adapter)
    asyncio.run(options.async_step_init())
    choose = asyncio.run(options.async_step_climate({"climate_area":"living"}))
    assert choose["step_id"] == "climate_room"
    setup = asyncio.run(options.async_step_climate_room({"climate_enabled":False}))
    assert setup["step_id"] == "climate_presence"
    assert "climate_sleep_start" in setup["data_schema"]
    assert asyncio.run(options.async_step_climate_presence({}))["step_id"]=="climate_profiles"
    saved = asyncio.run(options.async_step_climate_profiles({}))
    data = saved["completed"]["data"]
    assert data["climate_rooms"]["living"]["enabled"] is False
    assert data["climate_rooms"]["living"]["profiles"]["home"] == {"heat_c":20.0,"cool_c":26.0}
    assert data["thresholds"]["indoor_co2"] == 1200


def test_climate_room_rejects_new_actuation_without_real_sensor(monkeypatch,adapter):
    options=_make_options(monkeypatch,adapter)
    asyncio.run(options.async_step_init())
    asyncio.run(options.async_step_climate({"climate_area":"living"}))
    result=asyncio.run(options.async_step_climate_room({
        "climate_enabled":True,"climate_allow_actuation":True,
        "climate_entity":None,"climate_temperature_entity":None,
        "climate_controller":"device","climate_mode":"auto",
    }))
    assert result["errors"]["base"] == "climate_temperature_required"

def test_climate_schedule_and_comfort_settings_preserve_other_config(monkeypatch,adapter):
    options=_make_options(monkeypatch,adapter)
    asyncio.run(options.async_step_init())
    asyncio.run(options.async_step_climate({"climate_area":"living"}))
    asyncio.run(options.async_step_climate_room({"climate_enabled":False}))
    bad=asyncio.run(options.async_step_climate_presence({
        "climate_sleep_schedule_enabled":True,
        "climate_sleep_start":"22:00","climate_sleep_end":"22:00",
    }))
    assert bad["errors"]["base"]=="climate_invalid_sleep_schedule"
    nxt=asyncio.run(options.async_step_climate_presence({
        "climate_sleep_schedule_enabled":True,
        "climate_sleep_start":"22:00","climate_sleep_end":"07:00",
        "climate_target_source":"pmv",
        "climate_comfort_adjustment_max_c":1.5,
    }))
    assert nxt["step_id"]=="climate_profiles"
    saved=asyncio.run(options.async_step_climate_profiles({}))
    room=saved["completed"]["data"]["climate_rooms"]["living"]
    assert room["sleep_schedule_enabled"] is True
    assert room["target_source"]=="pmv"
    assert room["sleep_end"]=="07:00"
    assert saved["completed"]["data"]["thresholds"]["indoor_co2"]==1200


def test_direct_actuator_settings_are_separate_and_off_by_default(monkeypatch,adapter):
    options=_make_options(monkeypatch,adapter)
    asyncio.run(options.async_step_init())
    asyncio.run(options.async_step_climate({"climate_area":"living"}))
    nxt=asyncio.run(options.async_step_climate_room({
        "climate_enabled":False,"climate_controller":"pwm",
        "climate_allow_actuation":False,
    }))
    assert nxt["step_id"]=="climate_presence"
    assert asyncio.run(options.async_step_climate_presence({}))["step_id"]=="climate_actuators"
    nxt=asyncio.run(options.async_step_climate_actuators({
        "direct_hardware_confirmed":False,
    }))
    assert nxt["step_id"]=="climate_profiles"


def test_climate_extra_equipment_is_room_scoped_and_removable(monkeypatch,adapter):
    options=_make_options(monkeypatch,adapter)
    h=options.hass
    additional=[
        MockState("sensor.living_temperature",20,device_class="temperature",unit="°C"),
        MockState("sensor.living_humidity",58,device_class="humidity",unit="%"),
        MockState("climate.living", "heat"),
        MockState("climate.ac", "cool"),
        MockState("humidifier.dryer","off",device_class="dehumidifier"),
        MockState("fan.extractor","off"),
        MockState("humidifier.kitchen","off",device_class="humidifier"),
    ]
    for st in additional:
        h._values[st.entity_id]=st
        h._entity_areas[st.entity_id]=(
            "kitchen" if st.entity_id=="humidifier.kitchen" else "living")
    for entity in ("climate.living","climate.ac"):
        h._values[entity].attributes.update({
            "hvac_modes":["off","heat","cool","dry"],
            "supported_features":1,
        })
    asyncio.run(options.async_step_init())
    assert asyncio.run(options.async_step_climate({"climate_area":"living"}))["step_id"]=="climate_room"
    selection=asyncio.run(options.async_step_climate_room({
        "climate_enabled":True,
        "climate_entity":"climate.living",
        "climate_temperature_entity":"sensor.living_temperature",
        "climate_controller":"device","climate_mode":"auto",
    }))
    assert selection["step_id"]=="climate_presence"
    devices=asyncio.run(options.async_step_climate_presence({}))
    assert devices["step_id"]=="climate_equipment"
    assert "climate_dehumidifier_entity" in devices["data_schema"]
    invalid=asyncio.run(options.async_step_climate_equipment({
        "climate_humidifier_entity":"humidifier.kitchen",
    }))
    assert invalid["errors"]["base"]=="climate_target_required"
    devices=asyncio.run(options.async_step_climate_equipment({
        "climate_cool_climate_entity":"climate.ac",
        "climate_dehumidifier_entity":"humidifier.dryer",
        "climate_extraction_fan_entity":"fan.extractor",
        "climate_humidity_entity":"sensor.living_humidity",
        "climate_humidity_low_rh":40,
        "climate_humidity_high_rh":60,
        "climate_humidity_hysteresis_rh":3,
    }))
    assert devices["step_id"]=="climate_air_strategy"
    assert asyncio.run(options.async_step_climate_air_strategy({}))["step_id"]=="climate_profiles"
    saved=asyncio.run(options.async_step_climate_profiles({}))
    room=saved["completed"]["data"]["climate_rooms"]["living"]
    assert room["dehumidifier_entity"]=="humidifier.dryer"
    assert room["cool_climate_entity"]=="climate.ac"
    assert room["humidity_entity"]=="sensor.living_humidity"
    assert room["extraction_fan_entity"]=="fan.extractor"


def test_native_humidity_target_needs_separate_permission_and_known_sensor(monkeypatch,adapter):
    options=_make_options(monkeypatch,adapter)
    h=options.hass
    states=[
        MockState("sensor.living_temperature",20,device_class="temperature",unit="°C"),
        MockState("sensor.living_humidity",67,device_class="humidity",unit="%"),
        MockState("climate.living","heat"),
        MockState("humidifier.dryer","on",device_class="dehumidifier"),
    ]
    for state in states:
        h._values[state.entity_id]=state
        h._entity_areas[state.entity_id]="living"
    h._values["climate.living"].attributes.update({
        "hvac_modes":["off","heat"],"supported_features":1,
    })
    asyncio.run(options.async_step_init())
    asyncio.run(options.async_step_climate({"climate_area":"living"}))
    asyncio.run(options.async_step_climate_room({
        "climate_enabled":True,"climate_allow_actuation":True,
        "climate_entity":"climate.living",
        "climate_temperature_entity":"sensor.living_temperature",
        "climate_controller":"device","climate_mode":"heat",
    }))
    asyncio.run(options.async_step_climate_presence({}))
    invalid=asyncio.run(options.async_step_climate_equipment({
        "climate_humidity_setpoint_auto":True,
        "climate_dehumidifier_entity":"humidifier.dryer",
    }))
    assert invalid["errors"]["base"]=="climate_humidity_control_inputs_missing"
    next_form=asyncio.run(options.async_step_climate_equipment({
        "climate_humidity_setpoint_auto":True,
        "climate_dehumidifier_entity":"humidifier.dryer",
        "climate_humidity_entity":"sensor.living_humidity",
    }))
    assert next_form["step_id"]=="climate_profiles"
    saved=asyncio.run(options.async_step_climate_profiles({}))
    climate=saved["completed"]["data"]["climate_rooms"]["living"]
    assert climate["humidity_setpoint_auto"] is True
    assert climate["dehumidifier_entity"]=="humidifier.dryer"
    assert climate["humidity_entity"]=="sensor.living_humidity"


def test_climate_fan_air_wizard_requires_verified_room_sensor(monkeypatch,adapter):
    options=_make_options(monkeypatch,adapter)
    h=options.hass
    extra=[
        MockState("sensor.living_temperature",21,device_class="temperature",unit="°C"),
        MockState("sensor.living_co2",1580,device_class="co2",unit="ppm"),
        MockState("sensor.living_pm25",48,device_class="pm25",unit="µg/m³"),
        MockState("climate.living","heat"),
        MockState("fan.purifier","on"),
        MockState("fan.extractor","on"),
    ]
    for state in extra:
        h._values[state.entity_id]=state
        h._entity_areas[state.entity_id]="living"
    h._values["climate.living"].attributes.update({
        "hvac_modes":["off","heat"],"supported_features":1})
    asyncio.run(options.async_step_init())
    asyncio.run(options.async_step_climate({"climate_area":"living"}))
    asyncio.run(options.async_step_climate_room({
        "climate_enabled":True,"climate_allow_actuation":True,
        "climate_entity":"climate.living",
        "climate_temperature_entity":"sensor.living_temperature",
        "climate_controller":"device","climate_mode":"heat",
    }))
    asyncio.run(options.async_step_climate_presence({}))
    form=asyncio.run(options.async_step_climate_equipment({
        "climate_purifier_fan_entity":"fan.purifier",
        "climate_extraction_fan_entity":"fan.extractor",
    }))
    assert form["step_id"]=="climate_air_strategy"
    bad=asyncio.run(options.async_step_climate_air_strategy({
        "climate_fan_speed_auto":True,
        "climate_pm25_sensor_verified":False,
    }))
    assert bad["errors"]["base"]=="climate_fan_control_inputs_missing"
    save=asyncio.run(options.async_step_climate_air_strategy({
        "climate_fan_speed_auto":True,
        "climate_pm25_sensor_verified":True,
        "climate_pm25_entity":"sensor.living_pm25",
        "climate_co2_entity":"sensor.living_co2",
        "climate_extraction_speed_percent":70,
        "climate_purifier_speed_percent":75,
    }))
    assert save["step_id"]=="climate_profiles"
    room=asyncio.run(options.async_step_climate_profiles({}))["completed"]["data"]["climate_rooms"]["living"]
    assert room["fan_speed_auto"] is True
    assert room["co2_entity"]=="sensor.living_co2"
    assert room["pm25_entity"]=="sensor.living_pm25"
    assert room["pm25_sensor_verified"] is True
    assert room["purifier_speed_percent"]==75


def test_environment_only_room_can_enable_verified_dehumidifier_without_thermostat(monkeypatch,adapter):
    options=_make_options(monkeypatch,adapter)
    hass=options.hass
    humid=MockState("sensor.living_humidity",72,device_class="humidity",unit="%")
    appliance=MockState("humidifier.living_dehumidifier","off",device_class="dehumidifier")
    appliance.attributes.update({"humidity":60,"min_humidity":35,"max_humidity":75})
    for entity in (humid,appliance):
        hass._values[entity.entity_id]=entity
        hass._entity_areas[entity.entity_id]="living"
    asyncio.run(options.async_step_init())
    asyncio.run(options.async_step_climate({"climate_area":"living"}))
    step=asyncio.run(options.async_step_climate_room({
        "climate_enabled":True,"climate_allow_actuation":True,
        "climate_controller":"environment","climate_mode":"auto",
        "climate_temperature_entity":"none",
        "climate_entity":None,
    }))
    assert step["step_id"]=="climate_presence"
    step=asyncio.run(options.async_step_climate_presence({}))
    assert step["step_id"]=="climate_equipment"
    rejected=asyncio.run(options.async_step_climate_equipment({
        "climate_humidity_power_auto":True,
        "climate_dehumidifier_entity":"humidifier.living_dehumidifier",
        "climate_humidity_entity":"sensor.living_humidity",
    }))
    assert rejected["errors"]["base"]=="climate_humidity_power_inputs_missing"
    step=asyncio.run(options.async_step_climate_equipment({
        "climate_humidity_power_auto":True,
        "climate_humidity_power_hardware_confirmed":True,
        "climate_humidity_power_windowless_confirmed":True,
        "climate_humidity_power_min_on_s":600,
        "climate_humidity_power_min_off_s":600,
        "climate_humidity_power_max_on_s":7200,
        "climate_dehumidifier_entity":"humidifier.living_dehumidifier",
        "climate_humidity_entity":"sensor.living_humidity",
    }))
    assert step["step_id"]=="climate_profiles"
    saved=asyncio.run(options.async_step_climate_profiles({}))
    cfg=saved["completed"]["data"]["climate_rooms"]["living"]
    assert cfg["controller"]=="environment"
    assert cfg["climate_entity"] is None and cfg["temperature_entity"] is None
    assert cfg["humidity_power_auto"] is True
    assert cfg["humidity_power_hardware_confirmed"] is True
    assert cfg["dehumidifier_entity"]=="humidifier.living_dehumidifier"


def test_humidity_power_and_setpoint_cannot_be_enabled_together(monkeypatch,adapter):
    options=_make_options(monkeypatch,adapter)
    h=options.hass
    values=[
        MockState("sensor.living_humidity",72,device_class="humidity",unit="%"),
        MockState("humidifier.living_dry","off",device_class="dehumidifier"),
    ]
    for item in values:
        h._values[item.entity_id]=item
        h._entity_areas[item.entity_id]="living"
    asyncio.run(options.async_step_init())
    asyncio.run(options.async_step_climate({"climate_area":"living"}))
    asyncio.run(options.async_step_climate_room({
        "climate_enabled":True,"climate_allow_actuation":True,
        "climate_controller":"environment",
        "climate_temperature_entity":"none",
    }))
    asyncio.run(options.async_step_climate_presence({}))
    result=asyncio.run(options.async_step_climate_equipment({
        "climate_humidity_power_auto":True,
        "climate_humidity_setpoint_auto":True,
        "climate_humidity_power_hardware_confirmed":True,
        "climate_dehumidifier_entity":"humidifier.living_dry",
        "climate_humidity_entity":"sensor.living_humidity",
    }))
    assert result["errors"]["base"]=="climate_humidity_power_inputs_missing"


def test_dry_only_climate_mode_without_fictitious_temperature_sensor(monkeypatch,adapter):
    options=_make_options(monkeypatch,adapter)
    h=options.hass
    dryer=MockState("climate.room_dryer","dry")
    dryer.attributes.update({"hvac_modes":["dry"],"supported_features":0})
    h._values[dryer.entity_id]=dryer
    h._entity_areas[dryer.entity_id]="living"
    asyncio.run(options.async_step_init())
    asyncio.run(options.async_step_climate({"climate_area":"living"}))
    result=asyncio.run(options.async_step_climate_room({
        "climate_enabled":True,
        "climate_controller":"device",
        "climate_mode":"dry",
        "climate_entity":"climate.room_dryer",
        "climate_temperature_entity":"none",
        "climate_allow_actuation":False,
    }))
    assert result["step_id"]=="climate_presence"
    result=asyncio.run(options.async_step_climate_presence({}))
    assert result["step_id"]=="climate_equipment"
    result=asyncio.run(options.async_step_climate_equipment({
        "climate_window_efficiency_notify":True,
    }))
    assert result["step_id"]=="climate_profiles"
    result=asyncio.run(options.async_step_climate_profiles({}))
    room=result["completed"]["data"]["climate_rooms"]["living"]
    assert room["mode"]=="dry"
    assert room["temperature_entity"] is None
    assert room["window_efficiency_notify"] is True


def test_window_substitution_notifications_default_off_for_legacy_climate_rooms(monkeypatch,adapter):
    options=_make_options(monkeypatch,adapter)
    asyncio.run(options.async_step_init())
    asyncio.run(options.async_step_climate({"climate_area":"living"}))
    asyncio.run(options.async_step_climate_room({"climate_enabled":False}))
    asyncio.run(options.async_step_climate_presence({}))
    result=asyncio.run(options.async_step_climate_profiles({}))
    cfg=result["completed"]["data"]["climate_rooms"]["living"]
    assert cfg.get("window_efficiency_notify") is not True


def test_environment_only_native_fan_power_consent_and_mutual_exclusion(monkeypatch,adapter):
    options=_make_options(monkeypatch,adapter)
    h=options.hass
    fan=MockState("fan.living_extractor","off")
    co2=MockState("sensor.living_co2",1600,device_class="co2",unit="ppm")
    for device in (fan,co2):
        h._values[device.entity_id]=device
        h._entity_areas[device.entity_id]="living"
    asyncio.run(options.async_step_init())
    asyncio.run(options.async_step_climate({"climate_area":"living"}))
    asyncio.run(options.async_step_climate_room({
        "climate_enabled":True,"climate_allow_actuation":True,
        "climate_controller":"environment",
        "climate_temperature_entity":"none",
    }))
    asyncio.run(options.async_step_climate_presence({}))
    next_form=asyncio.run(options.async_step_climate_equipment({
        "climate_extraction_fan_entity":"fan.living_extractor",
    }))
    assert next_form["step_id"]=="climate_air_strategy"
    invalid=asyncio.run(options.async_step_climate_air_strategy({
        "climate_fan_power_auto":True,
        "climate_co2_entity":"sensor.living_co2",
    }))
    assert invalid["errors"]["base"]=="climate_fan_power_inputs_missing"
    invalid=asyncio.run(options.async_step_climate_air_strategy({
        "climate_fan_power_auto":True,"climate_fan_speed_auto":True,
        "climate_fan_power_hardware_confirmed":True,
        "climate_co2_entity":"sensor.living_co2",
    }))
    assert invalid["errors"]["base"]=="climate_fan_power_inputs_missing"
    enabled=asyncio.run(options.async_step_climate_air_strategy({
        "climate_fan_power_auto":True,
        "climate_fan_speed_auto":False,
        "climate_fan_power_hardware_confirmed":True,
        "climate_fan_power_min_on_s":300,
        "climate_fan_power_min_off_s":300,
        "climate_fan_power_max_on_s":3600,
        "climate_co2_entity":"sensor.living_co2",
    }))
    assert enabled["step_id"]=="climate_profiles"
    saved=asyncio.run(options.async_step_climate_profiles({}))
    cfg=saved["completed"]["data"]["climate_rooms"]["living"]
    assert cfg["controller"]=="environment"
    assert cfg["fan_power_auto"] is True and cfg["fan_speed_auto"] is False
    assert cfg["fan_power_hardware_confirmed"] is True



def test_commissioned_dry_fan_setup_requires_exact_modes_sensor_and_extra_consent(
    monkeypatch,adapter,
):
    options=_make_options(monkeypatch,adapter)
    hass=options.hass
    sensor=MockState("sensor.living_humidity",76,device_class="humidity",unit="%")
    ac=MockState("climate.living_dry","fan_only")
    ac.attributes.update({"hvac_modes":["off","dry","fan_only"],
                          "supported_features":0,"hvac_action":"fan"})
    for item in (sensor,ac):
        hass._values[item.entity_id]=item
        hass._entity_areas[item.entity_id]="living"
    asyncio.run(options.async_step_init())
    asyncio.run(options.async_step_climate({"climate_area":"living"}))
    result=asyncio.run(options.async_step_climate_room({
        "climate_enabled":True,"climate_allow_actuation":True,
        "climate_controller":"environment","climate_temperature_entity":"none",
    }))
    assert result["step_id"]=="climate_presence"
    asyncio.run(options.async_step_climate_presence({}))
    request={
        "climate_dry_climate_entity":ac.entity_id,
        "climate_humidity_entity":sensor.entity_id,
        "climate_dry_fan_mode_auto":True,
    }
    result=asyncio.run(options.async_step_climate_equipment(request))
    assert result["errors"]["base"]=="climate_dry_fan_control_inputs_missing"
    # A configured DRY-only model does not invent FAN_ONLY support.
    ac.attributes["hvac_modes"]=["dry"]
    result=asyncio.run(options.async_step_climate_equipment({
        **request,"climate_dry_fan_hardware_confirmed":True,
    }))
    assert result["errors"]["base"]=="climate_dry_fan_control_inputs_missing"
    ac.attributes["hvac_modes"]=["off","dry","fan_only"]
    result=asyncio.run(options.async_step_climate_equipment({
        **request,"climate_dry_fan_hardware_confirmed":True,
        "climate_dry_fan_mode_dwell_s":1800,
        "climate_dry_fan_windowless_confirmed":True,
    }))
    assert result["step_id"]=="climate_profiles"
    saved=asyncio.run(options.async_step_climate_profiles({}))
    final=saved["completed"]["data"]["climate_rooms"]["living"]
    assert final["controller"]=="environment"
    assert final["climate_entity"] is None
    assert final["dry_climate_entity"]==ac.entity_id
    assert final["humidity_entity"]==sensor.entity_id
    assert final["dry_fan_mode_auto"] is True
    assert final["dry_fan_hardware_confirmed"] is True
    assert final["dry_fan_mode_dwell_s"]==1800


def test_dry_fan_mode_consent_does_not_override_separate_humidity_controller(
    monkeypatch,adapter,
):
    options=_make_options(monkeypatch,adapter)
    hass=options.hass
    for item in (
        MockState("sensor.living_humidity",76,device_class="humidity",unit="%"),
        MockState("climate.living_dry","fan_only"),
        MockState("humidifier.living_dry","off",device_class="dehumidifier"),
    ):
        hass._values[item.entity_id]=item
        hass._entity_areas[item.entity_id]="living"
    hass.states.get("climate.living_dry").attributes.update({
        "hvac_modes":["off","dry","fan_only"],"hvac_action":"fan",
    })
    asyncio.run(options.async_step_init())
    asyncio.run(options.async_step_climate({"climate_area":"living"}))
    asyncio.run(options.async_step_climate_room({
        "climate_enabled":True,"climate_allow_actuation":True,
        "climate_controller":"environment","climate_temperature_entity":"none",
    }))
    asyncio.run(options.async_step_climate_presence({}))
    result=asyncio.run(options.async_step_climate_equipment({
        "climate_dry_fan_mode_auto":True,
        "climate_dry_fan_hardware_confirmed":True,
        "climate_dry_climate_entity":"climate.living_dry",
        "climate_humidity_entity":"sensor.living_humidity",
        "climate_dehumidifier_entity":"humidifier.living_dry",
        "climate_humidity_setpoint_auto":True,
    }))
    assert result["errors"]["base"]=="climate_dry_fan_control_inputs_missing"


def test_pollen_step_from_outside_submenu_is_reliable_without_aqi(monkeypatch, adapter):
    opt = _make_options(monkeypatch, adapter)
    asyncio.run(opt.async_step_init())
    menu = asyncio.run(opt.async_step_outside_data())
    assert "pollen" in menu["menu_options"]
    form = asyncio.run(opt.async_step_pollen())
    assert form["step_id"] == "pollen"
    assert "pollen_entity" in form["data_schema"]
    bad = asyncio.run(opt.async_step_pollen({
        "pollen_entity":None, "pollen_high_from":9,"pollen_max_scale":5
    }))
    assert bad["errors"]["base"] == "invalid_environment_scale"
    done = asyncio.run(opt.async_step_pollen({
        "pollen_entity":None,"pollen_high_from":3,
        "pollen_max_scale":5,"pollen_avoid_ventilation":True,
    }))
    assert done["completed"]["data"]["environment_global"]["pollen_high_from"]==3
    assert done["completed"]["data"]["environment_global"]["pollen_avoid_ventilation"] is True
    assert done["completed"]["data"]["thresholds"]=={"indoor_co2":1200}


def test_outside_aqi_submenu_no_sources_still_renders_nonempty_form(monkeypatch,adapter):
    opt=_make_options(monkeypatch,adapter)
    asyncio.run(opt.async_step_init())
    form=asyncio.run(opt.async_step_outside_aqi())
    assert form["step_id"]=="outside_aqi"
    assert "outside_aqi_no_sources" in form["data_schema"]
    done=asyncio.run(opt.async_step_outside_aqi({"outside_aqi_no_sources":False}))
    assert done["completed"]["data"]["weather_entities"]==["weather.home"]


def test_shared_general_presence_sources_saved_without_touching_room_settings(monkeypatch,adapter):
    opt=_make_options(monkeypatch,adapter)
    tracker=MockState("person.occupant","home")
    global_rooms=MockState("sensor.house_occupied_rooms",'["living"]')
    sleep=MockState("sensor.sleep_rooms",'[]')
    global_rooms.attributes["occupied"]=["living"]
    sleep.attributes["rooms"]=["living"]
    sensor=MockState("binary_sensor.living_occupancy","on",device_class="occupancy")
    for st in (tracker,global_rooms,sleep,sensor):
        opt.hass._values[st.entity_id]=st
    opt.hass._entity_areas[sensor.entity_id]="living"
    asyncio.run(opt.async_step_init())
    form=asyncio.run(opt.async_step_general_settings())
    assert form["step_id"]=="general_settings"
    assert "general_sleep_rooms_attribute" in form["data_schema"]
    done=asyncio.run(opt.async_step_general_settings({
        "general_room_occupancy_sensors":[sensor.entity_id],
        "general_occupied_rooms_entity":global_rooms.entity_id,
        "general_occupied_rooms_attribute":"occupied",
        "general_home_trackers":[tracker.entity_id],
        "general_home_policy":"any_home",
        "general_sleep_rooms_entity":sleep.entity_id,
        "general_sleep_rooms_attribute":"rooms",
        "general_source_stale_minutes":240,
    }))
    assert done["step_id"]=="general_settings"
    attr_picker=next(v for k,v in done["data_schema"].items()
                     if k=="general_sleep_rooms_attribute")
    assert "rooms" in [x["value"] for x in attr_picker.config.options]
    assert "__state__" in [x["value"] for x in attr_picker.config.options]
    done=asyncio.run(opt.async_step_general_settings({
        "general_room_occupancy_sensors":[sensor.entity_id],
        "general_occupied_rooms_entity":global_rooms.entity_id,
        "general_occupied_rooms_attribute":"occupied",
        "general_home_trackers":[tracker.entity_id],
        "general_home_policy":"any_home",
        "general_sleep_rooms_entity":sleep.entity_id,
        "general_sleep_rooms_attribute":"rooms",
        "general_source_stale_minutes":240,
    }))
    config=done["completed"]["data"]
    assert config["occupancy_global"]["occupied_rooms_entity"]==global_rooms.entity_id
    assert config["occupancy_global"]["sleep_rooms_attribute"]=="rooms"
    assert config["areas"]==["living"]
    assert config["thresholds"]=={"indoor_co2":1200}


def test_area_device_list_preselects_every_supported_room_entity_without_actuation(monkeypatch,adapter):
    opt=_make_options(monkeypatch,adapter)
    ha=opt.hass
    st=MockState("climate.living_ac","cool")
    st.attributes["hvac_modes"]=["off","cool","dry","fan_only"]
    fan=MockState("fan.living_filter","off")
    humidifier=MockState("humidifier.living_dryer","off",device_class="dehumidifier")
    foreign=MockState("fan.other_room","off")
    for x in (st,fan,humidifier,foreign):
        ha._values[x.entity_id]=x
        ha._entity_areas[x.entity_id]="kitchen" if x==foreign else "living"
    asyncio.run(opt.async_step_init())
    assert asyncio.run(opt.async_step_area_devices({"area_devices_area":"living"}))["step_id"]=="select_devices"
    listing=asyncio.run(opt.async_step_select_devices())
    choice=next(k.default for k in listing["data_schema"] if k=="selected_devices")
    assert set(choice)=={st.entity_id,fan.entity_id,humidifier.entity_id}
    assert "fan.other_room" not in choice
    nxt=asyncio.run(opt.async_step_select_devices({"selected_devices":choice}))
    assert nxt["step_id"]=="device_choice"
    assert asyncio.run(opt.async_step_device_choice({"device_choice":st.entity_id}))["step_id"]=="device_menu"
    form=asyncio.run(opt.async_step_device_settings())
    assert form["step_id"]=="device_settings"
    assert "device_sleep_heat_c" in form["data_schema"]
    assert "device_presence_requirement" in form["data_schema"]
    saved=asyncio.run(opt.async_step_device_settings({"device_auto_control":False}))
    data=saved["completed"]["data"]["climate_rooms"]["living"]
    assert set(data["selected_devices"])==set(choice)
    assert data["device_settings"][st.entity_id]["auto_control"] is False
    assert data.get("allow_actuation") is not True


def test_device_auto_control_requires_exact_sensor_and_hardware_for_off(monkeypatch,adapter):
    opt=_make_options(monkeypatch,adapter)
    ha=opt.hass
    st=MockState("climate.living_heat","heat")
    st.attributes.update({"hvac_modes":["off","heat"],"supported_features":1})
    temp=MockState("sensor.living_temperature",20,device_class="temperature",unit="°C")
    for x in (st,temp):
        ha._values[x.entity_id]=x
        ha._entity_areas[x.entity_id]="living"
    asyncio.run(opt.async_step_init())
    asyncio.run(opt.async_step_area_devices({"area_devices_area":"living"}))
    asyncio.run(opt.async_step_select_devices({"selected_devices":[st.entity_id]}))
    asyncio.run(opt.async_step_device_choice({"device_choice":st.entity_id}))
    missing=asyncio.run(opt.async_step_device_settings({
        "device_auto_control":True,"device_absence_action":"off",
        "device_presence_requirement":"room",
        "device_temperature_entity":temp.entity_id,
        "device_hardware_confirmed":False,
    }))
    assert missing["errors"]["base"]=="device_hardware_required"
    okay=asyncio.run(opt.async_step_device_settings({
        "device_auto_control":True,"device_method":"setpoint",
        "device_absence_action":"off","device_presence_requirement":"room",
        "device_temperature_entity":temp.entity_id,"device_hardware_confirmed":True,
    }))
    room=okay["completed"]["data"]["climate_rooms"]["living"]
    assert room["enabled"] is True
    assert room["allow_actuation"] is True
    assert room["climate_entity"]==st.entity_id
    assert room["device_settings"][st.entity_id]["presence_requirement"]=="room"



def test_humidifier_without_device_class_stays_visible_but_cannot_be_armed(monkeypatch,adapter):
    options=_make_options(monkeypatch,adapter)
    old=MockState("humidifier.generic","off")
    options.hass._values[old.entity_id]=old
    options.hass._entity_areas[old.entity_id]="living"
    asyncio.run(options.async_step_init())
    asyncio.run(options.async_step_area_devices({"area_devices_area":"living"}))
    form=asyncio.run(options.async_step_select_devices())
    selected=next(k.default for k in form["data_schema"] if k=="selected_devices")
    assert old.entity_id in selected
    asyncio.run(options.async_step_select_devices({"selected_devices":[old.entity_id]}))
    asyncio.run(options.async_step_device_choice({"device_choice":old.entity_id}))
    bad=asyncio.run(options.async_step_device_settings({
        "device_auto_control":True,"device_method":"power",
        "device_hardware_confirmed":True,
    }))
    assert bad["errors"]["base"]=="device_hardware_required"


def test_dry_only_climate_is_inventory_and_advisory_not_temperature_auto(monkeypatch,adapter):
    options=_make_options(monkeypatch,adapter)
    ac=MockState("climate.dry_only","dry")
    ac.attributes["hvac_modes"]=["off","dry"]
    temp=MockState("sensor.living_temperature",21,device_class="temperature",unit="°C")
    for st in (ac,temp):
        options.hass._values[st.entity_id]=st
        options.hass._entity_areas[st.entity_id]="living"
    asyncio.run(options.async_step_init())
    asyncio.run(options.async_step_area_devices({"area_devices_area":"living"}))
    asyncio.run(options.async_step_select_devices({"selected_devices":[ac.entity_id]}))
    asyncio.run(options.async_step_device_choice({"device_choice":ac.entity_id}))
    invalid=asyncio.run(options.async_step_device_settings({
        "device_auto_control":True,"device_method":"setpoint",
        "device_temperature_entity":temp.entity_id,
    }))
    assert invalid["errors"]["base"]=="device_method_invalid"
    result=asyncio.run(options.async_step_device_settings({
        "device_auto_control":False,
    }))
    assert result["completed"]["data"]["climate_rooms"]["living"][
        "device_settings"
    ][ac.entity_id]["auto_control"] is False


def test_room_source_picker_excludes_irrelevant_entities_and_only_valid_attributes(monkeypatch,adapter):
    options=_make_options(monkeypatch,adapter)
    h=options.hass
    irrelevant=MockState("sensor.rubbish",'["not_a_real_area"]')
    valid=MockState("sensor.sleep_rooms","active")
    valid.attributes["sleeping_areas"]=["living"]
    valid.attributes["unrelated"]={"other":["something"]}
    for state in (irrelevant,valid):
        h._values[state.entity_id]=state
    asyncio.run(options.async_step_init())
    form=asyncio.run(options.async_step_general_settings())
    ent=next(v for k,v in form["data_schema"].items()
             if k=="general_sleep_rooms_entity")
    eligible=[x["value"] for x in ent.config.options]
    assert valid.entity_id in eligible
    assert irrelevant.entity_id not in eligible
    choose=asyncio.run(options.async_step_general_settings({
        "general_sleep_rooms_entity":valid.entity_id,
    }))
    assert choose["step_id"]=="general_settings"
    attrs=next(v for k,v in choose["data_schema"].items()
               if k=="general_sleep_rooms_attribute")
    assert [x["value"] for x in attrs.config.options]==["sleeping_areas"]
