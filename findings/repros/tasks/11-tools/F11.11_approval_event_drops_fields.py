"""Repro for F11.11 — ApprovalEventView drops `approver`, `modified`, `message`.

Run:
    ./findings/repros/run.sh findings/repros/tasks/11-tools/F11.11_approval_event_drops_fields.py 11-tools
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
from inspect_ai.approval import (  # noqa: E402
    Approval,
    ApprovalPolicy,
    Approver,
    approver,
)
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.model import ChatMessage, get_model  # noqa: E402
from inspect_ai.solver import (  # noqa: E402
    Generate,
    Solver,
    TaskState,
    solver,
)
from inspect_ai.tool import Tool, ToolCall, ToolCallView, tool  # noqa: E402

APPROVER_SENTINEL = "F11.11_APPROVER_NAME_security_reviewer"
MODIFIED_SENTINEL = "F11.11_MODIFIED_ARG_VALUE_sanitised_path"

DESC = bug_description(
    finding_id="F11.11",
    title="ApprovalEventView drops `approver`, `modified`, and `message`",
    where_to_look=(
        "**Transcript** tab → the thin row with a ✏️ pencil icon and "
        "the label **MODIFIED**, directly below the **TOOL: WRITE_FILE** "
        "panel (and above the second **MODEL CALL** panel). It is a "
        "single non-expandable line — there is no separate 'Approval' panel."
    ),
    observed=(
        "The row renders only the pencil icon, the decision label "
        "**Modified**, and the `explanation` string. The approver name "
        f"(`{APPROVER_SENTINEL}`), the rewritten arguments "
        f"(`path={MODIFIED_SENTINEL}`), and `ApprovalEvent.message` "
        "(`F11.11_ASSISTANT_MESSAGE…`) are not rendered anywhere in the row."
    ),
    expected=(
        "The approval row should also show WHO approved and — for "
        "`decision='modify'` — the original→modified argument diff "
        "(the adjacent Tool panel shows the *original* `path` but the "
        "*modified* output, so without a diff the mismatch is unexplained)."
    ),
    extra=(
        "Switch to the sample **JSON** tab and search for "
        "`\"event\": \"approval\"` — `approver`, `modified`, and "
        "`message` are all populated in the log but never read by "
        "`ApprovalEventView.tsx`."
    ),
)


@tool
def write_file() -> Tool:
    async def execute(path: str) -> str:
        """Write to a file.

        Args:
            path: target path
        """
        return f"wrote to {path}"

    return execute


@approver(name=APPROVER_SENTINEL)
def modifying_approver() -> Approver:
    """Approver that MODIFIES the tool call (decision='modify')."""

    async def approve(
        message: str,
        call: ToolCall,
        view: ToolCallView,
        history: list[ChatMessage],
    ) -> Approval:
        return Approval(
            decision="modify",
            modified=ToolCall(
                id=call.id,
                function=call.function,
                arguments={"path": MODIFIED_SENTINEL},
            ),
            explanation=(
                "Rewrote `path` to a sandboxed value. (This sentence is "
                "`ApprovalEvent.explanation` — if the row shows only the "
                "pencil icon, 'Modified', and this sentence, with no "
                "approver name or arg diff, F11.11 is confirmed.)"
            ),
        )

    return approve


@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        state.tools = [write_file()]
        return await generate(state)

    return solve


@task
def f11_11_approval_event_drops_fields() -> Task:
    outputs = [
        mock_tool_call(
            "write_file",
            {"path": "/etc/passwd"},
            content=(
                "F11.11_ASSISTANT_MESSAGE — this is `ApprovalEvent.message`; "
                "it should be visible in the Approval event view."
            ),
        ),
        mock_text("Done."),
    ]
    return Task(
        name="F11.11_approval_event_drops_fields",
        dataset=[Sample(id="F11.11", input=DESC, target="n/a")],
        solver=repro_solver(),
        approval=[ApprovalPolicy(approver=modifying_approver(), tools="*")],
        model=get_model("mockllm/model", custom_outputs=outputs),
    )
