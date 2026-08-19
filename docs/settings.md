# Settings

Every setting lives on the hardware page in Domoticz: **Setup** then **Hardware**, then select the
Dell iDRAC Monitor entry. Changing any of them restarts the plugin. Your devices and their history
are kept.

## Connection

| Setting | Default | What it does |
|---|---|---|
| **iDRAC Address** | none | Hostname or IP of the iDRAC, with no scheme and no trailing path. A leading `https://` or `http://` is stripped for you, and a trailing `/` is removed. |
| **Username** | `root` | iDRAC account. A read-only account is enough for monitoring. |
| **Password** | none | Stored in the Domoticz database in cleartext. Never written to the log. See [Security](security.md). |
| **Allow Control** | `No` | Master switch for power actions and the identify LED. See [Power control](control.md). |

## Polling

| Setting | Default | Range | What it does |
|---|---|---|---|
| **Poll Interval (s)** | 30 | 20 to 600, step 10 | How often live sensors are read. One HTTP request per poll. |
| **Slow Poll (every N polls)** | 10 | 1 to 60 | How often the slower information is refreshed, as a **multiple** of the poll interval. At the defaults that is every 5 minutes. |

The plugin polls in two tiers because they cost very differently.

The **fast tier** is a single request for the sensor collection: temperatures, fan speeds,
utilization and system power. That is what you want frequently.

The **slow tier** re-reads system health, the fault list, chassis state, power supplies, storage
controllers, drives, volumes, network interfaces and the Dell attribute set, and re-runs
discovery so newly added hardware appears. That is several requests, so running it every poll
would put needless load on the iDRAC's management controller for information that changes rarely.

!!! note "Why the minimum is 20 seconds and the step is 10"
    Domoticz calls the plugin on a fixed 10-second heartbeat, and the plugin polls on the first
    heartbeat at or past your interval. A value that is not a multiple of 10 would therefore poll
    later than you asked. The manifest constrains the field so the setting cannot lie to you.

## Devices

These control which optional device families are created. Turning one off stops the plugin
creating and updating those devices; it does **not** delete devices that already exist.

| Setting | Default | What it does |
|---|---|---|
| **Physical drives** | on | One alert device per physical disk. |
| **RAID volumes** | on | One alert device per virtual disk. |
| **Power supplies** | on | One wattage device per PSU. |
| **Network interfaces** | on | One alert device per NIC port. |
| **Drive life warning (%)** | 10 | Warn when a drive reports less predicted media life remaining than this. Only applies to drives that report the figure at all, which in practice means SSDs. |

Turning off a family also skips the requests that fetch it, so on a server with many drives,
switching **Physical drives** off measurably shortens the slow tier.

## Control

| Setting | Default | What it does |
|---|---|---|
| **Allow Force Off and Power Cycle** | off | Adds the two hard power actions to the Power Control selector. |

This is inert while **Allow Control** is `No`: with control off, no control device is created at
all and every command is refused. Read [Power control](control.md) before enabling either.

## Advanced

| Setting | Default | What it does |
|---|---|---|
| **Verify TLS certificate** | off | Off because an iDRAC ships a self-signed certificate. While off, traffic is encrypted but **not authenticated**. See [Security](security.md). |
| **Request Timeout (s)** | 30 | Per-request timeout. |
| **Debug Level** | `None` | `Basic` and `Verbose` add detail to the Domoticz log. The password is never logged at any level. |

!!! danger "Do not lower Request Timeout much"
    A recovering iDRAC can take several seconds to answer its first request after a restart. This
    was measured at 1.9 and 7.4 seconds across two real iDRAC restarts. A short timeout turns a
    normal recovery into a failed poll and starts a backoff you did not need. The 30 second
    default is deliberate.

## When a setting is adjusted for you

If a value is out of range or unreadable, the plugin clamps or falls back to the default and says
so in the log at Status level, for example:

```
Status: Dell iDRAC Monitor: setting adjusted: PollInterval: 5 is outside 20-600, using 20
```

A silently rewritten setting you never see is worse than a wrong one you can spot, so these are
always reported rather than applied quietly.
