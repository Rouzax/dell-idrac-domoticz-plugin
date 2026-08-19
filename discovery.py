"""Turn parsed Redfish payloads into the inventory of hardware that exists. Pure."""

import re
from dataclasses import dataclass

_DIMM_MAX_ID = "Temperature.DIMM_MAX"
_FAN_UNITS = "RPM"


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


def _is_cpu_temp(sensor) -> bool:
    # The PhysicalContext test below already excludes DIMM_MAX, whose context is
    # MemorySubsystem. This id check is a deliberate second line of defence against a firmware
    # that mis-tags it as CPU, not redundant code to be tidied away.
    if sensor.id == _DIMM_MAX_ID:
        return False
    return sensor.physical_context == "CPU" and sensor.units == "Cel"


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
    return Inventory(
        cpu_temps=tuple(cpu_temps),
        fans=tuple(fans),
        dimm_max=_DIMM_MAX_ID if _DIMM_MAX_ID in sensors else None,
        psus=tuple(sorted((p.id for p in psus), key=_natural_key)),
        drives=tuple(sorted((d.id for d in drives), key=_natural_key)),
        volumes=tuple(sorted((v.id for v in volumes), key=_natural_key)),
        nics=tuple(sorted((n.id for n in nics), key=_natural_key)),
    )
