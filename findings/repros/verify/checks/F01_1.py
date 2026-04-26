"""F01.1 — ModelEventView Summary tab drops preceding messages when input ends with assistant.

Repro: input = [system(SENTINEL), user(desc), user(SENTINEL), assistant]. With the
``slice(-1)`` bug, Summary shows only [assistant, output]. The sentinel
"IF YOU CANNOT SEE THIS IN THE SUMMARY TAB" appears nowhere else (the bug-
description message uses different wording), so its absence in the Summary
pane is load-bearing.
"""

from harness import VerifyResult, ViewerSession

BATCH = "01-events"

SENTINEL = "IF YOU CANNOT SEE THIS IN THE SUMMARY TAB"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F01.1", tab="transcript", log="F01.1-model")

    panel = session.event_panel("Model Call")
    # Summary is the default-selected sub-tab.
    summary = panel.locator(".tab-pane.active").inner_text()
    summary_has_sentinel = SENTINEL in summary

    # Cross-check: All tab DOES contain it (proves the messages are in event.input).
    session.click_event_subtab("All", in_event="Model Call")
    all_tab = panel.locator(".tab-pane.active").inner_text()
    all_has_sentinel = SENTINEL in all_tab

    evidence = (
        f"Summary tab contains sentinel: {summary_has_sentinel}\n"
        f"All tab contains sentinel:     {all_has_sentinel}\n"
        f"--- Summary tab (first 400 chars) ---\n{summary[:400]}"
    )

    if not all_has_sentinel:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=evidence,
            notes="Sentinel missing from All tab too — repro input not as expected.",
        )
    if not summary_has_sentinel:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "Preceding system/user messages absent from Summary; present in "
                "All. `event.input.slice(-1)` bug confirmed."
            ),
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=evidence,
        notes="Summary tab shows the preceding user/system messages.",
    )
