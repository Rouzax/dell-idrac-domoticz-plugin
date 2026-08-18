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
