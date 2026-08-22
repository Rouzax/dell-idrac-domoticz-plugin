# tests/test_domoticz_stub.py
import DomoticzEx as Domoticz

from tests import domoticz_stub


def test_unit_create_registers_under_device_id():
    Domoticz.Unit(Name="Power", DeviceID="dellidrac_1", Unit=1, TypeName="Usage").Create()
    dev = domoticz_stub.Devices["dellidrac_1"]
    assert dev.Units[1].Name == "Power"
    assert dev.Units[1].TypeName == "Usage"


def test_install_resets_devices_between_tests():
    assert domoticz_stub.Devices == {}


def test_configuration_round_trips():
    Domoticz.Configuration({"state": "abc"})
    assert Domoticz.Configuration()["state"] == "abc"


def test_unit_carries_the_numeric_type_of_its_typename():
    unit = domoticz_stub.Unit(Name="P", DeviceID="d", Unit=1, TypeName="Usage")
    assert (unit.Type, unit.SubType) == (248, 1)
    unit = domoticz_stub.Unit(Name="P", DeviceID="d", Unit=2, TypeName="kWh")
    assert (unit.Type, unit.SubType) == (243, 29)


def test_update_with_a_typename_remaps_the_numeric_type_and_resets_the_value():
    unit = domoticz_stub.Unit(Name="P", DeviceID="d", Unit=1, TypeName="Usage")
    unit.Create()
    unit.sValue = "123.4"
    unit.Update(Log=False)
    unit.Update(TypeName="kWh", UpdateOptions=True)
    assert (unit.Type, unit.SubType) == (243, 29)
    # The core resets nValue and sValue when the type changes.
    assert unit.sValue == "0;0.0"
    assert unit.stored["Type"] == 243


def test_an_unmodelled_typename_leaves_the_numeric_type_alone():
    # Only kWh and Usage are modelled, because they are the only two the plugin converts between.
    unit = domoticz_stub.Unit(Name="A", DeviceID="d", Unit=1, TypeName="Alert")
    assert (unit.Type, unit.SubType) == (0, 0)
    unit.Update(TypeName="Alert")
    assert (unit.Type, unit.SubType) == (0, 0)
