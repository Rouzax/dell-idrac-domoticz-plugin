"""Load sanitized Redfish fixtures by profile."""

import json
from pathlib import Path

FIXTURE_ROOT = Path(__file__).parent / "fixtures"
# "ome" is a partial profile: a single metric report from an OpenManage-managed
# server, kept for the report shape rather than for whole-machine discovery.
# "r750" is partial too, captured from a PowerEdge R750 for two states no other fixture holds:
# a Critical health rollup with an EMPTY fault list, and an NVMe drive, which Dell reports with
# MediaType "SSD" exactly like a SATA disk and distinguishes only by Protocol.
# "redundant" is partial as well: the SAME T550 as the "t550" profile, recaptured after its
# redundancy policy was changed. Every other profile here was taken from a machine configured
# "Not Redundant", which reports an EMPTY Redundancy array, so until this one existed no test
# had ever seen a populated redundancy group from real hardware. It also carries Hot Spare
# enabled, which is what makes one supply carry the whole load.
# "input_lost" is the same T550 again with one supply's MAINS CORD pulled. It captures the SAME
# hardware condition as "degraded", a supply enumerated as Critical and UnavailableOffline at
# 0 W, under the OPPOSITE redundancy policy. That pairing is the point: "degraded" is configured
# "Not Redundant" and reports no redundancy group, "input_lost" is configured redundant and
# reports a group gone Critical, so together they show that the empty array follows the POLICY
# and not the failed supply.
PROFILES = ("t550", "dual", "degraded", "ome", "r750", "redundant", "input_lost")


def load(profile: str, name: str) -> dict:
    path = FIXTURE_ROOT / profile / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))
