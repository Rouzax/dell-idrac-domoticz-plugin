"""Energy counter arithmetic. Pure.

The counter is monotonic by construction: it never decreases and never exceeds an absolute
ceiling. A sub-deadband backward step is absorbed silently, because a source re-reporting a
reading a fraction of a Wh lower is jitter rather than data loss, and warning on it would fill
the log with noise that hides a genuine problem.
"""

COUNTER_DEADBAND_WH = 1.0


def integrate_wh(watts: float, elapsed_seconds: float) -> float:
    if elapsed_seconds <= 0:
        return 0.0
    return float(watts) * float(elapsed_seconds) / 3600.0


def clamp_counter(prev_wh: float, candidate_wh: float, ceiling_wh: float) -> tuple:
    if candidate_wh > ceiling_wh:
        return prev_wh, f"counter held: {candidate_wh:.4f} exceeds ceiling {ceiling_wh:.4f}"
    if candidate_wh >= prev_wh:
        return candidate_wh, None
    if prev_wh - candidate_wh <= COUNTER_DEADBAND_WH:
        return prev_wh, None
    return prev_wh, f"counter held: decrease {prev_wh:.4f} -> {candidate_wh:.4f}"
