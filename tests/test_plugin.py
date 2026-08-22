import pytest

import control
import planner
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
    assert float(units[plugin.planner.UNIT_CPU_POWER].sValue.split(";")[0]) > 0
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
    assert float(units[plugin.planner.UNIT_CPU_POWER].sValue.split(";")[0]) > 0
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
    assert float(units[plugin.planner.UNIT_CPU_POWER].sValue.split(";")[0]) > 0


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


def test_identify_survives_the_next_poll(started):
    """The plugin used to fight the user here.

    identify_on is refreshed only in the slow tier, but the control devices are rewritten every
    fast poll, so 30 seconds after a successful switch-on the plugin wrote the tile back to off
    from its stale cache. The LED really was blinking; the tile said otherwise.
    """
    started.cfg = plugin.config.parse_config({**_PARAMS, "AllowControl": "true"})
    patched = []
    started.client = FakeClient()
    started.client.patch = lambda path, body: patched.append(body) or {}
    _beat_once(started)

    plugin.onCommand(_control_id(), control.UNIT_IDENTIFY, "On", 0, "")
    assert patched == [{"LocationIndicatorActive": True}]
    assert started.slow_parts["chassis"].identify_on is True

    _beat_once(started)
    unit = _units(plugin.planner.DEVICE_CONTROL)[control.UNIT_IDENTIFY]
    assert unit.nValue == 1, "the next poll reverted the switch the user just turned on"


def test_identify_off_is_also_remembered(started):
    started.cfg = plugin.config.parse_config({**_PARAMS, "AllowControl": "true"})
    started.client = FakeClient()
    started.client.patch = lambda path, body: {}
    _beat_once(started)
    plugin.onCommand(_control_id(), control.UNIT_IDENTIFY, "On", 0, "")
    plugin.onCommand(_control_id(), control.UNIT_IDENTIFY, "Off", 0, "")
    assert started.slow_parts["chassis"].identify_on is False
    _beat_once(started)
    assert _units(plugin.planner.DEVICE_CONTROL)[control.UNIT_IDENTIFY].nValue == 0


def test_a_failed_identify_does_not_claim_success(started):
    started.cfg = plugin.config.parse_config({**_PARAMS, "AllowControl": "true"})
    started.client = FakeClient()

    def boom(path, body):
        raise plugin.redfish_client.RedfishError("nope")

    started.client.patch = boom
    _beat_once(started)
    before = started.slow_parts["chassis"].identify_on
    plugin.onCommand(_control_id(), control.UNIT_IDENTIFY, "On", 0, "")
    assert started.slow_parts["chassis"].identify_on == before


def test_the_identify_switch_responds_immediately(started):
    """A switch that takes a poll interval to move looks broken even when it worked."""
    started.cfg = plugin.config.parse_config({**_PARAMS, "AllowControl": "true"})
    started.client = FakeClient()
    started.client.patch = lambda path, body: {}
    _beat_once(started)
    unit = _units(plugin.planner.DEVICE_CONTROL)[control.UNIT_IDENTIFY]
    assert unit.nValue == 0

    plugin.onCommand(_control_id(), control.UNIT_IDENTIFY, "On", 0, "")
    assert unit.nValue == 1, "the tile should move on the command, not on the next poll"

    plugin.onCommand(_control_id(), control.UNIT_IDENTIFY, "Off", 0, "")
    assert unit.nValue == 0


class ManyReportsClient(FakeClient):
    """A machine advertising far more metric reports than the plugin's read budget.

    Modelled on a real PowerEdge R440: it lists 39 reports and the only one carrying
    SystemInputPower, "PowerMetrics", sits at position 23. Reading the list in the order the
    server happens to return it means never seeing it.
    """

    def __init__(self, *args, power_at=22, total=39, **kwargs):
        super().__init__(*args, telemetry_available=True, **kwargs)
        names = [f"Filler{i}" for i in range(total)]
        names[power_at] = "PowerMetrics"
        self.report_names = names

    def get(self, path):
        if path == self.metric_reports:
            self._maybe_fail(path)
            return {
                "Members": [{"@odata.id": f"{self.metric_reports}/{n}"} for n in self.report_names]
            }
        return super().get(path)


def test_a_power_report_beyond_the_read_budget_is_still_found(started):
    """The read budget must not be able to hide the one report that matters.

    Measured on a real R440: with the reports read in server order, SystemInputPower and
    TotalPciePower were both lost and the plugin fell back to the board power sensor without
    saying so. The board sensor misses the power supplies' own conversion loss, so the figure
    is quietly wrong rather than absent.
    """
    started.client = ManyReportsClient()
    _beat_once(started)
    assert started.telemetry is True
    assert started.metric_paths == (f"{started.client.metric_reports}/PowerMetrics",)


def test_a_report_is_still_chosen_by_content_and_never_by_its_name(started):
    """Names only decide the ORDER reports are read in. A report called "...Power..." that
    carries no power metric must still be rejected, or the ordering hint would have quietly
    become a selection rule."""
    client = ManyReportsClient()
    # A decoy that sorts to the front on name but holds nothing the plugin wants.
    client.report_names[0] = "OME-PMP-Power-Decoy"
    started.client = client
    _beat_once(started)
    assert "Decoy" not in " ".join(started.metric_paths)
    assert started.metric_paths == (f"{client.metric_reports}/PowerMetrics",)


@pytest.fixture
def started_with_affix(monkeypatch, request):
    """A plugin started with a name prefix and/or suffix already configured."""
    params = dict(_PARAMS)
    params.update(getattr(request, "param", {}))
    monkeypatch.setattr(plugin, "Parameters", params, raising=False)
    monkeypatch.setattr(plugin, "Devices", domoticz_stub.Devices, raising=False)
    plugin.onStart()
    plugin._state.client = FakeClient()
    return plugin._state


@pytest.mark.parametrize("started_with_affix", [{"NamePrefix": "R750 - "}], indirect=True)
def test_a_name_prefix_is_applied_to_every_created_device(started_with_affix):
    """Two installs monitoring two servers otherwise produce identical device names, and a
    dzVents lookup by name then silently picks whichever it finds first."""
    _beat_once(started_with_affix)
    names = [u.Name for u in _units().values()]
    assert names, "no devices created"
    assert all(n.startswith("R750 - ") for n in names), names


@pytest.mark.parametrize("started_with_affix", [{"NameSuffix": "_TESTSRV"}], indirect=True)
def test_a_name_suffix_reaches_the_control_devices_too(started_with_affix):
    """The affix is applied after the control devices are appended, so nothing is missed."""
    started_with_affix.cfg = plugin.dataclasses.replace(started_with_affix.cfg, allow_control=True)
    _beat_once(started_with_affix)
    control_names = [u.Name for u in _units(plugin.planner.DEVICE_CONTROL).values()]
    assert control_names, "no control devices created"
    assert all(n.endswith("_TESTSRV") for n in control_names), control_names


@pytest.mark.parametrize("started_with_affix", [{"NamePrefix": "{servicetag} - "}], indirect=True)
def test_a_token_prefix_is_expanded_from_the_machine_itself(started_with_affix):
    """The whole point of the tokens: the user does not have to know or type the identifier."""
    _beat_once(started_with_affix)
    names = [u.Name for u in _units().values()]
    assert names
    assert not any("{servicetag}" in n for n in names), "token was not expanded"
    # The t550 fixture is sanitized, so the tag is the scrubber's placeholder, not a real one.
    assert all(n.startswith("SVCTAG0 - ") for n in names), names


@pytest.mark.parametrize("started_with_affix", [{"NamePrefix": "{servicetag} - "}], indirect=True)
def test_the_resolved_affix_is_shown_once_as_a_worked_example(started_with_affix):
    """A trailing space is invisible in the settings form, and a token is not what the user
    typed. Printing one finished name is the only way they can check it is what they meant."""
    import DomoticzEx

    DomoticzEx._log.clear()
    _beat_once(started_with_affix)
    examples = [line for line in DomoticzEx._log if "device names look like" in line]
    assert len(examples) == 1, DomoticzEx._log
    assert "SVCTAG0 - " in examples[0]
    # And it is not repeated on every poll.
    _beat_once(started_with_affix)
    assert sum("device names look like" in line for line in DomoticzEx._log) == 1


def test_no_worked_example_is_logged_when_no_affix_is_configured(started):
    import DomoticzEx

    DomoticzEx._log.clear()
    _beat_once(started)
    assert not [line for line in DomoticzEx._log if "device names look like" in line]


def _seed_domoticz_db(tmp_path, owned_names, owner_hardware_id=1):
    import sqlite3

    path = tmp_path / "domoticz.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE Hardware ([ID] INTEGER PRIMARY KEY, [Name] VARCHAR(200) NOT NULL)")
    con.execute(
        "CREATE TABLE DeviceStatus ([ID] INTEGER PRIMARY KEY, [HardwareID] INTEGER NOT NULL, "
        "[Name] VARCHAR(100) DEFAULT Unknown)"
    )
    con.execute("INSERT INTO Hardware VALUES (?, 'iDRAC T550')", (owner_hardware_id,))
    for name in owned_names:
        con.execute(
            "INSERT INTO DeviceStatus (HardwareID, Name) VALUES (?, ?)", (owner_hardware_id, name)
        )
    con.commit()
    con.close()
    return str(path)


def test_names_already_owned_by_another_install_are_reported_once(monkeypatch, tmp_path, started):
    """The motivating case: a second install with no prefix, colliding with the first. The
    plugin API cannot see the other install's devices, so this reads the database read-only."""
    import DomoticzEx

    db = _seed_domoticz_db(tmp_path, ["System Health", "Inlet Temp"])
    plugin.Parameters["Database"] = db
    DomoticzEx._log.clear()
    _beat_once(started)
    warnings = [line for line in DomoticzEx._log if "already exist under hardware" in line]
    assert len(warnings) == 1, DomoticzEx._log
    assert "iDRAC T550" in warnings[0]
    assert "System Health" in warnings[0]
    # Checked once per plugin start, not on every poll.
    _beat_once(started)
    assert sum("already exist under hardware" in line for line in DomoticzEx._log) == 1


def test_no_collision_warning_when_the_names_are_free(monkeypatch, tmp_path, started):
    import DomoticzEx

    plugin.Parameters["Database"] = _seed_domoticz_db(tmp_path, ["Something Else"])
    DomoticzEx._log.clear()
    _beat_once(started)
    assert not [line for line in DomoticzEx._log if "already exist under hardware" in line]


def _counter_update(unit, svalue, counter, name="CPU Power", device=planner.DEVICE_SYSTEM):
    return planner.DeviceUpdate(
        unit=unit,
        type_name="kWh",
        name=name,
        nvalue=0,
        svalue=svalue,
        device=device,
        counter=counter,
    )


def _seed_counter_device(dev_id, unit, svalue):
    u = domoticz_stub.Unit(Name="X", DeviceID=dev_id, Unit=unit, TypeName="kWh")
    u.Create()
    u.sValue = svalue
    u.Update(Log=False)


def test_attach_counters_appends_the_integrated_energy():
    plugin._state.dev_ids = {planner.DEVICE_SYSTEM: "dellidrac_1_system"}
    plugin._state.first_watts = {"dellidrac_1_system:14": 10.0}
    plugin._state.moved = {"dellidrac_1_system:14"}
    _seed_counter_device("dellidrac_1_system", 14, "40.0;100.0")
    out = plugin.attach_counters(
        domoticz_stub.Devices,
        [_counter_update(14, "36.0", planner.COUNTER_GATED)],
        elapsed_s=3600.0,
        system_watts=150.0,
        peak_w=200.0,
    )
    assert out[0].svalue == "36.0;136.0"


def test_attach_counters_leaves_a_non_counter_update_alone():
    plugin._state.dev_ids = {planner.DEVICE_SYSTEM: "dellidrac_1_system"}
    update = planner.DeviceUpdate(
        unit=2, type_name="Alert", name="System Health", nvalue=1, svalue="OK"
    )
    assert plugin.attach_counters(
        domoticz_stub.Devices, [update], elapsed_s=30.0, system_watts=150.0, peak_w=200.0
    ) == [update]


def test_attach_counters_holds_a_gated_reading_that_has_never_moved():
    plugin._state.dev_ids = {planner.DEVICE_SYSTEM: "dellidrac_1_system"}
    plugin._state.first_watts = {}
    plugin._state.moved = set()
    _seed_counter_device("dellidrac_1_system", 19, "43.0;500.0")
    args = (
        domoticz_stub.Devices,
        [_counter_update(19, "43.0", planner.COUNTER_GATED, name="FPGA Power")],
    )
    first = plugin.attach_counters(*args, elapsed_s=3600.0, system_watts=582.0, peak_w=800.0)
    second = plugin.attach_counters(*args, elapsed_s=3600.0, system_watts=582.0, peak_w=800.0)
    # The counter never advances while the reading is a static figure.
    assert first[0].svalue == "43.0;500.0"
    assert second[0].svalue == "43.0;500.0"


def test_attach_counters_starts_counting_once_a_gated_reading_moves():
    plugin._state.dev_ids = {planner.DEVICE_SYSTEM: "dellidrac_1_system"}
    plugin._state.first_watts = {}
    plugin._state.moved = set()
    _seed_counter_device("dellidrac_1_system", 14, "40.0;100.0")
    plugin.attach_counters(
        domoticz_stub.Devices,
        [_counter_update(14, "40.0", planner.COUNTER_GATED)],
        elapsed_s=3600.0,
        system_watts=150.0,
        peak_w=200.0,
    )
    out = plugin.attach_counters(
        domoticz_stub.Devices,
        [_counter_update(14, "36.0", planner.COUNTER_GATED)],
        elapsed_s=3600.0,
        system_watts=150.0,
        peak_w=200.0,
    )
    assert out[0].svalue == "36.0;136.0"


def test_attach_counters_never_gates_a_direct_counter():
    # An R750 hot spare supply can sit at exactly 5.0 W for hours. That is real standby energy.
    plugin._state.dev_ids = {planner.DEVICE_POWER: "dellidrac_1_power"}
    plugin._state.first_watts = {}
    plugin._state.moved = set()
    _seed_counter_device("dellidrac_1_power", 1, "5.0;10.0")
    out = plugin.attach_counters(
        domoticz_stub.Devices,
        [
            _counter_update(
                1, "5.0", planner.COUNTER_DIRECT, name="PS2 Status", device=planner.DEVICE_POWER
            )
        ],
        elapsed_s=3600.0,
        system_watts=461.0,
        peak_w=800.0,
    )
    assert out[0].svalue == "5.0;15.0"


def test_attach_counters_holds_a_reading_above_the_chassis_draw():
    plugin._state.dev_ids = {planner.DEVICE_SYSTEM: "dellidrac_1_system"}
    plugin._state.first_watts = {"dellidrac_1_system:19": 10.0}
    plugin._state.moved = {"dellidrac_1_system:19"}
    _seed_counter_device("dellidrac_1_system", 19, "43.0;500.0")
    out = plugin.attach_counters(
        domoticz_stub.Devices,
        [_counter_update(19, "43.0", planner.COUNTER_GATED, name="FPGA Power")],
        elapsed_s=3600.0,
        system_watts=22.0,
        peak_w=200.0,
    )
    assert out[0].svalue == "43.0;500.0"


def test_attach_counters_drops_an_update_whose_previous_value_is_unreadable():
    plugin._state.dev_ids = {planner.DEVICE_SYSTEM: "dellidrac_1_system"}
    plugin._state.first_watts = {"dellidrac_1_system:14": 10.0}
    plugin._state.moved = {"dellidrac_1_system:14"}
    _seed_counter_device("dellidrac_1_system", 14, "40.0;not-a-number")
    # Writing anything here would reset a counter whose whole contract is that it only climbs.
    assert (
        plugin.attach_counters(
            domoticz_stub.Devices,
            [_counter_update(14, "36.0", planner.COUNTER_GATED)],
            elapsed_s=3600.0,
            system_watts=150.0,
            peak_w=200.0,
        )
        == []
    )
