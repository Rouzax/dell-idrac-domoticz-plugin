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
        unit.TimedOut = 0
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


def mark_timed_out(devices, dev_id, units) -> None:
    """Flag units as stale WITHOUT changing their values.

    A zero is a reading. Writing one when the source is unreachable would poison
    the device history, so the last good value is left in place.
    """
    for unit_no in units:
        unit = _existing_unit(devices, dev_id, unit_no)
        if unit is not None:
            unit.TimedOut = 1
            unit.Update(Log=False, TimedOut=1)


def read_prev_counter_wh(devices, dev_id, unit_no) -> float:
    unit = _existing_unit(devices, dev_id, unit_no)
    if unit is None or ";" not in str(unit.sValue):
        return 0.0
    try:
        return float(str(unit.sValue).split(";", 1)[1])
    except (ValueError, IndexError):
        return 0.0


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
