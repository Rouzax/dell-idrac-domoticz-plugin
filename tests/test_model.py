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


def test_parse_volumes_reads_raid_type_and_health():
    volumes = model.parse_volumes(load("t550", "volumes"))
    assert len(volumes) == 2
    assert all(v.raid_type == "RAID5" for v in volumes)
    assert all(v.health == "OK" for v in volumes)
    assert all(v.id and v.name for v in volumes)


def test_parse_volumes_ignores_unexpanded_members():
    assert model.parse_volumes({"Members": [{"@odata.id": "/redfish/v1/x"}]}) == []


def test_malformed_numbers_become_none_never_zero():
    """A 0 is a real measurement; a malformed value must not masquerade as one."""
    drives = model.parse_drives(
        {"Drives": [{"Id": "D", "CapacityBytes": "lots", "PredictedMediaLifeLeftPercent": "n/a"}]}
    )
    assert drives[0].capacity_bytes is None
    assert drives[0].life_left_pct is None
    assert model.parse_system({"ProcessorSummary": {"Count": "two"}}).cpu_count == 0
    assert model.parse_nics({"Members": [{"Id": "N", "SpeedMbps": "fast"}]})[0].speed_mbps is None


def test_parse_nics_reads_link_status():
    nics = model.parse_nics(load("t550", "ethernet"))
    assert len(nics) == 2
    assert nics[0].link_status == "LinkUp"
    assert nics[0].speed_mbps == 1000
    assert nics[1].link_status == "LinkDown"


def test_a_sentinel_temperature_is_not_a_reading():
    """Measured on a powered-off PowerEdge R6515: DIMM_MAX reports -128.0, a signed-byte
    sentinel meaning "no reading". Writing it would put a permanent false value in the history."""
    s = model.parse_sensors(
        {
            "Members": [
                {
                    "Id": "Temperature.DIMM_MAX",
                    "Name": "Max DIMM Temperature",
                    "ReadingUnits": "Cel",
                    "Reading": -128.0,
                    "PhysicalContext": "MemorySubsystem",
                },
                {"Id": "InletTemp", "Name": "Inlet", "ReadingUnits": "Cel", "Reading": 30.0},
                {"Id": "Watts", "Name": "W", "ReadingUnits": "W", "Reading": -128.0},
            ]
        }
    )
    assert s["Temperature.DIMM_MAX"].reading is None
    assert s["InletTemp"].reading == 30.0
    # The sentinel rule applies to temperatures only; a negative watt reading is not our business.
    assert s["Watts"].reading == -128.0


def test_boot_progress_none_string_is_an_absence():
    """A powered-off host reports the STRING "None", which must not become device text."""
    assert model.parse_system({"BootProgress": {"LastState": "None"}}).boot_state is None
    assert (
        model.parse_system({"BootProgress": {"LastState": "OSRunning"}}).boot_state == "OSRunning"
    )


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


def test_parse_faults_reads_severity_and_message():
    payload = {
        "Members": [
            {
                "Severity": "Critical",
                "Message": "Power supply redundancy is lost.",
                "Id": "Fault_03200004_1",
            },
        ]
    }
    faults = model.parse_faults(payload)
    assert faults[0].severity == "Critical"
    assert faults[0].message == "Power supply redundancy is lost."


def test_parse_faults_skips_entries_with_no_message():
    assert model.parse_faults({"Members": [{"Severity": "Critical"}]}) == []


def test_parse_redundancy_on_the_degraded_capture_is_empty():
    """Measured: with a PSU physically absent the iDRAC EMPTIES the Redundancy array."""
    assert model.parse_redundancy(load("degraded", "power")) == []


def test_parse_redundancy_reads_a_populated_set():
    """Values measured live on the T550 after the pulled PSU was reseated.

    Both power supplies report Status.Health OK while redundancy itself reports Critical. No
    per-component status reveals this, which is the whole reason UNIT_REDUNDANCY exists.
    """
    payload = {
        "Redundancy": [
            {
                "Name": "System Board PS Redundancy",
                "Mode": "N+m",
                "MinNumNeeded": 1,
                "MaxNumSupported": 2,
                "Status": {"Health": "Critical", "State": "Enabled"},
            }
        ]
    }
    red = model.parse_redundancy(payload)
    assert len(red) == 1
    assert red[0].name == "System Board PS Redundancy"
    assert red[0].mode == "N+m"
    assert red[0].health == "Critical"


def test_parse_redundancy_skips_an_entry_with_no_name():
    assert model.parse_redundancy({"Redundancy": [{"Mode": "N+m"}]}) == []


def test_parse_metric_report_takes_the_newest_sample_per_metric():
    """A metric report is a TIME SERIES, not a snapshot.

    The live PowerMetrics report carried 120 MetricValues: ten metrics sampled about every five
    seconds. Reading it like a flat object would pick an arbitrary sample, so the newest one per
    MetricId is taken.
    """
    metrics = model.parse_metric_report(load("t550", "power_metrics"))
    assert metrics["TotalCPUPower"] == 52.0
    assert metrics["TotalMemoryPower"] == 7.0
    assert metrics["TotalFanPower"] == 3.4
    assert metrics["SystemInputPower"] == 170.0
    # PCIe genuinely reads zero on this machine; zero reported IS a value, unlike an absence.
    assert metrics["TotalPciePower"] == 0.0


def test_parse_metric_report_survives_an_empty_or_odd_payload():
    assert model.parse_metric_report({}) == {}
    assert model.parse_metric_report({"MetricValues": []}) == {}
    assert model.parse_metric_report({"MetricValues": [{"MetricId": "X"}]}) == {}
    assert model.parse_metric_report({"MetricValues": ["nope"]}) == {}
    assert (
        model.parse_metric_report(
            {"MetricValues": [{"MetricId": "X", "MetricValue": "not-a-number"}]}
        )
        == {}
    )


def test_parse_metric_report_ignores_a_sample_with_no_timestamp_ordering():
    """Timestamps are strings; ordering must not blow up when one is missing."""
    payload = {
        "MetricValues": [
            {"MetricId": "P", "MetricValue": "1", "Timestamp": "2026-08-19T11:00:00.000Z"},
            {"MetricId": "P", "MetricValue": "2"},
        ]
    }
    assert model.parse_metric_report(payload)["P"] == 1.0
