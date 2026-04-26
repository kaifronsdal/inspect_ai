"""Repro for F02.1 — groupSandboxEvents is a no-op in span-based logs.

Run:
    ./findings/repros/run.sh findings/repros/tasks/02-transform/F02.1_sandbox_grouping_noop.py 02-transform
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
    finding_id="F02.1",
    title="groupSandboxEvents is a no-op in span-based logs — sandbox events render individually",
    where_to_look=(
        "Transcript tab → **switch the Events filter to Debug first** "
        "(funnel button top-right: `Events: Default` → `Debug`) — sandbox "
        "events are hidden under the Default filter. Scroll past the model "
        "call and you will see three separate `SANDBOX: EXEC` / "
        "`SANDBOX: EXEC` / `SANDBOX: READ_FILE` panels."
    ),
    observed=(
        "Three individual `SANDBOX:` panels render as flat top-level "
        "siblings. No collapsible **Sandbox Events** group wrapper appears."
    ),
    expected=(
        "A single collapsible **Sandbox Events** group node containing "
        "all three events (the `kSandboxSignalName` synthetic span)."
    ),
    extra=(
        "`groupSandboxEvents` (fixups.ts) wraps consecutive sandbox events "
        "in a synthetic span with `parent_id: null`, but leaves each "
        "sandbox event's original `span_id` intact. `treeifyWithSpans` "
        "then parents the events back under their *real* span, leaving "
        "the wrapper empty — which `filterEmpty` strips. Net effect: the "
        "whole grouping mechanism is dead for any modern (span-based) log.\n\n"
        "Also demonstrates **F02.9**: if the wrapper *did* appear, its "
        "begin-timestamp would equal the *last* event's timestamp, not "
        "the first."
    ),
)


@solver
def emit_sandbox_events() -> Solver:
    """Emit three consecutive SandboxEvents inside the solver span.

    No real sandbox is started — events are pushed directly onto the
    transcript so the viewer's `groupSandboxEvents` fixup is exercised.
    Each event inherits the solver span's `span_id` (non-null), which is
    exactly the condition that breaks the synthetic-wrapper grouping.
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        state = await generate(state)
        # Three back-to-back sandbox events. The fixup should wrap these in a
        # single collapsible "Sandbox Events" group, but the wrapper's
        # parent_id/span_id wiring is wrong so they render individually.
        transcript()._event(
            SandboxEvent(
                action="exec",
                cmd="ls /SHOULD_BE_GROUPED_WITH_NEXT_TWO",
                result=0,
                output="file1\nfile2",
            )
        )
        transcript()._event(
            SandboxEvent(
                action="exec",
                cmd="echo I_SHOULD_BE_IN_THE_SAME_SANDBOX_GROUP",
                result=0,
                output="I_SHOULD_BE_IN_THE_SAME_SANDBOX_GROUP",
            )
        )
        transcript()._event(
            SandboxEvent(
                action="read_file",
                file="/tmp/ALSO_SHOULD_BE_GROUPED.txt",
                output="contents that should appear inside the group",
            )
        )
        return state

    return solve


@task
def f02_1_sandbox_grouping_noop() -> Task:
    return Task(
        name="F02.1_sandbox_grouping_noop",
        dataset=[Sample(id="F02.1", input=DESC, target="n/a")],
        solver=emit_sandbox_events(),
    )
