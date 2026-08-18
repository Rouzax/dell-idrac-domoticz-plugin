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
