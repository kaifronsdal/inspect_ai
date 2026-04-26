"""Repro for F01.2 — ToolChoiceView renders literal `` `$name()` `` instead of `name()`.

Run:
    ./findings/repros/run.sh findings/repros/tasks/01-events/F01.2_tool_choice_literal_dollar.py 01-events
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.event import ModelEvent  # noqa: E402
from inspect_ai.log import transcript  # noqa: E402
from inspect_ai.model import (  # noqa: E402
    ChatMessageUser,
    GenerateConfig,
    ModelOutput,
)
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402
from inspect_ai.tool import ToolFunction, ToolInfo, ToolParams  # noqa: E402

MOCK = "mockllm/model"

DESC = bug_description(
    finding_id="F01.2",
    title="ToolChoiceView renders literal `` `$name()` `` instead of `name()`",
    where_to_look=(
        "Transcript tab → in the **Model Call: mockllm/model** event, "
        "click the **Tools** sub-tab → look at the **Tool Choice** row at the bottom"
    ),
    observed=(
        "Tool Choice shows the literal text `` `$my_forced_tool()` `` "
        "(backtick, dollar sign, name, parens, backtick)."
    ),
    expected="Tool Choice should show `my_forced_tool()` with no stray `` ` `` or `$`.",
    extra=(
        "Root cause: ``<code>`${toolChoice.name}()`</code>`` — JSX text is "
        "not a template literal; the backticks and `$` are rendered "
        "verbatim.\n\n"
        "Note: two tools are defined here so the Tools tab actually appears "
        "(it is gated on `tools.length > 1` — see F04.2)."
    ),
)


@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        del generate
        # generate(tool_choice=ToolFunction(...)) makes inspect filter
        # event.tools down to the single forced tool, so F04.2's `> 1` guard
        # would hide the Tools tab. Construct the ModelEvent directly with
        # two ToolInfo entries so the Tools tab is reachable.
        transcript()._event(
            ModelEvent(
                model=MOCK,
                input=[ChatMessageUser(content="(synthetic model call for F01.2)")],
                tools=[
                    ToolInfo(
                        name="my_forced_tool",
                        description="The tool the model is forced to call.",
                        parameters=ToolParams(),
                    ),
                    ToolInfo(
                        name="other_tool",
                        description="Second tool so tools.length > 1 (see F04.2).",
                        parameters=ToolParams(),
                    ),
                ],
                tool_choice=ToolFunction(name="my_forced_tool"),
                config=GenerateConfig(),
                output=ModelOutput.from_content(MOCK, "(output)"),
            )
        )
        return state

    return solve


@task
def f01_2_tool_choice_literal_dollar() -> Task:
    return Task(
        name="F01.2_tool_choice_literal_dollar",
        dataset=[
            Sample(
                id="F01.2",
                input=DESC,
                target="n/a",
                metadata={"finding_id": "F01.2", "bug_title": DESC.splitlines()[2]},
            )
        ],
        solver=repro_solver(),
    )
