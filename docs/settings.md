# Settings

Every setting lives on the hardware page in Domoticz: **Setup** then **Hardware**, then select the Dell iDRAC Monitor entry. Changing any of them restarts the plugin. Your devices and their history are kept.

![The plugin's settings on the Domoticz hardware page](assets/settings.png)

Each setting carries its own explanation on that page, and a link to the matching section here.

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
| **Poll Interval (s)** | 30 | 20 to 600, step 10 | How often live sensors are read. |
| **Slow Poll (every N polls)** | 10 | 1 to 60 | How often the slower information is refreshed, as a **multiple** of the poll interval. At the defaults that is every 5 minutes. |

The plugin polls in two tiers because they cost very differently.

The **fast tier** is a single request for the sensor collection: temperatures, fan speeds, utilization and system power. That is what you want frequently. On a machine where [per-component power](devices.md#per-component-power-needs-a-licence) is available, the fast tier also reads the telemetry report that carries it, which is one further request.

The **slow tier** re-reads system health, the fault list, chassis state, power supplies, storage controllers, drives, volumes, network interfaces and the Dell attribute set, and re-runs discovery so newly added hardware appears. That is several requests, so running it every poll would put needless load on the iDRAC's management controller for information that changes rarely.

!!! note "Why the minimum is 20 seconds and the step is 10"
    Domoticz calls the plugin on a fixed 10-second heartbeat, and the plugin polls on the first heartbeat at or past your interval. A value that is not a multiple of 10 would therefore poll later than you asked. The manifest constrains the field so the setting cannot lie to you.

## Devices

These control which optional device families are created. Turning one off stops the plugin creating and updating those devices; it does **not** delete devices that already exist.

| Setting | Default | What it does |
|---|---|---|
| **Physical drives** | on | One alert device per physical disk. |
| **RAID volumes** | on | One alert device per virtual disk. |
| **Power supplies** | on | One wattage device per PSU. Also the source of the Power Redundancy device, see below. |
| **Network interfaces** | on | One alert device per NIC port. |
| **Drive life warning (%)** | 10 | Warn when a drive reports less predicted media life remaining than this. Only applies to drives that report the figure at all, which in practice means SSDs. |
| **Drive life % devices** | off | A second device per drive reporting predicted media life as a graphable percentage. See below. |
| **Fan bar maximum (RPM)** | 6000 | Top of the scale on fan bar graphs. `0` switches fan bars off. See below. |

Turning off a family also skips the requests that fetch it, so on a server with many drives, switching **Physical drives** off measurably shortens the slow tier.

!!! warning "Power supplies also controls Power Redundancy"
    The redundancy group is reported inside the same Redfish payload as the power supplies, so switching **Power supplies** off stops the [Power Redundancy](devices.md#power-redundancy) device updating too. The device is not deleted; it simply stops receiving values and Domoticz ages it out. If you want redundancy monitoring, leave power supplies on.

### Drive life % devices

Every physical drive already reports its predicted media life on its own tile, as text such as `SSD, life 96%`. That tile is an Alert device, and Domoticz does not graph an Alert.

Switching this on adds a **second** device per drive, a Percentage carrying the same figure, which Domoticz does graph and which gets a [bar](devices.md#bar-graphs) coloured from your **Drive life warning (%)** setting. It is off by default because for most people the number on the drive's own tile is enough, and one extra device per drive adds up on a full chassis.

Only drives that actually report a life figure get one, which in practice means SSDs. The setting has no effect while **Physical drives** is off, since the life device hangs off the drive device.

### Why the fan bar maximum is a setting

Redfish does not report a maximum fan speed, so the plugin cannot detect one. There is no sensible default either: on one tower server the three chassis fans topped out at 4920, 4920 and **5520** RPM, so even a single machine has no one maximum, and 1U servers run far faster again.

Pick a value a little above what your fans actually reach. If you do not know, run them at full speed once and read the devices, or leave the default.

A fan spinning faster than this setting is not a problem: the bar simply reads full and stays green. That is the correct reading for a fan, where a **low** speed is the fault and a high one just means it is working hard.

Changing this value updates the bars on the next poll, unless you have edited a fan's bands by hand, in which case your version is left alone.

## Control

| Setting | Default | What it does |
|---|---|---|
| **Allow Force Off and Power Cycle** | off | Adds the two hard power actions to the Power Control selector. |

This is inert while **Allow Control** is `No`: with control off, no control device is created at all and every command is refused. Read [Power control](control.md) before enabling either.

## Advanced

| Setting | Default | Range | What it does |
|---|---|---|---|
| **Verify TLS certificate** | off | | Off because an iDRAC ships a self-signed certificate. While off, traffic is encrypted but **not authenticated**. See [Security](security.md). |
| **Configure iDRAC telemetry** | off | | Switches Dell telemetry on so per-component power devices can appear. The only setting that writes configuration to your server. See below. |
| **Request Timeout (s)** | 30 | 5 to 120, step 5 | Per-request timeout. |
| **Debug Level** | `None` | | `Basic` and `Verbose` add detail to the Domoticz log. The password is never logged at any level. |

### Configure iDRAC telemetry

[Per-component power](devices.md#per-component-power-needs-a-licence) comes from Dell's telemetry service, which is licence-gated and switched off by default on the iDRAC. Turning this setting on lets the plugin switch it on for you.

This is the **only** setting that makes the plugin write configuration to your server, so it has deliberate limits:

- It acts **only** when per-component power was already found to be unavailable. On a machine where telemetry is already working, including one managed by OpenManage Enterprise, the plugin never touches the configuration.
- It writes exactly two iDRAC attributes, `Telemetry.1.EnableTelemetry` and `TelemetryPowerMetrics.1.EnableTelemetry`, both set to `Enabled`, and nothing else.
- It tries **once per plugin start**. A machine that cannot be fixed this way, because the licence does not allow it, is not written to again on every poll.
- It says what it did in the Domoticz log, at Status level, before it does it.

If the licence does not permit telemetry you will see:

```
Error: Dell iDRAC Monitor: could not configure iDRAC telemetry, which usually means the licence
does not allow it: ...
```

Leave this off if OpenManage manages the server, or if you would rather set the two attributes yourself from the iDRAC interface or with `racadm`.

!!! danger "Do not lower Request Timeout much"
    A recovering iDRAC can take several seconds to answer its first request after a restart, sometimes the better part of ten. A short timeout turns a normal recovery into a failed poll and starts a backoff you did not need. The 30 second default is deliberate.

## When a setting is adjusted for you

If a value is out of range or unreadable, the plugin clamps or falls back to the default and says so in the log at Status level, for example:

```
Status: Dell iDRAC Monitor: setting adjusted: PollInterval: 5 is outside 20-600, using 20
```

A silently rewritten setting you never see is worse than a wrong one you can spot, so these are always reported rather than applied quietly.
