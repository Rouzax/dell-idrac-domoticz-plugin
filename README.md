# Dell iDRAC Monitor for Domoticz

Monitors a Dell PowerEdge server from Domoticz by reading its iDRAC over the Redfish API. It
creates Domoticz devices for the hardware your server actually has, so a machine with three fans
and eight drives gets three fan devices and eight drive devices, not a fixed list.

Read-only by default. Power control and the identify LED exist but stay switched off until you
deliberately enable them.

## What you need before you start

- **A Dell PowerEdge with an iDRAC that speaks Redfish.** Developed and verified against iDRAC 9
  on two 15G PowerEdge servers, one Intel and one AMD. Dell's own Redfish reference documents
  iDRAC 9 and 10. Older iDRAC generations and non-Dell Redfish are untested rather than known
  broken: the plugin discovers resource paths from the service instead of assuming them, and
  guards each subsystem separately, so an endpoint an older iDRAC lacks should degrade to a
  warning rather than break the poll.
- **An iDRAC account.** A read-only account is enough for monitoring. Power control and the
  identify LED need an account with Server Control privilege.
- **Network reachability from the machine running Domoticz to the iDRAC**, on HTTPS port 443.
- **Domoticz with the Python plugin system enabled**, Python 3.11 or newer.

The plugin uses only the Python standard library. There is nothing to `pip install`.

## Install

1. Copy this folder into Domoticz's `plugins` directory so that `plugin.py` sits at
   `plugins/dell-idrac-plugin/plugin.py`.
2. Restart Domoticz.
3. Check the log. It should say `plugin definitions loaded` with a count one higher than before.
   If the count did not go up, the manifest failed to parse and the plugin will not appear in the
   hardware list.
4. Go to **Setup** then **Hardware**, add hardware of type **Dell iDRAC Monitor**, fill in the
   address, username and password, and save.

Devices appear after the first successful poll, which is one poll interval later, not instantly.

## Settings

| Setting | Default | What it does |
|---|---|---|
| iDRAC Address | none | Hostname or IP, with no scheme. `https://` is stripped if you paste it. |
| Username / Password | none | iDRAC credentials. See [Security](#security). |
| Allow Control | No | Master switch for power actions and the identify LED. See [Control](#control). |
| Poll Interval (s) | 30 | How often live sensors are read. One request per poll. Minimum 20, in steps of 10. |
| Slow Poll (every N polls) | 10 | How often health, storage, network and discovery are refreshed, as a multiple of the poll interval. 30 s and 10 means every 5 minutes. |
| Physical drives | on | Create a device per physical disk. |
| RAID volumes | on | Create a device per virtual disk. |
| Power supplies | on | Create a device per PSU. |
| Network interfaces | on | Create a device per NIC port. |
| Drive life warning (%) | 10 | Warn when an SSD reports less predicted media life remaining than this. |
| Allow Force Off and Power Cycle | off | Adds the two hard power actions. Inert unless Allow Control is Yes. |
| Verify TLS certificate | off | See [Security](#security). |
| Request Timeout (s) | 30 | Per-request timeout. Do not lower it below about 10; see [Troubleshooting](#troubleshooting). |
| Debug Level | None | `Basic` and `Verbose` add detail to the Domoticz log. The password is never logged at any level. |

Changing a setting restarts the plugin. Your devices and their history are kept.

## Devices it creates

The exact set depends on what the server reports. Nothing is created for hardware the iDRAC does
not describe, and a sensor that reports no reading produces no device at all rather than a zero.

**Always, when the server reports them:**

| Device | Type | Notes |
|---|---|---|
| Server Power | kWh | Live watts plus an energy counter the plugin integrates itself. |
| System Health | Alert | One tile for overall health. When the iDRAC raises a fault it shows the iDRAC's own wording, for example `Power supply redundancy is lost.` |
| Power State | Alert | `On` in green, `Off` in grey. Read-only; use Power Control to change it. |
| Inlet Temp, Exhaust Temp | Temperature | Chassis airflow. |
| CPU / Memory / I/O / System Usage | Percentage | Utilization as the iDRAC reports it. |
| Uptime | Custom (hours) | Time since the host was powered on. |
| Boot Status | Text | For example `OSRunning`. |
| Chassis Intrusion | Alert | |
| Power Redundancy | Alert | Reports the redundancy group's own health, which can be Critical while every individual PSU still reads OK. |

**Per discovered component:** one temperature device per CPU, one for the hottest DIMM, one fan
device per fan, one watts device per PSU, one alert per RAID volume, per NIC port and per physical
drive.

Temperature and fan devices carry their iDRAC warning and critical thresholds in the device
description, so you can see the limits without looking them up. A threshold marked `(estimated)`
was derived by the plugin because the server did not report one.

Devices keep the unit numbers they were first given. If you remove hardware, its device stays
until you delete it, and the freed unit number is not reused.

### Icons

Fans get the Fan icon and Uptime gets the Clock icon when they are first created. If you change an
icon yourself afterwards, the plugin leaves your choice alone.

## Control

With **Allow Control** set to No, which is the default, the plugin is strictly read-only. No
control device is created at all and every command is refused.

Setting it to Yes creates two devices:

- **Power Control**, a selector with five fixed entries: Power On, Graceful Shutdown, Graceful
  Restart, Force Off and Power Cycle. Entries the server does not currently offer, or that the
  hard-power setting withholds, are shown as `(unavailable)` rather than removed, so the position
  of every entry stays stable for scenes and timers you have already saved.
- **Identify LED**, which toggles the chassis identify light.

**Allow Force Off and Power Cycle** is a second, separate gate. Graceful Shutdown and Graceful
Restart are requests handed to the host operating system, which can flush disks and close files
first. Force Off and Power Cycle cut power electrically with no warning, the equivalent of holding
the power button, and can lose data or corrupt a filesystem. Leave the hard actions off unless you
specifically need them.

Two things worth knowing before you enable control:

- Once control is on, **any** Domoticz user, scene, timer or API client with access to this
  hardware can power off the server.
- A graceful action is fire-and-forget. The iDRAC accepts it and returns success even when no
  operating system or agent is there to act on it. The log therefore says the action was
  *accepted*, not that it succeeded. Watch the Power State device for what actually happened. The
  plugin deliberately does not escalate to a forced power-off when a graceful request goes
  unanswered.

## Security

- **The iDRAC password is stored in cleartext in the Domoticz database.** This is how Domoticz
  stores hardware credentials generally, not something this plugin chose. Treat your Domoticz
  database and its backups as secrets, and prefer a dedicated read-only iDRAC account over an
  administrator one.
- The password is never written to the Domoticz log at any debug level. Error messages are
  redacted before they are logged.
- **Verify TLS certificate is off by default.** An iDRAC ships with a self-signed certificate, so
  verification would fail on a stock machine. While it is off the connection is still encrypted
  but it is **not authenticated**, which means a host on your network could impersonate the iDRAC.
  If you have installed a certificate the Domoticz machine trusts, turn verification on.

## Troubleshooting

**No new hardware type appears in the list after installing.**
The manifest did not parse. Check the Domoticz log at startup for the `plugin definitions loaded`
count and confirm it went up by one. Confirm `plugin.py` is directly inside its own folder under
`plugins`, and that the Python plugin system is enabled in your Domoticz build.

**The hardware is added but no devices appear.**
Devices are created on the first successful poll, so wait one poll interval. If nothing arrives,
look in the log for `iDRAC unreachable`. Check the address has no `https://` and no trailing path,
and that the Domoticz machine can reach the iDRAC on port 443.

**Devices appear but show as timed out, and their values are stale.**
The plugin holds the last known value rather than writing a zero when the iDRAC cannot be reached,
and Domoticz marks the device stale itself. Look for `iDRAC unreachable, backing off` in the log.
The wait doubles on each consecutive failure, up to 15 minutes, and resets as soon as one poll
succeeds. An iDRAC reboot typically takes three to four minutes to recover.

**Everything is unreachable and the log mentions a certificate.**
Turn Verify TLS certificate off, or install a certificate the Domoticz machine trusts.

**Authentication fails.**
Confirm the account works by signing in to the iDRAC web interface with it. iDRAC locks an account
after repeated failures, so a wrong password saved in Domoticz can lock you out through sheer
retry volume.

**A power command is refused.**
Check Allow Control is Yes. For Force Off or Power Cycle, also check Allow Force Off and Power
Cycle. If the selector entry reads `(unavailable)`, the server is not currently offering that
action, which commonly means the action does not apply in the current power state. The account
also needs Server Control privilege in the iDRAC.

**A PSU reads close to 0 W.**
That is normal on a server configured for hot standby, where one supply carries the load and the
other idles. Wattage alone is not a fault signal. Watch System Health and Power Redundancy
instead, which is what the plugin keys on.

**The System Health tile is red but every component reads OK.**
Dell's health rollups track raised faults, not instantaneous component state, so a rollup can stay
red while each part reports healthy. The tile shows the iDRAC's own fault text when there is one,
which is the sentence that explains why. The fault clears when the underlying condition does, not
when you clear the system event log.

**Lowering Request Timeout made things worse.**
A recovering iDRAC can take several seconds to answer its first request after a restart. The 30 s
default is deliberate. A short timeout turns a normal recovery into a failed poll.

## Limitations

- The iDRAC cannot see UPS battery health, charge or runtime. It only knows whether input voltage
  is present at each PSU. For real UPS monitoring, add NUT or apcupsd alongside this plugin.
- The lifetime energy counter the iDRAC reports is not continuous across power-off periods, so the
  plugin integrates energy itself rather than trusting it. Energy accrued while Domoticz is not
  running is not recovered.
- Only the first power redundancy group is reported.
- Turning Allow Control back off leaves the two control devices in place. They are refused at the
  guard so no power action can get through, but they stay visible until you delete them.

## Contributing

Issues and pull requests are welcome. The plugin has a test suite that runs without any hardware,
against recorded Redfish payloads:

```
pip install -r requirements-dev.txt
python3 -m pytest
```

Please keep new code covered and run `ruff check .` and `pyright` before opening a pull request.

## License

MIT. See [LICENSE](LICENSE).
