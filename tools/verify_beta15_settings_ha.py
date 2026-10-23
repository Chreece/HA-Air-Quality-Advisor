"""Real HA config-entry/registry tests for beta15. No hardware services called."""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import MappingProxyType

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntries
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from custom_components.air_quality_advisor.device_controls import update_device_setting
from custom_components.air_quality_advisor.equipment_runtime import EquipmentRuntime
from custom_components.air_quality_advisor import equipment_model as model
from custom_components.air_quality_advisor.compact_options import CompactOptionsMixin
from custom_components.air_quality_advisor.occupancy_policy import configured_rooms
from custom_components.air_quality_advisor.room_sources import label
from custom_components.air_quality_advisor.device_hierarchy import async_register_hierarchy
from custom_components.air_quality_advisor.room_hubs import async_sync_room_hubs
from verify_room_setup_ha import entry


class MemoryStore:
    async def async_save(self, data):
        self.saved = data


class Manager:
    _active = False

    @property
    def settings(self):
        return {**self.entry.data, **self.entry.options}


async def check(directory):
    hass = HomeAssistant(directory)
    hass.config_entries = ConfigEntries(hass, {})
    dr.async_setup(hass)
    await ar.async_load(hass)
    await dr.async_load(hass)
    await er.async_load(hass)
    areas, devices, entities = ar.async_get(hass), dr.async_get(hass), er.async_get(hass)
    area = areas.async_create('Living room')
    native = entry('demo', 'native-source-entry', {})
    hass.config_entries._entries[native.entry_id] = native
    physical = devices.async_get_or_create(config_entry_id=native.entry_id,
        identifiers={('demo', 'real-registry-device')}, name='Test climate')
    devices.async_update_device(physical.id, area_id=area.id)
    climate = entities.async_get_or_create('climate', 'demo', 'beta15-climate', config_entry=native,
        device_id=physical.id, original_name='Climate')
    hass.states.async_set(climate.entity_id, 'off', {'friendly_name': 'Climate',
        'hvac_modes': ['off', 'heat'], 'supported_features': 1,
        'temperature_unit': '°C', 'temperature': 20, 'min_temp': 5, 'max_temp': 35})
    cfg = entry('air_quality_advisor', 'beta15-settings-test', {
        'areas': [area.id], 'climate_rooms': {area.id: {'selected_devices': [climate.entity_id],
            'device_settings': {climate.entity_id: {'auto_control': False}}}}})
    hass.config_entries._entries[cfg.entry_id] = cfg
    manager = Manager()
    manager.hass, manager.entry = hass, cfg
    cfg.runtime_data = manager
    manager._room_subentries = async_sync_room_hubs(hass, cfg)
    async_register_hierarchy(hass, cfg)
    assert isinstance(cfg.options, MappingProxyType)
    for key in ('sleep_room', 'enable_pmv'):
        await update_device_setting(manager, 'area_environment', key, True, area=area.id)
        assert cfg.options['environment_rooms'][area.id][key] is True
        await update_device_setting(manager, 'area_environment', key, False, area=area.id)
        assert cfg.options['environment_rooms'][area.id][key] is False
    runtime = manager.equipment = EquipmentRuntime(manager)
    runtime._active = runtime._ready = True
    runtime._store = MemoryStore()
    spec = model.specs(manager)[0]
    for method in ('automatic', 'pid', 'manual', 'off'):
        await runtime.async_update(spec, {'control_mode': method})
        assert model.settings(manager, spec)['control_mode'] == method
    assert cfg.options.get('climate_rooms', {}).get(area.id, {}).get('allow_actuation') is not True
    await runtime.async_update(spec, {'control_mode': 'automatic'})
    assert model.permission(manager, spec, model.capabilities(manager, spec)) == (True, False)
    await runtime.async_update(spec, {'allow_power': True})
    assert model.permission(manager, spec, model.capabilities(manager, spec)) == (True, True)
    await runtime.async_update(spec, {'allow_power': False})
    templates = entry('template', 'template-test-entry', {})
    hass.config_entries._entries[templates.entry_id] = templates
    template = entities.async_get_or_create('sensor', 'template', 'beta15-presence',
        config_entry=templates, original_name='Multi room presence')
    hass.states.async_set(template.entity_id, '2', {'friendly_name': 'Multi room presence', 'rooms': [area.name]})
    assert template.entity_id in {v['value'] for v in CompactOptionsMixin._room_source_options(hass)}
    assert 'rooms' in {v['value'] for v in CompactOptionsMixin._room_attribute_options(hass, template.entity_id)}
    assert configured_rooms(hass, template.entity_id, 'rooms', {area.id})[0] == {area.id}
    assert label(hass, template.entity_id) == 'Multi room presence (2)'
    hass.states.async_set(template.entity_id, '', {'friendly_name': 'Multi room presence'})
    assert template.entity_id in {v['value'] for v in CompactOptionsMixin._room_source_options(hass)}
    assert configured_rooms(hass, template.entity_id, '', {area.id})[0] == set()
    assert label(hass, template.entity_id) == 'Multi room presence'
    hass.states.async_set(template.entity_id, 'unavailable')
    assert template.entity_id in {v['value'] for v in CompactOptionsMixin._room_source_options(hass)}
    assert configured_rooms(hass, template.entity_id, '', {area.id})[0] is None
    # All operations above edit local HA configuration and registry metadata only.
    # No native climate service is registered or invoked by this isolated test.
    assert not hass.services.has_service('climate', 'set_temperature')
    await runtime.async_stop()
    await hass.async_block_till_done()
    await hass.async_stop(force=True)
    print('Actual HA read-only options, sleep/PMV switches, per-device methods, template selectors and labels: PASS')


if __name__ == '__main__':
    with TemporaryDirectory(prefix='hem-beta15-settings-') as directory:
        asyncio.run(check(directory))
