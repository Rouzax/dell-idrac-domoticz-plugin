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

- Confirm `plugin.py` is directly inside its own folder under `plugins`, not nested deeper and not
  loose in `plugins` itself.
- Confirm your Domoticz build has the Python plugin system enabled.
- Look for a line mentioning `dellidrac` in the log, which will name the parse problem.

### The hardware is added but no devices appear

Devices are created on the **first successful poll**, not when you click Add, so wait one poll
interval (30 seconds by default).

If nothing arrives after that, look for:

```
Error: Dell iDRAC Monitor: iDRAC unreachable, backing off 20s: ...
```

Then check:

- The address has **no scheme** and no trailing path. Just `hostname` or `10.0.0.5`.
- The machine running Domoticz can reach the iDRAC on port 443. In a container, that means the
  container, not the host.
- The credentials work by signing in to the iDRAC web interface with them.

### Fewer devices than I expected

That is usually correct rather than a fault. The plugin only creates devices for hardware the
iDRAC actually describes, and skips sensors that report no value. Common reasons:

- A device family is switched off in [Settings](settings.md).
- The server genuinely does not report that sensor. Not every PowerEdge exposes exhaust
  temperature, for instance.
- The host is powered off, so most sensors report nothing at all.

## Running

### Devices show as timed out and their values are stale

This is the plugin behaving correctly during an outage. It **holds the last known value** rather
than writing a zero, and Domoticz marks the device stale itself based on its last update time.

Look for `iDRAC unreachable, backing off` in the log. The wait doubles on each consecutive failure
up to 15 minutes and resets as soon as one poll succeeds. An iDRAC reboot typically takes three to
four minutes to recover.

If it never recovers, the address, credentials or network path is the problem, not a transient
outage.

### The log says the plugin thread ended unexpectedly

```
Error: Dell iDRAC Monitor hardware (8) thread seems to have ended unexpectedly
```

This is Domoticz's own watchdog, which fires when hardware has not reported in for 60 seconds. It
only logs; it does not restart anything.

If you see it, a single poll is blocking longer than 60 seconds, which in practice means your
**Request Timeout** is set high and the iDRAC address is unreachable in a way that blackholes
packets rather than refusing them. Lower the timeout somewhat or fix the address. At the default
30 second timeout a single failed poll cannot reach the watchdog threshold.

### Everything fails and the log mentions a certificate

Turn **Verify TLS certificate** off, or install a certificate that the machine running Domoticz
trusts. An iDRAC ships with a self-signed certificate, so verification fails on a stock machine.
See [Security](security.md).

### Authentication keeps failing

Confirm the account works by signing in to the iDRAC web interface with it.

!!! warning "A wrong password can lock the account"
    iDRAC locks an account after repeated failed attempts. A wrong password saved in Domoticz will
    retry on every poll, so it can lock you out through sheer volume. Fix or disable the hardware
    entry before the lockout window resets.

### Lowering Request Timeout made things worse

A recovering iDRAC can take several seconds to answer its first request after a restart, measured
at 1.9 and 7.4 seconds on two real restarts. A short timeout turns a normal recovery into a failed
poll. The 30 second default is deliberate.

## Readings that look wrong

### A power supply reads 0 W or close to it

Normal on a server configured for hot standby, where one supply carries the load and the other
idles. Wattage alone is not a fault signal and the plugin never treats it as one.

The signals that do mean something are the supply's own health and the **Power Redundancy**
device.

### System Health is red but every component reads OK

Dell's health rollups track **raised faults**, not instantaneous component state, so a rollup can
stay red while each individual part reports healthy. This is not a bug in the plugin and it is not
a stale reading.

The System Health tile shows the iDRAC's own fault message when there is one, and that sentence is
the explanation. For example `Power supply redundancy is lost.` points at a redundancy condition
that no per-component health field reports.

The fault clears when the underlying condition clears. Clearing the system event log does **not**
clear it: the fault list is a separate store tracking the live condition, which was confirmed by
clearing the log and watching the fault persist.

### Power State says On but I shut the server down

Power State reflects what the iDRAC reports, and a graceful shutdown request is fire-and-forget:
the iDRAC accepts it and returns success even when no operating system is there to act on it. The
log says the action was *accepted*, not that it succeeded. If the state does not change, the
request never reached anything that could act on it. See [Power control](control.md).

### The energy counter does not match my meter

The counter is integrated by the plugin from the wattage the server reports, which is board power
as the iDRAC measures it. It is not a revenue meter, and it does not include the conversion loss
between wall and board, which is typically a few percent.

Energy accrued while Domoticz is not running is not recovered. The iDRAC's own lifetime counter is
not used, because it does not accumulate continuously and would produce invented plateaus and
jumps. See [Energy](devices.md#energy).

### A temperature reads a huge negative number

It should not, and if it does, please report it. The plugin rejects out-of-range Celsius readings
specifically because a powered-off host reports `-128.0` as a "no reading" marker.

## Control

### A power command is refused

Work through these in order:

1. Is **Allow Control** set to `Yes`?
2. For Force Off or Power Cycle, is **Allow Force Off and Power Cycle** also enabled?
3. Does the selector entry read `(unavailable)`? Then the server is not currently offering that
   action, which usually means it does not apply in the current power state.
4. Does the iDRAC account have **Server Control** privilege? A read-only account can monitor but
   not act.

### I turned control off but the control devices are still there

They are not deleted, only made inert. Every command is refused at the guard so nothing can leak
through, but the widgets stay visible and clickable with no sign that they do nothing. Delete them
under **Setup** then **Devices** if you want them gone.

## Things the plugin cannot do

### It does not see my UPS

The iDRAC cannot report UPS battery health, charge or runtime. It only knows whether input voltage
is present at each power supply.

That limit is real and it matters: during development, a failing UPS was detected by the iDRAC as
loss of input voltage within about one second of mains being pulled, but nothing in Redfish could
have warned that the battery had degraded beforehand.

For real UPS monitoring, add Domoticz's native NUT or apcupsd support alongside this plugin.

### It only shows one power redundancy group

Chassis that expose several redundancy groups will show only the first.

### It does not report per-component power

Dell exposes per-subsystem power figures through its telemetry service, but telemetry is disabled
by default on the iDRAC and enabling it requires writing configuration to the server. The plugin
stays read-only by default, so it does not enable it for you.
