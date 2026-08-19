"""Gate on the committed fixtures: they must carry no identifier from the real machine.

THE LIST OF FORBIDDEN STRINGS IS NOT IN THIS REPO, DELIBERATELY. Committing the strings you are
searching for publishes every one of them, which is precisely the leak this file exists to
prevent. The first version of this test did exactly that: it put a service tag, a drive serial, a
MAC address, the system UUID, the internal hostname and the iDRAC password into git in plaintext,
inside the test whose whole purpose was to keep them out. The strings now live in an untracked
local file, so the sweep runs on the machine where captures are actually taken.

To enable the sweep, create `tests/forbidden_literals.local.json` (gitignored) holding a JSON
array of the real strings, for example:

    ["ABC1234", "hostname.example", "10.0.0.5", "the-idrac-password"]
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURE_ROOT = Path(__file__).parent / "fixtures"
LOCAL_LITERALS = Path(__file__).parent / "forbidden_literals.local.json"


def _forbidden_literals():
    if not LOCAL_LITERALS.exists():
        return ()
    return tuple(json.loads(LOCAL_LITERALS.read_text(encoding="utf-8")))


def _scrubber_mac_placeholders() -> set:
    """MAC-shaped values the scrubber deliberately writes in place of a real address."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
    try:
        import capture_fixtures
    finally:
        sys.path.pop(0)
    return {
        str(v).lower()
        for v in capture_fixtures.PLACEHOLDERS.values()
        if re.fullmatch(r"(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}", str(v))
    }


def _fixture_files():
    return sorted(FIXTURE_ROOT.rglob("*.json"))


def test_fixtures_exist():
    assert _fixture_files(), "no fixtures captured yet"


def test_the_local_literals_file_is_not_tracked():
    """Belt and braces: the file holding the real strings must never enter git.

    Cheap to check, and it fails loudly if someone force-adds it past .gitignore.
    """
    if not LOCAL_LITERALS.exists():
        pytest.skip("no local literals file on this machine")
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(LOCAL_LITERALS)],
        capture_output=True,
        cwd=Path(__file__).parent.parent,
        check=False,
    )
    assert tracked.returncode != 0, f"{LOCAL_LITERALS.name} IS TRACKED BY GIT. Remove it now."


@pytest.mark.parametrize("path", _fixture_files(), ids=lambda p: p.name)
def test_no_real_identifiers(path):
    literals = _forbidden_literals()
    if not literals:
        pytest.skip(
            f"{LOCAL_LITERALS.name} is not present, so this test proves NOTHING about real "
            "identifiers. Anyone capturing fixtures must create it first; see this module's "
            "docstring. Contributors who only consume the committed fixtures can ignore this."
        )
    text = path.read_text(encoding="utf-8")
    for index, literal in enumerate(literals):
        # The literal is never put in the message: that would defeat the whole point.
        assert literal.lower() not in text.lower(), (
            f"{path.name} leaks a real identifier (entry {index} of the local list). "
            "The capture was not sanitized."
        )


@pytest.mark.parametrize("path", _fixture_files(), ids=lambda p: p.name)
def test_fixtures_are_valid_json(path):
    json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", _fixture_files(), ids=lambda p: p.name)
def test_no_private_ipv4(path):
    """An address range is a class, not a secret, so this pattern stays in the repo."""
    text = path.read_text(encoding="utf-8")
    found = re.findall(r"\b(?:192\.168|10)\.\d{1,3}\.\d{1,3}(?:\.\d{1,3})?\b", text)
    found += re.findall(r"\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b", text)
    assert not found, f"{path.name} leaks private addresses: {found}"


@pytest.mark.parametrize("path", _fixture_files(), ids=lambda p: p.name)
def test_no_mac_addresses(path):
    """Also a class rather than a secret, so it runs even without the local list."""
    text = path.read_text(encoding="utf-8")
    found = {
        m
        for m in re.findall(r"\b(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\b", text)
        # Whatever the committed scrubber writes as a placeholder is legitimate. Read it from
        # the tool rather than repeating it here, so the two cannot drift apart.
        if m.lower() not in _scrubber_mac_placeholders()
    }
    assert not found, f"{path.name} leaks MAC addresses: {sorted(found)}"
