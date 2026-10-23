"""Native room grouping and in-place beta11 migration; no hardware calls."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace
from types import MappingProxyType, SimpleNamespace
import sys
import types
import uuid

import pytest
from test_device_hierarchy import hierarchy
from test_discovery import adapter
from custom_components.air_quality_advisor import room_hubs as rooms
from custom_components.air_quality_advisor.device_hierarchy import async_register_hierarchy


@dataclass(frozen=True, kw_only=True)
class Subentry:
    data: object
    subentry_type: str
    title: str
    unique_id: str | None
    subentry_id: str = field(default_factory=lambda: uuid.uuid4().hex)


class ConfigEntries:
    def __init__(self):
        self.updated = []
        self.reloads = []
        self.removed = []
        self.callbacks = []

    def notify(self, entry):
        for callback in tuple(self.callbacks):
            callback("updated", entry)

    def async_update_entry(self, entry, **values):
        if all(getattr(entry, k) == v for k, v in values.items()):
            return False
        self.updated.append((entry.entry_id, values))
        for k, v in values.items():
            setattr(entry, k, v)
        self.notify(entry)
        return True

    def async_add_subentry(self, entry, subentry):
        assert not any(s.unique_id == subentry.unique_id for s in entry.subentries.values())
        entry.subentries = {**entry.subentries, subentry.subentry_id: subentry}
        self.notify(entry)
        return True

    def async_update_subentry(self, entry, subentry, **values):
        entry.subentries = {**entry.subentries, subentry.subentry_id: replace(subentry, **values)}
        self.notify(entry)
        return True

    def async_remove_subentry(self, entry, subentry_id):
        entry.subentries = {k: v for k, v in entry.subentries.items() if k != subentry_id}
        self.removed.append(subentry_id)
        self.notify(entry)
        return True

    def async_schedule_reload(self, entry_id):
        self.reloads.append(entry_id)


def install_api(monkeypatch, hass, entry):
    module = sys.modules.get("homeassistant.config_entries") or types.ModuleType("homeassistant.config_entries")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setattr(module, "ConfigSubentry", Subentry, raising=False)
    monkeypatch.setattr(module, "SIGNAL_CONFIG_ENTRY_CHANGED", "config_entry_changed", raising=False)
    monkeypatch.setattr(module, "ConfigEntryChange", SimpleNamespace(UPDATED="updated"), raising=False)
    from homeassistant import core
    monkeypatch.setattr(core, "callback", lambda f: f, raising=False)
    if not hasattr(hass, "config_entries"):
        hass.config_entries = ConfigEntries()
    entry.subentries = {}
    entry.async_on_unload = lambda callback: None
    dispatcher = types.ModuleType("homeassistant.helpers.dispatcher")
    def connect(h, signal, callback):
        assert signal == "config_entry_changed"
        h.config_entries.callbacks.append(callback)
        return lambda: h.config_entries.callbacks.remove(callback)
    dispatcher.async_dispatcher_connect = connect
    monkeypatch.setitem(sys.modules, dispatcher.__name__, dispatcher)


@pytest.fixture
def grouped(hierarchy, monkeypatch):
    h = hierarchy
    install_api(monkeypatch, h.hass, h.entry)
    from homeassistant.helpers import entity_registry as er
    ent = SimpleNamespace(entries={}, changes=[])
    def update(entity_id, **changes):
        ent.changes.append((entity_id, changes))
        item = ent.entries[entity_id]
        for key, value in changes.items():
            setattr(item, key, value)
    ent.async_update_entity = update
    ent.async_get = h.entities.get
    monkeypatch.setattr(er, "async_get", lambda hass: ent)
    monkeypatch.setattr(er, "async_entries_for_device", lambda reg, did, **kw:
        [e for e in ent.entries.values() if e.device_id == did], raising=False)
    h.entity_registry = ent
    return h


def sync(h):
    h.manager._room_subentries = rooms.async_sync_room_hubs(h.hass, h.entry)
    async_register_hierarchy(h.hass, h.entry)


def test_beta11_services_migrate_in_place_to_real_room_groups(grouped):
    h = grouped
    h.source("climate.ac")
    h.source("fan.ac")
    async_register_hierarchy(h.hass, h.entry)
    originals = {key: device.id for key, device in h.registry.keys.items()}
    source_before = deepcopy(vars(h.registry.devices["physical-ac"]))
    for device in h.registry.keys.values():
        device.entry_type = "service"  # Actual beta11 stored classification.
        device.labels = {"custom-label"}
        device.disabled_by = "user"
        device.name_by_user = "User's name"
    area_device = h.registry.keys[("hem", ("air_quality_advisor", "hem_area_kitchen"))]
    entity = SimpleNamespace(entity_id="number.original_room", unique_id="stable-id",
        device_id=area_device.id, config_entry_id="hem", config_subentry_id=None,
        disabled_by="user", name="User's setting")
    h.entity_registry.entries[entity.entity_id] = entity
    sync(h)
    assert {key: d.id for key, d in h.registry.keys.items()} == originals
    assert len(h.entry.subentries) == 4  # Home + three configured room groups.
    for key, device in h.registry.keys.items():
        assert device.entry_type is None
        assert device.labels == {"custom-label"} and device.disabled_by == "user"
        assert device.name_by_user == "User's name"
        if key[1][1] != "hem":
            assert device.config_subentry_id in h.entry.subentries
    assert entity.config_subentry_id == h.manager._room_subentries["kitchen"]
    assert entity.unique_id == "stable-id" and entity.entity_id == "number.original_room"
    assert entity.disabled_by == "user" and entity.name == "User's setting"
    assert vars(h.registry.devices["physical-ac"]) == source_before


def test_one_room_group_contains_room_settings_and_multiple_physical_devices(grouped):
    h = grouped
    h.source("climate.ac")
    h.source("fan.ac")  # Same physical device, not a second controller device.
    h.source("humidifier.dry", device_id="physical-dry", device_name="Dehumidifier")
    cfg = h.settings["climate_rooms"]["kitchen"]
    cfg["selected_devices"].append("humidifier.dry")
    cfg["device_settings"]["humidifier.dry"] = {"auto_control": True}
    cfg["dehumidifier_entity"] = "humidifier.dry"
    sync(h)
    sid = h.manager._room_subentries["kitchen"]
    # HA frontend partitions ordinary devices by config_subentry_id.
    displayed = [d for d in h.registry.keys.values() if d.config_subentry_id == sid and d.entry_type is None]
    assert len(displayed) == 3  # General room settings + AC + dehumidifier.
    assert sum(d.model == "Managed Environment Controller" for d in displayed) == 2
    assert not any(d.entry_type == "service" for d in h.registry.keys.values())
    hub = next(d for d in displayed if d.model == "Area Environment Hub")
    assert all(d.via_device_id == hub.id for d in displayed if d is not hub)


def test_reload_does_not_duplicate_or_reassign_room_devices(grouped):
    h = grouped
    h.source("climate.ac")
    sync(h)
    before = deepcopy(h.manager._device_hierarchy)
    options = deepcopy(h.entry.options)
    revision_count = len(h.hass.config_entries.updated)
    sync(h)
    assert h.manager._device_hierarchy == before and h.entry.options == options
    assert len(h.hass.config_entries.updated) == revision_count
    assert h.registry.updated  # Initial area assignments only.


def test_native_area_rename_and_custom_group_title_preserved(grouped):
    h = grouped
    sync(h)
    sid = h.manager._room_subentries["kitchen"]
    h.areas["kitchen"].name = "Kitchen renamed"
    sync(h)
    assert h.entry.subentries[sid].title == "Kitchen renamed"
    h.hass.config_entries.async_update_subentry(h.entry, h.entry.subentries[sid], title="My hub")
    h.areas["kitchen"].name = "Kitchen again"
    sync(h)
    assert h.entry.subentries[sid].title == "My hub"


def test_removing_group_disables_only_that_room_without_recreating_it(grouped):
    h = grouped
    h.settings["pid_rooms"] = {"kitchen": {"enabled": True, "kp": 12}, "office": {"enabled": True, "kp": 21}}
    sync(h)
    remove = h.manager._room_subentries["kitchen"]
    h.hass.config_entries.async_remove_subentry(h.entry, remove)
    groups = rooms.async_sync_room_hubs(h.hass, h.entry)
    assert "kitchen" not in groups
    options = h.entry.options
    assert "kitchen" not in options["areas"]
    assert options["climate_rooms"]["kitchen"]["enabled"] is False
    assert options["climate_rooms"]["kitchen"]["allow_actuation"] is False
    assert options["pid_rooms"]["kitchen"] == {"enabled": False, "kp": 12}
    assert options["pid_rooms"]["office"] == {"enabled": True, "kp": 21}
    # Original configuration/calibration is retained, not deleted.
    assert h.entry.data["climate_rooms"]["kitchen"]["enabled"] is True


def test_configure_deselection_and_deleted_ha_area_remove_only_stale_groups(grouped):
    h = grouped
    sync(h)
    stale = h.manager._room_subentries["kitchen"]
    h.entry.options["areas"] = ["office"]
    h.entry.options["climate_rooms"] = {"bedroom": {"enabled": True}}
    groups = rooms.async_sync_room_hubs(h.hass, h.entry)
    assert set(groups) == {"office", "bedroom"}
    assert stale not in h.entry.subentries
    del h.areas["office"]
    assert set(rooms.async_sync_room_hubs(h.hass, h.entry)) == {"bedroom"}


def test_deletion_watcher_blocks_room_then_reloads_but_ignores_tuning_and_titles(grouped):
    h = grouped
    sync(h)
    calls = []
    h.manager._active = True
    h.manager._recalculate = lambda **kw: calls.append(kw)
    unsub = rooms.async_watch_room_hubs(h.hass, h.entry)
    sub = h.entry.subentries[h.manager._room_subentries["kitchen"]]
    h.hass.config_entries.async_update_subentry(h.entry, sub, title="Custom kitchen")
    h.hass.config_entries.async_update_entry(h.entry, options={**h.entry.options, "unrelated_setting": 3})
    assert not h.hass.config_entries.reloads
    h.hass.config_entries.async_remove_subentry(h.entry, sub.subentry_id)
    assert h.entry.options["climate_rooms"]["kitchen"]["enabled"] is False
    assert calls == [{"initial": True}]
    assert h.hass.config_entries.reloads == ["hem"]
    unsub()
    assert not h.hass.config_entries.callbacks


def test_all_platform_entities_use_same_subentry_as_their_device(grouped):
    h = grouped
    h.source("climate.ac")
    sync(h)
    mapping = h.manager._device_hierarchy["device_subentries"]
    entities = [SimpleNamespace(_attr_device_info={"identifiers": {("air_quality_advisor", identity)}})
                for identity in mapping]
    calls = []
    rooms.async_add_grouped_entities(h.manager, lambda batch, **kwargs: calls.append((batch, kwargs)), entities)
    assert sum(len(batch) for batch, _ in calls) == len(entities)
    for batch, kwargs in calls:
        for entity in batch:
            identity = next(iter(entity._attr_device_info["identifiers"]))[1]
            assert kwargs.get("config_subentry_id") == mapping[identity]
    assert len(calls) == 4  # Home + kitchen + bedroom + office.


def test_every_platform_uses_shared_native_grouping_not_private_entity_attributes():
    from pathlib import Path
    root = Path(__file__).parents[1] / "custom_components/air_quality_advisor"
    for name in ("sensor", "number", "select", "switch", "time", "button", "climate"):
        source = (root / f"{name}.py").read_text()
        assert "async_add_grouped_entities(entry.runtime_data, async_add_entities," in source, name
        assert "_attr_config_subentry_id" not in source, name


def test_foreign_subentries_and_settings_are_never_removed(grouped):
    h = grouped
    foreign = Subentry(data=MappingProxyType({"other": "value"}), subentry_type="other",
                       title="Unrelated", unique_id="foreign")
    h.hass.config_entries.async_add_subentry(h.entry, foreign)
    sync(h)
    assert h.entry.subentries[foreign.subentry_id] is foreign
    assert foreign.subentry_id not in h.hass.config_entries.removed


def test_selected_devices_remain_visible_without_automatic_control(grouped):
    h = grouped
    h.source("climate.ac")
    h.source("fan.ac")
    cfg = h.settings["climate_rooms"]["kitchen"]
    cfg["enabled"] = cfg["allow_actuation"] = False
    cfg["device_settings"] = {e: {"auto_control": False} for e in cfg["selected_devices"]}
    original = deepcopy(cfg)
    sync(h)
    sid = h.manager._room_subentries["kitchen"]
    displayed = [d for d in h.registry.keys.values() if d.config_subentry_id == sid]
    assert len(displayed) == 2  # General room settings and one physical AC.
    assert h.settings["climate_rooms"]["kitchen"] == original
    assert len(h.manager._device_hierarchy["controllers"]) == 1


def test_inventory_only_room_can_be_removed_without_reappearing(grouped):
    h = grouped
    h.settings["areas"] = []
    cfg = h.settings["climate_rooms"]["kitchen"]
    cfg["enabled"] = cfg["allow_actuation"] = False
    sync(h)
    sid = h.manager._room_subentries["kitchen"]
    h.hass.config_entries.async_remove_subentry(h.entry, sid)
    assert "kitchen" not in rooms.async_sync_room_hubs(h.hass, h.entry)
    assert h.entry.options["climate_rooms"]["kitchen"]["selected_devices"] == []
    assert h.entry.options["climate_rooms"]["kitchen"]["device_settings"] == cfg["device_settings"]


@pytest.fixture
def room_flow(grouped, monkeypatch):
    import importlib
    from homeassistant.helpers import area_registry as ar
    h = grouped
    monkeypatch.setattr(ar, "async_get", lambda hass: SimpleNamespace(areas=h.areas, async_get_area=h.areas.get))
    schema = types.ModuleType("probatio")
    schema.Schema = lambda obj: obj
    schema.Required = lambda key: key
    monkeypatch.setitem(sys.modules, "probatio", schema)
    selectors = types.ModuleType("homeassistant.helpers.selector")
    selectors.SelectSelectorConfig = lambda **kw: SimpleNamespace(**kw)
    selectors.SelectSelector = lambda config: SimpleNamespace(config=config)
    selectors.SelectSelectorMode = SimpleNamespace(DROPDOWN="dropdown")
    monkeypatch.setitem(sys.modules, selectors.__name__, selectors)
    class FlowBase:
        def _get_entry(self):
            return h.entry
        def async_abort(self, **kw):
            return {"type": "abort", **kw}
        def async_show_form(self, **kw):
            return {"type": "form", **kw}
        def async_create_entry(self, **kw):
            return {"type": "create_entry", **kw}
    ce = sys.modules["homeassistant.config_entries"]
    monkeypatch.setattr(ce, "ConfigSubentryFlow", FlowBase, raising=False)
    name = "custom_components.air_quality_advisor.room_hub_flow"
    monkeypatch.delitem(sys.modules, name, raising=False)
    cls = importlib.import_module(name).RoomHubFlow
    flow = cls()
    flow.hass = h.hass
    return flow, h


def test_room_add_flow_uses_real_areas_and_never_grants_hardware_control(room_flow):
    import asyncio
    flow, h = room_flow
    before = deepcopy(h.settings["climate_rooms"])
    form = asyncio.run(flow.async_step_user())
    assert {v["value"] for v in form["data_schema"]["area_id"].config.options} == set(h.areas)
    result = asyncio.run(flow.async_step_user({"area_id": "office"}))
    assert result["type"] == "create_entry"
    assert result["title"] == "Office" and result["unique_id"] == "area:office"
    assert h.entry.options["areas"] == ["kitchen", "office"]
    assert h.settings["climate_rooms"] == before
    assert "climate_rooms" not in h.entry.options
    assert h.hass.config_entries.reloads == ["hem"]  # Unloaded parent retries.


def test_room_add_flow_rejects_invalid_or_already_assigned_areas(room_flow):
    import asyncio
    flow, h = room_flow
    result = asyncio.run(flow.async_step_user({"area_id": "not-real"}))
    assert result["errors"] == {"base": "invalid_area"}
    assert not h.entry.options
    sync(h)
    result = asyncio.run(flow.async_step_user())
    assert result == {"type": "abort", "reason": "already_configured"}


def test_loaded_parent_addition_reloads_once_when_subentry_is_created(room_flow):
    import asyncio
    flow, h = room_flow
    h.manager._active = True
    unsub = rooms.async_watch_room_hubs(h.hass, h.entry)
    result = asyncio.run(flow.async_step_user({"area_id": "office"}))
    assert not h.hass.config_entries.reloads
    # Emulate core's flow completion, which adds the returned subentry.
    h.hass.config_entries.async_add_subentry(h.entry, Subentry(
        data=result["data"], title=result["title"], unique_id=result["unique_id"], subentry_type="room"))
    assert h.hass.config_entries.reloads == ["hem"]
    unsub()


def test_adding_room_to_disabled_entry_does_not_enable_it(room_flow):
    import asyncio
    flow, h = room_flow
    h.entry.disabled_by = "user"
    result = asyncio.run(flow.async_step_user({"area_id": "office"}))
    assert result["type"] == "create_entry"
    assert h.entry.disabled_by == "user" and not h.hass.config_entries.reloads


def test_every_room_subentry_catalog_is_localized_and_reproducible(tmp_path, monkeypatch):
    import json
    import shutil
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))
    from apply_room_hub_i18n import ROOM_TEXT, apply_room_hub_i18n
    component = root / "custom_components/air_quality_advisor"
    for name in ("strings.json", "compact_locales.json"):
        shutil.copy(component / name, tmp_path / name)
    shutil.copytree(component / "translations", tmp_path / "translations")
    files = [tmp_path / "strings.json", *sorted((tmp_path / "translations").glob("*.json"))]
    before = {p: p.read_bytes() for p in files}
    apply_room_hub_i18n(tmp_path)
    assert {p: p.read_bytes() for p in files} == before
    assert len(ROOM_TEXT) == 38
    for lang, (title, explanation) in ROOM_TEXT.items():
        doc = json.loads((tmp_path / "translations" / f"{lang}.json").read_text())
        sub = doc["config_subentries"]["room"]
        assert sub["entry_type"] == title
        assert sub["step"]["user"]["data_description"]["area_id"] == explanation
        assert "invalid_area" in sub["error"] and "already_configured" in sub["abort"]
        if lang != "en":
            assert title != ROOM_TEXT["en"][0] and explanation != ROOM_TEXT["en"][1]


def test_home_device_and_entities_use_native_home_subentry(grouped):
    h = grouped
    sync(h)
    from custom_components.air_quality_advisor.room_hubs import HOME_TYPE, home_subentry_id
    sid = home_subentry_id(h.entry)
    assert sid is not None
    assert h.entry.subentries[sid].subentry_type == HOME_TYPE
    assert h.manager._device_hierarchy["device_subentries"][h.entry.entry_id] == sid
    home_device = h.registry.async_get(h.manager._device_hierarchy["home_device_id"])
    assert home_device.config_subentry_id == sid
