"""Card text: the same facts rendered as plain text or as the markup Domoticz draws. Pure.

Domoticz runs Text and Alert device data through DOMPurify and renders the result as HTML
(sanitizeHTML in www/js/domoticzdevices.js, reached from DashboardDesktopController and
dzUtilityWidget), so <br>, <ul><li> and <a href target> all reach the card. That has been in
released Domoticz since 2026.1.

Everything here builds from the SAME list of facts the plain path uses, so the two forms cannot
drift apart as the wording changes.

Only sValue is rendered this way. A device Description never reaches a card at all, so markup
must never be put in one.
"""

import html

LINK_LABEL = "Open iDRAC"

# The link takes the card's OWN text colour rather than a colour of its own. Measured on a live
# Machinon card: the theme sets `a { color: #43A4D3 }` but also `a:link { color: #FFF }`, and
# `a:link` wins for any anchor with an href, so an unstyled link renders white on a white card and
# is invisible. A hard-coded hex cannot work either, because the same link has to read on a white
# card, a dark-theme card and a red alert card, and no single value does all three. `inherit`
# takes whatever the theme already guarantees is readable on that surface, in either mode; the
# underline is what marks it as a link. DOMPurify allows the style attribute, so this survives
# sanitisation.
LINK_STYLE = "color:inherit;text-decoration:underline"


def escape(value) -> str:
    """HTML-escape a value before it is interpolated into markup.

    Applied to everything that came from the server or from the user's settings. DOMPurify would
    strip an injected tag when the card renders, but the value is also written to the database
    and read back by dzVents and the JSON API, neither of which sanitizes anything.
    """
    return html.escape(str(value), quote=True)


def idrac_link(address) -> str:
    """A link to the iDRAC's own web interface, or nothing when there is no address.

    The scheme is always https: redfish_client builds every request that way whatever the
    VerifyTLS setting says, so the configured address never carries one. It MAY already carry a
    port, which passes through untouched.
    """
    if not address:
        return ""
    return (
        f'<a href="https://{escape(address)}" target="_blank"'
        f' style="{LINK_STYLE}">{LINK_LABEL}</a>'
    )


def lines(parts, link: str = "") -> str:
    """Facts joined with <br>, link last. Empty facts are dropped rather than leaving a blank line.

    The shipped caller passes exactly one fact plus the link, since both cards use bullets(), not
    lines(), for a list of several facts. The multi-fact <br> join is exercised only by this
    function's own tests; it is kept as a general-purpose primitive, not because production joins
    more than one line today.
    """
    items = [escape(part) for part in parts if part]
    if link:
        items.append(link)
    return "<br>".join(items)


def bullets(items, link: str = "") -> str:
    """Facts as a real list, link last.

    A list with nothing in it emits no <ul> at all, so a healthy card does not carry an empty
    bullet.
    """
    listed = "".join(f"<li>{escape(item)}</li>" for item in items if item)
    body = f"<ul>{listed}</ul>" if listed else ""
    return body + link
