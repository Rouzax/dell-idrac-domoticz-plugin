"""Load sanitized Redfish fixtures by profile."""

import json
from pathlib import Path

FIXTURE_ROOT = Path(__file__).parent / "fixtures"
PROFILES = ("t550", "dual")


def load(profile: str, name: str) -> dict:
    path = FIXTURE_ROOT / profile / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))
