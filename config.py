"""Manifest parameters -> typed configuration. Pure."""

from dataclasses import dataclass

_TRUE = {"true", "yes", "1", "on"}


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


def _bool(params: dict, key: str, default: bool) -> bool:
    raw = params.get(key)
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in _TRUE


def _int(params: dict, key: str, default: int, low: int, high: int) -> int:
    try:
        value = int(str(params.get(key, default)).strip())
    except (TypeError, ValueError):
        return default
    return max(low, min(high, value))


def _address(raw: str) -> str:
    text = str(raw).strip()
    for scheme in ("https://", "http://"):
        if text.lower().startswith(scheme):
            text = text[len(scheme) :]
    return text.rstrip("/")


def parse_config(parameters: dict) -> PluginConfig:
    return PluginConfig(
        address=_address(parameters.get("Address", "")),
        username=str(parameters.get("Username", "")).strip(),
        password=str(parameters.get("Password", "")),
        allow_control=_bool(parameters, "AllowControl", False),
        allow_hard_power=_bool(parameters, "AllowHardPowerActions", False),
        poll_interval=_int(parameters, "PollInterval", 30, 15, 600),
        slow_every=_int(parameters, "SlowEvery", 10, 1, 60),
        enable_drives=_bool(parameters, "EnableDrives", True),
        enable_volumes=_bool(parameters, "EnableVolumes", True),
        enable_nics=_bool(parameters, "EnableNICs", True),
        enable_psus=_bool(parameters, "EnablePSUs", True),
        drive_life_floor=_int(parameters, "DriveLifeFloor", 10, 0, 100),
        verify_tls=_bool(parameters, "VerifyTLS", False),
        request_timeout=_int(parameters, "RequestTimeout", 30, 5, 120),
        debug_level=_int(parameters, "DebugLevel", 0, 0, 2),
    )
