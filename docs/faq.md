# Troubleshooting / FAQ

Organised by what you see, not by what is happening internally.

## Installation

### No new hardware type appears in the list

Domoticz could not parse the plugin manifest, so it never registered the hardware type.

Check the Domoticz log at startup for the plugin count:

```
Status: PluginSystem: Started, Python version '3.13.5', 3 plugin definitions loaded.
```

It should be one higher than before you installed. If it is not:

- Confirm `plugin.py` is directly inside its own folder under `plugins`, not nested deeper and not loose in `plugins` itself.
- Confirm your Domoticz build has the Python plugin system enabled.
- Look for a line mentioning `dellidrac` in the log, which will name the parse problem.

### The hardware is added but no devices appear

Devices are created on the **first successful poll**, not when you click Add, so wait one poll interval (30 seconds by default).

If nothing arrives after that, look for:

```
Error: Dell iDRAC Monitor: iDRAC unreachable, backing off 20s: ...
```

Then check:

- The address has **no scheme** and no trailing path. Just `hostname` or `10.0.0.5`.
- The machine running Domoticz can reach the iDRAC on port 443. In a container, that means the container, not the host.
- The credentials work by signing in to the iDRAC web interface with them.

### Fewer devices than I expected

That is usually correct rather than a fault. The plugin only creates devices for hardware the iDRAC actually describes, and skips sensors that report no value. Common reasons:

- A device family is switched off in [Settings](settings.md).
- The server genuinely does not report that sensor. Not every PowerEdge exposes exhaust temperature, for instance.
- The host is powered off, so most sensors report nothing at all.
- The [per-component power](devices.md#per-component-power-needs-a-licence) devices need a licence most machines do not have, so on a typical iDRAC six of the devices in the documentation are legitimately missing.
- The drive-life percentage devices are **off by default**. See [Drive life % devices](settings.md#drive-life-devices).

## Running

### Devices show as timed out and their values are stale

This is the plugin behaving correctly during an outage. It **holds the last known value** rather than writing a zero, and Domoticz marks the device stale itself based on its last update time.

Look for `iDRAC unreachable, backing off` in the log. The wait doubles on each consecutive failure up to 15 minutes and resets as soon as one poll succeeds. An iDRAC reboot typically takes three to four minutes to recover.

If it never recovers, the address, credentials or network path is the problem, not a transient outage.

### The log says the plugin thread ended unexpectedly

```
Error: Dell iDRAC Monitor hardware (8) thread seems to have ended unexpectedly
```

This is Domoticz's own watchdog, which fires when hardware has not reported in for 60 seconds. It only logs; it does not restart anything.

If you see it, a single poll is blocking longer than 60 seconds, which in practice means your **Request Timeout** is set high and the iDRAC address is unreachable in a way that blackholes packets rather than refusing them. Lower the timeout somewhat or fix the address. At the default 30 second timeout a single failed poll cannot reach the watchdog threshold.

### Everything fails and the log mentions a certificate

Turn **Verify TLS certificate** off, or install a certificate that the machine running Domoticz trusts. An iDRAC ships with a self-signed certificate, so verification fails on a stock machine. See [Security](security.md).

### Authentication keeps failing

Confirm the account works by signing in to the iDRAC web interface with it.

!!! warning "A wrong password can lock the account"
    iDRAC locks an account after repeated failed attempts. A wrong password saved in Domoticz will retry on every poll, so it can lock you out through sheer volume. Fix or disable the hardware entry before the lockout window resets.

### Lowering Request Timeout made things worse

A recovering iDRAC can take several seconds to answer its first request after a restart, sometimes the better part of ten. A short timeout turns a normal recovery into a failed poll and starts a backoff you did not need. The 30 second default is deliberate.

## Readings that look wrong

### A power supply reads 0 W or close to it

Normal on a server configured for hot standby, where one supply carries the load and the other idles. Wattage alone is not a fault signal and the plugin never treats it as one.

The signals that do mean something are the supply's own health and the **Power Redundancy** device.

### System Health is red but every component reads OK

Dell's health rollups track **raised faults**, not instantaneous component state, so a rollup can stay red while each individual part reports healthy. This is not a bug in the plugin and it is not a stale reading.

The System Health tile shows the iDRAC's own fault message when there is one, and that sentence is the explanation. For example `Power supply redundancy is lost.` points at a redundancy condition that no per-component health field reports.

The fault clears when the underlying condition clears. Clearing the system event log does **not** clear it: the fault list is a separate store tracking the live condition, which was confirmed by clearing the log and watching the fault persist.

### Power State says On but I shut the server down

Power State reflects what the iDRAC reports, and a graceful shutdown request is fire-and-forget: the iDRAC accepts it and returns success even when no operating system is there to act on it. The log says the action was *accepted*, not that it succeeded. If the state does not change, the request never reached anything that could act on it. See [Power control](control.md).

### The energy counter does not match my meter

The counter is integrated by the plugin from the wattage the server reports, which is board power as the iDRAC measures it. It is not a revenue meter, and it does not include the conversion loss between wall and board, which is typically a few percent.

Energy accrued while Domoticz is not running is not recovered. The iDRAC's own lifetime counter is not used, because it does not accumulate continuously and would produce invented plateaus and jumps. See [Energy](devices.md#energy).

With [Energy counters](settings.md#energy-counters) on, up to fifteen devices carry a counter this way: Server Power, the six subsystem power devices, each power supply and each GPU. The subsystem, power supply and GPU counters are not meant to add up to Server Power and will not: each measures one internal rail, and together they never account for the whole machine. See [Why the component counters do not add up to Server Power](devices.md#why-the-component-counters-do-not-add-up-to-server-power) for the actual shortfall measured across a fleet of test servers, rather than repeating it here.

### The fan and temperature cards have no coloured bar

The bands are computed and sent, and your Domoticz build is discarding them. Plugin-supplied bar ranges need [domoticz/domoticz#6968](https://github.com/domoticz/domoticz/pull/6968), merged 19 August 2026, which is **not in any stable release yet**, 2026.3 included. A beta or development build has it. Nothing is logged, because from the plugin's side the write succeeded.

Two other reasons a specific card has no bar, both correct behaviour:

- The server reports no thresholds for that sensor, or only one of the two critical limits. The axis cannot be derived from one edge, so no bar is drawn rather than a guessed one.
- **Fan bar maximum** is set to `0`, which switches fan bars off.

See [Bar graphs](devices.md#bar-graphs).

### The System Health or Power Redundancy card shows literal `<ul><li>` or `<a href=...>` text

**Formatted card text** needs a Domoticz build that renders Text and Alert device data as HTML, which is Domoticz 2026.1 or newer. On an older build the markup is not rendered and shows up on the card as raw tags instead of a bullet list and a link.

Update Domoticz to 2026.1 or newer, or turn [Formatted card text](settings.md#formatted-card-text) off to go back to plain single-line text.

### Power Redundancy stopped updating

The redundancy group arrives in the same payload as the power supplies, so switching **Power supplies** off in [Settings](settings.md#devices) stops it being read. The device is not deleted, it just stops receiving values, and Domoticz eventually marks it stale.

### A temperature reads a huge negative number

It should not, and if it does, please report it. The plugin rejects out-of-range Celsius readings specifically because a powered-off host reports `-128.0` as a "no reading" marker.

## Per-component power and GPUs

### The CPU, memory and storage power devices never appeared

They need Dell's telemetry service, which is licence-gated, and most iDRACs do not have the licence. The plugin asks once per plugin start and then says so in the log:

```
Status: Dell iDRAC Monitor: per-component power unavailable, so those devices will not be created
(needs Dell telemetry, which is licence-gated): ...
```

Two licences unlock it, by different routes: **iDRAC Datacenter** for Dell's own built-in reports, and **OpenManage Enterprise Advanced** for the OME Power Manager reports. See [Per-component power](devices.md#per-component-power-needs-a-licence).

If you do have a licence, telemetry still has to be switched on. Either set `Telemetry.1.EnableTelemetry` and `TelemetryPowerMetrics.1.EnableTelemetry` to `Enabled` yourself, or switch on [Configure iDRAC telemetry](settings.md#configure-idrac-telemetry).

### The log says telemetry is reachable but carries no power metrics

```
Status: Dell iDRAC Monitor: Dell telemetry is reachable but no report carries power metrics, so
the per-component power devices will not be created
```

The service answered, but none of the reports the machine serves contained any of the metrics the plugin wants. The usual cause is that the specific report is still disabled while the master switch is on. Enabling `TelemetryPowerMetrics.1.EnableTelemetry`, or the equivalent Power Manager report, is what fills it in.

### I turned on Configure iDRAC telemetry and nothing changed

It is attempted **once per plugin start**, and only when per-component power was already found to be unavailable, so nothing happens on a machine where telemetry already works. Look for either of these in the log:

```
Status: Dell iDRAC Monitor: configuring iDRAC telemetry, because per-component power was
unavailable and Configure iDRAC telemetry is on: ...
Error: Dell iDRAC Monitor: could not configure iDRAC telemetry, which usually means the licence
does not allow it: ...
```

If neither appears, the plugin never got as far as trying. If the error appears, the licence does not permit it and no setting in the plugin will change that.

### My GPUs do not appear

GPU figures come from telemetry as well, so everything above applies first. GPU power and temperature have now been read live from two GPU servers, a 7-card Dell DSS8440 and a 4-card PowerEdge R7525. Cards that report temperature but no power, which both machines had, produce a temperature device on their own. If you have the licence and the cards and still see nothing, that is worth reporting.

## Control

### A power command is refused

Work through these in order:

1. Is **Allow Control** set to `Yes`?
2. For Force Off or Power Cycle, is **Allow Force Off and Power Cycle** also enabled?
3. Does the selector entry read `(unavailable)`? Then the server is not currently offering that action, which usually means it does not apply in the current power state.
4. Does the iDRAC account have **Server Control** privilege? A read-only account can monitor but not act.

### I turned control off but the control devices are still there

They are not deleted, only made inert. Every command is refused at the guard so nothing can leak through, but the widgets stay visible and clickable with no sign that they do nothing. Delete them under **Setup** then **Devices** if you want them gone.

## Things the plugin cannot do

### It does not see my UPS

The iDRAC cannot report UPS battery health, charge or runtime. It only knows whether input voltage is present at each power supply.

That distinction matters. The iDRAC will tell you the instant a supply loses input voltage, but nothing in Redfish can warn you that a UPS battery has degraded and will not hold the load next time.

For real UPS monitoring, add Domoticz's native NUT or apcupsd support alongside this plugin.

### It only shows one power redundancy group

Chassis that expose several redundancy groups will show only the first.

