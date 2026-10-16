# Changelog

## 0.1.2 — preselected areas and incomplete outdoor readings

- Preselect all discovered rooms with Window-class **binary sensors** during initial setup; keep saved area selections during reconfiguration.
- Exclude all covers, including covers of device class Window, from area suggestions, window counts and recommendations.
- Ignore unknown, unavailable and stale outdoor air-quality readings as hazards; known high readings still block opening.
- Keep blocking behavior for missing weather, active warnings and unknown warning status.
- Add `outdoor_data_complete` and `unavailable_outdoor_sensors` attributes to the single recommendation sensor.
- Refresh all five setup languages, documentation and regression tests.

## 0.1.1 — setup and integration visibility

- Suggest only actual Home Assistant areas containing Window-class binary sensors or covers, showing the number of detected windows per area.
- Preserve already selected areas without currently detected windows (marked ⚠) when editing options, instead of silently deleting them.
- Validate submitted area choices, with actionable guidance when no windows have been discovered.
- Classify the integration as a `service` rather than `helper` so Home Assistant lists it in **Devices & services → Integrations** instead of Helpers.
- Keep the existing single sensor and config entry identifiers; no re-pairing or deleting the integration is needed. Restart Home Assistant to reload the changed manifest.


## 0.1.0 — initial testable release

- Added one area-aware window recommendation sensor (`open`, `close`, `idle`, `blocked`) with window IDs, reasons, and diagnostics.
- Added multi-step Home Assistant UI setup for areas, compatible outdoor air sensors, weather and warning entities, optional delivery, and configurable thresholds.
- Added event-driven re-evaluation and cautious policies for missing outdoor data, rain, storms, severe weather warnings and opened windows.
- Added optional Announcement Hub or direct Home Assistant notify/TTS delivery, including five translation languages and per-action language overrides.
- Added HACS metadata, locally bundled Home Assistant branding, validation workflows and sample diagrams.

**Validation:** Pure Python tests and static checks pass locally; Home Assistant, HACS and Hassfest live validation are still required.
