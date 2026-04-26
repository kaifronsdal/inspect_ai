"""Repro for F04.2 — Tools tab hidden when exactly one tool is defined.

Run:
    ./findings/repros/run.sh findings/repros/tasks/01-events/F04.2_tools_tab_hidden_single_tool.py 01-events
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402
from inspect_ai.tool import Tool, tool  # noqa: E402

DESC = bug_description(
    finding_id="F04.2",
    title="TOOLS sub-tab hidden when exactly one tool is defined (`> 1` instead of `> 0`)",
    where_to_look=(
        "Transcript tab → **MODEL CALL: MOCKLLM/MODEL** panel → "
        "look at the pill nav in the panel header (top-right)"
    ),
    observed=(
        "Only **SUMMARY** / **ALL** / **API** pills are present. "
        "**No TOOLS pill** — even though `event.tools` contains exactly "
        "one tool (`the_only_tool`). The tool definition and `tool_choice` "
        "are visible only in the raw API tab JSON."
    ),
    expected=(
        "A **TOOLS** pill listing `the_only_tool` and its `tool_choice`. "
        "Single-tool agents (`bash`-only, `submit`-only) are very common."
    ),
    extra=(
        "Root cause: `ModelEventView.tsx:198` — "
        "`{event.tools.length > 1 && <div data-name=\"Tools\">...}` "
        "— off-by-one; should be `> 0`.\n\n"
        "Contrast: open `F01.2-tool-choice-literal-dollar` in this same "
        "log dir — it has TWO tools and its MODEL CALL panel DOES show the "
        "TOOLS pill.\n\n"
        "**Note:** severity downgraded HIGH → MEDIUM — the tool definition "
        "is still recoverable from the API tab's raw request JSON; impact "
        "is informational. Duplicate of F01.4."
    ),
)


@tool
def the_only_tool() -> Tool:
    async def execute(query: str) -> str:
        """The single tool available to this model call.

        Args:
            query: a query string
        """
        return f"result for {query}"

    return execute


@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        state.tools = [the_only_tool()]
        state.tool_choice = "auto"
        return await generate(state)

    return solve


@task
def f04_2_tools_tab_hidden_single_tool() -> Task:
    return Task(
        name="F04.2_tools_tab_hidden_single_tool",
        dataset=[Sample(id="F04.2", input=DESC, target="n/a")],
        solver=repro_solver(),
    )
