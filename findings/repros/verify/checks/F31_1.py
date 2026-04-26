"""F31.1 — EvalConfig is built but never rendered in the Task tab.

Repro sets ``epochs=7``, ``message_limit=42``, ``token_limit=999999``,
``fail_on_error=0.5``. None of these should appear anywhere in the Task tab
(or Info tab) because ``TaskTab.tsx`` copies ``evalSpec.config`` into a local
``config`` record and never references it.

Sentinel: ``999999`` is the most distinctive value (won't collide with the
embedded bug-description text, which lives in the *Samples* tab).
"""

from harness import VerifyResult, ViewerSession

BATCH = "30-loglist"

# (key, sentinel-value) pairs that uniquely identify rendered EvalConfig.
# We avoid "42" / "7" alone because they collide with timestamps / token counts.
CONFIG_NEEDLES = ["message_limit", "token_limit", "999999", "fail_on_error"]


def check(session: ViewerSession) -> VerifyResult:
    # Task tab
    session.goto_log("F31.1", tab="task")
    session.wait_settled(ms=500)
    task_text = session.all_text()
    task_hits = {n: (n in task_text) for n in CONFIG_NEEDLES}

    # Info tab (PlanCard) — second possible home for a Config card.
    session.goto_log("F31.1", tab="info")
    session.wait_settled(ms=500)
    info_text = session.all_text()
    info_hits = {n: (n in info_text) for n in CONFIG_NEEDLES}

    visible = sorted(k for k, v in {**task_hits, **info_hits}.items() if v)
    evidence = (
        f"Task-tab config matches: {task_hits}; Info-tab matches: {info_hits}"
    )

    if not visible:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "EvalConfig fields (epochs=7, message_limit=42, token_limit=999999, "
                "fail_on_error=0.5) are present in the .eval but absent from both "
                "the Task and Info tabs. The dead `config` loop in TaskTab.tsx:54-59 "
                "never feeds a card."
            ),
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=evidence,
        notes=f"EvalConfig now surfaced: {visible}",
    )
