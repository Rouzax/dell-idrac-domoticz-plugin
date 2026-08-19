import config
import discovery
import health
import model
import planner
from tests.fixture_loader import load


def _parts(profile):
    return {
        "sensors": model.parse_sensors(load(profile, "sensors_expanded")),
        "system": model.parse_system(load(profile, "system")),
        "psus": model.parse_power(load(profile, "power")),
        "drives": model.parse_drives(load(profile, "storage_expanded")),
        "volumes": model.parse_volumes(load(profile, "volumes")),
        "nics": model.parse_nics(load(profile, "ethernet")),
        "threshold_map": model.parse_thermal_thresholds(load(profile, "thermal")),
        "chassis": model.parse_chassis(load(profile, "chassis")),
        "dell_attrs": model.parse_dell_attributes(load(profile, "dell_attributes")),
    }


def _inventory(parts):
    # discover() takes only the collections; chassis and dell_attrs are not inventory.
    return discovery.discover(
        sensors=parts["sensors"],
        psus=parts["psus"],
        drives=parts["drives"],
        volumes=parts["volumes"],
        nics=parts["nics"],
    )


def test_units_are_assigned_inside_their_blocks():
    parts = _parts("t550")
    alloc = planner.assign_units(_inventory(parts), {})
    assert alloc["CPU1Temp"] == planner.BLOCK_TEMPS
    assert alloc["Fan.Embedded.1"] == planner.BLOCK_FANS
    assert alloc["Fan.Embedded.3"] == planner.BLOCK_FANS + 1
    assert min(alloc[d] for d in alloc if d.startswith("Disk.Bay.")) >= planner.BLOCK_DRIVES


def test_existing_assignments_are_never_reshuffled():
    parts = _parts("t550")
    inv = _inventory(parts)
    first = planner.assign_units(inv, {})
    # A fan disappears; the survivors must keep their units.
    reduced = discovery.Inventory(
        cpu_temps=inv.cpu_temps,
        fans=("Fan.Embedded.1", "Fan.Embedded.4"),
        dimm_max=inv.dimm_max,
        psus=inv.psus,
        drives=inv.drives,
        volumes=inv.volumes,
        nics=inv.nics,
    )
    second = planner.assign_units(reduced, dict(first))
    assert second["Fan.Embedded.4"] == first["Fan.Embedded.4"]
    # And the vacated unit is not handed to something else.
    assert second["Fan.Embedded.1"] == first["Fan.Embedded.1"]


def test_block_exhaustion_skips_the_overflow_instead_of_failing_the_whole_poll():
    """One item that does not fit must not cost every other device its update.

    Blocks are fixed ranges and a unit is never freed, so a long-lived install can exhaust one
    through ordinary component churn. Raising here would lose the entire poll.
    """
    sensors = {}
    for i in range(1, 22):
        sensors[f"Fan.Embedded.{i}"] = model.Sensor(
            id=f"Fan.Embedded.{i}",
            name=f"Fan{i}",
            reading=1000.0,
            units="RPM",
            health="OK",
            physical_context="SystemBoard",
        )
    inv = discovery.discover(sensors=sensors, psus=[], drives=[], volumes=[], nics=[])
    alloc = planner.assign_units(inv, {})
    assert planner.unassigned(inv, alloc) == ("Fan.Embedded.21",)
    parts = _parts("t550")
    parts["sensors"] = sensors
    updates = planner.plan(inventory=inv, alloc=alloc, cfg=_cfg(), **parts)
    fans = [u for u in updates if planner.BLOCK_FANS <= u.unit < planner.BLOCK_FANS + 20]
    assert len(fans) == 20
    assert updates


def test_nothing_is_unassigned_on_a_normal_chassis():
    parts = _parts("dual")
    inv = _inventory(parts)
    assert planner.unassigned(inv, planner.assign_units(inv, {})) == ()


def test_a_new_item_takes_the_next_free_unit_in_its_block():
    inv = discovery.Inventory(fans=("Fan.Embedded.1", "Fan.Embedded.9"))
    alloc = planner.assign_units(inv, {"Fan.Embedded.1": planner.BLOCK_FANS})
    assert alloc["Fan.Embedded.9"] == planner.BLOCK_FANS + 1


def _cfg(**kw):
    base = {
        "address": "h",
        "username": "u",
        "password": "p",
        "allow_control": False,
        "allow_hard_power": False,
        "poll_interval": 30,
        "slow_every": 10,
        "enable_drives": True,
        "enable_volumes": True,
        "enable_nics": True,
        "enable_psus": True,
        "drive_life_floor": 10,
        "verify_tls": False,
        "request_timeout": 30,
        "debug_level": 0,
    }
    base.update(kw)
    return config.PluginConfig(**base)


def _plan(profile, cfg=None):
    parts = _parts(profile)
    inv = _inventory(parts)
    alloc = planner.assign_units(inv, {})
    return planner.plan(inventory=inv, alloc=alloc, cfg=cfg or _cfg(), **parts)


def _by_unit(updates):
    return {u.unit: u for u in updates}


def test_core_devices_are_always_planned():
    got = _by_unit(_plan("t550"))
    assert got[planner.UNIT_POWER].type_name == "kWh"
    assert got[planner.UNIT_POWER].options == {"EnergyMeterMode": "0"}
    assert got[planner.UNIT_HEALTH].type_name == "Alert"
    assert got[planner.UNIT_CPU_USAGE].svalue == "5.0"
    assert got[planner.UNIT_INLET].svalue == "25.0"


def test_power_svalue_is_power_semicolon_energy_in_wh():
    got = _by_unit(_plan("t550"))
    power, energy_wh = got[planner.UNIT_POWER].svalue.split(";")
    assert float(power) == 144.0
    assert float(energy_wh) >= 0


def test_single_socket_plans_one_cpu_temp_and_dual_plans_two():
    single = [u for u in _plan("t550") if u.name.startswith("CPU") and "Temp" in u.name]
    dual = [u for u in _plan("dual") if u.name.startswith("CPU") and "Temp" in u.name]
    assert len(single) == 1
    assert len(dual) == 2


def test_fan_devices_carry_rpm_units_and_threshold_description():
    fans = [u for u in _plan("t550") if u.type_name == "Custom" and "Fan" in u.name]
    assert len(fans) == 3
    assert fans[0].options == {"Custom": "1;RPM"}
    assert "critical below 480 RPM" in fans[0].description


def test_temperature_description_carries_the_estimated_warn_band():
    got = _by_unit(_plan("t550"))
    cpu = next(u for u in _plan("t550") if "CPU" in u.name and "Temp" in u.name)
    assert "critical above 98 C" in cpu.description
    assert "estimated" in cpu.description.lower()
    assert got[planner.UNIT_INLET].type_name == "Temperature"


def test_drive_devices_are_planned_per_disk_and_reflect_health():
    updates = _plan("dual")
    drives = [u for u in updates if planner.BLOCK_DRIVES <= u.unit < planner.BLOCK_DRIVES + 100]
    assert len(drives) == 24
    assert any(u.nvalue == health.LEVEL_ORANGE for u in drives)


def test_disabling_a_block_removes_those_devices():
    updates = _plan("dual", cfg=_cfg(enable_drives=False))
    assert not [u for u in updates if planner.BLOCK_DRIVES <= u.unit < planner.BLOCK_DRIVES + 100]


def test_updates_are_sorted_by_unit_so_creation_order_matches_layout():
    units = [u.unit for u in _plan("t550")]
    assert units == sorted(units)


def test_uptime_is_planned_in_hours():
    got = _by_unit(_plan("t550"))
    # 1486865 s / 3600 = 413.0 h
    assert got[planner.UNIT_UPTIME].type_name == "Custom"
    assert got[planner.UNIT_UPTIME].options == {"Custom": "1;h"}
    assert float(got[planner.UNIT_UPTIME].svalue) == 413.0


def test_intrusion_is_planned_as_an_alert():
    got = _by_unit(_plan("t550"))
    assert got[planner.UNIT_INTRUSION].type_name == "Alert"
    assert got[planner.UNIT_INTRUSION].nvalue == health.LEVEL_OK
    assert got[planner.UNIT_INTRUSION].svalue == "Normal"


def test_a_tripped_intrusion_sensor_goes_red():
    parts = _parts("t550")
    parts["chassis"] = model.ChassisInfo(intrusion="HardwareIntrusion", identify_on=False)
    inv = _inventory(parts)
    got = _by_unit(
        planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    )
    assert got[planner.UNIT_INTRUSION].nvalue == health.LEVEL_RED


def test_uptime_and_intrusion_are_omitted_when_not_reported():
    parts = _parts("t550")
    parts["chassis"] = model.ChassisInfo(intrusion=None, identify_on=False)
    parts["dell_attrs"] = model.DellAttrs(
        accumulative_power=None, peak_watts=None, powered_on_seconds=None
    )
    inv = _inventory(parts)
    got = _by_unit(
        planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    )
    assert planner.UNIT_UPTIME not in got
    assert planner.UNIT_INTRUSION not in got


def test_a_missing_sensor_does_not_emit_a_zero_reading():
    parts = _parts("t550")
    parts["sensors"] = {k: v for k, v in parts["sensors"].items() if k != "InletTemp"}
    inv = _inventory(parts)
    updates = planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    assert planner.UNIT_INLET not in _by_unit(updates)


def test_redundancy_device_is_planned_when_reported():
    parts = _parts("t550")
    parts["redundancy"] = [
        model.Redundancy(name="System Board PS Redundancy", mode="N+m", health="Critical")
    ]
    inv = _inventory(parts)
    got = _by_unit(
        planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    )
    assert got[planner.UNIT_REDUNDANCY].type_name == "Alert"
    assert got[planner.UNIT_REDUNDANCY].nvalue == health.LEVEL_RED


def test_no_redundancy_device_when_the_chassis_reports_none():
    parts = _parts("t550")
    parts["redundancy"] = []
    inv = _inventory(parts)
    got = _by_unit(
        planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    )
    assert planner.UNIT_REDUNDANCY not in got


def test_fault_messages_replace_bare_subsystem_names_in_system_health():
    """A latched rollup with no unhealthy component is unreadable without the fault text."""
    parts = _parts("degraded")
    parts["faults"] = [model.Fault(severity="Critical", message="Power supply redundancy is lost.")]
    inv = _inventory(parts)
    got = _by_unit(
        planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    )
    text = got[planner.UNIT_HEALTH].svalue
    assert "Power supply redundancy is lost." in text
    assert got[planner.UNIT_HEALTH].nvalue == health.LEVEL_RED


def test_system_health_falls_back_to_subsystem_names_without_faults():
    parts = _parts("degraded")
    parts["faults"] = []
    inv = _inventory(parts)
    got = _by_unit(
        planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    )
    assert "PS" in got[planner.UNIT_HEALTH].svalue
