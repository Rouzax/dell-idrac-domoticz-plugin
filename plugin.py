# pyright: reportMissingImports=false, reportUndefinedVariable=false, reportAttributeAccessIssue=false
"""\
<plugin key="dellidrac" name="Dell iDRAC Monitor" author="Rouzax" version="0.3.0" externallink="https://github.com/Rouzax/dell-idrac-domoticz-plugin">
    <description>
        <!-- Inlined as a data URI so no asset has to be web-served from the plugin folder.
             A PNG rather than an inline SVG deliberately: an inline SVG style block is DOCUMENT
             scoped, so the generator's stock .cls-N names and ids like "mask" would land in the
             Domoticz page. An img tag cannot affect the page at all. Rendered at 128px and shown
             at 64px so it stays sharp on a HiDPI display. Source art: iDRAC Icon - Alternate. -->
        <div style="display:flex;align-items:center;gap:14px;margin:0 0 8px 0">
            <img src="data:image/png;base64,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" width="64" height="60" alt="iDRAC"/>
            <h2 style="margin:0">Dell PowerEdge monitor via iDRAC Redfish</h2>
        </div>
        <p>Reads temperatures, fans, power, utilization, storage and health from a Dell iDRAC and creates devices for the hardware your server actually has.</p>
        <p><b>The iDRAC password is stored in cleartext in the Domoticz database. Treat database backups as secrets.</b></p>
        <p><a href="https://rouzax.github.io/dell-idrac-domoticz-plugin/" target="_blank">Documentation</a>: every setting, every device, and troubleshooting by symptom.</p>
    </description>
    <params>
        <param field="Address" label="iDRAC Address" width="200px" required="true">
            <description>Hostname or IP of the iDRAC, without a scheme (for example 192.168.1.10). (<a href="https://rouzax.github.io/dell-idrac-domoticz-plugin/install/#step-4-add-the-hardware" target="_blank">setting it up</a>).</description>
        </param>
        <param field="Username" label="Username" width="150px" required="true" default="root">
            <description>A read-only iDRAC account is enough for monitoring; only power control needs Server Control privilege. Prefer a dedicated account over root. (<a href="https://rouzax.github.io/dell-idrac-domoticz-plugin/security/" target="_blank">why</a>).</description>
        </param>
        <param field="Password" label="Password" width="200px" required="true" password="true">
            <description>iDRAC password. Stored in cleartext in the Domoticz database and never written to the log. (<a href="https://rouzax.github.io/dell-idrac-domoticz-plugin/security/#the-idrac-password-is-stored-in-cleartext" target="_blank">what that means</a>).</description>
        </param>
        <param field="AllowControl" label="Allow Control" width="150px">
            <description>Off by default; the plugin stays strictly read-only until you turn it on. Once on, any Domoticz user, scene, timer or API client can power off the server. (<a href="https://rouzax.github.io/dell-idrac-domoticz-plugin/control/" target="_blank">read this first</a>).</description>
            <options>
                <option label="No" value="false" default="true"/>
                <option label="Yes" value="true"/>
            </options>
        </param>
        <group label="Polling">
            <param field="PollInterval" type="number" label="Poll Interval (s)" min="20" max="600" step="10" default="30" width="100px">
                <description>How often to read live sensors, in seconds. One request per poll. (<a href="https://rouzax.github.io/dell-idrac-domoticz-plugin/settings/#polling" target="_blank">how the two tiers work</a>).</description>
            </param>
            <param field="SlowEvery" type="number" label="Slow Poll (every N polls)" min="1" max="60" step="1" default="10" width="100px">
                <description>How often to refresh health, storage, NICs and re-run discovery, as a multiple of the poll interval. At the defaults this is every 5 minutes. (<a href="https://rouzax.github.io/dell-idrac-domoticz-plugin/settings/#polling" target="_blank">how the two tiers work</a>).</description>
            </param>
        </group>
        <group label="Devices">
            <param field="EnableDrives" type="boolean" label="Physical drives" default="true"/>
            <param field="EnableVolumes" type="boolean" label="RAID volumes" default="true"/>
            <param field="EnablePSUs" type="boolean" label="Power supplies" default="true">
            <description>One wattage device per PSU. Also the source of the Power Redundancy device, which stops updating if you turn this off. (<a href="https://rouzax.github.io/dell-idrac-domoticz-plugin/devices/#power-redundancy" target="_blank">details</a>).</description>
            </param>
            <param field="EnableNICs" type="boolean" label="Network interfaces" default="true"/>
            <param field="DriveLifeFloor" type="number" label="Drive life warning (%)" min="0" max="100" step="1" default="10" width="100px">
                <description>Warn when a drive reports less than this much predicted media life remaining. Also sets where the drive life bar turns red. (<a href="https://rouzax.github.io/dell-idrac-domoticz-plugin/devices/#drive-life-devices" target="_blank">details</a>).</description>
            </param>
            <param field="EnableDriveLife" type="boolean" label="Drive life % devices" default="false">
                <description>Adds a second device per drive that reports predicted media life, showing it as a percentage with a bar. Off by default: the life figure is already on the drive's own tile, so this duplicates it for the sake of the graph. Only drives that report life get one, which in practice means SSDs. (<a href="https://rouzax.github.io/dell-idrac-domoticz-plugin/settings/#drive-life-devices" target="_blank">details</a>).</description>
            </param>
            <param field="RichCardText" type="boolean" label="Formatted card text" default="true">
                <description>Renders the System Health and Power Redundancy cards as a bullet list with a link to the iDRAC, instead of a single line of text. Turn it off to go back to plain single-line text, which is what any dzVents script written before this setting existed will be comparing against. (<a href="https://rouzax.github.io/dell-idrac-domoticz-plugin/settings/#formatted-card-text" target="_blank">details</a>).</description>
            </param>
            <param field="EnergyCounters" type="boolean" label="Energy counters" default="true">
                <description>Reports per-component power as kWh counters instead of plain watt gauges, so each one appears in Domoticz's energy report with a total and a cost. Applies to the CPU, memory, storage, fan, PCIe and FPGA power devices, to each power supply and to each GPU. Existing devices are converted in place and keep their name and history. Turn it off to go back to watt gauges (<a href="https://rouzax.github.io/dell-idrac-domoticz-plugin/settings/#energy-counters" target="_blank">details</a>).</description>
            </param>
            <param field="FanBarMax" type="number" label="Fan bar maximum (RPM)" min="0" max="60000" step="500" default="6000" width="100px">
                <description>Top of the scale on fan bar graphs; 0 turns them off. Redfish reports no maximum fan speed, so it cannot be detected. (<a href="https://rouzax.github.io/dell-idrac-domoticz-plugin/settings/#why-the-fan-bar-maximum-is-a-setting" target="_blank">choosing a value</a>).</description>
            </param>
        </group>
        <group label="Device names">
            <param field="NamePrefix" label="Name prefix" width="200px">
                <description>Put in front of every device name, exactly as typed, so include your own separator and any trailing space. Leave empty to keep the current names. Use it when you monitor more than one server, because otherwise both installs create a device called System Health and a dzVents lookup by name cannot tell them apart. May contain {servicetag}, {hostname}, {fqdn}, {model} or {idrac}, which are filled in from the server itself. (<a href="https://rouzax.github.io/dell-idrac-domoticz-plugin/settings/#device-names" target="_blank">examples, and what changing it renames</a>).</description>
            </param>
            <param field="NameSuffix" label="Name suffix" width="200px">
                <description>The same, appended instead. Example: _TESTSRV. (<a href="https://rouzax.github.io/dell-idrac-domoticz-plugin/settings/#device-names" target="_blank">examples</a>).</description>
            </param>
        </group>
        <group label="Control">
            <param field="AllowHardPowerActions" type="boolean" label="Allow Force Off and Power Cycle" default="false">
                <description>Adds Force Off and Power Cycle, which cut power with no warning and can lose data. Graceful actions are always offered. No effect while Allow Control is No. (<a href="https://rouzax.github.io/dell-idrac-domoticz-plugin/control/#graceful-versus-hard" target="_blank">details</a>).</description>
            </param>
        </group>
        <group label="Advanced">
            <param field="VerifyTLS" type="boolean" label="Verify TLS certificate" default="false">
                <description>Off because iDRAC ships a self-signed certificate. While off the connection is encrypted but NOT authenticated. (<a href="https://rouzax.github.io/dell-idrac-domoticz-plugin/security/" target="_blank">what that means</a>).</description>
            </param>
            <param field="SetupTelemetry" type="boolean" label="Configure iDRAC telemetry" default="false">
                <description>The ONLY setting that writes configuration to your server. Enables Dell telemetry for per-component power, and only if that is found unavailable. Needs a Datacenter or OME Advanced licence. Leave off if OpenManage manages this server. (<a href="https://rouzax.github.io/dell-idrac-domoticz-plugin/settings/#configure-idrac-telemetry" target="_blank">details, and how to do it by hand</a>).</description>
            </param>
            <param field="RequestTimeout" type="number" label="Request Timeout (s)" min="5" max="120" step="5" default="30" width="100px">
                <description>Per-request timeout. Do not lower it much: a recovering iDRAC can take several seconds to answer its first request, so a short timeout turns a normal recovery into a failed poll. (<a href="https://rouzax.github.io/dell-idrac-domoticz-plugin/settings/#advanced" target="_blank">why 30 is the default</a>).</description>
            </param>
            <param field="DebugLevel" label="Debug Level" width="150px">
                <description>Logging verbosity. The iDRAC password is never written to the log at any level. (<a href="https://rouzax.github.io/dell-idrac-domoticz-plugin/faq/" target="_blank">troubleshooting by symptom</a>).</description>
                <options>
                    <option label="None" value="0" default="true"/>
                    <option label="Basic" value="1"/>
                    <option label="Verbose" value="2"/>
                </options>
            </param>
        </group>
    </params>
</plugin>
"""

import dataclasses
import time

import DomoticzEx as Domoticz

import config
import control
import discovery
import domoticz_api
import energy
import model
import planner
import redfish_client

_BACKOFF_INITIAL = 20.0
_BACKOFF_CAP = 900.0
_HEARTBEAT_SECONDS = 10


class _PluginState:
    def __init__(self):
        self.cfg = None
        self.client = None
        # family -> DeviceID. One Device per family, each with its own 1-255 unit space.
        self.dev_ids = {}
        self.beat = 0
        self.slow_tick = 0
        # Telemetry is licence-gated and absent on most iDRACs. None means "not tried yet";
        # False latches after the first refusal so the plugin stops paying for a request that
        # will never succeed. Reset by onStart, so a licence upgrade is picked up on restart.
        self.telemetry = None
        # Which report paths actually carry power metrics on THIS machine. Discovered once,
        # because the ids differ by licence and management, then polled directly.
        self.metric_paths = ()
        # One configuration attempt per plugin start, never more, whether or not it worked.
        self.telemetry_setup_tried = False
        # Per-GPU watts and temperature, when telemetry reports them. Empty on most machines.
        self.gpus = {}
        # Two values, deliberately. `backoff` is the countdown the heartbeat drains to zero;
        # `backoff_level` is how long the current wait is and is what doubles. Reading growth
        # back off the countdown cannot work: it is always exactly 0.0 by the time the next poll
        # runs, so the doubling never fires and the cap is dead configuration.
        self.backoff = 0.0
        self.backoff_level = 0.0
        self.slow_parts = {}
        self.alloc = {}
        self.resolved = False
        self.orphaned_reported = ()
        # The iDRAC's own DNS name, for the {idrac} token. It lives on a different resource from
        # everything else the poll reads, so it is fetched once and only when an affix asks for
        # it. None means "not looked up yet"; "" means looked up and unavailable.
        self.idrac_name = None
        self.affix_warned = ()
        self.affix_logged = None
        self.duplicates_reported = ()
        self.collisions_checked = False
        # Wall-clock reference for the energy counters, stamped only after a SUCCESSFUL poll.
        # None means "no measured interval yet", which integrates nothing rather than guessing.
        self.last_poll_monotonic = None
        # (counter key, reason) pairs already warned about, so a machine reporting a permanently
        # bad figure costs one log line per plugin start per reason instead of one per poll, and
        # one reason firing first does not permanently silence a different reason on the same
        # device.
        self.counter_warned = set()
        self.reset_slow()

    def reset_slow(self):
        self.slow_parts = {
            "system": model.SystemInfo(None, None, None, None, 0, {}),
            "chassis": model.ChassisInfo(None, False),
            "dell_attrs": model.DellAttrs(None, None, None),
            "threshold_map": {},
            "allowable": [],
            "psus": [],
            "drives": [],
            "volumes": [],
            "nics": [],
        }
        self.allowable = []


_state = _PluginState()


def _devices():
    return globals().get("Devices")


def onStart():
    global _state
    _state = _PluginState()
    _state.cfg = config.parse_config(Parameters)
    if _state.cfg.debug_level >= 2:
        Domoticz.Debugging(1)
    _state.dev_ids = {
        family: domoticz_api.device_id(Parameters["HardwareID"], family)
        for family in planner.DEVICE_FAMILIES
    }
    _state.client = redfish_client.RedfishClient(
        host=_state.cfg.address,
        username=_state.cfg.username,
        password=_state.cfg.password,
        verify_tls=_state.cfg.verify_tls,
        timeout=_state.cfg.request_timeout,
    )
    # NO network I/O here. Domoticz calls onStart synchronously while starting the hardware, so
    # a request to an unreachable iDRAC would stall Domoticz itself for the full timeout plus
    # retries. Path resolution happens lazily on the first heartbeat instead.
    # config is pure and cannot log, so it reports what it silently changed and we surface it.
    # A setting quietly rewritten behind the user's back is worse than a wrong one they can see.
    for warning in _state.cfg.warnings:
        # Status, not Error. Nothing failed and nothing needs a human to intervene; the operator
        # simply needs to see that a value they typed is not the value being used.
        Domoticz.Status(f"setting adjusted: {warning}")
    saved = domoticz_api.load_state()
    _state.alloc = dict(saved.unit_alloc)
    Domoticz.Heartbeat(_HEARTBEAT_SECONDS)
    Domoticz.Status(f"Dell iDRAC Monitor started for {_state.cfg.address}")


def onStop():
    Domoticz.Status("Dell iDRAC Monitor stopped")


def poll_fast(client) -> dict:
    return model.parse_sensors(client.get_expanded(client.sensors))


# Metric ids worth fetching a report for. A report carrying none of these is not polled again.
_WANTED_METRICS = frozenset(
    {
        "SystemInputPower",
        "TotalCPUPower",
        "TotalMemoryPower",
        "TotalStoragePower",
        "TotalFanPower",
        "TotalPciePower",
        "TotalFPGAPower",
    }
)
# A machine managed by OpenManage can expose a dozen reports, several of them large (SMART data,
# NIC statistics). Discovery reads them once; this caps the damage if a server offers many more.
# The budget cannot simply be lifted: a real R440 advertises 39 reports, and reading all of them
# in one heartbeat risks the 60 s watchdog that Domoticz applies to a plugin thread.
_MAX_METRIC_REPORTS = 16

# ORDERING ONLY, never selection. Reports whose id hints at power are read first so the budget
# above cannot hide the one that matters; what a report actually contains still decides whether
# it is used. Measured on an R440: "PowerMetrics" is the only report carrying SystemInputPower
# and the server lists it 23rd, so in server order it was never read, and the plugin silently
# fell back to the board sensor, which misses the power supplies' own conversion loss.
_POWER_NAME_HINTS = ("power", "pmp", "psu")


def _power_first(path: str) -> tuple:
    name = path.rsplit("/", 1)[-1].lower()
    return (0 if any(hint in name for hint in _POWER_NAME_HINTS) else 1, name)


def discover_metric_paths(client, state) -> tuple:
    """Find which reports on THIS machine carry the power metrics, by reading them.

    Report ids are not fixed. A Datacenter iDRAC serves Dell's built-in "PowerMetrics"; a machine
    managed by OpenManage Enterprise under the Advanced licence instead carries the Power Manager
    Plugin's own reports, "OME-PMP-Power-A" and friends, and answers the built-in names with a
    licence error. Both were seen on real hardware, so the report is selected by the metric ids it
    actually contains rather than by its name.
    """
    every = sorted(client.metric_report_ids(), key=_power_first)
    considered = every[:_MAX_METRIC_REPORTS]
    paths = []
    seen = set()
    for path in considered:
        try:
            found = model.parse_metric_report(client.get(path))
        except redfish_client.RedfishError as exc:
            # One unreadable report, licence-gated or otherwise, must not hide the others.
            Domoticz.Debug(f"metric report {path} unreadable: {exc}")
            continue
        carried = _WANTED_METRICS & {sample.metric_id for sample in found}
        if carried:
            paths.append(path)
            seen |= carried
    # Deliberately NOT stopping as soon as every wanted metric has been seen. metric_value()
    # reduces across the samples of every selected report at once, because a metric id repeats
    # per aggregation and per device, so cutting the search short would change which sample wins
    # rather than merely saving a request.
    skipped = len(every) - len(considered)
    if skipped and seen < _WANTED_METRICS:
        # Never truncate silently: say what was not read and what is missing because of it.
        Domoticz.Debug(
            f"{skipped} further metric report(s) not read (budget {_MAX_METRIC_REPORTS}); "
            f"still missing {', '.join(sorted(_WANTED_METRICS - seen))}"
        )
    state.metric_paths = tuple(paths)
    return state.metric_paths


# The minimum needed for the per-component power report: the master switch and that one report.
# Nothing else is touched, so an OpenManage-managed server keeps whatever else it has configured.
_TELEMETRY_ATTRIBUTES = {
    "Telemetry.1.EnableTelemetry": "Enabled",
    "TelemetryPowerMetrics.1.EnableTelemetry": "Enabled",
}


def setup_telemetry(client, state) -> None:
    """Enable Dell telemetry, but ONLY when it is already known to be unavailable.

    This is the one place the plugin writes configuration to the server, and it is off by
    default. Writing only when the read failed matters: it keeps the plugin away from a machine
    where OpenManage, or anything else, already has telemetry working and owns that config.
    Attempted once per plugin start, so a server that cannot be fixed this way, because the
    licence is missing, is not written to on every poll.
    """
    if state.telemetry_setup_tried:
        return
    state.telemetry_setup_tried = True
    Domoticz.Status(
        "configuring iDRAC telemetry, because per-component power was unavailable and "
        "Configure iDRAC telemetry is on: "
        + ", ".join(f"{k}={v}" for k, v in sorted(_TELEMETRY_ATTRIBUTES.items()))
    )
    try:
        client.patch(client.idrac_attributes, {"Attributes": dict(_TELEMETRY_ATTRIBUTES)})
    except redfish_client.RedfishError as exc:
        Domoticz.Error(
            "could not configure iDRAC telemetry, which usually means the licence does not "
            f"allow it: {exc}"
        )
        return
    Domoticz.Status("iDRAC telemetry configured; per-component power should appear shortly")
    # Let the next poll rediscover rather than latching the failure that prompted this.
    state.telemetry = None
    state.metric_paths = ()


def poll_metrics(client, state) -> dict:
    """Per-subsystem power. Optional, and absent on most machines.

    Fetched in the fast tier because it also supplies the wattage the energy counter integrates,
    which would otherwise be up to a full slow cycle stale. Guarded and latched: once the plugin
    knows this machine cannot serve it, it stops asking, so an unlicensed iDRAC pays for one
    discovery per plugin start rather than a wasted request on every poll.
    """
    if state.telemetry is False:
        return {}
    try:
        if state.telemetry is None:
            discover_metric_paths(client, state)
        samples = []
        for path in state.metric_paths:
            samples.extend(model.parse_metric_report(client.get(path)))
        # Reduce to one value per metric only at the end. Selection has to see every sample at
        # once: the same metric id repeats per aggregation and per device, so choosing early
        # would pick a Minimum, or one power supply's temperature, and call it the answer.
        metrics = {}
        for metric_id in _WANTED_METRICS:
            value = model.metric_value(samples, metric_id)
            if value is not None:
                metrics[metric_id] = value
        state.gpus = planner.gpu_readings(samples)
    except redfish_client.RedfishError as exc:
        if state.telemetry is None:
            Domoticz.Status(
                "per-component power unavailable, so those devices will not be created "
                f"(needs Dell telemetry, which is licence-gated): {exc}"
            )
        state.telemetry = False
        return {}
    if not metrics:
        if state.telemetry is None:
            Domoticz.Status(
                "Dell telemetry is reachable but no report carries power metrics, so the "
                "per-component power devices will not be created"
            )
        state.telemetry = False
        return {}
    if state.telemetry is None:
        names = ", ".join(p.rsplit("/", 1)[-1] for p in state.metric_paths)
        Domoticz.Status(f"Dell telemetry available: {len(metrics)} metrics from {names}")
    state.telemetry = True
    return metrics


def idrac_dns_name(client, state) -> str:
    """The iDRAC's own DNS name, read once per plugin start.

    It sits on the iDRAC attribute resource rather than on the system, so reading it costs an
    extra request. That is only worth paying when a name affix actually uses {idrac}, and the
    answer does not change while the plugin runs, so it is cached either way.
    """
    if state.idrac_name is not None:
        return state.idrac_name
    try:
        attributes = client.get(client.idrac_attributes).get("Attributes") or {}
    except redfish_client.RedfishError as exc:
        # Not fatal: the token simply does not resolve and expand_affix reports it.
        Domoticz.Debug(f"iDRAC DNS name unavailable: {exc}")
        state.idrac_name = ""
        return state.idrac_name
    state.idrac_name = str(attributes.get("NIC.1.DNSRacName") or "")
    return state.idrac_name


def resolve_affixes(cfg, state, system) -> tuple:
    """The user's prefix and suffix with their {tokens} expanded for this machine."""
    wants_idrac = "{idrac}" in cfg.name_prefix or "{idrac}" in cfg.name_suffix
    tokens = planner.name_tokens(
        system, idrac_dns_name(state.client, state) if wants_idrac else None
    )
    prefix, missing_prefix = planner.expand_affix(cfg.name_prefix, tokens)
    suffix, missing_suffix = planner.expand_affix(cfg.name_suffix, tokens)
    unresolved = tuple(sorted(set(missing_prefix + missing_suffix)))
    if unresolved != state.affix_warned:
        # Report only on CHANGE: this runs every poll and the condition persists until the
        # hardware or the setting changes, so logging each time would bury the message.
        if unresolved:
            Domoticz.Error(
                "device name token(s) this server does not report, so they expand to nothing: "
                + ", ".join(f"{{{name}}}" for name in unresolved)
            )
        state.affix_warned = unresolved
    if (prefix, suffix) != state.affix_logged:
        # Show ONE finished name. A trailing space is invisible in the settings form and a token
        # is not what the user typed, so this is the only place they can confirm the result is
        # what they meant. Logged on change only, never every poll.
        if prefix or suffix:
            Domoticz.Status(f'device names look like "{prefix}System Health{suffix}"')
        state.affix_logged = (prefix, suffix)
    return prefix, suffix


def poll_slow(client, cfg) -> dict:
    system_payload = client.get(client.system)
    reset_action = (system_payload.get("Actions") or {}).get("#ComputerSystem.Reset") or {}
    power_payload = client.get(client.power) if cfg.enable_psus else {}
    parts = {
        "system": model.parse_system(system_payload),
        "chassis": model.parse_chassis(client.get(client.chassis)),
        "redundancy": model.parse_redundancy(power_payload),
        "faults": [],
        "dell_attrs": model.parse_dell_attributes(client.get(client.dell_attributes)),
        "threshold_map": model.parse_thermal_thresholds(client.get(client.thermal)),
        "allowable": reset_action.get("ResetType@Redfish.AllowableValues") or [],
        "psus": [],
        "drives": [],
        "volumes": [],
        "nics": [],
    }
    # Each sub-call is independently guarded: one failing subsystem must not cost
    # us the rest of the slow tier.
    if cfg.enable_psus:
        parts["psus"] = model.parse_power(power_payload)
    # The fault list states WHY health is red. Dell rollups latch, so without it a red System
    # Health device can have no unhealthy component behind it and no explanation on screen.
    try:
        parts["faults"] = model.parse_faults(client.get(client.faults))
    except redfish_client.RedfishError as exc:
        # Older iDRACs may not expose FaultList. Degrade to subsystem names, do not fail.
        Domoticz.Debug(f"fault list unavailable: {exc}")
    if cfg.enable_nics:
        try:
            parts["nics"] = model.parse_nics(client.get_expanded(client.ethernet))
        except redfish_client.RedfishError as exc:
            Domoticz.Error(f"nic poll failed: {exc}")
    if cfg.enable_drives or cfg.enable_volumes:
        try:
            collection = client.get(client.storage_collection)
            for member in collection.get("Members", []):
                ctrl = member["@odata.id"]
                if cfg.enable_drives:
                    parts["drives"].extend(model.parse_drives(client.get_expanded(ctrl)))
                if cfg.enable_volumes:
                    parts["volumes"].extend(
                        model.parse_volumes(client.get_expanded(ctrl + "/Volumes"))
                    )
        except redfish_client.RedfishError as exc:
            Domoticz.Error(f"storage poll failed: {exc}")
    return parts


# Enough names to make the problem obvious without writing a wall of text to the log.
_MAX_LISTED_COLLISIONS = 8


def report_name_collisions(updates) -> None:
    """Warn once when another hardware entry already owns names this install plans to use.

    Checked BEFORE the devices are created, so the warning arrives on the first poll rather than
    after a full set of duplicates already exists.
    """
    if _state.collisions_checked:
        return
    _state.collisions_checked = True
    found = domoticz_api.names_used_by_other_hardware(
        str(Parameters.get("Database", "")),
        Parameters.get("HardwareID"),
        [update.name for update in updates],
    )
    if not found:
        return
    names = [name for name, _ in found]
    owners = sorted({owner for _, owner in found})
    listed = ", ".join(names[:_MAX_LISTED_COLLISIONS])
    if len(names) > _MAX_LISTED_COLLISIONS:
        listed += f", and {len(names) - _MAX_LISTED_COLLISIONS} more"
    Domoticz.Error(
        f"{len(names)} planned device name(s) already exist under hardware "
        f"{', '.join(repr(owner) for owner in owners)}: {listed}. "
        "A dzVents lookup by name cannot tell them apart; set a Name Prefix or Name Suffix."
    )


def report_duplicate_names(updates) -> None:
    """Warn when this plan would give two devices the same name.

    Domoticz permits duplicate names and a dzVents lookup by name then silently picks one of
    them, so a collision is invisible until a script acts on the wrong device.
    """
    duplicates = planner.duplicate_names(updates)
    if duplicates == _state.duplicates_reported:
        return
    # Report only on CHANGE, the same rule as the orphaned-unit message below.
    if duplicates:
        Domoticz.Error(
            f"{len(duplicates)} device name(s) used more than once, which makes a dzVents "
            f"lookup by name ambiguous: {', '.join(duplicates)}"
        )
    elif _state.duplicates_reported:
        Domoticz.Status("device names are unique again")
    _state.duplicates_reported = duplicates


def _warn_counter_once(key: str, reason: str, message: str) -> None:
    """One line per counter per plugin start, PER REASON. Keying on the device alone would let
    the first condition to fire (say, an unreadable previous value) permanently silence the
    other two for that device; a component that later goes implausible would then log nothing
    at all. Keying on (key, reason) keeps each condition's own one-line-per-start latch."""
    latch = (key, reason)
    if latch in _state.counter_warned:
        return
    _state.counter_warned.add(latch)
    Domoticz.Error(message)


def attach_counters(devices, updates, elapsed_s, system_watts, peak_w):
    """Fill in the energy half of every counter device's sValue.

    The previous total is read back off the device itself, so no counter state is persisted and
    a device the user deleted simply starts again from zero. Returns the updates to apply: a
    counter whose previous value cannot be read is DROPPED, because writing anything at all
    would reset a counter whose entire contract is that it only climbs.
    """
    out = []
    for up in updates:
        if not up.counter:
            out.append(up)
            continue
        # Keyed on the resolved DeviceID rather than the bare family name, so the key matches
        # what read_prev_counter_wh actually reads: two families never share a DeviceID, but the
        # family alone is not what identifies a device on the wire.
        dev_id = _state.dev_ids[up.device]
        key = f"{dev_id}:{up.unit}"
        watts = float(up.svalue)
        prev_wh = domoticz_api.read_prev_counter_wh(devices, dev_id, up.unit)
        if prev_wh is None:
            _warn_counter_once(
                key, "unreadable", f"{up.name}: energy counter unreadable, not written"
            )
            continue
        if energy.implausible(watts, system_watts):
            _warn_counter_once(
                key,
                "implausible",
                f"{up.name}: {watts} W exceeds the {system_watts} W the machine is drawing, "
                "counter held",
            )
            out.append(dataclasses.replace(up, svalue=f"{up.svalue};{prev_wh}"))
            continue
        counter_wh, warning = energy.advance(prev_wh, watts, elapsed_s, peak_w * 2)
        if warning:
            _warn_counter_once(key, "advance", f"{up.name}: {warning}")
        out.append(dataclasses.replace(up, svalue=f"{up.svalue};{counter_wh}"))
    return out


def onHeartbeat():
    cfg = _state.cfg
    if cfg is None:
        return
    _state.beat += 1
    if _state.backoff > 0:
        _state.backoff -= _HEARTBEAT_SECONDS
        return
    if _state.beat * _HEARTBEAT_SECONDS < cfg.poll_interval:
        return
    _state.beat = 0

    devices = _devices()
    try:
        if not _state.resolved:
            # Lazy, and inside the same guard as the poll so an unreachable iDRAC backs off
            # rather than stalling. resolve() raises only when the service root is unreachable;
            # a readable service with an odd collection falls back to the conventional id and
            # returns False. Latch only when every id was genuinely discovered, otherwise a
            # first heartbeat during an outage would pin the wrong paths for the whole process.
            _state.resolved = _state.client.resolve()
        sensors = poll_fast(_state.client)
        metrics = poll_metrics(_state.client, _state)
        if not metrics and cfg.setup_telemetry and not _state.telemetry_setup_tried:
            setup_telemetry(_state.client, _state)
        _state.slow_tick += 1
        if _state.slow_tick >= cfg.slow_every or not _state.slow_parts["threshold_map"]:
            # Reset only AFTER the call returns. Resetting first means a transient slow-tier
            # failure pushes the next refresh out by a whole extra cycle instead of retrying.
            _state.slow_parts = poll_slow(_state.client, cfg)
            _state.slow_tick = 0
    except redfish_client.RedfishError as exc:
        _state.backoff_level = min(
            _BACKOFF_CAP,
            _state.backoff_level * 2 if _state.backoff_level else _BACKOFF_INITIAL,
        )
        _state.backoff = _state.backoff_level
        Domoticz.Error(f"iDRAC unreachable, backing off {_state.backoff:.0f}s: {exc}")
        # Write nothing. Domoticz flags the devices itself once LastUpdate goes stale, and a
        # zero written here would corrupt every device's recorded history permanently.
        return

    _state.backoff = 0.0
    _state.backoff_level = 0.0
    parts = dict(_state.slow_parts)
    # Not plan() arguments: consumed by the control plane in Task 13.
    _state.allowable = parts.pop("allowable", [])
    inventory = discovery.discover(
        sensors=sensors,
        psus=parts["psus"],
        drives=parts["drives"],
        volumes=parts["volumes"],
        nics=parts["nics"],
    )
    # GPUs come from telemetry rather than from a Redfish collection, so discover() cannot find
    # them. They still need units allocated from the same persisted map as everything else.
    if _state.gpus:
        inventory = discovery.Inventory(
            **{**inventory.__dict__, "gpus": tuple(sorted(_state.gpus))}
        )
    saved = domoticz_api.load_state()
    _state.alloc = planner.assign_units(inventory, _state.alloc or saved.unit_alloc)
    # A unit is never freed once taken, so a block can exhaust through component churn. The
    # affected devices are skipped rather than crashing the poll, but the gap must not be silent.
    orphaned = planner.unassigned(inventory, _state.alloc)
    if orphaned != _state.orphaned_reported:
        # Report only on CHANGE. An exhausted block persists until the hardware changes, so
        # logging it every poll would bury the message it is trying to deliver.
        if orphaned:
            Domoticz.Error(
                f"no free unit for {len(orphaned)} item(s), not shown: {', '.join(orphaned)}"
            )
        elif _state.orphaned_reported:
            Domoticz.Status("all discovered items now have a unit")
        _state.orphaned_reported = orphaned

    # The figure the counters integrate is the same one Server Power displays: wall draw when
    # telemetry supplies it, otherwise the board sensor. Anything else would make a counter
    # disagree with its own watts, and it is what the chassis bound compares a component against.
    board = sensors.get("SystemBoardPwrConsumption")
    system_watts = metrics.get("SystemInputPower")
    if system_watts is None:
        system_watts = board.reading if board is not None else None
    peak_w = parts["dell_attrs"].peak_watts or 1000.0
    # Measured, not nominal. A poll that runs late would otherwise be counted as though it ran on
    # time. Capped at two intervals because an unreachable iDRAC does not stamp the clock, so a
    # long outage would otherwise be integrated in full at whatever the last reading happened to
    # be. Under-counting a period with no measurements is the honest error.
    now = time.monotonic()
    elapsed_s = (
        0.0
        if _state.last_poll_monotonic is None
        else min(now - _state.last_poll_monotonic, cfg.poll_interval * 2)
    )
    _state.last_poll_monotonic = now

    updates = planner.plan(
        sensors=sensors,
        inventory=inventory,
        alloc=_state.alloc,
        cfg=cfg,
        metrics=metrics,
        gpus=_state.gpus,
        **parts,
    )
    updates = attach_counters(devices, updates, elapsed_s, system_watts, peak_w)
    updates.extend(control.control_updates(cfg, _state.allowable, parts["chassis"].identify_on))
    # ONE choke point for naming, after the control devices are appended so nothing is missed.
    prefix, suffix = resolve_affixes(cfg, _state, parts["system"])
    updates = planner.decorate_names(updates, prefix, suffix)
    report_duplicate_names(updates)
    report_name_collisions(updates)
    updates.sort(key=lambda u: u.unit)
    names, colors, descriptions = domoticz_api.apply_updates(
        devices,
        _state.dev_ids,
        updates,
        saved.auto_names,
        saved.auto_colors,
        saved.auto_descriptions,
        allow_create=True,
    )
    saved.auto_names = names
    saved.auto_colors = colors
    saved.auto_descriptions = descriptions
    saved.unit_alloc = _state.alloc
    domoticz_api.save_state(saved)


def onCommand(DeviceID, Unit, Command, Level, Color):
    cfg = _state.cfg
    if cfg is None or not cfg.allow_control:
        Domoticz.Error("command ignored: control is disabled")
        return
    # Match the DEVICE as well as the unit. Unit numbers are unique only within a Device, so
    # unit 1 exists on every one of them; dispatching on the number alone could fire a power
    # action from an unrelated tile.
    if DeviceID != _state.dev_ids.get(planner.DEVICE_CONTROL):
        return
    if Unit == control.UNIT_IDENTIFY:
        want = str(Command).strip().lower() == "on"
        try:
            _state.client.patch(_state.client.chassis, {"LocationIndicatorActive": want})
        except redfish_client.RedfishError as exc:
            Domoticz.Error(f"identify LED failed: {exc}")
            return
        # Remember it straight away. The chassis is only re-read on the SLOW tier, while the
        # control devices are rewritten on EVERY poll, so without this the next poll would push
        # the switch back to its stale value and undo what the user just did.
        chassis = _state.slow_parts.get("chassis")
        if chassis is not None:
            _state.slow_parts["chassis"] = dataclasses.replace(chassis, identify_on=want)
        domoticz_api.set_switch(
            _devices(), _state.dev_ids[planner.DEVICE_CONTROL], control.UNIT_IDENTIFY, want
        )
        Domoticz.Status(f"identify LED turned {'on' if want else 'off'}")
        return
    if Unit != control.UNIT_POWER_CONTROL:
        return
    reset_type = control.level_to_reset_type(Level)
    if reset_type is None:
        Domoticz.Error(f"power command refused: level {Level} maps to no action")
        return
    # Availability is checked HERE, not by renumbering the menu, so a stored level in a scene or
    # timer always means what it meant when it was saved.
    if not control.is_available(reset_type, _state.allowable, cfg.allow_hard_power):
        Domoticz.Error(
            f"power command refused: {reset_type} is not currently available "
            f"(server-advertised={bool(_state.allowable)}, hard actions allowed="
            f"{cfg.allow_hard_power})"
        )
        return
    try:
        _state.client.post(
            _state.client.system + "/Actions/ComputerSystem.Reset",
            {"ResetType": reset_type},
        )
        # HTTP 204 means the iDRAC ACCEPTED the action, not that the server acted on it. A
        # graceful shutdown or restart is handed to the host OS, so with no OS or agent running it
        # returns 204 and nothing happens. The Power State device reports what actually occurred.
        Domoticz.Status(f"power action accepted by iDRAC: {reset_type}")
    except redfish_client.RedfishError as exc:
        Domoticz.Error(f"power action {reset_type} refused: {exc}")
