"""Symbols vulture cannot see being used, because Domoticz calls them, not our code.

Nothing here is dead: deleting any of it breaks the plugin at runtime while every test still
passes, because the test stub never exercises the framework's own call path. Run the sweep with:

    python3 -m vulture . .vulture_whitelist.py --min-confidence 80 --exclude tests,_TEMP,docs
"""

import plugin

# Domoticz's plugin framework looks these up by name on the module. There is no in-repo caller.
_HOOKS = (plugin.onStart, plugin.onStop, plugin.onHeartbeat, plugin.onCommand)


def _framework_command_signature(DeviceID, Unit, Command, Level, Color):
    """onCommand's parameter list is fixed by Domoticz and passed positionally.

    The plugin dispatches on Unit, Command and Level only, so DeviceID and Color are genuinely
    unread, but neither can be dropped or renamed. Mirroring the signature here marks both names
    as used without putting a noqa on the real function.
    """
    return DeviceID, Unit, Command, Level, Color
