"""Control-plane decisions. Pure: no HTTP, no Domoticz.

A LEVEL'S MEANING IS FIXED AND MUST NEVER CHANGE. Domoticz stores selector levels inside scenes,
timers and scripts, which are written once and replayed for years. If a level were an index into
whatever happens to be offered today, dropping one action from the offered set would compact
everything after it downward, and a saved automation meaning "Graceful Restart" would come to mean
"Force Off". Redfish permits ResetType@Redfish.AllowableValues to vary, so that set is not stable
ground to number a menu from. Every action therefore owns a permanent slot, and availability is
enforced when the command arrives rather than by renumbering.

Nmi is deliberately absent from the table: it crashes the host on purpose and is not something a
scene or timer should be able to reach.
"""

import planner

UNIT_POWER_CONTROL = planner.BLOCK_CONTROL
UNIT_IDENTIFY = planner.BLOCK_CONTROL + 1

# Position defines the level: index 0 is level 10, index 1 is level 20, and so on.
# NEVER reorder and never remove an entry. Append only.
ACTION_SLOTS = (
    ("Power On", "On"),
    ("Graceful Shutdown", "GracefulShutdown"),
    ("Graceful Restart", "GracefulRestart"),
    ("Force Off", "ForceOff"),
    ("Power Cycle", "PowerCycle"),
)

HARD_RESET_TYPES = frozenset({"ForceOff", "PowerCycle"})


def level_to_reset_type(level):
    """Domoticz selector levels are 0, 10, 20 ...; level 0 is the idle entry.

    Fixed and independent of what is currently offered, so a stored level always denotes the same
    action. Whether it may RUN is a separate question, answered by is_available.
    """
    try:
        level = int(level)
    except (TypeError, ValueError):
        return None
    if level <= 0 or level % 10 != 0:
        return None
    index = level // 10 - 1
    if index >= len(ACTION_SLOTS):
        return None
    return ACTION_SLOTS[index][1]


def is_available(reset_type, allowable, allow_hard: bool) -> bool:
    """A reset type may run only if the server advertises it AND the hard gate permits it."""
    if reset_type is None:
        return False
    if reset_type in HARD_RESET_TYPES and not allow_hard:
        return False
    return reset_type in set(allowable or ())


def level_names(allowable, allow_hard: bool) -> str:
    """Every slot always appears, so positions never move. Unusable ones say so."""
    names = ["Idle"]
    for label, reset_type in ACTION_SLOTS:
        suffix = "" if is_available(reset_type, allowable, allow_hard) else " (unavailable)"
        names.append(f"{label}{suffix}")
    return "|".join(names)


def control_updates(cfg, allowable, identify_on: bool) -> list:
    if not cfg.allow_control:
        return []
    return [
        planner.DeviceUpdate(
            unit=UNIT_POWER_CONTROL,
            type_name="Selector Switch",
            name="Power Control",
            device=planner.DEVICE_CONTROL,
            image=planner.IMAGE_GENERIC,
            nvalue=0,
            svalue="0",
            options={
                "LevelActions": "|" * len(ACTION_SLOTS),
                "LevelNames": level_names(allowable, cfg.allow_hard_power),
                "LevelOffHidden": "false",
                "SelectorStyle": "1",
            },
        ),
        planner.DeviceUpdate(
            unit=UNIT_IDENTIFY,
            type_name="Switch",
            name="Identify LED",
            device=planner.DEVICE_CONTROL,
            nvalue=1 if identify_on else 0,
            svalue="",
        ),
    ]
