"""Repro for F11.1 — tool errors render identically to successful output.

Run:
    ./findings/repros/run.sh findings/repros/tasks/11-tools/F11.1_tool_error_styled_as_success.py 11-tools
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
from inspect_ai.tool import Tool, ToolError, tool  # noqa: E402

DESC = bug_description(
    finding_id="F11.1",
    title="Tool errors render identically to successful tool output",
    where_to_look=(
        "**Transcript tab** → compare the two `Tool:` panels below "
        "(`Tool: good_tool` vs `Tool: bad_tool` — both already expanded). "
        "Also **Messages tab** → rows 2 and 3 (assistant turns calling "
        "`good_tool` / `bad_tool`)."
    ),
    observed=(
        "The `Tool: bad_tool` panel renders its ❌ error in a plain grey "
        "`<pre>` block with **identical** CSS classes, icon, and header "
        "colour to the ✅ success output in `Tool: good_tool`. No error "
        "icon, red border, or `Error:` label is added by the viewer."
    ),
    expected=(
        "The error result has distinct styling — e.g. red "
        "left-border + `Error (unknown):` prefix — like "
        "`ServerToolCall.tsx` already does for server tools."
    ),
    extra=(
        "Both render paths (`ToolEventView.tsx:110`, "
        "`ChatMessageRow.tsx:228-231`) flatten "
        "`ToolCallError` to `.message` and pipe it through the "
        "same `output` prop as success. The ❌/✅ emoji visible "
        "here are part of the *repro's* message text — the viewer "
        "adds nothing to distinguish them."
    ),
)


@tool
def good_tool() -> Tool:
    async def execute(q: str) -> str:
        """A tool that succeeds.

        Args:
            q: query
        """
        return "✅ SUCCESS RESULT — this is normal tool output."

    return execute


@tool
def bad_tool() -> Tool:
    async def execute(q: str) -> str:
        """A tool that always fails.

        Args:
            q: query
        """
        raise ToolError(
            "❌ THIS IS AN ERROR — should look visually DIFFERENT from the "
            "✅ SUCCESS row above (red border / error icon / 'Error:' label). "
            "If this grey <pre> block looks identical to the success block, "
            "F11.1 is confirmed."
        )

    return execute


@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        state.tools = [good_tool(), bad_tool()]
        return await generate(state)

    return solve


@task
def f11_1_tool_error_styled_as_success() -> Task:
    outputs = [
        mock_tool_call("good_tool", {"q": "x"}, content="Calling good_tool…"),
        mock_tool_call("bad_tool", {"q": "x"}, content="Calling bad_tool…"),
        mock_text("Done."),
    ]
    return Task(
        name="F11.1_tool_error_styled_as_success",
        dataset=[Sample(id="F11.1", input=DESC, target="n/a")],
        solver=repro_solver(),
        model=get_model("mockllm/model", custom_outputs=outputs),
        config=GenerateConfig(max_tool_output=4096),
    )
