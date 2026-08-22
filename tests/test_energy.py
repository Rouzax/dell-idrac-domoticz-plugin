import energy


def test_integrate_wh_converts_watt_seconds():
    assert energy.integrate_wh(3600.0, 1.0) == 1.0
    assert energy.integrate_wh(150.0, 3600.0) == 150.0


def test_integrate_wh_rejects_a_non_positive_interval():
    assert energy.integrate_wh(150.0, -5.0) == 0.0
    assert energy.integrate_wh(150.0, 0.0) == 0.0


def test_clamp_counter_accepts_a_rise():
    value, warning = energy.clamp_counter(100.0, 150.0, ceiling_wh=1_000_000.0)
    assert value == 150.0
    assert warning is None


def test_clamp_counter_holds_a_real_decrease_and_warns():
    value, warning = energy.clamp_counter(150.0, 100.0, ceiling_wh=1_000_000.0)
    assert value == 150.0
    assert warning is not None and "decrease" in warning.lower()


def test_sub_deadband_dip_is_held_silently():
    """Jitter below the deadband is held WITHOUT a warning, so the log does not spam."""
    value, warning = energy.clamp_counter(150.0, 149.5, ceiling_wh=1_000_000.0)
    assert value == 150.0
    assert warning is None


def test_ceiling_breach_is_held_and_warned():
    value, warning = energy.clamp_counter(100.0, 5_000_000.0, ceiling_wh=1_000_000.0)
    assert value == 100.0
    assert warning is not None and "ceiling" in warning.lower()


def test_counter_is_monotonic_across_a_noisy_sequence():
    """The property that matters: a counter fed to Domoticz must never go backwards."""
    value = 0.0
    for candidate in (10.0, 9.8, 25.0, 24.5, 24.9, 40.0, 39.2, 41.0):
        value, _ = energy.clamp_counter(value, candidate, ceiling_wh=1_000_000.0)
    assert value == 41.0


def test_advance_adds_the_integral_and_reports_no_warning():
    value, warning = energy.advance(100.0, 150.0, 3600.0, ceiling_watts=1000.0)
    assert value == 250.0
    assert warning is None


def test_advance_adds_nothing_when_no_time_has_passed():
    value, warning = energy.advance(100.0, 150.0, 0.0, ceiling_watts=1000.0)
    assert value == 100.0
    assert warning is None


def test_advance_holds_a_draw_beyond_the_ceiling_watts():
    value, warning = energy.advance(100.0, 5000.0, 3600.0, ceiling_watts=1000.0)
    assert value == 100.0
    assert warning is not None


def test_implausible_rejects_a_component_drawing_more_than_the_chassis():
    # R7525, powered off: TotalFPGAPower 43 W against SystemPowerConsumption 22 W.
    assert energy.implausible(43.0, 22.0) is True


def test_implausible_accepts_a_supply_carrying_almost_the_whole_load():
    # R750 hot spare: PS1 at 446.5 W against a 461 W total.
    assert energy.implausible(446.5, 461.0) is False


def test_implausible_accepts_anything_when_the_system_figure_is_unknown():
    assert energy.implausible(43.0, None) is False
    assert energy.implausible(43.0, 0.0) is False


def test_has_moved_is_false_until_a_reading_differs_from_the_first():
    assert energy.has_moved(None, 43.0) is False
    assert energy.has_moved(43.0, 43.0) is False
    assert energy.has_moved(43.0, 42.9) is True
