# Changelog

All notable changes to this project are documented here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-08-20

### Added

- **Device name prefix and suffix settings.** Two servers monitored by two installs otherwise produce identical device names, which makes a dzVents lookup by name ambiguous. The text is used exactly as typed, so it carries its own separator, and it may contain `{servicetag}`, `{hostname}`, `{fqdn}`, `{idrac}` or `{model}` tokens that the plugin fills in from the server. See [Device names](https://rouzax.github.io/dell-idrac-domoticz-plugin/settings/#device-names).
- **A Ko-fi support link**, on the GitHub sponsor button, in the README and in the documentation footer. Documentation only: nothing about running the plugin changes, and it never prompts you.
- **GPU temperature without a telemetry licence.** GPU metrics are licence-gated, but a card's temperature is usually also present in the ordinary sensor list. When telemetry reports no cards, the plugin now creates a temperature device from any sensor the server tags with the Redfish physical context `GPU`. It is a fallback, not an addition: where telemetry does report cards, these sensors are ignored so no card gets two temperature devices. Found a card running at 74 °C on a PowerEdge R750 whose telemetry reported no GPU at all.
- **Power supply efficiency devices.** Where a supply reports both the AC it draws and the DC it delivers, a percentage device now shows the conversion efficiency. Measured across a fleet: 93.3% on a loaded R750, 75.0% on an idling R440. Nothing is written when the figure would be meaningless, so a supply on standby, a supply below 25 W of input, or a reading claiming more output than input produces no device rather than a misleading zero.
- **Duplicate device name warnings.** The plugin now checks, once per start and before creating anything, whether the names it plans to use are already owned by another hardware entry, and names the owner in the log. It only warns; it never renames anything automatically to dodge a collision.

### Changed

- **Drives attached by PCIe are now named `NVMe`.** Dell reports an NVMe drive with `MediaType: SSD`, identical to a SATA disk, and names it `PCIe SSD in Slot 23 in Bay 2`; only the bus protocol distinguishes the two. The rename is driven by the protocol the server reports, never by the name, so a drive that merely reads like a PCIe device is untouched. `PCIe SSD in Slot 23 in Bay 2` becomes `NVMe in Slot 23 in Bay 2`.
- **A RAID-state qualifier now survives the media-type shortening.** `NonRAID Solid State Disk 0:1:0` becomes `NonRAID SSD 0:1:0` rather than being left in full. The qualifier is kept because it says the disk is in pass-through mode rather than part of an array.

  Both drive changes rename existing devices on the first poll after the update, for the drives concerned, unless you renamed them by hand. Any dzVents script that looks those drives up by name needs updating.

- **Power Redundancy now distinguishes "switched off" from "not reported".** The Redfish redundancy list is empty both when a supply has been pulled and when the operator configured redundancy off, and the device said `Not reported` either way. It now reads `Not redundant (configured)` when Dell's own policy attribute says so. Verified across six servers, where the correlation was exact. Still grey rather than green: not redundant is an intended state, not a healthy one to advertise.

### Fixed

- **Wall-socket power could be silently missed on a server advertising many telemetry reports.** Reports were read in the order the server returned them, up to a fixed budget. A PowerEdge R440 lists 39 reports and puts `PowerMetrics`, the only one carrying `SystemInputPower`, at position 23, so it was never read: the Server Power device fell back to the mainboard sensor, which excludes the power supplies' own conversion loss, and nothing said so. Reports whose name suggests power are now read first. Which report is *used* is still decided by the metrics it actually contains, never by its name.

## [0.1.0] - 2026-08-19

First release.

### Added

- **Monitoring of a Dell PowerEdge server through the iDRAC's Redfish API.** Devices are created for the hardware the server actually reports rather than from a fixed list: chassis inlet and exhaust temperature, per-CPU temperature, maximum DIMM temperature, per-fan speed, system power with an integrated energy counter, per-PSU input wattage, CPU / memory / I/O / system utilization, uptime, boot status, chassis intrusion, per-drive and per-volume health, and per-NIC link state.
- **A single System Health device that names the reason.** When the iDRAC has raised a fault the device shows the iDRAC's own message, for example `Power supply redundancy is lost.`, and falls back to naming the unhappy subsystems when there is no fault text.
- **A Power Redundancy device.** The redundancy group's health is a separate signal from per-supply health, and can read Critical while every individual PSU reports OK.
- **Per-component power**, where the iDRAC licence allows it: CPU, memory, storage, fan, PCIe and FPGA draw as separate devices, read from Dell's telemetry service. Unlocked either by an iDRAC Datacenter licence or by an OpenManage Enterprise Advanced licence through OME Power Manager. The report is chosen by the metrics it contains rather than by its name, so both routes work without configuration. Where telemetry is available, the Server Power device switches to reporting actual wall draw instead of the mainboard sensor.
- **Per-GPU power and temperature**, where telemetry reports cards, one device of each per slot.
- **Configure iDRAC telemetry**, an opt-in setting, off by default, that switches Dell telemetry on so the per-component power devices can appear. The only setting that writes configuration to the server. It acts only when per-component power was already found unavailable, writes exactly two attributes, and is attempted at most once per plugin start.
- **Threshold bar graphs** on fan, temperature and drive-life cards, built from the server's own warning and critical limits. A synthesized threshold is never drawn, and a bar you edit by hand is never overwritten. Needs a Domoticz build that includes [domoticz/domoticz#6968](https://github.com/domoticz/domoticz/pull/6968).
- **Thresholds in device descriptions.** Temperature and fan devices carry the server's own warning and critical limits. A synthesized warning threshold is labelled `(estimated)` so it can never be mistaken for a reported value.
- **Drive names by media type and location**, for example `SSD 0:2:0` and `HDD 0:2:3`, with a BOSS boot card marked as such, so drives behind different controllers read consistently in one list.
- **Optional drive life percentage devices**, off by default, giving each drive that reports predicted media life a graphable percentage device with its own bar.
- **Opt-in power control and identify LED**, behind two independent gates: `Allow Control` for anything at all, and `Allow Force Off and Power Cycle` for the destructive actions on top. Selector levels are fixed slots, so a saved scene or timer keeps its meaning even when the set of actions the server offers changes.
- **Two-tier polling.** One request per poll for live sensors; health, storage, network and re-discovery on a configurable multiple of that.
- **Documentation site** built with mkdocs-material, with a troubleshooting page organised by symptom. Every setting on the Domoticz hardware page links to its section.

### Notable behaviour

- **A missing reading never becomes a zero.** A sensor that reports no value produces no device update at all, because Domoticz keeps history and a single written zero is permanent. Sentinel values that are not really readings, such as the `-128` a powered-off host reports for DIMM temperature, are rejected on the same principle.
- **When the iDRAC is unreachable the plugin writes nothing.** Domoticz does its own staleness detection from each device's last update, so the last good value stays on screen and ages out naturally. Backoff starts at 20 s, doubles per consecutive failure, caps at 15 minutes, and resets on the first success.
- **Nothing about the hardware is hardcoded.** Resource paths, sensor ids and telemetry reports are all discovered from the server, because the same physical probe has different ids on different PowerEdge models.
- **`onStart` performs no network I/O**, because Domoticz starts hardware synchronously and an unreachable server would otherwise stall Domoticz itself.
- **Refused connections are retried, timeouts are not.** A refusal fails in milliseconds; a timeout has already spent its full budget and retrying it multiplies how long a poll blocks. Only a `GET` is retried at all, since replaying a lost power action could power-cycle a server that already obeyed.
- **One Domoticz Device per family**, so a machine with many drives or GPUs cannot exhaust the 255-unit limit.
- **Renaming a device, changing its icon or editing its bar stops the plugin from touching that property**, permanently.
- **Unit numbers persist and are never recycled**, so scenes and scripts keep pointing at the same component across hardware changes.

### Known limitations

- GPU support is built from real captures but has not yet been confirmed on a live GPU server.
- Only the first power redundancy group is reported.
- Turning `Allow Control` back off leaves the two control devices in place, inert but visible.
- The iDRAC cannot see UPS battery health, charge or runtime. Add NUT or apcupsd alongside for that.

[0.2.0]: https://github.com/Rouzax/dell-idrac-domoticz-plugin/releases/tag/v0.2.0
[0.1.0]: https://github.com/Rouzax/dell-idrac-domoticz-plugin/releases/tag/v0.1.0
