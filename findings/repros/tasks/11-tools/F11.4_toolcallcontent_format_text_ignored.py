"""Repro for F11.4 — `ToolCallContent.format="text"` is rendered as markdown.

Run:
    ./findings/repros/run.sh findings/repros/tasks/11-tools/F11.4_toolcallcontent_format_text_ignored.py 11-tools
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.model import ChatMessageAssistant, ChatMessageTool  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402
from inspect_ai.tool import ToolCall, ToolCallContent  # noqa: E402

PLAIN_TEXT_BODY = (
    "# This line should be PLAIN TEXT not an <h1> heading\n"
    "**this should be literal asterisks, not bold**\n"
    "- this should be a literal hyphen, not a bullet\n"
    "[not a link](http://example.invalid)\n"
    "\n"
    "If you see a bullet point and a blue hyperlink above (instead of a "
    "literal hyphen and literal square-bracket text), F11.4 is confirmed: "
    "format='text' was ignored."
)

DESC = bug_description(
    finding_id="F11.4",
    title="ToolCallContent.format='text' is ignored — content rendered as markdown",
    where_to_look=(
        "**Messages tab** → message #2 (the assistant tool call) → the "
        "block titled `format='text' custom view`, just above the grey "
        "tool-output box."
    ),
    observed=(
        "Line 1 renders as a bold heading (the `#` is consumed — it's an "
        "`<h1>` in the DOM, though styled small); line 2 is bold (`**` "
        "consumed); line 3 is a `•` bullet; line 4 is a blue underlined "
        "hyperlink. `format='text'` was not honoured."
    ),
    expected=(
        "All lines render as literal text with `#`, `**`, `- `, and "
        "`[...]()` shown verbatim (e.g. in a `<pre>`)."
    ),
    extra=(
        "`ToolInput.tsx` unconditionally passes "
        "`toolCallView.content` to `<RenderedText markdown=…>`, "
        "ignoring `toolCallView.format`."
    ),
)


@solver
def inject_text_format_view() -> Solver:
    async def solve(state: TaskState, _generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        state.messages.append(
            ChatMessageAssistant(
                model="mockllm/model",
                content="Calling plain_text_tool…",
                tool_calls=[
                    ToolCall(
                        id="t1",
                        function="plain_text_tool",
                        arguments={"data": "raw"},
                        # The Python contract: format="text" means render
                        # literally, no markdown parsing.
                        view=ToolCallContent(
                            title="format='text' custom view",
                            format="text",
                            content=PLAIN_TEXT_BODY,
                        ),
                    )
                ],
            )
        )
        state.messages.append(
            ChatMessageTool(
                tool_call_id="t1",
                function="plain_text_tool",
                content="(tool output — not under test)",
            )
        )
        return state

    return solve


@task
def f11_4_toolcallcontent_format_text_ignored() -> Task:
    return Task(
        name="F11.4_toolcallcontent_format_text_ignored",
        dataset=[Sample(id="F11.4", input=DESC, target="n/a")],
        solver=inject_text_format_view(),
    )
