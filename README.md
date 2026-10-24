<p align="center">
  <img src="https://raw.githubusercontent.com/Chreece/HA-Home-Environment-Manager/main/.github/assets/home-environment-manager-banner.svg" alt="Home Environment Manager — room-aware ventilation recommendations for Home Assistant" width="100%">
</p>

<p align="center">
  <a href="https://ko-fi.com/chreece"><img src="https://raw.githubusercontent.com/Chreece/HA-Home-Environment-Manager/main/.github/assets/ko-fi-banner.svg" alt="Support Chreece on Ko-fi" width="480"></a>
</p>

<p align="center">
  <a href="https://github.com/Chreece/HA-Home-Environment-Manager/releases"><img alt="Release" src="https://img.shields.io/github/v/release/Chreece/HA-Home-Environment-Manager?display_name=tag"></a>
  <a href="https://github.com/Chreece/HA-Home-Environment-Manager/actions/workflows/validate.yml"><img alt="Validation" src="https://img.shields.io/github/actions/workflow/status/Chreece/HA-Home-Environment-Manager/validate.yml?label=Validation"></a>
  <a href="https://www.hacs.xyz/"><img alt="HACS compatible" src="https://img.shields.io/badge/HACS-Custom%20Repository-41BDF5"></a>
  <a href="https://github.com/Chreece/HA-Home-Environment-Manager/blob/main/LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/license-MIT-2aa198"></a>
</p>

<p align="center">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=Chreece&repository=HA-Home-Environment-Manager&category=integration">
    <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open Home Environment Manager in HACS">
  </a>
</p>

# Home Environment Manager for Home Assistant

> **v0.6.0 beta 32 is available for opt-in testing.** Stable remains **v0.5.1**. Beta32 fixes an excessive HA entity dispatcher/event loop caused by treating an internal timestamp as a public state change, and stops reading manifest.json synchronously from async_setup. Beta31's PID numbers/Room Environment profile repairs are preserved; the only integration domain is `environment_manager`.

## Beta 32 - event dispatch and async startup repairs

Reported Home Assistant 2026.10 logs showed thousands of dispatcher failures due to the 10,000 `state_reported` event queue safety limit. Room calculations refreshed an internal `air_evidence_at` timestamp on every pass and then republished all Manager entities as though that internal clock were a physical sensor or status change.

Beta32 compares meaningful plan contents for state publication, excludes Manager-generated entities from its own input tracking, and ignores duplicate physical sensor state events. The newest evidence timestamp is still preserved for physical safety decisions. Frontend cache-busting now loads `manifest.json` in Home Assistant's executor rather than performing blocking `open`/`read_text` on the event loop.

The native Comfee low/quiet fan controls remain subject to the physical integration's actually advertised fan modes; no hardware capabilities are fabricated from device names or screenshots. This beta does not alter fan speed or physical HVAC actuation.

## Beta 31 - restore room and controller numbers after delayed native startup

**A beta30 Python variable-name collision also left Room Environment heating/cooling target values empty even when hardware was online; beta31 fixes that runtime exception.**\n\n**Configuration values must not disappear because an underlying physical device is late to start.** This release restores already-registered Kp/Ki/Kd, PID sampling/cycle intervals, and minimum/maximum ON/OFF entities even when the native climate/fan/humidifier state is temporarily unavailable.

For each **Room Environment** hub, previously available Comfort/Home/Away/Sleep/Eco heating, cooling and humidity targets are retained when compatible equipment is temporarily offline. When a selected device publishes its capabilities after Home Assistant started, newly supported targets and PID fields register without another restart. Real hardware capabilities still determine which kinds of targets apply (for example, a heat-only device does not gain a cooling mode).

The change does not command physical equipment, bypass native minimum ON/OFF protections, reset user settings, or add any migration/legacy domain.

## Beta 30 - visible per-device controller status

Every managed physical controller now has a read-only **Control status** diagnostic sensor. The original managed climate entity still truthfully reflects the physical HVAC state. Select PID or Automatic on the controller's **Control method** entity; if the physical device is still OFF, inspect **Control status** on that same device to see whether the controller is waiting for minimum-OFF time, startup warmup, sensor feedback, a window/ownership interlock, or native command acknowledgement.

The sensor also shows the selected method/preset, evaluated HVAC mode, PID demand percentage, current physical source states, ownership, and any pause reason. When verified demand is satisfied it reports `within_target_band`; when PID output is currently inactive despite positive demand it reports `pid_output_inactive`. These diagnostic status distinctions do not alter physical actuation.

## Beta 29 - optional window contact must not block room heating

Monitored rooms **without any window contact** can now operate their authorized heating, cooling and humidity controllers on verified demand; Home Environment Manager no longer treats absent optional hardware as an open window. **Any configured/discovered window contact that is open, missing or unavailable still blocks actuation.** The controller's live fallback and primary room plan agree on this rule.

The one canonical `environment_manager` integration, Comfort/Home/Away/Sleep/Eco room targets, PID/Automatic native device ON/OFF and safety dwell/ownership checks remain intact.

## Beta 28 - final canonical room targets and active controllers

Beta28 is built from the fully validated final source after beta26/beta27 were found to be intermediate payloads. It ships only the canonical `environment_manager` domain and uses `environment_manager.*` for every runtime/storage namespace.

Each Room Environment device exposes capability-appropriate **Comfort / Home / Away / Sleep / Eco** heating, cooling and humidity targets. These are editable room policies even while automation is Off.

Selecting **Automatic, PID or Manual** on a managed native controller is sufficient authorization for that exact controller to regulate and to start/stop the supported physical device or HVAC mode when verified demand requires it. There is no second power toggle. Real minimum ON/OFF time, max runtime, windows, availability, ownership, defrost/interlocks and acknowledgement protections still apply.

Beta28 also preserves the physical entity's actual OFF age when selecting a method and treats deliberate method reselection as an explicit re-arm of a previous software pause.

## Beta 27 - canonical storage, room targets and active controllers

Beta27 supersedes beta26. The beta26 tag already contained the new Room Environment targets and active controller-method behavior, but two native safety stores still used historical `air_quality_advisor.*` storage keys. Beta27 uses `environment_manager.*` for every runtime and persistence namespace.

The Room Environment device exposes applicable **Comfort / Home / Away / Sleep / Eco** heating, cooling and humidity targets. Selecting **Automatic, PID or Manual** on a managed controller is sufficient authorization for that exact native controller to start/stop the supported physical device or HVAC mode when verified demand requires it. There is no second hidden power switch.

Beta27 retains the physical entity's actual OFF age when a method is selected, so a device that has already satisfied its minimum-OFF time can start immediately on demand. Deliberately reselecting an active method also re-arms a prior software pause. Hardware dwell/runtime, windows, availability, ownership, defrost/interlocks and command acknowledgement remain enforced.

## Beta 26 - room targets and active controller methods

Beta26 removes domain migration entirely and ships only `environment_manager`. There is no migration module, old-domain config-flow step, legacy storage import or legacy runtime alias.

Each **Room Environment** device exposes applicable profile targets for **Comfort, Home, Away, Sleep and Eco**: heating °C, cooling °C and humidity %. These targets are room policy and remain editable even when automation is currently Off. Away now uses its own editable targets instead of silently substituting room hard limits.

Selecting **Automatic, PID or Manual** on a managed native controller is the authorization for that exact controller to regulate and, when verified demand exists, turn the physical device/native HVAC mode ON or OFF. There is no second hidden power switch. Beta26 also uses the physical device's real OFF age, so selecting PID does not create a fake new minimum-OFF delay, and deliberately reselecting a method re-arms a previous software pause.

Minimum ON/OFF time, maximum runtime, windows, availability, identity/ownership, defrost and command-acknowledgement protections remain enforced.

## Beta 25 - one canonical integration only

Beta25 exposes only `environment_manager`. The old `air_quality_advisor`, typo `enviroment_manager`, and `home_environment_manager` names are **not** registered as services, frontend paths or installable integrations anymore. They exist only inside the one-time migration reader.

If an older HACS install left `/config/custom_components/air_quality_advisor` or `/config/custom_components/enviroment_manager`, the canonical integration verifies the old folder's manifest, moves it to `/config/.environment_manager_legacy_components/` as backup, and refreshes Home Assistant's custom-component cache. Unrelated custom components are untouched.

All Developer Tools actions use `environment_manager.*` only.

## Beta 24 - flat HACS tag payload

Beta24 no longer uses HACS `zip_release`. The `v0.6.0b24` tag itself contains the integration files at repository root, with `content_in_root: true`. HACS can therefore switch away from its cached `custom_components/air_quality_advisor` remote path, discover the root `environment_manager` manifest, and extract GitHub's normal tag archive directly into `/config/custom_components/environment_manager`.

This avoids both earlier failure modes: looking for the old `air_quality_advisor/manifest.json`, and the later release-asset download failure. The Home Assistant migration remains the beta22 identity-preserving migration.

## Beta 23 - HACS domain-switch installation fix

If HACS previously knew this repository as `custom_components/air_quality_advisor`, beta22 could fail before download with **No manifest.json file found 'custom_components/air_quality_advisor/manifest.json'**. Beta23 fixes that repository-path transition using HACS-supported root discovery plus a release ZIP.

The beta23 tag has `content_in_root: true`, `zip_release: true` and `filename: environment_manager.zip`. A root discovery manifest declares the canonical domain `environment_manager`, so HACS resets the cached old remote directory and targets `/config/custom_components/environment_manager`. The attached ZIP contains the integration files directly at archive root, preventing a nested `custom_components/` install.

Beta22's in-place config-entry migration is unchanged: the exact config-entry ID, room subentries, entity/device identities, options and user customizations are preserved.

## Beta 22 - exact config-entry identity during domain migration

Beta22 migrates an existing `air_quality_advisor` or beta20 `enviroment_manager` entry **in place**. The exact config-entry ID survives, as do room subentry IDs, entity IDs/unique IDs, device IDs, user custom names, disabled states, options and stored settings. Only the registry ownership that must follow the canonical domain changes.

Home Assistant 2026.10 freezes a config entry's domain and does not provide a public cross-domain setter. The migration therefore performs a tightly checked reindex of the existing entry and fails closed if the validated HA internals are unavailable or the entry is in an unsafe transitional state. The release gate runs this migration against installed Home Assistant 2026.10 for both legacy domains.

After updating through HACS and restarting, use **Settings -> Devices & services -> Add integration -> Home Environment Manager** if the migration is not already surfaced. Confirming migration re-homes the existing entry; it does not create a second Home Environment Manager instance.

## Beta 21 - canonical environment_manager spelling repair

Beta21 corrected beta20's domain spelling mistake. The installed package is `custom_components/environment_manager` and the runtime/manifest domain is `environment_manager`. It retained `air_quality_advisor`, beta20 `enviroment_manager`, and `home_environment_manager` service/card compatibility during the beta migration window.

Beta21 preserved entity/device registry identity, room-owned Comfort/Home/Sleep/Eco targets, verified Away behavior, room-wide limits and room-sensor feedback precedence. Beta22 supersedes its temporary replacement-entry migration by preserving the config-entry ID as well.

## Beta 20 - transitional enviroment_manager typo and automatic room presets

Beta20 introduced the room-owned preset/controller changes but accidentally installed under the misspelled domain **enviroment_manager**. Beta22 treats that domain as a migration source so beta20 testers are not stranded.

The separate **Allow power and HVAC mode control** entity/backend flag was removed. Selecting Automatic, PID or Manual on an authorized native controller is the control permission; when room policy and demand require it, the controller may turn the native device/mode on, regulate it and turn it off again under availability, ownership, dwell, window and protection gates.

Room Environment owns **Comfort**, **Home**, **Sleep** and explicit **Eco** heating/cooling targets. **Away** is chosen only from verified nobody-home evidence and uses the Room Environment temperature bounds instead of duplicate device setpoints.

## Beta 19 - migration bridge and room-owned operating presets

Beta19 remained on the legacy `air_quality_advisor` package/domain as the HACS-safe bridge toward the later canonical package. It introduced the room preset semantics and migration metadata needed by subsequent betas. Direct beta19 -> beta22 and chained beta19 -> beta20 -> beta22 storage ancestry are both retained.

## Beta 18 - Room Environment limits and room-sensor control feedback

The temperature, humidity and percentage-fan min/max controls now live **once on the Room Environment device**, not on every managed physical-device controller. A room shows only limits supported by at least one selected physical device. The editable range is the common safe intersection of the available selected devices; each controller still enforces its own stricter native limits when issuing commands.

Beta 17 per-device limit values are migrated conservatively: room minimums inherit the highest saved minimum and room maximums inherit the lowest saved maximum when valid. The obsolete b17 per-device limit registry entities are removed so they do not remain as unavailable controls on physical-controller devices.

Controllers now treat the room's explicitly selected **temperature, humidity and air-quality sensors** as the authoritative default feedback. Multiple selected room sensors are averaged only when all selected sources are valid/fresh. A climate device's built-in current-temperature/current-humidity reading no longer overrides explicitly selected room measurements. Legacy source fallback remains only for installations that have never made an explicit room-source selection.

Per-device **Quiet when in room / Quiet when sleeping** and **Always / Room occupied / Room absent** control policies remain on each physical controller. Availability-first calculation and all ownership/safety gates remain unchanged.

## Beta 17 - Per-device quiet, occupancy and hard control bounds

Every managed physical-device controller with an adjustable fan now has **Quiet when in room** and **Quiet when sleeping**. Percentage fans use the controller's quiet percentage; discrete fans use an advertised native mode such as Low. Unknown occupancy or sleep evidence holds the current fan setting instead of reducing or restoring speed, and quiet control never powers an appliance merely to change its fan speed.

Each managed controller also has one **Control availability** policy: **Always**, **Room occupied**, or **Room absent**. Automatic/PID control is permitted only in that device's selected state; unknown occupancy blocks conditional control. Legacy room/home policies remain compatible for old drivers, but managed controllers migrate to the stricter room-occupied policy.

Capability-specific min/max bounds live on each controller: temperature bounds for temperature-capable equipment, humidity bounds for humidity-capable equipment, and fan-percentage bounds for percentage fans. Manager-generated targets, PID trims and speed commands are clamped to these values and the physical device's own native bounds. These are hard bounds for the **Manager-owned control path**; they do not seize unrelated manual/native control from another integration.

The runtime now checks that every selected native endpoint of the managed physical device is available **before** calculating capabilities, occupancy policy, targets, room measurements or PID demand. Unavailable devices remain in a waiting state and receive no control calculation or service command.

## Beta 16 - General sources, Home hub, Task AI and away cooldown

On the first General settings pass, Home Environment Manager now preselects all discovered weather and outdoor air-quality sources and every discovered pollen provider. Later explicit empty selections remain empty. **Enable Announcement Hub** is shown only when the Hub is actually configured; enabling it keeps Hub routing authoritative.

The AI selector now includes both Home Assistant conversation agents and data-capable **Task AI** entities. Direct Task AI rewrites use `ai_task.generate_data`; the same output-safety validation and original-message fallback remain in place. TTS language choices come from the selected TTS entity's advertised capabilities and display readable language names. Region labels such as **English (US)** and **English (UK)** appear only when that provider advertises multiple variants.

Home-wide controls and diagnostics now belong to a native **Home** group/device instead of appearing unassigned. Room groups and managed physical-device controllers remain unchanged. A fresh, explicitly empty occupied-room source means nobody is home, but **Away** is applied only after the configurable Home away cooldown. Unknown, unavailable or stale occupancy never starts that timer or authorizes Away.

## Beta 15 - Device methods, editable preferences and template selectors

Choose Automatic, Manual, Off or supported PID **on each managed device**; no
return to Configure is needed. Explicit method choice approves only that
controller's current native endpoints and feedback. Power/HVAC-mode switching
uses its separate **Allow power and HVAC mode control** device switch and
per-device minimum ON/OFF/maximum-runtime fields. The old room drivers and
other devices receive no new permission. Changes to sensors or identity require
explicit reselection; manual/restart pauses and physical protections remain.

Room Sleep and ISO 7730/PMV switches now work with Home Assistant's read-only
config-entry options. PMV may be enabled with incomplete inputs, but never
returns fabricated scientific results. Select measured radiant-temperature
and air-speed sources on the room device; MET/CLO and applicable values stay there.

Occupied-room/sleep-room template sensors are selectable even when empty or
unavailable. State or a list attribute (including `rooms`) is supported. Fresh
empty lists mean no rooms; unknown/stale values never imply absence.
Selectors display **Device name - Entity name (state)**, with a normal hyphen
and empty parts omitted. The rooms-first wizard and hub layout are unchanged.

## Beta 14 — Rooms, room inputs, general settings, done

**Select monitored rooms → one page per selected room → General settings → Finish.** Each room page has six separate multi-selects: windows, air-quality/environmental sensors, temperature, humidity, pressure and climate/fan/humidity devices. Options show **device name — entity name**, plus the exact entity ID. All real HA areas are selectable, including rooms without windows.

Setup then creates or retains the Home hub with general input/output entities and each selected room hub with its general settings/overview device and one managed controller per physical product. No further Climate or PID configuration menu is part of this route. Targets, presets, control methods and quiet settings stay on the managed devices. Selecting equipment does not authorize automatic power.

Explicit source lists govern actual monitoring; empty means unused. Selected missing inputs remain unavailable instead of silently falling back. Qualified temperatures are normalized before averaging; selected pressure readings appear in room input diagnostics in hPa. Cancelling writes nothing, and the final save preserves unrelated concurrent settings. Existing IDs and tuning are retained.

## Beta 13 — One climate-device selection path

**Configure → Area settings → Climate devices → room → physical devices → Save.** The separate Climate and Climate PID setup entries are removed. Saving creates the selected controller devices inside the room hub without a mandatory setup wizard. One physical product is one selector choice even when it exposes several native endpoints.

Targets, presets, Automatic/Manual/Off/PID and quiet settings belong to the managed devices; general room settings remain on the room hub. The optional sensor/hardware commissioning checkbox continues in this same setup path. Selection is not an automatic-control grant. Deselecting a device also removes its old supervisory PID assignment without deleting tuning or changing other rooms. All 38 locales are included.

## Beta 12 — Expandable room hubs with devices, not services

The integration page now has **one native room group per configured area**.
Expand that room to find its **general room settings device** and **one managed
controller device per selected physical product**. Home-wide settings remain on
Home. All are ordinary devices; beta 11's incorrect Services classification is
explicitly cleared during the upgrade. Parent-device links still preserve the
Home → Area → controller relationship, but room subentries provide the actual
integration-page grouping.

The migration keeps existing device/entity/unique IDs and user customizations.
Do **not** delete and recreate the integration. Selected devices are visible
without enabling automatic control; existing commissioning and control-method
permissions are unchanged. Removing a room group removes only its membership
and control grants, not native hardware or another room's settings. Routine
room target changes do not reload the integration.

## Beta 11 — Area hubs and per-device climate control

**Home hub → Area hub → managed equipment controller devices.** Room-wide
entities/settings stay on the Area hub. Each supported physical controller
gets a native Home Assistant climate interface beneath that hub, with the
room's valid temperature/humidity readings, only its actual HVAC/fan/swing
capabilities, and **None / Home / Comfort / Away / Sleep / Eco** presets.
Independent channels on the same physical device stay separate controls on
one logical child. Native equipment remains with its original integration.

The per-device **Control method** selector offers **Existing, Automatic,
Manual, Off** and **PID where supported**. Existing is the upgrade default;
new controllers do not take ownership automatically. Automatic and PID follow
qualified room/preset policy. Manual with None retains explicit user targets
independently of occupancy changes. Presets affect targets and may retain their
own native fan choices. Off stops the Manager path and retires its owned
outputs after the required minimum ON time; it does not seize unrelated manual
appliances. The original room drivers cannot write the same claimed endpoint.

**On/off PID** uses slow, bounded duty cycles for commissioned fans,
humidifiers/dehumidifiers, supported native climate modes and qualified direct
outputs. Editable gains and sample/cycle intervals are checked against physical
minimum ON/OFF constraints and maximum continuous runtime. Tiny invalid pulses
are skipped. These controls are not an auto-tuner and do not bypass manufacturer
compressor or independent safety requirements. Setpoint-only permission remains
setpoint-only, even when PID is selected.

**Quiet during sleep** and **Quiet while occupied** appear only on controllers
with adjustable native fan support. Choose a percentage limit or a real native
fan mode; no vendor-specific quiet mode is guessed. Quiet control never starts
a device and restores speed only with known context and unchanged ownership.
It limits fan settings, not measured sound pressure.

Device status/help attributes explain pending acknowledgements, interlocks and
pauses. Commands persist their intent before exact-target dispatch and recheck
sources, identity and ownership. After restart or manual interference, use
**Reconcile and resume** only after checking the physical endpoint. Existing
hardware commissioning remains mandatory; automatic power control does not
adopt a device already running manually. Keep experimental control disabled
until actual equipment protection and response have been verified.

See [the controller implementation and test boundaries](docs/DEVICE_CONTROLLER_CHECKPOINT.md).
The 38-language UI includes Greek. CI checks software behavior with mocked HA
boundaries, not physical hardware certification.

## Beta 10 — Sources in Configure, controls on devices

The **Configure** flow concentrates on areas, Home Assistant entities, outdoor
data providers, measurement sensors, controlled equipment and hardware-specific
commissioning. It no longer asks for ordinary room/environment operating
settings that belong on the Home and Area devices.

Open the **Home Environment Manager** device for shared air/weather limits,
notification channels and language, occupancy policies, AQI provider scales and
custom thresholds, and pollen preferences. Each **Area Environment** device
provides adjustable computed/managing settings: temperature and humidity policy,
thermal comfort science, occupied/unoccupied/away/sleep profiles, local Time
entities for sleep start/end and safely bounded PID/direct control where actual
equipment has been commissioned. Native climate, humidifier and fan entities
remain authoritative for their own power, HVAC modes and active setpoints.

For mold indication, select a **same-room indoor temperature sensor** and a
weather source with a valid outdoor temperature in Configure. On the Area
device, enter the **measured temperature of its coldest surface** and press
**Recalculate mold factor**. This is not an inferred surface temperature.
Recalculation checks that room's current indoor and outdoor temperature,
source freshness, physical geometry and plausible factor. Changing the
measurement invalidates the old factor; a failed button calculation does not
silently replace otherwise valid calibration.

The 38-language Home Assistant catalogs include translated device controls
and explanations (including Greek). Device preference edits do **not**
authorize physical relays, fans or compressor commands. Independent
commissioning and every existing safety interlock remain required for
any experimental opt-in physical actuator.

## Native Home and Area device settings (beta 10)

Every configured monitoring area has a **<Room> Environment** device. The
**Home Environment Manager** parent device uses the original recommendation
sensor (with its complete `dashboard` snapshot and global source/settings
attributes); all existing entity unique IDs and Lovelace cards remain intact.

**Home device (shared settings):** edit all 22 air/weather monitoring thresholds
through Home Assistant Number entities, plus the announcement repeat interval,
automatic text/TTS notification switches, AI rewrite and Announcement Hub
switches and the output-language selector. Updating a global threshold applies
to **every room** and preserves source availability/validity checks. The options
wizard now keeps only settings requiring specialized source/entity pickers,
calibration, device assignment and safety commissioning.

**Area device (unique manager-derived controls):** keep original climate/fan/
humidifier entity controls as native Home Assistant equipment. When an advanced
PID is explicitly commissioned for a room, the area device exposes its
**supervisory target**, Kp, Ki, Kd, sample interval, bounded setpoint offset,
minimum/maximum allowed setpoint and movement thresholds as editable Number
entities. A selector chooses **Defaults** or **Manual** for the PID *gains*;
editing a gain selects Manual, and switching to Defaults restores
Kp **22 %/°C**, Ki **0.25 %/(°C·minute)** and Kd **0 %·minute/°C**.
The default interval is **300 seconds**. **This is not an auto-tuner.** PID
auto-identification requires enough verified device response measurements and
must never infer gains from a cold start without reliable evidence. The
existing supervisor sends bounded thermostat *setpoint corrections*, never
direct compressor/relay cycles. Gains are validated, the previous PID
integrator is reset safely between command cycles, and any running command
blocks concurrent tuning edits.

For rooms with a climate management profile, the area device also exposes
explicit home, unoccupied, away and sleep heating/cooling **policy targets**
and the manual/automatic occupancy profile selector. Those separate policies
are not duplicates of a real thermostat's active setpoint. Home Assistant
validates temperature-band deadbands before applying changes.

The Lovelace dashboard displays a **gear icon on every room** that resolves
the actual Home Assistant registry device ID and opens
`/config/devices/device/<device_id>`. The card header offers the equivalent
shortcut to the home device. Missing or ambiguous device registry entries are
never converted into guessed URLs. The original environment overview sensors
remain read-only snapshots of all raw inputs and computed decisions.

**Hardware/safety controls remain under Configure:** select or reassign
thermostats, raw sensors, room occupancy providers, direct outputs and
commissioning permissions through the validated setup flow. A device-number
editor must never implicitly enable any actuator or override its safety
interlocks.

## Install or upgrade to the v0.6 beta with HACS

1. **Back up Home Assistant and your existing configuration.** Home Assistant 2026.10+ is required. The only active integration domain is `environment_manager`; legacy entries are migration inputs only and keep their existing IDs/entities during the one-time migration.
2. Open [Home Environment Manager in HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=Chreece&repository=HA-Home-Environment-Manager&category=integration), or add `Chreece/HA-Home-Environment-Manager` as a **custom Integration repository** if not already installed.
3. Open the integration in HACS, choose **Redownload** or the available version-selection menu, enable **Show beta versions** (wording depends on your HACS version), and select **v0.6.0b28**. Beta versions are deliberately optional; do not download `main` to obtain the beta.
4. Restart Home Assistant after the installation/update, then verify that **Home Environment Manager** loads and your prior windows, announcement settings, sensors and entities are retained.
5. Start with **read-only climate diagnostics** in Developer Tools → Actions: `environment_manager.climate_diagnostics`. Leave direct relay/PWM, fan power, humidifier power and native DRY/FAN_ONLY auto-control unapproved until equipment-specific commissioning.

If your HACS version cannot select prereleases, use the **Manual installation ZIP** attached to the [beta GitHub release](https://github.com/Chreece/HA-Home-Environment-Manager/releases/tag/v0.6.0b28). Extract it into the Home Assistant configuration directory, preserving `custom_components/environment_manager/`, then restart. **The ZIP is a manual-install asset; HACS installs the selected version from the GitHub tag.** To return to stable, use HACS to select **v0.5.1**, then restart. Beta-only settings may need review after downgrading.


### Complete configuration translations and explanations — beta 9

A field-by-field localization audit found that an old generator supplied
the correct JSON keys while leaving many option descriptions in English or
with generic “select a source” text. The new final translation pass documents
every visible initial-setup and options-flow field, including **all 22 advanced
thresholds**, per-device occupancy/sleep controls, native climate and
humidity/fan safety settings, PID, mold/air measurements and optional
building-science modules. It uses distinct safety-oriented English and Greek
explanations for critical controls and locale-specific terminology for the
other 36 supported languages.

The generator runs last so re-generating the 38 catalogs cannot silently
reintroduce missing descriptions. Runtime keys, saved config data, Home
Assistant entity IDs and physical actuator permissions are unchanged.
Threshold explanations distinguish operational policy from actual medical
or legal exposure standards. Historical configuration is retained.

### Setup retry fix in beta 4

If the first **Add integration** click silently closes its dialog, an unfinished
Home Assistant configuration flow can block later attempts with **“This is
already being configured.”** Beta 4 avoids reserving the integration's fixed
unique ID before the initial room form is visible. A fresh setup attempt can
open a new first page without waiting for the abandoned browser dialog.
Before saving, it performs both a unique-ID and an existing-entry check; it
still creates at most one new Home Environment Manager entry.

**Already seeing that error with an earlier beta?** Restart **Home Assistant
only** (Settings → System → Restart), not your Debian host. This clears
in-memory unfinished flows from older integration code. Then check
**Settings → Devices & services → Integrations**: use **Configure** on an
existing Home Environment Manager entry; use **Add integration** only when
no entry exists. HACS updates the code but does not require adding a second
integration. Do not remove existing entries or delete `.storage` to recover
an interrupted setup.

### What's improved in beta 3

- **Info bubbles** (ⓘ): tap or click each primary and scientific measurement to understand what it means, its practical value or risk, and a limit **only when the sensor actually supplies one**. The overview works with keyboards and mobile touch.
- **Real Home Assistant source choices:** occupied and sleeping room lists show only source entities containing recognizable HA rooms. After choosing the source, the next selector offers the source's actual usable attributes plus **State** when the state is a valid room list. Choosing another source refreshes these options without saving a stale attribute.
- **What does “240 min” mean?** It is the maximum permitted age of occupancy/sleep source data. Old or unknown data hold new control commands; it is **not a minimum sleep period**.
- **Improved per-room translations:** localized headings and help for climate, occupancy, PID, sensors and equipment in all 38 languages, with additional Greek descriptions.

## What's new in v0.6 beta

| Capability | Beta behavior |
| --- | --- |
| Room climate | Home, unoccupied, away and sleep heat/cool bands; capability-aware native thermostats, secondary heat/cool and native range targets |
| Humidity | Fresh-room RH thresholds and hysteresis, advisory and separately opted-in humidity setpoint/power supervision |
| Ventilation and filtration | CO₂ and PM2.5 evidence, qualified outdoor-air interlocks, separately commissioned fan speed or fan power paths |
| DRY and FAN_ONLY | Supports DRY-only equipment for advice; automatic DRY↔FAN_ONLY is experimental, disabled by default and requires independent compressor protection |
| Free conditioning | Suggests window airing when *measured* outdoor conditions could cool, warm or dry the room; **never automatically opens windows or stops HVAC** |
| Safety | One room-purpose arbitration policy, exact output ownership across config entries, manual-override pauses and durable write-intent recovery |
| UX | Room-by-room climate cards, German/Greek/English controls and notifications, localization support, dashboard coordination details and read-only diagnostics |

Full setup and scientific measurement details are documented below. [Report a beta issue](https://github.com/Chreece/HA-Home-Environment-Manager/issues/new), including software version, relevant HA entity capabilities and redacted diagnostics—never credentials or personal addresses.

**Home Environment Manager** combines local sensor data, international environmental sources,
building physics and optional advanced comfort models to recommend how to keep a room
comfortable while balancing ventilation, air quality, moisture and potential
pollutant exposure. **PID climate control is optional and initially disabled.** When enabled by the
user for an explicitly chosen room and thermostat, it adjusts only the target
temperature while keeping heating/cooling modes under device control.
The Home Assistant integration domain, existing entity unique IDs and all
saved configuration remain `air_quality_advisor` for upgrade compatibility.


**New in beta 9 — controller/menu audit:** The room-aware entities from beta 6 remain minimal; this beta fixes stale device selections retaining control roles, checks real equipment features/timing limits, protects absence-OFF from deselected targets, corrects purifier-speed setpoints, moves fan purpose assignments safely, promotes replacement thermostats properly, excludes rejected sensors, and improves occupancy/AQI source editors.\n\n**Area devices introduced in beta 6:** Each selected monitoring room, and each active climate/PID-only room, gets its own Home Environment Manager device in the actual Home Assistant area. It contains one `Environment overview` sensor (assessment state with raw input/source values, window contacts, derived calculations and climate diagnostics as attributes). If calibrated mold indication is enabled for a monitored room, the device additionally exposes one genuine calculated `Surface humidity` percentage sensor; unknown inputs remain unavailable. The integration does **not** duplicate native thermostat setpoints, humidity, temperature, CO₂, PM or fan controls. Those remain on their original Home Assistant equipment entities. No new hardware control is authorized by the area devices.\n\n**One compatibility-preserving Home Assistant recommendation entity and one expandable dashboard card for all selected rooms.** It compares indoor CO₂, AQI, particles, VOCs and either room RH or an optional calibrated mold indicator against outdoor air quality, current weather and selected weather-warning entities, then recommends **which windows to open or close and why**. Announcements are entirely optional.

> This project is an advisor, **not an automatic window actuator**, medical device, emergency warning system, or authoritative weather alert. It never controls covers. Outdoor warnings and uncertain conditions are intentionally treated as blockers.

<p align="center"><img src="https://raw.githubusercontent.com/Chreece/HA-Home-Environment-Manager/main/.github/assets/home-environment-manager-workflow.svg" alt="Indoor sensors, outdoor air quality and weather feed a single recommendation sensor, with optional announcements" width="100%"></p>

## Dashboard screenshots

The examples below are **real renders of the bundled Lovelace card** using *sample sensor values*, not screenshots of a live Home Assistant installation. They demonstrate the available room summary, ventilation recommendations, outdoor warnings, responsive layout and Greek localization.

### Desktop overview — light theme

<p align="center">
  <img src="https://raw.githubusercontent.com/Chreece/HA-Home-Environment-Manager/main/.github/assets/screenshots/dashboard-overview-light.png" alt="Home Environment Manager light-theme dashboard: outdoor air conditions, good and attention rooms, four-room infographic and recommendation to open a window" width="850">
</p>

### Greek localization — dark theme

<p align="center">
  <img src="https://raw.githubusercontent.com/Chreece/HA-Home-Environment-Manager/main/.github/assets/screenshots/dashboard-greek-dark.png" alt="Greek Home Environment Manager dashboard in Home Assistant dark theme, with measured CO2 and a window recommendation" width="800">
</p>

### Mobile view and outdoor warning

<table>
  <tr>
    <td align="center" width="38%"><b>Responsive mobile dashboard</b></td>
    <td align="center"><b>Unsafe outdoor conditions — close windows</b></td>
  </tr>
  <tr>
    <td valign="top" align="center"><img src="https://raw.githubusercontent.com/Chreece/HA-Home-Environment-Manager/main/.github/assets/screenshots/dashboard-mobile.png" alt="Home Environment Manager mobile dashboard with room cards and sensor gauges" width="340"></td>
    <td valign="top" align="center"><img src="https://raw.githubusercontent.com/Chreece/HA-Home-Environment-Manager/main/.github/assets/screenshots/dashboard-outdoor-alert.png" alt="Home Environment Manager dark-theme outdoor weather and air-quality warning, with close-window recommendation" width="550"></td>
  </tr>
</table>

*Demo sensor values are illustrative; actual recommendations always use your configured Home Assistant entities. The card does not operate windows. Additional v0.6 climate screenshots are shown in the beta section below.*

Screenshots are generated with the bundled card source using [`tools/generate_readme_screenshots.py`](tools/generate_readme_screenshots.py). To refresh them after changing the card, run the one-time [README screenshots workflow](.github/workflows/readme-screenshots.yml) manually; it does not run on routine development pushes.


### Scientific environment details — desktop and mobile

The following examples show the **actual bundled Lovelace card** with
illustrative, explicitly simulated sensor values and advanced room analysis.
They are not screenshots from a live user's home.

<p align="center"><img src="https://raw.githubusercontent.com/Chreece/HA-Home-Environment-Manager/main/.github/assets/screenshots/dashboard-science-desktop.png" width="850" alt="Home Environment Manager Lovelace scientific room metrics for ventilation, comfort, moisture, pollutants and energy"></p>
<p align="center"><img src="https://raw.githubusercontent.com/Chreece/HA-Home-Environment-Manager/main/.github/assets/screenshots/dashboard-science-mobile.png" width="360" alt="Home Environment Manager responsive mobile scientific room card"></p>

## What it provides

- A single `sensor.air_quality_advisor_window_recommendations` (actual entity ID may vary with user settings). States: `open`, `close`, `idle`, `blocked`.
- Attributes: `open_windows`, `close_windows`, structured `recommendations` with windows, room/area, sensor reason, value and localised message, `outside_blockers`, `diagnostics`, `outdoor_safe`, `announcement_hub_available`.
- Event-driven updates and periodic 5-minute freshness checks. No external APIs, daemons, cloud credentials or Home Assistant tokens. Uses existing entities only.
- **Optional calibrated mold indicator with automatic RH fallback:** per-room measured cold-surface temperature plus a room temperature sensor and an outdoor weather temperature are used to calibrate a surface-humidity estimate. When unavailable, the average of valid room RH sensors automatically substitutes as the ventilation trigger (default 65% RH); the room remains marked incomplete and the card explicitly says RH fallback is active. Unavailable, zero, stale and out-of-range RH sources are excluded.
- A guided setup with editable, automatically suggested window exclusions, room selection, outdoor measurements and weather warnings. Indoor measurements and genuine window contacts are discovered using HA's entity/device area assignments. Configurable thresholds are tucked into **Configure → Advanced thresholds**.
- Optional room-aware [Announcement Hub](https://github.com/Chreece/HA-Announcement-Hub) output (`notify.announcement_hub`), **or** direct `notify.send_message` and `tts.speak` via supported entities. Not installing Announcement Hub does not affect the recommendation sensor.
- **One optional AI setting** for both delivery paths. With Announcement Hub configured, it explicitly forwards `use_ai: true/false` and optionally `ai_agent`; otherwise the selected Home Assistant conversation agent rewrites direct notification/TTS text. AI never changes the window decisions and is off by default. Only a **not-running/unavailable Hub** permits Home Assistant direct/persistent notification fallback. A **running Hub** owns room/output routing and rejections; Advisor reports enqueue failure but never creates a second native notification.
- Auto notifications/TTS can each be enabled or disabled independently. Open announcements wait 90 seconds for conditions to stay stable; close announcements are immediate. Repeated open recommendations have a 15-minute cooldown during the current HA process. New urgent close recommendations are not suppressed by that cooldown, even if the same window was reopened. No notification is generated on every unchanged sensor reading.
- Manual `environment_manager.announce` action with an independent language override across **38 supported Home Assistant language choices**. Speech requires a compatible TTS voice.
- A responsive **Home Environment Manager dashboard card**: safe/attention/unknown room counts, current outdoor weather and pollution, threshold meters, window states, and room-specific advice. Card text follows your **Home Assistant user language**, independently of voice/notification language.

## International environmental intelligence (v0.4.0)

**Works internationally:** no German/Greek-only integrations, coordinates, AQI
scales or pollen sources are hard-coded. All optional provider information
comes from sensors and integrations *already connected to Home Assistant*.
Users supply and explicitly identify which scale and units each sensor uses.

### New science available in each room

| Capability | Inputs and methods | Output and evidence limits |
| --- | --- | --- |
| Region-specific AQI | Explicit per-entity EPA 0–500, European categorical 1–6, or custom provider scale | Never guesses the country or misuses another scale. Unspecified scales remain *unknown* rather than declaring safe air. |
| Outdoor gases | Actual NO₂, O₃ and SO₂ sensors in µg/m³ | Configurable operational screening, not equivalent to a regulatory 24-hour or 8-hour mean. |
| Pollen-aware airing | A user-selected numeric pollen forecast from any HA integration; user declares scale and high threshold | Informational by default. Blocking ventilation on high pollen is an **explicit opt-in** policy, not a global default. |
| Ventilation learning | Real NDIR CO₂, calibrated history, window contacts | Reports *indicative* declining CO₂ and time to an operational target if the trend remains stable; no arbitrary prediction if windows are closed or data insufficient. |
| Particle filtration | User-measured room volume and purifier's *particle CADR* (m³/h), optional operation sensor | Nominal equivalent clean-air changes per hour. Does not claim removal of gases, infections, or measured causal benefit. |
| Moisture events | Time history of indoor RH, optional extractor state | Detects rapid RH rises and suggests checking extraction. A shower/cooking source is **not** inferred from RH alone. |
| Indoor/outdoor PM | Indoor + outdoor PM2.5 and overlapping 24-hour qualified history | Descriptive concentration ratio, explicitly **not** a calibrated particle infiltration fraction. |
| Radon | A verified dedicated radon sensor, Bq/m³ or pCi/L | Long-term screening only after about a year of sufficient daily averages. The local monitoring reference is configurable; regulatory levels depend on the jurisdiction. |
| Formaldehyde | Verified real HCHO measurement, µg/m³ or mg/m³ | 30-minute observed concentration; comparison is disabled for cheap estimated HCHO/eCO₂ proxies. |
| Acoustic environment | Calibrated A-weighted equivalent sound readings in dB(A) | Proper logarithmic acoustic-energy averaging, optionally the preceding local nighttime period for sleeping rooms. Peak-only meters are unsuitable. |
| Lighting | Calibrated photopic lux measurements; independently measured melanopic EDI only | Daylight-exposure history. Ordinary lux is **never** converted into a fake circadian/melanopic result. |
| Thermal comfort | Actual radiant temperature, air speed, occupant activity (met) and clothing (clo), opt-in | ISO 7730:2025 PMV / PPD computed locally using an independently verified scalar Fanger model, without Numba or LLVM. Missing inputs suppress the result. |
| Overheating | Time history of room temperature | Observed temperature degree-hours above a chosen reference, not TM52/TM59 building-certification compliance. |

Existing modules from v0.3.0 remain, including humidity-ratio calculations,
surface-condensation margin, measured PM 24-hour averages, adaptive comfort,
passive cooling, controlled CO₂ decay estimation and local bounded history.
New specialist sensors, comfort assumptions and equipment measurements are
**optional**. Most households can benefit without buying extra hardware.

### Clear configuration

In **Home Assistant → Settings → Devices & services → Home Environment Manager → Configure**:

1. **Rooms and safety:** retain your window contacts, sensor exclusions, indoor and outdoor readings, optional mold calibration, weather warnings and existing notification settings.
2. **International air quality & pollen:** choose your outdoor AQI provider's published scale and optionally a pollen forecast. Unknown AQI scales cannot be silently interpreted.
3. **Room environmental measurements:** select **one room at a time**, then configure optional temperature-source override, actual air volume, purifier CADR, extractor state and real CO₂ technology.
4. **Specialist measurements:** choose validated radon, formaldehyde, noise and daylight sensors, verifying hardware/calibration where required.
5. **Advanced comfort:** enable PMV/PPD **only** when all physical inputs exist; otherwise rely on the simpler adaptive comfort indication with its applicability limits.

Every module uses **evidence statuses** such as not configured, invalid units,
insufficient history, unverified sensing hardware and calculated. Missing
data never justifies an invented positive health result. All calculations are
local; selected external forecasts come from Home Assistant's existing providers.

### Compatibility and the upcoming PID phase

The public title, integration manifest, dashboard branding and Home Assistant domain are all **Home Environment Manager / `environment_manager`**. Historical domains are accepted only as migration sources; they are not registered as services, frontend paths or installable integrations. Existing entity unique IDs, area selections, statistics storage and prior configurations are preserved during migration. Existing
`custom:air-quality-advisor-card` Lovelace dashboards still work; new
cards may use `custom:home-environment-manager-card`.

**PID-based climate control is not enabled in v0.4.0.** In the next phase,
climate actuators will need explicit device selection, safety constraints,
anti-windup, deadbands, duty limits, manual-override respect, safe fallbacks
and independent validation before any control can be enabled. None of the
current advice triggers an actuator directly.

**Research and frameworks:**
[ASHRAE Standard 55](https://www.ashrae.org/technical-resources/bookstore/standard-55-thermal-environmental-conditions-for-human-occupancy),
[ISO 7730:2025](https://www.iso.org/standard/79804.html),
[WHO 2021 air-quality guidelines](https://www.who.int/publications/i/item/9789240034228),
[European Environment Agency air quality index](https://airindex.eea.europa.eu/),
[US EPA AQI](https://www.airnow.gov/aqi/aqi-basics/),
[WHO radon](https://www.who.int/news-room/fact-sheets/detail/radon-and-health),
[CIE S 026](https://cie.co.at/publications/cie-system-metrology-optical-radiation-iprgc-influenced-responses-light-0).


## Installation

### HACS (versioned releases)

1. In HACS, open **Custom repositories**; enter `https://github.com/Chreece/HA-Home-Environment-Manager` and choose **Integration**.
2. Install **Home Environment Manager**, restart Home Assistant and add it under **Settings → Devices & services → Add integration**. The dashboard card is bundled and registered automatically when Home Assistant starts; no separate HACS frontend repository or copy to `www` is required.
3. No YAML configuration is required. After updating from a version that was classified as a Helper, **restart Home Assistant** so the new manifest type takes effect. The existing configuration and entity ID are kept; the integration should now appear under **Settings → Devices & services → Integrations** instead of being categorized under Helpers.

### Manual

Copy `custom_components/environment_manager/` to `<your Home Assistant config>/custom_components/environment_manager/`, restart HA, then add the integration from the UI. Alternatively, from the extracted repository run:

```bash
HA_CONFIG=/path/to/homeassistant/config bash ./install.sh
```

The installer writes **only** the integration directory, makes a rollback backup of an older installation and does not restart HA or end your SSH session.

## HACS releases

**Latest stable release: v0.5.1; opt-in beta: v0.6.0b15.** See [GitHub Releases](https://github.com/Chreece/HA-Home-Environment-Manager/releases). Each push to `main` runs Python and frontend tests, translations, Hassfest and HACS validation; a new version is automatically published only when all gates pass.

Update through [HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=Chreece&repository=HA-Home-Environment-Manager&category=integration), then restart Home Assistant. Existing config entries and the single recommendation sensor retain their IDs. The bundled Lovelace card is refreshed automatically.

## Internationalization — 38 languages

Home Environment Manager supports **38 Home Assistant language choices**, including 33 new locale packs for setup, reconfiguration, room states, notification messages, announcement text and the built-in dashboard card. The card follows the signed-in **Home Assistant user's language**, while `environment_manager.announce` can override message language independently.

**Languages:** English, German, Greek, French, Spanish, Italian, Dutch, Portuguese (Portugal and Brazil), Polish, Russian, Ukrainian, Turkish, Czech, Slovak, Hungarian, Romanian, Bulgarian, Croatian, Serbian, Swedish, Norwegian Bokmål, Danish, Finnish, Indonesian, Vietnamese, Thai, Hindi, Simplified/Traditional Chinese, Japanese, Korean, Arabic, Hebrew, Persian, Bengali, Urdu and Tamil.

BCP47 support distinguishes `pt-BR` from `pt-PT`, and `zh-Hans` from `zh-Hant` (`zh-CN` and `zh-TW` are also recognized). Unsupported locales fall back to English. The dashboard uses right-to-left layout for Arabic, Hebrew, Persian and Urdu.

**Translation audit (v0.2.4):** All 38 language files now provide localized configuration and Reconfigure field labels, help text, validation errors, the settings-selection menu, abort messages, and the language selector's **Home Assistant default** option. Greek, German, French and Spanish include fully translated advanced-threshold labels and detailed explanations. The other 33 languages use short translated safety guidance and error messages with technical terms and symbols; native-speaker review is welcome. **Dynamic weather warnings, device names, room names, geographic names, sensor readings and IDs come from the user's Home Assistant or the weather provider and are not translated by this integration.** Actual spoken language still depends on the installed TTS voice.

Locale sources are in `custom_components/environment_manager/locale_pack_*.py` and the reviewed, centralized `config_i18n_overrides.json` file. After editing either source, run `python generate_translations.py` and `python -m pytest -q tests/test_config_i18n_audit.py`. The generator applies the localized configuration overrides, then the optional mold-room translations, **last**, so it cannot silently restore English helper text. Native-speaker improvements are welcome.

### Config-flow translation quality assurance

The full UI localization audit checks **all seven setup/Reconfigure sections**: Rooms, Window sensor exclusions, Per-room indoor sensors, Outdoor air, Weather/warnings, Announcements and Advanced thresholds. It also covers every helper description, every validation/abort message, the independent Options menu and dropdown option labels.

For example, the Greek Weather page explains directly that at least one weather provider is required, that unsafe weather prevents opening, and that active/unavailable warnings block opening. German, French, Spanish and the additional language packs receive corresponding localized instructions. [Audit details](TRANSLATION_AUDIT.md).

## Guided configuration and reconfiguration

**Initial setup** starts with Rooms, then window exclusions, followed by the remaining guided steps:

1. **Areas / rooms (multi-select).** Start by choosing which rooms to monitor. Rooms with Window-class `binary_sensor` contacts are suggested and automatically preselected. Window-class `cover` entities are never considered window contacts. You can remove unwanted rooms before continuing.
2. **Window sensor exclusions (multi-select).** Next, review recognized window contacts. Likely thermostat-derived or virtual window signals are preselected for exclusion; uncheck any actual window contacts or add other exclusions. If these exclusions remove the last usable contact from a selected room, setup returns to Rooms for review. If all contacts would be excluded, setup explains that at least one must remain. Your choices—including an explicitly empty exclusion list—are saved.
3. **Indoor air-quality exclusions (one page per selected room).** Each room with supported indoor sensors has its own multi-select. Available candidates include **humidity, CO₂, US AQI, PM2.5, PM10, total VOC mass concentration and VOC parts concentration**, using only the supported device classes or recognized sensor IDs with compatible units. Options show **device name › entity name · measurement · entity ID**; entities without a registered device still show entity name, metric and ID. Select sensors to **exclude** from that specific room; **leave empty to monitor them all**. On reconfiguration the saved exclusions are checked. Previously excluded but now missing sensors remain selectable, so you can remove obsolete exclusions. Rooms without supported indoor sensors are skipped rather than showing a useless blank menu.
4. **Outdoor air quality.** Select recognized outdoor entities not associated with monitored rooms. Unknown, unavailable and stale readings are reported as missing, not treated as dangerous. Valid high readings still block opening.
5. **Weather and warnings.** Select one or more `weather.*` entities and optional recognized warning sensors. Unsafe weather and active or unknown warnings block window opening.
6. **Announcements (optional).** Configure spoken/visual delivery, language and optional [Announcement Hub](https://github.com/Chreece/HA-Announcement-Hub) routing. Advanced thresholds are edited separately through Configure.

Indoor exclusions and mold calibrations are stored **by Home Assistant area**, used for both recommendations and the dashboard snapshot. An excluded indoor sensor remains available in Home Assistant; the integration does not disable, delete or modify it. Areas with no remaining active indoor measurements are shown as **unknown**, never silently marked safe. Only the single existing window-recommendation entity is generated.

For an installed integration, open **Settings → Devices & services → Integrations → Home Environment Manager → Configure**. A translated menu lets you choose exactly which section to edit: Rooms, Window sensor exclusions, Per-room indoor air sensors, Outdoor air sensors, Weather and warnings, Announcements, or Advanced thresholds. Only the selected section opens. Indoor sensor exclusions continue room by room, but every other section saves immediately without forcing the rest of setup. Your saved selections are prefilled; cancelling leaves existing settings unchanged. The full flow uses the same five Home Assistant UI languages (English, German, Greek, French and Spanish).

### Mold indication instead of RH (optional)

Check **Use mold indication instead of raw room RH** on the first **Rooms** setup page. The legacy 65% room-RH rule remains unchanged until you enable it. When enabled, the Advisor **prefers** the estimated relative humidity **at the coldest surface** (default trigger 70%); when mold estimation is unavailable, it **automatically falls back to the valid room RH average** (default trigger 65%). Both limits can be changed independently in **Advanced thresholds**. The mold indicator is a moisture/mold-growth indication, not a probability of having mold.

For each room, first open **Weather and warnings** (second option in **Configure**) and choose a weather entity providing a current `temperature` attribute (°C/°F). The Advisor reads this attribute as outdoor temperature; it does **not** obtain temperature from the humidity sensor or the outdoor air-quality/pollution sensors. Then open **Room settings — indoor air and mold** (third option in Configure), choose a room temperature sensor (°C or °F), and measure the room's **coldest wall surface**, usually an outside corner or window frame, with a contact/infrared thermometer. Enter the measured critical-point temperature in **°C**. Measure at the same time as the room temperature sensor and selected weather entity's outdoor temperature. They should differ by at least 3 °C for a stable calibration. The integration calculates the same factor as Home Assistant's [Mold Indicator](https://www.home-assistant.io/integrations/mold_indicator/):

```text
calibration_factor = (temperature_indoors - temperature_outdoors)
                   / (temperature_coldest_surface - temperature_outdoors)
estimated_surface_temp = temperature_outdoors
                       + (temperature_indoors - temperature_outdoors) / calibration_factor
```

Until the coldest-surface measurement is entered, the mold indication is unavailable. **If there is at least one valid room RH reading, the card now displays an active RH fallback reading and its own 65% threshold**. The fallback is always an average of available valid room RH sensors, never a mold surface-humidity percentage. The room remains **partially verified (not green/safe)** while mold is missing; PM2.5, AQI, CO₂ and VOC continue independently. An RH average at or above its threshold can still recommend opening a closed window when outdoor conditions are suitable.

On the dashboard, the compact mold gauge uses readable labels, for example **“Μέση υγρασία: 55% · 2 αισθητήρες”** and **“Εκτιμώμενη επιφάνεια: 17,1°C”** in Greek. The count is the number of valid room RH sensors, **not** the calibration factor. Select **More details** for the room—even when it has only three measurement cards—to view the saved **calibration factor** and the current indoor/outdoor temperatures used by the estimate. The factor is preserved at full floating-point precision in the sensor's dashboard metadata; the card formats it to up to six decimal places (minimum two) without changing the calculation.

The room's humidity sensors are discovered and filtered through the normal per-room exclusion list. **Only valid RH readings above 0% and at most 100% are averaged**; `unknown`, `unavailable`, out-of-range, NaN, stale and excluded readings do not contribute. The indoor average and the room/outdoor temperatures determine dew point and estimated surface RH via the Magnus formula. The dashboard shows the calculated indicator, number of valid RH contributors, their average and estimated surface temperature.

The original calibration factor is **preserved** when sensors, conditions or excluded entities change, including the particular selected weather source used for that calibration. If that weather entity is removed or stops providing temperature, the mold estimate becomes unavailable and reports the missing outdoor temperature instead of silently using another source; **the room switches to its valid averaged RH fallback when possible**. Use **Recalibrate** only after physically measuring the surface again. If indoor temperature, outdoor temperature or calibration is missing, the mold reading remains unavailable; an RH fallback works as long as at least one valid RH reading exists. With no valid RH, neither humidity method can trigger ventilation. Bad weather continues to take priority and requires closing any open monitored windows.

During initial setup, the wizard already selects **Outdoor air** and **Weather and warnings** before the per-room cold-surface calibration. On an existing installation, select **Configure → Rooms** to enable mold mode, then **Configure → Weather and warnings** (second menu option) to verify that a weather entity provides outdoor temperature, followed by **Configure → Room settings** (third option) for each room.

If calibration, room temperature, weather temperature, usable nonzero room humidity, or the mathematical estimate is missing, the room card displays a separate actionable warning for each missing input; the recommendation sensor also exposes `mold_input_warnings` and detailed `diagnostics` attributes. Bad weather and missing data do not suppress these warnings. The card explicitly says **RH fallback active** with its current mean and threshold when available. A missing mold input **alone** does not generate a spoken announcement, but a valid averaged RH measurement crossing the ventilation threshold can produce the existing delayed open-window recommendation and optional announcement. Incomplete calibration does not falsely mark a room safe.

### Supported indoor and outdoor measurements

| Measurement | Supported unit(s) | Outdoor good at or below | Indoor requires ventilation at or above |
|---|---|---:|---:|
| AQI — **US scale 0–500** | index / none / AQI | 50 | 100 |
| CO₂ | ppm | 800 | 1,000 |
| PM2.5 | µg/m³ or mg/m³ | 15 | 25 |
| PM10 | µg/m³ or mg/m³ | 45 | 45 |
| Total VOC | µg/m³ or mg/m³ | 500 | 500 |
| VOC concentration (parts) | ppb or ppm | 500 ppb | 500 ppb |
| Relative humidity (legacy mode) | % | — | 65% |
| Averaged room RH fallback (mold unavailable) | % | — | 65% |
| Mold indication (opt-in, available) | estimated surface RH, % | — | 70% |

Sensor values are normalised to the units above. Outdoor temperatures from weather entities must remain from **5–32 °C**, humidity at most **85%** and wind at most **35 km/h** when those attributes are provided. Supported fair weather states: `sunny`, `clear-night`, `partlycloudy`, `cloudy`. All other states, including rain, snow, thunderstorms, fog and high wind, block opening. Selected warnings that are active **or cannot be verified** also block opening. Weather providers with unknown state block opening. Selected outdoor data older than 90 minutes (using `last_reported` when available) are reported as unavailable, without blocking opening. Adjust the freshness interval by checking **Edit advanced thresholds** on the announcements page.

**AQI scales differ internationally.** A European 1–5 index is *not* the US 0–500 AQI. For 1–5 index sensors, change the outdoor AQI limit (for example `2`) and indoor AQI trigger (for example `3`) using **Edit advanced thresholds**, or use the measured pollutant sensors instead. Numeric thresholds are configurable per installation, not per sensor, and do not represent exposure-duration standards.

### Decision policy

| Outdoor state | Indoor state and windows | Recommendation |
|---|---|---|
| Good, no selected warnings | Indoor CO₂/particles/VOC/AQI/humidity exceed a threshold and all room windows are closed | **Open** the room's recognized windows, with the measured reason |
| Bad, rainy, extreme, warning active or unknown | Any recognized window is actually open | **Close** each open window, with outdoor blocker(s) |
| Good | Room already has a window open | No further open action (ventilation already underway) |
| Good | Indoor values acceptable | `idle` |
| Missing weather or unknown weather-warning status | No windows verified open | `blocked`; no open recommendation |
| An outside air-quality sensor is unknown/unavailable | Otherwise good known conditions | No blocker from that sensor; diagnostics show missing data |
| No room sensor or window contact | Missing information | No guessed recommendation; diagnostics attribute identifies the gap |

Only **non-excluded** `binary_sensor` entities with device class `window` count as windows. A `cover` is never counted, even if its device class is `window`. Excluded entities are ignored by room suggestions, window counts, open/close recommendations, automatic announcements, and the dashboard. The automatic suggestions are based on entity and device metadata, **not a guaranteed physical-contact identification**; review them for your hardware. Missing outside readings do not themselves block opening/require closure, but appear in `unavailable_outdoor_sensors` and set `outdoor_data_complete: false`. Missing weather or an unknown weather-warning status still blocks opening.

## Home Environment Manager dashboard card

<p align="center"><img src="https://raw.githubusercontent.com/Chreece/HA-Home-Environment-Manager/main/.github/assets/dashboard-card-preview.svg" alt="Illustrative Home Environment Manager Lovelace card with outdoor weather, safe rooms, attention counts, sensors and windows" width="100%"></p>

**Add it from the dashboard card picker**: Edit your dashboard → **Add card** → **Home Environment Manager**. The integration registers the card JavaScript automatically after a Home Assistant restart, and the card discovers the recommendation sensor if you have exactly one Home Environment Manager instance. The card picker also suggests it for your recommendation entity. A built-in graphical editor lets you select the sensor, rename the card and toggle the outdoor panel and detailed metrics.

The equivalent YAML is:

```yaml
type: custom:air-quality-advisor-card
# Optional when exactly one Home Environment Manager integration exists:
entity: sensor.air_quality_advisor_window_recommendations
# Optional card settings:
show_outside: true
show_metrics: true
```

Use the actual entity ID from **Developer tools → States** if it differs from the example. The card reads `attributes.dashboard` from the integration's **single existing recommendation sensor**; it creates **no additional entities** and never controls windows. It works in Sections and masonry dashboards, light/dark themes, phones and desktop. It shows:

- An **outdoor status panel** with the current weather, temperature, wind, humidity, selected outdoor pollution readings and warnings. *Unsafe* means a known hazard; *unknown* means required weather/warning information is missing; *partial* means a selected air sensor is unavailable even though available readings do not block ventilation.
- A **donut chart and totals** for rooms marked **Good**, **Needs attention** and **No data**. Rooms with high indoor pollutants, or an urgent close-window recommendation, require attention. Rooms with missing measurements or unknown window contacts are never counted as good. Already-open windows with bad indoor air remain visible as requiring attention.
- **Room panels** with CO₂/PM/AQI/VOC/humidity gauges against the thresholds in your integration settings, plus actual window contacts and open/close recommendations. Extra readings can be expanded without leaving the dashboard.

The card automatically uses **Home Assistant's per-user interface language** (`hass.language`), not the separately configured announcement language. It includes native text for English, German, Greek, French, Spanish, Italian, Dutch, Portuguese, Polish, Russian and Turkish; unsupported languages fall back to English. Sensor names and room names remain as named in Home Assistant.

If the card doesn't appear after updating via HACS, **restart Home Assistant**, reload the browser and reopen the card picker. It also exposes a normal JS resource endpoint at `/air_quality_advisor/air-quality-advisor-card.js` for installations where automatic frontend loading has been disabled; there is no need to copy it to `/config/www`.

## Building-physics and exposure diagnostics

Home Environment Manager also derives **optional, deterministic environmental context** from
real Home Assistant measurements. The existing window safety rules, weather alerts
and Announcement Hub routing remain authoritative. These are **engineering
indicators**, not a medical assessment, building certification, or an automatic
window actuator.

| Indicator | Inputs | Interpretation and limits |
| --- | --- | --- |
| Moisture and drying potential | Indoor air temperature + relative humidity and one valid outdoor weather temperature/RH source | Actual vapor content in g/kg dry air; positive drying potential means outside air carries less water. Shows predicted RH if outside air were warmed indoors without adding vapor. Cold 90% outdoor RH can still be drying. |
| Adaptive comfort | Indoor temperature and **at least seven days** of sufficiently complete outdoor temperature samples | Indicative ASHRAE 55 80% band, only relevant to naturally conditioned spaces with occupant-controlled windows. Room air temperature is a proxy for operative temperature, *not proof of compliance*. |
| Passive cooling and energy | Above comfort inputs and indoor/outdoor temperature difference | Opportunistic cooling only when outdoor safety policy also passes; approximate Wh **per cubic meter for one complete air exchange**, not measured heating energy or savings. |
| Condensation and mold moisture exposure | Indoor temp/RH and optional existing calibrated mold surface temperature | Dew-point/surface margin and recorded hours at estimated surface RH ≥80%. Not a VTT mold index, mold probability, or verified wall measurement. |
| 24-hour particles | PM2.5 and PM10 sensors | Time-weighted average with at least 80% observed coverage and no bridging gaps over 15 minutes. Shows WHO 2021 **24-hour** references (15/45 µg/m³), not instantaneous exposure compliance. |
| CO₂ slope and tentative ACH | Real indoor/outdoor CO₂; open window contact; a confirmed vacant-state sensor | Trend requires at least 10 minutes of observations. ACH requires a vacant, open-window decay interval with sufficient measurements; occupancy uncertainty or no measured outdoor CO₂ means *no ACH estimate*. True NDIR sensor technology must be independently verified. |
| Observed nighttime overheating | Valid room temperature, local timezone, 7 days of samples | Hours above 26°C between 22:00 and 07:00, reported only with adequate coverage. **Not** a CIBSE TM59:2026 design-stage assessment. |

### Sensor selection, accuracy and persistence

The advisor automatically discovers an indoor temperature sensor **only if exactly
one current valid candidate exists in a room**. When there are several, it uses
the explicitly configured temperature sensor from that room's mold calibration
(if present); otherwise temperature-dependent metrics remain unavailable rather
than randomly combining sources. Outdoor psychrometrics similarly require
one unambiguous current weather temperature source with relative humidity.

The historical indicators start in a **warming-up / insufficient-coverage** state.
The integration saves a compact, capped collection of room observations in
Home Assistant's **local storage**, retaining up to eight days and sampling at
most every five minutes except when window/occupancy state changes. To calculate
conditional ACH, the local history includes the occupancy boolean and window
contact state. No cloud analytics are used. Changes to HA Recorder retention do
not automatically delete the separate bounded history storage.

Missing, stale and physically implausible CO₂/RH readings remain unknown; a
measurement labeled CO₂ does **not** establish that the hardware contains an
NDIR sensor. Outdoor PM2.5 = 15 and PM10 = 45 in the legacy configurable
instantaneous decision rules remain operational screening cutoffs and must
not be described as WHO 24-hour guideline compliance. Humidity-only opening
is suppressed when reliable current paired readings indicate that outside air
contains *more* vapor. This does not override rain, wind, cold-weather or
severe-weather safety restrictions.

These diagnostics are available inside the existing room dashboard's
**Building physics** section and in the recommendation sensor's
`dashboard.rooms[].environment` attributes; no extra devices are created.
The card shows German, Greek and English labels, with English fallback for
additional locales.

**Scientific references:**
[ASHRAE Standard 55](https://www.ashrae.org/technical-resources/bookstore/standard-55-thermal-environmental-conditions-for-human-occupancy),
[ISO 13788](https://www.iso.org/standard/51615.html),
[WHO 2021 global AQ guidelines](https://www.who.int/publications/i/item/9789240034228),
[EPA indoor sensor limitations](https://www.epa.gov/indoor-air-quality-iaq/low-cost-air-pollution-monitors-and-indoor-air-quality),
[CIBSE TM59:2026](https://www.cibse.org/knowledge-research/knowledge-portal/tm59-overheating-risk-in-dwellings-a-design-stage-methodology-2026).

**Not implemented as a purported validated result:** Fanger PMV/PPD (would require
measured radiant temperature/air speed and supplied clothing/activity inputs),
Finnish VTT mold index (requires surface moisture history *and* verified
material properties), or reliable heat-loss prediction without measured
airflow/room geometry. Rather than manufacture these quantities from weather
and RH alone, the advisor displays only the defensible indicators above.

## The single backward-compatible recommendation sensor

<p align="center"><img src="https://raw.githubusercontent.com/Chreece/HA-Home-Environment-Manager/main/.github/assets/recommendation-preview.svg" alt="Illustrative Home Environment Manager close-window recommendation" width="100%"></p>

Typical state when CO₂ is high but outdoor air and weather are good:

```yaml
state: open
attributes:
  outdoor_safe: true
  outdoor_data_complete: true
  unavailable_outdoor_sensors: []
  open_windows:
    - binary_sensor.living_room_window
  close_windows: []
  recommendations:
    - action: open
      area_id: living_room
      area: Living room
      windows:
        - binary_sensor.living_room_window
      reasons:
        - code: inside_co2
          entity: Living room CO₂
          value: 1,200 ppm
      message: "Open Living room window in Living room: Living room CO₂ is high (1,200 ppm). Outdoor conditions are suitable."
```

The system automatically updates this entity. You can display `recommendations`, `open_windows`, `close_windows` and `outside_blockers` in dashboards or automations. No duplicate per-area sensors.

## Repeating persistent window recommendations

Under **Home Environment Manager → Configure → Announcements**, set **Repeat announcements (minutes)** to any whole number from **0 to 1440**. The default is **10 minutes** for new and existing installations; **0 means never repeat**. This applies only if automatic notifications or automatic TTS are enabled. Manually invoked announcements are not scheduled for repetition.

- A **new open-window** recommendation still waits 90 seconds for stable conditions; a **close-window** recommendation is announced immediately. Repeats run at the configured interval **after the previous automatic submission finishes**, so slower AI/Hub calls do not cause overlapping reminders.
- A reminder is sent only while **the same room, window action and cause remain actionable**. Before each reminder, the sensors and window contacts are checked again. When the window is opened/closed or air/weather conditions recover, remaining timers are cancelled.
- Each monitored **room has its own reminder timer**. A CO₂ value fluctuating above its threshold does not reset the timer, but a different sensor reason or weather category starts a fresh interval. The existing 15-minute anti-flapping cooldown applies only to newly reappearing open-window recommendations; it **does not block timed reminders**.
- On Home Assistant restart, an already-urgent close recommendation still announces immediately; an existing open recommendation receives its first reminder after one full repeat interval rather than immediately on boot.

The setting works with Announcement Hub, direct TTS, native notification entities and persistent Home Assistant notifications. It does not alter pollutant thresholds, AI permissions or actual window control.

## AI-enhanced announcements and fallback

Open **Home Environment Manager → Configure → Announcements**. **Use AI for announcements** is a single checkbox for both routes, off by default. The automatic notification and TTS switches still independently control whether anything is announced. Existing saved AI settings are preserved during upgrades.

- **Announcement Hub selected:** This checkbox sends an explicit `use_ai: true` (or `use_ai: false` when unchecked) with the room-specific `notify.announcement_hub` action. A custom conversation agent is forwarded as `ai_agent`; leaving **Home Assistant default** selected omits the field so the Hub uses its own configured agent. The Hub performs the rewriting and controls delivery; the advisor does not rewrite the same message again.
- **Announcement Hub not selected:** The advisor uses `conversation.process` to rewrite the original text before sending it to direct `notify.send_message` and/or `tts.speak` outputs. The agent choice defaults to Home Assistant's default conversation agent; other `conversation.*` entities can be selected. Failed or invalid rewrites use the unchanged original message (up to eight seconds for opening and three seconds for urgent closing recommendations).

**When the Hub option appears:** It is offered **only if Announcement Hub has a Home Assistant configuration entry**. Merely having an action named `notify.announcement_hub` is not enough. If Hub is removed, unconfigured, stopped or not loaded, Advisor uses native Home Assistant delivery instead. **When Hub is running**, Advisor forwards the recommendation and actual Home Assistant area display name, then stops: even if Hub rejects the request, cannot route it, returns no acknowledgement, or exceeds the acknowledgement safety timeout, **Advisor does not create any native notifications or TTS**. A rejected Hub job is reported in the manual action response and logged, **not falsely counted as queued**. Resolve the routing problem in Announcement Hub, not by broadcasting from Advisor.

**Fallback order, used ONLY without a running Hub:** configured `notify.send_message` outputs and/or `tts.speak` engines/players → built-in `persistent_notification.create` (one updated notification per room) if nothing was delivered. A persistent notification is **visual only**. Hub owns its own queue and delivery once it is running; Advisor never duplicates failed Hub routes or AI jobs with a persistent Home Assistant notification.

**AI safeguards and privacy:** Window/room selection, weather limits, sensor reasons and alert timing stay deterministic. The advisor validates direct AI text to preserve the action, room, window names and measurements; failures fall back to the original message. Home Assistant conversation agents can have device-control privileges and may execute tools even when asked to rewrite text only. Use a text-only/low-permission agent, and review cloud-agent data sharing (room and window names and sensor readings can leave your Home Assistant). The built-in non-generative Assist agent may not rephrase arbitrary text.

## Announcing in a different language on each action

```yaml
action: environment_manager.announce
data:
  language: el  # any supported locale, e.g. el, de or pt-BR
  channels: both  # both, tts, notification
  areas:
    - living_room
```

Omit `areas` to report every room with an actionable recommendation. The manual action can be called even when automatic TTS/notifications are disabled. Passing `language` changes the **generated recommendation text** and requests the matching speech language. Actual spoken voice availability depends on the selected TTS provider. The service may report accepted/submitted requests; this does not guarantee a physical speaker played audio or a notification was displayed.

Announcement Hub delivery uses the established action:

```yaml
action: notify.announcement_hub
data:
  text: "Schließe das Fenster in Küche wegen schlechten Wetters."
  area:
    - Küche  # HA area display name, not internal ID 'kouzina'
  level: warning
  use_ai: true
```

When both channels are enabled, Advisor submits the common `text` field, exactly as in this example. For notification-only or TTS-only settings it sends `text_notify` or `text_tts` respectively so the other channel is not silently activated. In every case, `area` uses the **actual Home Assistant area name** from the Area Registry (`Küche`), while Hub resolves that name back to its internal area ID and decides which devices/routes are eligible. Advisor does **not** override `occupied_only` or manually choose notification or audio devices. The example text is illustrative; live messages contain the real room, window names and sensor reasons.

**Important:** Sending `Küche` instead of `kouzina` makes the handoff readable, but does not create a missing Hub output. If Hub reports `The selected text has no configured matching output`, **configure room/global delivery in Announcement Hub**; Advisor will report the refusal without an unwanted native Home Assistant event notification.

## Testing, validation, and publishing

```bash
python -m pytest -q tests
python -m compileall -q custom_components
bash ./publish.sh
```

`publish.sh` is an optional local publishing script requiring an authenticated GitHub CLI (`gh auth status`). It **never force-pushes** or mutates other repositories. **GitHub Actions automatically validates every completed push to `main`** and creates a new GitHub/HACS Release after Python, JavaScript, translation, HACS and Hassfest checks pass. Superseded commits and already published version tags cannot create duplicate releases. Push the complete code, translations and release notes with matching manifest and release-request versions; no manual action is required. Manual validation remains available through [Actions → Validate and release (after push)](https://github.com/Chreece/HA-Home-Environment-Manager/actions/workflows/validate.yml), without publishing by default. See [RELEASING.md](RELEASING.md).

## Opt-in PID climate control (v0.5.0)

Home Environment Manager can now **control explicitly authorized Home Assistant
`climate.*` entities** using a bounded supervisory PID controller.

**Important:** Unlike a direct compressor or heater relay PID, this is an
*outer-loop thermostat setpoint regulator*. It changes only
`climate.set_temperature` with a single `temperature` value.
It never sends `climate.set_hvac_mode`, `climate.turn_on` or `climate.turn_off`.
The climate device retains its own safety protections and compressor cycling.
Not all thermostat models support safe nested PID control; test behavior carefully.

### Configure a room

Open **Settings → Devices & services → Home Environment Manager → Configure
→ Climate PID**. Choose one monitored room, then provide:

| Input | Why it is required |
| --- | --- |
| Enable PID | Explicit opt-in; disabled for every existing and new room by default. |
| Authorized climate devices | Select only the target `climate.*` entities that are allowed to be controlled in this particular Home Assistant room. No area-wide service broadcast. |
| Independent room temperature sensor | Required current `sensor.*` measurement, normalized from °C or °F; older than 10 minutes stops control. |
| Existing HVAC mode | Choose heat or cool; the physical thermostat must already be in that mode. No automatic mode or compressor switching. |
| Desired room temperature | Current fixed room-temperature goal in °C. |
| Pause when window open/unknown | Enabled by default. Open or unknown window contacts suppress commands without turning climate hardware on or off. |

The next **Advanced PID tuning** page contains Kp, Ki and Kd gains, the
maximum permitted setpoint trim, minimum/maximum thermostat targets, sample
interval, maximum step change and minimum meaningful change. Defaults are
conservative: **300 seconds per cycle, up to 0.5°C change per cycle, 1.5°C
maximum trim**. The controller waits for enough fresh measurements before its
first command.

Kp is measured in percentage points of PID demand per °C; Ki in percentage
points per (°C·minute), and Kd in percentage points·minute per °C. The derivative
is taken from observed room temperature, and an anti-windup guard prevents
further integral growth into a saturated output. Demand maps into a heating
setpoint between `target` and `target + offset`, or a cooling setpoint
between `target - offset` and `target`. It is not a compressor duty cycle.

### Manual controls and failure safety

- A user changing thermostat target or HVAC mode pauses that room's PID.
  Such pauses are saved across Home Assistant restarts; the user must explicitly
  resume after checking the current thermostat state.
- Use the **Pause PID / Resume PID** button on the room's Lovelace card or
  the action `environment_manager.pid_control` with an explicit
  `area` and `action: pause | resume | reset`. Reset clears PID history and
  remains paused until separately resumed.
- Missing or stale sensor input, open/unknown windows, active thermostat presets,
  unsupported single-setpoint devices, wrong-area targets, duplicate climate
  assignments and invalid device units cause control to stop rather than guess.
  A Home Assistant service-write failure requires manual resume.
- Thermostat setpoint acknowledgements are checked against the exact entity
  selected. Unacknowledged writes or an unexpected manual setpoint change
  result in a persistent pause, not repeated commands.
- An integration reload cancels pending PID tasks. PID calculations and
  manual pause state use local Home Assistant storage and do not require a cloud
  controller. Restored PID state is never used to power on or restart hardware.

All existing sensor entities, native announcement actions, room calibration,
environmental-science observations and Lovelace card identifiers are preserved.
One room may control multiple explicitly selected thermostats, but the same
climate entity cannot be assigned to more than one enabled PID room.

**Safety:** Home Environment Manager is not a certified heater, boiler,
compressor, frost-prevention or life-safety controller. Leave independent
hardware overtemperature/frost/compressor protections in place. It is not
recommended to put medical, industrial or freeze-sensitive loads under this
experimental supervisory controller without independent safeguards. No climate
commands are sent until the user enables PID for that room.

## Climate room profiles and automatic control (development branch)

The next Home Environment Manager climate update builds on v0.5.0's
conservative thermostat-setpoint PID. It distinguishes **four controller
strategies by actual Home Assistant capabilities**, rather than equating a
thermostat with a relay:

| Equipment and strategy | Commands | Hard limitations |
| --- | --- | --- |
| Built-in thermostat (`climate.*`) | `climate.set_temperature`; optionally `climate.set_hvac_mode` | Requires TARGET_TEMPERATURE support. Automatic heat/cool mode changes need a *second* explicit opt-in, minimum mode dwell and acknowledgement. An OFF thermostat is not restarted. |
| Native heat/cool range thermostat (`climate.*`) | `climate.set_temperature` with both `target_temp_low` and `target_temp_high` | Requires TARGET_TEMPERATURE_RANGE feature and an *already active* `heat_cool` mode; preserves device's compressor safety, bounds both setpoints and pauses on manual range changes. |
| Existing v0.5 setpoint PID (`climate.*`) | Rate-limited `climate.set_temperature` only | Can never run alongside another enabled room controller. |
| Non-compressor heating/cooling relay (`switch.*`) | `switch.turn_on`/`turn_off` | Explicit non-compressor/independent-protection attestation, room ownership, hysteresis, minimum ON/OFF intervals and maximum ON watchdog. |
| Slow thermal PWM relay (`switch.*`) | Bounded time-proportioning ON/OFF | Only loads documented as safe for repeated switching; fixed PWM period and minimum pulse durations. **Never attach a compressor or unprotected resistive heater.** |
| True proportional actuator (`number.*`) | `number.set_value` | Sensor must expose a verified 0–100% output with unit `%`, range 0–100 and valid step; rate-limited commands. |

A `climate.*` entity that only exposes heat/off control is **not** assumed
to be safe for rapid relay PWM. Direct actuators must be assigned to the
actual HA room, with explicit heat/cool output selectors and confirmation of
hardware type. The integration does not discover or infer compressor safety.

### Configure temperatures, occupancy and schedules

Open **Home Environment Manager → Configure → Climate**. For each monitored
room:

1. Select a real temperature sensor, controller strategy and target devices.
   Enable the room and then separately authorize actuator commands if wanted.
   Optional automatic native heat/cool switching is another distinct setting.
2. Select a subset of occupancy sensors or leave it empty to use **all
   Home Assistant presence/occupancy binary sensors assigned to that room**.
   Any occupied sensor wins. All known-off sensors must remain off for the
   configured vacancy delay before an unoccupied setback takes effect.
   Stale/unknown readings do not automatically prove vacancy.
3. Choose any supported `person.*`, `device_tracker.*`, or explicitly
   selected home-presence `binary_sensor.*` entities for whole-home
   home/away decisions. A named zone such as work is considered away.
4. Configure an optional **local-time sleeping schedule**, manual profile
   override, and your desired temperature control basis.
5. Set **separate heating/cooling bands** for *home, unoccupied, away
   and sleep*. Heat and cool thresholds must remain separated by a deadband;
   mode changes are filtered through hysteresis. The default example
   setpoints (20/26°C at home, 18/28°C unoccupied, 16/30°C away and
   18/26°C sleeping) are only starting points, not universal comfort targets.
6. If choosing a relay, PWM or proportional driver, a separate **Direct
   Actuators** page collects exact entities, hardware attestation,
   minimum-on/off times, maximum runtime and applicable PID/PWM bounds.

Each room is configured independently. All global and local settings work
with any supported Home Assistant provider and local timezone; no German,
Greek or other national integration is hardcoded.

### Optional scientific comfort targeting

Two target-selection modes are supported:

- **Temperature:** use the explicit profile heating/cooling bands.
- **ISO 7730 PMV:** when enabled in the room's advanced environmental
  measurements, require a genuine mean radiant temperature, humidity,
  measured/explicit air speed, clothing insulation (clo), and activity (met).
  The bundled dependency-free Fanger implementation solves a bounded air
  temperature corresponding approximately to PMV 0. The correction to the
  owner's chosen temperature bands is capped; without valid current physical
  inputs the fixed profile targets remain in force. No PMV-based correction
  is applied to away/unoccupied setbacks.

ISO 7730 is a *population thermal-comfort model*, not a personalized
guarantee. A PMV-derived target assumes the other model inputs stay fixed;
actual indoor radiant temperature and airflow can change with HVAC operation.
See the [pythermalcomfort model documentation](https://pythermalcomfort.readthedocs.io/en/stable/documentation/models.html).

### Safety and scope

Direct actuator control requires real-world commissioning. The code contains
restart-persistent manual pauses, output acknowledgement, explicit room/device
ownership, heating/cooling interlocks, short service-call timeouts, a
maximum-on safeguard and best-effort safe-off on controller pause or reload
for devices it previously operated. Unowned active outputs are *not* silently
overwritten. If a relay cannot be verified OFF or an integration becomes
unresponsive, hardware cutouts remain indispensable.

The v0.6 development controller now **durably records direct ON/positive-percent
intent before issuing a relay, PWM or proportional actuator command**. Interrupted
writes, missing/corrupt safety history and failed acknowledgement persistence
fail closed; the controller does not automatically repeat uncertain ON commands.
Resuming an interrupted ON requires the exact output to be verified OFF for
the configured minimum-OFF dwell, followed by startup settling. Changes to the
assigned actuator, safety timing, device permissions or room removal cause a
bounded best-effort shutdown of the *previously confirmed owned* output. An
output moved to another Home Assistant area or claimed by another config entry
is not touched automatically; manual reconciliation is required. Physical
cutouts and supervised equipment commissioning remain necessary.

**This v0.6 climate expansion is published as an opt-in beta, not a
stable update.** Integration and simulation tests must pass before
publication, followed by controlled testing with representative actual
hardware. Direct relay/PWM modes are for slow, safely protected thermal
loads; they must not control compressor power circuits or serve as the sole
frost/overtemperature protection.


### Multi-device room equipment (v0.6 development branch)

The **Climate** options now include an additional equipment page. You can
assign a dedicated heating climate (such as a radiator), cooling climate
(such as an AC or reversible heat pump), native DRY/FAN_ONLY climate entities,
a humidifier, dehumidifier, extraction fan and purifier fan. The wizard
restricts options to the selected Home Assistant area and can select a single
known humidity sensor for configurable humidity bands and hysteresis.

Each candidate is checked against its actual Home Assistant `hvac_modes`,
`supported_features` or humidifier `device_class`. The planner identifies
active opposing heating/cooling, missing measurements and ownership conflicts
if a device is assigned to multiple rooms. Climate-only rooms need not have a
window contact; existing monitored rooms still block control if their required
window contact disappears.

**Native humidity setpoint (extra opt-in):** With climate actuation and
**Allow native humidity setpoint changes** enabled, the integration may
adjust the target on an already-on selected `humidifier.*` or
`dehumidifier.*`. It requires a fresh, explicitly chosen same-room humidity
sensor, the verified device class and native limits. Commands are bounded,
rate-limited and acknowledged; manual target changes suspend control until
explicit resume. It never turns the device on or off or changes its mode.

**Remaining limits:** The existing primary thermostat retains its own native
heat/cool control. Additional devices require their own explicitly commissioned
native or guarded controller. DRY/FAN_ONLY monitoring remains advisory
by default; the draft has a separately authorized transition driver, but
no unverified device mode or compressor-power commands are permitted. Actual
hardware commissioning and restart tests are still mandatory before releasing
v0.6.

## Known limitations

- Only the named supported metric/device classes and units are interpreted. Unrecognized AQI variants, CO/ozone/NO₂/SO₂, arbitrary provider attributes and event-based weather alerts are not guessed at. Add a normalized HA template sensor where necessary.
- The thresholds apply to individual current readings, rather than averaging over standardized pollutant exposure windows. Relative humidity alone does not account for absolute outdoor humidity; the advice is a useful home automation signal, not a guaranteed best ventilation strategy.
- Advisory window names/rooms depend on HA registry assignments. If window contacts are missing, a recommendation cannot name a window.
- Direct TTS is a standard `tts.speak` call and may interrupt the chosen media player; use Announcement Hub for its queued/synchronized room audio policies.
- Dynamic Home Assistant environment tests (config flow and live TTS/notifications) require a Home Assistant instance; the included automated tests cover the pure policy, not all integrations/providers.

## License

MIT © 2026 Chreece

## Project status, compatibility and releases

- **Home Assistant 2026.10+**; modern UI config/options flow and a bundled Lovelace dashboard card. The component ships local `custom_components/environment_manager/brand/` assets for Home Assistant 2026.3+ as well as repository-level HACS assets.
- **HACS custom integration repository:** `hacs.json`, `manifest.json` and conventional `custom_components/` layout are included. Public HACS catalog inclusion is a separate community-review process.
- **Validations:** `pytest`, static syntax checks, JSON checks, HACS action and Hassfest run automatically on each completed push to main (plus optional manual validation). Actual platform compatibility and output delivery require a Home Assistant integration test; see the [release checklist](RELEASING.md).
- **Versions:** see [CHANGELOG.md](CHANGELOG.md). This release is a first testable version, not an independently verified stable integration. No automatic window opening/closing is performed.

## Support this project

If this integration helps, you can support ongoing development on [Ko-fi](https://ko-fi.com/chreece). Contributions and bug reports are welcome through the repository's [issues](https://github.com/Chreece/HA-Home-Environment-Manager/issues).


### Home Assistant Python 3.14 installation (v0.5.1)

The v0.5.1 production hotfix removes the required `pythermalcomfort`/
Numba/`llvmlite` installation chain. `pmv_core.py` uses a compact,
reference-tested ISO 7730 Fanger scalar implementation without binary
scientific dependencies, preserving advanced thermal comfort calculations
in Home Assistant's Alpine/musl Python 3.14 environment. The experimental
v0.6 climate-device controls are available only when the prerelease is deliberately selected.


### Multi-device climate status in the Lovelace room panel (v0.6 draft)

The room's climate panel now reports **primary thermostat**, **secondary
heating/cooling**, and **native humidity target supervision** separately.
Selecting a secondary AC no longer makes the primary thermostat's hold
status appear as if all climate control has failed. The selected equipment,
room humidity evidence and pause/resume state remain visible with English,
German and Greek labels. Device ID and diagnostic reason are shown for audit.
All operations remain entity-targeted and retain the existing climate-control
pause/resume action; secondary DRY/FAN modes are still advisory.


### Climate air-treatment and verified fan speed (v0.6 draft)

The new room air-treatment wizard selects actual same-room CO₂ and PM2.5
sensors, an explicitly chosen short-term **operational** PM2.5 action threshold
(not a WHO exposure threshold), and desired upper fan speeds. It records the
user's NDIR/particle-sensor verification and only provides automatic
percentage changes after separate consent. Indoor–outdoor moisture-ratio
evidence determines whether ventilation would remove or add moisture.

The coordinator reports distinct **extraction** and **filtration** intentions.
When CO₂ is high, extraction is recommended only if outside air was assessed
safe; verified NDIR inputs and a specific sensor are required for actual fan
speed control. When PM2.5 indoors exceeds the configured action threshold,
filtration remains an option even while windows should stay closed.
Moisture-only extraction remains **advisory** until outdoors sensors and fan
physical behavior can be commissioned.

An enabled fan speed controller uses `fan.set_percentage` on an already-on
room fan only, increases by at most 10 percentage points per five-minute
interval, requires a known native speed step and command acknowledgments,
pauses on a manual speed change and never sets 0% or sends on/off/preset
actions. Unverified devices remain advisory and the controller will not
power any purifier or ventilation equipment on.


### Climate-only rooms without window sensors

Climate can be configured for a Home Assistant area even when there is no
window contact in the room. These areas now appear as dedicated **climate
cards** in the Lovelace view with their controller and equipment diagnostics.
They are not automatically counted as air-quality safe (or unsafe), do not
receive invented window recommendations, and do not change the number of
monitored areas or Announcement Hub delivery targets. Existing monitored
rooms continue to use strict window-contact interlocks.


### Native AC dry/fan-only mode advisory (v0.6 development)

For an already-operating air conditioner exposing real `dry` and `fan_only`
HVAC modes, the room now indicates when a manually selected mode may improve
humidity and when the drying requirement has resolved. It never changes the
mode automatically. Advice requires usable humidity evidence, no competing
thermostat demand, a supported native mode pair, and a confirmed 30-minute
mode dwell. An OFF unit remains untouched. This prevents silently starting
compressor operation without verified real-device protection and recovery.


### Dedicated humidity power and environmental-only rooms (v0.6 draft)

For a bathroom or bedroom without any thermostat, choose
**Climate → Environmental devices only**. Assign the room's humidity sensor
and `humidifier.*` or `dehumidifier.*` entity; heating, cooling and
temperature measurements are optional for this method.

An additional experimental, **disabled-by-default** `humidity_power_auto`
control can turn a *dedicated Home Assistant humidifier/dehumidifier* on or
off, only after the user confirms independent equipment protections and
selects safe minimum on/off and maximum continuous running times. The default
minimum ON/OFF period is 10 minutes, and a newly starting controller will
not power a device on before it has observed a full off period. A
windowless room requires another explicit permission. Device target humidity
must be already programmed near the chosen room threshold and expose known
bounds/resolution. Only the named `humidifier.turn_on` /
`humidifier.turn_off` actions are used.

The power controller **does not take ownership of an already-running
appliance**. It pauses after out-of-band power changes, service/acknowledgement
failures or a restart with a previously owned active output. Manually
switch the device OFF, reconcile it, and explicitly resume before automatic
starts can be considered again. It never controls a compressor exposed only
as `climate.*`, and power control cannot be combined with the separate
native humidity-setpoint driver. The v0.6 feature is still a development
draft requiring hardware-level testing and must not be treated as a
certified safety controller.


### Heat-only, cool-only and DRY-only climate devices (v0.6 draft)

A device can advertise **only HEAT**, **only COOL** or **only DRY** in Home
Assistant and still be configured. The climate engine respects actual native
capabilities. Automatic planning will not attempt to cool with a heat-only
radiator or heat with a cooling-only AC. For DRY-only climate equipment,
choose the \`dry\` operating intent without inventing a temperature setpoint
or a FAN_ONLY capability. Compressor-affecting DRY mode changes remain
**manual/advisory** until physical commissioning is complete.

### Window ventilation instead of running mechanical climate equipment

When **Window efficiency notifications** is enabled in a climate room, the
integration can advise opening its existing closed window if credible measured
outdoor conditions could help with the same goal as currently operating
heating, cooling or dehumidification. These are conservative suggestions,
not unconditional claims of equivalent energy savings.

Examples:

- Cooling: the room's air conditioner is actually cooling, outdoor air is
  measured at least 2°C cooler, and outdoor weather/pollutants are safe.
- Heating: a heater is operating and outdoor air is at least 2°C warmer and
  can approach the room's requested heating temperature. A cold outdoors
  situation never generates a fake warming opportunity.
- Drying: a verified dehumidifier or AC DRY mode is actively removing
  moisture, and measured indoor/outdoor temperature and relative humidity
  show at least a 1.5 g/kg dry-air drying advantage, with reasonable
  indoor/outdoor temperature difference and a plausible RH reduction.

A high *outdoor relative humidity* alone cannot establish indoor
dehumidification effectiveness; moisture **mass** is considered. Missing
sensor data, pollutant warnings, ambiguous weather stations, already-open
windows or uncertain device operating state suppress advice. For a
humidity-only room, a measured room temperature is optional for running
a dedicated dehumidifier but **required** to estimate how much window airing
could reduce humidity; the advisor never fabricates it.

Announcements use the existing global opt-in channels and Announcement Hub
room-routing authority. Each climate room explicitly opts into these extra
messages. A climate-only area can receive a notice for its actual recognized
window without becoming a new general air-quality monitoring room. The
integration never automatically opens a window or switches off a running
heater, air conditioner or dehumidifier to exploit the potential savings.


### Native extraction and air-purifier fan power (v0.6 draft)

The climate room air-treatment page now has two **mutually exclusive**
control options: adjust the speed of an *already-running* verified fan,
or separately authorize the new guarded \`fan.*\` power controller.
The latter is OFF by default and requires independent fire, backdraft,
pressure and electrical-safety confirmation along with minimum ON/OFF
and maximum continuous runtime limits.

For extraction it verifies actual indoor CO₂, sensor technology,
outdoor air quality/weather, fresh source evidence and the specific
room's window state before any ON request. For particle filtration it
uses measured room PM2.5 and can run even when outdoor pollution
makes opening a window unsuitable. A running fan that the integration
did not turn on remains user-controlled; the integration does not turn
it off. Runtime acknowledgments, persistent ownership, user override
and restart reconciliation are mandatory before later power commands.

All calls target one actual \`fan.*\` entity through Home Assistant's
native fan power services. There are no automatic compressor or
\`climate.set_hvac_mode\` commands, and no claim that a powered fan
guarantees a measured air-change rate or equivalent pollutant removal.
This remains a draft pending field commissioning.


### Climate dashboard: coordinated devices (illustrative data)

These screenshots render the actual bundled Lovelace card with **synthetic
Home Assistant sensor and device states**, not real equipment measurements.
They demonstrate a humidity-only room, a cooling room, central room priorities
and independently guarded fan/dehumidifier status.

<p align="center">
  <img src="https://raw.githubusercontent.com/Chreece/HA-Home-Environment-Manager/v0.6.0b15/.github/assets/screenshots/dashboard-climate-coordination.png"
       alt="Actual Home Environment Manager card with simulated bedroom cooling and dehumidifier controls, coordinated priorities and safety holds"
       width="850">
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/Chreece/HA-Home-Environment-Manager/v0.6.0b15/.github/assets/screenshots/dashboard-climate-coordination-mobile.png"
       alt="Actual Greek dark-theme climate room card, simulated dehumidification status and room priority"
       width="360">
</p>

### Unified climate room coordination (v0.6 development)

Each climate room now has one shared **thermal, humidity, outdoor
ventilation and particle filtration** arbitration policy. Rather than
letting six controllers independently decide whether to issue a new
command, each driver must pass the same room grant plus a **fresh live**
verification immediately before it sends a Home Assistant service call.

The climate card displays the current control priority and why any
physical objective is held. A heat-only radiator will not compete against
an armed cooling-only AC. Separate dehumidifier startup can wait while an
air conditioner is already cooling. The owner can configure the
deferral margin between 0 and 20 RH percentage points (default 10);
zero disables this preference. Verified severe humidity can still be
treated with dedicated drying equipment. High CO₂ extraction has priority for air-quality guidance
when outdoor air is verified safe, while PM2.5 filtration can remain
eligible even if outside air is polluted.

This shared coordinator is an extra *safety/efficiency gate*, **not**
a replacement for the separate user authorizations, physical device
protections, acknowledgment tracking, startup settling, minimum
on/off durations or manual restart reconciliation. It never acts on a
window-opportunity suggestion to automatically switch off running
heating, cooling or DRY equipment.

CI includes coordinated room and live-transition regressions on both
Python 3.13 and 3.14. Representative hardware commissioning remains
mandatory before releasing the experimental control functions.


### Native DRY ↔ FAN_ONLY management (v0.6 development only)

The climate equipment wizard now offers a **separate, disabled-by-default**
permission for already-running native \`climate.*\` units that actually support
both \`dry\` and \`fan_only\`. After physical commissioning, the controller
can choose a native mode based on fresh measured indoor RH and comfort
interlocks. For example, it may switch FAN_ONLY → DRY when verified humidity
is too high, then DRY → FAN_ONLY **only after its compressor reports idle**
and RH has recovered with hysteresis.

This driver cannot switch equipment ON/OFF, never requests HEAT/COOL/AUTO,
never controls a generic relay or invents FAN_ONLY for a DRY-only unit,
and never targets an entire HA area or device. It requires exact area
ownership, window and humidity evidence, independent manufacturer-proven
compressor/frost/electrical protections, a minimum 30-minute mode dwell
with persistent acknowledgement, and another explicit consent to operate
without a window contact. Manual overrides and missing acknowledgements
persistently pause the controller; resume never immediately sends a command.

You can keep the permission disabled and still see the original native
DRY/FAN_ONLY suggestions in the climate dashboard. **Do not enable the
automatic mode controller in an uncommissioned home.** Tests using simulated
Home Assistant devices do not establish hardware compressor safety. This
work remains in draft PR #2, not the published v0.5.1 release.


#### DRY/FAN_ONLY mode-change recovery (development)

The commissioned DRY/FAN driver additionally persists each exact-target
mode-change **intent before issuing the HA command**. If storage fails,
Home Assistant stops during the write, or a manual override changes the
unit, automatic commands latch a pause rather than repeat a potentially
compressor-affecting transition. Resume requires a verified stable FAN_ONLY
state and retains the previous native mode dwell.

New commands are rechecked for live window, humidity, native operating mode
and competing equipment immediately after the durable save. DRY → FAN_ONLY
also requires five consecutive minutes of observed idle compressor state
before attempting a transition, in addition to the original 30-minute
mode-change dwell. These extra software guards do not certify any specific
compressor, heat pump, defrost cycle or shared refrigeration circuit.

The feature remains **disabled by default and experimental** in the v0.6 beta.
The physical AC must be independently commissioned first.


### Read-only Home Assistant climate commissioning report (v0.6 draft)

The integration now exposes
\`environment_manager.climate_diagnostics\` under **Developer Tools → Actions**.
Select an optional Home Assistant \`area\` to inspect only that configured room,
or omit it to inspect all explicitly configured climate rooms. Request the
action response to obtain a structured report of selected entity IDs, actual
native HEAT/COOL/DRY/FAN modes, current HVAC action, device/room ownership,
sensor freshness, windows, safety opt-ins, room-coordinator state and existing
native DRY/FAN mode diagnostic status.

This service **never changes an entity**. It does not export serial numbers,
network addresses, credentials, device tokens or unrelated unconfigured
entities. The reported \`software_preflight_ready\` flag reflects the data
visible to HA; it does **not** certify manufacturer compressor protection,
minimum compressor OFF time, defrost logic, electrical safety, or mechanical
ventilation safety. Physical commissioning remains an independent release
gate.

The native DRY/FAN controller now also rechecks the **full configured dwell**
after persistent write-ahead and refuses superseded room plans or revoked
permissions. If post-command history persistence fails, its original
uncertain intent is retained for manual reconciliation rather than silently
promoted to a completed command.


### Multiple integrations, shared-device safety and reliable unload (v0.6)

A configured thermostat, PID-controlled climate entity, protected heating
relay, dehumidifier or fan must not receive commands from two independent
Home Environment Manager configuration entries. The draft now detects
duplicate device ownership **across entries**, not just rooms within one
entry, and checks live ownership again before hardware writes.

The \`climate_diagnostics\` service can identify shared equipment in
configured rooms without exposing other entry IDs or device credentials.
All controllers still require their own opt-ins and physical safety
protections; existing owned outputs retain their bounded, acknowledged
shutdown/reconciliation policy. On HA shutdown or options reload, failure
of one controller's persistence no longer prevents the remaining
controllers, announcements, listeners or background tasks from being
cleaned up.

These features are included in the opt-in [v0.6.0b15 prerelease](https://github.com/Chreece/HA-Home-Environment-Manager/releases/tag/v0.6.0b28).
The [development PR #2](https://github.com/Chreece/HA-Home-Environment-Manager/pull/2) remains unmerged and production v0.5.1 stays unchanged pending representative hardware testing.


### Multiple Home Assistant entries: exact control routing (v0.6 draft)

The same integration may retain historical independent config entries.
Room-scoped \`climate_control\` and \`pid_control\` actions now resolve
**exactly one enabled configured-room owner**, rather than forwarding every
request to whichever entry happened to load first. A missing or ambiguous
area returns a clean error without issuing any device command or attempting
a broadcast. Both original and rebranded action aliases behave identically.

Within each entry, explicit advisory-only room configurations can continue
to monitor the same device without claiming actuator ownership. When a
separate entry also has authorized control over the output, live write-time
interlocks hold new commands in both entries until ownership is corrected.
The \`climate_diagnostics\` action identifies the conflict without exposing
another config entry's internal identifier. Legacy PID targets and
non-compressor thermal actuators are included.

This is validated using a simulated two-entry Home Assistant service
registry, interleaved state changes, Python unit tests and HACS/Hassfest.
Hardware commissioning remains mandatory for device-changing functions.


### Compact options and per-device occupancy (v0.6.0b15 beta)

The grouped options menu is reorganized as **Outside data** (weather, warnings,
outdoor-air sensors, AQI scales and international pollen), **General settings**
(shared occupancy sensors, resident trackers, and occupied/sleep-room lists held
in a Home Assistant entity state or named attribute), **Area settings**
(per-room air, humidity, window sensor exclusions, climate and device inventory),
Announcements and Advanced thresholds. The old saved configuration keys and
Home Assistant domain remain intact.

The new **Area settings → Devices** wizard preselects all compatible native
`climate.*`, `humidifier.*` and `fan.*` devices in an assigned Home Assistant
area for **inventory only**; no automatic device control is implied. Select
an individual device to configure its control method, independent opt-in,
normal/sleep targets, room occupancy/whole-home occupancy requirement,
absence action (hold or hardware-confirmed OFF) and relevant runtime bounds.

Shared occupied-room/sleep-room entities may contain a list of actual
Home Assistant area IDs or room names as JSON in their state or a selected
attribute (e.g. `["living_room","kitchen"]`). Unknown/stale/unrecognized
sources do **not** mean the house is empty and will never justify a new
physical shutdown. Any confirmed presence overrides conflicting absence
signals. Unoccupied conditions require a configurable stability period.
Native thermostat OFF is supported only when separately attested and remains
OFF until the user restarts it manually; no controller restarts an OFF
compressor. Humidifier/fan power OFF follows their existing owned-output
minimum-on, runtime and acknowledgement rules.

This refinement is included in the opt-in **v0.6.0b15 beta**. Existing
automation stays off until explicitly enabled, and all experimental power/
compressor-control paths still require separate real-device commissioning.
