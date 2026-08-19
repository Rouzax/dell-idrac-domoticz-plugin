import domoticz_api
import planner
from tests import domoticz_stub


def _update(unit, name="X", type_name="Alert", nvalue=1, svalue="OK", description="", options=None):
    return planner.DeviceUpdate(
        unit=unit,
        type_name=type_name,
        name=name,
        options=options or {},
        nvalue=nvalue,
        svalue=svalue,
        description=description,
    )


def test_device_id_is_namespaced_by_hardware():
    assert domoticz_api.device_id(7, planner.DEVICE_SYSTEM) == "dellidrac_7_system"
    # One DeviceID per family, so each gets its own 1-255 unit space.
    assert domoticz_api.device_id(7, planner.DEVICE_GPU) == "dellidrac_7_gpu"
    assert len({domoticz_api.device_id(7, f) for f in planner.DEVICE_FAMILIES}) == len(
        planner.DEVICE_FAMILIES
    )


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
            _ids("dellidrac_1"),
            [_update(40), _update(1), _update(100)],
            {},
        )
    finally:
        domoticz_stub.Unit.Create = original
    assert created == [1, 40, 100]


def test_apply_returns_auto_names_for_created_units():
    names = domoticz_api.apply_updates(
        domoticz_stub.Devices, _ids("dellidrac_1"), [_update(1, name="Server Power")], {}
    )
    assert names[domoticz_api.name_key("dellidrac_1", 1)] == "Server Power"


def test_allow_create_false_does_not_create():
    domoticz_api.apply_updates(
        domoticz_stub.Devices, _ids("dellidrac_1"), [_update(1)], {}, allow_create=False
    )
    assert "dellidrac_1" not in domoticz_stub.Devices


def test_existing_unit_gets_new_values():
    domoticz_api.apply_updates(
        domoticz_stub.Devices, _ids("dellidrac_1"), [_update(1, svalue="OK")], {}
    )
    domoticz_api.apply_updates(
        domoticz_stub.Devices,
        _ids("dellidrac_1"),
        [_update(1, svalue="Warning", nvalue=3)],
        {domoticz_api.name_key("dellidrac_1", 1): "X"},
    )
    unit = domoticz_stub.Devices["dellidrac_1"].Units[1]
    assert unit.sValue == "Warning"
    assert unit.nValue == 3


def test_a_user_rename_is_never_overwritten():
    domoticz_api.apply_updates(
        domoticz_stub.Devices, _ids("dellidrac_1"), [_update(1, name="Auto")], {}
    )
    unit = domoticz_stub.Devices["dellidrac_1"].Units[1]
    unit.Name = "My Server"
    names = domoticz_api.apply_updates(
        domoticz_stub.Devices,
        _ids("dellidrac_1"),
        [_update(1, name="Auto2")],
        {domoticz_api.name_key("dellidrac_1", 1): "Auto"},
    )
    assert unit.Name == "My Server"
    assert names[domoticz_api.name_key("dellidrac_1", 1)] == "Auto"


def test_an_owned_name_is_renamed_when_the_plugin_changes_it():
    domoticz_api.apply_updates(
        domoticz_stub.Devices, _ids("dellidrac_1"), [_update(1, name="Auto")], {}
    )
    names = domoticz_api.apply_updates(
        domoticz_stub.Devices,
        _ids("dellidrac_1"),
        [_update(1, name="Auto2")],
        {domoticz_api.name_key("dellidrac_1", 1): "Auto"},
    )
    assert domoticz_stub.Devices["dellidrac_1"].Units[1].Name == "Auto2"
    assert names[domoticz_api.name_key("dellidrac_1", 1)] == "Auto2"


def test_there_is_no_mark_timed_out():
    """Domoticz does its own staleness detection and Unit has no TimedOut member.

    Writing one would raise against real Domoticz on a path reached every heartbeat.
    """
    assert not hasattr(domoticz_api, "mark_timed_out")


def test_apply_updates_never_touches_timedout():
    domoticz_api.apply_updates(domoticz_stub.Devices, _ids("dellidrac_1"), [_update(1)], {})
    domoticz_api.apply_updates(
        domoticz_stub.Devices,
        _ids("dellidrac_1"),
        [_update(1)],
        {domoticz_api.name_key("dellidrac_1", 1): "X"},
    )
    assert domoticz_stub.Devices["dellidrac_1"].Units[1].TimedOut == 0


def test_an_unreadable_counter_returns_none_not_zero():
    """None means unknown. Zero would reset the baseline and drag the counter backwards."""
    domoticz_api.apply_updates(
        domoticz_stub.Devices,
        _ids("dellidrac_1"),
        [_update(1, type_name="kWh", svalue="144;not-a-number")],
        {},
    )
    assert domoticz_api.read_prev_counter_wh(domoticz_stub.Devices, "dellidrac_1", 1) is None


def test_a_counter_with_extra_semicolons_still_reads():
    domoticz_api.apply_updates(
        domoticz_stub.Devices,
        _ids("dellidrac_1"),
        [_update(1, type_name="kWh", svalue="144;2500.5;extra")],
        {},
    )
    assert domoticz_api.read_prev_counter_wh(domoticz_stub.Devices, "dellidrac_1", 1) == 2500.5


def test_read_prev_counter_wh_parses_the_power_energy_svalue():
    domoticz_api.apply_updates(
        domoticz_stub.Devices,
        _ids("dellidrac_1"),
        [_update(1, type_name="kWh", svalue="144;2500.5")],
        {},
    )
    assert domoticz_api.read_prev_counter_wh(domoticz_stub.Devices, "dellidrac_1", 1) == 2500.5


def test_read_prev_counter_wh_is_zero_when_absent_or_malformed():
    assert domoticz_api.read_prev_counter_wh(domoticz_stub.Devices, "dellidrac_1", 99) == 0.0


def _spy_on_update():
    """Record Update() kwargs. The stub's Update is a no-op, so this is the only way to see them."""
    calls = []
    original = domoticz_stub.Unit.Update

    def spy(self, **kw):
        calls.append(kw)
        return original(self, **kw)

    domoticz_stub.Unit.Update = spy
    return calls, original


def test_options_are_refreshed_when_they_change():
    """The control selector recomputes its menu every poll.

    Setting Options only at creation would freeze the labels, so the UI could name an action that
    is not the one a level actually performs.
    """
    domoticz_api.apply_updates(
        domoticz_stub.Devices,
        _ids("dellidrac_1"),
        [_update(200, options={"LevelNames": "Idle|Power On"})],
        {},
    )
    calls, original = _spy_on_update()
    try:
        domoticz_api.apply_updates(
            domoticz_stub.Devices,
            _ids("dellidrac_1"),
            [_update(200, options={"LevelNames": "Idle|Power On (unavailable)"})],
            {"200": "X"},
        )
    finally:
        domoticz_stub.Unit.Update = original
    unit = domoticz_stub.Devices["dellidrac_1"].Units[200]
    assert unit.Options == {"LevelNames": "Idle|Power On (unavailable)"}
    assert any(kw.get("UpdateOptions") for kw in calls), "must ask Domoticz to persist Options"


def test_options_are_not_rewritten_when_unchanged():
    """Steady state must not issue a device write on every poll."""
    opts = {"LevelNames": "Idle|Power On"}
    domoticz_api.apply_updates(
        domoticz_stub.Devices, _ids("dellidrac_1"), [_update(200, options=dict(opts))], {}
    )
    calls, original = _spy_on_update()
    try:
        domoticz_api.apply_updates(
            domoticz_stub.Devices,
            _ids("dellidrac_1"),
            [_update(200, options=dict(opts))],
            {"200": "X"},
        )
    finally:
        domoticz_stub.Unit.Update = original
    assert not any(kw.get("UpdateOptions") for kw in calls)


def test_a_device_with_no_options_is_untouched_by_the_refresh():
    """apply_updates is shared by every device; only ones declaring options may be rewritten."""
    domoticz_api.apply_updates(domoticz_stub.Devices, _ids("dellidrac_1"), [_update(4)], {})
    calls, original = _spy_on_update()
    try:
        domoticz_api.apply_updates(
            domoticz_stub.Devices, _ids("dellidrac_1"), [_update(4, svalue="53")], {"4": "X"}
        )
    finally:
        domoticz_stub.Unit.Update = original
    assert not any(kw.get("UpdateOptions") for kw in calls)


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


def test_bar_ranges_are_written_at_creation():
    """Color is NOT a constructor keyword on DomoticzEx.Unit.

    Checked against the core: CUnitEx's init kwlist (hardware/plugins/PythonObjectEx.cpp) has no
    "color" member, so Domoticz.Unit(Color=...) would be silently dropped. Create() does persist
    self->Color into the INSERT, so it has to be assigned on the object first.
    """
    domoticz_stub.Devices.clear()
    update = planner.DeviceUpdate(
        unit=4,
        type_name="Temperature",
        name="Inlet Temp",
        nvalue=0,
        svalue="27.0",
        color='{"temp":[{"from":0,"to":40,"color":"#66bb6a"}]}',
    )
    domoticz_api.apply_updates(domoticz_stub.Devices, _ids("dev"), [update], {})
    assert domoticz_stub.Devices["dev"].Units[4].Color == update.color


def test_bar_ranges_are_never_rewritten_on_an_existing_device():
    """Same rule as icons: bands a user tuned by hand must survive every later poll."""
    domoticz_stub.Devices.clear()
    update = planner.DeviceUpdate(
        unit=4,
        type_name="Temperature",
        name="Inlet Temp",
        nvalue=0,
        svalue="27.0",
        color='{"temp":[{"from":0,"to":40,"color":"#66bb6a"}]}',
    )
    names = domoticz_api.apply_updates(domoticz_stub.Devices, _ids("dev"), [update], {})
    unit = domoticz_stub.Devices["dev"].Units[4]
    unit.Color = '{"temp":[{"from":0,"to":99,"color":"#123456"}]}'
    domoticz_api.apply_updates(domoticz_stub.Devices, _ids("dev"), [update], names)
    assert unit.Color == '{"temp":[{"from":0,"to":99,"color":"#123456"}]}'


def _ids(dev_id):
    """Every family mapped to one DeviceID, so a test can keep using a single device."""
    return dict.fromkeys(planner.DEVICE_FAMILIES, dev_id)
