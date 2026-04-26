"""Repro for F11.7 — `ToolEvent.truncated` is never surfaced.

Run:
    ./findings/repros/run.sh findings/repros/tasks/11-tools/F11.7_toolevent_truncated_not_shown.py 11-tools
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import (  # noqa: E402
    bug_description,
    emit_bug_banner,
    mock_text,
    mock_tool_call,
)

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.model import GenerateConfig, get_model  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402
from inspect_ai.tool import Tool, tool  # noqa: E402

DESC = bug_description(
    finding_id="F11.7",
    title="ToolEvent.truncated byte counts are never surfaced in viewer chrome",
    where_to_look=(
        "**Transcript tab** → the **Tool: big_output** event panel "
        "(expanded by default below this banner)."
    ),
    observed=(
        "The output box leads with Inspect's Python preamble — *\"The "
        "output of your call to big_output was too long to be "
        "displayed. Here is a truncated version:\"* — so the user IS "
        "told it was truncated. Head+tail truncation means both "
        "`F11.7_FULL_OUTPUT_START` and `F11.7_FULL_OUTPUT_END` "
        "survive. But there is no viewer-chrome footer/badge showing "
        "the byte counts: `ToolEvent.truncated == (2054, 200)` is in "
        "the raw event yet never read by `ToolEventView.tsx`."
    ),
    expected=(
        "A muted footer/badge below the output, e.g. `Output "
        "truncated (showing 200 of 2,054 bytes)`, sourced from "
        "`event.truncated`."
    ),
    extra=(
        "**Note:** impact is minor — the Python preamble already "
        "tells the user the output was truncated; only the precise "
        "`(raw_bytes, kept_bytes)` figures are lost. This is a UX "
        "nicety, not a confusion bug.\n\n"
        "`max_tool_output=200` is set on this Task so Inspect clips "
        "the ~2 KB result and records "
        "`ToolEvent.truncated=(raw_bytes, kept_bytes)`. Verify the "
        "raw field in **JSON tab** → `events` → the tool event → "
        "`truncated`."
    ),
)


@tool
def big_output() -> Tool:
    async def execute() -> str:
        """Produce ~2 KB of output so it exceeds max_tool_output=200."""
        body = "0123456789" * 200  # 2000 bytes
        return (
            "F11.7_FULL_OUTPUT_START >>> " + body + " <<< F11.7_FULL_OUTPUT_END"
        )

    return execute


@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        state.tools = [big_output()]
        return await generate(state)

    return solve


@task
def f11_7_toolevent_truncated_not_shown() -> Task:
    outputs = [
        mock_tool_call("big_output", {}, content="Generating 2 KB…"),
        mock_text("Done."),
    ]
    return Task(
        name="F11.7_toolevent_truncated_not_shown",
        dataset=[Sample(id="F11.7", input=DESC, target="n/a")],
        solver=repro_solver(),
        model=get_model("mockllm/model", custom_outputs=outputs),
        config=GenerateConfig(max_tool_output=200),
    )
