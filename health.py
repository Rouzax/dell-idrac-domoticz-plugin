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
