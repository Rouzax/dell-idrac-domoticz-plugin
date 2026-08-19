# pyright: reportMissingImports=false
"""Thin adapter over the DomoticzEx device API. The ONLY module importing Domoticz."""

import DomoticzEx as Domoticz

import persistence


def device_id(hardware_id) -> str:
    return f"dellidrac_{hardware_id}"


def _existing_unit(devices, dev_id, unit):
    dev = devices.get(dev_id)
    if dev is None:
        return None
    return dev.Units.get(unit)


def apply_updates(devices, dev_id, updates, auto_names, allow_create=True) -> dict:
    names = dict(auto_names)
    created = 0
    renamed = 0
    # Create in ascending unit order: Domoticz lists devices in creation order, so
    # this keeps the on-disk layout matching the logical unit numbering.
    for up in sorted(updates, key=lambda u: u.unit):
        unit = _existing_unit(devices, dev_id, up.unit)
        if unit is None:
            if not allow_create:
                continue
            Domoticz.Unit(
                Name=up.name,
                DeviceID=dev_id,
                Unit=up.unit,
                TypeName=up.type_name,
                Options=up.options,
                Image=up.image,
                Switchtype=up.switchtype,
                Description=up.description,
                Used=1,
            ).Create()
            unit = devices[dev_id].Units[up.unit]
            unit.nValue = up.nvalue
            unit.sValue = up.svalue
            unit.Update(Log=False)
            names[str(up.unit)] = up.name
            created += 1
            continue

        unit.nValue = up.nvalue
        unit.sValue = up.svalue
        if up.options and unit.Options != up.options:
            # Options are recomputed every poll for the control selector. Setting them only at
            # creation would freeze the menu labels, so the UI could describe an action that is no
            # longer offered.
            unit.Options = up.options
            unit.Update(Log=False, UpdateOptions=True)
        owned = unit.Name == names.get(str(up.unit))
        if owned and unit.Name != up.name:
            unit.Name = up.name
            unit.Update(Log=False, UpdateProperties=True)
            names[str(up.unit)] = up.name
            renamed += 1
        else:
            unit.Update(Log=False)
    if updates:
        Domoticz.Debug(f"apply units={len(updates)} created={created} renamed={renamed}")
    return names


# There is deliberately NO mark_timed_out here. Checked against the Domoticz core:
# DomoticzEx.Unit exposes no TimedOut member (CUnitEx_members in
# hardware/plugins/PythonObjectEx.h lists ID, Unit, Name, nValue, sValue ... Parent, while
# TimedOut lives on CDeviceEx, the parent Device), and Unit.Update accepts only
# log/typename/updateproperties/updateoptions/suppresstriggers. Assigning unit.TimedOut would
# raise against real Domoticz, on a path reached every heartbeat.
# It is also unnecessary. Domoticz does its own staleness detection from LastUpdate against the
# SensorTimeout preference (main/mainworker.cpp), exactly as for every built-in hardware type.
# So when the iDRAC is unreachable the correct action is to write NOTHING: the last good value
# stays on screen, LastUpdate goes stale, and Domoticz flags the device itself. Writing nothing
# is also what keeps a zero out of the recorded history.


def read_prev_counter_wh(devices, dev_id, unit_no):
    """Energy half of a "POWER;ENERGY" sValue, or None when it cannot be read.

    None means unknown, NOT zero. Returning 0.0 for an unreadable value would reset the counter's
    baseline, and the next write would be a large backward jump in a device whose entire contract
    is that it only ever climbs. The caller leaves the counter alone for that cycle instead.
    """
    unit = _existing_unit(devices, dev_id, unit_no)
    if unit is None:
        return 0.0
    parts = str(unit.sValue).split(";")
    if len(parts) < 2:
        return 0.0
    try:
        return float(parts[1])
    except ValueError:
        return None


def load_state():
    return persistence.loads(Domoticz.Configuration().get("state", ""))


def save_state(state) -> None:
    # Read-modify-write so other Configuration keys are preserved.
    cfg = Domoticz.Configuration()
    cfg["state"] = persistence.dumps(state)
    Domoticz.Configuration(cfg)


def log_redacted(level_fn, message, secret) -> None:
    text = str(message)
    if secret:
        text = text.replace(str(secret), "***")
    level_fn(text)
