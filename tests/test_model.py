import model
from tests.fixture_loader import load


def test_parse_sensors_keys_by_id_and_reads_values():
    sensors = model.parse_sensors(load("t550", "sensors_expanded"))
    assert sensors["SystemBoardCPUUsage"].reading == 5.0
    assert sensors["SystemBoardCPUUsage"].units == "%"
    assert sensors["InletTemp"].reading == 25.0
    assert sensors["SystemBoardPwrConsumption"].units == "W"
    assert sensors["Fan.Embedded.1"].units == "RPM"


def test_parse_sensors_survives_a_missing_reading():
    payload = {"Members": [{"Id": "X", "Name": "X", "ReadingUnits": "W"}]}
    assert model.parse_sensors(payload)["X"].reading is None


def test_parse_sensors_ignores_unexpanded_members():
    """A collection fetched without $expand has members that are only links."""
    payload = {"Members": [{"@odata.id": "/redfish/v1/.../Sensors/Foo"}]}
    assert model.parse_sensors(payload) == {}


def test_parse_thermal_thresholds_keyed_by_name():
    th = model.parse_thermal_thresholds(load("t550", "thermal"))
    assert th["CPU1 Temp"].upper_critical == 98
    assert th["CPU1 Temp"].upper_non_critical is None
    assert th["System Board Fan1"].lower_critical == 480
    assert th["System Board Fan1"].lower_non_critical == 840


def test_parse_system_reads_state_and_rollups():
    info = model.parse_system(load("t550", "system"))
    assert info.power_state == "On"
    assert info.health == "OK"
    assert info.boot_state == "OSRunning"
    assert info.model == "PowerEdge T550"
    assert info.cpu_count == 1
    assert info.rollups["StorageRollupStatus"] == "OK"
    # Not-applicable rollups are dropped, not reported as a status.
    assert "CMCRollupStatus" not in info.rollups


def test_parse_power_reads_psu_input_watts():
    psus = model.parse_power(load("t550", "power"))
    assert [p.id for p in psus] == ["PSU.0", "PSU.1"]
    assert [p.name for p in psus] == ["PS1 Status", "PS2 Status"]
    assert psus[0].input_watts == 69.5
    assert psus[0].health == "OK"


def test_parse_drives_reads_health_signals():
    drives = model.parse_drives(load("dual", "storage_expanded"))
    assert len(drives) == 24
    by_id = {d.id: d for d in drives}
    bay5 = next(d for d in drives if d.id.startswith("Disk.Bay.5"))
    assert bay5.failure_predicted is True
    bay9 = next(d for d in drives if d.id.startswith("Disk.Bay.9"))
    assert bay9.life_left_pct == 4
    assert all(d.media_type in ("SSD", "HDD") for d in by_id.values())


def test_parse_nics_reads_link_status():
    nics = model.parse_nics(load("t550", "ethernet"))
    assert len(nics) == 2
    assert nics[0].link_status == "LinkUp"
    assert nics[0].speed_mbps == 1000
    assert nics[1].link_status == "LinkDown"


def test_parse_chassis_reads_intrusion_and_identify():
    info = model.parse_chassis(load("t550", "chassis"))
    assert info.intrusion == "Normal"
    assert info.identify_on is False


def test_parse_chassis_tolerates_a_missing_security_block():
    info = model.parse_chassis({})
    assert info.intrusion is None
    assert info.identify_on is False


def test_parse_dell_attributes():
    attrs = model.parse_dell_attributes(load("t550", "dell_attributes"))
    assert attrs.accumulative_power == 699375
    assert attrs.peak_watts == 508
    assert attrs.powered_on_seconds == 1486865
