"""F31.13 — Start/End/Duration show epoch-0 dates when stats.started_at is empty.

The repro log has ``header.json → stats.started_at = ""`` (and
``completed_at = ""``). ``TaskTab.tsx`` does
``new Date(evalStats?.started_at || 0)`` → Jan 1 1970.

We open the log-level **Task** tab, grab the Task Info card text, and look
for "1970". If present → CONFIRMED. If the rows are omitted or show a real
date → FALSE_POSITIVE (there's a fallback we missed).
"""

from pathlib import Path

from harness import VerifyResult, ViewerSession

BATCH = "30-loglist"
ART = Path(__file__).resolve().parents[1] / "artifacts" / "per-finding"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_log("F31.13", tab="task")
    session.wait_settled(ms=500)

    body = session.all_text()
    # The Task Info card body has id="task-card-config" (TaskTab.tsx:127).
    card = session.page.locator("#task-card-config")
    card_text = card.inner_text() if card.count() else "<#task-card-config not found>"

    ART.mkdir(parents=True, exist_ok=True)
    shot = session.screenshot(ART / "F31.13-task-tab.png")

    has_1970 = "1970" in card_text or "1970" in body
    has_start_row = "Start" in card_text

    evidence = f"#task-card-config text:\n{card_text}"[:800]

    if has_1970:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "Task tab shows '1970' for Start/End — `new Date(\"\" || 0)` "
                "fell back to the Unix epoch instead of omitting the rows. "
                "Note: requires a hand-edited / interrupted log to trigger; "
                "completed evals always set started_at."
            ),
            artifacts=[shot],
        )

    if not has_start_row:
        return VerifyResult(
            verdict="FALSE_POSITIVE",
            evidence=evidence,
            notes=(
                "Start/End rows are omitted entirely when started_at is "
                "empty — the viewer already guards this case. Finding "
                "description is wrong."
            ),
            artifacts=[shot],
        )

    return VerifyResult(
        verdict="FALSE_POSITIVE",
        evidence=evidence,
        notes=(
            "Start row is present but does not show 1970 — the viewer falls "
            "back to something other than `new Date(0)` (e.g. eval.created). "
            "Finding description is wrong about user-visible behaviour."
        ),
        artifacts=[shot],
    )
