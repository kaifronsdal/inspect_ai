"""Repro for F90.3 — Transcript ScoreEvent bypasses the score-descriptor system.

Run:
    ./findings/repros/run.sh findings/repros/tasks/90-cross/F90.3_score_event_bypasses_descriptor.py 90-cross
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
    finding_id="F90.3",
    title="ScoreEventView renders score via String(value), not via ScoreDescriptor",
    where_to_look=(
        "This sample's score is the boolean `True`. Compare: "
        "**(1)** the **Score** column in the sample header (top "
        "right, next to Id/Input/Target/Answer) and **(2)** the "
        "**Scoring** tab — both render via `BooleanScoreDescriptor` "
        "→ a **green oval badge** reading `true`. Then **(3)** on "
        "the **Transcript** tab, scroll to the **SCORE** event panel "
        "at the bottom (already expanded, not collapsible) — its "
        "**Score** row renders via `ScoreValue → String(value)` → "
        "bare unstyled text **`true`** (no colour, no badge)."
    ),
    observed=(
        "Header Score column / sample list / Scoring tab all show a "
        "green oval badge for `true`. The transcript SCORE event "
        "panel's Score row shows plain unstyled text `true` for the "
        "same value."
    ),
    expected=(
        "The transcript ScoreEvent should render the value through "
        "the same `ScoreDescriptor.render()` path as the header, so "
        "boolean / pass-fail / numeric scores look identical "
        "everywhere they appear."
    ),
    extra=(
        "Source: `packages/inspect-components/src/transcript/"
        "ScoreValue.tsx:18-26` does `String(value)` for scalars, "
        "bypassing `apps/inspect/src/app/samples/descriptor/score/"
        "BooleanScoreDescriptor.tsx`. Same divergence applies to "
        '`"C"`/`"I"` pass-fail and to long-decimal numerics. '
        "Extends F20.4 / F21.10 — this is a fourth independent "
        "renderer for the same value."
    ),
)


@scorer(metrics=[accuracy()])
def boolean_scorer() -> Scorer:
    """Returns a Python ``True`` so the descriptor system picks BooleanScoreDescriptor."""

    async def score(_state: TaskState, _target: Target) -> Score:
        return Score(
            value=True,
            answer="yes",
            explanation="Boolean True — should render as a green badge everywhere.",
        )

    return score


@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, gen: Generate) -> TaskState:
        emit_bug_banner(DESC)
        return await gen(state)

    return solve


@task
def f90_3_score_event_bypasses_descriptor() -> Task:
    return Task(
        name="F90.3_score_event_bypasses_descriptor",
        dataset=[Sample(id="F90.3", input=DESC, target="n/a")],
        solver=repro_solver(),
        scorer=boolean_scorer(),
    )
