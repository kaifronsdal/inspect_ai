"""Repro for F90.5 — Sample 'Error' tab omits error.message; log-level Error tab shows it.

Run:
    ./findings/repros/run.sh findings/repros/tasks/90-cross/F90.5_sample_error_tab_drops_message.py 90-cross
"""

from __future__ import annotations

import sys
from pathlib import Path

# make findings/repros/_common.py importable
sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

DISTINCTIVE = (
    "F90.5_ERROR_MESSAGE_SHOULD_BE_VISIBLE — this is `error.message`. "
    "It carries context (request_id=abc123, retries=5) that is NOT in the "
    "traceback frames. The sample-level Error tab should display this string."
)

DESC = bug_description(
    finding_id="F90.5",
    title="Sample-level Error tab renders only traceback_ansi; no dedicated error.message panel",
    where_to_look=(
        "Open this sample → click the **Error** tab. The card is "
        "titled **SAMPLE ERROR** and its body contains exactly one "
        "element: the ANSI traceback box."
    ),
    observed=(
        "The sentinel `F90.5_ERROR_MESSAGE_SHOULD_BE_VISIBLE` **is** "
        "visible — but only as the final `RuntimeError: …` line "
        "*inside* the ANSI traceback. There is **no** separate "
        "`error.message` panel above the traceback and **no** header "
        "icon. The card body renders `sample.error.traceback_ansi` "
        "and nothing else; `sample.error.message` is never read."
    ),
    expected=(
        "Sample Error tab should mirror the log-level "
        "`TaskErrorPanel`: header icon + `error.message` rendered in "
        "its own `ExpandablePanel` above the ANSI traceback. (No "
        "log-level Error tab exists in *this* log to compare against "
        "— the task succeeds because `fail_on_error=False`; the "
        "comparison is in source.)"
    ),
    extra=(
        "Source: `apps/inspect/src/app/samples/SampleDisplay.tsx:607-623` "
        "(traceback only) vs `apps/inspect/src/app/log-view/error/"
        "TaskErrorPanel.tsx:29-44` (icon + message + traceback). Both "
        "consume the same `EvalError` shape.\n\n"
        "**Note:** impact is minor — for ordinary Python exceptions "
        "the message text still reaches the screen via the "
        "traceback's last line, so this is a UI-consistency gap "
        "rather than data loss in the common case."
    ),
)


@solver
def raise_with_message() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        state = await generate(state)
        raise RuntimeError(DISTINCTIVE)

    return solve


@task
def f90_5_sample_error_tab_drops_message() -> Task:
    return Task(
        name="F90.5_sample_error_tab_drops_message",
        dataset=[Sample(id="F90.5", input=DESC, target="n/a")],
        solver=raise_with_message(),
        fail_on_error=False,
    )
