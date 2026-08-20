import discovery
import model
from tests.fixture_loader import load


def _inventory(profile):
    return discovery.discover(
        sensors=model.parse_sensors(load(profile, "sensors_expanded")),
        psus=model.parse_power(load(profile, "power")),
        drives=model.parse_drives(load(profile, "storage_expanded")),
        volumes=model.parse_volumes(load(profile, "volumes")),
        nics=model.parse_nics(load(profile, "ethernet")),
    )


def test_single_socket_machine_finds_one_cpu_temp():
    inv = _inventory("t550")
    assert inv.cpu_temps == ("CPU1Temp",)


def test_dual_socket_machine_finds_two_cpu_temps():
    inv = _inventory("dual")
    assert inv.cpu_temps == ("CPU1Temp", "CPU2Temp")


def test_fans_are_discovered_despite_the_numbering_gap():
    inv = _inventory("t550")
    assert inv.fans == ("Fan.Embedded.1", "Fan.Embedded.3", "Fan.Embedded.4")


def test_dual_profile_finds_six_fans():
    assert len(_inventory("dual").fans) == 6


def test_dimm_max_detected_when_present():
    assert _inventory("t550").dimm_max == "Temperature.DIMM_MAX"


def test_dimm_max_absent_is_none():
    inv = discovery.discover(sensors={}, psus=[], drives=[], volumes=[], nics=[])
    assert inv.dimm_max is None


def test_counts_scale_with_hardware():
    t550 = _inventory("t550")
    dual = _inventory("dual")
    assert len(t550.drives) == 8
    assert len(dual.drives) == 24
    assert len(t550.psus) == 2
    assert len(t550.volumes) == 2
    assert len(t550.nics) == 2


def test_drive_order_is_natural_not_lexicographic():
    """Bay 2 must precede bay 10. Unit numbers follow this order and are persisted for good."""
    bays = [d.split(":")[0].replace("Disk.Bay.", "") for d in _inventory("dual").drives]
    assert bays == [str(n) for n in range(24)]


def test_order_is_deterministic_across_repeated_discovery():
    first, second = _inventory("dual"), _inventory("dual")
    assert first.drives == second.drives
    assert first.fans == second.fans


def _sensor(sid, units, ctx, reading=40.0, name=None):
    return model.Sensor(
        id=sid, name=name or sid, reading=reading, units=units, health="OK", physical_context=ctx
    )


def test_gpu_temperature_sensors_are_discovered_by_physical_context():
    """Telemetry is licence-gated, but a GPU's temperature is also in the plain Sensors
    collection tagged PhysicalContext "GPU". A real PowerEdge R750 reports a card at 74 C there
    while its telemetry reports no GPU at all.

    Matched on the Redfish PhysicalContext enum rather than an id prefix, for the same reason
    fans are matched on their unit: an id rule works on one vendor's naming and no other.
    """
    sensors = {
        "GPUTemp8": _sensor("GPUTemp8", "Cel", "GPU", 74.0),
        "SystemBoardSLOT5Temp": _sensor("SystemBoardSLOT5Temp", "Cel", "GPU", 35.0),
        "CPU1Temp": _sensor("CPU1Temp", "Cel", "CPU"),
        "Fan.Embedded.1": _sensor("Fan.Embedded.1", "RPM", "SystemBoard", 6000.0),
    }
    inv = discovery.discover(sensors=sensors, psus=[], drives=[], volumes=[], nics=[])
    assert inv.gpu_temps == ("GPUTemp8", "SystemBoardSLOT5Temp")
    # And they must not be mistaken for CPU temperatures.
    assert inv.cpu_temps == ("CPU1Temp",)


def test_a_gpu_sensor_that_is_not_a_temperature_is_not_a_gpu_temp():
    sensors = {"GPUPower1": _sensor("GPUPower1", "W", "GPU", 44.0)}
    inv = discovery.discover(sensors=sensors, psus=[], drives=[], volumes=[], nics=[])
    assert inv.gpu_temps == ()


def _psu_sensor(sid, reading):
    return model.Sensor(
        id=sid, name=sid, reading=reading, units="W", health="OK", physical_context="PowerSupply"
    )


def test_power_supplies_reporting_both_sides_are_discovered_as_efficiency_pairs():
    """A supply that reports AC in and DC out lets efficiency be computed. Both halves must be
    present: one alone says nothing about the conversion loss."""
    sensors = {
        "PSU.Slot.1_InputPower": _psu_sensor("PSU.Slot.1_InputPower", 464.5),
        "PSU.Slot.1_OutputPower": _psu_sensor("PSU.Slot.1_OutputPower", 433.5),
        "PSU.Slot.2_InputPower": _psu_sensor("PSU.Slot.2_InputPower", 5.0),
        "PSU.Slot.2_OutputPower": _psu_sensor("PSU.Slot.2_OutputPower", 0.0),
    }
    inv = discovery.discover(sensors=sensors, psus=[], drives=[], volumes=[], nics=[])
    assert inv.psu_efficiency == ("PSU.Slot.1", "PSU.Slot.2")


def test_a_supply_reporting_only_one_side_is_not_an_efficiency_pair():
    sensors = {"PSU.Slot.1_InputPower": _psu_sensor("PSU.Slot.1_InputPower", 100.0)}
    inv = discovery.discover(sensors=sensors, psus=[], drives=[], volumes=[], nics=[])
    assert inv.psu_efficiency == ()
