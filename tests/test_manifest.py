"""Gate on the plugin manifest, which Domoticz parses at load time.

Nothing else in the suite reads it: the manifest is a docstring, so a malformed tag or a
parameter the code never reads is invisible to every other test and shows up only as an empty
or broken settings form in Domoticz.
"""

import ast
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import config

PLUGIN_SOURCE = Path(__file__).parent.parent / "plugin.py"


def _manifest() -> ET.Element:
    docstring = ast.get_docstring(ast.parse(PLUGIN_SOURCE.read_text(encoding="utf-8")))
    return ET.fromstring(docstring)


def test_the_manifest_is_well_formed_xml():
    """A broken tag makes Domoticz render no settings form at all, with nothing in the log."""
    assert _manifest().tag == "plugin"


def test_every_declared_parameter_is_read_by_config():
    """A parameter in the form that nothing consumes is a setting that silently does nothing.

    parse_config is the only reader, so its source is the authority on what is actually used.
    """
    declared = {param.get("field") for param in _manifest().iter("param")}
    source = Path(config.__file__).read_text(encoding="utf-8")
    read = set(re.findall(r'["\'](\w+)["\']', source))
    unused = sorted(field for field in declared if field not in read)
    assert not unused, f"declared in the manifest but never read by config: {unused}"


def test_the_name_affix_settings_are_offered():
    declared = {param.get("field") for param in _manifest().iter("param")}
    assert {"NamePrefix", "NameSuffix"} <= declared


def test_no_description_link_is_preceded_by_a_bare_space():
    """Domoticz strips a text node's trailing whitespace before a child element, so a link
    written as "... text <a href=...>" renders glued to the previous word. Wrapping the link in
    parentheses is what avoids it; this keeps every description consistent with that."""
    raw = ast.get_docstring(ast.parse(PLUGIN_SOURCE.read_text(encoding="utf-8")))
    glued = re.findall(r"[^(\s]\s<a href=", raw)
    assert not glued, f"{len(glued)} description link(s) not wrapped in parentheses"
