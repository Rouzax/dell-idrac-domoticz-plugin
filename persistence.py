"""Durable plugin state <-> JSON for Domoticz.Configuration()."""

import json
from dataclasses import dataclass, field

STATE_VERSION = 1


@dataclass
class PluginState:
    """Persisted state.

    - unit_alloc: Redfish resource Id -> Domoticz Unit number, so a discovered
      item keeps its unit across restarts and a unit is never reused for a
      different physical item.
    - auto_names: Unit number (as string) -> last auto-generated device name,
      used to detect a user rename and never overwrite it.
    - base_wh: Unit number (as string) -> cumulative Wh baseline.
    - control_shown: whether control units are currently shown by us, so the
      show/hide runs once per AllowControl transition and a manual hide sticks.
    - energy_scale: multiplier turning AccumulativePower into Wh, once measured.
    """

    unit_alloc: dict = field(default_factory=dict)
    auto_names: dict = field(default_factory=dict)
    base_wh: dict = field(default_factory=dict)
    control_shown: bool = False
    energy_scale: float | None = None


def migrate(raw: dict) -> dict:
    raw.setdefault("unit_alloc", {})
    raw.setdefault("auto_names", {})
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
            "base_wh": state.base_wh,
            "control_shown": state.control_shown,
            "energy_scale": state.energy_scale,
        },
        separators=(",", ":"),
    )


def loads(text: str) -> PluginState:
    if not text:
        return PluginState()
    raw = migrate(json.loads(text))
    return PluginState(
        unit_alloc=raw["unit_alloc"],
        auto_names=raw["auto_names"],
        base_wh=raw["base_wh"],
        control_shown=raw["control_shown"],
        energy_scale=raw["energy_scale"],
    )
