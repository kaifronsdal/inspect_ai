"""F31.3 — EvalPlan.name is never surfaced. (plan.finish half is FALSE_POSITIVE.)

Re-audited 2026-04-24. The finding has two claims:

  (a) ``plan.name`` never shown — **CONFIRMED**. ``PlanDetailView.tsx:26``
      reads only ``plan?.steps``; the column header is the literal "Solvers".
  (b) ``plan.finish`` "silently omitted from the solver chain diagram" —
      **FALSE_POSITIVE**. ``_eval/task/log.py:361-362`` appends
      ``plan.finish`` to ``eval_plan.steps`` before writing the log, so the
      finish solver IS in the diagram. The viewer reading ``plan.finish``
      would in fact duplicate it.

Primary assertion: the plan-name sentinel is absent from Info AND Task tabs;
the finish solver IS present in the Solvers card (proves (b) false).
"""

from harness import VerifyResult, ViewerSession

BATCH = "30-loglist"

PLAN_NAME = "F31.3_PLAN_NAME_SHOULD_APPEAR_SOMEWHERE"
FINISH_STEP = "f31_3_finish_solver"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_log("F31.3", tab="info")
    session.wait_settled(ms=500)

    info_text = session.all_text()
    plan_card = session.text_of("#task-plan-card-body")

    session.goto_log("F31.3", tab="task")
    session.wait_settled(ms=400)
    task_text = session.all_text()

    name_shown = PLAN_NAME in info_text or PLAN_NAME in task_text
    finish_in_card = FINISH_STEP in plan_card

    evidence = (
        f"plan.name {PLAN_NAME!r} on Info tab: {PLAN_NAME in info_text}, "
        f"on Task tab: {PLAN_NAME in task_text}; "
        f"finish solver in Solvers card: {finish_in_card}; "
        f"Plan card text: {plan_card!r}"
    )

    if not name_shown and finish_in_card:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "PARTIAL: plan.name half CONFIRMED (sentinel absent from "
                "Info AND Task tabs). plan.finish half is FALSE_POSITIVE — "
                f"{FINISH_STEP!r} IS in the Solvers diagram because "
                "_eval/task/log.py:361-362 appends finish to plan.steps. "
                "The finding's 'silently omitted' claim is wrong; the "
                "suggested fix (append plan.finish in the viewer) would "
                "duplicate it. Recommend: keep finding for plan.name only."
            ),
        )
    if name_shown:
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=evidence,
            notes="plan.name now visible.",
        )
    return VerifyResult(
        verdict="CONFIRMED",
        evidence=evidence,
        notes=(
            "plan.name absent. (finish solver also absent from card — "
            "unexpected; check whether log writer changed.)"
        ),
    )
