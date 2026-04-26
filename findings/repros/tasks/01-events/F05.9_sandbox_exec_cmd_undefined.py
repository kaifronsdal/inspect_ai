"""Repro for F05.9 — SandboxEventView ExecView `=== null` guard misses `undefined`.

Run:
    ./findings/repros/run.sh findings/repros/tasks/01-events/F05.9_sandbox_exec_cmd_undefined.py 01-events
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.event import SandboxEvent  # noqa: E402
from inspect_ai.log import transcript  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

DESC = bug_description(
    finding_id="F05.9",
    title="SandboxEventView ExecView guards `cmd === null` but `.eval` omits null → `undefined`",
    where_to_look=(
        "Transcript tab → **switch the filter to Debug** (top-right "
        "`Events: Default` button → `Debug`; sandbox events are hidden "
        "under Default) → look at the **Sandbox: exec** panel (already "
        "open, no expand needed)"
    ),
    observed=(
        "A **Command** heading is rendered with nothing beneath it (two "
        "empty `<pre>` elements in the DOM), followed by the **Result** "
        "section. The `if (event.cmd === null) return undefined` guard "
        "did NOT fire because `cmd` is `undefined`, not `null`."
    ),
    expected=(
        "Either the whole ExecView should be suppressed (as the guard "
        "intends), or the Command section should be hidden — not a "
        "dangling heading over empty `<pre>`s."
    ),
    extra=(
        "**Note:** impact is minor — this state is **synthetic-only**. "
        "The sole production emitter of `SandboxEvent(action=\"exec\")` "
        "(`util/_sandbox/events.py`) always sets `cmd` to a joined string, "
        "so real sandbox calls never reach `cmd=undefined`. The guard is "
        "still dead code (`exclude_none=True` means JS can never see "
        "`null` here) and should be `if (!event.cmd)` to match the "
        "sibling `ReadFileView`/`WriteFileView` checks."
    ),
)


@solver
def emit_sandbox_exec_no_cmd() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        del generate
        # cmd left at default (None). The .eval recorder serialises with
        # exclude_none=True, so the `cmd` key is OMITTED from the JSON →
        # JS receives `event.cmd === undefined`, not `=== null`.
        transcript()._event(
            SandboxEvent(
                action="exec",
                # cmd=None  ← omitted
                output="(stdout from a sandbox exec whose `cmd` field was omitted)",
                result=1,
            )
        )
        return state

    return solve


@task
def f05_9_sandbox_exec_cmd_undefined() -> Task:
    return Task(
        name="F05.9_sandbox_exec_cmd_undefined",
        dataset=[Sample(id="F05.9", input=DESC, target="n/a")],
        solver=emit_sandbox_exec_no_cmd(),
    )
