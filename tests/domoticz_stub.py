"""Minimal in-memory fake of the DomoticzEx plugin API for unit tests."""

import sys
import types

# TypeName -> (Type, SubType, sValue after a type change), mirroring maptypename in the core
# (hardware/plugins/PythonObjects.cpp) for the ONLY two names the plugin ever converts between.
# Numeric values from hardware/hardwaretypes.h: pTypeGeneral 0xF3, sTypeKwh 0x1D,
# pTypeUsage 0xF8, sTypeElectric 0x01. Every other type name maps to (0, 0), because nothing in
# the plugin inspects those, and inventing numbers for them would put unverified constants in a
# test double where a wrong one would silently pass.
TYPE_MAP: dict[str, tuple[int, int, str]] = {
    "kWh": (243, 29, "0;0.0"),
    "Usage": (248, 1, ""),
}


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
        # Real CUnitEx exposes Type and SubType as writable members (PythonObjectEx.h), and the
        # plugin now reads them to decide whether a unit needs converting. A stub without them
        # cannot fail that code.
        mapped = TYPE_MAP.get(TypeName)
        self.Type, self.SubType = (mapped[0], mapped[1]) if mapped else (0, 0)
        self.Options = Options or {}
        self.Used = Used
        self.Image = Image
        self.SwitchType = Switchtype
        self.Description = Description
        self.nValue = 0
        self.sValue = ""
        self.TimedOut = 0
        # Color is a real CUnitEx member but is deliberately NOT a constructor keyword here,
        # because it is not one in the core either: CUnitEx's init kwlist has no "color", so
        # Domoticz.Unit(Color=...) is silently dropped. Assign it on the object before Create().
        self.Color = ""
        # What Domoticz would actually have PERSISTED, as opposed to what has merely been
        # assigned to this object. The two are not the same, and a stub that ignores the
        # difference passes tests for code that can never work against real Domoticz: the core
        # writes Name, Description, Color and CustomImage only when Update() is passed
        # UpdateProperties=True, and Options only under UpdateOptions=True
        # (hardware/plugins/PythonObjectEx.cpp, CUnitEx_update). A missing flag is silently
        # dropped, which is exactly how a Description that never updated shipped.
        self.stored = {}
        # Every Update() call's keyword arguments, in order, so a test can assert the flags.
        self.updates = []

    def Create(self):
        dev = Devices.setdefault(self.DeviceID, _FakeDevice(self.DeviceID))
        dev.Units[self.Unit] = self
        self.stored = {
            "Name": self.Name,
            "Description": self.Description,
            "Color": self.Color,
            "Image": self.Image,
            "Options": dict(self.Options),
            "nValue": self.nValue,
            "sValue": self.sValue,
            "Type": self.Type,
            "SubType": self.SubType,
        }

    def Update(self, **kw):
        self.updates.append(kw)
        # A TypeName on Update remaps the type and RESETS the value, exactly as CUnitEx_update
        # does (PythonObjectEx.cpp): maptypename hands back a fresh sValue and the core assigns
        # nValue = 0 before writing. SwitchType is deliberately not modelled: maptypename assigns
        # it only in the switch-family branches, never in "kwh" or "usage", so for the two names
        # this stub covers the core leaves it untouched. That is also what makes an in-place
        # conversion safe, since a Usage device already carries the 0 a kWh device wants.
        mapped = TYPE_MAP.get(kw.get("TypeName") or "")
        if mapped is not None:
            self.Type, self.SubType, self.TypeName = mapped[0], mapped[1], kw["TypeName"]
            self.nValue = 0
            self.sValue = mapped[2]
            self.stored["Type"] = self.Type
            self.stored["SubType"] = self.SubType
        # Values always persist; that is what Update is for.
        self.stored["nValue"] = self.nValue
        self.stored["sValue"] = self.sValue
        if kw.get("UpdateProperties"):
            self.stored["Name"] = self.Name
            self.stored["Description"] = self.Description
            self.stored["Color"] = self.Color
            self.stored["Image"] = self.Image
        if kw.get("UpdateOptions"):
            self.stored["Options"] = dict(self.Options)
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
