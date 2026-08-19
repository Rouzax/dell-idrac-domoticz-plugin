# pyright: reportMissingImports=false
"""Thin adapter over the DomoticzEx device API. The ONLY module importing Domoticz."""

import DomoticzEx as Domoticz

import persistence


def device_id(hardware_id, family: str) -> str:
    """One DeviceID per family, because each Device has its own 1-255 unit space.

    Including the hardware id keeps two iDRAC hardware entries in one Domoticz install apart.
    """
    return f"dellidrac_{hardware_id}_{family}"


def name_key(dev_id: str, unit: int) -> str:
    """Names are tracked per DEVICE and unit: unit numbers repeat across devices now, so keying
    on the number alone would let a rename on one device suppress renaming on another."""
    return f"{dev_id}:{unit}"


def _existing_unit(devices, dev_id, unit):
    dev = devices.get(dev_id)
    if dev is None:
        return None
    return dev.Units.get(unit)


def apply_updates(devices, dev_ids, updates, auto_names, auto_colors=None, allow_create=True):
    """Apply updates across every Device the plan touches.

    `dev_ids` maps a planner family name to its DeviceID. Domoticz creates each Device implicitly
    when its first Unit is created, so nothing has to be set up in advance.
    """
    names = dict(auto_names)
    colors = dict(auto_colors or {})
    created = 0
    renamed = 0
    recoloured = 0
    # Create in ascending device then unit order: Domoticz lists devices in creation order, so
    # this keeps the on-disk layout matching the logical numbering.
    for up in sorted(updates, key=lambda u: (u.device, u.unit)):
        dev_id = dev_ids[up.device]
        key = name_key(dev_id, up.unit)
        unit = _existing_unit(devices, dev_id, up.unit)
        if unit is None:
            if not allow_create:
                continue
            new_unit = Domoticz.Unit(
                Name=up.name,
                DeviceID=dev_id,
                Unit=up.unit,
                TypeName=up.type_name,
                Options=up.options,
                Image=up.image,
                Switchtype=up.switchtype,
                Description=up.description,
                Used=1,
            )
            # Color carries the bar ranges. It is NOT a constructor keyword: CUnitEx's init
            # kwlist (hardware/plugins/PythonObjectEx.cpp) has no "color" member, so passing it
            # above would be silently dropped. Create() does persist self->Color into the INSERT,
            # so it has to be assigned here first. Set at creation ONLY, like the icon: bands a
            # user tuned by hand must survive every later poll.
            if up.color:
                new_unit.Color = up.color
                colors[key] = up.color
            new_unit.Create()
            unit = devices[dev_id].Units[up.unit]
            unit.nValue = up.nvalue
            unit.sValue = up.svalue
            unit.Update(Log=False)
            names[key] = up.name
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
        # Bands are DERIVED from settings and hardware thresholds, so they must follow a change
        # to either. They are still only rewritten while the plugin still owns them: the same
        # rule as names, so bands a user tuned by hand survive every later poll.
        if up.color and up.color != unit.Color:
            owns_color = not unit.Color or unit.Color == colors.get(key)
            if owns_color:
                unit.Color = up.color
                unit.Update(Log=False, UpdateProperties=True)
                colors[key] = up.color
                recoloured += 1

        owned = unit.Name == names.get(key)
        if owned and unit.Name != up.name:
            unit.Name = up.name
            unit.Update(Log=False, UpdateProperties=True)
            names[key] = up.name
            renamed += 1
        else:
            unit.Update(Log=False)
    if updates:
        Domoticz.Debug(
            f"apply units={len(updates)} created={created} renamed={renamed} "
            f"recoloured={recoloured}"
        )
    return names, colors


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


def set_switch(devices, dev_id, unit_no, on: bool) -> None:
    """Move a switch immediately, without waiting for the next poll.

    A control device is only rewritten when the poll runs, so without this a switch the user just
    clicked sits at its old value for up to a full poll interval and reads as though the command
    was ignored.
    """
    unit = _existing_unit(devices, dev_id, unit_no)
    if unit is None:
        return
    unit.nValue = 1 if on else 0
    unit.Update(Log=False)
