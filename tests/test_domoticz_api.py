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
    names, _, _ = domoticz_api.apply_updates(
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
    names, _, _ = domoticz_api.apply_updates(
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
    names, _, _ = domoticz_api.apply_updates(
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


def test_a_missing_type_attribute_degrades_the_conversion_not_the_poll():
    """Type/SubType are read with getattr precisely because we could not establish the oldest
    Domoticz release exposing them, and the read sits on a path hit every heartbeat. A build
    without them must still write every unit's values instead of raising AttributeError and
    taking the whole poll down with it."""
    domoticz_stub.Devices.clear()
    domoticz_api.apply_updates(
        domoticz_stub.Devices,
        _ids("dev"),
        [_update(1, type_name="Usage"), _update(2, type_name="Alert", svalue="OK")],
        {},
    )
    unit = domoticz_stub.Devices["dev"].Units[1]
    del unit.Type
    del unit.SubType
    domoticz_api.apply_updates(
        domoticz_stub.Devices,
        _ids("dev"),
        [
            _update(1, type_name="kWh", svalue="144;2500.5"),
            _update(2, type_name="Alert", svalue="Warning"),
        ],
        {},
    )
    assert unit.sValue == "144;2500.5"
    assert domoticz_stub.Devices["dev"].Units[2].sValue == "Warning"


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
    names, _, _ = domoticz_api.apply_updates(domoticz_stub.Devices, _ids("dev"), [update], {})
    unit = domoticz_stub.Devices["dev"].Units[4]
    unit.Color = '{"temp":[{"from":0,"to":99,"color":"#123456"}]}'
    domoticz_api.apply_updates(domoticz_stub.Devices, _ids("dev"), [update], names)
    assert unit.Color == '{"temp":[{"from":0,"to":99,"color":"#123456"}]}'


def _ids(dev_id):
    """Every family mapped to one DeviceID, so a test can keep using a single device."""
    return dict.fromkeys(planner.DEVICE_FAMILIES, dev_id)


def _life(color):
    return planner.DeviceUpdate(
        unit=4, type_name="Percentage", name="SSD Life", nvalue=0, svalue="100", color=color
    )


def test_bands_follow_a_changed_setting():
    """Bands are derived from settings and hardware thresholds, so they must not be frozen.

    Writing them only at creation meant changing Drive life warning left every existing bar on
    the old threshold, with nothing to show the setting had taken effect.
    """
    domoticz_stub.Devices.clear()
    first = '{"a":1}'
    names, colors, _ = domoticz_api.apply_updates(
        domoticz_stub.Devices, _ids("dev"), [_life(first)], {}, {}
    )
    unit = domoticz_stub.Devices["dev"].Units[4]
    assert unit.Color == first
    second = '{"a":2}'
    domoticz_api.apply_updates(domoticz_stub.Devices, _ids("dev"), [_life(second)], names, colors)
    assert unit.Color == second


def test_bands_a_user_edited_are_never_overwritten():
    """Same ownership rule as device names: once you change it, it is yours."""
    domoticz_stub.Devices.clear()
    names, colors, _ = domoticz_api.apply_updates(
        domoticz_stub.Devices, _ids("dev"), [_life('{"a":1}')], {}, {}
    )
    unit = domoticz_stub.Devices["dev"].Units[4]
    unit.Color = '{"mine":true}'
    domoticz_api.apply_updates(
        domoticz_stub.Devices, _ids("dev"), [_life('{"a":2}')], names, colors
    )
    assert unit.Color == '{"mine":true}'


def test_unchanged_bands_are_not_rewritten_every_poll():
    domoticz_stub.Devices.clear()
    names, colors, _ = domoticz_api.apply_updates(
        domoticz_stub.Devices, _ids("dev"), [_life('{"a":1}')], {}, {}
    )
    unit = domoticz_stub.Devices["dev"].Units[4]
    calls = []
    unit.Update = lambda **kw: calls.append(kw)
    domoticz_api.apply_updates(
        domoticz_stub.Devices, _ids("dev"), [_life('{"a":1}')], names, colors
    )
    assert not [c for c in calls if c.get("UpdateProperties")]


def _domoticz_db(tmp_path, rows):
    """A stand-in for domoticz.db carrying just the two tables and columns we read.

    Built with real sqlite rather than a mock: the point of the check is that it survives
    contact with an actual database file, including being opened read-only.
    """
    import sqlite3

    path = tmp_path / "domoticz.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE Hardware ([ID] INTEGER PRIMARY KEY, [Name] VARCHAR(200) NOT NULL)")
    con.execute(
        "CREATE TABLE DeviceStatus ([ID] INTEGER PRIMARY KEY, [HardwareID] INTEGER NOT NULL, "
        "[Name] VARCHAR(100) DEFAULT Unknown)"
    )
    con.execute("INSERT INTO Hardware VALUES (1, 'iDRAC T550')")
    con.execute("INSERT INTO Hardware VALUES (2, 'iDRAC R750')")
    for hardware_id, name in rows:
        con.execute(
            "INSERT INTO DeviceStatus (HardwareID, Name) VALUES (?, ?)", (hardware_id, name)
        )
    con.commit()
    con.close()
    return str(path)


def test_a_name_owned_by_another_hardware_entry_is_reported(tmp_path):
    """The collision that motivated the whole feature: a second install of this plugin, with no
    prefix set, planning the same names as the first."""
    db = _domoticz_db(tmp_path, [(1, "System Health"), (1, "Inlet Temp"), (1, "Fan1")])
    found = domoticz_api.names_used_by_other_hardware(db, 2, ["System Health", "Inlet Temp", "New"])
    assert found == (("Inlet Temp", "iDRAC T550"), ("System Health", "iDRAC T550"))


def test_our_own_devices_are_never_reported_as_a_collision(tmp_path):
    """On every poll after the first, our own names are in the table. Matching them would make
    the plugin warn about itself forever."""
    db = _domoticz_db(tmp_path, [(2, "System Health"), (2, "Inlet Temp")])
    assert domoticz_api.names_used_by_other_hardware(db, 2, ["System Health"]) == ()


def test_a_collision_with_unrelated_hardware_is_reported_too(tmp_path):
    """Not just a second copy of this plugin: any device in the install can own the name."""
    db = _domoticz_db(tmp_path, [(1, "Uptime")])
    found = domoticz_api.names_used_by_other_hardware(db, 9, ["Uptime"])
    assert found == (("Uptime", "iDRAC T550"),)


def test_an_unreadable_database_reports_nothing_instead_of_failing(tmp_path):
    """This runs inside the heartbeat. A locked or missing database must cost a debug line, not
    the poll."""
    assert domoticz_api.names_used_by_other_hardware(str(tmp_path / "nope.db"), 1, ["X"]) == ()
    assert domoticz_api.names_used_by_other_hardware("", 1, ["X"]) == ()


def test_no_query_is_made_for_an_empty_name_list(tmp_path):
    db = _domoticz_db(tmp_path, [(1, "System Health")])
    assert domoticz_api.names_used_by_other_hardware(db, 2, []) == ()


def _stored_unit(dev_id, unit):
    return domoticz_stub.Devices[dev_id].Units[unit]


def test_a_changed_description_is_actually_persisted():
    """A PSU is a Usage device, so its DESCRIPTION is the only place its health can appear.
    Written once at creation and never again, a supply that failed after the device existed read
    "OK" for ever. Verified on live hardware: the iDRAC reported PS1 Critical at 0 W while
    Domoticz still stored OK.

    Asserted against `stored`, not against the attribute: assigning Unit.Description does
    nothing on its own, the core persists it only under UpdateProperties.
    """
    names, colors, descriptions = domoticz_api.apply_updates(
        domoticz_stub.Devices, _ids("dellidrac_1"), [_update(1, description="OK")], {}
    )
    unit = _stored_unit("dellidrac_1", 1)
    assert unit.stored["Description"] == "OK"

    domoticz_api.apply_updates(
        domoticz_stub.Devices,
        _ids("dellidrac_1"),
        [_update(1, description="Critical")],
        names,
        colors,
        descriptions,
    )
    assert unit.stored["Description"] == "Critical"


def test_a_user_edited_description_is_never_overwritten():
    """The same rule names and bar bands already follow: what the user typed survives."""
    names, colors, descriptions = domoticz_api.apply_updates(
        domoticz_stub.Devices, _ids("dellidrac_1"), [_update(1, description="OK")], {}
    )
    unit = _stored_unit("dellidrac_1", 1)
    unit.Description = "feeds the rack PDU on the left"
    unit.stored["Description"] = unit.Description

    domoticz_api.apply_updates(
        domoticz_stub.Devices,
        _ids("dellidrac_1"),
        [_update(1, description="Critical")],
        names,
        colors,
        descriptions,
    )
    assert unit.stored["Description"] == "feeds the rack PDU on the left"


def test_an_unchanged_description_is_not_rewritten_every_poll():
    """This runs on every unit on every heartbeat, so it must not write when nothing moved."""
    names, colors, descriptions = domoticz_api.apply_updates(
        domoticz_stub.Devices, _ids("dellidrac_1"), [_update(1, description="OK")], {}
    )
    unit = _stored_unit("dellidrac_1", 1)
    unit.updates.clear()
    domoticz_api.apply_updates(
        domoticz_stub.Devices,
        _ids("dellidrac_1"),
        [_update(1, description="OK")],
        names,
        colors,
        descriptions,
    )
    assert not any(call.get("UpdateProperties") for call in unit.updates)


def test_a_device_with_no_description_is_left_alone():
    """Most devices carry no description at all; an empty one must not clear a user's note."""
    names, colors, descriptions = domoticz_api.apply_updates(
        domoticz_stub.Devices, _ids("dellidrac_1"), [_update(1, description="")], {}
    )
    unit = _stored_unit("dellidrac_1", 1)
    unit.Description = "hand written"
    unit.stored["Description"] = unit.Description
    domoticz_api.apply_updates(
        domoticz_stub.Devices,
        _ids("dellidrac_1"),
        [_update(1, description="")],
        names,
        colors,
        descriptions,
    )
    assert unit.stored["Description"] == "hand written"


def test_a_description_from_before_ownership_tracking_is_adopted_not_frozen():
    """The upgrade path. An install created its devices under a version that wrote descriptions
    only at creation, so the health text is stale AND there is no ownership record for it.
    Treating "no record" as "the user's" would leave that text frozen for ever.
    """
    domoticz_api.apply_updates(
        domoticz_stub.Devices, _ids("dellidrac_1"), [_update(1, description="OK")], {}
    )
    unit = _stored_unit("dellidrac_1", 1)
    # Simulate the upgrade: the device exists and carries a description, the map is empty.
    _, _, descriptions = domoticz_api.apply_updates(
        domoticz_stub.Devices, _ids("dellidrac_1"), [_update(1, description="Critical")], {}
    )
    assert unit.stored["Description"] == "Critical"
    # And it is recorded from now on, so the next edit by the user does survive.
    assert descriptions[domoticz_api.name_key("dellidrac_1", 1)] == "Critical"


def test_apply_converts_a_usage_device_to_kwh_in_place():
    domoticz_api.apply_updates(
        domoticz_stub.Devices,
        _ids("dellidrac_1_system"),
        [_update(14, name="CPU Power", type_name="Usage", svalue="41.0")],
        {},
    )
    unit = domoticz_stub.Devices["dellidrac_1_system"].Units[14]
    created_id = id(unit)
    assert (unit.Type, unit.SubType) == (248, 1)

    domoticz_api.apply_updates(
        domoticz_stub.Devices,
        _ids("dellidrac_1_system"),
        [
            _update(
                14,
                name="CPU Power",
                type_name="kWh",
                svalue="41.0;12.5",
                options={"EnergyMeterMode": "0"},
            )
        ],
        {"dellidrac_1_system:14": "CPU Power"},
    )
    unit = domoticz_stub.Devices["dellidrac_1_system"].Units[14]
    # Same object, so same device row: idx, name and history all survive.
    assert id(unit) == created_id
    assert unit.Name == "CPU Power"
    assert (unit.Type, unit.SubType) == (243, 29)
    # The real values are written immediately after the conversion reset them.
    assert unit.sValue == "41.0;12.5"
    assert unit.stored["Options"] == {"EnergyMeterMode": "0"}


def test_apply_converts_back_to_usage_when_the_setting_is_turned_off():
    domoticz_api.apply_updates(
        domoticz_stub.Devices,
        _ids("dellidrac_1_system"),
        [_update(14, name="CPU Power", type_name="kWh", svalue="41.0;12.5")],
        {},
    )
    domoticz_api.apply_updates(
        domoticz_stub.Devices,
        _ids("dellidrac_1_system"),
        [_update(14, name="CPU Power", type_name="Usage", svalue="41.0")],
        {"dellidrac_1_system:14": "CPU Power"},
    )
    unit = domoticz_stub.Devices["dellidrac_1_system"].Units[14]
    assert (unit.Type, unit.SubType) == (248, 1)
    assert unit.sValue == "41.0"


def test_apply_does_not_convert_a_unit_that_already_has_the_right_type():
    domoticz_api.apply_updates(
        domoticz_stub.Devices,
        _ids("dellidrac_1_system"),
        [_update(14, name="CPU Power", type_name="kWh", svalue="41.0;12.5")],
        {},
    )
    unit = domoticz_stub.Devices["dellidrac_1_system"].Units[14]
    unit.updates.clear()
    domoticz_api.apply_updates(
        domoticz_stub.Devices,
        _ids("dellidrac_1_system"),
        [_update(14, name="CPU Power", type_name="kWh", svalue="41.0;13.5")],
        {"dellidrac_1_system:14": "CPU Power"},
    )
    assert not any("TypeName" in call for call in unit.updates)


def test_apply_never_converts_a_device_whose_type_is_not_convertible():
    domoticz_api.apply_updates(
        domoticz_stub.Devices,
        _ids("dellidrac_1_system"),
        [_update(2, name="System Health", type_name="Alert", nvalue=1, svalue="OK")],
        {},
    )
    unit = domoticz_stub.Devices["dellidrac_1_system"].Units[2]
    unit.updates.clear()
    domoticz_api.apply_updates(
        domoticz_stub.Devices,
        _ids("dellidrac_1_system"),
        [_update(2, name="System Health", type_name="Alert", nvalue=1, svalue="OK")],
        {"dellidrac_1_system:2": "System Health"},
    )
    assert not any("TypeName" in call for call in unit.updates)
