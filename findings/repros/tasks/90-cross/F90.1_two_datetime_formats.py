"""Repro for F90.1 — Same screen, two timestamp formats.

Run:
    ./findings/repros/run.sh findings/repros/tasks/90-cross/F90.1_two_datetime_formats.py 90-cross
"""

from __future__ import annotations

import sys
from pathlib import Path

# make findings/repros/_common.py importable
sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.log import transcript  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

DESC = bug_description(
    finding_id="F90.1",
    title="Two datetime formats: transcript event panels vs log-list grid",
    where_to_look=(
        "**(A)** In this **Transcript** tab, hover any event-panel "
        "title — the tooltip reads e.g. `04/24/26, 8:47:45 PM`. Or "
        "click the **Model Call** panel's **ALL** subtab → scroll to "
        "**CLOCK TIME** → START/END show the same 12-hour format. "
        "**(B)** Click the back arrow to the **log list** and read "
        "this task's **Completed** column — it reads e.g. "
        "`2026-04-24 20:47:46` for the same instant."
    ),
    observed=(
        "Log-list **Completed** column uses `YYYY-MM-DD HH:mm:ss` "
        "(hardcoded sv-SE, 24-hour, 4-digit year). Transcript "
        "event-panel timestamps use `MM/DD/YY, h:mm:ss AM/PM` (Intl "
        "default locale, 12-hour, 2-digit year). Same instant, two "
        "formats, one click apart."
    ),
    expected=(
        "One datetime format everywhere. The sv-SE format should be "
        "adopted by `@tsmono/util` formatDateTime so transcript event "
        "panels match the log-list Completed column."
    ),
    extra=(
        "Root cause: `apps/inspect/src/utils/format.ts:formatDateTime` "
        "(sv-SE) shadows `packages/util/src/format.ts:formatDateTime` "
        "(Intl default locale, `hour12: true`, `year: '2-digit'`). The "
        "log-list grid (`hooks.tsx:265`) imports the app-local copy; "
        "every transcript `*EventView` / `EventTimingPanel` imports "
        "the util copy. **Note:** the original finding cited the "
        "sample-detail header / Metadata→Time card as an sv-SE "
        "surface — that is wrong; those render *durations* "
        "(`formatTime`), not datetimes."
    ),
)


@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        # Generate once → ModelEvent in transcript carries a timestamp rendered
        # via @tsmono/util formatDateTime (12-hour locale).
        state = await generate(state)
        # Add an InfoEvent so there is a second event-panel header timestamp
        # (hover tooltip) to compare against the log-list Completed column.
        transcript().info(
            "Hover this panel's title — the tooltip timestamp uses the "
            "@tsmono/util formatter (`MM/DD/YY, h:mm:ss AM/PM`). Compare it "
            "to the **log-list Completed column** (back arrow → log list), "
            "which uses the app-local sv-SE formatter "
            "(`YYYY-MM-DD HH:mm:ss`) for the same instant.",
            source="F90.1",
        )
        return state

    return solve


@task
def f90_1_two_datetime_formats() -> Task:
    return Task(
        name="F90.1_two_datetime_formats",
        dataset=[Sample(id="F90.1", input=DESC, target="n/a")],
        solver=repro_solver(),
    )
