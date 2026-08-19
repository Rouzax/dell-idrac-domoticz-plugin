# How it works

This page covers the behaviour that affects what you see, and the design decisions behind the parts that are easy to misread. It is not a code tour.

## Two polling tiers

Every poll interval, the plugin makes **one** request for the sensor collection, expanded so a single response carries temperatures, fan speeds, utilization and system power.

Every *N*th poll, it additionally refreshes system health, the fault list, chassis state, power supplies, storage controllers, drives, volumes, network interfaces and the Dell attribute set, and re-runs discovery so new hardware appears.

Each slow-tier sub-request is guarded on its own. If the storage call fails, you lose the storage update for that cycle and keep everything else, rather than losing the whole poll.

Where [per-component power](devices.md#per-component-power-needs-a-licence) is available, the telemetry report is read on the **fast** tier, not the slow one. It carries the wall-draw figure the energy counter integrates, which would otherwise be up to a whole slow cycle out of date.

## Discovery, not hardcoding

Redfish resource ids like `System.Embedded.1` are conventional but not guaranteed. The plugin reads the `Systems`, `Chassis` and `Managers` collections and uses what the server actually reports, falling back to the conventional ids only when a collection cannot be read.

The same caution applies one level down. **Sensor ids differ between models**: the chassis inlet probe is `InletTemp` on one PowerEdge and `SystemBoardInletTemp` on another. A hardcoded lookup silently loses the reading on half a fleet, so each sensor slot carries the known aliases and takes the first one that reports a value.

Telemetry works the same way. The report that carries per-component power has a different name depending on whether the licence is iDRAC Datacenter or OpenManage Enterprise Advanced, so the plugin looks at what each report contains rather than what it is called. That is why the same setting works on both kinds of machine.

Fans are recognised by the fact that they report a speed in RPM, not by their name, so an unusual cooling device on your chassis will still show up, under whatever name the server gives it.

## A missing reading is never a zero

If a sensor reports no value, the plugin writes **no device update at all** for it.

This is the single most important rule in the plugin. Domoticz keeps history, so one zero written into a temperature or energy device is in that device's graph permanently, and no later correct reading removes it.

The same rule covers sentinel values that are not really readings. A powered-off host reports its maximum DIMM temperature as `-128.0`, which is a signed-byte "no reading" marker rather than a measurement. The plugin rejects out-of-range Celsius readings so that value never reaches a device. The rule applies to temperatures only; a negative wattage is left alone, because there it could be genuine.

## What happens when the iDRAC is unreachable

The plugin **writes nothing**. It does not zero devices and it does not flag them itself.

Domoticz already does its own staleness detection: it compares each device's last-update time against the `SensorTimeout` preference and marks the device timed out for you, exactly as it does for built-in hardware. So the correct behaviour on failure is to leave every device untouched, let its last good value stay on screen, and let Domoticz age it out.

Meanwhile the plugin backs off. The wait starts at 20 seconds and **doubles** on each consecutive failure, up to a 15 minute ceiling, and resets to zero as soon as one poll succeeds:

```
Error: iDRAC unreachable, backing off 20s: ...
Error: iDRAC unreachable, backing off 40s: ...
Error: iDRAC unreachable, backing off 80s: ...
```

## Why a slow iDRAC is handled differently from an absent one

- A **refused connection** is retried. It fails in a couple of milliseconds, so retrying costs nothing and covers a transient blip.
- A **timeout** is never retried. It has already spent its full budget, so a retry multiplies how long a single poll blocks. Three retries at a 30 second timeout would stall one poll for over 90 seconds.
- Transient HTTP statuses (401, 500, 503) are retried, because Dell's own tooling treats them as transient rather than fatal while the controller is busy.
- Only a `GET` is retried at all. A `POST` or `PATCH` makes exactly one attempt, whatever the failure, because replaying a lost power action could power-cycle a server that already obeyed.

That split matches what an iDRAC reboot actually looks like: a few minutes where connections are refused outright, then a short window where the controller accepts connections but does not answer yet. Retrying the cheap failure and not the expensive one keeps a poll short throughout.

## One Domoticz Device per family

Domoticz gives each **Device** its own unit-number space of 1 to 255, and a plugin may create as many Devices as it likes. This plugin uses one per family, so you will see several entries rather than one:

| Device | Holds |
|---|---|
| `..._system` | overall power, health, power state, chassis temperatures, utilization, uptime, boot status, intrusion, redundancy, per-component power |
| `..._thermal` | per-CPU and DIMM temperatures, fan speeds |
| `..._power` | per-power-supply wattage |
| `..._storage` | RAID volumes, physical drives, drive life |
| `..._network` | NIC ports |
| `..._gpu` | per-GPU power and temperature |
| `..._control` | power control and identify LED |

The split exists because a single Device caps out at 255 units, which a machine with many drives and GPUs can exhaust. Each Device is created automatically when its first unit appears, so nothing needs setting up.

One consequence worth knowing: **a unit number is unique only within its Device**. Unit 1 exists on every one of them. Anything acting on a unit, including the plugin's own command handling, has to match the Device as well as the number.

## Unit numbers persist

Every discovered component is assigned a Domoticz unit number once, from a block reserved for its type, and that assignment is stored. Later polls reuse it.

A vacated unit number is **not** recycled. If you swap a drive, the new drive gets a new unit number rather than inheriting the old drive's history. Blocks are finite, so a very long-lived install with a lot of hardware churn could exhaust one; if that happens the plugin skips the unplaceable items, keeps everything else working, and says which ones it could not place rather than failing the poll silently:

```
Error: no free unit for 1 item(s), not shown: Fan.Embedded.21
```

That message is logged when the situation changes, not on every poll, and a matching Status line appears when it clears.

## What the plugin owns, and what you own

Three properties are written when a device is created and then treated as yours:

- **Name.** The plugin records the name it used. On later polls it renames only a device whose current name still matches what it last set. **Rename a device yourself and the plugin stops touching its name**, permanently.
- **Icon.** Set at creation only, never afterwards.
- **Bar ranges.** These are derived from hardware thresholds and from your settings, so unlike an icon they do have to follow a change to either. They are still only rewritten while they are the bands the plugin last wrote. Edit a bar by hand and it is yours from then on.

In practice: change the fan bar maximum and every fan bar follows it on the next poll, unless you have tuned one yourself, in which case yours survives.

## Health mapping

Redfish reports `OK`, `Warning` and `Critical`. Dell's OEM rollups use a different vocabulary, including `Error` where Redfish says `Critical`, and `Unknown` where a component is not present or not powered.

Both vocabularies are mapped explicitly. An unrecognised value maps to grey `Unknown (<value>)` rather than to green, so a status the plugin does not know about is visibly unknown instead of silently passing as healthy. `Unknown` itself is grey, not red: a powered-off host reports `Unknown` for nearly everything, and that is an absence of information, not an alarm.
