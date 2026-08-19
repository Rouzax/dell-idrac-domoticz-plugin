# Changelog

All notable changes to this project are documented here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

First release, not yet published.

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
