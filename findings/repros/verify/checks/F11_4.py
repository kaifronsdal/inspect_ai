"""F11.4 — `ToolCallContent.format='text'` is ignored (rendered as markdown).

Where: Messages tab → the ``plain_text_tool`` call's input view. The repro sets
``view=ToolCallContent(format='text', content='# This line should be PLAIN…')``.
If ``format='text'`` were honoured, the ``#`` would render literally; instead
``ToolInput.tsx`` always pipes it through ``<RenderedText markdown=…>`` →
becomes an ``<h1>``.
"""

import re

from harness import VerifyResult, ViewerSession

BATCH = "11-tools"

H1_SENTINEL = "This line should be PLAIN TEXT not an"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F11.4", tab="messages", log="F11.4-")
    session.wait_settled(ms=600)

    html = session.html_of("#messages-contents")

    # Find <h1>/<h2> elements whose text contains the sentinel (NOT the
    # bug-description's <h1>, which is "VIEWER BUG REPRO — F11.4").
    h1s = re.findall(r"<(h[12])[^>]*>([^<]+)</\1>", html)
    sentinel_heading = next(
        (f"<{tag}>{body}</{tag}>" for tag, body in h1s if H1_SENTINEL in body),
        None,
    )

    # Secondary signal: was `**…**` rendered as <strong>?
    bold_rendered = "<strong>this should be literal asterisks" in html
    # Tertiary: was `[not a link](…)` rendered as <a>?
    link_rendered = bool(re.search(r'<a [^>]*href="http://example\.invalid"', html))

    evidence = (
        f"h1_with_sentinel={sentinel_heading!r} "
        f"bold_rendered={bold_rendered} link_rendered={link_rendered}"
    )

    if sentinel_heading or bold_rendered or link_rendered:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "ToolCallContent with format='text' was parsed as markdown: "
                "`# …` → <h1>, `**…**` → <strong>, `[...]()` → <a>. The "
                "`format` field is ignored."
            ),
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=evidence,
        notes="No markdown structures found — format='text' appears honoured.",
    )
