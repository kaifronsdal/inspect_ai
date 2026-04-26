"""F90.3 — Transcript ScoreEvent bypasses the score-descriptor system.

Boolean score `True`:
  (A) Sample header "Score" cell → `BooleanScoreDescriptor.render()` →
      `<span class="_circle_* _green_*">true</span>` — coloured badge.
  (B) Transcript → Score event → "Score" row → `ScoreValue → String(value)` →
      bare `<div>true</div>` — no badge classes.

Check: header score cell has the `_circle_` / `_green_` badge classes; the
Score event's value cell does not.
"""

from harness import VerifyResult, ViewerSession

BATCH = "90-cross"


def _find_score_panel(session: ViewerSession):
    """Locate the event panel whose own title is exactly 'Score'.

    `event_panel("Score")` matches the Model Call panel because the bug
    description text contains the word "Score", so filter on the title label.
    """
    panels = session.page.locator('[id^="event-panel-"]')
    for i in range(panels.count()):
        p = panels.nth(i)
        title = p.locator(".text-style-label").first.inner_text().strip().upper()
        if title == "SCORE":
            return p
    return None


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F90.3", log="F90.3", tab="transcript")

    # --- (A) header score cell --------------------------------------------
    hdr = session.page.locator('[id^="sample-heading-"]').first
    score_cell = hdr.locator('[class*="_centerValue_"]').last
    hdr_html = score_cell.evaluate("el => el.outerHTML")
    hdr_has_badge = "_circle_" in hdr_html and ("_green_" in hdr_html or "_red_" in hdr_html)

    # --- (B) transcript Score event value cell -----------------------------
    score_panel = _find_score_panel(session)
    if score_panel is None:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=f"header score cell html = {hdr_html}",
            notes="Could not locate a transcript event panel titled 'Score'.",
        )
    chev = score_panel.locator("i.bi-chevron-right")
    if chev.count() and chev.first.is_visible():
        chev.first.click()
        session.wait_settled(network_idle=False)
    panel_html = score_panel.evaluate("el => el.outerHTML")
    # The value cell is the <div> immediately following the "Score" label
    # inside the active tab-pane. Just check for badge classes anywhere in
    # the panel body.
    body_html = score_panel.locator(".tab-pane.active").first.evaluate(
        "el => el.outerHTML"
    )
    panel_has_badge = "_circle_" in body_html

    evidence = (
        f"header score cell: {hdr_html} | "
        f"ScoreEvent body has badge class: {panel_has_badge} "
        f"(body excerpt: ...{body_html[body_html.rfind('Score</div>'):][:120]!r})"
    )

    if hdr_has_badge and not panel_has_badge:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "Header renders boolean score via BooleanScoreDescriptor "
                "(green-circle badge classes). Transcript ScoreEvent renders "
                "the same value as bare unstyled text — no `_circle_` class."
            ),
        )
    if hdr_has_badge and panel_has_badge:
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=evidence,
            notes="ScoreEvent now renders the descriptor badge too.",
        )
    if not hdr_has_badge:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=evidence,
            notes=(
                "Header score cell lacks the expected `_circle_` badge class — "
                "BooleanScoreDescriptor may have changed; can't compare."
            ),
        )
    return VerifyResult("INCONCLUSIVE", evidence)
