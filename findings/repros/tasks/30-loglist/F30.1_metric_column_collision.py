"""Repro for F30.1 — Per-metric score columns collide when scorers share a metric name.

Two scorers in one task, both reporting an ``accuracy`` metric with DIFFERENT
values (0.0 vs 1.0). The log-list grid keys columns by bare metric name, so
only one ``accuracy`` column appears and the last scorer iterated wins.

Run:
    ./findings/repros/run.sh findings/repros/tasks/30-loglist/F30.1_metric_column_collision.py 30-loglist
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.scorer import (  # noqa: E402
    CORRECT,
    INCORRECT,
    Score,
    Scorer,
    Target,
    accuracy,
    scorer,
    stderr,
)
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

DESC = bug_description(
    finding_id="F30.1",
    title="Log-list metric columns collide when 2 scorers share a metric name",
    where_to_look=(
        "**Log-list grid** (breadcrumb back to `30-loglist`). Click **Choose "
        "Columns** (top-right) — the **Scorers** section offers only ONE "
        "`accuracy` checkbox. Tick it → a single `accuracy` column is added at "
        "the far right."
    ),
    observed=(
        "One `accuracy` checkbox, one `accuracy` column. Row "
        "`F30.1_metric_collision_a` shows **1.0** (scorer_beta — last in its "
        "scorer list); row `…_b` shows **0.0** (scorer_alpha — last in *its* "
        "list). Same scorers, same data — value flips with scorer order. The "
        "header says just `accuracy` with no scorer attribution, and the "
        "headline `Score` column on the same row shows the *other* scorer's "
        "value (`0.0` vs `1.0`)."
    ),
    expected=(
        "One column per scorer/metric pair — e.g. `scorer_alpha/accuracy` and "
        "`scorer_beta/accuracy` — or any presentation that keeps scorer "
        "identity instead of overwriting `score_${metricName}`."
    ),
    extra=(
        "For contrast open either log: the title-bar score table correctly "
        "lists **both** `scorer_alpha` (accuracy 0.0) and `scorer_beta` "
        "(accuracy 1.0). Only the log-list grid collapses them.\n\n"
        "Two `@task`s are defined with the scorer list **reversed** between "
        "them, so the two grid rows display contradictory `accuracy` values "
        "for identical underlying scores."
    ),
)


@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        return await generate(state)

    return solve


@scorer(metrics=[accuracy(), stderr()])
def scorer_alpha() -> Scorer:
    """Always wrong → accuracy = 0.0."""

    async def score(_state: TaskState, _target: Target) -> Score:
        return Score(value=INCORRECT, answer="alpha", explanation="alpha → accuracy 0.0")

    return score


@scorer(metrics=[accuracy(), stderr()])
def scorer_beta() -> Scorer:
    """Always right → accuracy = 1.0."""

    async def score(_state: TaskState, _target: Target) -> Score:
        return Score(value=CORRECT, answer="beta", explanation="beta → accuracy 1.0")

    return score


@task
def f30_1_metric_collision_a() -> Task:
    return Task(
        name="F30.1_metric_collision_a",
        dataset=[Sample(id="F30.1", input=DESC, target="n/a")],
        solver=repro_solver(),
        scorer=[scorer_alpha(), scorer_beta()],  # beta last → grid accuracy = 1.0
    )


@task
def f30_1_metric_collision_b() -> Task:
    return Task(
        name="F30.1_metric_collision_b",
        dataset=[Sample(id="F30.1-b", input=DESC, target="n/a")],
        solver=repro_solver(),
        scorer=[scorer_beta(), scorer_alpha()],  # alpha last → grid accuracy = 0.0
    )
