# Managed controller implementation — beta 11

## Implemented topology

Home Environment Manager has one Home device and one Area hub per configured
monitoring, climate-only or PID-only area. Room environmental/policy entities
belong to their Area hub. Managed physical devices have logical controller
children, linked back to the native source device without modifying its own
integration, gateway or user-assigned area. Multiple independently controlled
native channels remain separate climate entities on the same logical child.

## Implemented controller surface

`climate.py` uses actual current capability flags and real mode lists. Native
HEAT/COOL/range/AUTO/DRY/FAN_ONLY, supported humidity, fan, swing and horizontal
swing controls are represented without inventing native services. External
room temperature/humidity are used only when qualified. Binary thermal
actuators receive a logical Manager target rather than an unsupported native
setpoint call. Manager presets are None/Home/Comfort/Away/Sleep/Eco.

`equipment_model.py` defines capability/permission validation, profile targets,
physical channel identities, ownership, PID math and bounded duty calculation.
`equipment_runtime.py` owns new execution; `equipment_entity.py` supplies
localized help and push updates. Existing Number/Select/Switch/Button platforms
add only supported device-specific algorithm, PID, quiet and resume controls.

Control method Existing preserves old room behavior and is the upgrade default.
Automatic follows current room/preset policy. Manual/None uses independent
manual targets and explicit native choices; changing occupancy does not change
them. PID uses the selected feedback and supported actuator method. Off retires
only this controller's owned outputs after minimum run time. Explicit presets
change targets and can carry native fan choices; they never clear a safety pause.

## Duty control and quiet operation

Qualified fan CO2/PM, dedicated humidity and thermal feedback use sampled PID
with anti-windup and derivative on measurement. Native on/off equipment uses
slow duty cycles, not rapid toggling. Dwell and maximum-on settings come from
independent equipment commissioning and cannot be shortened by changing
algorithm. Compressor-affecting devices have at least ten-minute ON/OFF
software floors; fan floors are two minutes, with larger configured values
preserved. Demand pulses that cannot satisfy both dwell intervals are skipped.
Native setpoint PID is bounded and cannot obtain new power permission.

Quiet sleep/occupied controls exist only where a real fan percentage or native
mode list can be controlled. Native discrete quiet mode must be selected (or
actual advertised `low` used); unknown vendor options are not inferred.
Reduction and restoration do not start equipment and require fresh known
presence context and unchanged ownership. They are fan-setting policies, not
sound-pressure measurement or acoustic compliance claims.

## Transaction and ownership contract

A logical physical device has one lock shared by all its channels; different
physical devices can progress concurrently, with bounded dispatch concurrency.
An in-flight/owned old driver blocks transfer. Exact new endpoints are filtered
out of old scheduling and checked again at the old write boundary. Foreign
entry and retained retired ownership remain conflicts.

Before dispatch, the command's exact intent is persisted. Following storage
and semaphore awaits, source identity, device capabilities, source/control
snapshots, configuration, room plan, measurement freshness and interlocks are
rechecked. Any relevant change cancels that tick without sending a stale
follow-up command. Service requests target one exact entity only. Acknowledgment
is required; uncertain or interrupted intents are never automatically retried.

A physical manual change latches a pause. Restart with owned power or uncertain
intent requires explicit reconciliation, actual OFF confirmation where needed,
warmup and minimum-OFF dwell. Automatic power ownership refuses to adopt an
already-running manual appliance. Removing/retiring equipment preserves its
stored original safe timing for shutdown; reassigned identities are not touched.
Manager-generated climate facades are rejected as physical selector inputs and
at dispatch, preventing self-recursive control.

## Verification and limits

Regression tests use Home Assistant boundary doubles and mock service/state
acknowledgements. Coverage includes native capabilities, separate channel
identity, presets/manual isolation, binary fan/dehumidifier/climate duty,
ON/OFF intervals, saturation/pulses, safe retirement, explicit resume,
manual overrides, failed/uncertain transactions, post-await stale evidence,
foreign ownership, Fahrenheit conversion and quiet-speed restoration.

All 38 locale catalogs and generated device help must reproduce exactly.
Python 3.13 and 3.14 tests, Node frontend tests, Hassfest, HACS and manual
installation packaging gate the beta. No live Home Assistant instance or
physical appliance is tested by these mock regressions. Software timing cannot
certify electrical, compressor, frost/defrost, condensate, fire/backdraft or
ventilation protection. Independently qualified real hardware is mandatory
before enabling experimental physical power or mode changes.

## User activation

Upgrade via HACS beta selection and restart Home Assistant without adding a
second integration entry. Open the Area hub, then its controller device.
Check native hardware/source commissioning, valid current measurements and
required manufacturer timing. Change Existing to the intended method only for
that device. Inspect its status/help and verify physical response before
unattended operation. Defaults are fixed gains, not automatic PID tuning.
