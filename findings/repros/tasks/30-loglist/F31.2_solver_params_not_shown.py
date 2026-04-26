"""Repro for F31.2 — Solver step params are never displayed in the Plan card.

A custom ``@solver`` is given distinctive parameters; the Plan card shows only
the solver *name* with an arrow, never the params (whereas scorer params in
the same card ARE shown).

Run:
    ./findings/repros/run.sh findings/repros/tasks/30-loglist/F31.2_solver_params_not_shown.py 30-loglist
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.scorer import includes  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

DESC = bug_description(
    finding_id="F31.2",
    title="Info → Summary card shows solver name but never its params",
    where_to_look=(
        "Open this log → **Info** tab → **SUMMARY** card → **SOLVERS** "
        "column. Compare against the **SCORER** column to its right."
    ),
    observed=(
        "SOLVERS column shows only `parameterised_solver` (bare name). "
        "The params `my_param='F31.2_SHOULD_BE_VISIBLE'`, "
        "`threshold=0.777`, `retries=3` are nowhere on the page — even "
        "though `EvalPlanStep.params` carries them (check log-level "
        "**JSON** tab → `plan.steps[0].params`). Meanwhile the SCORER "
        "column *does* render its param grid: `includes` shows "
        "`IGNORE_CASE true` underneath."
    ),
    expected=(
        "Solver params listed under the solver name, the same way the "
        "SCORER column already lists scorer params. Root cause: "
        "`SolversDetailView` calls `<DetailStep name={step.solver}>` but "
        "omits `params={step.params}`; `ScorerDetailView` passes `params`."
    ),
)


@solver
def parameterised_solver(
    my_param: str = "F31.2_SHOULD_BE_VISIBLE",
    threshold: float = 0.777,
    retries: int = 3,
) -> Solver:
    """Solver whose parameters should appear in the Info-tab Plan card."""

    # reference the params so linters don't strip them
    _ = (my_param, threshold, retries)

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        return await generate(state)

    return solve


@task
def f31_2_solver_params_not_shown() -> Task:
    return Task(
        name="F31.2_solver_params_not_shown",
        dataset=[Sample(id="F31.2", input=DESC, target="n/a")],
        solver=parameterised_solver(
            my_param="F31.2_SHOULD_BE_VISIBLE", threshold=0.777, retries=3
        ),
        # Pass ignore_case explicitly so it's recorded in results.scores[0].params
        # and the SCORER column visibly renders a param grid — demonstrating the
        # asymmetry (scorer params ARE shown, solver params are NOT).
        scorer=includes(ignore_case=True),
    )
