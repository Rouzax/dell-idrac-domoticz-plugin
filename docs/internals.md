# How it works

This page covers the behaviour that affects what you see, and the design decisions behind the
parts that are easy to misread. It is not a code tour.

## Two polling tiers

Every poll interval, the plugin makes **one** request for the sensor collection, expanded so a
single response carries temperatures, fan speeds, utilization and system power.

Every *N*th poll, it additionally refreshes system health, the fault list, chassis state, power
supplies, storage controllers, drives, volumes, network interfaces and the Dell attribute set, and
re-runs discovery so new hardware appears.

Each slow-tier sub-request is guarded on its own. If the storage call fails, you lose the storage
update for that cycle and keep everything else, rather than losing the whole poll.

## Discovery, not hardcoding

Redfish resource ids like `System.Embedded.1` are conventional but not guaranteed. The plugin
reads the `Systems`, `Chassis` and `Managers` collections and uses what the server actually
reports, falling back to the conventional ids only when a collection cannot be read.

The same caution applies one level down. **Sensor ids differ between models**: the chassis inlet
probe is `InletTemp` on one PowerEdge and `SystemBoardInletTemp` on another. A hardcoded lookup
silently loses the reading on half a fleet, so each sensor slot carries the known aliases and
takes the first one that reports a value.

## A missing reading is never a zero

If a sensor reports no value, the plugin writes **no device update at all** for it.

This is the single most important rule in the plugin. Domoticz keeps history, so one zero written
into a temperature or energy device is in that device's graph permanently, and no later correct
reading removes it.

The same rule covers sentinel values that are not really readings. A powered-off host reports its
maximum DIMM temperature as `-128.0`, which is a signed-byte "no reading" marker rather than a
measurement. The plugin rejects out-of-range Celsius readings so that value never reaches a
device. The rule applies to temperatures only; a negative wattage is left alone, because there it
could be genuine.

## What happens when the iDRAC is unreachable

The plugin **writes nothing**. It does not zero devices and it does not flag them itself.

Domoticz already does its own staleness detection: it compares each device's last-update time
against the `SensorTimeout` preference and marks the device timed out for you, exactly as it does
for built-in hardware. So the correct behaviour on failure is to leave every device untouched, let
its last good value stay on screen, and let Domoticz age it out.

Meanwhile the plugin backs off. The wait starts at 20 seconds and **doubles** on each consecutive
failure, up to a 15 minute ceiling, and resets to zero as soon as one poll succeeds:

```
Error: iDRAC unreachable, backing off 20s: ...
Error: iDRAC unreachable, backing off 40s: ...
Error: iDRAC unreachable, backing off 80s: ...
```

## Retries are asymmetric on purpose

- A **refused connection** is retried. It fails in a couple of milliseconds, so retrying costs
  nothing and covers a transient blip.
- A **timeout** is never retried. It has already spent its full budget, so a retry multiplies how
  long a single poll blocks. Three retries at a 30 second timeout would stall one poll for over 90
  seconds.
- Transient HTTP statuses (401, 500, 503) are retried, because Dell's own tooling treats them as
  transient rather than fatal while the controller is busy.
- A `POST` is **never** retried, whatever the failure. Replaying a lost power action could
  power-cycle a server that already obeyed.

An iDRAC restart, measured twice, has two distinct phases: roughly three minutes of refused
connections failing in milliseconds, then a short window where the controller accepts connections
but does not answer, producing timeouts. The split above is chosen for exactly that shape.

## Unit numbers persist

Every discovered component is assigned a Domoticz unit number once, from a block reserved for its
type, and that assignment is stored. Later polls reuse it.

A vacated unit number is **not** recycled. If you swap a drive, the new drive gets a new unit
number rather than inheriting the old drive's history. Blocks are finite, so a very long-lived
install with a lot of hardware churn could exhaust one; if that happens the plugin skips the
unplaceable items, keeps everything else working, and says which ones it could not place rather
than failing the poll silently.

## Name ownership

When the plugin creates a device it records the name it used. On later polls it only renames a
device whose current name still matches what it last set. **Rename a device yourself and the
plugin stops touching its name**, permanently.

## Health mapping

Redfish reports `OK`, `Warning` and `Critical`. Dell's OEM rollups use a different vocabulary,
including `Error` where Redfish says `Critical`, and `Unknown` where a component is not present or
not powered.

Both vocabularies are mapped explicitly. An unrecognised value maps to grey `Unknown (<value>)`
rather than to green, so a status the plugin does not know about is visibly unknown instead of
silently passing as healthy. `Unknown` itself is grey, not red: a powered-off host reports
`Unknown` for nearly everything, and that is an absence of information, not an alarm.

## Testing

The whole plugin is tested against recorded Redfish payloads captured from real servers, so the
suite runs in about a second with no hardware. Three fixture profiles are committed: a healthy
machine, the same machine in a genuinely degraded state captured during a real power supply
failure, and a synthetic dual-socket 24-drive variant that exercises discovery beyond the
hardware available.

A fourth state, a server whose host is powered off while its iDRAC stays up, was captured from a
second machine and used to find and fix four real defects, but it is **not** committed as a
fixture profile yet. Until it is, that state is covered by tests using synthesised absence, which
is coverage rather than verification.

Captured payloads are sanitized before they enter the repository, and a test gates that.
