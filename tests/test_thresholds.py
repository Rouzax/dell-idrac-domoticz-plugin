import model
import thresholds


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
