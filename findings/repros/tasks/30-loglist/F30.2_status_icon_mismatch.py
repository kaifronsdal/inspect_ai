"""Repro for F30.2 — Status icons differ between log-list grid and log-detail header.

Produces a log with ``status="error"`` (solver raises). Compare the icon shown
in the log-list Status column against the icon shown in the title bar after
opening the log.

Run:
    ./findings/repros/run.sh findings/repros/tasks/30-loglist/F30.2_status_icon_mismatch.py 30-loglist

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
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

DESC = bug_description(
    finding_id="F30.2",
    title="Status icons differ between log-list grid and detail header",
    where_to_look=(
        "(1) Log list → **Status** column for this row. "
        "(2) Then click the row → look at the status icon in the **title bar** "
        "(top right, next to the 'Task Failed' label)."
    ),
    observed=(
        "List shows a **filled red circle with a white '!'** "
        "(`bi-exclamation-circle-fill`) for `error`; detail header shows an "
        "**outlined circle with an X** (`bi-x-circle`) for the same `error` "
        "status. `bi-x-circle` is what the *list* uses for `cancelled` — so "
        "the same glyph means two different things one click apart."
    ),
    expected=(
        "Same icon in both places. The list's mapping "
        "(`ApplicationIcons.error` / `ApplicationIcons.cancelled`) is the "
        "correct one; `StatusPanel.tsx` should match it."
    ),
    extra=(
        "Cancelled status (`bi-x-circle` in list vs `bi-info-square` in "
        "header) is the more egregious case but a `cancelled` log cannot "
        "be cleanly produced via a scripted mockllm run. The `error` case "
        "shown here is sufficient to demonstrate the divergence."
    ),
)


@solver
def raise_for_error_status() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        # generate once so the bug-description message is in the transcript
        state = await generate(state)
        raise RuntimeError(
            "F30.2 — DELIBERATE ERROR to produce a log with status='error'. "
            "Compare the status icon for this row in the log LIST against the "
            "icon in this log's TITLE BAR after opening it."
        )

    return solve


@task
def f30_2_status_icon_mismatch() -> Task:
    return Task(
        name="F30.2_status_icon_mismatch_ERROR",
        dataset=[Sample(id="F30.2", input=DESC, target="n/a")],
        solver=raise_for_error_status(),
        # default fail_on_error=None → eval halts with status="error"
    )
