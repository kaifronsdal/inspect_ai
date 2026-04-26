"""Repro for F30.4 — SecondaryBar hidden entirely unless status == "success".

Produces a log with ``status="error"``. The header's secondary bar (Dataset,
Scorer, Config, Duration) returns ``null`` for any non-success status even
though all the underlying data is present.

Run:
    ./findings/repros/run.sh findings/repros/tasks/30-loglist/F30.4_secondary_bar_hidden.py 30-loglist

NOTE: ``inspect eval`` exits non-zero for an errored task — that is expected.
The .eval file is still written.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.scorer import match  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

DESC = bug_description(
    finding_id="F30.4",
    title="SecondaryBar (Dataset / Scorer / Duration row) hidden for non-success logs",
    where_to_look=(
        "Look at the **header** directly below the task title / model name. "
        "Compare against any *successful* log in this directory (e.g. F30.1), "
        "whose header has a second row reading `DATASET … SCORERS … DURATION …`."
    ),
    observed=(
        "No second header row at all — `DATASET`, `SCORER` and `DURATION` are "
        "absent; the header stops after the `TASK FAILED` badge. The data is "
        "in the log (open the log-level **JSON** tab: `task_args.distinctive_arg`, "
        "`stats.started_at`/`completed_at` are populated)."
    ),
    expected=(
        "The secondary bar should render for errored/cancelled/started logs "
        "too. Only the score summary is genuinely success-gated; sample "
        "count, task args and elapsed time are exactly what you want when "
        "triaging a failure."
    ),
    extra=(
        "This log also has a task arg (`distinctive_arg='F30.4_TASK_ARG'`), so "
        "a fourth `CONFIG` cell would render here as well — the comparison "
        "logs (F30.1 etc.) have no task args, so they show only "
        "Dataset/Scorer/Duration. Source: `SecondaryBar.tsx:45` "
        "`if (!evalSpec || status !== \"success\") return null;`."
    ),
)


@solver
def raise_after_generate() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        state = await generate(state)
        raise RuntimeError(
            "F30.4 — DELIBERATE ERROR to produce status='error'. The dataset, "
            "task_args, scorer, and elapsed-duration data are all present on "
            "this log but SecondaryBar.tsx hides the whole bar."
        )

    return solve


@task
def f30_4_secondary_bar_hidden(distinctive_arg: str = "F30.4_TASK_ARG") -> Task:
    """The ``distinctive_arg`` task arg should appear in the Config cell of the
    secondary bar — proving the data exists even though the bar is hidden."""
    del distinctive_arg  # captured into eval.task_args by inspect; value unused here
    return Task(
        name="F30.4_secondary_bar_hidden_ERROR",
        dataset=[Sample(id="F30.4", input=DESC, target="n/a")],
        solver=raise_after_generate(),
        scorer=match(),
    )
