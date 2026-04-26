r"""F11.7 — `ToolEvent.truncated` is never surfaced by the viewer.

Where: Transcript tab → Tool event ``big_output``. ``max_tool_output=200`` makes
inspect record ``event.truncated=(raw_bytes, kept_bytes)``. Finding claims the
viewer never reads this field, so users get no indication of truncation.

Nuance: Python's ``truncate_tool_output`` rewrites the result *string* to
``"…too long to be displayed.\\nHere is a truncated version:\\n<START>…<END>"``.
That preamble appears in ``event.result`` and the viewer faithfully prints it.
So users DO get a truncation indicator — just not from the viewer reading
``event.truncated``. We confirm the narrow claim (no viewer-side
"showing N of M bytes" footer) but note the impact is overstated.
"""

import re

from harness import VerifyResult, ViewerSession

BATCH = "11-tools"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F11.7", tab="transcript", log="F11.7-")
    session.wait_settled(ms=800)

    panels = session.page.locator('[id^="event-panel-"]')
    panel_text = None
    for i in range(panels.count()):
        t = panels.nth(i).inner_text()
        if t.startswith("TOOL: BIG_OUTPUT"):
            panel_text = t
            break
    if panel_text is None:
        return VerifyResult(
            "INCONCLUSIVE", evidence="", notes="big_output Tool event not found."
        )

    # The Python-side preamble (part of event.result, NOT viewer chrome).
    python_preamble = "too long to be displayed" in panel_text

    # A viewer-side footer reading event.truncated would say "N of M bytes" or
    # "showing N of M" or similar. Anything matching r"\d+\s*(of|/)\s*\d+\s*byte".
    viewer_footer = bool(
        re.search(r"\b\d[\d,]*\s*(?:of|/)\s*\d[\d,]*\s*bytes?\b", panel_text, re.I)
    ) or bool(re.search(r"truncated\s*[\(\[:]\s*\d", panel_text, re.I))

    evidence = (
        f"python_preamble_in_result={python_preamble} "
        f"viewer_truncated_footer={viewer_footer} | panel: {panel_text[:200]!r}…"
    )

    if not viewer_footer:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "No viewer-rendered footer surfaces `event.truncated` "
                "(no 'showing N of M bytes'). Narrow claim confirmed. "
                "IMPACT OVERSTATED: the result string itself contains "
                "Python's '…too long to be displayed. Here is a truncated "
                "version:' preamble, so users DO see a truncation hint — it "
                "just comes from inspect-core, not the viewer reading the "
                "`truncated` tuple. The repro's 'you will NOT see "
                "F11.7_FULL_OUTPUT_END' claim is also wrong (head+tail "
                "truncation keeps both markers)."
            ),
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=evidence,
        notes="Viewer renders a truncated-bytes footer.",
    )
