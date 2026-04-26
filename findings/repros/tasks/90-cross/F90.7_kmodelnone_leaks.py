"""Repro for F90.7 — kModelNone ("none/none") suppressed in title bar but leaks elsewhere.

Run:
    ./findings/repros/run.sh findings/repros/tasks/90-cross/F90.7_kmodelnone_leaks.py 90-cross

The task-level ``model="none"`` overrides the CLI ``--model mockllm/model``, so
the log's ``eval.model`` field is the sentinel ``"none/none"``. The solver never
calls ``generate()`` (NoModel raises if it does), so this still satisfies the
mockllm-only constraint — no real provider is contacted.
"""

from __future__ import annotations

import sys
from pathlib import Path

# make findings/repros/_common.py importable
sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.model import get_model  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

DESC = bug_description(
    finding_id="F90.7",
    title='kModelNone ("none/none") is hidden in the title bar but rendered verbatim elsewhere',
    where_to_look=(
        "This eval's top-level model is the sentinel `none/none` "
        "(real work goes through `model_roles`). Compare: "
        "**(1)** the **title bar** at the top of this log — the "
        "sentinel is suppressed and the subtitle shows the role "
        "`WORKER:mockllm/model` instead (correct: it guards "
        "`!== kModelNone`). **(2)** the **log-list** grid (click "
        "`90-cross` in the breadcrumb) → **Model** column for this "
        "row — shows literal `none/none`. **(3)** from the log-list, "
        "click the **Samples** toggle (top-right) → **Model** column "
        "— `none/none`. **(4)** this log's **Models** tab → the "
        "**EVAL** card → `MODEL: none/none`."
    ),
    observed=(
        "Title bar treats `none/none` as a sentinel and suppresses it "
        "(showing the `WORKER` role instead). The log-list Model "
        "column, the log-list Samples-view Model column, and the "
        "Models-tab **EVAL** card all leak the raw string `none/none`."
    ),
    expected=(
        "All four surfaces should suppress / replace the sentinel "
        "(e.g. show `—` or the first model_role instead)."
    ),
    extra=(
        "Source: `PrimaryBar.tsx:74` guards `evalSpec.model !== "
        "kModelNone`; `log-list/grid/columns/hooks.tsx:160`, "
        "`samples-panel/SamplesPanel.tsx:182`, and "
        "`plan/ModelCard.tsx:24,57` do not.\n\n"
        "A mockllm role (`worker`) is attached so the Models tab has "
        "a real **WORKER** card alongside the leaking **EVAL** card."
    ),
)


@solver
def no_generate() -> Solver:
    """Do not call generate() — model is `none/none` which would raise."""

    async def solve(state: TaskState, _generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        state.output.completion = "(no model was called — eval uses model_roles only)"
        return state

    return solve


@task
def f90_7_kmodelnone_leaks() -> Task:
    return Task(
        name="F90.7_kmodelnone_leaks",
        dataset=[Sample(id="F90.7", input=DESC, target="n/a")],
        solver=no_generate(),
        model="none",
        model_roles={"worker": get_model("mockllm/model")},
    )
