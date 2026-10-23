"""Add an HA area group without granting equipment-control permissions."""
from __future__ import annotations

from .config_data import mutable_copy as deepcopy

import probatio
from homeassistant.config_entries import ConfigSubentryFlow
from homeassistant.helpers import area_registry as ar, selector

from .const import CONF_AREAS
from .room_hubs import ROOM_TYPE


class RoomHubFlow(ConfigSubentryFlow):
    """Room membership is configured here; operating controls live on devices."""

    async def async_step_user(self, user_input=None):
        entry = self._get_entry()
        registry = ar.async_get(self.hass)
        assigned = {sub.data.get("area_id") for sub in entry.subentries.values()
                    if sub.subentry_type == ROOM_TYPE}
        choices = [{"value": area.id, "label": area.name}
                   for area in registry.areas.values() if area.id not in assigned]
        if not choices:
            return self.async_abort(reason="already_configured")
        errors = {}
        if user_input is not None:
            area_id = user_input.get("area_id")
            if area_id not in {item["value"] for item in choices}:
                errors["base"] = "invalid_area"
            else:
                area = registry.async_get_area(area_id)
                options = deepcopy(dict(entry.options))
                selected = {**entry.data, **entry.options}.get(CONF_AREAS, [])
                options[CONF_AREAS] = list(dict.fromkeys([*selected, area_id]))
                # One synchronous edit, no hardware selection/enablement. The
                # subentry change dispatcher schedules the normal parent reload.
                self.hass.config_entries.async_update_entry(entry, options=options)
                # A loaded entry observes additions through the dispatcher. A
                # failed/unloaded entry has no observer; retry after flow finish.
                # Disabled entries stay disabled and load their group next time.
                if (not getattr(getattr(entry, "runtime_data", None), "_active", False)
                        and not getattr(entry, "disabled_by", None)):
                    self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_create_entry(title=area.name,
                    data={"area_id": area_id, "area_name": area.name},
                    unique_id=f"area:{area_id}")
        return self.async_show_form(step_id="user", errors=errors,
            data_schema=probatio.Schema({probatio.Required("area_id"):
                selector.SelectSelector(selector.SelectSelectorConfig(
                    options=choices, multiple=False, custom_value=False,
                    mode=selector.SelectSelectorMode.DROPDOWN))}))
