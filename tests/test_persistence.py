import persistence


def test_round_trip_preserves_every_field():
    state = persistence.PluginState(
        unit_alloc={"Disk.Bay.0": 100},
        auto_names={"1": "Server Power"},
        base_wh={"1": 12.5},
        control_shown=True,
        energy_scale=1.0,
    )
    restored = persistence.loads(persistence.dumps(state))
    assert restored == state


def test_empty_text_yields_defaults():
    state = persistence.loads("")
    assert state.unit_alloc == {}
    assert state.energy_scale is None
    assert state.control_shown is False


def test_migrate_fills_missing_keys():
    raw = persistence.migrate({"unit_alloc": {"a": 1}})
    assert raw["control_shown"] is False
    assert raw["energy_scale"] is None
    assert raw["version"] == persistence.STATE_VERSION


def test_loads_tolerates_a_payload_from_a_future_field_set():
    text = '{"version":1,"unit_alloc":{},"unknown_future_key":123}'
    assert persistence.loads(text).unit_alloc == {}
