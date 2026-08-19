import pytest

import control
import plugin
import redfish_client
from tests import domoticz_stub
from tests.fixture_loader import load


class FakeClient:
    """Replays fixtures by path. Raises for paths the test did not stub."""

    def __init__(
        self, profile="t550", fail_paths=(), telemetry_available=False, report_name="PowerMetrics"
    ):
        self.profile = profile
        self.fail_paths = set(fail_paths)
        self.telemetry_available = telemetry_available
        # Report ids differ by licence and management. "PowerMetrics" is what a Datacenter iDRAC
        # serves; "OME-PMP-Power-A" is what an OpenManage-managed machine on the Advanced licence
        # serves instead, alongside reports the plugin has no use for. Both are real.
        self.report_name = report_name
        self.calls = []
        # Reuse the real path derivation so the test exercises the same mapping.
        redfish_client.RedfishClient._set_paths(
            self,
            redfish_client.DEFAULT_SYSTEM,
            redfish_client.DEFAULT_CHASSIS,
            redfish_client.DEFAULT_MANAGER,
        )

    def resolve(self):
        return None

    def metric_report_ids(self):
        # Reuse the real implementation so the test exercises the same parsing.
        return redfish_client.RedfishClient.metric_report_ids(self)

    def _maybe_fail(self, path):
        self.calls.append(path)
        for bad in self.fail_paths:
            if bad in path:
                raise redfish_client.RedfishError(f"boom for {path}")

    def get(self, path):
        self._maybe_fail(path)
        if path == self.system:
            return load(self.profile, "system")
        if path == self.chassis:
            return load(self.profile, "chassis")
        if path == self.thermal:
            return load(self.profile, "thermal")
        if path == self.power:
            return load(self.profile, "power")
        if path == self.dell_attributes:
            return load(self.profile, "dell_attributes")
        if path == self.storage_collection:
            return {"Members": [{"@odata.id": "/ctrl"}]}
        if path == self.metric_reports:
            if not self.telemetry_available:
                return {}
            return {
                "Members": [
                    # A report the plugin must look at and then never poll again.
                    {"@odata.id": f"{self.metric_reports}/OME-Telemetry-SMARTData"},
                    {"@odata.id": f"{self.metric_reports}/{self.report_name}"},
                ]
            }
        if path == f"{self.metric_reports}/{self.report_name}":
            return load(self.profile, "power_metrics")
        if path.startswith(f"{self.metric_reports}/"):
            # Carries no power metrics, so it must be discarded after discovery.
            return {"MetricValues": [{"MetricId": "Junk", "MetricValue": "1"}]}
        return {}

    def get_expanded(self, path, levels=1):
        self._maybe_fail(path)
        if path == self.sensors:
            return load(self.profile, "sensors_expanded")
        if path == self.ethernet:
            return load(self.profile, "ethernet")
        if path == "/ctrl":
            return load(self.profile, "storage_expanded")
        if path == "/ctrl/Volumes":
            return load(self.profile, "volumes")
        return {}


_PARAMS = {
    "HardwareID": 3,
    "Address": "10.0.0.1",
    "Username": "root",
    "Password": "secret",
    "AllowControl": "false",
    "PollInterval": "30",
    "SlowEvery": "10",
    "EnableDrives": "true",
    "EnableVolumes": "true",
    "EnableNICs": "true",
    "EnablePSUs": "true",
    "DriveLifeFloor": "10",
    "VerifyTLS": "false",
    "RequestTimeout": "30",
    "DebugLevel": "0",
}


@pytest.fixture
def started(monkeypatch):
    params = dict(_PARAMS)
    monkeypatch.setattr(plugin, "Parameters", params, raising=False)
    monkeypatch.setattr(plugin, "Devices", domoticz_stub.Devices, raising=False)
    plugin.onStart()
    plugin._state.client = FakeClient()
    return plugin._state


def _units(family=None):
    """Units of one Device. Unit numbers repeat across devices now, so a lookup names its family."""
    dev_id = plugin._state.dev_ids[family or plugin.planner.DEVICE_SYSTEM]
    dev = domoticz_stub.Devices.get(dev_id)
    return dev.Units if dev else {}


def _control_id():
    return plugin._state.dev_ids[plugin.planner.DEVICE_CONTROL]


def _beat_once(state):
    """Advance past the poll-interval gate and run one heartbeat."""
    state.beat = state.cfg.poll_interval // 10
    plugin.onHeartbeat()


def test_onstart_sets_up_state_without_touching_the_network():
    pass  # exercised by the `started` fixture


def test_heartbeat_creates_devices_for_discovered_hardware(started):
    _beat_once(started)
    units = _units()
    assert plugin.planner.UNIT_POWER in units
    assert plugin.planner.UNIT_HEALTH in units
    # Fans live on the thermal Device, not the system one.
    fans = [
        u
        for u in _units(plugin.planner.DEVICE_THERMAL).values()
        if u.Options.get("Custom") == "1;RPM"
    ]
    assert len(fans) == 3


def test_heartbeat_is_idempotent(started):
    _beat_once(started)
    first = len(_units())
    _beat_once(started)
    assert len(_units()) == first


def test_unit_allocation_persists_across_a_restart(started, monkeypatch):
    _beat_once(started)
    alloc_before = dict(plugin._state.alloc)
    monkeypatch.setattr(plugin, "Devices", domoticz_stub.Devices, raising=False)
    plugin.onStart()
    plugin._state.client = FakeClient()
    assert plugin._state.alloc == alloc_before


def test_transport_failure_writes_nothing_and_keeps_the_last_value(started):
    """An unreachable iDRAC must leave every device exactly as it was.

    The plugin does not flag devices itself: Domoticz does its own staleness detection from
    LastUpdate. Writing anything here, a zero above all, would corrupt recorded history.
    """
    _beat_once(started)
    unit = _units()[plugin.planner.UNIT_INLET]
    before_s, before_n = unit.sValue, unit.nValue
    started.client = FakeClient(fail_paths=("/Sensors",))
    _beat_once(started)
    assert unit.sValue == before_s
    assert unit.nValue == before_n
    assert unit.TimedOut == 0
    assert started.backoff > 0


def test_backoff_grows_and_suppresses_polling(started):
    started.client = FakeClient(fail_paths=("/Sensors",))
    _beat_once(started)
    assert started.backoff == plugin._BACKOFF_INITIAL
    calls = len(started.client.calls)
    plugin.onHeartbeat()
    assert len(started.client.calls) == calls


def _drain_backoff(state):
    """Burn heartbeats until the backoff countdown lets the next poll through."""
    for _ in range(int(plugin._BACKOFF_CAP // plugin._HEARTBEAT_SECONDS) + 2):
        if state.backoff <= 0:
            return
        plugin.onHeartbeat()
    raise AssertionError("backoff never drained")


def test_backoff_actually_doubles_across_consecutive_failures(started):
    """The countdown is consumed to exactly zero, so growth must not be read back off it.

    Found live: the log said "backing off 20s" on every failure of a sustained outage. The
    doubling branch was unreachable because _BACKOFF_INITIAL is an exact multiple of the
    heartbeat, so the countdown always hit 0.0 and the falsy branch reset it to the initial
    value. The 900 s cap was dead configuration.
    """
    started.client = FakeClient(fail_paths=("/Sensors",))
    seen = []
    for _ in range(4):
        _drain_backoff(started)
        _beat_once(started)
        seen.append(started.backoff)
    assert seen == [
        plugin._BACKOFF_INITIAL,
        plugin._BACKOFF_INITIAL * 2,
        plugin._BACKOFF_INITIAL * 4,
        plugin._BACKOFF_INITIAL * 8,
    ]


def test_backoff_resets_after_a_successful_poll(started):
    started.client = FakeClient(fail_paths=("/Sensors",))
    _beat_once(started)
    _drain_backoff(started)
    _beat_once(started)
    assert started.backoff == plugin._BACKOFF_INITIAL * 2
    started.client = FakeClient()
    _drain_backoff(started)
    _beat_once(started)
    assert started.backoff == 0.0
    # And the NEXT failure starts from the initial value again, not from where it left off.
    started.client = FakeClient(fail_paths=("/Sensors",))
    _beat_once(started)
    assert started.backoff == plugin._BACKOFF_INITIAL


def test_a_failing_storage_subcall_does_not_cost_the_rest_of_the_slow_tier(started):
    started.client = FakeClient(fail_paths=("/ctrl",))
    _beat_once(started)
    units = _units()
    assert plugin.planner.UNIT_HEALTH in units
    assert not [u for u in units if u >= plugin.planner.BLOCK_DRIVES]


def test_uptime_and_intrusion_devices_are_created(started):
    _beat_once(started)
    units = _units()
    assert float(units[plugin.planner.UNIT_UPTIME].sValue) > 0
    assert units[plugin.planner.UNIT_INTRUSION].sValue == "Normal"


def test_dual_socket_profile_creates_two_cpu_temp_devices(started):
    started.client = FakeClient(profile="dual")
    _beat_once(started)
    cpu = [
        u
        for u in _units(plugin.planner.DEVICE_THERMAL).values()
        if "CPU" in u.Name and "Temp" in u.Name
    ]
    assert len(cpu) == 2


def test_energy_counter_never_decreases(started):
    _beat_once(started)
    first = float(_units()[plugin.planner.UNIT_POWER].sValue.split(";")[1])
    _beat_once(started)
    second = float(_units()[plugin.planner.UNIT_POWER].sValue.split(";")[1])
    assert second >= first


def test_password_never_reaches_the_log(started):
    started.client = FakeClient(fail_paths=("/Sensors",))
    _beat_once(started)
    assert not any("secret" in line for line in domoticz_stub._module._log)


def test_no_control_devices_when_control_is_off(started):
    _beat_once(started)
    units = _units(plugin.planner.DEVICE_CONTROL)
    assert control.UNIT_POWER_CONTROL not in units
    assert control.UNIT_IDENTIFY not in units


def test_command_is_refused_when_control_is_off(started):
    _beat_once(started)
    sent = []
    started.client.post = lambda path, body: sent.append((path, body))
    plugin.onCommand(_control_id(), control.UNIT_POWER_CONTROL, "Set Level", 10, "")
    assert sent == []


def test_control_enabled_creates_the_control_devices(started, monkeypatch):
    monkeypatch.setitem(plugin.Parameters, "AllowControl", "true")
    plugin.onStart()
    plugin._state.client = FakeClient()
    _beat_once(plugin._state)
    units = _units()
    assert control.UNIT_POWER_CONTROL in units
    assert control.UNIT_IDENTIFY in units


def test_a_power_command_posts_the_reset_action(started, monkeypatch):
    monkeypatch.setitem(plugin.Parameters, "AllowControl", "true")
    plugin.onStart()
    plugin._state.client = FakeClient()
    _beat_once(plugin._state)
    sent = []
    plugin._state.client.post = lambda path, body: sent.append((path, body)) or {}
    plugin.onCommand(_control_id(), control.UNIT_POWER_CONTROL, "Set Level", 10, "")
    assert sent and sent[0][1]["ResetType"] == "On"


def test_a_hard_action_level_is_refused_while_hard_actions_are_off(started, monkeypatch):
    monkeypatch.setitem(plugin.Parameters, "AllowControl", "true")
    monkeypatch.setitem(plugin.Parameters, "AllowHardPowerActions", "false")
    plugin.onStart()
    plugin._state.client = FakeClient()
    _beat_once(plugin._state)
    sent = []
    plugin._state.client.post = lambda path, body: sent.append((path, body)) or {}
    # Level 40 would be a hard action if they were enabled; only 3 graceful ones exist.
    plugin.onCommand(_control_id(), control.UNIT_POWER_CONTROL, "Set Level", 40, "")
    assert sent == []


def test_component_power_devices_appear_when_telemetry_is_available(started):
    started.client = FakeClient(telemetry_available=True)
    _beat_once(started)
    units = _units()
    assert float(units[plugin.planner.UNIT_CPU_POWER].sValue) > 0
    assert units[plugin.planner.UNIT_STORAGE_POWER].Name == "Storage Power"
    assert started.telemetry is True
    # And the energy device switches to the wall figure telemetry reports.
    assert float(units[plugin.planner.UNIT_POWER].sValue.split(";")[0]) == 170.0


def test_no_component_power_devices_when_telemetry_is_absent(started):
    """The normal case: most iDRACs cannot serve this at all."""
    _beat_once(started)
    units = _units()
    assert plugin.planner.UNIT_CPU_POWER not in units
    assert started.telemetry is False
    # Energy falls back to the board sensor.
    assert float(units[plugin.planner.UNIT_POWER].sValue.split(";")[0]) == 144.0


def test_an_unavailable_telemetry_endpoint_is_asked_for_only_once(started):
    """A licence-gated endpoint must not cost a wasted request on every single poll."""
    started.client = FakeClient(fail_paths=("MetricReports",))
    _beat_once(started)
    assert started.telemetry is False
    assert sum("MetricReports" in c for c in started.client.calls) == 1
    _beat_once(started)
    assert sum("MetricReports" in c for c in started.client.calls) == 1


def test_the_power_report_is_found_under_an_openmanage_name(started):
    """An OpenManage-managed machine has no "PowerMetrics" report at all.

    Its Power Manager Plugin publishes "OME-PMP-Power-A" and friends under the Advanced licence,
    while Dell's built-in reports answer with a licence error. Selecting by name would find
    nothing here, so the report is selected by the metric ids it actually contains.
    """
    started.client = FakeClient(telemetry_available=True, report_name="OME-PMP-Power-A")
    _beat_once(started)
    units = _units()
    assert float(units[plugin.planner.UNIT_CPU_POWER].sValue) > 0
    assert started.telemetry is True
    assert started.metric_paths == ("/redfish/v1/TelemetryService/MetricReports/OME-PMP-Power-A",)


def test_reports_without_power_metrics_are_discovered_once_then_dropped(started):
    """A managed machine can expose a dozen reports, several of them large. Poll only the useful."""
    started.client = FakeClient(telemetry_available=True)
    _beat_once(started)
    assert all("SMARTData" not in p for p in started.metric_paths)
    before = sum("SMARTData" in c for c in started.client.calls)
    assert before == 1, "the useless report is read once, during discovery"
    _beat_once(started)
    assert sum("SMARTData" in c for c in started.client.calls) == 1
    # And the collection itself is not re-listed on every poll either.
    assert sum(c.endswith("/MetricReports") for c in started.client.calls) == 1


def test_a_failing_telemetry_call_does_not_cost_the_rest_of_the_poll(started):
    started.client = FakeClient(fail_paths=("MetricReports",))
    _beat_once(started)
    units = _units()
    assert plugin.planner.UNIT_HEALTH in units
    assert plugin.planner.UNIT_INLET in units
    assert started.backoff == 0.0


class RecordingClient(FakeClient):
    """FakeClient that records PATCHes and can start unlicensed, then succeed after one."""

    def __init__(self, *a, becomes_available=False, **kw):
        super().__init__(*a, **kw)
        self.patches = []
        self.becomes_available = becomes_available

    def patch(self, path, body):
        self.calls.append(f"PATCH {path}")
        self.patches.append((path, body))
        if self.becomes_available:
            self.telemetry_available = True
        return {}


def test_telemetry_is_never_configured_unless_the_setting_is_on(started):
    started.client = RecordingClient()
    _beat_once(started)
    assert started.client.patches == []


def test_the_setting_enables_telemetry_and_the_metrics_then_appear(started):
    started.cfg = plugin.config.parse_config(
        {**_PARAMS, "SetupTelemetry": "true", "DebugLevel": "0"}
    )
    started.client = RecordingClient(becomes_available=True)
    _beat_once(started)
    paths = {p for p, _ in started.client.patches}
    assert paths == {started.client.idrac_attributes}
    body = started.client.patches[0][1]["Attributes"]
    assert body == {
        "Telemetry.1.EnableTelemetry": "Enabled",
        "TelemetryPowerMetrics.1.EnableTelemetry": "Enabled",
    }
    # The next poll finds the report that the write just switched on.
    _beat_once(started)
    units = _units()
    assert float(units[plugin.planner.UNIT_CPU_POWER].sValue) > 0


def test_telemetry_is_not_reconfigured_when_it_already_works(started):
    """The safeguard that keeps the plugin off a machine OpenManage already manages."""
    started.cfg = plugin.config.parse_config({**_PARAMS, "SetupTelemetry": "true"})
    started.client = RecordingClient(telemetry_available=True)
    _beat_once(started)
    assert started.client.patches == []
    assert started.telemetry is True


def test_telemetry_setup_is_attempted_only_once_per_start(started):
    """A machine that cannot be fixed this way must not be written to on every poll."""
    started.cfg = plugin.config.parse_config({**_PARAMS, "SetupTelemetry": "true"})
    started.client = RecordingClient(becomes_available=False)
    _beat_once(started)
    _beat_once(started)
    _beat_once(started)
    assert len(started.client.patches) == 1


def test_a_command_from_another_device_is_ignored(started):
    """Unit numbers are unique only WITHIN a Device, so unit 1 exists on every one of them.

    Dispatching on the unit number alone would let a click on an unrelated tile, the first PSU
    or the first RAID volume, fire a power action. onCommand must match the DeviceID too.
    """
    started.cfg = plugin.config.parse_config({**_PARAMS, "AllowControl": "true"})
    sent = []
    started.client = FakeClient()
    started.client.post = lambda path, body: sent.append((path, body))
    started.allowable = ["On"]

    for family in (
        plugin.planner.DEVICE_SYSTEM,
        plugin.planner.DEVICE_POWER,
        plugin.planner.DEVICE_STORAGE,
        plugin.planner.DEVICE_GPU,
    ):
        plugin.onCommand(started.dev_ids[family], control.UNIT_POWER_CONTROL, "Set Level", 10, "")
    assert sent == [], "a power action fired from a device that is not the control device"

    # And the real control device still works.
    plugin.onCommand(_control_id(), control.UNIT_POWER_CONTROL, "Set Level", 10, "")
    assert sent and sent[0][1]["ResetType"] == "On"


def test_each_family_gets_its_own_device_id(started):
    ids = started.dev_ids
    assert len(set(ids.values())) == len(plugin.planner.DEVICE_FAMILIES)
    assert all(str(_PARAMS["HardwareID"]) in v for v in ids.values())
