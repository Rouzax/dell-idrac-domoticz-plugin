import json

import config
import discovery
import health
import model
import planner
import thresholds
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
        "fan_bar_max": 6000,
        "setup_telemetry": False,
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


def test_the_inlet_sensor_is_found_under_either_model_name():
    """A T550 calls it InletTemp, an R6515 calls it SystemBoardInletTemp. Both must work."""
    for sensor_id in ("InletTemp", "SystemBoardInletTemp"):
        parts = _parts("t550")
        parts["sensors"] = dict(parts["sensors"])
        parts["sensors"].pop("InletTemp", None)
        parts["sensors"][sensor_id] = model.Sensor(
            id=sensor_id,
            name="Inlet",
            reading=25.0,
            units="Cel",
            health="OK",
            physical_context="SystemBoard",
        )
        inv = _inventory(parts)
        got = _by_unit(
            planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
        )
        assert planner.UNIT_INLET in got, f"inlet lost when the id is {sensor_id}"
        assert got[planner.UNIT_INLET].svalue == "25.0"


def test_a_nic_with_no_link_status_is_unknown_not_down():
    """A powered-off host reports LinkStatus null. Unknown must not read as a fault."""
    parts = _parts("t550")
    parts["nics"] = [model.Nic(id="NIC.Embedded.1-1-1", link_status=None, speed_mbps=0)]
    inv = _inventory(parts)
    got = [
        u
        for u in planner.plan(
            inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts
        )
        if planner.BLOCK_NICS <= u.unit < planner.BLOCK_NICS + 20
    ]
    assert got[0].nvalue == health.LEVEL_GREY
    assert got[0].svalue == "Unknown"


def test_power_state_is_a_read_only_alert_not_a_switch():
    """onCommand handles only the control units, so a Switch here would be clickable and inert.

    Alert states the word and colours the tile. GREY when off, not red: a server the user
    powered down deliberately is not a fault. Domoticz has no read-only switch type, and the
    Contact type's Open/Closed wording is hardcoded in the core (main/RFXNames.cpp).
    """
    parts = _parts("t550")
    inv = _inventory(parts)
    got = _by_unit(
        planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    )
    on = got[planner.UNIT_POWER_STATE]
    assert on.type_name == "Alert"
    assert (on.nvalue, on.svalue) == (health.LEVEL_OK, "On")

    parts["system"] = model.SystemInfo(
        power_state="Off", health="OK", boot_state=None, model="X", cpu_count=1, rollups={}
    )
    off = _by_unit(
        planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    )[planner.UNIT_POWER_STATE]
    assert (off.nvalue, off.svalue) == (health.LEVEL_GREY, "Off")


def test_temperature_devices_carry_bar_ranges_keyed_by_sensor():
    """Temperature cards read Color as an OBJECT keyed by sensor, not a bare array.

    Confirmed from the core: dzBarService.loadForKey parses Color and indexes it by sensor key
    (www/app/widgets/dzBar.js), unlike the utility card which reads a bare array. Getting the
    shape wrong yields no bar and no error.
    """
    parts = _parts("t550")
    inv = _inventory(parts)
    got = _by_unit(
        planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    )
    payload = json.loads(got[planner.UNIT_INLET].color)
    assert list(payload) == ["temp"]
    assert payload["temp"] == thresholds.bar_ranges(parts["threshold_map"]["Inlet Temp"])
    assert payload["temp"][0]["color"] == thresholds.BAR_CRITICAL


def test_a_device_without_usable_thresholds_gets_no_bar():
    """No bar is better than a guessed one, so Color stays empty."""
    parts = _parts("t550")
    parts["threshold_map"] = {}
    inv = _inventory(parts)
    got = _by_unit(
        planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    )
    assert got[planner.UNIT_INLET].color == ""


def test_power_redundancy_reads_in_plain_english():
    parts = _parts("t550")
    parts["redundancy"] = [
        model.Redundancy(
            name="System Board PS Redundancy",
            mode="N+m",
            health="OK",
            min_needed=1,
            supplies=2,
        )
    ]
    inv = _inventory(parts)
    got = _by_unit(
        planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    )
    assert got[planner.UNIT_REDUNDANCY].svalue == "Redundant, 2 supplies (1 needed)"
    assert got[planner.UNIT_REDUNDANCY].nvalue == health.LEVEL_OK


def test_a_vanished_redundancy_group_is_reported_not_left_stale():
    """Pulling a PSU EMPTIES Power.Redundancy rather than marking it Critical.

    Measured on real hardware. Looping over the empty list emitted nothing, so the tile kept its
    last value and sat green saying "N+m" at the exact moment redundancy was lost. A chassis that
    has power supplies but reports no redundancy group now says so. Grey, not red: the plugin
    cannot know why the group vanished, and System Health carries the iDRAC's own fault text.
    """
    parts = _parts("t550")
    parts["redundancy"] = []
    assert parts["psus"], "the profile must have PSUs for this to mean anything"
    inv = _inventory(parts)
    got = _by_unit(
        planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    )
    assert got[planner.UNIT_REDUNDANCY].nvalue == health.LEVEL_GREY
    assert got[planner.UNIT_REDUNDANCY].svalue == "Not reported"


def test_no_redundancy_device_on_a_chassis_with_no_power_supplies():
    """No PSUs means nothing to be redundant about, so no device rather than a grey one."""
    parts = _parts("t550")
    parts["redundancy"] = []
    parts["psus"] = []
    inv = _inventory(parts)
    got = _by_unit(
        planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    )
    assert planner.UNIT_REDUNDANCY not in got


def test_bars_appear_only_where_the_server_reports_thresholds():
    """Temperatures and fans report thresholds, so they get bars. Nothing else does.

    Percentages, PSU watts and the energy counter carry no server thresholds at all, so any
    bands there would be invented rather than reported, and they stay bare on purpose.
    """
    parts = _parts("t550")
    inv = _inventory(parts)
    updates = planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    assert {u.type_name for u in updates if u.color} == {"Temperature", "Custom"}
    fans = [
        u for u in updates if planner.BLOCK_FANS <= u.unit < planner.BLOCK_FANS + 20 and u.color
    ]
    assert fans, "the t550 profile must produce fan bars"
    # A fan is a Custom Sensor, drawn by the utility card, which needs a BARE ARRAY.
    for fan in fans:
        assert fan.color.startswith("[")
    # A temperature card needs the keyed OBJECT instead. Two shapes, same column.
    assert _by_unit(updates)[planner.UNIT_INLET].color.startswith("{")


def test_fan_bars_are_switched_off_by_setting_the_maximum_to_zero():
    parts = _parts("t550")
    inv = _inventory(parts)
    updates = planner.plan(
        inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(fan_bar_max=0), **parts
    )
    assert not [
        u for u in updates if planner.BLOCK_FANS <= u.unit < planner.BLOCK_FANS + 20 and u.color
    ]
    # Temperatures are unaffected by the fan setting.
    assert _by_unit(updates)[planner.UNIT_INLET].color


def test_a_bar_never_shows_a_synthesized_threshold_as_if_it_were_reported():
    """CPU1 reports no upper warning. describe() synthesizes one and LABELS it "(estimated)".

    A bar band carries no label, so drawing amber there would present an estimate as a reported
    limit. The band is deliberately omitted instead, which is why the description and the bar
    legitimately disagree for this sensor.
    """
    parts = _parts("t550")
    threshold = parts["threshold_map"]["CPU1 Temp"]
    assert threshold.upper_non_critical is None
    assert "(estimated)" in thresholds.describe(threshold, "C")
    bands = thresholds.bar_ranges(threshold)
    assert [b["color"] for b in bands] == [
        thresholds.BAR_CRITICAL,
        thresholds.BAR_OK,
        thresholds.BAR_CRITICAL,
    ]


def test_fans_and_uptime_get_their_icons():
    """Icons chosen by the user on the live rig. Domoticz's plugin API maps Image to the
    CustomImage column (PythonObjectEx.cpp), and apply_updates sets it only at CREATION, so a
    user who later picks a different icon keeps it."""
    parts = _parts("t550")
    inv = _inventory(parts)
    got = _by_unit(
        planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    )
    fans = [u for unit, u in got.items() if planner.BLOCK_FANS <= unit < planner.BLOCK_FANS + 20]
    assert fans, "the t550 profile must have fans for this to mean anything"
    assert all(u.image == planner.IMAGE_FAN for u in fans)
    assert got[planner.UNIT_UPTIME].image == planner.IMAGE_CLOCK
    # Nothing else is given an icon; Domoticz picks its own.
    assert got[planner.UNIT_INLET].image == 0


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


def _metrics():
    samples = model.parse_metric_report(load("t550", "power_metrics"))
    ids = {s.metric_id for s in samples}
    return {
        i: model.metric_value(samples, i) for i in ids if model.metric_value(samples, i) is not None
    }


def test_component_power_devices_are_created_from_telemetry():
    """Dell's PowerMetrics report breaks system power down by subsystem.

    Licence-gated in practice (Datacenter, or OME Advanced), so these devices exist only when
    the report is readable.
    """
    parts = _parts("t550")
    parts["metrics"] = _metrics()
    inv = _inventory(parts)
    got = _by_unit(
        planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    )
    assert got[planner.UNIT_CPU_POWER].svalue == "52.0"
    assert got[planner.UNIT_CPU_POWER].name == "CPU Power"
    assert got[planner.UNIT_CPU_POWER].type_name == "Usage"
    assert got[planner.UNIT_MEMORY_POWER].svalue == "7.0"
    assert got[planner.UNIT_STORAGE_POWER].svalue == "63.6"
    assert got[planner.UNIT_FAN_POWER].svalue == "3.4"
    # PCIe genuinely reads zero here. A reported zero is a value, not an absence.
    assert got[planner.UNIT_PCIE_POWER].svalue == "0.0"
    assert got[planner.UNIT_FPGA_POWER].svalue == "0.0"


def test_no_component_power_devices_without_telemetry():
    """Most iDRACs cannot serve this, so the devices must simply not appear."""
    parts = _parts("t550")
    parts["metrics"] = {}
    inv = _inventory(parts)
    got = _by_unit(
        planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    )
    for unit in (
        planner.UNIT_CPU_POWER,
        planner.UNIT_MEMORY_POWER,
        planner.UNIT_STORAGE_POWER,
        planner.UNIT_FAN_POWER,
        planner.UNIT_PCIE_POWER,
        planner.UNIT_FPGA_POWER,
    ):
        assert unit not in got


def test_a_metric_the_server_omits_creates_no_device():
    parts = _parts("t550")
    parts["metrics"] = {"TotalCPUPower": 44.0}
    inv = _inventory(parts)
    got = _by_unit(
        planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    )
    assert planner.UNIT_CPU_POWER in got
    assert planner.UNIT_MEMORY_POWER not in got


def test_energy_prefers_wall_draw_when_telemetry_reports_it():
    """SystemInputPower is what the wall socket delivers; the board sensor misses conversion loss.

    Measured on a T550: input 158 to 174 W against a board figure of 144 W, roughly 6 percent.
    """
    parts = _parts("t550")
    parts["metrics"] = _metrics()
    inv = _inventory(parts)
    got = _by_unit(
        planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    )
    watts = float(got[planner.UNIT_POWER].svalue.split(";")[0])
    assert watts == 170.0


def test_energy_falls_back_to_the_board_sensor_without_telemetry():
    parts = _parts("t550")
    parts["metrics"] = {}
    inv = _inventory(parts)
    got = _by_unit(
        planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    )
    watts = float(got[planner.UNIT_POWER].svalue.split(";")[0])
    assert watts == 144.0


def _ome_samples():
    return model.parse_metric_report(load("ome", "power_metrics"))


def test_gpu_devices_are_created_one_per_card():
    """From a real seven-GPU OpenManage-managed server. Power arrives in MILLIWATTS."""
    parts = _parts("t550")
    parts["metrics"] = {}
    parts["gpus"] = planner.gpu_readings(_ome_samples())
    inv = _inventory(parts)
    inv = discovery.Inventory(**{**inv.__dict__, "gpus": tuple(sorted(parts["gpus"]))})
    got = _by_unit(
        planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    )
    powers = [
        u
        for unit, u in got.items()
        if planner.BLOCK_GPU_POWER <= unit < planner.BLOCK_GPU_POWER + 20
    ]
    temps = [
        u for unit, u in got.items() if planner.BLOCK_GPU_TEMP <= unit < planner.BLOCK_GPU_TEMP + 20
    ]
    assert len(powers) == 7
    assert len(temps) == 7
    # 39100.14 mW is 39.1 W, not 39100 W.
    watts = {u.name: u.svalue for u in powers}
    assert watts["GPU Video.Slot.10-1 Power"] == "39.1"
    assert {u.type_name for u in powers} == {"Usage"}
    assert {u.type_name for u in temps} == {"Temperature"}
    assert dict((u.name, u.svalue) for u in temps)["GPU Video.Slot.6-1 Temp"] == "40.0"


def test_no_gpu_devices_without_gpu_metrics():
    parts = _parts("t550")
    parts["metrics"] = {}
    parts["gpus"] = {}
    inv = _inventory(parts)
    got = planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    assert not [u for u in got if u.unit >= planner.BLOCK_GPU_POWER]


def test_gpu_readings_converts_milliwatts_and_pairs_temperature():
    readings = planner.gpu_readings(_ome_samples())
    assert len(readings) == 7
    assert readings["Video.Slot.10-1"] == (39.1, 41.0)
    # A card reporting zero power is still a card; zero reported is a value.
    assert readings["Video.Slot.9-1"][0] == 0.0


def test_a_gpu_reporting_only_temperature_still_appears():
    """Real shape from a third server: Video.Slot.7-1 through 7-4, four GPUs in ONE slot,
    reporting PrimaryTemperature but no PowerConsumption in that report."""
    samples = [
        model.MetricSample("PrimaryTemperature", "Video.Slot.7-2", "Average", 41.0, "t"),
        model.MetricSample("PrimaryTemperature", "Video.Slot.7-3", "Average", 36.0, "t"),
        model.MetricSample("PowerConsumption", "Video.Slot.7-2", "Average", 39012.0, "t"),
    ]
    readings = planner.gpu_readings(samples)
    assert readings["Video.Slot.7-2"] == (39.0, 41.0)
    # Temperature only: the missing power is left out rather than shown as zero.
    assert readings["Video.Slot.7-3"] == (None, 36.0)
    parts = _parts("t550")
    parts["metrics"] = {}
    parts["gpus"] = readings
    inv = _inventory(parts)
    inv = discovery.Inventory(**{**inv.__dict__, "gpus": tuple(sorted(readings))})
    got = planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    gpu = [u for u in got if u.unit >= planner.BLOCK_GPU_POWER]
    # Three devices, not four: two for 7-2, temperature only for 7-3.
    assert len(gpu) == 3


def test_scientific_notation_survives_the_parser():
    """A real CPUUsage average arrived as "9.14149423131894e-13"."""
    payload = {"MetricValues": [{"MetricId": "U", "MetricValue": "9.14149423131894e-13"}]}
    assert model.metric_value(model.parse_metric_report(payload), "U") == 9.14149423131894e-13


def test_fpga_power_is_real_on_some_machines():
    """Zero on the development server, 43 W on a third machine's capture. A reported zero is a
    value, so the device appears either way; only an absent metric suppresses it."""
    parts = _parts("t550")
    parts["metrics"] = {"TotalFPGAPower": 43.0}
    inv = _inventory(parts)
    got = _by_unit(
        planner.plan(inventory=inv, alloc=planner.assign_units(inv, {}), cfg=_cfg(), **parts)
    )
    assert got[planner.UNIT_FPGA_POWER].svalue == "43.0"
    assert got[planner.UNIT_FPGA_POWER].name == "FPGA Power"
