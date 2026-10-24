"""Shared push updates for logical managed-device entities."""
from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, SIGNAL_UPDATED
from . import equipment_model as model
from .equipment_text import DEVICE_HELP


class EquipmentEntity:
    """Mixin: all entities attach to the existing Area-hub child device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def _equipment_init(self, manager, spec, key):
        self._manager, self._spec, self._key = manager, spec, key
        self._attr_unique_id = f"{spec.identifier}_{key}"
        self._attr_translation_key = f"equipment_{key}"
        # Home Assistant ordinarily prepends a device name to friendly_name
        # when has_entity_name=True. Disable that ONLY for PID parameters so
        # the real displayed friendly name begins with the translated "PID".
        # The device association and unique ID remain exactly unchanged.
        if key in ("kp", "ki", "kd", "sample_seconds", "cycle_seconds") or key.startswith("pid_"):
            self._attr_has_entity_name = False
        self._attr_device_info = {"identifiers": {(DOMAIN, model.device_identifier(spec))}}
        self._attr_translation_placeholders = {
            "channel": f"{spec.name} · " if isinstance(spec, model.ManagedEndpoint) else ""
        }

    @property
    def controller_settings(self):
        return model.settings(self._manager, self._spec)

    @property
    def extra_state_attributes(self):
        locale = self._manager.settings.get("language", "auto")
        if locale == "auto":
            locale = getattr(getattr(self._manager.hass, "config", None), "language", "en")
        locale = str(locale).replace("_", "-").casefold()
        language = next((key for key in DEVICE_HELP if key.casefold() == locale), locale.split("-")[0])
        return {"area_id": self._spec.area_id,
                "source_device_id": self._spec.source_device_id,
                "source_entity_ids": list(self._spec.source_entities),
                "controller_status": self._manager.equipment.statuses.get(self._spec.identifier, {}),
                "configuration_help": DEVICE_HELP.get(language, DEVICE_HELP["en"])}

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(
            self.hass, f"{SIGNAL_UPDATED}_{self._manager.entry.entry_id}", self._equipment_update))

    def _watch_native_updates(self) -> None:
        """Refresh physical facades/quiet controls only when their source changes.

        Stored controller preferences are independent of physical availability,
        while available native options and physical HVAC truth are dynamic.
        Subscribe only to this controller's exact physical inputs, never to the
        generated Manager entities, to avoid dispatcher/event feedback loops.
        """
        from homeassistant.const import EVENT_STATE_CHANGED

        selected = frozenset(self._spec.source_entities)

        @callback
        def source_changed(event):
            if event.data.get("entity_id") not in selected:
                return
            old, new = event.data.get("old_state"), event.data.get("new_state")
            if (old is not None and new is not None
                    and old.state == new.state
                    and old.attributes == new.attributes):
                return
            self.async_write_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_STATE_CHANGED, source_changed)
        )

    @callback
    def _equipment_update(self):
        self.async_write_ha_state()
