"""Unit allocation and the ordered list of device updates. Pure."""

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


def _temp_update(unit, sensor, name, threshold_map) -> DeviceUpdate:
    return DeviceUpdate(
        unit=unit,
        type_name="Temperature",
        name=name,
        nvalue=0,
        svalue=_fmt_reading(sensor.reading),
        description=thresholds.describe(threshold_map.get(sensor.name), "C"),
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
) -> list:
    faults = faults or []
    redundancy = redundancy or []
    out = []

    power = sensors.get("SystemBoardPwrConsumption")
    if power is not None and power.reading is not None:
        out.append(
            DeviceUpdate(
                unit=UNIT_POWER,
                type_name="kWh",
                name="Server Power",
                nvalue=0,
                svalue=f"{power.reading};{energy_wh}",
                options={"EnergyMeterMode": "0"},
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

    for entry in redundancy:
        level, text = health.simple_health(entry.health, entry.mode or "OK")
        out.append(
            DeviceUpdate(
                unit=UNIT_REDUNDANCY,
                type_name="Alert",
                name="Power Redundancy",
                nvalue=level,
                svalue=text,
            )
        )
        break

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
