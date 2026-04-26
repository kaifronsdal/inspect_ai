"""Repro for F20.5 — Scoring tab omits `target`.

Run:
    ./findings/repros/run.sh findings/repros/tasks/20-samples/F20.5_scoring_tab_omits_target.py 20-samples
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

SENTINEL_TARGET = "F20.5_TARGET_SHOULD_APPEAR_IN_SCORING_TAB"

DESC = bug_description(
    finding_id="F20.5",
    title="Scoring tab omits `sample.target`",
    where_to_look="Open this sample → click the **Scoring** tab.",
    observed=(
        "The Scoring tab body renders an **Input** heading, then a grid with "
        "columns **Scorer / Answer / Score / Explanation**. There is no "
        "**Target** heading or row anywhere in the tab body — the view never "
        f"reads `sample.target` (here `{SENTINEL_TARGET}`)."
    ),
    expected=(
        "A **Target** heading + value rendered alongside **Input**, for parity."
    ),
    extra=(
        "**Note:** impact is minor — the pinned sample header directly above "
        "the tab strip already shows a labelled **Target** column with the "
        "full sentinel, visible on screen at the same time as the Scoring tab "
        "(no navigation needed). The only residual gap is that the header "
        "truncates long values while **Input** gets a full expandable panel."
    ),
)


@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        return await generate(state)

    return solve


@scorer(metrics=[accuracy()])
def trivial_scorer() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        return Score(
            value=1.0,
            answer="model-answer-here",
            explanation="Trivial scorer — always returns 1.0.",
        )

    return score


@task
def f20_5_scoring_tab_omits_target() -> Task:
    return Task(
        name="F20.5_scoring_tab_omits_target",
        dataset=[Sample(id="F20.5", input=DESC, target=SENTINEL_TARGET)],
        solver=repro_solver(),
        scorer=trivial_scorer(),
    )
