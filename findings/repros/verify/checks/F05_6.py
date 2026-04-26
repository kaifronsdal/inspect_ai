"""F05.6 — ScoreEditEventView Metadata is nested inside Summary → not a tab.

Repro: ScoreEdit with metadata={..., "MARKER": "..."}. ``EventPanel`` reads
``data-name`` only on direct children. CONFIRMED if:
  - the Edit Score panel has NO sub-tab nav (single child), and
  - the metadata MARKER text is visible inline in that single body.

For contrast, the Score event in the same transcript DOES render Metadata as
its own tab (we report that too).
"""

from harness import VerifyResult, ViewerSession

BATCH = "01-events"

MARKER = "this metadata block should be in its OWN"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F05.6", tab="transcript", log="F05.6-score")
    session.expand_event("Edit Score")
    edit_panel = session.event_panel("Edit Score")
    edit_subtabs = edit_panel.locator('button[role="tab"]').all_inner_texts()
    edit_text = edit_panel.inner_text()
    marker_inline = MARKER in edit_text

    # Contrast: Score event below — title is "Score" exactly (avoid matching
    # "Edit Score").
    score_subtabs: list[str] = []
    panels = session.page.locator('[id^="event-panel-"]')
    for i in range(panels.count()):
        first_line = panels.nth(i).inner_text().split("\n", 1)[0].strip().upper()
        if first_line == "SCORE":
            chev = panels.nth(i).locator("i.bi-chevron-right")
            if chev.count():
                chev.first.click()
                session.wait_settled(network_idle=False)
            score_subtabs = (
                panels.nth(i).locator('button[role="tab"]').all_inner_texts()
            )
            break

    has_metadata_tab = any(t.strip().lower() == "metadata" for t in edit_subtabs)
    evidence = (
        f"Edit Score sub-tabs: {edit_subtabs}\n"
        f"Edit Score has Metadata tab: {has_metadata_tab}\n"
        f"metadata MARKER visible inline in body: {marker_inline}\n"
        f"(contrast) Score event sub-tabs: {score_subtabs}"
    )

    if not has_metadata_tab and marker_inline:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "Metadata renders inline at the bottom of Summary (no separate "
                "tab) because `<div data-name=\"Metadata\">` is nested inside "
                "`<div data-name=\"Summary\">`. ScoreEventView correctly shows "
                "a Metadata tab for contrast."
            ),
        )
    if has_metadata_tab:
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=evidence,
            notes="Edit Score has a separate Metadata tab — bug appears fixed.",
        )
    return VerifyResult(
        verdict="INCONCLUSIVE",
        evidence=evidence,
        notes="No Metadata tab AND marker not visible — repro metadata may not have landed.",
    )
