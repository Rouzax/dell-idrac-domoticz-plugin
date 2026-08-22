"""Redfish and Dell health values mapped to Domoticz Alert levels. Pure."""

LEVEL_GREY = 0
LEVEL_OK = 1
LEVEL_YELLOW = 2
LEVEL_ORANGE = 3
LEVEL_RED = 4

# Redfish Status.Health uses OK / Warning / Critical. Dell's OEM rollup attributes use a
# DIFFERENT vocabulary and report "Error" where Redfish reports Critical. Measured against a
# real PSU failure on a PowerEdge T550, not assumed from documentation.
_LEVEL_BY_STATUS = {
    "ok": LEVEL_OK,
    "warning": LEVEL_ORANGE,
    "noncritical": LEVEL_ORANGE,
    "non-critical": LEVEL_ORANGE,
    "critical": LEVEL_RED,
    "error": LEVEL_RED,
    "failed": LEVEL_RED,
    "fatal": LEVEL_RED,
    "non-recoverable": LEVEL_RED,
    "nonrecoverable": LEVEL_RED,
}

# The aggregate rollup raises the level like any other, but naming it as a "subsystem" would
# just echo the level back at the reader.
_AGGREGATE_ROLLUPS = {"SystemHealthRollupStatus"}

_LABEL_BY_LEVEL = {
    LEVEL_OK: "OK",
    LEVEL_YELLOW: "Warning",
    LEVEL_ORANGE: "Warning",
    LEVEL_RED: "Critical",
}


def alert_level(status: str | None) -> int:
    if not status:
        return LEVEL_GREY
    return _LEVEL_BY_STATUS.get(str(status).strip().lower(), LEVEL_GREY)


def _subsystem_name(rollup_key: str) -> str:
    for suffix in ("RollupStatus", "Status"):
        if rollup_key.endswith(suffix):
            return rollup_key[: -len(suffix)]
    return rollup_key


def system_health(overall: str | None, rollups: dict) -> tuple:
    worst = alert_level(overall)
    unhappy = []
    for key in sorted(rollups):
        level = alert_level(rollups[key])
        if level > worst:
            worst = level
        if level not in (LEVEL_OK, LEVEL_GREY) and key not in _AGGREGATE_ROLLUPS:
            unhappy.append(_subsystem_name(key))
    if worst == LEVEL_GREY:
        return LEVEL_GREY, "Unknown"
    if worst == LEVEL_OK:
        return LEVEL_OK, "OK"
    label = _LABEL_BY_LEVEL[worst]
    if not unhappy:
        return worst, label
    return worst, f"{label}: {', '.join(unhappy)}"


def simple_health(status: str | None, ok_text: str) -> tuple:
    level = alert_level(status)
    if level == LEVEL_OK:
        return level, ok_text
    if level == LEVEL_GREY:
        # Keep the raw string when there IS one. An absent status and a status whose spelling
        # this module does not know must not look identical in the Domoticz UI, otherwise the
        # next vocabulary gap is invisible until someone investigates the hardware by hand.
        return level, f"Unknown ({status})" if status else "Unknown"
    return level, str(status)


def drive_health(drive, life_floor_pct: int) -> tuple:
    level = alert_level(drive.health)
    notes = []
    if drive.media_type:
        notes.append(str(drive.media_type))
    if drive.life_left_pct is not None:
        notes.append(f"life {drive.life_left_pct}%")
        if drive.life_left_pct < life_floor_pct:
            level = max(level, LEVEL_ORANGE)
    if drive.failure_predicted:
        notes.append("failure predicted")
        level = max(level, LEVEL_ORANGE)
    return level, ", ".join(notes) if notes else "OK"


# Redfish's Redundancy Mode enum, in words. An unrecognised mode is shown verbatim rather than
# guessed at, the same rule the rest of this module follows for unknown vocabulary.
_REDUNDANCY_MODE_TEXT = {
    "n+m": "Redundant",
    "failover": "Failover",
    "sharing": "Load sharing",
    "sparing": "Sparing",
    "notredundant": "Not redundant",
}


# Dell spells the non-redundant policy "Not Redundant". Matched loosely because the exact
# wording is Dell's and could gain a qualifier; anything else is treated as "should be
# redundant", which is the safe direction: an unrecognised policy keeps neutral wording rather
# than telling the user a redundancy loss was intentional.
_NOT_REDUNDANT = "not redundant"


def is_not_redundant(policy: str | None) -> bool:
    return bool(policy) and _NOT_REDUNDANT in str(policy).strip().lower()


# Dell spells Hot Spare "PSRapidOn" and reports it as this word or "Disabled".
_HOT_SPARE_ON = "enabled"


def _hot_spare_clause(dell_attrs) -> str:
    """ ", hot spare, primary PSU1" when the feature is on, otherwise nothing.

    THE NAMED SUPPLY IS THE ACTIVE ONE, NOT THE SPARE. Dell's RapidOnPrimaryPSU names the supply
    that CARRIES the load; the unnamed ones are what get parked. Measured on a four-supply
    DSS8440 configured "PSU1 and PSU3": those two delivered 288 W and 307 W while PSU2 and PSU4
    sat at exactly 0 W out. An earlier version of this read ", hot spare PSU1", which labelled
    the working supply as the spare, the precise opposite of what the server means.

    Reports the CONFIGURATION, which is what the iDRAC's own power screen does, and is not proof
    that a supply is actually parked. The same DSS8440 under a "PSU Redundant" policy, Hot Spare
    still on and the same primaries named, shared its load evenly across all four supplies. Only
    the grid policy parked anything on the machines measured.

    Only ever appended to a group that EXISTS.
    """
    if dell_attrs is None:
        return ""
    if str(dell_attrs.hot_spare or "").strip().lower() != _HOT_SPARE_ON:
        return ""
    primary = str(dell_attrs.hot_spare_primary or "").strip()
    # Dell's value is a whole phrase on multi-supply hardware, literally "PSU1 and PSU3", so it
    # goes through verbatim rather than being reworded.
    return f", hot spare, primary {primary}" if primary else ", hot spare enabled"


def redundancy_health(entry, dell_attrs=None) -> tuple:
    """Level and text for a power redundancy group.

    The level always comes from the server's own Status.Health, which is the only field that
    reports an actual fault. The text leads with the CONFIGURED policy, because the generic
    Redfish Mode does not vary: measured across eight Dell servers it was "N+m" on every single
    one, so a tile built from the mode read identically whether the machine was set to A/B Grid
    Redundant or PSU Redundant, and changing the setting could never change the card.

    Falls back to the mode for a server that reports no policy, which is any non-Dell Redfish
    endpoint. Where the server also reports how many supplies are in the set and how many are
    needed, both are included; neither number is inferred.
    """
    level = alert_level(entry.health)
    if level == LEVEL_GREY:
        return level, f"Unknown ({entry.health})" if entry.health else "Unknown"
    if level != LEVEL_OK:
        # A failure states the failure. The configuration that is no longer being met is not
        # what the operator needs to read at that moment.
        return level, "Redundancy lost" if level == LEVEL_RED else "Redundancy degraded"

    mode = entry.mode or ""
    policy = (dell_attrs.redundancy_policy or "").strip() if dell_attrs is not None else ""
    if policy and not is_not_redundant(policy):
        # A server reporting a healthy group under a "Not Redundant" policy is contradicting
        # itself. Leading with the policy there would put "Not Redundant, 2 supplies (1 needed)"
        # on a GREEN tile, which reads worse than the generic wording, so the two disagreeing
        # cases fall back to what the group itself says. Hot Spare goes with the policy for the
        # same reason: three fleet machines run it on under a non-redundant policy and share
        # their load evenly anyway, so claiming a standby supply there would be inventing one.
        text = policy
        suffix = _hot_spare_clause(dell_attrs)
    else:
        text = _REDUNDANCY_MODE_TEXT.get(mode.strip().lower(), mode) or "Redundant"
        suffix = ""
    if entry.supplies:
        text += f", {entry.supplies} supplies"
        if entry.min_needed:
            text += f" ({entry.min_needed} needed)"
    return level, text + suffix
