"""Repro for F05.12 — BranchEventView discards `event.metadata`.

Run:
    ./findings/repros/run.sh findings/repros/tasks/01-events/F05.12_branch_event_omits_metadata.py 01-events
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.event import BranchEvent  # noqa: E402
from inspect_ai.log import transcript  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

DESC = bug_description(
    finding_id="F05.12",
    title="BranchEventView discards `event.metadata`",
    where_to_look=(
        "Transcript tab → set the **Events** filter (top-right) to "
        "**Debug** → look at the **Branch** panel (it is not collapsible — "
        "the two-row grid is its full content)."
    ),
    observed=(
        "Only `from_span` and `from_message` rows are shown. The "
        "`metadata` dict (`branch_reason`, `branch_index`, `MARKER`) "
        "is **not rendered anywhere** in the panel."
    ),
    expected=(
        "`event.metadata` entries merged into the data grid, as "
        "`CompactionEventView` does (`{ ...data, ...event.metadata }`)."
    ),
    extra=(
        "**Note:** impact is minor — BranchEventView follows the codebase "
        "norm: **no** event view renders `BaseEvent.metadata` except "
        "`CompactionEventView`. Branch events are also hidden by the "
        "default filter, and no public API currently sets metadata on a "
        "BranchEvent (this repro uses `transcript()._event()` directly).\n\n"
        "Verify the data exists: sample **JSON** tab → `branch` event → "
        "`metadata.MARKER` is present in the raw event."
    ),
)


@solver
def emit_branch_with_metadata() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        del generate
        transcript()._event(
            BranchEvent(
                from_span="origin-span-id-12345",
                from_message="origin-message-id-abcde",
                metadata={
                    "branch_reason": "best-of-n exploration",
                    "branch_index": 2,
                    "MARKER": (
                        "⚠️ IF THIS METADATA IS NOT VISIBLE IN THE BRANCH EVENT "
                        "PANEL, BUG F05.12 IS CONFIRMED ⚠️"
                    ),
                },
            )
        )
        return state

    return solve


@task
def f05_12_branch_event_omits_metadata() -> Task:
    return Task(
        name="F05.12_branch_event_omits_metadata",
        dataset=[Sample(id="F05.12", input=DESC, target="n/a")],
        solver=emit_branch_with_metadata(),
    )
