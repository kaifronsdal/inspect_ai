"""Repro for F90.14 — Same numeric score formatted three ways across three surfaces.

Produces TWO .eval files (A and B) so the multi-log Samples grid is populated.

Run:
    ./findings/repros/run.sh findings/repros/tasks/90-cross/F90.14_numeric_score_precision.py 90-cross
"""

from __future__ import annotations

import sys
from pathlib import Path

# make findings/repros/_common.py importable
sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.scorer import Score, Scorer, Target, mean, scorer  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

DESC = bug_description(
    finding_id="F90.14",
    title="Numeric score 1.0 renders as `1.0` / `1` / `1.000` on three adjacent surfaces",
    where_to_look=(
        "Every sample scores exactly `1.0`, so the headline `mean` is also "
        "exactly `1.0`. Compare the SAME value in three places. "
        "**(1) `1.0`** — open this log → top-right headline metric (`MEAN` "
        "over **`1.0`**); also root log listing → **Tasks** view → **Score** "
        "column (`formatPrettyDecimal`, forces ≥1 decimal). "
        "**(2) `1`** — same log → **Sample** tab → sample-list row → **Score** "
        "column shows **`1`** (`formatDecimalNoTrailingZeroes`, strips the "
        "trailing zero). Surfaces 1 and 2 are visible together on one screen. "
        "**(3) `1.000`** — go back to the root log listing → click the "
        "**Samples** toggle (top-right, next to Tasks/Folders) → the "
        "**`returns_one_point_zero`** column shows **`1.000`** for both "
        "F90.14 rows (`value.toFixed(3)`)."
    ),
    observed="`1.0` vs `1` vs `1.000` for the identical underlying value.",
    expected="One numeric formatter shared across headline metrics, sample list, and multi-log grid.",
    extra=(
        "Source: `ResultsPanel.tsx:225` / `log-list/.../hooks.tsx:177` use "
        "`formatPrettyDecimal`; `NumericScoreDescriptor.tsx:31` uses "
        "`formatDecimalNoTrailingZeroes`; `samples-panel/samples-grid/"
        "hooks.tsx:208` uses `value.toFixed(3)`.\n\n"
        "**Requires both `F90.14_..._A` and `F90.14_..._B` logs in the same "
        "directory** so the multi-log Samples grid (surface 3) has two "
        "`1.000` rows to compare."
    ),
)


@scorer(metrics=[mean()])
def returns_one_point_zero() -> Scorer:
    """Every sample scores exactly ``1.0`` → headline mean is exactly ``1.0``."""

    async def score(_state: TaskState, _target: Target) -> Score:
        return Score(value=1.0, explanation="Exactly 1.0 — watch how it's formatted.")

    return score


@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, gen: Generate) -> TaskState:
        emit_bug_banner(DESC)
        return await gen(state)

    return solve


_SAMPLE = Sample(id="F90.14", input=DESC, target="n/a")


@task
def f90_14_numeric_score_precision_A() -> Task:  # noqa: N802
    return Task(
        name="F90.14_numeric_score_precision_A",
        dataset=[_SAMPLE],
        solver=repro_solver(),
        scorer=returns_one_point_zero(),
    )


@task
def f90_14_numeric_score_precision_B() -> Task:  # noqa: N802
    return Task(
        name="F90.14_numeric_score_precision_B",
        dataset=[_SAMPLE],
        solver=repro_solver(),
        scorer=returns_one_point_zero(),
    )
