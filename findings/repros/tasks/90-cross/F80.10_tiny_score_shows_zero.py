"""Repro for F80.10 — formatPrettyDecimal / formatDecimalNoTrailingZeroes break on scientific notation.

Run:
    ./findings/repros/run.sh findings/repros/tasks/90-cross/F80.10_tiny_score_shows_zero.py 90-cross
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

TINY = 0.0000001234  # 1.234e-7 — Number.toString() returns "1.234e-7" in JS

DESC = bug_description(
    finding_id="F80.10",
    title="formatDecimalNoTrailingZeroes collapses 1.234e-7 to '0.000000' (discontinuity at 1e-6)",
    where_to_look=(
        "This sample's score is exactly `0.0000001234` (= `1.234e-7`). "
        "Close this dialog and look at the **Samples tab → Score "
        "column** for the single row (also shown top-right of this "
        "dialog header). Both render via `formatDecimalNoTrailingZeroes`."
    ),
    observed=(
        "Score column shows **`0.000000`** — every significant digit "
        "dropped, *trailing zeros added*, indistinguishable from a "
        "true zero. Yet a score of `0.0001234` on the same code path "
        "renders as `0.0001234` (full precision). The collapse happens "
        "discontinuously at the `1e-6` boundary where JS "
        "`Number.toString()` switches to exponential notation."
    ),
    expected=(
        "Render in exponential form (`1.234e-7`) or with enough "
        "significant figures to distinguish from zero (e.g. "
        "`0.000000123`) — consistent with how the same formatter "
        "handles `0.0001234`."
    ),
    extra=(
        "Root cause (`packages/util/src/format.ts:88-98`): "
        "`num.toString().split('.')` is used to count decimal places. "
        "For `|n| < 1e-6` JS returns `'1.234e-7'`, so the 'decimal "
        "part' is `'234e-7'` (length 6) → `toFixed(6)` → `'0.000000'`."
        "\n\n"
        "**Not the bug:** the title-bar headline `MEAN 0.000` and the "
        "log-list `0.000` are *ordinary 3-dp rounding* via "
        "`formatPrettyDecimal` — any value `< 0.0005` rounds to "
        "`0.000` there regardless of the `toString()` issue, so they "
        "are not evidence of this defect."
        "\n\n"
        "**Note:** impact is minor — scores `< 1e-6` are rare in "
        "typical accuracy/match workloads, and the raw value is still "
        "visible in the Scoring tab and JSON. The defect is the "
        "discontinuity / contradiction of the function's "
        "no-trailing-zeroes contract, not a common-path display loss."
    ),
)


@scorer(metrics=[mean()])
def tiny_scorer() -> Scorer:
    """Returns 1.234e-7 so JS ``Number.toString()`` yields exponential notation."""

    async def score(_state: TaskState, _target: Target) -> Score:
        return Score(
            value=TINY,
            explanation=f"Score is {TINY!r} (1.234e-7) — non-zero, but tiny.",
        )

    return score


@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, gen: Generate) -> TaskState:
        emit_bug_banner(DESC)
        return await gen(state)

    return solve


@task
def f80_10_tiny_score_shows_zero() -> Task:
    return Task(
        name="F80.10_tiny_score_shows_zero",
        dataset=[Sample(id="F80.10", input=DESC, target="n/a")],
        solver=repro_solver(),
        scorer=tiny_scorer(),
    )
