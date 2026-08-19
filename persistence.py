"""Durable plugin state <-> JSON for Domoticz.Configuration()."""

import json
from dataclasses import dataclass, field

STATE_VERSION = 1


@dataclass
class PluginState:
    """Persisted state.

    - unit_alloc: Redfish resource Id -> Domoticz Unit number, so a discovered item keeps its
      unit across restarts and a unit is never reused for a different physical item.
    - auto_names: Unit number (as string) -> last auto-generated device name, used to detect a
      user rename and never overwrite it.
    - base_wh: Unit number (as string) -> cumulative Wh baseline.
    - control_shown: whether control units are currently shown by us, so the show/hide runs once
      per AllowControl transition and a manual hide sticks.
    - energy_scale: multiplier turning a raw counter into Wh, once measured.
    """

    unit_alloc: dict[str, int] = field(default_factory=dict)
    auto_names: dict[str, str] = field(default_factory=dict)
    # Bar-range payloads the plugin last wrote, so it can tell its own bands from a user's edit.
    auto_colors: dict[str, str] = field(default_factory=dict)
    base_wh: dict[str, float] = field(default_factory=dict)
    control_shown: bool = False
    energy_scale: float | None = None


def migrate(raw: dict) -> dict:
    # Defaulting only. There is deliberately no version-dispatch seam yet, because v1 has nothing
    # to migrate FROM. When STATE_VERSION first bumps, the dispatch must be added HERE before any
    # field changes meaning, otherwise a v1 payload would be read under v2 semantics.
    raw.setdefault("unit_alloc", {})
    raw.setdefault("auto_names", {})
    raw.setdefault("auto_colors", {})
    raw.setdefault("base_wh", {})
    raw.setdefault("control_shown", False)
    raw.setdefault("energy_scale", None)
    raw.setdefault("version", STATE_VERSION)
    return raw


def dumps(state: PluginState) -> str:
    return json.dumps(
        {
            "version": STATE_VERSION,
            "unit_alloc": state.unit_alloc,
            "auto_names": state.auto_names,
            "auto_colors": state.auto_colors,
            "base_wh": state.base_wh,
            "control_shown": state.control_shown,
            "energy_scale": state.energy_scale,
        },
        separators=(",", ":"),
    )


def _number(value):
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return value


def _str_keyed(node, want) -> dict:
    """Keep only entries whose key is a string and whose value is the expected type.

    A payload with the wrong shape yields an empty mapping rather than a type-corrupted one.
    Handing a list or a string-valued counter downstream would defer the crash to polling code,
    where it is far harder to trace back to a bad stored value.
    """
    if not isinstance(node, dict):
        return {}
    out = {}
    for key, value in node.items():
        if not isinstance(key, str) or isinstance(value, bool):
            continue
        if isinstance(value, want):
            out[key] = value
    return out


def loads(text: str) -> PluginState:
    """Never raises. Any unusable payload yields default state.

    This value comes from a database column, so a truncated write, a hand edit or a payload from
    an incompatible version are all realistic. It is read during onStart, where raising would kill
    the plugin before it could report why.
    """
    if not text or not text.strip():
        return PluginState()
    try:
        raw = json.loads(text)
    except ValueError:
        return PluginState()
    if not isinstance(raw, dict):
        return PluginState()
    raw = migrate(raw)
    return PluginState(
        unit_alloc=_str_keyed(raw.get("unit_alloc"), int),
        auto_names=_str_keyed(raw.get("auto_names"), str),
        auto_colors=_str_keyed(raw.get("auto_colors"), str),
        base_wh={k: float(v) for k, v in _str_keyed(raw.get("base_wh"), int | float).items()},
        control_shown=raw.get("control_shown") is True,
        energy_scale=_number(raw.get("energy_scale")),
    )
