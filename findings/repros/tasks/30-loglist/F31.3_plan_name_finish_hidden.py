"""Repro for F31.3 — EvalPlan.name and EvalPlan.finish are never surfaced.

Builds a ``Plan`` with an explicit ``name`` and a ``finish`` solver. The
viewer's PlanDetailView reads only ``plan.steps``.

Run:
    ./findings/repros/run.sh findings/repros/tasks/30-loglist/F31.3_plan_name_finish_hidden.py 30-loglist
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.scorer import match  # noqa: E402
from inspect_ai.solver import (  # noqa: E402
    Generate,
    Plan,
    Solver,
    TaskState,
    solver,
)

DESC = bug_description(
    finding_id="F31.3",
    title="EvalPlan.name is never displayed (plan.finish half of the finding is FALSE — see below)",
    where_to_look=(
        "Close this sample → log-level **Info** tab → **SUMMARY** "
        "card. The plan is named "
        "`F31.3_PLAN_NAME_SHOULD_APPEAR_SOMEWHERE` — **Ctrl-F for "
        "that string** on the Info tab and on the Task tab."
    ),
    observed=(
        "Zero hits. `plan.name` is in the log JSON (JSON tab → "
        "`plan.name`) but `PlanDetailView.tsx:26` reads only "
        "`plan?.steps`, and the middle column heading in the "
        "SUMMARY card is the hard-coded literal **SOLVERS**."
    ),
    expected=(
        "The plan name `F31.3_PLAN_NAME_SHOULD_APPEAR_SOMEWHERE` "
        "shown somewhere — e.g. as the SOLVERS column heading, or "
        "as a row in the Task tab's TASK INFO card."
    ),
    extra=(
        "**✅ `plan.finish` half of the original finding is "
        "FALSE_POSITIVE.** The finding claims the finish solver is "
        "'silently omitted from the solver chain diagram'. It is "
        "**not** omitted: on the Info tab the SOLVERS column reads "
        "`f31_3_main_step → f31_3_finish_solver` — the finish step "
        "is right there. `_eval/task/log.py:361-362` appends "
        "`plan.finish` to `eval_plan.steps` before writing the log, "
        "so the viewer's `steps`-only iteration already shows it. "
        "Only the `plan.name` claim survives.\n\n"
        "**Note:** impact is minor — `Plan` is deprecated "
        "(`solver/_plan.py:67`) and `EvalPlan.name` defaults to "
        "`\"plan\"`, so very few logs carry an informative value."
    ),
)


@solver
def f31_3_main_step() -> Solver:
    """Emit banner + generate in one Plan step so the banner isn't in a collapsed SUB-AGENT span."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        return await generate(state)

    return solve


@solver
def f31_3_finish_solver() -> Solver:
    """The Plan's `finish` step — should be visibly distinguished as such."""

    async def solve(state: TaskState, _generate: Generate) -> TaskState:
        state.metadata["finish_ran"] = True
        return state

    return solve


@task
def f31_3_plan_name_finish_hidden() -> Task:
    return Task(
        name="F31.3_plan_name_finish_hidden",
        dataset=[Sample(id="F31.3", input=DESC, target="n/a")],
        solver=Plan(
            name="F31.3_PLAN_NAME_SHOULD_APPEAR_SOMEWHERE",
            steps=[f31_3_main_step()],
            finish=f31_3_finish_solver(),
            internal=True,  # suppress Plan deprecation warning
        ),
        scorer=match(),
    )
