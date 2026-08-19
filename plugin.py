# pyright: reportMissingImports=false, reportUndefinedVariable=false, reportAttributeAccessIssue=false
"""\
<plugin key="dellidrac" name="Dell iDRAC Monitor" author="Rouzax" version="0.1.0" externallink="https://github.com/Rouzax/dell-idrac-domoticz-plugin">
    <description>
        <h2>Dell PowerEdge monitor via iDRAC Redfish</h2>
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
            <param field="PollInterval" type="number" label="Poll Interval (s)" min="15" max="600" step="5" default="30" width="100px">
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
        </group>
        <group label="Control">
            <param field="AllowHardPowerActions" type="boolean" label="Allow Force Off and Power Cycle" default="false" visible_when="AllowControl=true">
                <description>Adds the two hard power actions to the Power Control selector. Graceful shutdown and restart are always offered when control is enabled.</description>
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
        self.backoff = 0.0
        self.slow_parts = {}
        self.alloc = {}
        self.resolved = False
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
    saved = domoticz_api.load_state()
    _state.alloc = dict(saved.unit_alloc)
    Domoticz.Heartbeat(_HEARTBEAT_SECONDS)
    Domoticz.Status(f"Dell iDRAC Monitor started for {_state.cfg.address}")


def onStop():
    Domoticz.Status("Dell iDRAC Monitor stopped")


def poll_fast(client) -> dict:
    return model.parse_sensors(client.get_expanded(client.sensors))


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
            # rather than stalling. Conventional default paths are used until this succeeds.
            _state.client.resolve()
            _state.resolved = True
        sensors = poll_fast(_state.client)
        _state.slow_tick += 1
        if _state.slow_tick >= cfg.slow_every or not _state.slow_parts["threshold_map"]:
            _state.slow_tick = 0
            _state.slow_parts = poll_slow(_state.client, cfg)
    except redfish_client.RedfishError as exc:
        _state.backoff = min(
            _BACKOFF_CAP, _state.backoff * 2 if _state.backoff else _BACKOFF_INITIAL
        )
        Domoticz.Error(f"iDRAC unreachable, backing off {_state.backoff:.0f}s: {exc}")
        # Write nothing. Domoticz flags the devices itself once LastUpdate goes stale, and a
        # zero written here would corrupt every device's recorded history permanently.
        return

    _state.backoff = 0.0
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

    power = sensors.get("SystemBoardPwrConsumption")
    prev_wh = domoticz_api.read_prev_counter_wh(devices, _state.dev_id, planner.UNIT_POWER)
    if prev_wh is None:
        # Unknown, not zero. Leave the counter untouched this cycle rather than restart it.
        Domoticz.Error("energy counter unreadable; leaving it untouched this cycle")
        prev_wh, power = 0.0, None
    added = (
        energy.integrate_wh(power.reading, cfg.poll_interval) if power and power.reading else 0.0
    )
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
        **parts,
    )
    names = domoticz_api.apply_updates(
        devices, _state.dev_id, updates, saved.auto_names, allow_create=True
    )
    saved.auto_names = names
    saved.unit_alloc = _state.alloc
    domoticz_api.save_state(saved)


def onCommand(DeviceID, Unit, Command, Level, Color):
    Domoticz.Debug(f"onCommand unit={Unit} command={Command!r} level={Level}")
