"""Repro for F05.5 — ScoreEditEventView hides edited value when it is 0/False/"".

Run:
    ./findings/repros/run.sh findings/repros/tasks/01-events/F05.5_score_edit_falsy_value_hidden.py 01-events
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
    finding_id="F05.5",
    title="ScoreEditEventView hides edited `value` when it is `0` / `False` / `\"\"`",
    where_to_look=(
        "Transcript tab → the three **Edit Score** panels → **Updated Values** section"
    ),
    observed=(
        "**No Value row** in any panel's Updated Values section — only "
        "**Answer** `[unchanged]` and **Explanation** are listed. The user "
        "cannot see what the score was changed TO."
    ),
    expected=(
        "Each Updated Values section should show **Value: 0** / "
        "**Value: False** / **Value: (empty)** respectively. Editing "
        "`1 → 0` is the single most common manual score correction."
    ),
    extra=(
        "Root cause: `{event.edit.value ? <ScoreValue …/> : \"\"}` — "
        "truthy check.\n\n"
        "This is the **inverse** of F01.3: F01.3 shows the `\"UNCHANGED\"` "
        "sentinel when it shouldn't; F05.5 hides real falsy values when it "
        "should show them. Both are fixed by "
        "`event.edit.value !== kUnchangedSentinel`."
    ),
)


@solver
def emit_falsy_edits() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        del generate
        prov = ProvenanceData(
            author="repro-harness",
            reason="F05.5: edit score to a falsy value",
        )
        # Three edits, one per falsy type — each should show a Value row.
        transcript()._event(
            ScoreEditEvent(
                score_name="repro_scorer",
                edit=ScoreEdit(
                    value=0,
                    explanation="Edited value to **`0`** (int). The Value row "
                    "should show `0`, but F05.5 hides it.",
                    provenance=prov,
                ),
            )
        )
        transcript()._event(
            ScoreEditEvent(
                score_name="repro_scorer",
                edit=ScoreEdit(
                    value=False,
                    explanation="Edited value to **`False`** (bool). Value row hidden.",
                    provenance=prov,
                ),
            )
        )
        transcript()._event(
            ScoreEditEvent(
                score_name="repro_scorer",
                edit=ScoreEdit(
                    value="",
                    explanation="Edited value to **`\"\"`** (empty string). Value row hidden.",
                    provenance=prov,
                ),
            )
        )
        return state

    return solve


@scorer(metrics=[accuracy()])
def repro_scorer() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        del state, target
        return Score(value=1.0, answer="original", explanation="original score = 1.0")

    return score


@task
def f05_5_score_edit_falsy_value_hidden() -> Task:
    return Task(
        name="F05.5_score_edit_falsy_value_hidden",
        dataset=[Sample(id="F05.5", input=DESC, target="n/a")],
        solver=emit_falsy_edits(),
        scorer=repro_scorer(),
    )
