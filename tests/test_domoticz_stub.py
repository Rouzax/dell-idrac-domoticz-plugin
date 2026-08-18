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
