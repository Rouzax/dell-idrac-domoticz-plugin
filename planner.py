"""Unit allocation and the ordered list of device updates. Pure."""

import json
from dataclasses import dataclass, field

import health
import thresholds

UNIT_POWER = 1
UNIT_HEALTH = 2
UNIT_POWER_STATE = 3
UNIT_INLET = 4
UNIT_EXHAUST = 5
UNIT_CPU_USAGE = 6
UNIT_MEM_USAGE = 7
UNIT_IO_USAGE = 8
UNIT_SYS_USAGE = 9
UNIT_UPTIME = 10
UNIT_BOOT = 11
UNIT_INTRUSION = 12
UNIT_REDUNDANCY = 13

# Per-subsystem power from Dell's PowerMetrics telemetry report. Separate constants rather than a
# block, because each is a FIXED slot tied to one metric: a stored unit number must always mean
# the same thing. Licence-gated in practice, so these devices simply do not appear on most iDRACs.
UNIT_CPU_POWER = 14
UNIT_MEMORY_POWER = 15
UNIT_STORAGE_POWER = 16
UNIT_FAN_POWER = 17
UNIT_PCIE_POWER = 18

# Domoticz built-in icon ids. The plugin API's Image= sets the CustomImage column
# (hardware/plugins/PythonObjectEx.cpp), and domoticz_api applies it only when a unit is CREATED,
# so a user who later picks a different icon keeps it.
IMAGE_FAN = 7
IMAGE_CLOCK = 21

BLOCK_TEMPS = 20
BLOCK_FANS = 40
BLOCK_PSUS = 60
BLOCK_VOLUMES = 70
BLOCK_NICS = 80
BLOCK_DRIVES = 100
BLOCK_CONTROL = 200

_BLOCK_LIMITS = {
    BLOCK_TEMPS: 20,
    BLOCK_FANS: 20,
    BLOCK_PSUS: 10,
    BLOCK_VOLUMES: 10,
    BLOCK_NICS: 20,
    BLOCK_DRIVES: 100,
}


@dataclass
class DeviceUpdate:
    unit: int
    type_name: str
    name: str
    nvalue: int
    svalue: str
    options: dict = field(default_factory=dict)
    description: str = ""
    # Domoticz bar ranges, written to the device's Color field. Empty means no bar.
    color: str = ""
    image: int = 0
    switchtype: int = 0


def _assign_block(ids, base: int, alloc: dict, taken: set) -> None:
    limit = _BLOCK_LIMITS[base]
    for resource_id in ids:
        if resource_id in alloc:
            continue
        for offset in range(limit):
            candidate = base + offset
            if candidate not in taken:
                alloc[resource_id] = candidate
                taken.add(candidate)
                break


def unassigned(inventory, alloc: dict) -> tuple:
    """Resource ids discovery found that allocation could not place.

    Each block is a fixed range and a unit is never freed once taken, so a long-lived install with
    enough component churn can exhaust one. plan() skips these rather than failing the whole poll,
    and the caller reports them so the gap is visible instead of silent.
    """
    wanted = [
        *inventory.cpu_temps,
        *([inventory.dimm_max] if inventory.dimm_max else []),
        *inventory.fans,
        *inventory.psus,
        *inventory.volumes,
        *inventory.nics,
        *inventory.drives,
    ]
    return tuple(rid for rid in wanted if rid not in alloc)


def assign_units(inventory, alloc: dict) -> dict:
    out = dict(alloc)
    taken = set(out.values())
    temps = list(inventory.cpu_temps)
    if inventory.dimm_max:
        temps.append(inventory.dimm_max)
    _assign_block(temps, BLOCK_TEMPS, out, taken)
    _assign_block(inventory.fans, BLOCK_FANS, out, taken)
    _assign_block(inventory.psus, BLOCK_PSUS, out, taken)
    _assign_block(inventory.volumes, BLOCK_VOLUMES, out, taken)
    _assign_block(inventory.nics, BLOCK_NICS, out, taken)
    _assign_block(inventory.drives, BLOCK_DRIVES, out, taken)
    return out


_PCT_UNITS = {
    UNIT_CPU_USAGE: ("SystemBoardCPUUsage", "CPU Usage"),
    UNIT_MEM_USAGE: ("SystemBoardMEMUsage", "Memory Usage"),
    UNIT_IO_USAGE: ("SystemBoardIOUsage", "I/O Usage"),
    UNIT_SYS_USAGE: ("SystemBoardSYSUsage", "System Usage"),
}

# The sensor Id for the same physical probe DIFFERS BETWEEN MODELS. Measured: a PowerEdge T550
# calls it "InletTemp" while an R6515 calls it "SystemBoardInletTemp". A single hardcoded id
# silently loses the reading on half the fleet, so each slot accepts the known aliases in order.
# Append only, and never repoint a slot at a different metric. GPU power lives in separate
# telemetry reports (GPUSubsystemPower, GPUMetrics) that need their own switch, so it is not here.
_POWER_METRIC_UNITS = (
    (UNIT_CPU_POWER, "TotalCPUPower", "CPU Power"),
    (UNIT_MEMORY_POWER, "TotalMemoryPower", "Memory Power"),
    (UNIT_STORAGE_POWER, "TotalStoragePower", "Storage Power"),
    (UNIT_FAN_POWER, "TotalFanPower", "Fan Power"),
    (UNIT_PCIE_POWER, "TotalPciePower", "PCIe Power"),
)

_TEMP_UNITS = {
    UNIT_INLET: (("InletTemp", "SystemBoardInletTemp"), "Inlet Temp"),
    UNIT_EXHAUST: (("SystemBoardExhaustTemp", "ExhaustTemp"), "Exhaust Temp"),
}


def _first_present(sensors, ids):
    for sensor_id in ids:
        sensor = sensors.get(sensor_id)
        if sensor is not None and sensor.reading is not None:
            return sensor
    return None


def _fmt_reading(value: float) -> str:
    return str(value)


def _temp_bar(threshold) -> str:
    """A temperature card reads Color as an object KEYED BY SENSOR, not as a bare array.

    Verified against the core: dzBarService.loadForKey indexes the parsed Color by sensor key
    (www/app/widgets/dzBar.js), where the utility card's getBarRanges expects a bare array. The
    wrong shape produces no bar and no error, so it would fail silently.
    """
    bands = thresholds.bar_ranges(threshold)
    if not bands:
        return ""
    return json.dumps({"temp": bands}, separators=(",", ":"))


def _fan_bar(threshold, axis_max) -> str:
    """A fan is a Custom Sensor, which the UTILITY card renders, so Color is a BARE ARRAY.

    Temperature cards want an object keyed by sensor instead. Two different shapes for the same
    column, confirmed from the core: dzUtilityWidget.getBarRanges requires the string to start
    with "[", while dzBarService.loadForKey requires "{". The wrong one silently draws nothing.
    """
    bands = thresholds.bar_ranges_floor(threshold, axis_max)
    if not bands:
        return ""
    return json.dumps(bands, separators=(",", ":"))


def _temp_update(unit, sensor, name, threshold_map) -> DeviceUpdate:
    threshold = threshold_map.get(sensor.name)
    return DeviceUpdate(
        unit=unit,
        type_name="Temperature",
        name=name,
        nvalue=0,
        svalue=_fmt_reading(sensor.reading),
        description=thresholds.describe(threshold, "C"),
        color=_temp_bar(threshold),
    )


# Dell reports the intrusion sensor as a plain string, not a Status block.
_INTRUSION_OK = {"Normal"}


def plan(
    sensors,
    system,
    chassis,
    dell_attrs,
    psus,
    drives,
    volumes,
    nics,
    threshold_map,
    inventory,
    alloc,
    cfg,
    energy_wh: float = 0.0,
    faults: list | None = None,
    redundancy: list | None = None,
    metrics: dict | None = None,
) -> list:
    faults = faults or []
    redundancy = redundancy or []
    metrics = metrics or {}
    out = []

    # Prefer what the wall socket actually delivers. SystemBoardPwrConsumption misses the power
    # supplies' own conversion loss: measured on a T550, input ran 158 to 174 W against a board
    # figure of 144 W. Telemetry is licence-gated, so the board sensor remains the fallback and
    # is what most installs will use.
    watts = metrics.get("SystemInputPower")
    if watts is None:
        board = sensors.get("SystemBoardPwrConsumption")
        watts = board.reading if board is not None else None
    if watts is not None:
        out.append(
            DeviceUpdate(
                unit=UNIT_POWER,
                type_name="kWh",
                name="Server Power",
                nvalue=0,
                svalue=f"{watts};{energy_wh}",
                options={"EnergyMeterMode": "0"},
            )
        )

    for unit, metric_id, name in _POWER_METRIC_UNITS:
        value = metrics.get(metric_id)
        if value is None:
            continue
        out.append(
            DeviceUpdate(
                unit=unit,
                type_name="Usage",
                name=name,
                nvalue=0,
                # Telemetry values carry float32 noise, e.g. storage power arrives as
                # "63.600002". A tenth of a watt is well past anything meaningful here.
                svalue=_fmt_reading(round(value, 1)),
            )
        )

    level, text = health.system_health(system.health, system.rollups)
    # Dell rollups latch onto faults, so a red level often has no unhealthy component behind it.
    # When the iDRAC states a reason, show the reason instead of a list of subsystem initials.
    messages = [f.message for f in faults if f.message]
    if messages and level not in (health.LEVEL_OK, health.LEVEL_GREY):
        joined = "; ".join(messages)
        # Domoticz sValue is VARCHAR(200). Mark a cut so a truncated fault cannot be mistaken
        # for a complete one.
        text = joined if len(joined) <= 200 else joined[:197] + "..."
    out.append(
        DeviceUpdate(
            unit=UNIT_HEALTH, type_name="Alert", name="System Health", nvalue=level, svalue=text
        )
    )

    if system.power_state is not None:
        # Read-only. onCommand handles only the control units, so a Switch here would be clickable
        # and inert, and Domoticz has no read-only switch type: Contact reports Open/Closed, wording
        # hardcoded in the core (main/RFXNames.cpp), which is wrong for a server. An Alert states
        # the word Redfish reported and colours the tile. GREY when off, never red, because a
        # server the user powered down deliberately is not a fault.
        out.append(
            DeviceUpdate(
                unit=UNIT_POWER_STATE,
                type_name="Alert",
                name="Power State",
                nvalue=health.LEVEL_OK if system.power_state == "On" else health.LEVEL_GREY,
                svalue=system.power_state,
            )
        )

    for unit, (sensor_ids, name) in _TEMP_UNITS.items():
        sensor = _first_present(sensors, sensor_ids)
        if sensor is not None:
            out.append(_temp_update(unit, sensor, name, threshold_map))

    for unit, (sensor_id, name) in _PCT_UNITS.items():
        sensor = sensors.get(sensor_id)
        if sensor is not None and sensor.reading is not None:
            out.append(
                DeviceUpdate(
                    unit=unit,
                    type_name="Percentage",
                    name=name,
                    nvalue=0,
                    svalue=_fmt_reading(sensor.reading),
                )
            )

    if system.boot_state:
        out.append(
            DeviceUpdate(
                unit=UNIT_BOOT,
                type_name="Text",
                name="Boot Status",
                nvalue=0,
                svalue=system.boot_state,
            )
        )

    if dell_attrs.powered_on_seconds is not None:
        out.append(
            DeviceUpdate(
                unit=UNIT_UPTIME,
                type_name="Custom",
                name="Uptime",
                nvalue=0,
                svalue=str(round(dell_attrs.powered_on_seconds / 3600.0, 1)),
                options={"Custom": "1;h"},
                image=IMAGE_CLOCK,
            )
        )

    if chassis.intrusion is not None:
        tripped = chassis.intrusion not in _INTRUSION_OK
        out.append(
            DeviceUpdate(
                unit=UNIT_INTRUSION,
                type_name="Alert",
                name="Chassis Intrusion",
                nvalue=health.LEVEL_RED if tripped else health.LEVEL_OK,
                svalue=chassis.intrusion,
            )
        )

    # Only the first group is reported; a chassis exposing several loses the rest.
    redundancy_state = None
    if redundancy:
        redundancy_state = health.redundancy_health(redundancy[0])
    elif psus:
        # Pulling a supply EMPTIES this list rather than marking it Critical, measured on real
        # hardware. Emitting nothing left the tile showing its last value, so it sat green
        # claiming redundancy at the moment redundancy was lost. Grey rather than red because
        # the plugin cannot know WHY the group vanished; System Health carries the fault text.
        redundancy_state = (health.LEVEL_GREY, "Not reported")
    if redundancy_state is not None:
        level, text = redundancy_state
        out.append(
            DeviceUpdate(
                unit=UNIT_REDUNDANCY,
                type_name="Alert",
                name="Power Redundancy",
                nvalue=level,
                svalue=text,
            )
        )

    for sensor_id in inventory.cpu_temps:
        sensor = sensors[sensor_id]
        unit = alloc.get(sensor_id)
        if sensor.reading is None or unit is None:
            continue
        out.append(_temp_update(unit, sensor, sensor.name, threshold_map))

    if inventory.dimm_max:
        sensor = sensors[inventory.dimm_max]
        unit = alloc.get(inventory.dimm_max)
        if sensor.reading is not None and unit is not None:
            out.append(_temp_update(unit, sensor, "Max DIMM Temp", threshold_map))

    for sensor_id in inventory.fans:
        sensor = sensors[sensor_id]
        unit = alloc.get(sensor_id)
        if sensor.reading is None or unit is None:
            continue
        out.append(
            DeviceUpdate(
                unit=unit,
                type_name="Custom",
                name=sensor.name,
                nvalue=0,
                svalue=_fmt_reading(sensor.reading),
                options={"Custom": "1;RPM"},
                image=IMAGE_FAN,
                description=thresholds.describe(threshold_map.get(sensor.name), "RPM"),
                color=_fan_bar(threshold_map.get(sensor.name), cfg.fan_bar_max),
            )
        )

    if cfg.enable_psus:
        for psu in psus:
            unit = alloc.get(psu.id)
            if psu.input_watts is None or unit is None:
                continue
            _, text = health.simple_health(psu.health, "OK")
            out.append(
                DeviceUpdate(
                    unit=unit,
                    type_name="Usage",
                    name=psu.name,
                    nvalue=0,
                    svalue=_fmt_reading(psu.input_watts),
                    description=text,
                )
            )

    if cfg.enable_volumes:
        for volume in volumes:
            unit = alloc.get(volume.id)
            if unit is None:
                continue
            level, text = health.simple_health(volume.health, volume.raid_type or "OK")
            out.append(
                DeviceUpdate(
                    unit=unit,
                    type_name="Alert",
                    name=f"Volume {volume.name}",
                    nvalue=level,
                    svalue=text,
                )
            )

    if cfg.enable_nics:
        for nic in nics:
            unit = alloc.get(nic.id)
            if unit is None:
                continue
            if nic.link_status is None:
                # A powered-off host reports LinkStatus null, which is unknown rather than down.
                level, text = health.LEVEL_GREY, "Unknown"
            elif nic.link_status == "LinkUp":
                level, text = health.LEVEL_OK, f"LinkUp {nic.speed_mbps} Mb"
            else:
                level, text = health.LEVEL_YELLOW, str(nic.link_status)
            out.append(
                DeviceUpdate(
                    unit=unit,
                    type_name="Alert",
                    name=f"NIC {nic.id}",
                    nvalue=level,
                    svalue=text,
                )
            )

    if cfg.enable_drives:
        for drive in drives:
            unit = alloc.get(drive.id)
            if unit is None:
                continue
            level, text = health.drive_health(drive, cfg.drive_life_floor)
            out.append(
                DeviceUpdate(
                    unit=unit,
                    type_name="Alert",
                    name=drive.name,
                    nvalue=level,
                    svalue=text,
                )
            )

    out.sort(key=lambda u: u.unit)
    return out
