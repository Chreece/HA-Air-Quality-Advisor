# Changelog

## 0.6.0b30 - Visible per-controller operational status (beta)

- Create a per-controller **Control status** diagnostic sensor attached to each managed physical controller device.
- Expose control method, preset, real physical source states, pending command, current demand, blocked/pause reason, and Manager-owned power.
- Distinguish a PID output currently inactive from an Automatic controller sitting inside its target deadband; no actuator or duty-cycle changes.
- Translate the diagnostic entity in all 38 supported languages, including Greek and German.
- Retain beta29 window contact behavior, room temperature/humidity profile targets, and native PID/Automatic control with all safety gates.
- Continue canonical `environment_manager` only, no migration. Stable remains v0.5.1.

## 0.6.0b29 - Optional window-contact interlock correction (beta)

- Fix false `open_or_unknown_window` holds when a monitored room has no selected/discovered window contact.
- Preserve fail-closed behavior for real open, unavailable or missing selected contacts; continue rechecking before sending native commands.
- Align primary room policy and live controller fallback so Automatic/PID equipment can start when there is verified demand and no window contact to monitor.
- Keep the canonical `environment_manager` integration with no domain migration, capability-gated Room Environment targets, and safety interlocks/dwell/ownership.
- Retain stable Latest v0.5.1.

## 0.6.0b28 - Final canonical room targets and active controllers (beta)

- Supersede intermediate beta26/beta27 payloads with the fully validated final source.
- Use only `environment_manager` for the integration domain and every persisted/runtime storage namespace.
- Keep Room Environment Comfort/Home/Away/Sleep/Eco heating, cooling and humidity targets capability-gated and editable.
- Keep Automatic/PID/Manual selection as the authorization for that exact native controller to start/stop supported physical equipment or HVAC modes on verified demand.
- Preserve observed physical OFF age and allow deliberate method reselection to re-arm a software pause.
- Keep all availability, window, dwell/runtime, ownership, defrost/interlock and acknowledgement protections.
- Publish only from the frozen `release/beta28-ready2-20261024` candidate branch.

## 0.6.0b27 - Canonical storage, room targets and active controllers (beta)

- Supersede beta26 because two native safety stores still used historical `air_quality_advisor.*` keys.
- Canonicalize every runtime/config-flow/service/storage namespace to `environment_manager`; no old-domain migration code ships.
- Preserve Room Environment Comfort/Home/Away/Sleep/Eco heating, cooling and humidity targets.
- Preserve active Automatic/PID/Manual behavior: method selection alone authorizes the exact native controller to start/stop supported physical equipment or HVAC modes on verified demand.
- Preserve observed physical OFF age across method selection and allow explicit method reselection to re-arm a prior software pause.
- Keep minimum ON/OFF, maximum runtime, window, availability, ownership, defrost/interlock and acknowledgement protections.

## 0.6.0b26 - Room profile targets and active controller methods (beta)

- Remove historical-domain migration completely; `environment_manager` is the sole runtime/config-flow/storage domain.
- Add Room Environment targets for Comfort, Home, Away, Sleep and Eco with capability-gated heating, cooling and humidity controls.
- Keep room targets editable even while automation is Off; selecting equipment is enough to define room policy.
- Make Away use its explicit room profile targets instead of silently substituting room min/max limits.
- Selecting Automatic, PID or Manual authorizes that exact native controller to start/stop supported physical equipment/native HVAC modes when verified demand requires it.
- Clear a prior software pause when the user deliberately selects an active control method again.
- Preserve the physical entity's observed OFF age so selecting PID/Automatic does not create an artificial fresh minimum-OFF dwell.
- Keep physical availability, windows, identity/ownership, dwell/runtime, defrost, interlock and acknowledgement safety gates.

## 0.6.0b25 - Single canonical environment_manager integration (beta)

- Register only the canonical `environment_manager` Home Assistant domain, services and frontend path.
- Remove runtime compatibility aliases for `air_quality_advisor`, beta20 `enviroment_manager` and `home_environment_manager`; retain historical strings only as migration inputs.
- Move verified leftover legacy integration folders out of `custom_components` into `.environment_manager_legacy_components` backups and refresh HA's custom-component cache.
- Preserve the exact config-entry ID, subentries, entity/device identity, user customizations and stored settings during one-time migration.
- Keep beta24's flat HACS tag payload so the release itself contains only one installable integration.
- Update current documentation and actions to `environment_manager.*` only.

## 0.6.0b24 - Flat HACS tag payload (beta)

- Stop using HACS `zip_release` after the release-asset path still failed in the domain-switch upgrade.
- Publish the beta tag itself as a flattened `environment_manager` integration with `manifest.json`, `__init__.py`, platforms, translations, frontend and brand files at tag root.
- Keep `content_in_root: true` so a cached `custom_components/air_quality_advisor` remote path is replaced by the canonical root manifest/domain.
- Use HACS's normal GitHub tag-archive extraction path, which strips the internal `tags/` prefix before downloading.
- Simulate the cached-old-domain HACS extraction against the exact flattened payload before publishing.
- Preserve beta22's exact config-entry-ID migration and all controller/safety behavior.

## 0.6.0b23 - HACS domain-switch installation fix (beta)

- Fix HACS upgrades that still cache `custom_components/air_quality_advisor` and therefore fail to find beta22's canonical manifest.
- Use HACS `content_in_root` + `zip_release` with `environment_manager.zip` and a root discovery manifest for the canonical `environment_manager` domain.
- Package integration contents at ZIP root so HACS extracts directly into `/config/custom_components/environment_manager` without nested `custom_components/`.
- Hide the default branch in beta23 HACS metadata to keep the historical stable branch layout out of the beta migration path.
- Add a cached-old-path regression plus root manifest/ZIP layout checks.
- Preserve beta22 exact config-entry-ID migration and all existing controller/safety behavior.

## 0.6.0b22 - Preserve exact config-entry identity during domain migration (beta)

- Migrate legacy `air_quality_advisor` and beta20 `enviroment_manager` config entries in place so the exact Home Assistant config-entry ID survives.
- Preserve room subentry IDs/objects, entity IDs and unique IDs, device IDs, custom names, disabled states, options and stored controller settings.
- Reindex only after validating the Home Assistant 2026.10 ConfigEntryItems API shape; fail closed on unsupported internals, duplicate canonical homes or unsafe transitional states.
- Keep entity/device registry associations on the same config-entry/subentry IDs while changing only platform ownership and Manager-owned identifier namespaces.
- Preserve legacy storage ancestry for direct beta19 -> beta22 and chained beta19 -> beta20 -> beta22 upgrades.
- Verify both source domains on installed Home Assistant 2026.10 and retain all beta21 controller/safety semantics.

## 0.6.0b21 - Canonical environment_manager domain repair (beta)

- Correct the beta20 `enviroment_manager` package/domain typo to canonical `environment_manager`.
- Migrate registry ownership from both `air_quality_advisor` and beta20 `enviroment_manager` while preserving entity/device IDs, subentries and user customizations.
- Preserve chained storage migration markers for beta19 -> beta20 -> beta21 and direct beta19 -> beta21 upgrades.
- Keep temporary service/card compatibility for the historical domains while making `environment_manager` authoritative.
- Preserve beta20 room-owned presets, room-wide limits, selected-room feedback and controller safety behavior.
- Validate both migration paths on installed Home Assistant 2026.10 before publishing.

## 0.6.0b19 - environment_manager domain migration and room-owned presets (beta)

- Rename the canonical custom-integration package/domain to `environment_manager`; keep legacy service/card aliases for existing automations and dashboards.
- Add one-click migration from the immutable `air_quality_advisor` config-entry domain, preserving data/options/subentries and entity/device registry identities before retiring the old entry.
- Import legacy equipment/environment/PID/fan/humidity safety stores into the new-domain entry on first use.
- Define automatic room semantics: Comfort = verified occupied, Home = someone home but room unoccupied/unknown, Away = verified nobody home, Sleep = sleeping room; Eco is explicit-only.
- Put Comfort/Home/Sleep/Eco heat/cool setpoints on the Room Environment device. Away uses the room minimum/maximum temperature bounds and has no duplicate setpoint entities.
- Migrate beta18 Home → Comfort and Unoccupied → Home bands conservatively.
- Selecting Automatic/PID on exact native climate/fan/humidifier grants that controller power/mode consent so it can start/stop on verified demand; existing manual-running equipment is not seized and raw outputs retain separate commissioning.
- Preserve availability-first calculations, room sensor precedence, ownership/acknowledgement, dwell/runtime/interlock protections and stable v0.5.1.

## 0.6.0b18 - Room Environment limits and room feedback precedence (beta)

- Move temperature/humidity/fan percentage min/max controls from physical controllers to the Room Environment device.
- Derive editable room ranges from the common native range of selected available physical devices and apply the room limits to every compatible managed controller.
- Preserve stricter device-native ranges at command time and conservatively migrate beta17 per-device limit values into room defaults.
- Remove obsolete beta17 per-device limit registry entities without deleting their saved migration values.
- Make explicitly selected room temperature/humidity/air-quality sources authoritative controller feedback; average multiple selected room sensors when valid.
- Prevent climate-device built-in measurements from overriding explicit room sensor selection.
- Preserve per-device quiet/presence controls, availability-first execution, ownership/interlocks and stable v0.5.1.

## 0.6.0b17 - Per-device quiet, occupancy, limits and availability gating (beta)

- Add per-controller Quiet when in room / Quiet when sleeping switches for devices with adjustable native fan support.
- Use a native quiet/low mode or percentage, clamped to controller fan bounds; unknown presence/sleep holds the current fan speed and quiet logic never powers a device on by itself.
- Give every managed controller one Always / Room occupied / Room absent control-availability selector; conditional control requires verified room evidence.
- Add capability-specific temperature, humidity and percentage-fan min/max limits on the managed device and clamp every Manager-issued target/output to them and the physical native range.
- Gate runtime control before capabilities, occupancy, target, measurement or PID calculations until every selected physical endpoint is available.
- Preserve legacy room/home driver behavior while conservatively mapping old managed-controller values to Room occupied.
- Preserve command ownership, acknowledgement, dwell/interlock protections, rooms-first setup and stable v0.5.1.

## 0.6.0b16 - General sources, Home hub, Task AI, TTS languages and away cooldown (beta)

- Preselect discovered weather, outdoor air-quality and pollen sources on first General setup while preserving later explicit empty selections.
- Show Announcement Hub enablement only when configured; retain Hub-owned routing and recovery semantics.
- Add data-capable Task AI entities beside conversation agents and send direct Task AI rewrites through `ai_task.generate_data`.
- Build TTS language choices from the selected provider's real capabilities with readable names and conditional region labels.
- Place global settings, inputs, outputs and recommendation diagnostics on a native Home group/device; preserve existing Home/room/controller identities.
- Treat fresh empty occupied-room evidence as nobody home only after a configurable Home away cooldown; unknown/stale evidence stays unknown.
- Preserve rooms-first configuration, controller safety/ownership gates, all 38 localized catalogs and stable v0.5.1.

## 0.6.0b15 - Direct device methods, settings writes and template selectors (beta)

- Authorize exact native controller sources by explicit method selection; remove hidden Configure prerequisites without enabling old room drivers.
- Add device-page power/mode permission, timing, presence/sleep and applicable fan-purpose/verification controls.
- Make all shared configuration writers handle read-only mappings without pickle/deepcopy failures.
- Allow Sleep/ISO PMV preferences to save; expose scoped scientific input selectors and retain incomplete-data diagnostics.
- Include empty/unavailable room-list template sources with state/attribute choices and conservative runtime parsing.
- Use Device name - Entity name (state) captions and omit empty components.
- Guard source/identity changes, removal/reselection, post-await approval changes and competing configuration entries.
- Preserve the rooms-first flow, room hubs, stable v0.5.1 and prior tags.

## 0.6.0b14 — Rooms-first setup and explicit input lists (beta)

- Replace the public initial/options menu with rooms → per-room six-category multi-selects → general settings → finish.
- Label inputs by physical device and entity; filter by real room/type and exclude generated controllers.
- Apply positive source selection to monitoring, temperature/humidity feedback, windows and pressure diagnostics.
- Preserve empty selections, invalid-source visibility, device identities, calibration/tuning and unrelated concurrent settings.
- Withdraw affected automatic grants when feedback sources or rooms are removed; never authorize new devices implicitly.
- Supply all 38 localized setup catalogs and regression/actual-HA selector checks.

## 0.6.0b13 — Single per-room climate-device picker (beta)

- Replace duplicate Climate/PID/device menus with one physical-device picker.
- Save selection directly; optional sensor and hardware commissioning stays in the same path.
- Keep operating controls on managed devices and room-wide controls on the room hub.
- Preserve unavailable selected equipment and revoke deselected legacy PID assignments.
- Prevent inherited/stale automation grants for newly selected endpoints; preserve tuning and other rooms.
- Translate the new setup guidance in all 38 languages, including Greek.

## 0.6.0b12 — Native room groups and service-classification correction (beta)

- Replace service classification with ordinary Home/Area/controller devices and a hub integration. Explicitly migrate persisted beta 11 flags.
- Group each area using a native configuration subentry containing room settings and one managed controller device per selected physical product.
- Preserve registry IDs, custom names, disabled flags and native equipment; pass matching subentry IDs through every entity platform.
- Keep selected devices visible independently of automatic-control grants. Add/remove room groups without implicit hardware authorization.
- Cover migrations, reloads, multiple physical products, room lifecycle and localized setup in all 38 languages.

## 0.6.0b11 — Area hubs, per-device climates, on/off PID and quiet control (beta)

- Complete Home → Area hub → managed-controller hierarchy, retaining physical source devices and original Home/Area entity IDs.
- Add per-endpoint climate entities with real room data, actual HVAC/fan/swing capabilities and None/Home/Comfort/Away/Sleep/Eco presets; support independent channels on one physical device.
- Add Existing/Automatic/Manual/Off/PID control selection, editable gains/cycle settings and deterministic ownership transfer from old controllers.
- Support slow time-proportioned PID for qualified binary fans, humidity devices, native climate modes and direct actuators, with original dwell and maximum-runtime safeguards.
- Add capability-aware quiet-on-sleep and quiet-while-occupied controls with real native speed reduction/restoration and no implicit power-on.
- Persist exact command intent before dispatch; recheck identity, feedback, permissions and interlocks after awaits; latch manual/uncertain/restart pauses and safely retire removed equipment.
- Reject Manager climate entities as physical inputs; keep manual targets independent of occupancy and preserve surviving DRY/FAN-only commissioning when unrelated devices are removed.
- Localize new controls in all 38 languages and extend regression, generator, frontend and distribution checks. New per-device ownership remains opt-in; stable v0.5.1 and previous beta tags are unchanged.


## 0.6.0b10 — Source-only setup and Area/Home device operating controls (beta)

- Limit configuration menus to monitored areas, sensor/provider/equipment entity selection, and hardware-specific commissioning. Move global and room operating preferences to the Home and Area devices.
- Add editable Area sleep start/end Time entities, pollen and AQI settings, room comfort, policy and calibrated science values without duplicating native climate/humidity/fan controls.
- Add measured coldest-surface room Number and explicit **Recalculate mold factor** Button with fresh same-room temperature, outdoor weather and physically plausible calibration guards; invalidate prior factor after changing input.
- Offer guarded commissioned direct PID gains and demand/rate settings while retaining supervisor PID manual/defaults and existing physical interlocks.
- Correct a generator that forced English mold outdoor-source labels/help back into 33 locales; regenerate all 38 translations and add regression checks.
- Keep the `air_quality_advisor` domain and earlier entities stable. Stable v0.5.1 and earlier beta tags remain untouched; no new actuator permission is granted.


## 0.6.0b9 — Home and Area device-first configuration (beta)

- Attach all room devices under the existing Home Environment Manager device, reusing the unchanged whole-home recommendations/dashboard sensor.
- Add editable home-wide thresholds, language, announcement/AI switches and repeat interval, while keeping safety-related selectors in options.
- Expose per-area manual PID gains and supervised setpoint limits, with safe gain-source defaults/manual selection and integrator reset between writes; no blind auto-tuning.
- Expose distinct per-room comfort policy bands and occupancy profile controls without copying original thermostat/fan controls.
- Add registry-resolved home and room edit buttons on the dashboard, with Greek/German/French/Spanish labels and no guessed device IDs.
- Regenerate all 38 language catalogs and protect writes, device identity and navigation in regression tests.

## 0.6.0b8 — Controller and menu regression audit (beta)

- Revoke stale per-device actuator grants; block deselected thermostat absence OFF, verify actual native equipment target capabilities and power timing.
- Make fan purpose switches exclusive and promote replacement thermostats to primary without bypassing ownership safeguards.
- Fix filtration speed target field, excluded control sources, occupancy source clearing and AQI scale editor persistence.
- Test per-device revocation, room identity, HVAC mode support, hardware confirmation, sensor quality, safe dwell times and versioned beta distribution.

## 0.6.0b5 — Complete config-flow translation and field-help audit (beta)

- Audit all Home Assistant initial setup and options forms across 38 languages, detecting inherited English text and generic placeholder descriptions even when translation keys are technically complete.
- Provide dedicated explanatory text for every advanced threshold, supported climate device/actuator, PID parameter, humidity/ventilation control, home/room/sleep presence rule and specialist environmental input.
- Add a final generator pass so future releases cannot undo these translations, with locale-specific explanations, preserved units and original Home Assistant keys.
- Ensure every visible field has a nonempty help description, including the 22 advanced limits that previously had none; add regression tests preventing English fallback and stale generated JSON.
- Do not change actuator authorization, safety interlocks, hardware commissioning status, existing entity IDs or stable release behavior.

## 0.6.0b4 — Initial setup retry and existing-entry protection (beta)

- Avoid reserving the static `home` config-flow unique ID before the first setup form, so a frontend-abandoned initial flow cannot block every fresh attempt with `already_in_progress`.
- Recheck both the unique ID and legacy existing entries immediately before saving, including installs without a stored unique ID. Two simultaneous attempts cannot intentionally create duplicate entries.
- Add simulated regression tests for an abandoned original setup flow, retry, final ID assignment and an entry created while another flow was open.
- Document recovery from already-in-progress installation attempts; existing HACS users should use Configure, not Add integration, after upgrading.
- Keep hardware-control safety, translations, entity IDs and stable v0.5.1 untouched.

## 0.6.0b3 — Contextual measurement explanations and validated room-source selectors (beta)

- Add accessible info popovers for all room primary metrics and derived scientific measurements, explaining what each means, potential risks and benefits, and only configured limits when present.
- Restrict shared occupancy and sleep source selectors to actual parseable Home Assistant room lists; refresh the attribute choices after selecting a source and offer State as a choice when valid.
- Explain that source age in minutes is a freshness limit, not minimum sleep duration, and ensure stale/unknown data cannot authorize equipment shutdown.
- Expand Greek and international advanced per-room labels and explanations; regenerate all 38 locales.
- Preserve the original domain, IDs, storage, opt-in protection, HACS install and v0.5.1 stable release.

## 0.6.0b2 — Compact settings and evidence-qualified device occupancy (beta)

- Reorganize 11 flat settings into **Outside data**, **General settings**, **Area settings**, Announcements and Advanced thresholds; move international pollen/AQI into Outside data and window exclusions into Area settings.
- Replace dynamic AQI/pollen options with isolated, validated provider controls. Fix a crash-prone menu involving dynamically numbered selectors.
- Add global room presence sensor selection, an occupied-room source (state or named attribute), home trackers and a sleep-room source. Only fresh recognized HA area IDs/names count as reliable negative occupancy evidence.
- Auto-select compatible room climate/humidifier/fan entities for inventory only, with a separate per-device configuration page for opt-in automation, setpoint targets, occupancy prerequisites, safe absence actions and sleep behavior.
- Hold commands on unknown occupancy, conflicting device assignments, manual intervention or incomplete hardware protections; verified native HEAT/COOL OFF uses durable command intent and never automatically restarts equipment.
- Generate compact option titles, field labels, selector choices and contextual guidance across all 38 supported languages, with fuller Greek/German/English explanations. Existing v0.6.0b1 prerelease and v0.5.1 stable release remain untouched.

## 0.6.0b1 — v0.6 public beta 1 (opt-in, October 20, 2026)

- Add room-specific comfort and away profiles, occupancy debounce, local-time sleeping schedules and explicit device/control configuration.
- Implement guarded native heat/cool selection, native low/high temperature range support, and direct non-compressor relay, PWM and percentage-based output drivers, each with independent equipment constraints.
- Implement optional ISO 7730 PMV-target inversion using measured radiant temperature, humidity, air speed and configured clothing/activity inputs; never invent missing data.
- Enforce room-level ownership, temperature sensor freshness, mode-change dwell, manual-override pause, output acknowledgement, maximum-on watchdog, interlocks and restart handling.
- Persist direct actuator ON intentions *before* Home Assistant service dispatch; block interrupted writes until verified physical OFF and full minimum-OFF dwell, preserve unknown future safety history, revalidate grants after storage I/O, and retire formerly owned outputs when a room or actuator assignment changes.
- Expand Home Assistant configuration, tests, translations, documentation and rendered Lovelace-card examples. Remains unreleased pending end-to-end device validation.

- Add a HACS-selectable GitHub prerelease with a pinned beta manifest, manual ZIP asset, verified native light/dark brand images and service/state icons. Stable v0.5.1 remains the latest production release.
- Explicit beta hardware-commissioning warning and read-only device diagnostics. Automatic compressor-affecting and other experimental power controls are disabled by default and are NOT field-certified.

## 0.5.1 — Python 3.14 / Alpine dependency compatibility

- Remove the mandatory `pythermalcomfort` runtime package and its Numba/LLVM transitive dependencies.
- Keep self-contained ISO 7730 PMV/PPD scientific estimates tested against published reference values.
- Fix Home Assistant installation on Alpine Python 3.14 while retaining the climate controller, monitoring and compatibility safeguards.


## 0.5.0 — Opt-in bounded climate PID control

- Add per-room PID setpoint control for explicit `climate.*` entities with separate heat/cool tuning and strict safe operating bounds.
- Use integral anti-windup, filtered derivative on measured temperature, minimum sampling interval, maximum setpoint trim and maximum target change per control cycle.
- Keep the actual thermostat's HVAC modes and compressor-cycle protection: no mode switching, on/off calls or service broadcasts.
- Persist manual override pauses across restarts. Offer explicit `home_environment_manager.pid_control` pause/resume/reset actions and room-card controls.
- Block control for stale sensors, open/unknown windows, unsupported HVAC presets, missing units or climate service, wrong-area devices and duplicate room assignments.
- Add optional two-page room/device configuration, translations, mock climate actions and pure PID mathematical regression tests.
- Preserve the v0.4.0 international research methods, environmental monitoring, existing HACS domain and entity IDs.

## 0.4.0 — Home Environment Manager: international science and future climate-control identity

- Rebrand the public integration, dashboard, configuration and documentation as **Home Environment Manager**; preserve the existing Home Assistant domain, entity unique IDs, service and HACS repository for seamless upgrades. Expose a new Lovelace card alias while retaining the original one.
- Add explicitly identified international AQI providers, optional pollen policy, additional pollutant screening, ventilation learning, nominal particle CADR effectiveness and optional extraction suggestions.
- Introduce opt-in, hardware-verified monitoring of long-term radon, formaldehyde, calibrated acoustic exposure, daylight, measured melanopic EDI and ISO 7730 PMV/PPD with pinned Python dependency.
- Provide qualified overheating degree-hours, night acoustics and descriptive indoor/outdoor particle ratios; carefully distinguish engineering indicators from health or regulatory compliance.
- Separate optional global and per-room settings into clear guided forms. Rebrand and regenerate international translations, visual documentation, Lovelace screenshots and architecture artwork.
- **Climate-device PID control is a future release**, not enabled or advertised as operating in v0.4.0.


## 0.3.0 — Research-grounded building physics and time-dependent air-quality context

- Derive room-level humidity ratio, absolute humidity, dew point and real indoor/outdoor drying potential instead of inferring moisture exchange from relative humidity alone.
- Compute informational adaptive comfort bands from seven days of sufficiently complete outdoor observations, and evaluate clean-air passive-cooling opportunities without assuming heating/cooling state.
- Expose estimated surface condensation margin, historical hours at high surface RH, approximate sensible heat per full air exchange, and nighttime overheating exposure; do not misrepresent estimates as ISO/CIBSE certification.
- Add time-weighted 24-hour PM2.5/PM10 measurements with 80% coverage gates, CO₂ trends and strictly conditional CO₂-decay ACH estimates.
- Reject implausible CO₂ (<250 or >20,000 ppm) and impossible RH measurements as unavailable. Never treat unknown sensing hardware as verified NDIR or estimate ACH without outdoor CO₂ and vacant/open-window evidence.
- Prevent humidity-only opening advice if measured outdoor vapor mass is higher, while retaining rain, severe-weather, existing outside-temperature and Hub routing safeguards.
- Store up to eight days of bounded local samples with source-freshness limits, restore after HA restart, and display available derived measurements on the existing card in English, German and Greek.
- Add pure calculation and mocked Home Assistant regression tests, retain existing UX, config entries, entity identifiers and ANNOUNCEMENT HUB area targeting.

## 0.2.13 — Hand room names and routing ownership entirely to Announcement Hub

- For Hub-bound announcements, send the **real Home Assistant area display name** from the recommendation snapshot, not the internal slug/area ID. Example: `output: [Küche]` rather than `output: [kouzina]`. Hub supports both and resolves room names itself.
- Forward the original recommendation through Hub's primary `text` field whenever both visual and TTS channels are enabled. For single-channel requests retain the relevant `text_notify` or `text_tts` field without enabling the other channel. Preserve explicit AI override, language, severity and optional title.
- Stop forcing `occupied_only: false` so Hub's own occupancy/area policy controls physical delivery. Advisor never selects Hub devices, forces route fallbacks or broadcasts to other rooms.
- **When Announcement Hub is running, never issue direct Home Assistant notifications, TTS, or `persistent_notification.create`** even if Hub rejects a request, has no matching output, returns no acknowledgement or times out. Hub owns its own errors and output selection. Return a truthful manual action result (`submitted: 0` plus error) when Hub did not queue the job.
- Keep the previous direct Home Assistant and persistent-notification fallback only when Hub is disabled or genuinely unavailable before attempted handoff.
- Add contract-level regression tests for renamed/Unicode room names, text fields, single-channel selection, accepted Hub jobs, route rejection, timeout and offline Hub fallback. No changes to mold indication, RH fallback, weather decisions or automatic timer behavior.


## 0.2.12 — Clarify mold sensor count and show calibration details

- Replace ambiguous `RH Ø 55% · n=2 · 🌡️ 17.1°C` text in the mold gauge with localized, readable lines: **Average humidity: 55% · 2 sensors** and **Estimated surface: 17.1°C**.
- Add a dedicated **More details** panel for the mold indicator with the **actual calibration factor** and **current indoor and outdoor temperatures** used by the estimate. The panel is available with as few as three room measurement tiles, and is hidden until expanded.
- Preserve the exact saved floating-point calibration factor in the backend dashboard data; UI display uses 2–6 fractional digits and includes the full numeric factor in the tooltip. No precision changes to the underlying Magnus/mold calculations.
- Localize the humidity average, one/multiple sensor labels, surface temperature and calibration field labels across the 38 supported UI languages, including Greek and German.
- Support partially unavailable readings by showing any existing calibration factor with a dash for a missing temperature, without inventing sensor values. No new sensors, configuration options, automation triggers or Announcement Hub changes.
- Extend backend metadata and frontend tests covering calibration precision, locale rendering, expanded/collapsed layout and rooms with three measurement cards.


## 0.2.11 — Automatic per-room RH fallback when mold indication is unavailable

- While the optional mold indicator is enabled, **use calibrated estimated surface humidity whenever it is calculable**. If not, automatically use **one averaged valid room RH measurement** as the humidity ventilation trigger; no additional configuration toggle is necessary.
- Apply the existing `indoor_humidity` threshold (default **65% RH**) only to the fallback and the independent `indoor_mold` threshold (default **70% surface RH**) only to a valid mold indicator. Switching between methods is automatic and avoids counting both measurements simultaneously.
- Ignore unavailable/stale RH sources, zero, negative, NaN and readings above 100%; honor each room's selected sensor exclusions and do not count multiple RH sources as separate threshold exceedances.
- Retain the unavailable mold reading and every specific warning. Rooms using RH fallback remain **partially verified/unknown** when mold is not calculable rather than falsely marked fully safe.
- Show localized **RH fallback active** (38 card languages), the actual averaged RH and current RH threshold in the room card, and expose structured `rh_fallback` state in the dashboard attributes. The fallback uses a visible humidity metric rather than a misleading mold percentage.
- Recognize the fallback in spoken recommendations, with natural localized cause text for the five primary speech languages. Missing calibration alone is not an announcement trigger; a valid RH average above the configured threshold can trigger the existing open-window workflow.
- Preserve unsafe-weather closure priorities and Announcement Hub routing. No new entities, system services, network calls, or setup requirements are introduced. Extend regression coverage for recovery, per-room isolation, exclusions, precision and the Lovelace UI.


## 0.2.10 — Weather source first; report every missing mold input

- Place **Weather and warnings** second in Configure, ahead of the third **Room settings — indoor air and mold** page. The initial setup wizard continues selecting weather before cold-surface calibration.
- Clarify that outdoor temperature for mold estimation comes from the configured weather entity's live `temperature` attribute, not from outdoor PM2.5/AQI sensors.
- Show a current valid weather-temperature source or a visible warning for missing outdoor temperature on the Weather configuration page; show missing-input clues on every room calibration page.
- Expose separate diagnostic codes for missing **calibration, indoor temperature, outdoor temperature, usable room RH, and calculation failures**. Warnings appear as localized lines in the dashboard and in the recommendation sensor's `mold_input_warnings` attribute, even during bad weather.
- Preserve pinned weather providers after calibration; if the original provider is removed, warn instead of silently substituting another provider. Before calibration, a working selected provider is correctly recognized as available.
- Preserve the previous sensor aggregation, 70% surface humidity threshold, no-false-safe room status, and Announcement Hub delivery. No alert spam or additional automatic announcements on a missing mold input.
- Add regression tests for missing-input combinations, different weather-source states, configuration menu order, translated setup hints, and frontend warnings.


## 0.2.9 — Fix misleading room 'No data' while mold needs calibration

- A room with working PM2.5, AQI or other indoor sensors must not show **No indoor measurements** simply because the optional mold indication is uncalibrated.
- For incomplete rooms with working air sensors, show **Partial data** in the Lovelace room status. Explain **Mold indicator not calibrated** when the manually measured coldest-surface temperature has not been saved.
- Distinguish an uncalibrated mold estimator from one whose room temperature, outside weather temperature or humidity inputs are temporarily unavailable. Include the reason in the dashboard data and show it beneath the unavailable indicator.
- Continue displaying the mean of valid room RH values and contributing sensor count while the mold estimate is unavailable.
- Preserve safety semantics: a missing required mold estimate still leaves the room classified **unknown**, not green/safe. Existing CO₂, PM, VOC, weather and window actions are unchanged.
- Add targeted Python and Lovelace frontend regression tests; localize the new mold status messages for all 38 supported card languages. Refresh the bundled JavaScript cache key.


## 0.2.8 — Restore README images in HACS

- Replace all nine repository-local image references in `README.md` with absolute `https://raw.githubusercontent.com/Chreece/HA-Air-Quality-Advisor/main/` image URLs. This fixes broken cover, Ko-fi artwork, architecture diagrams, four dashboard screenshots and illustrative previews in HACS's README renderer while preserving GitHub rendering.
- Add a regression test that requires absolute HTTPS image URLs, checks referenced local assets actually exist and prevents broken relative `src` links from returning.
- Documentation-only correction; no sensor logic, mold estimation, announcements, Home Assistant configuration or runtime services are changed.


## 0.2.7 — Optional calibrated mold indication instead of raw humidity

- Add a **Use mold indication instead of room RH** checkbox to the first Rooms configuration page. Default remains **off** for existing installations, retaining the previous room humidity threshold and all pollution/weather safeguards.
- Rename the per-room indoor sensor options page to **Room settings — indoor air and mold**, and place it second in Configure. The existing room-specific sensor exclusion picker remains available.
- In mold mode, select each room's ambient temperature sensor and enter a measured temperature in °C for the **coldest surface** (critical point), measured at the same time as the outdoor temperature. Calculate and persist Home Assistant's compatible calibration factor; an explicit recalibration option prevents inadvertent changes from later weather or sensor updates.
- Average all **nonzero, finite, fresh RH values within 0–100%** from included room sensors. Invalid, excluded and unavailable humidity readings do not contribute. Convert indoor/outdoor temperatures to Celsius before estimating surface relative humidity via dew point; expose the result as one room indicator.
- Set the default **indoor mold surface-RH warning threshold to 70%**, adjustable in Advanced thresholds. Missing sensors or calibration remain **unknown**, never silently safe, and never fall back to raw RH. Air quality and unsafe-weather decisions retain precedence.
- Show the estimated surface RH, average valid room RH, contributor count and surface temperature in the dashboard; localize mold reasons and configuration into all 38 supported languages, including detailed Greek/German calibration instructions.
- Add unit, setup, integration and frontend regression tests. No extra cloud requests, Home Assistant services, persistent sensors or Announcement Hub changes.


## 0.2.6 — Fix automatic weather/window announcements (Home Assistant event-loop safety)

- Fix `RuntimeError: ... hass.async_create_task from a thread other than the event loop` seen when automatic window warnings fired. Home Assistant dispatched the integration's undecorated timer lambdas to a SyncWorker thread instead of the event loop.
- Mark both the initial announcement timer and the repeating-reminder timer with Home Assistant's `callback()` so they run safely on the event loop.
- Add two regression cases that require event-loop callback markers for immediate `close` alerts, stable `open` alerts, and their 10-minute repeats. Existing announcement behavior remains unchanged.
- Keep Announcement Hub handoff and AI processing untouched. No setting changes, migrations, weather-entity edits, or Home Assistant restarts are performed by the integration update itself.


## 0.2.5 — Respect Announcement Hub queue acknowledgements

- When Announcement Hub is running, Air Quality Advisor submits the selected notification/TTS channels and explicit AI settings, then trusts Hub's `accepted: true` response as successful queue handoff.
- Stop interpreting empty Hub route lists as a delivery failure after the job was accepted. Prevent duplicate local notifications when Hub owns the queued job.
- Raise Advisor's **acknowledgement safety timeout** from 20 to 120 seconds because current Hub performs optional AI rewriting before returning its queue acknowledgement. This is not an AI timeout; AI, routing, retry and actual delivery remain Hub responsibilities.
- Keep native Home Assistant fallback only when Hub is unavailable, rejects the request, returns no acknowledgement or does not respond within the safety bound.
- Add direct and manager-level regression tests for queued jobs with no immediately listed outputs. No configuration migration, sensor, thresholds or window logic changes.


## 0.2.4 — Full Home Assistant configuration translation audit

- Fix Hassfest compliance for regional/script language-selector translation keys (lowercase only); saved `pt-BR`, `zh-Hans` and `zh-Hant` continue to round-trip as canonical BCP47 values.

- Audit all **38** supported languages across initial setup and Reconfigure: step titles, page explanations, per-field help, validation/abort text, seven menu choices and advanced-threshold labels.
- Fix the untranslated Greek Weather/warnings explanations shown under the weather provider and warning-entity selectors; also correct outdoor sensor and Announcements help.
- Translate all 18 advanced limit labels in Greek, German, French and Spanish; maintain the complete original English set.
- Replace English validation-error/abort fallbacks in the 33 newer languages with concise translated, action-oriented messages and explanatory symbols. No hardcoded English helper strings remain in non-English config/options pages.
- Localize **Home Assistant default** for language selection via the supported Home Assistant `SelectSelectorConfig.translation_key` mechanism and corresponding per-language `selector` dictionaries. Localize conversation-agent default labels too.
- Add a single reviewed translation overlay source applied **after** generation, preventing old English explanations returning in future releases. Add full-coverage tests to detect missing or English-regressed setup/option strings.
- Keep real weather-provider alerts, device names, geographic locations and entities untouched; those are supplied by Home Assistant/other integrations, not Air Quality Advisor.
- GitHub Actions now **automatically validates completed pushes to main and publishes new versions only after all test, HACS and Hassfest gates succeed**. Superseded commits and already published versions are skipped; the optional manual-dispatch path stays validation-only by default. Existing configuration and recommendation logic are unchanged.

## 0.2.3 — Configurable, per-room repeat reminders (unreleased milestone)

- Add **Repeat announcements (minutes)** under Announcements, with **10 minutes default** and **0 = no repeats** (0–1440 whole minutes).
- Repeat only while the *same actionable window recommendation and underlying reason* persist. Each room has its own timer; changes in one room do not cause duplicate announcements elsewhere.
- Check sensors and windows again at each reminder deadline; stop immediately when a recommendation clears or its cause changes. Changes in numeric readings while still over the same threshold do not reset the timer.
- Keep 90 seconds for initial open advice and immediate closing advice. Timed reminders bypass the older 15-minute anti-flapping cooldown; existing startup/urgent behavior is preserved.
- All delivery methods are supported: Announcement Hub, direct TTS/notify and Home Assistant persistent notifications; no additional entities or window control.
- At this milestone CI was temporarily manual-only; **v0.2.4 supersedes this policy** with automatic post-push validation and publication. All release gates remain required.
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
