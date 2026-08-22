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

# The anchor carries NO styling of its own, deliberately. A plain link is the standard thing to
# emit and it is a theme's job to colour it.
#
# Known consequence: Domoticz core sets `a:link { color: #fff }` unscoped (www/css/style.css),
# which beats a bare `a` selector for any anchor with an href, so on a light card the link
# currently renders white on white and is invisible. That is a defect in the stylesheet, not in
# the markup, and it is filed against the Machinon theme as domoticz/Machinon#191. An earlier
# version of this file worked around it with an inline `style` attribute; that was removed
# because an inline style beats a stylesheet, so the plugin would have kept overriding the theme
# long after the theme was fixed.


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
    return f'<a href="https://{escape(address)}" target="_blank">{LINK_LABEL}</a>'


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
