import json
import re
from pathlib import Path

import pytest

FIXTURE_ROOT = Path(__file__).parent / "fixtures"

# The real identifiers that used to sit here were PURGED FROM GIT HISTORY on 2026-08-19.
# Committing the strings this test searches for published every one of them: a service tag, a
# drive serial, a MAC address, the system UUID, the internal hostname and the iDRAC password.
# They now live in tests/forbidden_literals.local.json, which is gitignored and exists only on
# the machine that takes captures. See this module's docstring on the branch tip.
# This historical revision is therefore inert, by design.
FORBIDDEN_LITERALS = ()

# A Dell service tag is 7 alphanumerics. Placeholders are allow-listed.
ALLOWED_TAGS = {"SVCTAG0", "SERIAL0", "PPID000"}


def _fixture_files():
    return sorted(FIXTURE_ROOT.rglob("*.json"))


def test_fixtures_exist():
    assert _fixture_files(), "no fixtures captured yet"


@pytest.mark.parametrize("path", _fixture_files(), ids=lambda p: p.name)
def test_no_real_identifiers(path):
    text = path.read_text(encoding="utf-8")
    for literal in FORBIDDEN_LITERALS:
        assert literal.lower() not in text.lower(), f"{path.name} leaks {literal!r}"


@pytest.mark.parametrize("path", _fixture_files(), ids=lambda p: p.name)
def test_fixtures_are_valid_json(path):
    json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", _fixture_files(), ids=lambda p: p.name)
def test_no_private_ipv4(path):
    text = path.read_text(encoding="utf-8")
    found = re.findall(r"\b192\.168\.\d{1,3}\.\d{1,3}\b", text)
    assert not found, f"{path.name} leaks private addresses: {found}"
