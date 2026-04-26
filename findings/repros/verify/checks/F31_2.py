"""F31.2 — Solver step params are never displayed in the Plan card.

Repro defines ``parameterised_solver(my_param="F31.2_SHOULD_BE_VISIBLE",
threshold=0.777, retries=3)``. The Info-tab Plan card (``#task-plan-card-body``)
should show the solver name but NOT its params (whereas the adjacent Scorer
column DOES show params).
"""

from harness import VerifyResult, ViewerSession

BATCH = "30-loglist"

SENTINEL_PARAM = "F31.2_SHOULD_BE_VISIBLE"
THRESHOLD = "0.777"
SOLVER_NAME = "parameterised_solver"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_log("F31.2", tab="info")
    session.wait_settled(ms=500)

    plan = session.text_of("#task-plan-card-body")

    if SOLVER_NAME not in plan:
        return VerifyResult(
            "INCONCLUSIVE",
            plan[:400],
            notes=f"Solver name {SOLVER_NAME!r} not in Plan card — wrong tab/selector?",
        )

    has_param = SENTINEL_PARAM in plan or THRESHOLD in plan

    if not has_param:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=f"Plan card text: {plan!r}",
            notes=(
                "Solvers column shows only the bare solver name; "
                f"{SENTINEL_PARAM!r} and threshold {THRESHOLD} (both present in "
                "plan.steps[0].params) are nowhere in the card. SolversDetailView "
                "calls <DetailStep name=...> without params=."
            ),
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=f"Plan card text: {plan!r}",
        notes="Solver params now visible in Plan card.",
    )
