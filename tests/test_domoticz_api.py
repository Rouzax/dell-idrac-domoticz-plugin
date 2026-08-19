import domoticz_api
import planner
from tests import domoticz_stub


def _update(unit, name="X", type_name="Alert", nvalue=1, svalue="OK", description=""):
    return planner.DeviceUpdate(
        unit=unit,
        type_name=type_name,
        name=name,
        nvalue=nvalue,
        svalue=svalue,
        description=description,
    )


def test_device_id_is_namespaced_by_hardware():
    assert domoticz_api.device_id(7) == "dellidrac_7"


def test_apply_creates_units_in_ascending_order():
    created = []
    original = domoticz_stub.Unit.Create

    def spy(self):
        created.append(self.Unit)
        original(self)

    domoticz_stub.Unit.Create = spy
    try:
        domoticz_api.apply_updates(
            domoticz_stub.Devices,
            "dellidrac_1",
            [_update(40), _update(1), _update(100)],
            {},
        )
    finally:
        domoticz_stub.Unit.Create = original
    assert created == [1, 40, 100]


def test_apply_returns_auto_names_for_created_units():
    names = domoticz_api.apply_updates(
        domoticz_stub.Devices, "dellidrac_1", [_update(1, name="Server Power")], {}
    )
    assert names["1"] == "Server Power"


def test_allow_create_false_does_not_create():
    domoticz_api.apply_updates(
        domoticz_stub.Devices, "dellidrac_1", [_update(1)], {}, allow_create=False
    )
    assert "dellidrac_1" not in domoticz_stub.Devices


def test_existing_unit_gets_new_values():
    domoticz_api.apply_updates(domoticz_stub.Devices, "dellidrac_1", [_update(1, svalue="OK")], {})
    domoticz_api.apply_updates(
        domoticz_stub.Devices,
        "dellidrac_1",
        [_update(1, svalue="Warning", nvalue=3)],
        {"1": "X"},
    )
    unit = domoticz_stub.Devices["dellidrac_1"].Units[1]
    assert unit.sValue == "Warning"
    assert unit.nValue == 3


def test_a_user_rename_is_never_overwritten():
    domoticz_api.apply_updates(domoticz_stub.Devices, "dellidrac_1", [_update(1, name="Auto")], {})
    unit = domoticz_stub.Devices["dellidrac_1"].Units[1]
    unit.Name = "My Server"
    names = domoticz_api.apply_updates(
        domoticz_stub.Devices, "dellidrac_1", [_update(1, name="Auto2")], {"1": "Auto"}
    )
    assert unit.Name == "My Server"
    assert names["1"] == "Auto"


def test_an_owned_name_is_renamed_when_the_plugin_changes_it():
    domoticz_api.apply_updates(domoticz_stub.Devices, "dellidrac_1", [_update(1, name="Auto")], {})
    names = domoticz_api.apply_updates(
        domoticz_stub.Devices, "dellidrac_1", [_update(1, name="Auto2")], {"1": "Auto"}
    )
    assert domoticz_stub.Devices["dellidrac_1"].Units[1].Name == "Auto2"
    assert names["1"] == "Auto2"


def test_there_is_no_mark_timed_out():
    """Domoticz does its own staleness detection and Unit has no TimedOut member.

    Writing one would raise against real Domoticz on a path reached every heartbeat.
    """
    assert not hasattr(domoticz_api, "mark_timed_out")


def test_apply_updates_never_touches_timedout():
    domoticz_api.apply_updates(domoticz_stub.Devices, "dellidrac_1", [_update(1)], {})
    domoticz_api.apply_updates(domoticz_stub.Devices, "dellidrac_1", [_update(1)], {"1": "X"})
    assert domoticz_stub.Devices["dellidrac_1"].Units[1].TimedOut == 0


def test_an_unreadable_counter_returns_none_not_zero():
    """None means unknown. Zero would reset the baseline and drag the counter backwards."""
    domoticz_api.apply_updates(
        domoticz_stub.Devices,
        "dellidrac_1",
        [_update(1, type_name="kWh", svalue="144;not-a-number")],
        {},
    )
    assert domoticz_api.read_prev_counter_wh(domoticz_stub.Devices, "dellidrac_1", 1) is None


def test_a_counter_with_extra_semicolons_still_reads():
    domoticz_api.apply_updates(
        domoticz_stub.Devices,
        "dellidrac_1",
        [_update(1, type_name="kWh", svalue="144;2500.5;extra")],
        {},
    )
    assert domoticz_api.read_prev_counter_wh(domoticz_stub.Devices, "dellidrac_1", 1) == 2500.5


def test_read_prev_counter_wh_parses_the_power_energy_svalue():
    domoticz_api.apply_updates(
        domoticz_stub.Devices,
        "dellidrac_1",
        [_update(1, type_name="kWh", svalue="144;2500.5")],
        {},
    )
    assert domoticz_api.read_prev_counter_wh(domoticz_stub.Devices, "dellidrac_1", 1) == 2500.5


def test_read_prev_counter_wh_is_zero_when_absent_or_malformed():
    assert domoticz_api.read_prev_counter_wh(domoticz_stub.Devices, "dellidrac_1", 99) == 0.0


def test_state_round_trips_through_configuration():
    state = domoticz_api.load_state()
    state.unit_alloc["Fan.Embedded.1"] = 40
    domoticz_api.save_state(state)
    assert domoticz_api.load_state().unit_alloc == {"Fan.Embedded.1": 40}


def test_save_state_preserves_other_configuration_keys():
    import DomoticzEx as Domoticz

    Domoticz.Configuration({"other": "keep"})
    domoticz_api.save_state(domoticz_api.load_state())
    assert Domoticz.Configuration()["other"] == "keep"


def test_log_redacted_replaces_the_secret():
    seen = []
    domoticz_api.log_redacted(seen.append, "password is hunter2", "hunter2")
    assert "hunter2" not in seen[0]
