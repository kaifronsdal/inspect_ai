"""F90.5 — Sample 'Error' tab omits `error.message`; renders only traceback.

The repro raises `RuntimeError(DISTINCTIVE)` where DISTINCTIVE contains the
sentinel `F90.5_ERROR_MESSAGE_SHOULD_BE_VISIBLE` plus extra context
(`request_id=abc123`).

`TaskErrorPanel` (log-level) renders `error.message` in its own
`ExpandablePanel` *above* the ANSI traceback. The sample-level Error tab
should do the same but instead renders **only** `<ANSIDisplay traceback_ansi>`.

Check: the Error-tab card body's children — is there anything *before* the
ANSIDisplay container? If the ANSIDisplay is the only child → message panel
is absent → CONFIRMED. (The sentinel does appear inside the traceback's
final line — that's incidental, not the dedicated message render.)
"""

from harness import VerifyResult, ViewerSession

BATCH = "90-cross"

SENTINEL = "F90.5_ERROR_MESSAGE_SHOULD_BE_VISIBLE"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F90.5", log="F90.5", tab="error")

    pane = session.page.locator("#error-contents")
    if pane.count() == 0:
        return VerifyResult("INCONCLUSIVE", "", notes="No #error-contents pane.")

    text = pane.inner_text()
    card_body = pane.locator('[class*="_body_"]').first
    body_html = card_body.evaluate("el => el.outerHTML")

    # What's in the card body? Count direct children and classify.
    child_classes: list[str] = card_body.evaluate(
        "el => Array.from(el.children).map(c => c.className)"
    )
    has_ansi = any("ansiDisplayContainer" in c for c in child_classes)
    has_message_panel = any(
        "ansiDisplay" not in c for c in child_classes
    )  # any non-ANSI sibling

    # Sentinel: present anywhere? present *outside* the ANSI block?
    sentinel_anywhere = SENTINEL in text
    ansi_text = card_body.locator('[class*="ansiDisplayContainer"]').first.inner_text()
    sentinel_outside_ansi = SENTINEL in text.replace(ansi_text, "")

    evidence = (
        f"card-body children classes = {child_classes}; "
        f"sentinel in tab text = {sentinel_anywhere}; "
        f"sentinel outside ANSI block = {sentinel_outside_ansi}"
    )

    if not has_ansi:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=evidence,
            notes="No ANSI traceback found in the Error tab — repro may be broken.",
        )

    if not has_message_panel and not sentinel_outside_ansi:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "Sample Error tab card-body contains ONLY the ANSIDisplay "
                "traceback — no dedicated `error.message` panel above it. "
                "The sentinel appears only as the traceback's final line "
                "(incidental), not as a separately rendered message. "
                "TaskErrorPanel would render message + traceback."
            ),
        )
    if has_message_panel or sentinel_outside_ansi:
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=evidence,
            notes="Error tab now renders something besides the ANSI traceback.",
        )
    return VerifyResult("INCONCLUSIVE", evidence)
