"""Repro for F20.14 — Object/List score descriptors mis-format `0` and `false`.

(Assignment row was labelled F20.13 but the described behaviour — "0/False
skips numeric formatter" — is finding **F20.14** in
`findings/20-sample-display-scores.md`. F20.13 is a pure code-smell with no
visible viewer effect.)

Run:
    ./findings/repros/run.sh findings/repros/tasks/20-samples/F20.14_list_score_zero_unformatted.py 20-samples
"""

from __future__ import annotations

import sys
from pathlib import Path

# make findings/repros/_common.py importable
sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.scorer import (  # noqa: E402
    Metric,
    SampleScore,
    Score,
    Scorer,
    Target,
    metric,
    scorer,
)
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402


@metric
def noop() -> Metric:
    """Metric that ignores non-scalar score values (mean() would crash)."""

    def compute(scores: list[SampleScore]) -> float:
        return 0.0

    return compute


DESC = bug_description(
    finding_id="F20.14",
    title="List score descriptor skips the numeric formatter for `0`",
    where_to_look=(
        "**Samples** tab → **LIST_SCORER** column (widen the column to see the "
        "full value, or open any sample and read the **SCORE** field in the "
        "header at top-right)."
    ),
    observed=(
        "List score `[0, 0.333333, 1]` renders as `[0, 0.333, 1.0]` — the "
        "first element `0` is bare (`String(0)`) while the third element `1` "
        "is formatted as `1.0` (`formatPrettyDecimal`), so two integer values "
        "in the same cell get inconsistent decimal places."
    ),
    expected=(
        "`0` should go through the same `formatPrettyDecimal` path as every "
        "other numeric element and render as `0.0`, giving `[0.0, 0.333, 1.0]`."
    ),
    extra=(
        "Root cause (`ListScoreDescriptor.tsx`): `value && isNumeric(value) ? "
        "formatPrettyDecimal(...) : String(value)` — `0` is falsy so the `&&` "
        "short-circuits. The identical guard exists in "
        "`ObjectScoreDescriptor.tsx` for dict-valued scores. Note there is no "
        "single `dict_scorer` column in the grid — the SCORERS picker exposes "
        "the dict keys (`zero` / `third` / `one`) individually."
    ),
)


@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        return await generate(state)

    return solve


@scorer(metrics=[noop()])
def list_scorer() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        return Score(value=[0.0, 0.333333, 1.0], answer="list-of-floats")

    return score


@scorer(metrics=[noop()])
def dict_scorer() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        return Score(
            value={"zero": 0.0, "third": 0.333333, "one": 1.0},
            answer="dict-of-floats",
        )

    return score


@task
def f20_14_list_score_zero_unformatted() -> Task:
    samples = [
        Sample(id=f"sample_{i}", input=DESC, target="n/a") for i in (1, 2, 3)
    ]
    return Task(
        name="F20.14_list_score_zero_unformatted",
        dataset=samples,
        solver=repro_solver(),
        scorer=[list_scorer(), dict_scorer()],
    )
