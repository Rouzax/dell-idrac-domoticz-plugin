"""Load sanitized Redfish fixtures by profile."""

import json
from pathlib import Path

FIXTURE_ROOT = Path(__file__).parent / "fixtures"
# "ome" is a partial profile: a single metric report from an OpenManage-managed
# server, kept for the report shape rather than for whole-machine discovery.
PROFILES = ("t550", "dual", "degraded", "ome")


def load(profile: str, name: str) -> dict:
    path = FIXTURE_ROOT / profile / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))
