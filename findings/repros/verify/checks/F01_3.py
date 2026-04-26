"""F01.3 — ScoreEditEventView renders the literal "UNCHANGED" sentinel.

Repro: ScoreEdit(answer="edited-answer-only") — value & explanation default to
the string "UNCHANGED". Panel structure (from inner_text):

    UPDATED VALUES
    VALUE
    <…>          ← bug: literal "UNCHANGED"
    ANSWER
    edited-answer-only
    EXPLANATION
    <…>          ← bug: literal "UNCHANGED"

Anchor on the line *immediately after* the VALUE / EXPLANATION labels — the
provenance.reason text also contains the word UNCHANGED so a plain grep would
false-positive.
"""

from harness import VerifyResult, ViewerSession

BATCH = "01-events"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F01.3", tab="transcript", log="F01.3-score")
    session.expand_event("Edit Score")
    text = session.event_panel_text("Edit Score")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    def value_after(label: str) -> str:
        for i, ln in enumerate(lines):
            if ln.upper() == label:
                return lines[i + 1] if i + 1 < len(lines) else ""
        return "<label-not-found>"

    val = value_after("VALUE")
    expl = value_after("EXPLANATION")
    ans = value_after("ANSWER")

    evidence = (
        f"VALUE → {val!r}\n"
        f"ANSWER → {ans!r}\n"
        f"EXPLANATION → {expl!r}"
    )

    value_leaks = val == "UNCHANGED"
    expl_leaks = expl == "UNCHANGED"

    if value_leaks or expl_leaks:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                f"Sentinel rendered as data — value:{value_leaks}, "
                f"explanation:{expl_leaks}. Answer correctly shows "
                f"'edited-answer-only'."
            ),
        )
    if val == "<label-not-found>":
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=text[:400],
            notes="Could not locate VALUE label in Edit Score panel.",
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=evidence,
        notes="Neither Value nor Explanation shows the UNCHANGED sentinel.",
    )
