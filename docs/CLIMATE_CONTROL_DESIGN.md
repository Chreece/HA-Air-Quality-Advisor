# Home Environment Manager — climate control architecture (development)

This document describes the safety contract of the next controller family. The
feature branch currently implements the deterministic policy and planner.
**Do not describe these planners as actuator control or install them for direct
switch/PWM control yet.** The released v0.5 supervisor remains separate.

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

## Capability-specific driver contracts (planned)

| HA equipment | Choice | Allowed API | Safety |
| --- | --- | --- | --- |
| Built-in thermostat | native device | climate.set_temperature | Keep device's own PID, native operating mode and compressor protections. |
| HVAC native heat/cool mode | automatic mode | climate.set_hvac_mode (only if device lists heat AND cool, explicit user opt-in) | Separation deadband, minimum mode dwell time and confirmation before issuing new setpoint. |
| Independent outer-loop PID | setpoint PID | climate.set_temperature | Existing v0.5 safeguards, no mode changes. |
| Single on/off slow thermal relay | hysteresis | switch.turn_on/off | Hard minimum-on/off, maximum-on watchdog and explicit switch ownership. |
| Slow thermal actuator with PWM | time proportioning | switch.turn_on/off at validated PWM periods | Pulse minimum and monotonic cycle anchor, no compressor switching. |
| True proportional actuator | native modulation | number.set_value / supported specific API | Bounded 0–100% output, rated capabilities and explicit source mapping. |

Each driver needs separate HA fake-platform integration tests, watchdog
and restart tests. Unsupported device capabilities must produce diagnostics
rather than automatic guessing or a generic service broadcast. One physical
actuator cannot be controlled by two enabled room controllers.

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
