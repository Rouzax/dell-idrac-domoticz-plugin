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


def test_everything_is_sorted_for_stable_unit_allocation():
    inv = _inventory("dual")
    assert list(inv.drives) == sorted(inv.drives)
    assert list(inv.fans) == sorted(inv.fans)
