# Dell iDRAC Monitor for Domoticz

![Dell iDRAC Monitor for Domoticz](docs/assets/hero.png)

Monitors a Dell PowerEdge server from Domoticz by reading its iDRAC over the Redfish API. It creates Domoticz devices for the hardware your server actually has, so a machine with three fans and eight drives gets three fan devices and eight drive devices, not a fixed list.

Read-only by default. Power control and the identify LED exist but stay switched off until you deliberately enable them.

Full documentation: <https://rouzax.github.io/dell-idrac-domoticz-plugin/>

## What you need before you start

- **A Dell PowerEdge with an iDRAC that speaks Redfish.** Built for iDRAC 9 and 10. Older iDRAC generations and non-Dell Redfish are untested rather than known broken: the plugin asks the server what it offers instead of assuming, and handles each subsystem separately, so an endpoint your iDRAC lacks costs you that one subsystem rather than the whole poll.
- **An iDRAC account.** A read-only account is enough for monitoring. Power control and the identify LED need an account with Server Control privilege.
- **Network reachability from the machine running Domoticz to the iDRAC**, on HTTPS port 443.
- **Domoticz with the Python plugin system enabled**, Python 3.11 or newer.

The plugin uses only the Python standard library. There is nothing to `pip install`.

## Install

The `dist` branch carries only the files needed to run the plugin, so it is the leanest install and the easiest to keep updated:

```bash
cd /opt/domoticz/plugins            # adjust to your Domoticz install path
git clone -b dist --single-branch https://github.com/Rouzax/dell-idrac-domoticz-plugin.git dell-idrac
```

To update later: `cd /opt/domoticz/plugins/dell-idrac && git pull`.

Without git, download `dell-idrac-vX.Y.Z.zip` from the [releases page](https://github.com/Rouzax/dell-idrac-domoticz-plugin/releases) and unzip it into the `plugins` directory; the zip already contains the `dell-idrac` folder.

Then:

1. Restart Domoticz.
2. Check the log. It should say `plugin definitions loaded` with a count one higher than before. If the count did not go up, the manifest failed to parse and the plugin will not appear in the hardware list.
3. Go to **Setup** then **Hardware**, add hardware of type **Dell iDRAC Monitor**, fill in the address, username and password, and save.

Devices appear after the first successful poll, which is one poll interval later, not instantly. Full instructions, including the developer clone, are in the [installation guide](https://rouzax.github.io/dell-idrac-domoticz-plugin/install/).

## Settings

| Setting | Default | What it does |
|---|---|---|
| iDRAC Address | none | Hostname or IP, with no scheme. `https://` is stripped if you paste it. |
| Username | `root` | iDRAC account. Read-only is enough for monitoring. |
| Password | none | Stored in cleartext in the Domoticz database. See [Security](#security). |
| Allow Control | No | Master switch for power actions and the identify LED. See [Control](#control). |
| Poll Interval (s) | 30 | How often live sensors are read. 20 to 600, in steps of 10. |
| Slow Poll (every N polls) | 10 | How often health, storage, network and discovery are refreshed, as a multiple of the poll interval. 30 s and 10 means every 5 minutes. |
| Physical drives | on | Create a device per physical disk. |
| RAID volumes | on | Create a device per virtual disk. |
| Power supplies | on | Create a device per PSU. Also the source of the Power Redundancy device. |
| Network interfaces | on | Create a device per NIC port. |
| Drive life warning (%) | 10 | Warn when a drive reports less predicted media life remaining than this. |
| Drive life % devices | off | Add a second device per drive showing predicted media life as a graphable percentage. |
| Formatted card text | on | Renders System Health and Power Redundancy as a bullet list with a link to the iDRAC, instead of a single line of text. Changes the device `sValue`; turn it off if a dzVents script or notification matches the old plain text. |
| Energy counters | on | Reports per-component power, each power supply and each GPU as a kWh counter with a running total, instead of a plain watt gauge. Changes the device `sValue`; turn it off if a dzVents script reads it as a plain number. |
| Fan bar maximum (RPM) | 6000 | Top of the scale on fan bar graphs; 0 turns them off. Redfish reports no fan maximum, so it cannot be detected. A faster fan still reads full and green. |
| Allow Force Off and Power Cycle | off | Adds the two hard power actions. Inert unless Allow Control is Yes. |
| Verify TLS certificate | off | See [Security](#security). |
| Configure iDRAC telemetry | off | The one setting that writes configuration to your server, to unlock per-component power. See [Per-component power](#per-component-power-needs-a-licence). |
| Request Timeout (s) | 30 | Per-request timeout, 5 to 120. Do not lower it much; see [Troubleshooting](#troubleshooting). |
| Debug Level | None | `Basic` and `Verbose` add detail to the Domoticz log. The password is never logged at any level. |

Changing a setting restarts the plugin. Your devices and their history are kept.

## Devices it creates

The exact set depends on what the server reports. Nothing is created for hardware the iDRAC does not describe, and a sensor that reports no reading produces no device at all rather than a zero.

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
| Power Redundancy | Alert | The redundancy group's own health, which can be Critical while every individual PSU still reads OK. Reads in plain English, for example `Redundant, 2 supplies (1 needed)`. Removing a supply makes the iDRAC drop the group entirely, which shows as a grey `Not reported` rather than a stale green tile. |

**Per discovered component:** one temperature device per CPU, one for the hottest DIMM, one fan device per fan, one power device per PSU, one alert per RAID volume, per NIC port and per physical drive. Physical drives are named by media type and location, for example `SSD 0:2:0`, `HDD 0:2:3` and `BOSS SSD 0` for a boot card.

**Optional:** switching on **Drive life % devices** adds a second device per drive reporting predicted media life as a percentage with a bar, for drives that report the figure at all, which in practice means SSDs.

### Per-component power (needs a licence)

Where the iDRAC licence allows it, six more devices break system power down by subsystem: **CPU, memory, storage, fan, PCIe and FPGA power**. This comes from Dell's telemetry service, which is licence-gated two ways: an **iDRAC Datacenter** licence unlocks Dell's own built-in reports, and an **OpenManage Enterprise Advanced** licence unlocks OME Power Manager, whose reports the plugin reads instead on such a machine. Telemetry must also be switched on. On an iDRAC with neither licence the devices simply do not appear and nothing else changes. When it is available, Server Power also reports actual wall draw instead of the mainboard sensor.

**Configure iDRAC telemetry** will switch telemetry on for you. It is off by default, it is the only setting that writes anything to your server, and it acts only when per-component power was already found to be unavailable, so it will not disturb a machine where OpenManage already owns that configuration.

Where telemetry reports GPUs, each card also gets a power device and a temperature device.

The six subsystem devices and each GPU power device also report a running kWh total alongside live watts, so they show up in Domoticz's energy report; turn **Energy counters** off for plain watt gauges instead.

### Bar graphs

Fan, temperature and drive-life cards show a coloured bar built from the server's own thresholds: red beyond critical, amber in the warning band, green in between. Devices with no server-reported thresholds get no bar rather than an invented one.

Bar graphs need a Domoticz build that includes the plugin `Color` fix ([domoticz/domoticz#6968](https://github.com/domoticz/domoticz/pull/6968), merged 19 August 2026). On an older build Domoticz discards the bands and the cards simply show no bar; everything else works exactly the same.

**Formatted card text** needs Domoticz 2026.1 or newer, the version from which Domoticz renders Text and Alert device data as HTML. On an older build the markup may show as literal tags on the System Health and Power Redundancy cards instead of a bullet list, so turn the setting off there.

### Icons

Fans get the Fan icon, Uptime the Clock icon and drive-life devices the Hard Disk icon when they are first created. If you change an icon yourself afterwards, the plugin leaves your choice alone.

## Control

With **Allow Control** set to No, which is the default, the plugin is strictly read-only. No control device is created at all and every command is refused.

Setting it to Yes creates two devices:

- **Power Control**, a selector with five fixed entries: Power On, Graceful Shutdown, Graceful Restart, Force Off and Power Cycle. Entries the server does not currently offer, or that the hard-power setting withholds, are shown as `(unavailable)` rather than removed, so the position of every entry stays stable for scenes and timers you have already saved.
- **Identify LED**, which toggles the chassis identify light.

**Allow Force Off and Power Cycle** is a second, separate gate. Graceful Shutdown and Graceful Restart are requests handed to the host operating system, which can flush disks and close files first. Force Off and Power Cycle cut power electrically with no warning, the equivalent of holding the power button, and can lose data or corrupt a filesystem. Leave the hard actions off unless you specifically need them.

Two things worth knowing before you enable control:

- Once control is on, **any** Domoticz user, scene, timer or API client with access to this hardware can power off the server.
- A graceful action is fire-and-forget. The iDRAC accepts it and returns success even when no operating system or agent is there to act on it. The log therefore says the action was *accepted*, not that it succeeded. Watch the Power State device for what actually happened. The plugin deliberately does not escalate to a forced power-off when a graceful request goes unanswered.

## Security

- **The iDRAC password is stored in cleartext in the Domoticz database.** This is how Domoticz stores hardware credentials generally, not something this plugin chose. Treat your Domoticz database and its backups as secrets, and prefer a dedicated read-only iDRAC account over an administrator one.
- The password is never written to the Domoticz log at any debug level. Error messages are redacted before they are logged.
- **Verify TLS certificate is off by default.** An iDRAC ships with a self-signed certificate, so verification would fail on a stock machine. While it is off the connection is still encrypted but it is **not authenticated**, which means a host on your network could impersonate the iDRAC. If you have installed a certificate the Domoticz machine trusts, turn verification on.
- The plugin writes to your server in exactly two situations, both opt-in: the power actions and identify LED behind **Allow Control**, and one telemetry configuration write behind **Configure iDRAC telemetry**. With both off, every request is a `GET`.

## Troubleshooting

**No new hardware type appears in the list after installing.** The manifest did not parse. Check the Domoticz log at startup for the `plugin definitions loaded` count and confirm it went up by one. Confirm `plugin.py` is directly inside its own folder under `plugins`, and that the Python plugin system is enabled in your Domoticz build.

**The hardware is added but no devices appear.** Devices are created on the first successful poll, so wait one poll interval. If nothing arrives, look in the log for `iDRAC unreachable`. Check the address has no `https://` and no trailing path, and that the Domoticz machine can reach the iDRAC on port 443.

**Devices appear but show as timed out, and their values are stale.** The plugin holds the last known value rather than writing a zero when the iDRAC cannot be reached, and Domoticz marks the device stale itself. Look for `iDRAC unreachable, backing off` in the log. The wait doubles on each consecutive failure, up to 15 minutes, and resets as soon as one poll succeeds. An iDRAC reboot typically takes three to four minutes to recover.

**Everything is unreachable and the log mentions a certificate.** Turn Verify TLS certificate off, or install a certificate the Domoticz machine trusts.

**Authentication fails.** Confirm the account works by signing in to the iDRAC web interface with it. iDRAC locks an account after repeated failures, so a wrong password saved in Domoticz can lock you out through sheer retry volume.

**A power command is refused.** Check Allow Control is Yes. For Force Off or Power Cycle, also check Allow Force Off and Power Cycle. If the selector entry reads `(unavailable)`, the server is not currently offering that action, which commonly means the action does not apply in the current power state. The account also needs Server Control privilege in the iDRAC.

**A PSU reads close to 0 W.** That is normal on a server configured for hot standby, where one supply carries the load and the other idles. Wattage alone is not a fault signal. Watch System Health and Power Redundancy instead, which is what the plugin keys on.

**The System Health tile is red but every component reads OK.** Dell's health rollups track raised faults, not instantaneous component state, so a rollup can stay red while each part reports healthy. The tile shows the iDRAC's own fault text when there is one, which is the sentence that explains why. The fault clears when the underlying condition does, not when you clear the system event log.

**No bars appear on the fan or temperature cards.** Your Domoticz build predates the plugin `Color` fix described under [Bar graphs](#bar-graphs). The bands are computed and sent, and Domoticz discards them.

**Lowering Request Timeout made things worse.** A recovering iDRAC can take several seconds to answer its first request after a restart. The 30 s default is deliberate. A short timeout turns a normal recovery into a failed poll.

## Limitations

- The iDRAC cannot see UPS battery health, charge or runtime. It only knows whether input voltage is present at each PSU. For real UPS monitoring, add NUT or apcupsd alongside this plugin.
- The lifetime energy counter the iDRAC reports is not continuous across power-off periods, so the plugin integrates energy itself rather than trusting it. Energy accrued while Domoticz is not running is not recovered.
- Only the first power redundancy group is reported.
- Turning Allow Control back off leaves the two control devices in place. They are refused at the guard so no power action can get through, but they stay visible until you delete them.

## Contributing

Issues and pull requests are welcome. The plugin has a test suite that runs without any hardware, against recorded Redfish payloads:

```
pip install -r requirements-dev.txt
python3 -m pytest
```

Please keep new code covered and run `ruff check .` and `pyright` before opening a pull request.

## Support

Building tools that solve my own problems and sharing them in the hope they solve yours too. This one means you find out your server has a failing drive from your own dashboard, instead of the next time you happen to log into the iDRAC.

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/O0W221GBUG)

## License

MIT. See [LICENSE](LICENSE).
