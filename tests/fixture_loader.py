"""Load sanitized Redfish fixtures by profile."""

import json
from pathlib import Path

FIXTURE_ROOT = Path(__file__).parent / "fixtures"
# "ome" is a partial profile: a single metric report from an OpenManage-managed
# server, kept for the report shape rather than for whole-machine discovery.
# "r750" is partial too, captured from a PowerEdge R750 for two states no other fixture holds:
# a Critical health rollup with an EMPTY fault list, and an NVMe drive, which Dell reports with
# MediaType "SSD" exactly like a SATA disk and distinguishes only by Protocol.
PROFILES = ("t550", "dual", "degraded", "ome", "r750")


def load(profile: str, name: str) -> dict:
    path = FIXTURE_ROOT / profile / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))
