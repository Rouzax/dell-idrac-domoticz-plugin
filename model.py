"""Pure parsing of Redfish payloads into typed values. No I/O, no Domoticz."""

from dataclasses import dataclass

# Dell reports a rollup as this string when the subsystem does not apply to the
# chassis. It is an absence, not a status.
_NOT_APPLICABLE = "None"

_ROLLUP_SUFFIX = "RollupStatus"
_EXTRA_ROLLUPS = ("SysMemPrimaryStatus",)


@dataclass(frozen=True)
class Threshold:
    upper_critical: float | None = None
    upper_non_critical: float | None = None
    lower_critical: float | None = None
    lower_non_critical: float | None = None


@dataclass(frozen=True)
class Sensor:
    id: str
    name: str
    reading: float | None
    units: str
    health: str | None
    physical_context: str | None


@dataclass(frozen=True)
class Psu:
    id: str
    name: str
    input_watts: float | None
    health: str | None
    state: str | None


@dataclass(frozen=True)
class Drive:
    id: str
    name: str
    media_type: str | None
    capacity_bytes: int | None
    health: str | None
    failure_predicted: bool
    life_left_pct: int | None


@dataclass(frozen=True)
class Volume:
    id: str
    name: str
    raid_type: str | None
    health: str | None


@dataclass(frozen=True)
class Nic:
    id: str
    link_status: str | None
    speed_mbps: int | None


@dataclass(frozen=True)
class SystemInfo:
    power_state: str | None
    health: str | None
    boot_state: str | None
    model: str | None
    cpu_count: int
    rollups: dict


@dataclass(frozen=True)
class ChassisInfo:
    intrusion: str | None
    identify_on: bool


@dataclass(frozen=True)
class DellAttrs:
    accumulative_power: float | None
    peak_watts: float | None
    powered_on_seconds: int | None


def _health(node: dict) -> str | None:
    status = node.get("Status") or {}
    return status.get("Health")


def _number(value) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return value
    return None


def _int(value) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return int(value)
    return None


# A powered-off host reports -128 for a temperature that has no reading, which is the classic
# signed-byte sentinel rather than a measurement. Measured on a PowerEdge R6515 with the host off:
# Temperature.DIMM_MAX returned -128.0 with Status.Health null. Writing that into a Domoticz
# temperature device would put a permanent false reading into its history.
_TEMP_SENTINEL_BELOW = -100.0
_TEMP_SENTINEL_ABOVE = 250.0


def _reading(value, units: str) -> float | None:
    number = _number(value)
    if number is None:
        return None
    if units == "Cel" and not (_TEMP_SENTINEL_BELOW < number < _TEMP_SENTINEL_ABOVE):
        return None
    return number


def parse_sensors(payload: dict) -> dict:
    out = {}
    for member in payload.get("Members", []):
        sensor_id = member.get("Id")
        if not sensor_id:
            # An unexpanded collection member is a link with no Id.
            continue
        units = member.get("ReadingUnits", "")
        out[sensor_id] = Sensor(
            id=sensor_id,
            name=member.get("Name", sensor_id),
            reading=_reading(member.get("Reading"), units),
            units=units,
            health=_health(member),
            physical_context=member.get("PhysicalContext"),
        )
    return out


def _threshold(node: dict) -> Threshold:
    return Threshold(
        upper_critical=_number(node.get("UpperThresholdCritical")),
        upper_non_critical=_number(node.get("UpperThresholdNonCritical")),
        lower_critical=_number(node.get("LowerThresholdCritical")),
        lower_non_critical=_number(node.get("LowerThresholdNonCritical")),
    )


def parse_thermal_thresholds(payload: dict) -> dict:
    out = {}
    for node in payload.get("Temperatures", []):
        out[node.get("Name", "")] = _threshold(node)
    for node in payload.get("Fans", []):
        out[node.get("Name", "")] = _threshold(node)
    out.pop("", None)
    return out


def parse_system(payload: dict) -> SystemInfo:
    dell = (payload.get("Oem") or {}).get("Dell") or {}
    dell_system = dell.get("DellSystem") or {}
    rollups = {}
    for key, value in dell_system.items():
        if (
            isinstance(value, str)
            and (key.endswith(_ROLLUP_SUFFIX) or key in _EXTRA_ROLLUPS)
            and value != _NOT_APPLICABLE
        ):
            rollups[key] = value
    boot = payload.get("BootProgress") or {}
    # A powered-off host reports the STRING "None" here, which is an absence, not a boot state.
    boot_state = boot.get("LastState")
    if boot_state == "None":
        boot_state = None
    processors = payload.get("ProcessorSummary") or {}
    return SystemInfo(
        power_state=payload.get("PowerState"),
        health=_health(payload),
        boot_state=boot_state,
        model=payload.get("Model"),
        cpu_count=_int(processors.get("Count")) or 0,
        rollups=rollups,
    )


def parse_power(payload: dict) -> list:
    out = []
    for node in payload.get("PowerSupplies", []):
        status = node.get("Status") or {}
        name = node.get("Name", "")
        # MemberId is a bare ordinal ("0", "1"). unit_alloc is one namespace shared by every
        # resource type, so the id is namespaced to stay collision-proof and readable there.
        member_id = node.get("MemberId")
        out.append(
            Psu(
                id=f"PSU.{member_id}" if member_id is not None else name,
                name=name,
                input_watts=_number(node.get("PowerInputWatts")),
                health=status.get("Health"),
                state=status.get("State"),
            )
        )
    return out


def parse_drives(payload: dict) -> list:
    out = []
    for node in payload.get("Drives", []):
        if not isinstance(node, dict) or "Id" not in node:
            continue
        out.append(
            Drive(
                id=node["Id"],
                name=node.get("Name", node["Id"]),
                media_type=node.get("MediaType"),
                capacity_bytes=_int(node.get("CapacityBytes")),
                health=_health(node),
                failure_predicted=bool(node.get("FailurePredicted")),
                life_left_pct=_int(node.get("PredictedMediaLifeLeftPercent")),
            )
        )
    return out


def parse_volumes(payload: dict) -> list:
    out = []
    for node in payload.get("Members", []):
        if not isinstance(node, dict) or "Id" not in node:
            continue
        out.append(
            Volume(
                id=node["Id"],
                name=node.get("Name", node["Id"]),
                raid_type=node.get("RAIDType"),
                health=_health(node),
            )
        )
    return out


def parse_nics(payload: dict) -> list:
    out = []
    for node in payload.get("Members", []):
        if not isinstance(node, dict) or "Id" not in node:
            continue
        out.append(
            Nic(
                id=node["Id"],
                link_status=node.get("LinkStatus"),
                speed_mbps=_int(node.get("SpeedMbps")),
            )
        )
    return out


def parse_chassis(payload: dict) -> ChassisInfo:
    security = payload.get("PhysicalSecurity") or {}
    return ChassisInfo(
        intrusion=security.get("IntrusionSensor"),
        identify_on=bool(payload.get("LocationIndicatorActive")),
    )


def parse_dell_attributes(payload: dict) -> DellAttrs:
    attrs = payload.get("Attributes") or {}
    return DellAttrs(
        accumulative_power=_number(attrs.get("ServerPwrMon.1.AccumulativePower")),
        peak_watts=_number(attrs.get("ServerPwrMon.1.PeakPowerWatts")),
        powered_on_seconds=_int(attrs.get("ServerOS.1.ServerPoweredOnTime")),
    )


@dataclass(frozen=True)
class Fault:
    severity: str | None
    message: str | None


@dataclass(frozen=True)
class Redundancy:
    name: str
    mode: str | None
    health: str | None


def parse_faults(payload: dict) -> list:
    out = []
    for node in payload.get("Members", []):
        if not isinstance(node, dict):
            continue
        message = node.get("Message")
        if not message:
            continue
        out.append(Fault(severity=node.get("Severity"), message=message))
    return out


def parse_redundancy(payload: dict) -> list:
    out = []
    for node in payload.get("Redundancy", []):
        if not isinstance(node, dict):
            continue
        name = node.get("Name")
        if not name:
            continue
        status = node.get("Status") or {}
        out.append(Redundancy(name=name, mode=node.get("Mode"), health=status.get("Health")))
    return out
