import cardtext


def test_a_link_points_at_the_idrac_over_https():
    """The scheme is always https: redfish_client builds every request that way whatever the
    VerifyTLS setting says, so the configured address never carries one."""
    assert cardtext.idrac_link("10.0.0.5") == (
        '<a href="https://10.0.0.5" target="_blank">Open iDRAC</a>'
    )


def test_a_link_keeps_a_port_the_user_typed():
    assert 'href="https://10.0.0.5:8443"' in cardtext.idrac_link("10.0.0.5:8443")


def test_a_hostile_address_cannot_break_out_of_the_attribute():
    """The address is user-supplied configuration going straight into an href. DOMPurify would
    strip an injected tag on the way out, but the value is also stored in the database and read
    by dzVents, which does no such thing."""
    link = cardtext.idrac_link('x" onload="alert(1)')
    assert "onload=" not in link.replace("&quot;", "")
    assert "&quot;" in link


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


def test_the_link_itself_is_not_escaped():
    """It is markup we built, not data. Escaping it would print the tag on the card."""
    link = cardtext.idrac_link("10.0.0.5")
    assert cardtext.lines(["OK"], link).endswith(link)
