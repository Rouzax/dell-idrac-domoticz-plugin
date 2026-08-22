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


# A component cannot draw more than the chassis it sits in. The margin is not headroom for the
# internal rails, which sit far below the total: it is there because a single power supply
# carries nearly the whole load, and the system figure may come from the board sensor, which
# excludes the supplies' own conversion loss. Measured on the fleet: it rejects an R7525
# reporting 43 W of FPGA power while the whole machine drew 22 W, and clears an R750 supply at
# 446.5 W against a 461 W total.
CHASSIS_HEADROOM = 1.5


def implausible(watts: float, system_watts) -> bool:
    """True when a component claims more power than the whole machine is drawing.

    An unknown or non-positive system figure returns False: with nothing to compare against,
    refusing to count would be a guess in the other direction.
    """
    if system_watts is None or float(system_watts) <= 0:
        return False
    return float(watts) > float(system_watts) * CHASSIS_HEADROOM


def advance(prev_wh: float, watts: float, elapsed_seconds: float, ceiling_watts: float) -> tuple:
    """One counter step: integrate, then clamp. Returns (counter_wh, warning or None)."""
    candidate = prev_wh + integrate_wh(watts, elapsed_seconds)
    ceiling = prev_wh + integrate_wh(ceiling_watts, elapsed_seconds)
    return clamp_counter(prev_wh, candidate, ceiling_wh=ceiling)
