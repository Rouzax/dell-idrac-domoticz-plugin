import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from tests import domoticz_stub

# Install at IMPORT (collection) time so `import DomoticzEx` resolves while pytest
# imports the test modules and the modules they pull in.
domoticz_stub.install()


@pytest.fixture(autouse=True)
def domoticz():
    """Reset the fake Domoticz and Devices before every test."""
    mod = domoticz_stub.install()
    if "plugin" in sys.modules:
        sys.modules["plugin"].Devices = mod.Devices
    return mod


@pytest.fixture(autouse=True)
def _reset_plugin_latches():
    """`plugin._state.counter_warned` and `last_poll_monotonic` are module-level latches meant to
    persist across a plugin run, not across tests. Left alone, a future test asserting that a
    warning IS emitted could pass or fail depending on test order. No-op if `plugin` has not been
    imported by the test module, since importing it here would pull it into modules that have
    nothing to do with it."""
    if "plugin" in sys.modules:
        state = sys.modules["plugin"]._state
        state.counter_warned = set()
        state.last_poll_monotonic = None
