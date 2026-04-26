"""Repro for F21.2 — categorical-score filter completions show `undefined`.

Run:
    ./findings/repros/run.sh findings/repros/tasks/20-samples/F21.2_categorical_filter_undefined.py 20-samples
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
    finding_id="F21.2",
    title="Categorical-score filter autocomplete suggests `undefined` instead of category values",
    where_to_look=(
        "Close this sample dialog → log-level **Samples** tab → click in the "
        "**FILTER:** input (top right) → type `category_scorer == ` (with the "
        "`==` and trailing space) → look at the autocomplete dropdown. Then "
        "clear the input and type just `category_scorer` → look at the info "
        "panel beside the highlighted dropdown item."
    ),
    observed=(
        "The dropdown offers a single `undefined` as the only category-value "
        "suggestion (above the generic variable list). The info panel reads "
        "`category_scorer: categorical` / `categories: undefined undefined "
        "undefined`. The actual values (`good`, `bad`, `ugly`) — visible in "
        "the score column right below — never appear."
    ),
    expected=(
        "The dropdown should offer `\"good\"`, `\"bad\"`, `\"ugly\"`; the info "
        "panel should read `categories: good bad ugly`."
    ),
    extra=(
        "`categoricalScoreDescriptor` sets `categories: values` (raw strings); "
        "every other descriptor uses `{val, text}` objects. "
        "`sampleFilterItems()` reads `(cat as Record).val` → `undefined` for "
        "bare strings. Fix: normalise to `{val, text}` or handle both shapes."
    ),
)


@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        return await generate(state)

    return solve


@scorer(metrics=[accuracy()])
def category_scorer() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        return Score(value=target.text, answer=target.text)

    return score


@task
def f21_2_categorical_filter_undefined() -> Task:
    # 3 distinct string values, none of them C/I/P/N → categoricalScoreDescriptor.
    samples = [
        Sample(id="cat_good", input=DESC, target="good"),
        Sample(id="cat_bad", input=DESC, target="bad"),
        Sample(id="cat_ugly", input=DESC, target="ugly"),
    ]
    return Task(
        name="F21.2_categorical_filter_undefined",
        dataset=samples,
        solver=repro_solver(),
        scorer=category_scorer(),
    )
