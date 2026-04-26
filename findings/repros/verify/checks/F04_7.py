"""F04.7 — `output.stop_reason` and `output.error` not displayed.

Repro: ModelOutput with stop_reason="max_tokens" and
error="⚠️ PROVIDER REFUSAL: content filtered (output.error field) ⚠️".

The substring "content filtered" appears ONLY in output.error (the bug-
description text says "PROVIDER REFUSAL …" with an ellipsis). For stop_reason
we look for a structured label/badge — not free text, since "max_tokens"
appears in the description and the assistant content.
"""

from harness import VerifyResult, ViewerSession

BATCH = "01-events"

ERROR_SENTINEL = "content filtered"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F04.7", tab="transcript", log="F04.7-stop")
    panel = session.event_panel("Model Call")
    subtabs = session.event_subtabs("Model Call")

    found_error = False
    found_stop_label = False
    labels: set[str] = set()
    for tab in subtabs:
        session.click_event_subtab(tab, in_event="Model Call")
        text = panel.locator(".tab-pane.active").inner_text()
        if ERROR_SENTINEL in text:
            found_error = True
        for raw in panel.locator(".text-style-label").all_inner_texts():
            labels.add(raw.strip().upper())

    found_stop_label = any(
        lb in {"STOP REASON", "STOP_REASON", "MAX_TOKENS", "TRUNCATED"} for lb in labels
    )

    evidence = (
        f"sub-tabs checked: {subtabs}\n"
        f"output.error sentinel ({ERROR_SENTINEL!r}) visible: {found_error}\n"
        f"stop_reason label/badge visible: {found_stop_label}\n"
        f"all label cells: {sorted(labels)}"
    )

    if not found_error and not found_stop_label:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "Neither output.error text nor any stop_reason indicator is "
                "rendered in any Model Call sub-tab."
            ),
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=evidence,
        notes=(
            f"output.error visible={found_error}, stop_reason visible="
            f"{found_stop_label} — at least one is now surfaced."
        ),
    )
