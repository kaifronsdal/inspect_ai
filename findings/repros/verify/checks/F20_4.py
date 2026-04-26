"""F20.4 — Scoring tab uses a fresh single-value descriptor ≠ list/header.

Where: three places for sample ``should_be_C``:
  (1) sample-list score cell  (2) header score column  (3) Scoring-tab grid.

Repro: scores are ``{C, I, X}``. Full set → categorical (plain ``String``).
The Scoring tab calls ``getScoreDescriptorForValues([C], ["string"])`` →
passFail → coloured circle badge (``span._circle_*``). Divergence == bug.
"""

from harness import VerifyResult, ViewerSession

BATCH = "20-samples"


def check(session: ViewerSession) -> VerifyResult:
    # --- (1) sample list -----------------------------------------------------
    session.goto_log("F20.4", tab="samples")
    list_cell = session.page.locator('.ag-cell[col-id="score-0"]').first
    list_html = list_cell.evaluate("el => el.innerHTML")
    list_circle = "circle" in list_html

    # --- (2) header + (3) scoring tab ---------------------------------------
    session.goto_sample("should_be_C", log="F20.4", tab="scoring")
    session.wait_settled(ms=400)

    hdr = session.page.locator('[id^="sample-heading-"]').first
    hdr_circle = hdr.locator("span[class*='circle']").count() > 0
    hdr_html_frag = hdr.evaluate("el => el.innerHTML")[-300:]

    sc = session.page.locator("#scoring-contents")
    if sc.count() == 0:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence="(#scoring-contents not present)",
            notes="Scoring tab failed to mount.",
        )
    score_span = sc.locator("span[class*='circle']")
    scoring_circle = score_span.count() > 0
    scoring_html = (
        score_span.first.evaluate("el => el.outerHTML") if scoring_circle else ""
    )

    evidence = (
        f"list cell uses circle badge: {list_circle}; "
        f"header uses circle badge: {hdr_circle}; "
        f"Scoring tab uses circle badge: {scoring_circle} "
        f"({scoring_html or '(plain text)'}). "
        f"list cell html: {list_html[:120]!r}"
    )

    if scoring_circle and not list_circle and not hdr_circle:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "Same value 'C' renders as a passFail circle badge in the "
                "Scoring tab but as plain categorical text in the list and "
                "header. SampleScores.tsx builds a fresh descriptor from the "
                "single value instead of reusing evalDescriptor."
            ),
        )
    if scoring_circle == list_circle == hdr_circle:
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=evidence,
            notes="All three views render with the same descriptor.",
        )
    return VerifyResult(
        verdict="CONFIRMED",
        evidence=evidence,
        notes=(
            "Some views use the circle badge, others don't — descriptors "
            "still diverge (partial)."
        ),
    )
