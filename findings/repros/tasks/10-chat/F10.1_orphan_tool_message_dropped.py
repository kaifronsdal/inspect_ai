"""Repro for F10.1 — Orphan tool messages are silently dropped.

Run:
    ./findings/repros/run.sh findings/repros/tasks/10-chat/F10.1_orphan_tool_message_dropped.py 10-chat
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.model import ChatMessageTool, ChatMessageUser  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

ORPHAN_SENTINEL = (
    "⚠️ F10.1 ORPHAN TOOL MESSAGE — IF THIS LINE IS MISSING FROM THE "
    "MESSAGES TAB, THE BUG IS CONFIRMED. (This tool message follows a USER "
    "message, not an assistant message.)"
)

DESC = bug_description(
    finding_id="F10.1",
    title="Orphan tool messages (not following an assistant) are silently dropped",
    where_to_look=(
        "**Messages tab**. Scroll past this description to rows 2 and 3."
    ),
    observed=(
        "Only **3 rows** render, all labelled USER. Row 2 "
        "('Second user turn… ↓') is immediately followed by row 3 "
        "('Third user turn… ↑') — the `role=tool` message that sits "
        "between them in the raw log has vanished with no placeholder "
        "or warning."
    ),
    expected=(
        "The orphan tool message containing the text "
        f"`{ORPHAN_SENTINEL[:40]}…` should be rendered as its own "
        "row between rows 2 and 3, since it has no assistant "
        "tool-call to pair with."
    ),
    extra=(
        "`resolveMessages` (messages.ts) attaches every tool "
        "message to the *preceding* row regardless of role; "
        "`ChatMessageRow` only iterates `toolMessages` when that "
        "row is `role=assistant` with `tool_calls`. So a tool "
        "message after a user row is collected but never rendered.\n\n"
        "Cross-check: open the **JSON tab** → `messages` array — "
        "roles are `[user, user, tool, user]` and the full sentinel "
        "+ `tool_call_id: orphan-001` are present, so the message "
        "*is* in the log.\n\n"
        "**Note:** impact is MEDIUM (downgraded from HIGH) — "
        "triggering this requires a malformed message sequence (a "
        "`tool` message not following an `assistant` tool-call); no "
        "standard `generate()` loop produces this. It only affects "
        "debugging of hand-built / compacted / imported conversations."
    ),
)


@solver
def inject_orphan_tool() -> Solver:
    async def solve(state: TaskState, _generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        # The first message is the user bug-description (from Sample.input).
        # We append a *user* turn followed immediately by a *tool* turn — no
        # assistant in between → the tool message is "orphaned".
        state.messages.append(
            ChatMessageUser(
                content=(
                    "Second user turn. The NEXT message in the raw log is a "
                    "`role=tool` message with no preceding assistant. ↓"
                )
            )
        )
        state.messages.append(
            ChatMessageTool(
                tool_call_id="orphan-001",
                function="orphaned_tool",
                content=ORPHAN_SENTINEL,
            )
        )
        state.messages.append(
            ChatMessageUser(
                content=(
                    "Third user turn. ↑ A tool message should appear "
                    "immediately ABOVE this line. If you see nothing between "
                    "the previous user turn and this one, F10.1 is confirmed."
                )
            )
        )
        return state

    return solve


@task
def f10_1_orphan_tool_message_dropped() -> Task:
    return Task(
        name="F10.1_orphan_tool_message_dropped",
        dataset=[Sample(id="F10.1", input=DESC, target="n/a")],
        solver=inject_orphan_tool(),
    )
