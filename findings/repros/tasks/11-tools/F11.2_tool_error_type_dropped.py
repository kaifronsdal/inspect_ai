"""Repro for F11.2 — `ToolCallError.type` is never displayed.

Run:
    ./findings/repros/run.sh findings/repros/tasks/11-tools/F11.2_tool_error_type_dropped.py 11-tools
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
from inspect_ai.tool import ToolCall, ToolCallError  # noqa: E402

DESC = bug_description(
    finding_id="F11.2",
    title="ToolCallError.type is dropped — only .message is shown",
    where_to_look=(
        "**Messages tab** → row 2 → the grey output box under "
        "`restricted_op`. (The Transcript tab has no Tool event in "
        "this repro — Messages is the only place to look.)"
    ),
    observed=(
        "The grey `tool-output` box renders `error.message` verbatim "
        "(`Access denied …`) and nothing else — no `permission:` "
        "prefix, no error-type badge, no visual cue that this is an "
        "error rather than a successful result."
    ),
    expected=(
        "Error rendered as e.g. `permission: <message>` (or with a "
        "type badge) so the diagnostic category — timeout vs "
        "permission vs approval vs limit … — is visible."
    ),
    extra=(
        "The field *is* in the log: **JSON tab** → search for "
        '`"error"` → shows `"type": "permission"`. The viewer reads '
        "`error.message` only (`ChatMessageRow.tsx`, "
        "`ToolEventView.tsx`) and never reads `error.type`."
    ),
)


@solver
def inject_typed_error() -> Solver:
    async def solve(state: TaskState, _generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        state.messages.append(
            ChatMessageAssistant(
                model="mockllm/model",
                content="Calling restricted_op…",
                tool_calls=[
                    ToolCall(id="t1", function="restricted_op", arguments={})
                ],
            )
        )
        state.messages.append(
            ChatMessageTool(
                tool_call_id="t1",
                function="restricted_op",
                content="",
                error=ToolCallError(
                    type="permission",  # ← the field under test; never rendered
                    message=(
                        "Access denied to /etc/shadow. "
                        "[This is error.message — note error.type is NOT "
                        "shown anywhere alongside it.]"
                    ),
                ),
            )
        )
        return state

    return solve


@task
def f11_2_tool_error_type_dropped() -> Task:
    return Task(
        name="F11.2_tool_error_type_dropped",
        dataset=[Sample(id="F11.2", input=DESC, target="n/a")],
        solver=inject_typed_error(),
    )
