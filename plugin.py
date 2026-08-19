# pyright: reportMissingImports=false, reportUndefinedVariable=false, reportAttributeAccessIssue=false
"""\
<plugin key="dellidrac" name="Dell iDRAC Monitor" author="Rouzax" version="0.1.0" externallink="https://github.com/Rouzax/dell-idrac-domoticz-plugin">
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
    </description>
    <params>
        <param field="Address" label="iDRAC Address" width="200px" required="true">
            <description>Hostname or IP of the iDRAC, without a scheme (for example 192.168.1.10).</description>
        </param>
        <param field="Username" label="Username" width="150px" required="true" default="root"/>
        <param field="Password" label="Password" width="200px" required="true" password="true">
            <description>iDRAC password. Stored in cleartext in the Domoticz database and never written to the log.</description>
        </param>
        <param field="AllowControl" label="Allow Control" width="150px">
            <description>Enable power actions and the identify LED. Off by default: the plugin stays strictly read-only until this is turned on. Once enabled, any Domoticz user, scene, timer or API client with access to this hardware can power off the server.</description>
            <options>
                <option label="No" value="false" default="true"/>
                <option label="Yes" value="true"/>
            </options>
        </param>
        <group label="Polling">
            <param field="PollInterval" type="number" label="Poll Interval (s)" min="20" max="600" step="10" default="30" width="100px">
                <description>How often to read live sensors, in seconds. One request per poll.</description>
            </param>
            <param field="SlowEvery" type="number" label="Slow Poll (every N polls)" min="1" max="60" step="1" default="10" width="100px">
                <description>How often to refresh health, storage, NICs and re-run discovery, as a multiple of the poll interval. At the defaults this is every 5 minutes.</description>
            </param>
        </group>
        <group label="Devices">
            <param field="EnableDrives" type="boolean" label="Physical drives" default="true"/>
            <param field="EnableVolumes" type="boolean" label="RAID volumes" default="true"/>
            <param field="EnablePSUs" type="boolean" label="Power supplies" default="true"/>
            <param field="EnableNICs" type="boolean" label="Network interfaces" default="true"/>
            <param field="DriveLifeFloor" type="number" label="Drive life warning (%)" min="0" max="100" step="1" default="10" width="100px">
                <description>Warn when a drive reports less than this much predicted media life remaining.</description>
            </param>
            <param field="FanBarMax" type="number" label="Fan bar maximum (RPM)" min="0" max="60000" step="500" default="6000" width="100px">
                <description>Top of the scale on fan bar graphs. Redfish does not report a maximum fan speed, so this cannot be detected: a tower or 2U server typically peaks around 5000 to 6000 RPM, while 1U fans can exceed 15000. Set 0 to leave fan bars off. A fan running faster than this still reads full and green rather than falling off the scale.</description>
            </param>
        </group>
        <group label="Control">
            <param field="AllowHardPowerActions" type="boolean" label="Allow Force Off and Power Cycle" default="false">
                <description>Adds the two hard power actions to the Power Control selector. Graceful shutdown and restart are always offered when control is enabled. Has no effect while Allow Control is No: no control device is created and every command is refused.</description>
            </param>
        </group>
        <group label="Advanced">
            <param field="VerifyTLS" type="boolean" label="Verify TLS certificate" default="false">
                <description>Off by default because iDRAC ships a self-signed certificate. While off, the connection is encrypted but NOT authenticated, so a host on your network could impersonate the iDRAC.</description>
            </param>
            <param field="RequestTimeout" type="number" label="Request Timeout (s)" min="5" max="120" step="5" default="30" width="100px"/>
            <param field="DebugLevel" label="Debug Level" width="150px">
                <description>Logging verbosity. The iDRAC password is never written to the log at any level.</description>
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
        self.dev_id = ""
        self.beat = 0
        self.slow_tick = 0
        # Telemetry is licence-gated and absent on most iDRACs. None means "not tried yet";
        # False latches after the first refusal so the plugin stops paying for a request that
        # will never succeed. Reset by onStart, so a licence upgrade is picked up on restart.
        self.telemetry = None
        # Which report paths actually carry power metrics on THIS machine. Discovered once,
        # because the ids differ by licence and management, then polled directly.
        self.metric_paths = ()
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
    _state.dev_id = domoticz_api.device_id(Parameters["HardwareID"])
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
    }
)
# A machine managed by OpenManage can expose a dozen reports, several of them large (SMART data,
# NIC statistics). Discovery reads them once; this caps the damage if a server offers many more.
_MAX_METRIC_REPORTS = 16


def discover_metric_paths(client, state) -> tuple:
    """Find which reports on THIS machine carry the power metrics, by reading them.

    Report ids are not fixed. A Datacenter iDRAC serves Dell's built-in "PowerMetrics"; a machine
    managed by OpenManage Enterprise under the Advanced licence instead carries the Power Manager
    Plugin's own reports, "OME-PMP-Power-A" and friends, and answers the built-in names with a
    licence error. Both were seen on real hardware, so the report is selected by the metric ids it
    actually contains rather than by its name.
    """
    paths = []
    for path in client.metric_report_ids()[:_MAX_METRIC_REPORTS]:
        try:
            found = model.parse_metric_report(client.get(path))
        except redfish_client.RedfishError as exc:
            # One unreadable report, licence-gated or otherwise, must not hide the others.
            Domoticz.Debug(f"metric report {path} unreadable: {exc}")
            continue
        if _WANTED_METRICS & set(found):
            paths.append(path)
    state.metric_paths = tuple(paths)
    return state.metric_paths


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
        metrics = {}
        for path in state.metric_paths:
            # Later reports win, which is right: they are polled in collection order and a
            # machine exposing the same metric twice is reporting the same quantity.
            metrics.update(model.parse_metric_report(client.get(path)))
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

    # Integrate the same figure the device displays: wall draw when telemetry supplies it,
    # otherwise the board sensor. Anything else would make the counter disagree with its own watts.
    board = sensors.get("SystemBoardPwrConsumption")
    watts = metrics.get("SystemInputPower")
    if watts is None:
        watts = board.reading if board is not None else None
    prev_wh = domoticz_api.read_prev_counter_wh(devices, _state.dev_id, planner.UNIT_POWER)
    if prev_wh is None:
        # Unknown, not zero. Leave the counter untouched this cycle rather than restart it.
        Domoticz.Error("energy counter unreadable; leaving it untouched this cycle")
        prev_wh, watts = 0.0, None
    added = energy.integrate_wh(watts, cfg.poll_interval) if watts else 0.0
    # Tie the sanity ceiling to the machine's OWN measured peak draw rather than a flat constant.
    # A flat 1_000_000 Wh headroom is roughly 278 days of running at 150 W, so it could never fire.
    # Allowing twice the observed peak over ten poll intervals still leaves generous slack for a
    # catch-up after downtime while rejecting a genuinely absurd jump.
    peak_w = parts["dell_attrs"].peak_watts or 1000.0
    ceiling = prev_wh + energy.integrate_wh(peak_w * 2, cfg.poll_interval * 10)
    counter_wh, warning = energy.clamp_counter(prev_wh, prev_wh + added, ceiling_wh=ceiling)
    if warning:
        Domoticz.Error(warning)

    updates = planner.plan(
        sensors=sensors,
        inventory=inventory,
        alloc=_state.alloc,
        cfg=cfg,
        energy_wh=counter_wh,
        metrics=metrics,
        **parts,
    )
    updates.extend(control.control_updates(cfg, _state.allowable, parts["chassis"].identify_on))
    updates.sort(key=lambda u: u.unit)
    names = domoticz_api.apply_updates(
        devices, _state.dev_id, updates, saved.auto_names, allow_create=True
    )
    saved.auto_names = names
    saved.unit_alloc = _state.alloc
    domoticz_api.save_state(saved)


def onCommand(DeviceID, Unit, Command, Level, Color):
    cfg = _state.cfg
    if cfg is None or not cfg.allow_control:
        Domoticz.Error("command ignored: control is disabled")
        return
    if Unit == control.UNIT_IDENTIFY:
        want = str(Command).strip().lower() == "on"
        try:
            _state.client.patch(_state.client.chassis, {"LocationIndicatorActive": want})
        except redfish_client.RedfishError as exc:
            Domoticz.Error(f"identify LED failed: {exc}")
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
