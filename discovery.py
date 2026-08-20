"""Turn parsed Redfish payloads into the inventory of hardware that exists. Pure."""

import re
from dataclasses import dataclass

_DIMM_MAX_ID = "Temperature.DIMM_MAX"
_FAN_UNITS = "RPM"
_CELSIUS = "Cel"


def _natural_key(value: str) -> tuple:
    """Sort ids so Disk.Bay.2 precedes Disk.Bay.10, which plain string order gets backwards.

    Unit numbers are allocated in this order and then persisted for the life of the install,
    so the ordering has to be right the first time a chassis is discovered.
    """
    return tuple(int(p) if p.isdigit() else p for p in re.split(r"(\d+)", value))


@dataclass(frozen=True)
class Inventory:
    cpu_temps: tuple = ()
    fans: tuple = ()
    dimm_max: str | None = None
    psus: tuple = ()
    drives: tuple = ()
    volumes: tuple = ()
    nics: tuple = ()
    # From telemetry, not from a Redfish collection, so discover() does not fill it.
    gpus: tuple = ()
    # GPU temperatures read from the plain Sensors collection instead of from telemetry, which
    # is licence-gated. Only used when telemetry reported no cards, so a machine never gets two
    # temperature devices for the same GPU.
    gpu_temps: tuple = ()
    # Power supplies reporting BOTH the AC they draw and the DC they deliver, identified by the
    # part of the sensor id they share. Efficiency is the ratio of the two.
    psu_efficiency: tuple = ()


def _is_cpu_temp(sensor) -> bool:
    # The PhysicalContext test below already excludes DIMM_MAX, whose context is
    # MemorySubsystem. This id check is a deliberate second line of defence against a firmware
    # that mis-tags it as CPU, not redundant code to be tidied away.
    if sensor.id == _DIMM_MAX_ID:
        return False
    return sensor.physical_context == "CPU" and sensor.units == _CELSIUS


def _is_gpu_temp(sensor) -> bool:
    """A GPU temperature from the ordinary Sensors collection.

    Matched on the Redfish PhysicalContext enum, never on an id prefix. The ids are wildly
    inconsistent even within one vendor: a real DSS8440 calls them SystemBoardSLOT5Temp while a
    real R750 calls the same kind of thing GPUTemp8, so an id rule would find one and miss the
    other. The unit test is what keeps a GPU POWER sensor, which shares the context, out.
    """
    return sensor.physical_context == "GPU" and sensor.units == _CELSIUS


_INPUT_SUFFIX = "_InputPower"
_OUTPUT_SUFFIX = "_OutputPower"
_WATTS = "W"


def _psu_power_bases(sensors: dict) -> list:
    """Supplies that report both sides of the conversion, by the id they share.

    The physical context identifies a power supply portably; the suffix is what says which
    DIRECTION a reading is, and nothing else in Redfish carries that, so the pair has to be
    matched on it. Both halves are required: input alone says nothing about conversion loss.

    Deliberately NOT correlated with the PowerSupplies collection. Those are numbered from zero
    (`PSU.0`) while these sensors are numbered from one (`PSU.Slot.1`), so pairing them would
    rest on an off-by-one nobody has verified. The device is named from the sensor's own slot.
    """
    supplies = {
        sid: sensor
        for sid, sensor in sensors.items()
        if sensor.physical_context == "PowerSupply" and sensor.units == _WATTS
    }
    bases = {sid[: -len(_INPUT_SUFFIX)] for sid in supplies if sid.endswith(_INPUT_SUFFIX)}
    return [base for base in bases if f"{base}{_OUTPUT_SUFFIX}" in supplies]


def _is_fan(sensor) -> bool:
    # Classified by unit alone. Dell tags its fans PhysicalContext "SystemBoard", not "Fan", so
    # context is no help, and requiring an id prefix such as "Fan." would report NO fans at all
    # on a model that names them differently. Unit alone fails safe instead: a pump or blower on
    # a liquid-cooled chassis would appear among the fans carrying its own reported name, which
    # is wrong but harmless, rather than the whole fan set going missing.
    return sensor.units == _FAN_UNITS


def discover(sensors: dict, psus: list, drives: list, volumes: list, nics: list) -> Inventory:
    cpu_temps = sorted((sid for sid, s in sensors.items() if _is_cpu_temp(s)), key=_natural_key)
    fans = sorted((sid for sid, s in sensors.items() if _is_fan(s)), key=_natural_key)
    gpu_temps = sorted((sid for sid, s in sensors.items() if _is_gpu_temp(s)), key=_natural_key)
    return Inventory(
        cpu_temps=tuple(cpu_temps),
        fans=tuple(fans),
        dimm_max=_DIMM_MAX_ID if _DIMM_MAX_ID in sensors else None,
        psus=tuple(sorted((p.id for p in psus), key=_natural_key)),
        drives=tuple(sorted((d.id for d in drives), key=_natural_key)),
        volumes=tuple(sorted((v.id for v in volumes), key=_natural_key)),
        nics=tuple(sorted((n.id for n in nics), key=_natural_key)),
        gpu_temps=tuple(gpu_temps),
        psu_efficiency=tuple(sorted(_psu_power_bases(sensors), key=_natural_key)),
    )
