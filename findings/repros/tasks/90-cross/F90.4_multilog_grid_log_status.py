"""Repro for F90.4 — Multi-log SamplesGrid 'Status' column shows the LOG's status, not the sample's.

Produces TWO .eval files in logs/90-cross/ so the multi-log Samples grid is populated.

Run:
    ./findings/repros/run.sh findings/repros/tasks/90-cross/F90.4_multilog_grid_log_status.py 90-cross
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
    finding_id="F90.4",
    title="Multi-log Samples grid: per-row Status is the parent LOG's status, not the sample's",
    where_to_look=(
        "From the **log-directory listing** (the `90-cross` folder view), "
        "click the **Samples** view-mode button at the **top right** (next to "
        "`Tasks` / `Folders`) to open the multi-log Samples grid. Find the "
        "row with Sample ID = **`F90.4-errored`** (Task = "
        "`F90.4_multilog_grid_log_status_A`) and look at its **Status** column."
    ),
    observed=(
        "The **Status** cell for `F90.4-errored` reads **`success`** (plain "
        "text) — because the column is filled from `logDetail.status` (the "
        "parent log completed successfully thanks to `fail_on_error=False`). "
        "The per-sample error *is* present, but only in the rightmost "
        "**Error** column (scroll right). Compare: click the "
        "`F90.4_multilog_grid_log_status_A` log in the directory listing → "
        "**Samples** tab, where the same sample correctly shows a red error "
        "icon and the RuntimeError text in its Status column."
    ),
    expected=(
        "Multi-log grid Status should be per-sample: `error` for "
        "`F90.4-errored`, `success` for `F90.4-ok`. The per-sample "
        "`error`/`completed` fields are already on the row object — they're "
        "just not used for this column."
    ),
    extra=(
        "Source: `apps/inspect/src/app/samples-panel/SamplesPanel.tsx:183` sets "
        "`status: logDetail.status` for every sample row. Compare to "
        "`apps/inspect/src/app/samples/list/columns.tsx:80-99` which derives "
        "per-sample status via `sampleStatus(completed, error)`.\n\n"
        "**This repro requires both `F90.4_..._A` and `F90.4_..._B` logs in "
        "the same directory** so the multi-log grid has rows to compare."
    ),
)


@solver
def maybe_raise() -> Solver:
    """Raise for the sample whose id ends with '-errored'; succeed otherwise."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        state = await generate(state)
        if str(state.sample_id).endswith("-errored"):
            raise RuntimeError(
                "F90.4: deliberate per-sample error. The parent log still has "
                "status=success because fail_on_error=False."
            )
        return state

    return solve


@scorer(metrics=[accuracy()])
def trivial_scorer() -> Scorer:
    async def score(_state: TaskState, _target: Target) -> Score:
        return Score(value=1.0)

    return score


@task
def f90_4_multilog_grid_log_status_A() -> Task:  # noqa: N802
    """Log A: 2 samples, one of which errors. Log status = success (fail_on_error=False)."""
    return Task(
        name="F90.4_multilog_grid_log_status_A",
        dataset=[
            Sample(
                id="F90.4-errored",
                input=DESC + "\n\n---\n\n**This sample (`F90.4-errored`) raises a "
                "RuntimeError in its solver.** In the multi-log Samples grid "
                "its Status column should say `error` — but it says `success`.",
                target="n/a",
                metadata={"finding_id": "F90.4"},
            ),
            Sample(
                id="F90.4-ok",
                input=DESC
                + "\n\n---\n\n**This sample (`F90.4-ok`) completes normally** "
                "and is the control row.",
                target="n/a",
                metadata={"finding_id": "F90.4"},
            ),
        ],
        solver=maybe_raise(),
        scorer=trivial_scorer(),
        fail_on_error=False,
    )


@task
def f90_4_multilog_grid_log_status_B() -> Task:  # noqa: N802
    """Log B: 1 normal sample — present so the multi-log grid aggregates >1 log."""
    return Task(
        name="F90.4_multilog_grid_log_status_B",
        dataset=[
            Sample(
                id="F90.4-companion",
                input=DESC
                + "\n\n---\n\n**(companion log)** This second log exists only "
                "so the multi-log Samples grid aggregates across >1 log. The "
                "bug is visible on log A's `F90.4-errored` row.",
                target="n/a",
                metadata={"finding_id": "F90.4"},
            )
        ],
        solver=maybe_raise(),
        scorer=trivial_scorer(),
    )
