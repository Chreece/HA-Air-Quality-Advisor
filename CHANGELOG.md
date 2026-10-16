# Changelog

## 0.1.4 — editable window sensor exclusions

- Add an **Exclude window entities** multi-select before area selection in the initial configuration wizard.
- Preselect likely virtual, thermostat-derived, detection-only, diagnostic or configuration window-class binary sensors; do not assume device class alone proves a physical window.
- Allow users to add and remove exclusions, including saving an explicitly empty exclusion list, without heuristics silently reselecting options when reconfiguring.
- Exclude selected contacts consistently from suggested areas, actual window status, close/open recommendations and dashboard; keep previously selected areas during reconfiguration.
- Support English, Greek, German, French and Spanish setup text and targeted regression tests.
- Keep the existing config entry, entity IDs, HACS installation and dashboard card.

## 0.1.4 — Window sensor exclusions

- Add an editable, multi-select **Window sensor exclusions** step to initial setup and reconfiguration before choosing monitored areas.
- Preselect likely virtual/auxiliary window-class binary sensors, using thermostat/TRV associations, diagnostic metadata, and window-detection descriptions. Users can uncheck any suggestion or exclude other window-class sensors.
- Honor saved choices, including an intentionally empty exclusion list, and retain temporarily missing excluded entities in configuration.
- Apply exclusions to room discovery, window counts, opening/closing recommendations, announcements, and the dashboard. Covers continue to be ignored.
- Keep existing config entries and entity IDs. Add regression tests and five setup translations.

## 0.1.3 — Dashboard card and live room overview

- Move the existing Ko-fi banner directly below the project banner on GitHub.
- Ship a responsive, standalone Air Quality Advisor Lovelace custom card inside the HACS integration.
- Register its Home Assistant static resource and card picker entry automatically at startup.
- Display all rooms (good, attention, unknown), their readings, limits and window contacts; outdoor weather, pollutants and warnings.
- Localize card UI using the Home Assistant user language, independently of announcement language.
- Keep a single existing recommendation entity and the same unique ID. Add dashboard-only structured attributes, without changing window control or announcement policy.
- Add Python snapshot tests and a Node.js frontend smoke/security test.

## 0.1.2 — room defaults and missing outdoor readings

- Preselect every discovered Window-class **binary sensor** area on first setup. Keep saved selections when editing the integration.
- Exclude **all covers**, including Window-class covers, from room/window detection and recommendations.
- Treat unknown, unavailable and stale outdoor air-quality values as neutral (not unsafe). Valid high measurements still block opening; weather and warning safety checks are unchanged.
- Expose `outdoor_data_complete` and `unavailable_outdoor_sensors` on the single recommendation entity.
- Update the setup descriptions in all five languages and add regression tests.


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
