"""Manifest parameters -> typed configuration. Pure."""

from dataclasses import dataclass, field

_TRUE = {"true", "yes", "1", "on"}
_FALSE = {"false", "no", "0", "off"}


@dataclass(frozen=True)
class PluginConfig:
    address: str
    username: str
    password: str
    allow_control: bool
    allow_hard_power: bool
    poll_interval: int
    slow_every: int
    enable_drives: bool
    enable_volumes: bool
    enable_nics: bool
    enable_psus: bool
    drive_life_floor: int
    verify_tls: bool
    request_timeout: int
    debug_level: int
    # Every value this module quietly changed from what the user typed. The module is pure and
    # cannot log, so it reports instead and the caller logs at onStart. A silently rewritten
    # setting the user never sees is worse than a wrong one they can spot.
    warnings: tuple[str, ...] = field(default_factory=tuple)


def _bool(params: dict, key: str, default: bool, notes: list) -> bool:
    raw = params.get(key)
    if raw is None or str(raw).strip() == "":
        return default
    text = str(raw).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    # Fall back to the FIELD'S declared default, not to False. The monitoring toggles default on,
    # so collapsing an unrecognised value to False would silently disable monitoring.
    notes.append(f"{key}: unrecognised value {raw!r}, using {default}")
    return default


def _int(params: dict, key: str, default: int, low: int, high: int, notes: list) -> int:
    raw = params.get(key, default)
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        notes.append(f"{key}: could not read {raw!r}, using {default}")
        return default
    clamped = max(low, min(high, value))
    if clamped != value:
        notes.append(f"{key}: {value} is outside {low}-{high}, using {clamped}")
    return clamped


def _address(raw: str) -> str:
    text = str(raw).strip()
    for scheme in ("https://", "http://"):
        if text.lower().startswith(scheme):
            text = text[len(scheme) :]
    return text.rstrip("/")


def parse_config(parameters: dict) -> PluginConfig:
    notes: list[str] = []
    return PluginConfig(
        address=_address(parameters.get("Address", "")),
        username=str(parameters.get("Username", "")).strip(),
        password=str(parameters.get("Password", "")),
        allow_control=_bool(parameters, "AllowControl", False, notes),
        allow_hard_power=_bool(parameters, "AllowHardPowerActions", False, notes),
        poll_interval=_int(parameters, "PollInterval", 30, 15, 600, notes),
        slow_every=_int(parameters, "SlowEvery", 10, 1, 60, notes),
        enable_drives=_bool(parameters, "EnableDrives", True, notes),
        enable_volumes=_bool(parameters, "EnableVolumes", True, notes),
        enable_nics=_bool(parameters, "EnableNICs", True, notes),
        enable_psus=_bool(parameters, "EnablePSUs", True, notes),
        drive_life_floor=_int(parameters, "DriveLifeFloor", 10, 0, 100, notes),
        verify_tls=_bool(parameters, "VerifyTLS", False, notes),
        request_timeout=_int(parameters, "RequestTimeout", 30, 5, 120, notes),
        debug_level=_int(parameters, "DebugLevel", 0, 0, 2, notes),
        warnings=tuple(notes),
    )
