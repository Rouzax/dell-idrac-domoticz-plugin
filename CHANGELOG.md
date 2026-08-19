# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

First release, not yet published.

### Added

- **Monitoring of a Dell PowerEdge server through the iDRAC's Redfish API.** Devices are created
  for the hardware the server actually reports rather than from a fixed list: chassis inlet and
  exhaust temperature, per-CPU temperature, maximum DIMM temperature, per-fan speed, system power
  with an integrated energy counter, per-PSU input wattage, CPU / memory / I/O / system
  utilization, uptime, boot status, chassis intrusion, per-drive and per-volume health, and
  per-NIC link state.
- **A single System Health device that names the reason.** When the iDRAC has raised a fault the
  device shows the iDRAC's own message, for example `Power supply redundancy is lost.`, and falls
  back to naming the unhappy subsystems when there is no fault text.
- **A Power Redundancy device.** The redundancy group's health is a separate signal from
  per-supply health, and can read Critical while every individual PSU reports OK.
- **Thresholds in device descriptions.** Temperature and fan devices carry the server's own
  warning and critical limits. A synthesized warning threshold is labelled `(estimated)` so it can
  never be mistaken for a reported value.
- **Opt-in power control and identify LED**, behind two independent gates: `Allow Control` for
  anything at all, and `Allow Force Off and Power Cycle` for the destructive actions on top.
  Selector levels are fixed slots, so a saved scene or timer keeps its meaning even when the set
  of actions the server offers changes.
- **Two-tier polling.** One request per poll for live sensors; health, storage, network and
  re-discovery on a configurable multiple of that.
- **Documentation site** built with mkdocs-material, with a troubleshooting page organised by
  symptom.

### Notable behaviour

- **A missing reading never becomes a zero.** A sensor that reports no value produces no device
  update at all, because Domoticz keeps history and a single written zero is permanent.
- **When the iDRAC is unreachable the plugin writes nothing.** Domoticz does its own staleness
  detection from each device's last update, so the last good value stays on screen and ages out
  naturally. Backoff starts at 20 s, doubles per consecutive failure, caps at 15 minutes, and
  resets on the first success.
- **`onStart` performs no network I/O**, because Domoticz starts hardware synchronously and an
  unreachable server would otherwise stall Domoticz itself.
- **Refused connections are retried, timeouts are not.** A refusal fails in milliseconds; a
  timeout has already spent its full budget and retrying it multiplies how long a poll blocks.
  A `POST` is never retried at all, since replaying a lost power action could power-cycle a server
  that already obeyed.
- **Renaming a device yourself stops the plugin from touching its name**, permanently.
- **Unit numbers persist and are never recycled**, so scenes and scripts keep pointing at the same
  component across hardware changes.

### Fixed before release

Found by testing against real hardware rather than by review:

- **A powered-off host reports `-128.0` for its maximum DIMM temperature**, a signed-byte "no
  reading" sentinel. It would have been written into a Domoticz temperature device and kept in
  that device's history permanently. Out-of-range Celsius readings are now rejected. Temperatures
  only; a negative wattage can be genuine and is left alone.
- **The chassis inlet sensor has a different id depending on the model** (`InletTemp` versus
  `SystemBoardInletTemp`), so a hardcoded lookup silently lost the reading on half a fleet. Sensor
  slots now carry known aliases.
- **NIC link status is null rather than `LinkDown` when the host is off**, which showed a warning
  tile reading `None`. Now grey and `Unknown`.
- **`BootProgress.LastState` is the literal string `"None"` when off**, which became device text.
  Now treated as an absence.
- **Dell's OEM rollups use `Error` where Redfish uses `Critical`.** The unmapped value fell through
  to grey, so a dead power supply could not name the culprit and, in the wrong combination, could
  have shown green. Found by physically unplugging a power supply.
- **An unreachable iDRAC blocked a single heartbeat for 120 seconds.** Path resolution swallowed a
  transport failure per collection, spending three full request timeouts before the poll added a
  fourth, long enough for Domoticz's own watchdog to report the plugin thread as dead five times.
  Resolution now probes the Redfish service root first and lets that failure propagate.
- **The exponential backoff never grew.** The countdown was drained to exactly zero before the next
  attempt, so the doubling branch was unreachable and the 15 minute cap was dead configuration.
  The wait length is now tracked separately from the countdown.
- **`DomoticzEx.Unit` has no `TimedOut` member.** Setting it would have raised against real
  Domoticz on a line reached every heartbeat, while every test passed because the test stub
  accepts any attribute. Found by reading the Domoticz core source. The feature was deleted rather
  than moved: Domoticz already does staleness detection itself.
- **A connect-phase timeout arrives wrapped in `URLError`, not `TimeoutError`.** It therefore
  slipped past the never-retry-timeouts rule that exists to prevent exactly that. Found by reading
  CPython's `urllib` source; no test could have caught it, because the test double bypasses
  urllib's own wrapping.
- **Selector levels were a positional index into the actions the server currently offered**, so a
  shrinking action set would compact everything after it down a slot and a saved automation
  meaning "graceful restart" could come to mean "force off".
- **The fixture sanitization test stored its list of forbidden strings in plaintext**, publishing
  the service tag, drive serial, MAC address, system UUID, hostname and password it existed to
  keep out of the repository. The list moved to an untracked local file and the values were purged
  from git history. Nothing had ever been pushed.
