"""Unit allocation and the ordered list of device updates. Pure."""

import json
import re
from collections import Counter
from dataclasses import dataclass, field, replace

import cardtext
import health
import model
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
UNIT_FPGA_POWER = 19

# Domoticz built-in icon ids. The plugin API's Image= sets the CustomImage column
# (hardware/plugins/PythonObjectEx.cpp), and domoticz_api applies it only when a unit is CREATED,
# so a user who later picks a different icon keeps it.
IMAGE_FAN = 7
IMAGE_CLOCK = 21
IMAGE_HARDDISK = 3
IMAGE_GENERIC = 9

# Each DeviceID has its own 1-255 unit space (Developing_a_Python_plugin.wiki: "each Device can
# have 256 Units", "Unit numbers must be less than 256"). Splitting by family therefore removes
# the cramping that a single Device imposes, and Domoticz creates each Device implicitly when its
# first Unit appears. A unit number is only unique WITHIN its device, which is why onCommand has
# to match on DeviceID as well as Unit.
DEVICE_SYSTEM = "system"
DEVICE_THERMAL = "thermal"
DEVICE_POWER = "power"
DEVICE_STORAGE = "storage"
DEVICE_NETWORK = "network"
DEVICE_GPU = "gpu"
DEVICE_CONTROL = "control"

# Every family, so the caller can build one DeviceID per family without duplicating the list.
DEVICE_FAMILIES = (
    DEVICE_SYSTEM,
    DEVICE_THERMAL,
    DEVICE_POWER,
    DEVICE_STORAGE,
    DEVICE_NETWORK,
    DEVICE_GPU,
    DEVICE_CONTROL,
)

BLOCK_TEMPS = 1
BLOCK_FANS = 40
BLOCK_PSUS = 1
BLOCK_PSU_EFFICIENCY = 40
BLOCK_VOLUMES = 1
BLOCK_DRIVES = 40
BLOCK_DRIVE_LIFE = 150
BLOCK_NICS = 1
BLOCK_GPU_POWER = 1
BLOCK_GPU_TEMP = 40
BLOCK_CONTROL = 1

# (device, base) -> how many units the block may use. The device is part of the key because the
# same base number now legitimately appears on more than one device.
_BLOCK_LIMITS = {
    (DEVICE_THERMAL, BLOCK_TEMPS): 20,
    (DEVICE_THERMAL, BLOCK_FANS): 20,
    (DEVICE_POWER, BLOCK_PSUS): 20,
    (DEVICE_POWER, BLOCK_PSU_EFFICIENCY): 20,
    (DEVICE_STORAGE, BLOCK_VOLUMES): 20,
    (DEVICE_STORAGE, BLOCK_DRIVES): 100,
    (DEVICE_STORAGE, BLOCK_DRIVE_LIFE): 100,
    (DEVICE_NETWORK, BLOCK_NICS): 20,
    (DEVICE_GPU, BLOCK_GPU_POWER): 20,
    (DEVICE_GPU, BLOCK_GPU_TEMP): 20,
    (DEVICE_CONTROL, BLOCK_CONTROL): 2,
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
    # Which DeviceID this unit belongs to. Unit numbers are unique only WITHIN a device.
    device: str = DEVICE_SYSTEM
    image: int = 0
    switchtype: int = 0


def _assign_block(ids, device: str, base: int, alloc: dict, taken: dict) -> None:
    """Allocate units for one block. `taken` is PER DEVICE, since the same unit number is free
    again on a different DeviceID and blocking it globally would waste the whole point of the
    split."""
    limit = _BLOCK_LIMITS[(device, base)]
    used = taken.setdefault(device, set())
    for resource_id in ids:
        if resource_id in alloc:
            continue
        for offset in range(limit):
            candidate = base + offset
            if candidate not in used:
                alloc[resource_id] = candidate
                used.add(candidate)
                break


def unassigned(inventory, alloc: dict) -> tuple:
    """Resource ids discovery found that allocation could not place.

    Each block is a fixed range and a unit is never freed once taken, so a long-lived install with
    enough component churn can exhaust one. plan() skips these rather than failing the whole poll,
    and the caller reports them so the gap is visible instead of silent.
    """
    wanted = [rid for _, _, ids in _block_members(inventory) for rid in ids]
    return tuple(rid for rid in wanted if rid not in alloc)


_INPUT_SUFFIX = "_InputPower"
_OUTPUT_SUFFIX = "_OutputPower"


# Below this the ratio is mostly measurement granularity: Dell reports PSU input in whole watts
# and output in quarter watts, so a supply drawing a trickle produces suspiciously round figures
# (a real R440 idling gave exactly 32 W in and 24 W out). Reporting that as an efficiency reading
# would be inventing precision the numbers do not have.
_MIN_EFFICIENCY_INPUT_W = 25.0


def psu_efficiency_percent(sensors: dict, base: str) -> float | None:
    """Conversion efficiency of one supply, or None when the figure would not be meaningful.

    None covers three real cases, all seen on live hardware: a supply on standby (a redundant
    grid feed reading 5 W in and 0 W out is doing nothing, not running at 0% efficiency), a
    supply under a load too light to measure, and a reading that claims more output than input,
    which cannot happen and means the sensor is wrong.
    """
    watts_in = (
        sensors[f"{base}{_INPUT_SUFFIX}"].reading if f"{base}{_INPUT_SUFFIX}" in sensors else None
    )
    watts_out = (
        sensors[f"{base}{_OUTPUT_SUFFIX}"].reading if f"{base}{_OUTPUT_SUFFIX}" in sensors else None
    )
    if watts_in is None or watts_out is None:
        return None
    if watts_out <= 0 or watts_in < _MIN_EFFICIENCY_INPUT_W or watts_out > watts_in:
        return None
    return 100.0 * watts_out / watts_in


def psu_efficiency_name(base: str) -> str:
    """ "PSU.Slot.1" -> "PS1 Efficiency", matching the "PS1 Status" the PowerSupplies list gives.

    Built from the sensor's OWN slot number rather than by pairing with that list, which numbers
    supplies from zero while these sensors number them from one.
    """
    digits = "".join(character for character in base.rsplit(".", 1)[-1] if character.isdigit())
    return f"PS{digits} Efficiency" if digits else f"{base} Efficiency"


def sensor_gpu_temps(inventory) -> list:
    """Sensor-derived GPU temperatures, which are a FALLBACK and never an addition.

    Telemetry carries power as well as temperature and names each card by its slot, so where it
    reports cards these sensors describe the same hardware again. A DSS8440 offers seven of each,
    and using both would put fourteen temperature devices on screen for seven cards.

    Used by allocation and by plan() alike, so the two can never disagree about which set is live.
    """
    if inventory.gpus:
        return []
    return list(inventory.gpu_temps)


def _block_members(inventory) -> tuple:
    """Every block, in allocation order, as (device, base, resource ids)."""
    temps = list(inventory.cpu_temps)
    if inventory.dimm_max:
        temps.append(inventory.dimm_max)
    return (
        (DEVICE_THERMAL, BLOCK_TEMPS, temps),
        (DEVICE_THERMAL, BLOCK_FANS, list(inventory.fans)),
        (DEVICE_POWER, BLOCK_PSUS, list(inventory.psus)),
        (DEVICE_POWER, BLOCK_PSU_EFFICIENCY, list(inventory.psu_efficiency)),
        (DEVICE_STORAGE, BLOCK_VOLUMES, list(inventory.volumes)),
        (DEVICE_STORAGE, BLOCK_DRIVES, list(inventory.drives)),
        # A second, optional device per drive, keyed by a suffixed id to stay unique.
        (DEVICE_STORAGE, BLOCK_DRIVE_LIFE, [f"{d}#life" for d in inventory.drives]),
        (DEVICE_NETWORK, BLOCK_NICS, list(inventory.nics)),
        # Two devices per card, so two blocks. Telemetry cards and sensor-derived GPU
        # temperatures share the temperature block: only one of the two is ever populated, so
        # they cannot collide, and a machine that later gains a licence keeps its unit numbers.
        (DEVICE_GPU, BLOCK_GPU_POWER, [f"{g}#power" for g in inventory.gpus]),
        (
            DEVICE_GPU,
            BLOCK_GPU_TEMP,
            [f"{g}#temp" for g in inventory.gpus] + sensor_gpu_temps(inventory),
        ),
    )


def assign_units(inventory, alloc: dict) -> dict:
    out = dict(alloc)
    # Rebuild the per-device used-set from what is already allocated, so a restart does not hand
    # a stored unit number to something else on the same device.
    taken: dict = {}
    for device, base, ids in _block_members(inventory):
        limit = _BLOCK_LIMITS[(device, base)]
        used = taken.setdefault(device, set())
        used.update(out[rid] for rid in ids if rid in out and base <= out[rid] < base + limit)
    for device, base, ids in _block_members(inventory):
        _assign_block(ids, device, base, out, taken)
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
    (UNIT_FPGA_POWER, "TotalFPGAPower", "FPGA Power"),
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


# Dell reports GPU draw in MILLIWATTS while every other power figure is watts. Reading it raw
# would put 39100 W on a card that is drawing 39 W.
_MILLIWATTS_PER_WATT = 1000.0


def gpu_readings(samples) -> dict:
    """Watts and temperature per GPU, from a telemetry report that repeats ids per card.

    Captured from a seven-GPU OpenManage-managed server. A card is included as soon as it reports
    either figure; the other is left out rather than invented.
    """
    power = model.metric_by_device(samples, "PowerConsumption")
    temps = model.metric_by_device(samples, "PrimaryTemperature")
    out = {}
    for device in sorted(set(power) | set(temps)):
        watts = power.get(device)
        out[device] = (
            None if watts is None else round(watts / _MILLIWATTS_PER_WATT, 1),
            temps.get(device),
        )
    return out


# Device names are what dzVents scripts look devices up by, so two installs monitoring two
# servers must not produce the same names. These tokens let a name affix carry the machine's own
# identity instead of something typed by hand and forgotten.
_TOKEN_PATTERN = re.compile(r"\{([a-z]+)\}")


def name_tokens(system, idrac_name: str | None = None) -> dict:
    """What each {token} in a name affix expands to for THIS machine.

    {hostname} is truncated at the first dot deliberately. A fleet reports host names
    inconsistently, some bare and some fully qualified, so passing the value straight through
    would give "web01" on one server and "web01.some.long.domain" on the next. {fqdn} is there
    for anyone who wants the whole thing.
    """
    hostname = (system.hostname or "").strip()
    return {
        "servicetag": (system.service_tag or "").strip(),
        "hostname": hostname.split(".")[0],
        "fqdn": hostname,
        "model": (system.model or "").strip(),
        "idrac": (idrac_name or "").strip(),
    }


def expand_affix(text: str, tokens: dict) -> tuple:
    """Expand {tokens} in a name affix. Returns (expanded text, tokens that did not resolve).

    Text outside the tokens is used EXACTLY as typed, whitespace included: a user writing
    "SERVER1 - " needs that trailing space, and Domoticz stores custom settings as JSON, which
    preserves it byte for byte.

    An affix that ends up with no alphanumeric character left is dropped completely. Otherwise a
    machine reporting no host name would turn "{hostname} - " into " - " and put half a separator
    in front of every device on the dashboard, which is worse than no affix at all.
    """
    if not text:
        return "", ()
    missing = []

    def _replace(match):
        key = match.group(1)
        value = tokens.get(key)
        if not value:
            missing.append(key)
            return ""
        return value

    out = _TOKEN_PATTERN.sub(_replace, text)
    if not any(character.isalnum() for character in out):
        return "", tuple(missing)
    return out, tuple(missing)


def decorate_names(updates: list, prefix: str = "", suffix: str = "") -> list:
    """Wrap every planned device name in the user's prefix and suffix.

    Applied at ONE point, after the control devices have been added, so every device the plugin
    owns is affected and no name can be missed by a new caller forgetting to do it.
    """
    if not prefix and not suffix:
        return updates
    return [replace(update, name=f"{prefix}{update.name}{suffix}") for update in updates]


def duplicate_names(updates: list) -> tuple:
    """Names this plan would give to more than one device.

    Domoticz allows duplicate names, and a dzVents lookup by name then silently picks one of
    them. No fleet machine has ever produced one of these, so this is a guard against a future
    firmware naming two components identically rather than a fix for a known fault.
    """
    counts = Counter(update.name for update in updates)
    return tuple(sorted(name for name, count in counts.items() if count > 1))


# Dell's own drive names, which differ by controller and read poorly next to each other:
# "Solid State Disk 0:2:0" from a PERC, "SSD 0" from a BOSS boot card. Only these two phrases
# are rewritten; any other name the server reports is left exactly as it is.
#
# Matched ANYWHERE in the name rather than only at the start: Dell prefixes a pass-through disk
# with its RAID state, giving "NonRAID Solid State Disk 0:1:0". That qualifier says the disk is
# in HBA mode rather than part of an array, which is worth keeping, so only the noun is shortened.
_DRIVE_PHRASES = {"Solid State Disk": "SSD", "Physical Disk": "HDD"}

# An NVMe drive is reported with MediaType "SSD", exactly like a SATA one, and named
# "PCIe SSD in Slot 23 in Bay 2". The bus protocol is the ONLY field that distinguishes the two,
# so the rename is gated on what the server reports and never on the name: a drive that merely
# reads like a PCIe device but is attached by SAS keeps the name the server gave it. Dell
# currently reports "PCIe"; the Redfish enum also allows "NVMe", so both take this branch.
_NVME_PROTOCOLS = frozenset({"pcie", "nvme"})
_NVME_PHRASE = "PCIe SSD"


def drive_name(drive) -> str:
    """A short, consistent name: media type then location, with a boot card marked as such."""
    name = drive.name
    protocol = (drive.protocol or "").strip().lower()
    if protocol in _NVME_PROTOCOLS and _NVME_PHRASE in name:
        # "SSD" is dropped rather than kept: NVMe already implies solid state.
        name = name.replace(_NVME_PHRASE, "NVMe", 1)
    elif drive.media_type:
        for verbose, short in _DRIVE_PHRASES.items():
            if verbose in name:
                name = name.replace(verbose, short, 1)
                break
    if drive.is_boot_card and not name.upper().startswith("BOSS"):
        name = f"BOSS {name}"
    return name


def _life_bar(floor_pct: int) -> str:
    """Bands for predicted drive life: red below the user's warning floor, green above it.

    A Percentage device, because the drive's own tile is an Alert and Alert is not in Domoticz's
    bar-supported list. Nothing is invented here: 0 to 100 is inherent to a percentage and the one
    threshold is the user's own setting. A bare array, because the utility card draws this one.
    """
    bands = []
    if floor_pct > 0:
        bands.append({"from": 0, "to": floor_pct, "color": thresholds.BAR_CRITICAL})
    # dzBar discards a zero-width range, so a floor of 0 yields one green band rather than two.
    bands.append({"from": max(0, floor_pct), "to": 100, "color": thresholds.BAR_OK})
    return json.dumps(bands, separators=(",", ":"))


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


def _temp_update(unit, sensor, name, threshold_map, device=DEVICE_SYSTEM) -> DeviceUpdate:
    threshold = threshold_map.get(sensor.name)
    return DeviceUpdate(
        unit=unit,
        type_name="Temperature",
        name=name,
        nvalue=0,
        svalue=_fmt_reading(sensor.reading),
        description=thresholds.describe(threshold, "C"),
        color=_temp_bar(threshold),
        device=device,
    )


# Dell reports the intrusion sensor as a plain string, not a Status block.
_INTRUSION_OK = {"Normal"}


# How much fault text a card carries before the rest becomes a count. NOT a database limit:
# sValue is declared VARCHAR(200) but SQLite does not enforce length, and a 350-character value
# was stored and rendered in full while designing this. It is a readability budget.
_FAULT_BUDGET = 200


def fault_lines(faults) -> list:
    """Fault messages that fit the budget, plus a count of any dropped.

    Replaces cutting the JOINED text mid-sentence, which left half a fault on screen that could
    not be told apart from a complete one. The first message is always kept whatever its length,
    so a single long fault is still readable rather than being replaced by a bare count.
    """
    messages = [fault.message for fault in faults if fault.message]
    kept = []
    used = 0
    for message in messages:
        if kept and used + len(message) > _FAULT_BUDGET:
            break
        kept.append(message)
        used += len(message)
    dropped = len(messages) - len(kept)
    if dropped:
        kept.append(f"+{dropped} more")
    return kept


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
    gpus: dict | None = None,
) -> list:
    faults = faults or []
    redundancy = redundancy or []
    metrics = metrics or {}
    gpus = gpus or {}
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

    for device, (watts, celsius) in sorted(gpus.items()):
        if watts is not None:
            unit = alloc.get(f"{device}#power")
            if unit is not None:
                out.append(
                    DeviceUpdate(
                        unit=unit,
                        type_name="Usage",
                        name=f"GPU {device} Power",
                        device=DEVICE_GPU,
                        nvalue=0,
                        svalue=_fmt_reading(watts),
                    )
                )
        if celsius is not None:
            unit = alloc.get(f"{device}#temp")
            if unit is not None:
                out.append(
                    DeviceUpdate(
                        unit=unit,
                        type_name="Temperature",
                        name=f"GPU {device} Temp",
                        device=DEVICE_GPU,
                        nvalue=0,
                        svalue=_fmt_reading(round(celsius, 1)),
                    )
                )

    # GPU temperatures read from the ordinary Sensors collection, for machines whose telemetry
    # licence does not cover GPU metrics. discover() only fills this when telemetry found no
    # cards, so a card never gets two temperature devices.
    for sensor_id in sensor_gpu_temps(inventory):
        sensor = sensors.get(sensor_id)
        unit = alloc.get(sensor_id)
        if sensor is None or sensor.reading is None or unit is None:
            continue
        out.append(
            DeviceUpdate(
                unit=unit,
                type_name="Temperature",
                name=sensor.name,
                device=DEVICE_GPU,
                nvalue=0,
                svalue=_fmt_reading(sensor.reading),
            )
        )

    if cfg.enable_psus:
        for base in inventory.psu_efficiency:
            unit = alloc.get(base)
            percent = psu_efficiency_percent(sensors, base)
            if unit is None or percent is None:
                continue
            out.append(
                DeviceUpdate(
                    unit=unit,
                    type_name="Percentage",
                    name=psu_efficiency_name(base),
                    device=DEVICE_POWER,
                    nvalue=0,
                    svalue=_fmt_reading(round(percent, 1)),
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
    link = cardtext.idrac_link(cfg.address) if cfg.rich_card_text else ""
    # Dell rollups latch onto faults, so a red level often has no unhealthy component behind it.
    # When the iDRAC states a reason, show the reason instead of a list of subsystem initials.
    messages = fault_lines(faults)
    faulted = bool(messages) and level not in (health.LEVEL_OK, health.LEVEL_GREY)
    if cfg.rich_card_text:
        text = cardtext.bullets(messages, link) if faulted else cardtext.lines([text], link)
    elif faulted:
        text = "; ".join(messages)
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
        # dell_attrs carries the configured policy and Hot Spare. The Redfish group on its own
        # cannot tell one Dell policy from another; see redundancy_parts.
        redundancy_state = health.redundancy_parts(redundancy[0], dell_attrs)
    elif psus:
        # An EMPTY list on a chassis that has supplies has never been observed under a
        # redundant policy. A failed supply does NOT empty it: measured twice, once by pulling a
        # mains cord and once in the "degraded" capture, the supply stays enumerated as Critical
        # and the group survives and goes Critical too, which redundancy_health reports as
        # "Redundancy lost". So this branch is a DEFENSIVE fallback for a state no machine here
        # has produced, not a documented iDRAC behaviour.
        #
        # It still must not emit nothing: that left the tile showing its last value, so it sat
        # green claiming redundancy at the moment redundancy was lost. Grey rather than red
        # because the plugin cannot know WHY the group would be missing; System Health carries
        # the fault text either way.
        #
        # Dell's own policy attribute separates the two reasons the list can be empty. Measured
        # across six servers, the correlation was exact: every machine set to a redundant policy
        # reported a group, and every machine set to Not Redundant reported none. A four-supply
        # DSS8440 is deliberately non-redundant so all four feed its GPUs, and calling that
        # "Not reported" suggests the server is withholding something rather than obeying its
        # configuration. Still grey, never green: not redundant is not a healthy state to
        # advertise, it is simply an intended one.
        if health.is_not_redundant(dell_attrs.redundancy_policy):
            redundancy_state = (health.LEVEL_GREY, ["Not redundant (configured)"])
        else:
            redundancy_state = (health.LEVEL_GREY, ["Not reported"])
    if redundancy_state is not None:
        level, parts = redundancy_state
        svalue = cardtext.lines(parts, link) if cfg.rich_card_text else ", ".join(parts)
        out.append(
            DeviceUpdate(
                unit=UNIT_REDUNDANCY,
                type_name="Alert",
                name="Power Redundancy",
                nvalue=level,
                svalue=svalue,
            )
        )

    for sensor_id in inventory.cpu_temps:
        sensor = sensors[sensor_id]
        unit = alloc.get(sensor_id)
        if sensor.reading is None or unit is None:
            continue
        out.append(_temp_update(unit, sensor, sensor.name, threshold_map, DEVICE_THERMAL))

    if inventory.dimm_max:
        sensor = sensors[inventory.dimm_max]
        unit = alloc.get(inventory.dimm_max)
        if sensor.reading is not None and unit is not None:
            out.append(_temp_update(unit, sensor, "Max DIMM Temp", threshold_map, DEVICE_THERMAL))

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
                device=DEVICE_THERMAL,
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
                    device=DEVICE_POWER,
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
                    device=DEVICE_STORAGE,
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
                    device=DEVICE_NETWORK,
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
                    name=drive_name(drive),
                    device=DEVICE_STORAGE,
                    nvalue=level,
                    svalue=text,
                )
            )
            if not cfg.enable_drive_life or drive.life_left_pct is None:
                continue
            life_unit = alloc.get(f"{drive.id}#life")
            if life_unit is None:
                continue
            out.append(
                DeviceUpdate(
                    unit=life_unit,
                    type_name="Percentage",
                    name=f"{drive_name(drive)} Life",
                    device=DEVICE_STORAGE,
                    nvalue=0,
                    svalue=str(drive.life_left_pct),
                    color=_life_bar(cfg.drive_life_floor),
                    image=IMAGE_HARDDISK,
                )
            )

    out.sort(key=lambda u: u.unit)
    return out
