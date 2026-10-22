# Area hub and per-device controller checkpoint

Development branch: `feat/device-climate-controllers-20261022`.
Base: published beta `v0.6.0b10`, commit `2485f39e6a205f0ca7b6d258f26427c33e23e8eb`.
The branch is not a new HACS prerelease.

## Agreed ownership model

Home Environment Manager has one logical **Home hub**, one logical **Area hub
for every configured area**, and the **managed equipment controller devices**
beneath the appropriate Area hub. Monitoring-only, climate-only and PID-only
areas all participate; unrelated unselected HA areas do not become controlled.

The area hub owns room-wide environmental assessments, calculated mold data,
room policies and settings. Device-specific entities belong to their managed
controller device, not to the Home hub or a flat collection on the Area hub.
Multiple configured endpoints/roles of the same physical HA device in one
area share one logical managed device. The native device, integration,
identifiers, connections, area and original gateway are never reassigned.

The source device remains accessible through the managed controller device's
configuration link. Area overview attributes expose the area hub ID, managed
controller device IDs, physical device IDs and exact source entity IDs.

## Implemented in this checkpoint

- Register Home, Area hubs and managed devices before forwarding entity platforms.
- Preserve existing Home/Area identifiers and existing entity unique IDs.
- Use actual registry source identities, rather than display names, for grouping.
- Handle current and earlier supported HA registry APIs with parent-first ordering.
- Keep unassigned, cross-area, deleted-area, unselected and self-referential
  controller sources out of the hierarchy; retain temporarily unavailable sources.
- Attach the existing per-device target and occupancy/sleep policy entities to
  their logical managed devices. Global AQI controls stay on Home; shared room
  and calibration settings stay on the Area hub.
- Cover hierarchy, duplicate roles, source renaming, reload identity, user area
  overrides, registry API versions and entity-device migration in regression tests.

## Remaining work from the larger controller request

The hierarchy is a prerequisite, not a claim that the entire new controller
interface exists. The following are NOT shipped by this checkpoint:

1. Per-device climate facade with room temperature/humidity, real supported
   modes, fan controls and Manager home/comfort/away/sleep presets.
2. Independent per-device automatic/manual/off/PID control selection, without
   competing with the existing room drivers or resuming a safety pause.
3. PID demand for supported on/off fans, dehumidifiers and native climate
   devices, with minimum ON/OFF dwell and durable ownership/restart handling.
4. Sleep/occupied-room quiet switches and capability-aware lower fan speeds.

Do not label these unfinished items as released. Keep beta `v0.6.0b10` and
stable `v0.5.1` unchanged until the complete next candidate is validated.
