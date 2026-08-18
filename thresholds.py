"""Redfish thresholds rendered as human-readable device Description text. Pure.

iDRAC frequently reports UpperThresholdNonCritical as null, so a warning band is
synthesized from the critical threshold. Synthesized values are labelled as
estimates so a reader never mistakes them for something the server reported.
"""

WARN_SYNTH_RATIO = 0.85


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
        parts.append(f"warning above {_fmt(estimated)}{unit_suffix} (estimated)")
    if threshold.upper_critical is not None:
        parts.append(f"critical above {_fmt(threshold.upper_critical)}{unit_suffix}")

    return "; ".join(parts)
