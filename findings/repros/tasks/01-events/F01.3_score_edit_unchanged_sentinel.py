"""Repro for F01.3 — ScoreEditEventView renders the literal "UNCHANGED" sentinel.

Run:
    ./findings/repros/run.sh findings/repros/tasks/01-events/F01.3_score_edit_unchanged_sentinel.py 01-events
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.event import ScoreEditEvent  # noqa: E402
from inspect_ai.log import ProvenanceData, transcript  # noqa: E402
from inspect_ai.scorer import (  # noqa: E402
    Score,
    ScoreEdit,
    Scorer,
    Target,
    accuracy,
    scorer,
)
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

DESC = bug_description(
    finding_id="F01.3",
    title="ScoreEditEventView renders the literal 'UNCHANGED' sentinel as data",
    where_to_look=(
        "Transcript tab → scroll to the **Edit Score** event (between the "
        "Model Call and Score events) → look at the **Updated Values** grid"
    ),
    observed=(
        "Under *Updated Values*, the **Value** row shows the string "
        "`UNCHANGED` rendered like a real score value, and the "
        "**Explanation** row shows the literal text `UNCHANGED`."
    ),
    expected=(
        "The Value and Explanation rows should be hidden (or show "
        "`[unchanged]`), since this edit only modified `answer`. Only the "
        "Answer row should show a new value (`edited-answer-only`)."
    ),
    extra=(
        "The `ScoreEdit` model uses the string literal `'UNCHANGED'` as a "
        "sentinel default for fields the editor did not touch. The view "
        "checks the sentinel for `answer` and `metadata` but **not** for "
        "`value` or `explanation`, so those leak through verbatim."
    ),
)


@solver
def emit_score_edit() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        state = await generate(state)
        # ScoreEdit with value + explanation left at default → both are the
        # literal string "UNCHANGED". The viewer should hide those fields,
        # but F01.3 says it renders them as if they were real data.
        edit = ScoreEdit(
            answer="edited-answer-only",
            provenance=ProvenanceData(
                author="repro-harness",
                reason="Demonstrate F01.3: only `answer` is changed; "
                "value & explanation remain UNCHANGED sentinel.",
            ),
        )
        transcript()._event(ScoreEditEvent(score_name="repro_scorer", edit=edit))
        return state

    return solve


@scorer(metrics=[accuracy()])
def repro_scorer() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        del state, target
        return Score(
            value=1.0,
            answer="original-answer",
            explanation="Original explanation from the scorer (NOT the edit).",
        )

    return score


@task
def f01_3_score_edit_unchanged_sentinel() -> Task:
    return Task(
        name="F01.3_score_edit_unchanged_sentinel",
        dataset=[Sample(id="F01.3", input=DESC, target="n/a")],
        solver=emit_score_edit(),
        scorer=repro_scorer(),
    )
