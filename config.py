"""Manifest parameters -> typed configuration. Pure."""

from dataclasses import dataclass, field

_TRUE = {"true", "yes", "1", "on"}
_FALSE = {"false", "no", "0", "off"}

# Longest affix accepted on either side. Domoticz stores a device name in a VARCHAR(100) and the
# longest name this plugin generates is 35 characters, so two affixes at this limit still leave
# real slack. A longer value is far more likely to be a mistake than an intention.
MAX_AFFIX = 24


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
    fan_bar_max: int
    enable_drive_life: bool
    setup_telemetry: bool
    verify_tls: bool
    request_timeout: int
    debug_level: int
    # Wrapped around every device name. Empty by default, so an existing install is untouched
    # until the user asks for it. May contain {servicetag}, {hostname}, {fqdn}, {model} and
    # {idrac} tokens, which planner expands once the machine has been read.
    name_prefix: str = ""
    name_suffix: str = ""
    # Line breaks, a bulleted fault list and a link to the iDRAC on the two roll-up cards.
    # Default ON, so it reaches existing installs on upgrade. Off reproduces the previous text
    # byte for byte, which matters because sValue is what dzVents compares and what Domoticz
    # notifications send.
    rich_card_text: bool = True
    # Per-component power devices as kWh counters instead of watt gauges. Default ON, so the
    # feature reaches existing installs on upgrade; the devices are converted IN PLACE and keep
    # their idx, name and room. Turning it off converts them back to Usage devices and their
    # original watt graphs reappear, because Domoticz keeps the two types' history in different
    # tables. Server Power is a counter either way and ignores this.
    energy_counters: bool = True
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


def _affix(params: dict, key: str, notes: list) -> str:
    """A name prefix or suffix, used EXACTLY as typed apart from a length clamp.

    Deliberately not stripped: "SERVER1 - " needs its trailing space to keep the separator off
    the device name, and Domoticz keeps custom settings in a JSON blob, which preserves it. Only
    Username and Password are trimmed on the way in (main/WebServerCmds.cpp), not this.
    """
    raw = params.get(key)
    if raw is None:
        return ""
    text = str(raw)
    if len(text) > MAX_AFFIX:
        notes.append(f"{key}: longer than {MAX_AFFIX} characters, using the first {MAX_AFFIX}")
        return text[:MAX_AFFIX]
    return text


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
        poll_interval=_int(parameters, "PollInterval", 30, 20, 600, notes),
        slow_every=_int(parameters, "SlowEvery", 10, 1, 60, notes),
        enable_drives=_bool(parameters, "EnableDrives", True, notes),
        enable_volumes=_bool(parameters, "EnableVolumes", True, notes),
        enable_nics=_bool(parameters, "EnableNICs", True, notes),
        enable_psus=_bool(parameters, "EnablePSUs", True, notes),
        drive_life_floor=_int(parameters, "DriveLifeFloor", 10, 0, 100, notes),
        fan_bar_max=_int(parameters, "FanBarMax", 6000, 0, 60000, notes),
        enable_drive_life=_bool(parameters, "EnableDriveLife", False, notes),
        setup_telemetry=_bool(parameters, "SetupTelemetry", False, notes),
        verify_tls=_bool(parameters, "VerifyTLS", False, notes),
        request_timeout=_int(parameters, "RequestTimeout", 30, 5, 120, notes),
        debug_level=_int(parameters, "DebugLevel", 0, 0, 2, notes),
        name_prefix=_affix(parameters, "NamePrefix", notes),
        name_suffix=_affix(parameters, "NameSuffix", notes),
        rich_card_text=_bool(parameters, "RichCardText", True, notes),
        energy_counters=_bool(parameters, "EnergyCounters", True, notes),
        warnings=tuple(notes),
    )
