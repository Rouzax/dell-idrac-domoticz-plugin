from html.parser import HTMLParser

import cardtext


class _AnchorAttrs(HTMLParser):
    """Collects the attributes of the first <a> tag, the way a browser would read them."""

    def __init__(self):
        super().__init__()
        self.attrs = {}

    def handle_starttag(self, tag, attrs):
        if tag == "a" and not self.attrs:
            self.attrs = dict(attrs)


def _anchor_attrs(markup: str) -> dict:
    parser = _AnchorAttrs()
    parser.feed(markup)
    return parser.attrs


def test_a_link_points_at_the_idrac_over_https():
    """The scheme is always https: redfish_client builds every request that way whatever the
    VerifyTLS setting says, so the configured address never carries one."""
    assert cardtext.idrac_link("10.0.0.5") == (
        '<a href="https://10.0.0.5" target="_blank"'
        ' style="color:inherit;text-decoration:underline">Open iDRAC</a>'
    )


def test_a_link_keeps_a_port_the_user_typed():
    assert 'href="https://10.0.0.5:8443"' in cardtext.idrac_link("10.0.0.5:8443")


def test_a_hostile_address_cannot_introduce_an_attribute():
    """The address is user-supplied configuration going straight into an href.

    Asserted by PARSING the result rather than by string-matching: the property that matters is
    that a browser sees only the three attributes we wrote, with the entire hostile value trapped
    inside href. Stripping the entity out and then searching the text would be testing something
    an attacker cannot do.
    """
    attrs = _anchor_attrs(cardtext.idrac_link('x" onload="alert(1)'))
    assert set(attrs) == {"href", "target", "style"}
    assert attrs["href"] == 'https://x" onload="alert(1)'
    assert attrs["target"] == "_blank"


def test_a_normal_address_parses_back_unchanged():
    attrs = _anchor_attrs(cardtext.idrac_link("10.0.0.5:8443"))
    assert attrs["href"] == "https://10.0.0.5:8443"


def test_the_link_takes_the_cards_own_colour_rather_than_its_own():
    """A theme that styles `a:link` can otherwise render this white on a white card, which was
    measured on a live Machinon instance. Inheriting is the only value that reads on a white
    card, a dark card and a red alert card alike."""
    attrs = _anchor_attrs(cardtext.idrac_link("10.0.0.5"))
    assert "color:inherit" in attrs["style"]
    assert "underline" in attrs["style"]


def test_no_address_means_no_link():
    assert cardtext.idrac_link("") == ""


def test_lines_puts_one_fact_per_line_and_the_link_last():
    assert cardtext.lines(["A/B Grid Redundant", "2 supplies (1 needed)"], "LINK") == (
        "A/B Grid Redundant<br>2 supplies (1 needed)<br>LINK"
    )


def test_lines_without_a_link_is_just_the_facts():
    assert cardtext.lines(["Redundancy lost"]) == "Redundancy lost"


def test_lines_drops_empty_facts_rather_than_leaving_a_blank_line():
    assert cardtext.lines(["A", "", "B"]) == "A<br>B"


def test_bullets_wraps_each_item_and_appends_the_link():
    assert cardtext.bullets(["one", "two"], "LINK") == "<ul><li>one</li><li>two</li></ul>LINK"


def test_bullets_with_nothing_to_list_emits_no_empty_list():
    assert cardtext.bullets([], "LINK") == "LINK"


def test_a_fault_message_containing_markup_is_escaped():
    """Fault text comes from the server, so it is not ours to trust."""
    assert cardtext.bullets(["<b>bad</b>"]) == "<ul><li>&lt;b&gt;bad&lt;/b&gt;</li></ul>"


def test_lines_also_escapes_its_facts():
    """Escaping is exercised through bullets() and idrac_link() elsewhere; lines() needs its own
    pin, since the shipped caller passes it a single server-reported fact."""
    assert cardtext.lines(["<b>bad</b>"]) == "&lt;b&gt;bad&lt;/b&gt;"


def test_the_link_itself_is_not_escaped():
    """It is markup we built, not data. Escaping it would print the tag on the card."""
    link = cardtext.idrac_link("10.0.0.5")
    assert cardtext.lines(["OK"], link).endswith(link)
