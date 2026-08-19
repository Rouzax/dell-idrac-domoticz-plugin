import config
import control


def _cfg(**kw):
    base = {
        "address": "h",
        "username": "u",
        "password": "p",
        "allow_control": True,
        "allow_hard_power": False,
        "poll_interval": 30,
        "slow_every": 10,
        "enable_drives": True,
        "enable_volumes": True,
        "enable_nics": True,
        "enable_psus": True,
        "drive_life_floor": 10,
        "fan_bar_max": 6000,
        "enable_drive_life": False,
        "setup_telemetry": False,
        "verify_tls": False,
        "request_timeout": 30,
        "debug_level": 0,
    }
    base.update(kw)
    return config.PluginConfig(**base)


ALLOWABLE = [
    "On",
    "ForceOff",
    "ForceRestart",
    "GracefulRestart",
    "GracefulShutdown",
    "PushPowerButton",
    "Nmi",
    "PowerCycle",
]


def test_a_level_always_means_the_same_action():
    """The safety property this module exists for.

    Domoticz stores selector levels in scenes and timers that are replayed for years. A level's
    meaning must not depend on what the server happens to advertise today.
    """
    assert control.level_to_reset_type(10) == "On"
    assert control.level_to_reset_type(20) == "GracefulShutdown"
    assert control.level_to_reset_type(30) == "GracefulRestart"
    assert control.level_to_reset_type(40) == "ForceOff"
    assert control.level_to_reset_type(50) == "PowerCycle"


def test_the_mapping_does_not_shift_when_the_advertised_set_shrinks():
    """Regression guard: a shrinking AllowableValues must not renumber anything."""
    for allowable in (ALLOWABLE, ["On", "ForceOff"], [], ["GracefulShutdown"]):
        assert control.level_to_reset_type(30) == "GracefulRestart"
        assert control.level_to_reset_type(40) == "ForceOff"
        # Availability changes; meaning does not.
        control.is_available("GracefulRestart", allowable, True)


def test_out_of_range_and_malformed_levels_are_refused():
    for bad in (0, -10, 15, 999, 60, None, "x"):
        assert control.level_to_reset_type(bad) is None


def test_nmi_is_never_offered_even_though_the_server_allows_it():
    """An NMI crashes the host on purpose. No level maps to it, under any setting."""
    mapped = {control.level_to_reset_type(lvl) for lvl in range(10, 200, 10)}
    assert "Nmi" not in mapped
    assert not any(rt == "Nmi" for _, rt in control.ACTION_SLOTS)


def test_hard_actions_are_unavailable_unless_the_gate_is_on():
    assert control.is_available("ForceOff", ALLOWABLE, allow_hard=False) is False
    assert control.is_available("PowerCycle", ALLOWABLE, allow_hard=False) is False
    assert control.is_available("ForceOff", ALLOWABLE, allow_hard=True) is True


def test_an_action_the_server_does_not_advertise_is_unavailable():
    assert control.is_available("GracefulRestart", ["On"], allow_hard=True) is False
    assert control.is_available("On", ["On"], allow_hard=True) is True


def test_nothing_is_available_when_the_server_advertised_nothing():
    for rt in ("On", "GracefulShutdown", "ForceOff"):
        assert control.is_available(rt, [], allow_hard=True) is False


def test_level_names_always_have_every_slot_so_positions_never_move():
    full = control.level_names(ALLOWABLE, allow_hard=True).split("|")
    limited = control.level_names(["On"], allow_hard=False).split("|")
    assert len(full) == len(limited) == len(control.ACTION_SLOTS) + 1
    assert full[0] == limited[0] == "Idle"
    # Same position, same action, regardless of availability.
    assert limited[4].startswith("Force Off")
    assert "(unavailable)" in limited[4]
    assert limited[1] == "Power On"


def test_no_control_devices_when_control_is_off():
    assert control.control_updates(_cfg(allow_control=False), ALLOWABLE, False) == []


def test_control_devices_are_in_the_control_block():
    updates = control.control_updates(_cfg(), ALLOWABLE, identify_on=False)
    assert [u.unit for u in updates] == [control.UNIT_POWER_CONTROL, control.UNIT_IDENTIFY]
    assert updates[0].options["SelectorStyle"] == "1"


def test_identify_reflects_current_state():
    assert control.control_updates(_cfg(), ALLOWABLE, identify_on=True)[1].nvalue == 1
    assert control.control_updates(_cfg(), ALLOWABLE, identify_on=False)[1].nvalue == 0
