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
