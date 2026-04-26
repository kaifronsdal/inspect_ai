"""Repro for F90.2 — Sub-minute durations rendered with three different precisions.

Run:
    ./findings/repros/run.sh findings/repros/tasks/90-cross/F90.2_three_duration_formats.py 90-cross
"""

from __future__ import annotations

import sys
from pathlib import Path

# make findings/repros/_common.py importable
sys.path.insert(0, str(Path(__file__).parents[2]))
import anyio  # noqa: E402
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402
from inspect_ai.util import span  # noqa: E402

DESC = bug_description(
    finding_id="F90.2",
    title="Two sub-minute duration precision styles in one sample view",
    where_to_look=(
        "Compare two places. **(A)** **Metadata** tab → **TIME** card "
        "→ `Working:` / `Total:` show e.g. `2.8 sec` — app-local "
        "`formatTime`, 1 decimal. **(B)** **Transcript** tab → second "
        "`MODEL CALL: MOCKLLM/MODEL` panel → click the **ALL** subtab "
        "→ **WORKING TIME** row → `START` / `END` show e.g. `3 sec` — "
        "`@tsmono/util formatTime`, rounded integer (the panel title "
        "also shows `(… 0 SEC)`)."
    ),
    observed=(
        "Two precision styles for sub-minute durations within one "
        "sample: `N.N sec` (1 decimal) on the Metadata tab vs `N sec` "
        "(rounded int) on the Transcript tab. These format *different* "
        "underlying fields (`sample.working_time` vs "
        "`model_event.working_start`), so no single value is rendered "
        "two ways — the inconsistency is the *style*, not the data."
    ),
    expected=(
        "One shared sub-minute `formatTime` so the Metadata TIME card "
        "and the Transcript event timing panel use the same precision."
    ),
    extra=(
        "**Note:** impact is minor — cosmetic precision mismatch only; "
        "each log field passes through exactly one formatter, so no "
        "value is shown inconsistently with itself. A third compact "
        "form (`formatDurationShort` → `3s`, "
        "`packages/util/src/format.ts:173`) exists in source but is "
        "only used by timeline/agent cards, which this sample does not "
        "trigger, so it is not visible here. Source: "
        "`apps/inspect/src/utils/format.ts:6` (1-decimal) vs "
        "`packages/util/src/format.ts:33` (rounded int)."
    ),
)


@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        # Sleep ~2.5 s of working time before the second model call so:
        #  - sample.working_time ≈ 2.8 s → Metadata TIME card → "2.8 sec"
        #    (app-local formatTime, 1 decimal)
        #  - second model event's working_start ≈ 2.8 s → Transcript ALL
        #    subtab WORKING TIME → "3 sec" (@tsmono/util formatTime, int)
        async with span("slow-phase", type="custom"):
            state = await generate(state)
            await anyio.sleep(2.5)
            state = await generate(state)
        return state

    return solve


@task
def f90_2_three_duration_formats() -> Task:
    return Task(
        name="F90.2_three_duration_formats",
        dataset=[Sample(id="F90.2", input=DESC, target="n/a")],
        solver=repro_solver(),
    )
