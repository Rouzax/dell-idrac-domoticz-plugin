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


def test_only_graceful_actions_without_the_hard_toggle():
    actions = control.available_actions(ALLOWABLE, allow_hard=False)
    reset_types = [rt for _, rt in actions]
    assert "GracefulShutdown" in reset_types
    assert "ForceOff" not in reset_types
    assert "PowerCycle" not in reset_types


def test_hard_actions_appear_when_enabled():
    reset_types = [rt for _, rt in control.available_actions(ALLOWABLE, allow_hard=True)]
    assert "ForceOff" in reset_types
    assert "PowerCycle" in reset_types


def test_actions_the_server_does_not_advertise_are_dropped():
    actions = control.available_actions(["On", "GracefulShutdown"], allow_hard=True)
    assert [rt for _, rt in actions] == ["On", "GracefulShutdown"]


def test_nmi_is_never_offered_even_though_the_server_allows_it():
    """An NMI crashes the host on purpose. It is not a power action a timer should reach."""
    for allow_hard in (False, True):
        actions = control.available_actions(ALLOWABLE, allow_hard=allow_hard)
        assert "Nmi" not in [rt for _, rt in actions]


def test_level_maps_to_a_reset_type():
    actions = control.available_actions(ALLOWABLE, allow_hard=False)
    assert control.level_to_reset_type(0, actions) is None
    assert control.level_to_reset_type(10, actions) == actions[0][1]
    assert control.level_to_reset_type(20, actions) == actions[1][1]


def test_an_out_of_range_level_is_refused_not_clamped():
    actions = control.available_actions(ALLOWABLE, allow_hard=False)
    assert control.level_to_reset_type(990, actions) is None
    assert control.level_to_reset_type(-10, actions) is None


def test_no_control_devices_when_control_is_off():
    assert control.control_updates(_cfg(allow_control=False), ALLOWABLE, False) == []


def test_control_devices_are_in_the_control_block():
    updates = control.control_updates(_cfg(), ALLOWABLE, identify_on=False)
    assert [u.unit for u in updates] == [control.UNIT_POWER_CONTROL, control.UNIT_IDENTIFY]
    assert updates[0].options["SelectorStyle"] == "1"


def test_identify_reflects_current_state():
    assert control.control_updates(_cfg(), ALLOWABLE, identify_on=True)[1].nvalue == 1
    assert control.control_updates(_cfg(), ALLOWABLE, identify_on=False)[1].nvalue == 0
