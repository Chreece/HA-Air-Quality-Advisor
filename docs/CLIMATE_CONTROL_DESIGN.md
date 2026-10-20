# Home Environment Manager — climate control architecture (development)

This document describes the safety contract of the next controller family. The
feature branch implements deterministic policy and separate early-stage
native/direct actuator drivers. **This is an experimental development branch;
it is not approved for physical actuator commissioning or HACS publication.**
The released v0.5 thermostat supervisor remains separate.

## Scientific and engineering basis

- ASHRAE Guideline 36: occupied, unoccupied, standby zone temperature setbacks
  and non-overlapping heating/cooling targets. Our defaults are configurable
  residential presets, **not** certification to Guideline 36.
- ASHRAE 55 / ISO 7730: comfort depends on radiant temperature, air movement,
  humidity, clothing and activity. An air-temperature-only model can provide a
  temperature goal but cannot guarantee occupant comfort.
- Schmitt trigger / deadband control: prevents repeated heat/cool changes near a
  single target. Control transitions require hysteresis and a validated device.
- PID: derivative on measurement and anti-windup as already validated in
  Home Environment Manager v0.5.0. Do not stack an external PID over a built-in
  PID unless the device explicitly supports supervisory setpoint operation.
- Time-proportioning control: duty-cycle PWM is suitable for slow thermal
  resistive/valve actuators if the hardware supports it, subject to minimum-on
  and minimum-off intervals. Never drive compressor power directly through
  short PWM cycles.
- Power loss, HA reload or stale input: no automatic assumption of safe
  actuator state. Reconcile real output state before writing.

## Capability-specific driver contracts (implementation under validation)

| HA equipment | Choice | Allowed API | Safety |
| --- | --- | --- | --- |
| Built-in thermostat | native device | climate.set_temperature | Keep device's own PID, native operating mode and compressor protections. |
| HVAC native heat/cool mode | automatic mode | climate.set_hvac_mode (only if device lists heat AND cool, explicit user opt-in) | Separation deadband, minimum mode dwell time and confirmation before issuing new setpoint. |
| Independent outer-loop PID | setpoint PID | climate.set_temperature | Existing v0.5 safeguards, no mode changes. |
| Single on/off slow thermal relay | hysteresis | switch.turn_on/off | Hard minimum-on/off, maximum-on watchdog and explicit switch ownership. |
| Slow thermal actuator with PWM | time proportioning | switch.turn_on/off at validated PWM periods | Pulse minimum and monotonic cycle anchor, no compressor switching. |
| True proportional actuator | native modulation | number.set_value / supported specific API | Bounded 0–100% output, rated capabilities and explicit source mapping. |

Pure-policy, fake Home Assistant actuator, watchdog and startup tests are
underway. Unsupported device capabilities must produce diagnostics rather
than automatic guessing or a generic service broadcast. One physical
actuator cannot be controlled by two enabled room controllers.


## Multi-device room coordination (new development checkpoint)

The room climate wizard now accepts any existing Home Assistant area with
supported equipment, even without a window contact. This does **not** widen
air-quality window announcements to additional rooms. If a room is already
monitored for windows and its expected contact disappears, HVAC plans still
fail closed.

Each room may explicitly assign:
- Primary `climate.*` thermostat, and optional separate climate entities for
  heating, cooling, native DRY and FAN_ONLY capabilities.
- `humidifier.*` entities for humidification and dehumidification, verified
  using Home Assistant's *device_class* rather than the entity name.
- `fan.*` extraction/ventilation and particle-purification equipment.
- One same-room humidity sensor and customizable low/high RH thresholds with
  Schmitt hysteresis. Multiple humidity sensors are not silently blended;
  choose the source used for humidity management.

The new `climate_coordination.py` is a **pure advisory planner**. It verifies
area and domain, supported HVAC modes, whether equipment is available, active
opposing heat/cool operation, and cross-room duplicate hardware ownership.
Explicitly selected dedicated equipment cannot silently fall back to another
device. Native thermostat control is permitted only on its existing primary
device driver when its safety policy is satisfied; extra heat/cool, DRY,
humidifier, extraction and purification roles do not yet issue service calls.

Only a single role may own a command at a time. Drying an AC while the same
reversible compressor is regulating temperature is prohibited until explicit
model-aware transition logic and independent device commissioning exist.
Humidity advice must not be confused with a guarantee of effective moisture
removal: outdoor *absolute moisture* and source control matter, and extractor
fan operation depends on safe outdoor evidence.

**Important:** Selecting extra equipment generally enables only inventory,
advisories and conflict diagnostics. The single exception is the independently
opted-in **native humidifier/dehumidifier setpoint controller** described below.

### Already-running humidifier/dehumidifier target supervision

The `humidity_setpoint_auto` permission is a separate opt-in. It requires
an exact `humidifier.*` entity, correct `humidifier`/`dehumidifier`
device class, explicit fresh same-room humidity sensor, permitted climate
actuation, valid native humidity limits/step size, all configured windows
closed, no competing humidity equipment and exclusive room ownership.

The controller sends only `humidifier.set_humidity` with a device-specific
single-entity target. It **never** calls `turn_on`, `turn_off`, `set_mode`,
`climate.set_hvac_mode`, or commands an AC compressor. If the selected device
is OFF, it is left OFF. Native device PID, operating mode, hardware protections
and shutoff behavior remain the equipment's responsibility.

Target changes are bounded to five percentage points per command, rate
limited to ten minutes, and forbidden when resolution/bounds are unknown.
The controller waits five minutes after startup/resume; persistent expected
setpoints are compared to observed hardware state; manual override, service
failure or missing acknowledgment latches a pause. A user must explicitly
resume after such a pause. Windows and sensor conditions are checked again
immediately before any new setpoint call. Full hardware commissioning and
restart testing remain outstanding.

For `climate.*` units exposing DRY and FAN_ONLY, no additional native
mode-switching driver is enabled by this exception. Similarly, standalone
extractors and purifier fans remain advisory until hardware verified.


## Occupancy / away

- HA Area Registry assigns each occupancy/presence sensor to a room; use all
  valid same-room sensors unless a user-selected subset was given. Any sensor
  reporting occupied wins. All known off means unoccupied; unknown sensors
  do NOT imply vacancy.
- Whole-home away is decided from explicitly chosen `person.*`,
  `device_tracker.*` or designated binary sensors. The default mode considers
  the home occupied if at least one person is present. Stale/unknown trackers
  retain conservative 'home' setpoints rather than declaring 'away'.
- Separate room goals for home, unoccupied, away and sleep; heating must remain
  strictly below cooling. Manual override has priority over profiles.
- Target changes are subject to ramp limiting, a stable interval and separate
  hardware constraints. Windows that are open/unknown stop extra HVAC commands
  in the initial policy.
- Per-room occupancy is not whole-home occupancy. Never treat a motion sensor
  being off as proof that a resident has left the home.

## Additional safe configuration needed

Per-room device selection, sensor selection, heat/cool mode preference,
external-away provider, schedule, occupant comfortable/eco band, allowed mode
transitions, minimum mode dwell, humidity guard, controller method, PID gains,
period and output bounds. All input selectors should explain WHY they are
required and show capability validation in the UI.

## Release gate

No direct actuation release until simulated and mocked HA tests confirm:
system startup with device off/unknown; sensor dropouts; HA restart; clock jump;
manual changes; multi-sensor presence disagreement; device unavailable;
duplicate ownership; heating/cooling reversal; rapid toggling; freezing
protection; PWM too-short pulses; service failure; command retry; unexpected
output state; dehumidifying vs cooling priority; and safe upgrade from v0.5.

Keep the internal integration domain `air_quality_advisor`, existing entities
and legacy announce services. The public product name remains Home Environment
Manager. Independent devices keep their own hardwired safety protections.

## Python 3.14 / Alpine compatibility

PMV/PPD uses the bundled scalar Fanger equation in `pmv_core.py`, tested
against `pythermalcomfort` 4.6.2 reference values. The integration no longer
installs pythermalcomfort, Numba, llvmlite, SciPy or NumPy. This avoids an
Alpine/musl LLVM source-build failure during Home Assistant startup.

The scalar model retains ISO 7730 input limits, rejects non-finite results and
supplies the existing PMV-derived comfort target bisection. All required
radiant temperature, relative air movement, activity and clothing parameters
remain explicit. The algorithm is an engineering estimate, not evidence of
ISO-compliant certification. The adapted reference model's MIT notice is
included in `docs/licenses/pythermalcomfort-MIT.txt`.


## Dashboard visibility

The v0.6 Lovelace climate section now shows primary thermostat, secondary
native setpoint, and humidifier/dehumidifier setpoint statuses independently,
plus the selected equipment and measured humidity evidence. It distinguishes
an intentional primary hold from a secondary setpoint controller that is
actively operating. Device names and failure reasons are presented as
traceable diagnostics; controls call only the existing room-specific
`home_environment_manager.climate_control` action.


## Air treatment / running fan speed policy

Per-room air treatment evaluates indoor CO₂, PM2.5, fresh humidity evidence,
measured indoor/outdoor moisture ratio, and the global outdoor safety state.
No air-quality guideline for a 24-hour *exposure* is treated as an
instantaneous switching threshold: the short-term PM2.5 operational trigger
is an independently configurable policy. Multi-sensor ambiguity and stale
or unverified readings never authorize commands.

A new `RunningFanSpeedControl` can optionally use an already ON `fan.*`
entity. For extractor fans, verified NDIR room CO₂, safe outdoor evidence,
and a user-selected room sensor are mandatory. For particle filtration,
a verified, explicitly selected PM2.5 sensor and a same-room purifier fan
are mandatory. The fan must expose `SET_SPEED`, a positive percentage,
native speed increment and no active preset. The controller ramps UP only,
by no more than 10% every five minutes, and issues at most one
`fan.set_percentage` per authorized target per cycle.

**Never** send power, oscillation, direction, preset, compressor or zero speed
commands via this driver. Incompatible native steps, manual overrides,
service failures, unknown fan state, duplicates and missing acknowledgements
hold or pause the driver. Outdoor changes and source events recalculate the
policy, but real hardware emergency and commissioning safeguards are still
independently required. Full automatic extraction/dehumidifier power, cooling
and DRY/FAN_ONLY transitions remain separate future control gates.


## Dashboard vs ventilation-monitoring room membership

`Plan.climate_rooms` contains independently configured HVAC-only areas.
`Plan.rooms` remains strictly the selected window/indoor air monitoring
areas used to calculate recommendations, announcements and monitored-room
status totals. The dashboard appends specially marked `climate_only`
room cards, without contributing them to air-quality summary counts or
fabricating window alerts. When a monitored room loses its required contact
its native setpoint policy still holds, unlike a deliberate HVAC-only room.


## Pending native DRY/FAN_ONLY commissioning

`climate_hvac_modes.native_air_mode_advice` is intentionally advisory.
It checks user-selected AC identity, actual HA `hvac_modes`, room and
humidity evidence, existing compressor/thermal demand, manual off and native
30-minute mode stability before proposing an explicit manual switch.
`automatic_control` is always false; none of its outputs may be passed to
`climate.set_hvac_mode` without a separately validated device-mode driver.
Converting this recommendation to automatic control will require verifying
compressor anti-short-cycle protections, multi-zone priority, restart
recovery, command acknowledgment and a safe manual override policy on
representative actual units.


## Native thermostat final-write live interlocks (October 2026)

The primary native temperature-setpoint and heat/cool range path now
revalidates the actual `climate.*` entity's area registry assignment before
sending commands. When a cached plan declares window contacts, each contact
is re-read and must still be a closed, correct-room window binary sensor.

All separately selected HVAC equipment is also re-read. An armed opposing
mode, active `hvac_action`, unavailable device, or missing operating
information holds the primary write. This is essential because independent
thermostats can begin heating or cooling after the last planning interval,
even when their current `hvac_action` was previously idle.

These checks are a final conservative gate; they do not start, switch off or
reconfigure another appliance. Hardware safety and commissioning remain
required, and native DRY/FAN_ONLY automation is still advisory-only.


## Experimental automatic dedicated humidifier/dehumidifier power

The `climate_humidity_power.py` driver is independently opted in and **OFF
by default**. It supports only explicitly selected and area-verified
`humidifier.*` or `dehumidifier.*` entities, not generic switches or
`climate.*` AC/heat-pump compressors. The hardware must have its own tank-full,
thermal, frost and, where applicable, compressor anti-short-cycle protections.

The room may use the new `environment` controller method to supervise
humidity or fans **without an unrelated temperature sensor or thermostat**.
Humidity actuator permission remains a separate explicit consent.

Before an ON command the driver requires a fresh exact room RH sensor, stable
windows (or another explicit permission for a windowless room), an exclusive
selected device, matching Home Assistant `device_class`, a native humidity
setpoint preconfigured within ±2 RH points of the room threshold, confirmed
device setpoint range and resolution, no active opposing humidifier, and no
selected AC already reporting DRY operation. It observes OFF continuously for
the configured minimum (default 600 s) before energizing. It issues only
single-entity `humidifier.turn_on` and `humidifier.turn_off` actions.

ON-to-OFF operation observes minimum runtime (default 600 s), Schmitt
humidity hysteresis, a maximum continuous controller-owned runtime (default
7200 s), missing humidity/window evidence and explicit pause. A successful
command must be acknowledged before another write. Unexpected manual power
changes, service failures and missing acknowledgements persist a pause.
After a restart, every persisted active output requires the user to reconcile
the physical OFF state; the controller does not silently reclaim or stop an
unverified appliance. Disabling the integration or reloading Home Assistant
does not magically provide hardware shutdown protection.

The **power and native humidity-setpoint drivers cannot simultaneously own
one device**. A new dedicated-device power permission never authorizes
fan power, AC DRY/FAN_ONLY changes, heating equipment or power-relay PWM.
Real hardware commissioning remains mandatory before releasing this feature.


## Single-purpose heat, cool and dry climate devices

Devices are classified by actual \`hvac_modes\`, not brand names. A heater
exposing only \`heat\` remains fully supported for valid heating requests;
an AC exposing only \`cool\` remains fully supported for valid cooling
requests. If automatic temperature planning detects demand for a missing
opposite mode, it holds that demand instead of sending an unsupported command
or turning off the only supported device.

A \`climate.*\` unit with only \`dry\` may be configured with the explicit
DRY-only mode; it does not require a temperature setpoint or nonexistent
\`fan_only\` mode. The native DRY pathway is informational only because
switching a compressor into DRY requires equipment-specific anti-short-cycle,
defrost and recovery validation. When the humidity is back within bounds,
DRY-only units recommend stopping the mode manually rather than fabricating
\`fan_only\` availability.

## Ventilation as a measured alternative to running equipment

\`climate_window.py\` evaluates an **advisory**, not an actuator instruction.
Before suggesting opening a window it requires all selected closed room window
contacts, unblocked outdoor air/weather, fresh and unambiguous outdoor
temperature from ONE weather provider, present outdoor pollutant measurements,
verified SAME-room climate device identity, and operating evidence: native
\`hvac_action=heating/cooling/drying\` (with the corresponding mode) or an
actually-ON dedicated dehumidifier. Idle units are not considered in use.
The integration does not silently reclassify an AQI scale.

A cooling alternative requires outdoor air at least 2°C below measured room
temperature. A warming alternative requires outside air at least 2°C warmer
AND at or above the selected heating target (within 0.25°C), rather than
pretending marginally warmer outside air can meet an unmet heat demand.
Dehumidifier/DRY alternatives require the room genuinely needs drying,
a humidity-ratio advantage of at least 1.5 g/kg dry air, the predicted
outdoor-air RH at room temperature below the room's humidity upper limit,
and no extreme (>12°C) temperature drop suggesting excessive heating cost.
These are conservative proposal gates, NOT an equivalence to AC or rated
dehumidifier CADR/drying capacity and NOT an energy-savings guarantee.

Additional protection: stale/unavailable outdoor pollutant sensors, weather
warnings, pollen blockers, unknown/open windows, uncertain humidity readings,
simultaneous incompatible equipment demands or known away occupancy suppress
the suggestion. Windows are never opened or operated automatically, and
running HVAC is never shut off automatically just because airing may help.

**Routing:** The optional per-room \`window_efficiency_notify\` toggle is OFF
for existing configurations, preserving delivery preferences. For monitored
rooms the new cause is attached to the existing window recommendation with
pollutant/mold reasons first. Explicitly opted-in climate-only rooms create a
separate room-specific notice without entering regular air-quality totals.
Existing 90-second stability, reminder/cooldown and channel permissions are
unchanged. Announcement Hub alone owns occupancy filtering, device selection,
fallback, TTS, text notification and AI processing while it is running.


## Native fan power (experimental draft, independently attested)

The new \`climate_fan_power.py\` is deliberately separate from the already-on
fan speed supervisor. Fan power requires \`fan_power_auto\`, a second
\`fan_power_hardware_confirmed\` safety attestation, a supported exact HA
\`fan.*\` entity belonging to the room, verified sensor inputs and configurable
minimum ON, minimum OFF and maximum continuous powered intervals. Fan power
and speed supervision are **mutually exclusive** for a room.

Extraction requires a current qualifying room CO₂ source (with explicit
NDIR verification), unblocked outdoor ventilation, a real measured outdoor
pollutant source and closed room window contacts. Purification requires
indoor PM2.5 measurement and explicit sensor verification; it remains
available when outdoor air is unsuitable for window ventilation. The
120-second air-policy freshness limit applies at the final write.

Manual ON fans are never commandeered or silently switched OFF.
Only controller-owned outputs may be turned OFF after minimum-on dwell or
when an acknowledged maximum-on watchdog expires. Native OFF dwell and HA
\`last_changed\` both protect restarts after a manual toggle. Failed service
calls, acknowledgments, user override, hardware unavailability or restart
with previously-owned ON power latch a persistent pause. Explicit OFF
reconciliation and manual resume are required after an active restart.

This driver issues ONLY exact-target \`fan.turn_on\` and \`fan.turn_off\`.
It does not operate generic switches, heat pumps, ACs, compressor modes,
fan presets, speed, room-wide broadcasts or motorized windows. Exhaust
systems may have special backdraft/fire/pressure requirements; simulated
tests are not hardware certification. Keep the feature in the v0.6 draft
until tested on supported real devices.


## Unified room purpose arbitration (v0.6 development checkpoint)

The \`climate_arbitration.py\` module implements a single, deterministic,
side-effect-free room policy. Every configured room exposes one
\`climate_plan.coordination\` record, with four separately documented
purposes: \`thermal\`, \`humidity\`, \`extraction\`, and \`filtration\`.

The coordinator uses the existing same-room device inventory, current
Home Assistant HVAC states, user-selected climate/humidity targets,
window interlocks, actual outdoor-air verification, and the existing
evidence-qualified CO₂/PM2.5 treatment intentions. It never invents
an HVAC mode, humidity sensor, target temperature or device capability.
\`eligible\` means *evidence-qualified to continue to a driver's own safety
checks*, **NOT** permission to power a device on. Explicit per-actuator
opt-in, real device safety protections and commissioning still apply.

The coordinator prioritizes qualified CO₂ extraction, measured indoor
particle filtration, temperature regulation and humidity management for
room diagnostics. These are distinct physical objectives; they may operate
in parallel ONLY if their actual device modes do not conflict.

- Opposing HEAT/COOL/AUTO/DRY modes can be armed while \`hvac_action\` reads
  \`idle\`. Any other live unit armed in an opposing mode blocks new native
  setpoint and direct thermal writes.
- A separate dehumidifier is conservatively deferred when native COOL is
  armed and RH is below the configured upper boundary plus the owner's
  `cooling_dry_deferral_rh_points` (default 10; range 0–20). Zero
  disables the deferral. This is a **control preference**, not scientific
  proof that the AC effectively dehumidifies. High measured RH still
  allows dedicated dehumidification after all other safeguards pass.
- Simultaneous humidification and cooling, or a separate humidifier and
  dehumidifier running against each other, hold humidity actuation.
  Native DRY already armed also blocks new separate dehumidifier starts.
- Extraction requires measured elevated CO₂ and verified safe outdoor
  conditions; a later-opened window blocks a new extractor command.
  Verified PM2.5 filtration remains independent of outdoor pollution and
  remains possible with a window already open.
- An energy-saving **open-window suggestion never forces a running unit
  off**, falsely grants power permissions, or bypasses minimum runtime.

**Fresh-write verification:** All primary/secondary native thermostats,
attested slow-load relays, native humidity setpoints, separately owned
dehumidifier power, fan-speed supervision and fan power now check the
shared planned permission AND recompute the affected channel's live
interlocks before a new write. A previous \`eligible\` decision is never
treated as permission after a competing device becomes armed, a window
opens, an owner changes, or outdoor data expires.

**Already-owned outputs** are a different case. A safety hold never
strands controller-owned power: its device-specific manual intervention,
minimum-on timing, OFF acknowledgement, maximum-runtime and restart
reconciliation logic remains authoritative. New ON, modulation or target
commands are held; physical emergency protection remains the device's
responsibility.

No new compressor-mode control was enabled in this checkpoint. Native
DRY/FAN_ONLY remain advisory until independently commissioned.


## Owned-device recovery during configuration edits and integration upgrades

A dedicated dehumidifier or ventilation fan may still be operating when
an administrator removes its room or changes its options. An automatic
controller must not silently lose that output, assume its maximum runtime
has reset, or substitute new default minimum-on limits mid-cycle.

The native \`HumidityPowerControl\` and \`FanPowerControl\` now record the
**commissioned minimum-on and maximum-on durations at every successful
new ON command**. While an output remains owned, those original bounds
govern the runtime and confirmation steps even if its configuration is
deleted, disabled or changed to shorter values. Scheduler enumeration
includes persisted owned outputs, not just currently configured rooms.

- If the original safety bounds are missing from an older ownership record
  AND no valid surviving configuration exists, the integration stops issuing
  automatic writes and requests physical OFF reconciliation. It never
  guesses the required compressor or fan dwell.
- A room-removal safety check may still issue an exact-target OFF command
  only after the originally recorded minimum-on interval, with the
  previously established acknowledgement and owner checks. No new ON is
  authorized for a removed or disabled room.
- If the fan has an owned output, processing that output terminates the
  current tick; it cannot silently overwrite a safety status with
  \`advisory_only\` or start another fan while the earlier command settles.
- The HA entry setup path now attempts controller teardown if **either**
  controller startup or sensor-platform forwarding fails, rather than
  leaving a partially started runtime. The original integration domain and
  config-entry data remain unchanged for v0.5.1 upgrades.
- The Lovelace card asset cache URL now derives its version directly from
  \`manifest.json\`, preventing a stale pinned version when the release
  advances.

Simulated regression tests cover room deletion, options edits, invalid
persisted records, setup failure, service registration and unload. These
are preflight software checks; no physical operating interval or hardware
safety certification is inferred from them.


## Commissioned native DRY/FAN_ONLY transitions (software implementation)

The controller \`climate_air_mode_native.py\` is now present and wired to
the regular per-room planning, Home Assistant option flow and climate
pause/resume service. It is **disabled by default**. Device-specific hardware
testing and explicit operator confirmation are mandatory before activation.

This driver is separate from the older \`climate_hvac_modes.py\` advisor,
which is always side-effect-free. The advisor now feeds the actual room plan
and Lovelace interface, even when automatic mode switching is disabled.

When both \`dry_fan_mode_auto\` and \`dry_fan_hardware_confirmed\` are
explicitly selected, the controller can request only exact-target
\`climate.set_hvac_mode\` transitions between existing \`dry\` and
\`fan_only\` modes for **one selected, already-running, same-room** AC.
The HA entity must publish both modes. A DRY-only unit remains fully
recognized for monitoring/advice but is **never** automatically switched
to a fictional FAN_ONLY mode or OFF.

Before issuing a command, the controller must verify:
- Same-room \`dry_climate_entity\`, fresh exact humidity sensor, and
  current confirmed closed window contacts (or separate windowless consent).
- No room cross-ownership, competing humidifier/dehumidifier, unverified
  native HVAC activity, or other armed cooling/heating/drying equipment.
- No independent humidity setpoint/power owner on the same room.
- Controller method \`environment\`, or a \`device\` configured for
  manual/advisory \`dry\` only; it cannot fight the primary temperature PID.
- Explicit compatible \`hvac_action\`: FAN_ONLY must report actual
  \`fan\`/\`idle\`. When humidity recovers, active compressor drying must
  first become \`idle\` before requesting FAN_ONLY.
- A verified Home Assistant \`last_changed\` timestamp and at least
  30 minutes of native mode stability, plus a bounded extra configured
  dwell between integration-originated changes.
- Valid independent hardware compressor/defrost/electrical protections,
  user consent, and functioning \`climate.set_hvac_mode\` service.

It **never** sends \`climate.turn_on\`, \`climate.turn_off\`, generic
switch commands, area broadcasts, HEAT/COOL/AUTO transitions or unsupported
mode values. Every successful request is persisted and must be acknowledged.
Unexpected manual changes, failed service calls or missing acknowledgements
latch a pause. After Home Assistant restarts, a five-minute warmup and
persistent mode history gate all new commands.

This is a **software implementation awaiting hardware commissioning**:
clicking a confirmation checkbox is not manufacturer certification, nor does
the integration directly measure compressor current, defrost state or actual
minimum off time. Do not merge or publish the experimental feature until
representative units and shared outdoor-unit safety are verified.

Reference API contract: https://www.home-assistant.io/actions/climate.set_hvac_mode/


### Native DRY/FAN_ONLY: durable command recovery and live revalidation

The DRY/FAN_ONLY native driver now follows a **durable write-ahead
contract**, because a successful Home Assistant service may reach the physical
AC just before the integration or host stops:

1. Before requesting a change, save a persistent record with the exact
   climate entity, intended native mode, timestamp and \`phase=intent\`.
   Storage errors abort the command with a latched safety pause.
2. After this asynchronous save returns, **recheck live** closed-window
   contacts, fresh RH, current native HVAC mode/action, competing room
   equipment and intended target. Changes during the save abort the service
   request and preserve the intent for manual reconciliation.
3. Only then call exact-target \`climate.set_hvac_mode\`. Persist
   \`phase=commanded\` on success and wait for the observed mode to
   acknowledge the target; failures leave the durable intent/last-write
   record in place. A crash or cancellation cannot silently trigger a retry.
4. Restore interrupted \`phase=intent\` writes as an *immediate* paused
   status on startup, not an apparently harmless warmup. Unsupported schema
   versions, malformed stored records and unreliable timestamps fail closed,
   preserving their original saved data for diagnosis.
5. Explicit Resume cannot erase \`last_write\` or clear an ambiguous command
   without verified manual reconciliation: the physical device must already
   be in FAN_ONLY, report a FAN/IDLE action, remain stable for its full native
   dwell, and observe the last write's full cooldown. Resume starts a further
   warmup before any new command.

A separate **five-minute consecutive observed compressor-IDLE requirement**
is now imposed for a DRY → FAN_ONLY request. A renewed DRYING report resets
that elapsed observation. An IDLE reading at just one instant is not enough
to stop an AC drying mode. The time is a software protection on top of the
native 30-minute mode dwell, **not** proof of manufacturer compressor safety.
It is not a license to bypass compressor defrost, short-cycling, humidity
condensation or shared outdoor-unit protections.

No new native modes were invented, no HA area-wide commands were added, and
this remains off by default pending representative hardware commissioning.


## Audit-only hardware commissioning interface and final write-time guards

\`climate_commissioning.report\` produces a bounded, entirely read-only
view of each explicitly configured HA room's native HVAC capabilities,
reported activity, current allowed modes, selected humidity/temperature/CO₂/
PM2.5 sensor values and ages, matched area registry ownership, window contacts,
user opt-ins and live arbitration status. It cannot operate device services
or infer protected compressor readiness. Credentials, token attributes,
device serial identifiers, unrelated rooms and network metadata are never
collected.

The optional HA actions \`air_quality_advisor.climate_diagnostics\` and
\`home_environment_manager.climate_diagnostics\` expose that same report as
a response for all configured climate rooms or for a selected exact
\`area\`. All service aliases are unregistered after the last config entry
unloads, and the v0.5.1 config-entry title, data and entity IDs are preserved.

The commissioned DRY↔FAN_ONLY controller has additional final-phase
protections against concurrent HA option edits: a new command holds if its
room's selected permissions, equipment, or environmental decision was
superseded while the durable write-ahead intent was being saved. Immediately
before the service call, it rechecks the **user-selected physical dwell**,
not just the advisor's default 30-minute threshold. Failed completion
persistence retains an uncertain \`intent\` rather than permitting an
automatic retry on subsequent startup.

These software checks are exercised with injected Home Assistant state
changes during asynchronous storage I/O and legacy entry teardown. Real
compressor/electrical safety is not measured or certified by the report.
