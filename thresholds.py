"""Redfish thresholds rendered as human-readable device Description text. Pure.

iDRAC frequently reports UpperThresholdNonCritical as null, so a warning band is
synthesized from the critical threshold. Synthesized values are labelled as
estimates so a reader never mistakes them for something the server reported.
"""

WARN_SYNTH_RATIO = 0.85

# Domoticz's own bar defaults (www/app/widgets/dzBar.js seedDefaults), so a plugin-supplied bar
# looks like one a user drew by hand. Amber is the Material 400 companion to that green.
BAR_OK = "#66bb6a"
BAR_WARNING = "#ffa726"
BAR_CRITICAL = "#DF2D3A"

# The outer red bands need an axis end, and Redfish does not supply one: MaxReadingRange and
# MinReadingRange exist in the schema but read null on real iDRAC hardware. Rather than invent a
# number, each red band is a fixed fraction of the span the server DID report, so the whole axis
# is derived from reported data and scales with the sensor.
BAR_MARGIN_RATIO = 0.1


def synth_warn(critical: float | None, ratio: float = WARN_SYNTH_RATIO) -> float | None:
    if critical is None:
        return None
    return round(critical * ratio, 1)


def _fmt(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(value)


def describe(threshold, units: str) -> str:
    if threshold is None:
        return ""
    unit_suffix = f" {units}" if units else ""
    parts = []

    if threshold.lower_non_critical is not None:
        parts.append(f"warning below {_fmt(threshold.lower_non_critical)}{unit_suffix}")
    if threshold.lower_critical is not None:
        parts.append(f"critical below {_fmt(threshold.lower_critical)}{unit_suffix}")

    if threshold.upper_non_critical is not None:
        parts.append(f"warning above {_fmt(threshold.upper_non_critical)}{unit_suffix}")
    elif threshold.upper_critical is not None:
        estimated = synth_warn(threshold.upper_critical)
        if estimated is not None:
            parts.append(f"warning above {_fmt(estimated)}{unit_suffix} (estimated)")
    if threshold.upper_critical is not None:
        parts.append(f"critical above {_fmt(threshold.upper_critical)}{unit_suffix}")

    return "; ".join(parts)


def bar_ranges(threshold) -> list | None:
    """Contiguous {from, to, color} bands for a Domoticz bar, or None when they cannot be derived.

    Returns None unless BOTH critical thresholds are reported: they define the axis span, and
    without it every edge would be guesswork. Intermediate bands are emitted only where their
    threshold exists, so a sensor reporting no lower warning simply has no lower amber band
    rather than a synthesized one.
    """
    if threshold is None:
        return None
    lower_critical = threshold.lower_critical
    upper_critical = threshold.upper_critical
    if lower_critical is None or upper_critical is None:
        return None
    span = upper_critical - lower_critical
    if span <= 0:
        return None

    margin = round(span * BAR_MARGIN_RATIO, 1)
    lower_warn = threshold.lower_non_critical
    upper_warn = threshold.upper_non_critical
    # The green band runs between the warning edges where they exist and falls back to the
    # criticals where they do not.
    ok_from = lower_warn if lower_warn is not None else lower_critical
    ok_to = upper_warn if upper_warn is not None else upper_critical

    bands = [
        {"from": round(lower_critical - margin, 1), "to": lower_critical, "color": BAR_CRITICAL}
    ]
    if lower_warn is not None:
        bands.append({"from": lower_critical, "to": lower_warn, "color": BAR_WARNING})
    bands.append({"from": ok_from, "to": ok_to, "color": BAR_OK})
    if upper_warn is not None:
        bands.append({"from": upper_warn, "to": upper_critical, "color": BAR_WARNING})
    bands.append(
        {"from": upper_critical, "to": round(upper_critical + margin, 1), "color": BAR_CRITICAL}
    )
    return bands


def bar_ranges_floor(threshold, axis_max) -> list | None:
    """Bands for a sensor where LOW is the fault and high is merely working hard, e.g. a fan.

    Redfish gives no maximum for these: MaxReadingRange reads null, and the Dell OEM fan
    endpoints do not exist (DellFans and DellNumericSensors both 404). Measuring a T550 at full
    speed gave 4920, 4920 and 5520 RPM, so even one chassis has no single maximum and a shipped
    constant would be wrong somewhere. The top therefore comes from the caller, as a user
    setting, and axis_max of 0 means "no bar" rather than a guess.

    A reading above axis_max is not a problem: dzBar's computeBar keeps the last band's colour
    and clamps the fill to 100%, so an over-speed fan reads full green rather than falling off
    the scale.
    """
    if threshold is None or not axis_max or axis_max <= 0:
        return None
    lower_critical = threshold.lower_critical
    if lower_critical is None:
        return None
    lower_warn = threshold.lower_non_critical
    # The top has to leave room for every band below it, or the axis is nonsense.
    if axis_max <= max(lower_critical, lower_warn or lower_critical):
        return None

    # Zero is a genuine floor for a rate like RPM, a stopped fan, so it is not an invented edge.
    bands = [{"from": 0, "to": lower_critical, "color": BAR_CRITICAL}]
    if lower_warn is not None and lower_warn > lower_critical:
        bands.append({"from": lower_critical, "to": lower_warn, "color": BAR_WARNING})
        bands.append({"from": lower_warn, "to": axis_max, "color": BAR_OK})
    else:
        bands.append({"from": lower_critical, "to": axis_max, "color": BAR_OK})
    return bands
