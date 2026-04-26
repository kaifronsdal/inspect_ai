"""F20.5 — Scoring tab omits `sample.target`.

Where: Sample → Scoring tab. The tab renders an ``Input`` label + the
SampleScoresGrid (Scorer / Answer / Score / Explanation). No ``Target`` row.

The sentinel target string also appears in the bug-description Input text
*and* the scorer's Explanation, so we cannot grep for the sentinel. Instead
we assert on the set of ``.text-style-label`` headings inside
``#scoring-contents``.
"""

from harness import VerifyResult, ViewerSession

BATCH = "20-samples"

SENTINEL = "F20.5_TARGET_SHOULD_APPEAR_IN_SCORING_TAB"


def check(session: ViewerSession) -> VerifyResult:
    # Land on the log first so the SPA's per-log state is initialised, then
    # deep-link the sample (direct sample → sample nav across logs sometimes
    # leaves the tab pane unmounted).
    session.goto_log("F20.5", tab="samples")
    session.goto_sample("F20.5", log="F20.5", tab="scoring")
    session.wait_settled(ms=500)

    sc = session.page.locator("#scoring-contents")
    if sc.count() == 0:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence="(#scoring-contents not present)",
            notes="Scoring tab pane did not mount.",
        )

    labels = [t.upper() for t in sc.locator(".text-style-label").all_inner_texts()]

    # Sanity: the header row above the tabs *does* show the target sentinel
    # (so we know the sample has one).
    hdr_text = session.page.locator('[id^="sample-heading-"]').first.inner_text()
    target_in_header = SENTINEL in hdr_text

    evidence = (
        f"Scoring-tab labels: {labels}; "
        f"target sentinel present in header row: {target_in_header}"
    )

    if "INPUT" not in labels:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=evidence,
            notes="Scoring tab missing expected 'Input' label — layout changed?",
        )

    if "TARGET" not in labels:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "Scoring tab shows Input + Scorer/Answer/Score/Explanation but "
                "no Target row. A reviewer cannot see what the answer is "
                "compared against without leaving the tab."
            ),
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=evidence,
        notes="A 'Target' label is present in the Scoring tab.",
    )
