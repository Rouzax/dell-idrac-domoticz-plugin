"""Minimal in-memory fake of the DomoticzEx plugin API for unit tests."""

import sys
import types


class Unit:
    def __init__(
        self,
        Name="",
        DeviceID="",
        Unit=0,
        TypeName="",
        Options=None,
        Used=0,
        Image=0,
        Switchtype=0,
        Description="",
        **_kw,
    ):
        self.Name = Name
        self.DeviceID = DeviceID
        self.Unit = Unit
        self.TypeName = TypeName
        self.Options = Options or {}
        self.Used = Used
        self.Image = Image
        self.SwitchType = Switchtype
        self.Description = Description
        self.nValue = 0
        self.sValue = ""
        self.TimedOut = 0

    def Create(self):
        dev = Devices.setdefault(self.DeviceID, _FakeDevice(self.DeviceID))
        dev.Units[self.Unit] = self

    def Update(self, **_kw):
        return None


class _FakeDevice:
    def __init__(self, device_id):
        self.DeviceID = device_id
        self.Units = {}


Devices = {}
_module = types.ModuleType("Domoticz")
_module._log = []
_module._heartbeat = None
_module._config = {}
_module.Unit = Unit
_module.Devices = Devices


def _log(msg):
    _module._log.append(str(msg))


_module.Log = _log
_module.Debug = _log
_module.Error = _log
_module.Status = _log
_module.Heartbeat = lambda seconds: setattr(_module, "_heartbeat", seconds)
_module.Debugging = lambda value: setattr(_module, "_debugging", value)


def _configuration(config=None):
    if config is not None:
        _module._config = dict(config)
    return dict(_module._config)


_module.Configuration = _configuration


def install():
    """Install the fake Domoticz module and reset its state."""
    Devices.clear()
    _module._log.clear()
    _module._heartbeat = None
    _module._config = {}
    # The plugin imports the EXTENDED framework as `import DomoticzEx as Domoticz`,
    # so register the stub under both names.
    sys.modules["Domoticz"] = _module
    sys.modules["DomoticzEx"] = _module
    return _module
