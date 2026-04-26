"""Repro for F04.8 — ModelUsagePanel renders zero-valued token counts as blank.

Run:
    ./findings/repros/run.sh findings/repros/tasks/01-events/F04.8_usage_zero_renders_blank.py 01-events
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.model import ModelOutput, ModelUsage, get_model  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

MOCK = "mockllm/model"

DESC = bug_description(
    finding_id="F04.8",
    title="ModelUsagePanel renders `0` token counts as blank cells",
    where_to_look=(
        "Transcript tab → expand **Model Call: mockllm/model** → click the "
        "**All** sub-tab → look at the **Usage** section. Also visible at the "
        "log level: **Models** tab → **Model Usage** card at the bottom."
    ),
    observed=(
        "The **input** row shows its label but the value cell is **blank** "
        "(while **cache_read**=`100`, **Output**=`50`, **Total**=`150` render "
        "fine). The **cache_write** and **Reasoning** rows are omitted "
        "entirely — separate truthy guards drop the whole row when the value "
        "is `0`."
    ),
    expected=(
        "The **input** row should display **`0`**, not an empty cell. A blank "
        "cell reads as 'not reported'; `0` is meaningful data (e.g. a "
        "fully-cached input)."
    ),
    extra=(
        "Root cause: `{row.value ? formatNumber(row.value) : \"\"}` — "
        "truthy check. Fix: `row.value != null ? … : \"\"`."
    ),
)


@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        return await generate(state)

    return solve


@task
def f04_8_usage_zero_renders_blank() -> Task:
    out = ModelOutput.from_content(
        model=MOCK,
        content=(
            "This output reports `input_tokens=0` (e.g. fully-cached request). "
            "The Usage panel should show **0**, not a blank cell."
        ),
    )
    out.usage = ModelUsage(
        input_tokens=0,  # ← the bug: 0 is falsy → renders as ""
        output_tokens=50,
        total_tokens=150,
        input_tokens_cache_read=100,
        input_tokens_cache_write=0,  # ← also 0 (row omitted entirely)
        reasoning_tokens=0,  # ← also 0 (row omitted entirely)
    )

    return Task(
        name="F04.8_usage_zero_renders_blank",
        dataset=[Sample(id="F04.8", input=DESC, target="n/a")],
        solver=repro_solver(),
        model=get_model(MOCK, custom_outputs=[out]),
    )
