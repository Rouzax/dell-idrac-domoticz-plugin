"""Control-plane decisions. Pure: no HTTP, no Domoticz.

Every action offered must be BOTH on our allow-list and advertised by the server.
Nmi is deliberately absent from both lists: it crashes the host on purpose and is
not something a scene or timer should be able to reach.
"""

import planner

UNIT_POWER_CONTROL = planner.BLOCK_CONTROL
UNIT_IDENTIFY = planner.BLOCK_CONTROL + 1

GRACEFUL_ACTIONS = (
    ("Power On", "On"),
    ("Graceful Shutdown", "GracefulShutdown"),
    ("Graceful Restart", "GracefulRestart"),
)

HARD_ACTIONS = (
    ("Force Off", "ForceOff"),
    ("Power Cycle", "PowerCycle"),
)


def available_actions(allowable, allow_hard: bool) -> tuple:
    advertised = set(allowable or ())
    candidates = GRACEFUL_ACTIONS + (HARD_ACTIONS if allow_hard else ())
    return tuple((label, rt) for label, rt in candidates if rt in advertised)


def level_to_reset_type(level: int, actions: tuple):
    """Domoticz selector levels are 0, 10, 20, ...; level 0 is the idle 'Off' entry."""
    try:
        level = int(level)
    except (TypeError, ValueError):
        return None
    if level <= 0 or level % 10 != 0:
        return None
    index = level // 10 - 1
    if index >= len(actions):
        return None
    return actions[index][1]


def control_updates(cfg, allowable, identify_on: bool) -> list:
    if not cfg.allow_control:
        return []
    actions = available_actions(allowable, cfg.allow_hard_power)
    names = "|".join(["Idle"] + [label for label, _ in actions])
    return [
        planner.DeviceUpdate(
            unit=UNIT_POWER_CONTROL,
            type_name="Selector Switch",
            name="Power Control",
            nvalue=0,
            svalue="0",
            options={
                "LevelActions": "|" * len(actions),
                "LevelNames": names,
                "LevelOffHidden": "false",
                "SelectorStyle": "1",
            },
        ),
        planner.DeviceUpdate(
            unit=UNIT_IDENTIFY,
            type_name="Switch",
            name="Identify LED",
            nvalue=1 if identify_on else 0,
            svalue="",
        ),
    ]
