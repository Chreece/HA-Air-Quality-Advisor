# Changelog

## 0.2.3 — Configurable, per-room repeat reminders and manual-only CI

- Add **Repeat announcements (minutes)** under Announcements, with **10 minutes default** and **0 = no repeats** (0–1440 whole minutes).
- Repeat only while the *same actionable window recommendation and underlying reason* persist. Each room has its own timer; changes in one room do not cause duplicate announcements elsewhere.
- Check sensors and windows again at each reminder deadline; stop immediately when a recommendation clears or its cause changes. Changes in numeric readings while still over the same threshold do not reset the timer.
- Keep 90 seconds for initial open advice and immediate closing advice. Timed reminders bypass the older 15-minute anti-flapping cooldown; existing startup/urgent behavior is preserved.
- All delivery methods are supported: Announcement Hub, direct TTS/notify and Home Assistant persistent notifications; no additional entities or window control.
- **GitHub Actions only runs via `workflow_dispatch` after all files are pushed.** An explicit, default-off **Publish release** input gates versioned releases after tests, translation generation, HACS and Hassfest. No push, PR, tag or release-request triggers.
- Update all 38 Home Assistant translations, release documentation, and recurrence/cancellation tests. No configuration migration is required.

## 0.2.2 — Shared AI control, smarter Hub availability and native fallback

- Use **one AI checkbox** for both delivery paths, preserving the existing `ai_rewrite_announcements` and `ai_conversation_agent` settings without migration.
- When Announcement Hub is selected, pass explicit `use_ai: true/false` and a custom `ai_agent` when configured; skip local rewriting for accepted Hub jobs.
- Show the **Use Announcement Hub** setting only when Home Assistant has a real Announcement Hub config entry; distinguish installed from currently running.
- Await Hub's queue acknowledgement. Fall back on absent/stopped Hub, rejected calls, timeouts or no eligible Hub outputs.
- Prefer configured direct Home Assistant notifications/TTS, with `persistent_notification.create` as the final visual fallback; don't silently lose announcements if no outputs are configured.
- On fallback, use the same AI checkbox for direct conversation rewriting when an agent is available. Preserve deterministic window decisions, room targeting and existing alert timing.
- Update all 38 translation files and add tests for Hub detection, AI routing and system fallback. No changes to entity IDs, thresholds or dashboard.

## 0.2.1 — Optional AI-rewritten direct announcements

- Add an opt-in **Rewrite direct announcements with AI** checkbox and a Home Assistant conversation-agent dropdown, with **Home Assistant default** preselected.
- Use the built-in `conversation.process` service only for direct TTS/notifications when Announcement Hub is not selected.
- Rewrite one actionable recommendation at a time with localized instructions for more natural and varied text; preserve the window action, area, window names and numeric reasons.
- Reject malformed, unverifiable, altered or action-related AI responses. Fall back to the original message on AI errors, missing agents or an eight-second timeout (three seconds for urgent closing advice).
- Never allow AI to change the underlying window decision, sensor thresholds, room targeting or Announcement Hub delivery. No extra notifications or changes to alert detection; AI rewriting may add up to three/eight seconds before delivery.
- Add all 38 UI translations, safeguards and regression tests. Existing integrations and stored configurations work without migration.

## 0.2.0 — Expanded language support

- Add 33 languages for a total of 38 Home Assistant language choices, while preserving the existing five detailed translations.
- Localize setup and Reconfigure labels, card status/readouts and actionable recommendation messages.
- Normalize regional and script variants (Brazil/Portugal Portuguese, Simplified/Traditional Chinese), and enable RTL dashboard layouts for Arabic, Hebrew, Persian and Urdu.
- Extend language override choices for manual notifications and TTS; voice availability still depends on the TTS engine.
- Ship generated HA translation files, comprehensive locale/placeholder tests and JavaScript card smoke tests.
- Keep existing entity IDs, rooms, settings and HACS installation untouched.

> **First public HACS release:** [v0.1.8](https://github.com/Chreece/HA-Air-Quality-Advisor/releases/tag/v0.1.8) (2026-10-16). Earlier v0.1.x entries document development milestones on `main`, not previous published GitHub Releases.

## v0.1.8 — First versioned HACS release (2026-10-16)

- Publish the integration, bundled Lovelace card, localization, brand assets and complete configuration UI as a selectable HACS release.
- Rooms-first setup and reconfiguration; editable contact/indoor measurement exclusions, outdoor/weather safeguards and optional announcements.
- Package a manual-install ZIP and full [release notes](.github/releases/v0.1.8.md).
- Gate publication on Python, JavaScript, HACS Action and Home Assistant Hassfest checks.

### Included development milestones

## 0.1.8 — rooms first throughout setup

- Show **Rooms** as the first page during initial installation, matching the existing Rooms-first Configure menu.
- Keep preselection of areas with Window-class binary sensors; never count covers as window contacts.
- Move editable window exclusions to the next initial setup step, ahead of per-room indoor air-quality sensor exclusions.
- Validate exclusions against selected areas: ask for a room review when contacts disappear from some areas, and block selections which exclude every usable contact.
- Localize the new Rooms-first wording and recovery errors in English, German, Greek, French and Spanish.
- Update current UI and wizard tests; keep unrelated settings, unique IDs and dashboard behavior unchanged.

## 0.1.7 — rooms first in Configure

- Put **Rooms** at the top of the seven-section Reconfigure menu, followed by window sensor exclusions and the remaining options.
- Retain window sensor exclusions before room discovery in initial setup; this is only a menu ordering change.
- Keep the menu order aligned across English, Greek, German, French and Spanish translations and tests.

## 0.1.6 — targeted and localized reconfiguration

- Remove the optional advanced-threshold checkbox from initial setup and the Announcements page.
- Restore the seven-section Configure menu: Window exclusions, Rooms, Per-room indoor sensors, Outdoor sensors, Weather/warnings, Announcements and Advanced thresholds.
- Edit and save only the chosen section, preserving all other existing settings. Indoor exclusion editing remains room-by-room.
- Keep the original first-time guided wizard and same HA entity IDs.
- Localize the menu into English, Greek, German, French and Spanish, and update tests and documentation.

## 0.1.5 — full reconfiguration and per-room indoor sensor exclusions

- Configure now starts the complete setup wizard again: window-contact exclusions, room selection, per-room indoor air exclusions, outside sensors, weather and announcements.
- After area selection, present one supported indoor-sensor multi-select per room, with device name, entity name, measurement and entity ID. Support humidity, CO₂, AQI, PM2.5, PM10 and both VOC metrics; omit unsupported units.
- Existing per-room exclusions are preselected during reconfiguration; an empty selection intentionally restores all supported sensors, and missing previously excluded sensors remain removable.
- Apply per-room exclusions to both decision logic and the visual dashboard; do not disable or alter the original Home Assistant entities.
- Allow advanced threshold editing from an optional checkbox on the final announcement page without losing saved values.
- Update English, German, Greek, French and Spanish setup/option translations and add comprehensive wizard, device-registry and recommendation regression tests.
- Preserve the same integration instance, entity unique ID, HACS layout and Lovelace card.

## 0.1.4 — editable window sensor exclusions

- Add an **Exclude window entities** multi-select before area selection in the initial configuration wizard.
- Preselect likely virtual, thermostat-derived, detection-only, diagnostic or configuration window-class binary sensors; do not assume device class alone proves a physical window.
- Allow users to add and remove exclusions, including saving an explicitly empty exclusion list, without heuristics silently reselecting options when reconfiguring.
- Exclude selected contacts consistently from suggested areas, actual window status, close/open recommendations and dashboard; keep previously selected areas during reconfiguration.
- Support English, Greek, German, French and Spanish setup text and targeted regression tests.
- Keep the existing config entry, entity IDs, HACS installation and dashboard card.

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

**Verification:** The release is gated by Python and JavaScript tests, HACS Action and Hassfest. A full live Home Assistant and physical notification-output test remains separate.
