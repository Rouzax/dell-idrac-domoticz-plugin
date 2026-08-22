# pyright: reportMissingImports=false
"""Thin adapter over the DomoticzEx device API. The ONLY module importing Domoticz."""

import sqlite3

import DomoticzEx as Domoticz

import persistence

# The heartbeat is on a 60 s watchdog, so a busy writer must never hold this up for long.
_DB_TIMEOUT_SECONDS = 2.0


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


# The only two type names a per-component power device ever holds, and the (Type, SubType) pair
# each maps to in the core (hardware/hardwaretypes.h: pTypeGeneral 0xF3, sTypeKwh 0x1D,
# pTypeUsage 0xF8, sTypeElectric 0x01). A unit whose plan entry names one of these while its
# stored pair is the other is converted IN PLACE, which keeps its idx, name, room and history
# rows. Deciding by inspection rather than by a stored migration flag makes it idempotent and
# self-healing: a device that somehow ends up with the wrong type is repaired on the next poll.
# Restricting the map to these two names is deliberate. Every other device the plugin creates
# keeps the type it was created with.
_CONVERTIBLE = {"kWh": (243, 29), "Usage": (248, 1)}


def apply_updates(
    devices,
    dev_ids,
    updates,
    auto_names,
    auto_colors=None,
    auto_descriptions=None,
    allow_create=True,
):
    """Apply updates across every Device the plan touches.

    `dev_ids` maps a planner family name to its DeviceID. Domoticz creates each Device implicitly
    when its first Unit is created, so nothing has to be set up in advance.
    """
    names = dict(auto_names)
    colors = dict(auto_colors or {})
    descriptions = dict(auto_descriptions or {})
    created = 0
    renamed = 0
    recoloured = 0
    redescribed = 0
    converted = 0
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
            if up.description:
                descriptions[key] = up.description
            created += 1
            continue

        # Read Type/SubType defensively. They are exposed on domoticz/domoticz:beta but we could
        # not establish the oldest release that carries them, and this file declares no minimum
        # Domoticz version. This runs on a path reached every heartbeat, same as the mark_timed_out
        # reasoning below: an AttributeError here would escape onHeartbeat's RedfishError-only
        # catch and kill the whole poll, taking every device update down with it. A build without
        # these members degrades to leaving units unconverted rather than dying.
        live_type = getattr(unit, "Type", None)
        live_subtype = getattr(unit, "SubType", None)
        wanted = _CONVERTIBLE.get(up.type_name)
        if (
            wanted is not None
            and None not in (live_type, live_subtype)
            and (live_type, live_subtype) != wanted
        ):
            # Update(TypeName=...) is the only way a plugin can change a unit's type. It remaps
            # Type, SubType and SwitchType and RESETS nValue and sValue
            # (hardware/plugins/PythonObjectEx.cpp, CUnitEx_update), which is why the real values
            # are written immediately below. Options travel with it: a kWh device needs
            # EnergyMeterMode set in the same breath, or the first counter write is interpreted
            # under the wrong mode.
            unit.Options = up.options or {}
            unit.Update(TypeName=up.type_name, UpdateOptions=True)
            converted += 1

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

        # A PSU is a Usage device, so its description is the ONLY channel its health has, and
        # it has to follow the hardware rather than being frozen at creation like the name and
        # the bands. Ownership is still respected the same way: a description the user typed is
        # not ours to overwrite. Skipped entirely when the plan carries no description, so an
        # empty one never clears a note on a device that has nothing to say.
        if up.description and unit.Description != up.description:
            # An unrecorded description is CLAIMED rather than treated as the user's. Until this
            # map existed the plugin was the only writer of these, so on an install upgrading
            # from an earlier version every description on a device it owns came from it, and
            # refusing to touch them would leave the health text frozen for ever on precisely
            # the installs that have the problem. It costs a note typed before the upgrade,
            # once. From here on the map is authoritative and an edit survives.
            owns_description = (
                not unit.Description
                or key not in descriptions
                or unit.Description == descriptions.get(key)
            )
            if owns_description:
                unit.Description = up.description
                unit.Update(Log=False, UpdateProperties=True)
                descriptions[key] = up.description
                redescribed += 1

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
            f"recoloured={recoloured} redescribed={redescribed} converted={converted}"
        )
    return names, colors, descriptions


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


def names_used_by_other_hardware(db_path: str, hardware_id, names) -> tuple:
    """Device names already owned by a DIFFERENT hardware entry, paired with the entry owning it.

    The plugin API cannot answer this. Every device query Domoticz exposes to a plugin is scoped
    to its own hardware id (`WHERE (HardwareID==%d)` throughout hardware/plugins/PythonObjects.cpp),
    so a second install of this plugin, or any other device that happens to be called
    "System Health", is structurally invisible. Domoticz does hand the plugin its database path in
    Parameters["Database"], so this opens it READ-ONLY to warn about a collision that would
    otherwise stay silent until a dzVents lookup acted on the wrong device.

    Read-only, one query, never a write. Anything going wrong at all returns nothing: this is
    called from the heartbeat, so a locked or unexpected database must cost a debug line rather
    than the poll.
    """
    wanted = [str(name) for name in names]
    if not db_path or not wanted:
        return ()
    placeholders = ",".join("?" * len(wanted))
    try:
        connection = sqlite3.connect(
            f"file:{db_path}?mode=ro", uri=True, timeout=_DB_TIMEOUT_SECONDS
        )
        try:
            rows = connection.execute(
                "SELECT d.Name, h.Name FROM DeviceStatus d "
                "JOIN Hardware h ON h.ID = d.HardwareID "
                f"WHERE d.HardwareID != ? AND d.Name IN ({placeholders})",
                [hardware_id, *wanted],
            ).fetchall()
        finally:
            connection.close()
    except Exception as exc:
        Domoticz.Debug(f"could not check for duplicate device names: {exc}")
        return ()
    return tuple(sorted({(str(name), str(owner)) for name, owner in rows}))


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
