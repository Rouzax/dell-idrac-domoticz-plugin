"""Turn parsed Redfish payloads into the inventory of hardware that exists. Pure."""

from dataclasses import dataclass

_DIMM_MAX_ID = "Temperature.DIMM_MAX"
_FAN_UNITS = "RPM"


@dataclass(frozen=True)
class Inventory:
    cpu_temps: tuple = ()
    fans: tuple = ()
    dimm_max: str | None = None
    psus: tuple = ()
    drives: tuple = ()
    volumes: tuple = ()
    nics: tuple = ()


def _is_cpu_temp(sensor) -> bool:
    if sensor.id == _DIMM_MAX_ID:
        return False
    return sensor.physical_context == "CPU" and sensor.units == "Cel"


def discover(sensors: dict, psus: list, drives: list, volumes: list, nics: list) -> Inventory:
    cpu_temps = sorted(sid for sid, s in sensors.items() if _is_cpu_temp(s))
    fans = sorted(sid for sid, s in sensors.items() if s.units == _FAN_UNITS)
    return Inventory(
        cpu_temps=tuple(cpu_temps),
        fans=tuple(fans),
        dimm_max=_DIMM_MAX_ID if _DIMM_MAX_ID in sensors else None,
        psus=tuple(sorted(p.id for p in psus)),
        drives=tuple(sorted(d.id for d in drives)),
        volumes=tuple(sorted(v.id for v in volumes)),
        nics=tuple(sorted(n.id for n in nics)),
    )
