import model
import thresholds
from tests.fixture_loader import load


def test_describe_upper_critical_with_synthesized_warn():
    th = model.Threshold(upper_critical=98, lower_critical=3)
    text = thresholds.describe(th, "C")
    assert "critical above 98 C" in text
    assert "83.3 C" in text
    assert "estimated" in text.lower()


def test_reported_warn_is_used_and_not_labelled_estimated():
    th = model.Threshold(upper_critical=98, upper_non_critical=84)
    text = thresholds.describe(th, "C")
    assert "warning above 84 C" in text
    assert "estimated" not in text.lower()


def test_describe_lower_thresholds_for_fans():
    th = model.Threshold(lower_critical=480, lower_non_critical=840)
    text = thresholds.describe(th, "RPM")
    assert "warning below 840 RPM" in text
    assert "critical below 480 RPM" in text


def test_describe_returns_empty_when_nothing_is_reported():
    assert thresholds.describe(model.Threshold(), "C") == ""
    assert thresholds.describe(None, "C") == ""


def test_synth_warn_is_none_without_a_critical():
    assert thresholds.synth_warn(None) is None


def test_real_cpu_thresholds_render_with_the_estimate_labelled():
    """The exact string a user reads on the CPU temperature device of the real T550."""
    th = model.parse_thermal_thresholds(load("t550", "thermal"))["CPU1 Temp"]
    assert thresholds.describe(th, "C") == (
        "critical below 3 C; warning above 83.3 C (estimated); critical above 98 C"
    )


def test_real_fan_thresholds_render_descending():
    th = model.parse_thermal_thresholds(load("t550", "thermal"))["System Board Fan1"]
    text = thresholds.describe(th, "RPM")
    assert text == "warning below 840 RPM; critical below 480 RPM"
    # A fan has no upper bound reported, so nothing may be invented for one.
    assert "above" not in text


def _th(lc=None, ln=None, un=None, uc=None):
    return model.Threshold(
        upper_critical=uc, upper_non_critical=un, lower_critical=lc, lower_non_critical=ln
    )


def test_bar_ranges_uses_the_reported_thresholds_as_band_edges():
    """The T550's Inlet Temp reports all four thresholds, so every edge comes from the server.

    Colours are Domoticz's own bar defaults (dzBar.js seedDefaults) plus an amber for the
    warning band, so a plugin-supplied bar looks like a hand-made one.
    """
    bands = thresholds.bar_ranges(_th(lc=-7, ln=3, un=33, uc=42))
    assert [(b["from"], b["to"]) for b in bands] == [
        (-11.9, -7),
        (-7, 3),
        (3, 33),
        (33, 42),
        (42, 46.9),
    ]
    assert [b["color"] for b in bands] == [
        thresholds.BAR_CRITICAL,
        thresholds.BAR_WARNING,
        thresholds.BAR_OK,
        thresholds.BAR_WARNING,
        thresholds.BAR_CRITICAL,
    ]


def test_bar_ranges_skips_bands_whose_thresholds_are_absent():
    """CPU1 Temp reports no lower warning, so there is no lower amber band and none is invented."""
    bands = thresholds.bar_ranges(_th(lc=3, un=83.3, uc=98))
    assert [(b["from"], b["to"], b["color"]) for b in bands] == [
        (-6.5, 3, thresholds.BAR_CRITICAL),
        (3, 83.3, thresholds.BAR_OK),
        (83.3, 98, thresholds.BAR_WARNING),
        (98, 107.5, thresholds.BAR_CRITICAL),
    ]


def test_bar_ranges_needs_both_critical_edges():
    """Without both criticals the axis span cannot be derived, so no bar beats a guessed one."""
    assert thresholds.bar_ranges(_th(lc=3)) is None
    assert thresholds.bar_ranges(_th(uc=98)) is None
    assert thresholds.bar_ranges(None) is None
    assert thresholds.bar_ranges(_th()) is None


def test_bar_ranges_rejects_a_degenerate_span():
    """Equal criticals would make a zero-width axis, which dzBar discards anyway."""
    assert thresholds.bar_ranges(_th(lc=50, uc=50)) is None


def test_bar_ranges_are_contiguous_and_ascending():
    bands = thresholds.bar_ranges(_th(lc=-7, ln=3, un=33, uc=42))
    # Deliberately not strict: pairing a list with its own tail is one shorter by design.
    for earlier, later in zip(bands, bands[1:], strict=False):
        # dzBar draws one continuous axis; a gap would misplace the needle.
        assert earlier["to"] == later["from"]
        assert earlier["from"] < earlier["to"]


def test_floor_bar_ranges_for_a_sensor_where_only_low_is_bad():
    """Fans report lower thresholds only, and no maximum exists anywhere in Redfish.

    Measured on a T550 at 100%: 4920, 4920 and 5520 RPM, so even one chassis has no single
    maximum. The axis top is therefore a user setting, not a guess. Zero is a real floor for
    RPM (a stopped fan), so the bottom is not invented either.
    """
    bands = thresholds.bar_ranges_floor(_th(lc=480, ln=840), 6000)
    assert [(b["from"], b["to"], b["color"]) for b in bands] == [
        (0, 480, thresholds.BAR_CRITICAL),
        (480, 840, thresholds.BAR_WARNING),
        (840, 6000, thresholds.BAR_OK),
    ]


def test_floor_bar_ranges_without_a_warning_threshold():
    bands = thresholds.bar_ranges_floor(_th(lc=480), 6000)
    assert [(b["from"], b["to"], b["color"]) for b in bands] == [
        (0, 480, thresholds.BAR_CRITICAL),
        (480, 6000, thresholds.BAR_OK),
    ]


def test_floor_bar_ranges_needs_a_usable_axis_top():
    """Zero disables fan bars, and a top at or below the thresholds would be nonsense."""
    assert thresholds.bar_ranges_floor(_th(lc=480, ln=840), 0) is None
    assert thresholds.bar_ranges_floor(_th(lc=480, ln=840), 840) is None
    assert thresholds.bar_ranges_floor(_th(lc=480, ln=840), 500) is None
    assert thresholds.bar_ranges_floor(_th(), 6000) is None
    assert thresholds.bar_ranges_floor(None, 6000) is None


def test_a_reading_above_the_axis_top_lands_in_the_last_band():
    """Verified against dzBar.js computeBar: currentIdx starts at the LAST band and the loop only
    breaks when a band's `to` reaches the value, so an over-range value keeps the last colour and
    pct is clamped to 100. For a fan that is green, which is right: low RPM is the fault."""
    bands = thresholds.bar_ranges_floor(_th(lc=480, ln=840), 6000)
    assert bands[-1]["color"] == thresholds.BAR_OK
