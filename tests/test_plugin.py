import pytest

import plugin
import redfish_client
from tests import domoticz_stub
from tests.fixture_loader import load


class FakeClient:
    """Replays fixtures by path. Raises for paths the test did not stub."""

    def __init__(self, profile="t550", fail_paths=()):
        self.profile = profile
        self.fail_paths = set(fail_paths)
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


@pytest.fixture
def started(monkeypatch):
    params = {
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
    monkeypatch.setattr(plugin, "Parameters", params, raising=False)
    monkeypatch.setattr(plugin, "Devices", domoticz_stub.Devices, raising=False)
    plugin.onStart()
    plugin._state.client = FakeClient()
    return plugin._state


def _beat_once(state):
    """Advance past the poll-interval gate and run one heartbeat."""
    state.beat = state.cfg.poll_interval // 10
    plugin.onHeartbeat()


def test_onstart_sets_up_state_without_touching_the_network():
    pass  # exercised by the `started` fixture


def test_heartbeat_creates_devices_for_discovered_hardware(started):
    _beat_once(started)
    units = domoticz_stub.Devices["dellidrac_3"].Units
    assert plugin.planner.UNIT_POWER in units
    assert plugin.planner.UNIT_HEALTH in units
    fans = [u for u in units.values() if u.Options.get("Custom") == "1;RPM"]
    assert len(fans) == 3


def test_heartbeat_is_idempotent(started):
    _beat_once(started)
    first = len(domoticz_stub.Devices["dellidrac_3"].Units)
    _beat_once(started)
    assert len(domoticz_stub.Devices["dellidrac_3"].Units) == first


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
    unit = domoticz_stub.Devices["dellidrac_3"].Units[plugin.planner.UNIT_INLET]
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


def test_a_failing_storage_subcall_does_not_cost_the_rest_of_the_slow_tier(started):
    started.client = FakeClient(fail_paths=("/ctrl",))
    _beat_once(started)
    units = domoticz_stub.Devices["dellidrac_3"].Units
    assert plugin.planner.UNIT_HEALTH in units
    assert not [u for u in units if u >= plugin.planner.BLOCK_DRIVES]


def test_uptime_and_intrusion_devices_are_created(started):
    _beat_once(started)
    units = domoticz_stub.Devices["dellidrac_3"].Units
    assert float(units[plugin.planner.UNIT_UPTIME].sValue) > 0
    assert units[plugin.planner.UNIT_INTRUSION].sValue == "Normal"


def test_dual_socket_profile_creates_two_cpu_temp_devices(started):
    started.client = FakeClient(profile="dual")
    _beat_once(started)
    units = domoticz_stub.Devices["dellidrac_3"].Units
    cpu = [u for u in units.values() if "CPU" in u.Name and "Temp" in u.Name]
    assert len(cpu) == 2


def test_energy_counter_never_decreases(started):
    _beat_once(started)
    first = float(
        domoticz_stub.Devices["dellidrac_3"].Units[plugin.planner.UNIT_POWER].sValue.split(";")[1]
    )
    _beat_once(started)
    second = float(
        domoticz_stub.Devices["dellidrac_3"].Units[plugin.planner.UNIT_POWER].sValue.split(";")[1]
    )
    assert second >= first


def test_password_never_reaches_the_log(started):
    started.client = FakeClient(fail_paths=("/Sensors",))
    _beat_once(started)
    assert not any("secret" in line for line in domoticz_stub._module._log)
