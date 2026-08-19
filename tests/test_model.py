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


def test_metric_id_alone_is_not_a_unique_key():
    """Captured from an OpenManage-managed server, where one report carried all of this.

    The same MetricId appears once per AGGREGATION, all at the identical timestamp, and again
    once per DEVICE. Keying on MetricId alone silently reports a minimum as if it were the
    current value, and collapses four power supplies into one.
    """
    payload = {
        "MetricValues": [
            _mv("TotalCPUPower", "100", label="PowerMetrics TotalCPUPower- Minimum (5m0s)"),
            _mv("TotalCPUPower", "140", label="PowerMetrics TotalCPUPower- Maximum (5m0s)"),
            _mv("TotalCPUPower", "106.6", label="PowerMetrics TotalCPUPower- Average (5m0s)"),
            _mv("PSUTemperatureReading", "44.9", fqdd="PSU.Slot.1", label="x Average (5m0s)"),
            _mv("PSUTemperatureReading", "46.5", fqdd="PSU.Slot.2", label="x Average (5m0s)"),
        ]
    }
    samples = model.parse_metric_report(payload)
    # The average is chosen, not the minimum that happens to come first.
    assert model.metric_value(samples, "TotalCPUPower") == 106.6
    # And the two supplies stay distinct rather than collapsing into one.
    by_device = model.metric_by_device(samples, "PSUTemperatureReading")
    assert by_device == {"PSU.Slot.1": 44.9, "PSU.Slot.2": 46.5}


def test_a_metric_with_no_aggregation_label_is_used_as_is():
    """Dell's own built-in reports carry no aggregation label, just the instantaneous value."""
    payload = {"MetricValues": [_mv("TotalCPUPower", "44.0", label=None)]}
    assert model.metric_value(model.parse_metric_report(payload), "TotalCPUPower") == 44.0


def test_an_average_is_preferred_over_min_and_max_whatever_the_order():
    for order in ([0, 1, 2], [2, 1, 0], [1, 2, 0]):
        rows = [
            _mv("P", "1", label="a Minimum (5m0s)"),
            _mv("P", "9", label="a Maximum (5m0s)"),
            _mv("P", "5", label="a Average (5m0s)"),
        ]
        payload = {"MetricValues": [rows[i] for i in order]}
        assert model.metric_value(model.parse_metric_report(payload), "P") == 5.0


def test_metric_value_returns_none_when_a_metric_spans_several_devices():
    """Ambiguous by construction: TemperatureReading covers CPU1, CPU2 and the inlet.

    Returning one of them arbitrarily would put a CPU temperature on an inlet device.
    """
    payload = {
        "MetricValues": [
            _mv("TemperatureReading", "34", fqdd="iDRAC.Embedded.1#CPU1Temp"),
            _mv("TemperatureReading", "47", fqdd="iDRAC.Embedded.1#CPU2Temp"),
        ]
    }
    assert model.metric_value(model.parse_metric_report(payload), "TemperatureReading") is None


def test_parse_metric_report_takes_the_newest_sample_per_metric():
    """A metric report is a TIME SERIES, not a snapshot.

    Dell's built-in PowerMetrics report carried 120 MetricValues: ten metrics sampled about every
    five seconds, with no aggregation labels, so the newest sample is the current value.
    """
    samples = model.parse_metric_report(load("t550", "power_metrics"))
    assert model.metric_value(samples, "TotalCPUPower") == 52.0
    assert model.metric_value(samples, "TotalMemoryPower") == 7.0
    assert model.metric_value(samples, "TotalFanPower") == 3.4
    assert model.metric_value(samples, "SystemInputPower") == 170.0
    # PCIe genuinely reads zero on this machine; zero reported IS a value, unlike an absence.
    assert model.metric_value(samples, "TotalPciePower") == 0.0


def test_parse_metric_report_survives_an_empty_or_odd_payload():
    assert model.parse_metric_report({}) == []
    assert model.parse_metric_report({"MetricValues": []}) == []
    assert model.parse_metric_report({"MetricValues": [{"MetricId": "X"}]}) == []
    assert model.parse_metric_report({"MetricValues": ["nope"]}) == []
    assert (
        model.parse_metric_report(
            {"MetricValues": [{"MetricId": "X", "MetricValue": "not-a-number"}]}
        )
        == []
    )
    assert model.metric_value([], "anything") is None
    assert model.metric_by_device([], "anything") == {}


def test_a_sample_with_no_timestamp_loses_to_one_that_has_it():
    payload = {
        "MetricValues": [
            {"MetricId": "P", "MetricValue": "1", "Timestamp": "2026-08-19T11:00:00.000Z"},
            {"MetricId": "P", "MetricValue": "2"},
        ]
    }
    assert model.metric_value(model.parse_metric_report(payload), "P") == 1.0


def _mv(metric_id, value, fqdd="PowerMetrics", label="", timestamp="2026-08-19T12:15:00.000Z"):
    node = {"MetricId": metric_id, "MetricValue": value, "Timestamp": timestamp}
    dell = {"FQDD": fqdd}
    if label is not None:
        dell["Label"] = label
    node["Oem"] = {"Dell": dell}
    return node


def test_gpu_power_and_temperature_are_read_per_device():
    """Captured from an OpenManage-managed server with seven GPUs.

    PowerConsumption is reported in MILLIWATTS, and every GPU shares the same metric id, so both
    the unit and the per-device split have to be handled or the numbers are nonsense.
    """
    samples = model.parse_metric_report(load("ome", "power_metrics"))
    power = model.metric_by_device(samples, "PowerConsumption")
    assert len(power) == 7
    # Averages, not the minimum that appears first in the payload.
    assert power["Video.Slot.10-1"] == 39100.1428571429
    assert power["Video.Slot.9-1"] == 0.0
    temps = model.metric_by_device(samples, "PrimaryTemperature")
    assert temps["Video.Slot.6-1"] == 40.0138041431262
    # Whole-system metrics still resolve to a single value despite the repeats.
    assert model.metric_value(samples, "TotalCPUPower") == 106.603223621845
    # And four power supplies stay four.
    assert len(model.metric_by_device(samples, "PSUTemperatureReading")) == 4


def test_drives_carry_the_controller_that_owns_them():
    """Dell names drives inconsistently depending on the controller.

    Measured on a real T550: the PERC H755 calls them "Solid State Disk 0:2:0", while the BOSS-S2
    boot card calls its two "SSD 0" and "SSD 1". Knowing the controller is what lets those be told
    apart, and it is already in the payload the plugin fetches.
    """
    payload = {
        "Name": "BOSS-S2",
        "StorageControllers": [{"Model": "BOSS-S2", "Manufacturer": "DELL"}],
        "Drives": [{"Id": "Disk.Direct.0-0:AHCI.SL.10-1", "Name": "SSD 0", "MediaType": "SSD"}],
    }
    drive = model.parse_drives(payload)[0]
    assert drive.controller == "BOSS-S2"
    assert drive.is_boot_card is True


def test_a_perc_controller_is_not_a_boot_card():
    payload = {
        "Name": "PERC H755 Front",
        "StorageControllers": [{"Model": "PERC H755 Front"}],
        "Drives": [{"Id": "Disk.Bay.0:x:RAID.SL.3-1", "Name": "Solid State Disk 0:2:0"}],
    }
    drive = model.parse_drives(payload)[0]
    assert drive.controller == "PERC H755 Front"
    assert drive.is_boot_card is False


def test_a_controller_with_no_name_does_not_break_drive_parsing():
    drive = model.parse_drives({"Drives": [{"Id": "X", "Name": "X"}]})[0]
    assert drive.controller is None
    assert drive.is_boot_card is False
