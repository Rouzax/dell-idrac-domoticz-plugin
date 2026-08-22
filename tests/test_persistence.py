import json

import pytest

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


@pytest.mark.parametrize(
    "text",
    ["not json at all", "{trunc", "[1,2,3]", "null", "42", '"a string"', "   ", "\t\n"],
)
def test_loads_never_raises_on_an_unusable_payload(text):
    """This value comes from a DB column and is read during onStart. A raise there is fatal."""
    assert persistence.loads(text) == persistence.PluginState()


def test_wrong_typed_fields_are_dropped_rather_than_corrupting_state():
    text = json.dumps(
        {
            "unit_alloc": [1, 2, 3],
            "auto_names": {"1": 7},
            "base_wh": {"1": "12.5", "2": 3},
            "control_shown": "yes",
            "energy_scale": "fast",
        }
    )
    state = persistence.loads(text)
    assert state.unit_alloc == {}
    assert state.auto_names == {}
    assert state.base_wh == {"2": 3.0}
    assert state.control_shown is False
    assert state.energy_scale is None


def test_realistic_redfish_ids_survive_two_round_trips():
    state = persistence.PluginState(
        unit_alloc={"Disk.Bay.7:Enclosure.Internal.0-2:RAID.SL.3-1": 107, "PSU.0": 60},
        auto_names={"1": "Server Power"},
        base_wh={"1": 12.5},
    )
    once = persistence.loads(persistence.dumps(state))
    twice = persistence.loads(persistence.dumps(once))
    assert once == state
    assert twice == state


def test_auto_descriptions_round_trip():
    state = persistence.PluginState()
    state.auto_descriptions = {"dellidrac_1:5": "OK"}
    assert persistence.loads(persistence.dumps(state)).auto_descriptions == {"dellidrac_1:5": "OK"}


def test_a_payload_written_before_auto_descriptions_existed_still_loads():
    """Additive field: an install upgrading from an earlier version has no such key, and must
    come back with an empty mapping rather than failing to load its unit allocation."""
    old = '{"version":1,"unit_alloc":{"PSU.Slot.1":5},"auto_names":{},"base_wh":{}}'
    state = persistence.loads(old)
    assert state.auto_descriptions == {}
    assert state.unit_alloc == {"PSU.Slot.1": 5}
