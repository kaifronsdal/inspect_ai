"""Repro for F21.1 — score columns sort with ag-grid default, not descriptor.compare.

Run:
    ./findings/repros/run.sh findings/repros/tasks/20-samples/F21.1_score_column_sort_alphabetical.py 20-samples
"""

from __future__ import annotations

import sys
from pathlib import Path

# make findings/repros/_common.py importable
sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.scorer import Score, Scorer, Target, accuracy, scorer  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

DESC = bug_description(
    finding_id="F21.1",
    title="Score columns sort alphabetically, not semantically (descriptor.compare unused)",
    where_to_look=(
        "Close this sample → **Samples** tab (the log-level grid) → click the "
        "**Score** column header (rightmost) once to sort ascending."
    ),
    observed=(
        "Rows sort `C, I, N, P` — plain alphabetical. Badge colours go "
        "green → red → red → orange. The sample IDs encode the intended "
        "semantic rank (`expect_rank_1_C` … `expect_rank_4_N`); after sorting "
        "the ID column reads ranks **1, 3, 4, 2**."
    ),
    expected=(
        "`passFailScoreDescriptor.compare` defines the order `C → P → I → N` "
        "(Correct → Partial → Incorrect → Refusal). Sorting ascending should "
        "give sample IDs in rank order 1, 2, 3, 4 (green → orange → red → red)."
    ),
    extra=(
        "Every `ScoreDescriptor` implements `compare()` but `columns.tsx` "
        "supplies no `comparator` to ag-grid, so the default lexical sort on "
        "the raw value is used. Object/array scores would sort as "
        "`[object Object]` (effectively random)."
    ),
)


@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        return await generate(state)

    return solve


@scorer(metrics=[accuracy()])
def passfail_scorer() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        return Score(value=target.text, answer=target.text)

    return score


@task
def f21_1_score_column_sort_alphabetical() -> Task:
    # IDs encode the *expected* (semantic) sort rank so the bug is obvious
    # when the column is sorted and the IDs are out of order.
    samples = [
        Sample(id="expect_rank_1_C", input=DESC, target="C"),
        Sample(id="expect_rank_2_P", input=DESC, target="P"),
        Sample(id="expect_rank_3_I", input=DESC, target="I"),
        Sample(id="expect_rank_4_N", input=DESC, target="N"),
    ]
    return Task(
        name="F21.1_score_column_sort_alphabetical",
        dataset=samples,
        solver=repro_solver(),
        scorer=passfail_scorer(),
    )
