"""Repro for F21.10 — multi-log SamplesGrid vs single-log SampleList format the
same data differently.

Two `@task` defs → two `.eval` files in `logs/20-samples/`. The bug only
manifests when **both** logs are present and you open the multi-log Samples
panel.

Run:
    ./findings/repros/run.sh findings/repros/tasks/20-samples/F21.10_multilog_grid_format_diverges.py 20-samples
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
    Score,
    Scorer,
    Target,
    accuracy,
    mean,
    scorer,
)
from inspect_ai.solver import (  # noqa: E402
    Generate,
    Solver,
    TaskState,
    solver,
)

DESC = bug_description(
    finding_id="F21.10",
    title="Multi-log SamplesGrid and single-log SampleList format the same score differently",
    where_to_look=(
        "**(1) Multi-log grid:** from the log-listing page click the "
        "**Samples** button (top-right, next to *Tasks* / *Folders*) to open "
        "the cross-log grid; scroll right to the `passfail` / `numeric` / "
        "`dictscore` columns on the `F21.10_multilog_*` rows. "
        "**(2) Single-log list:** click the `F21.10_multilog_a` task → "
        "**Samples** tab → click the **SCORERS:** dropdown (top-right) → "
        "**All** so the `PASSFAIL`, `NUMERIC`, `A`, `B` columns all appear. "
        "Compare the same sample (id `2`) in both views."
    ),
    observed=(
        "• `passfail` score `C`: single-log list → **green circle badge**; "
        "multi-log grid → plain black text `C`.  "
        "• `numeric` score `2.0`: single-log list → `2` "
        "(`formatDecimalNoTrailingZeroes`); multi-log grid → `2.000` "
        "(`value.toFixed(3)`).  "
        "• `dictscore` `{a:1,b:0}`: single-log list → split into separate "
        "per-key columns `A`=`1`, `B`=`0`; multi-log grid → raw "
        '`{"a":1,"b":0}` JSON string in one cell.'
    ),
    expected=(
        "Both grids should reuse `getScoreDescriptorForValues` so the same "
        "score renders identically everywhere."
    ),
    extra=(
        "Both `F21.10_multilog_a` and `F21.10_multilog_b` are generated so "
        "the cross-log **Samples** view has multiple rows with these scorers."
    ),
)


@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        return await generate(state)

    return solve


@scorer(metrics=[accuracy()])
def passfail() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        return Score(value="C" if int(str(state.sample_id)) % 2 == 0 else "I")

    return score


@scorer(metrics=[mean()])
def numeric() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        # Integer-valued floats make the .toFixed(3) vs no-trailing-zeroes
        # divergence obvious: 1 vs 1.000.
        return Score(value=float(int(str(state.sample_id)) % 3))

    return score


@scorer(metrics={"a": [mean()], "b": [mean()]})
def dictscore() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        return Score(value={"a": 1.0, "b": 0.0})

    return score


def _samples() -> list[Sample]:
    # IDs 2 and 10 to expose lexical-vs-numeric ID sort.
    return [Sample(id=i, input=DESC, target="n/a") for i in (2, 10)]


@task
def f21_10_multilog_a() -> Task:
    return Task(
        name="F21.10_multilog_a",
        dataset=_samples(),
        solver=repro_solver(),
        scorer=[passfail(), numeric(), dictscore()],
    )


@task
def f21_10_multilog_b() -> Task:
    return Task(
        name="F21.10_multilog_b",
        dataset=_samples(),
        solver=repro_solver(),
        scorer=[passfail(), numeric(), dictscore()],
    )
