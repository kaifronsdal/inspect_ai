"""Repro for F31.1 — EvalConfig is built but never rendered in the Task tab.

Sets several distinctive ``EvalConfig`` fields (epochs=7, message_limit=42,
fail_on_error=0.5) so it is obvious they are missing from the Task tab.

Run:
    ./findings/repros/run.sh findings/repros/tasks/30-loglist/F31.1_eval_config_not_rendered.py 30-loglist
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
    finding_id="F31.1",
    title="EvalConfig is computed but never rendered in the Task tab",
    where_to_look=(
        "Close this sample → click the log-level **Task** tab (top row: "
        "Samples / Task / Models / Info / JSON). The only card rendered is "
        "**Task Info** (Task ID, Run ID, Git Revision, Inspect, Start, End, "
        "Duration)."
    ),
    observed=(
        "None of `epochs=7`, `message_limit=42`, `token_limit=999999`, "
        "`fail_on_error=0.5` appear anywhere in the Task tab — only the "
        "**Task Info** card is shown. `TaskTab.tsx` copies every key of "
        "`evalSpec.config` into a local `config` record and then never "
        "references it."
    ),
    expected=(
        "A **Config** card listing the `EvalConfig` fields. Open the "
        "log-level **JSON** tab and search for `\"epochs\": 7` to confirm "
        "the data is present in the log."
    ),
    extra=(
        "The header bar above the tabs shows only DATASET / SCORER / DURATION "
        "for this log — no Config column (its source is `plan.config` + "
        "`task_args`, both empty here, *not* `EvalConfig`). The only hint of "
        "`epochs=7` is the implicit `1 x 7 samples` dataset multiplier.\n\n"
        "**Note:** impact is minor — data is still reachable via the JSON "
        "tab; recommend MEDIUM severity (was HIGH)."
    ),
)


@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        return await generate(state)

    return solve


@task
def f31_1_eval_config_not_rendered() -> Task:
    return Task(
        name="F31.1_eval_config_not_rendered",
        dataset=[Sample(id="F31.1", input=DESC, target="n/a")],
        solver=repro_solver(),
        scorer=match(),
        epochs=7,
        message_limit=42,
        token_limit=999999,
        fail_on_error=0.5,
    )
