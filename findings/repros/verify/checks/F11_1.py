"""F11.1 — Tool errors render identically to successful output.

Where: Transcript tab → two Tool events: ``good_tool`` (success) and
``bad_tool`` (raises ToolError). Both render their result via the same
``output`` prop → same ``<pre class="tool-output">`` styling.

This is fundamentally a *visual* check, so we (a) compare the CSS class set
of the two output ``<pre>`` blocks and (b) capture a screenshot.
"""

import re
from pathlib import Path

from harness import VerifyResult, ViewerSession

BATCH = "11-tools"
ARTIFACTS = Path(__file__).resolve().parents[1] / "artifacts"

SUCCESS_ANCHOR = "SUCCESS RESULT"
ERROR_ANCHOR = "THIS IS AN ERROR"


def _output_pre(html: str, anchor: str) -> str | None:
    """Return the <pre …>…</pre> element whose text contains ``anchor``."""
    for m in re.finditer(r"<pre\b[^>]*>.*?</pre>", html, re.S):
        if anchor in m.group(0):
            return m.group(0)
    return None


def check(session: ViewerSession) -> VerifyResult:
    # Disambiguate F11.1 vs F11.11 in the same log dir.
    session.goto_sample("F11.1", tab="transcript", log="F11.1-")
    session.wait_settled(ms=800)

    panels = session.page.locator('[id^="event-panel-"]')
    good_html = bad_html = None
    for i in range(panels.count()):
        t = panels.nth(i).inner_text()
        if t.startswith("TOOL: GOOD_TOOL"):
            good_html = panels.nth(i).evaluate("el => el.outerHTML")
        elif t.startswith("TOOL: BAD_TOOL"):
            bad_html = panels.nth(i).evaluate("el => el.outerHTML")

    if not good_html or not bad_html:
        return VerifyResult(
            "INCONCLUSIVE",
            evidence=f"good={bool(good_html)} bad={bool(bad_html)}",
            notes="Could not locate both Tool event panels.",
        )

    good_pre = _output_pre(good_html, SUCCESS_ANCHOR)
    bad_pre = _output_pre(bad_html, ERROR_ANCHOR)
    if not good_pre or not bad_pre:
        return VerifyResult(
            "INCONCLUSIVE",
            evidence=f"good_pre={bool(good_pre)} bad_pre={bool(bad_pre)}",
            notes="Output <pre> not found in one of the panels.",
        )

    good_cls = re.search(r'class="([^"]*)"', good_pre).group(1)
    bad_cls = re.search(r'class="([^"]*)"', bad_pre).group(1)

    # Any error indicator anywhere in the bad panel that the good panel lacks?
    bad_only_classes = set(re.findall(r'class="([^"]+)"', bad_html)) - set(
        re.findall(r'class="([^"]+)"', good_html)
    )
    # Any error-ish icon (bootstrap-icons exclamation/x-circle) on the bad
    # panel that the good panel lacks?
    err_icons = {
        "bi-exclamation",
        "bi-x-circle",
        "bi-x-octagon",
        "bi-bug",
        "text-danger",
    }
    bad_err_icon = any(i in bad_html and i not in good_html for i in err_icons)

    artifacts = [
        session.screenshot(
            ARTIFACTS / "F11.1-transcript.png", selector="#transcript-contents"
        )
    ]

    evidence = (
        f"good_tool output <pre class={good_cls!r}> | "
        f"bad_tool output <pre class={bad_cls!r}> | "
        f"classes on bad_tool panel not on good_tool panel="
        f"{sorted(bad_only_classes) or 'NONE'} | "
        f"error-icon-on-bad-only={bad_err_icon}"
    )

    if good_cls == bad_cls and not bad_only_classes and not bad_err_icon:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "Success and error tool outputs use the same `<pre>` class; "
                "the bad_tool panel carries zero CSS classes the good_tool "
                "panel lacks; no error icon (bi-exclamation/x-circle/"
                "text-danger) is added. Visually indistinguishable — "
                "see screenshot."
            ),
            artifacts=artifacts,
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=evidence,
        notes=(
            "bad_tool panel has distinct styling: "
            f"extra classes={sorted(bad_only_classes)}, "
            f"error-icon={bad_err_icon}."
        ),
        artifacts=artifacts,
    )
