"""Repro for F10.7 — multiple system messages merged + hoisted to top.

Run:
    ./findings/repros/run.sh findings/repros/tasks/10-chat/F10.7_system_messages_merged_hoisted.py 10-chat
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.model import (  # noqa: E402
    ChatMessageAssistant,
    ChatMessageSystem,
    ChatMessageUser,
)
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

DESC = bug_description(
    finding_id="F10.7",
    title="System-message collapse drops per-message metadata and mid-stream position",
    where_to_look=(
        "**Messages** tab → row **1** (`SYSTEM`). Compare against row **4** "
        "(`USER`), which renders a `Metadata` section. Then open the **JSON** "
        "tab and search for `F10.7_SYSTEM` to confirm the system metadata is "
        "in the log."
    ),
    observed=(
        "5 rows render (source list has 7 messages). Row 1 is one `SYSTEM` "
        "box containing all three system texts run together; it has **no** "
        "`Metadata` section — the `F10.7_SYSTEM_*_METADATA` sentinels are "
        "absent from this tab (yet row 4's user metadata *is* shown). "
        "Mid-stream injections #2 and #3 are hoisted above row 3 "
        "(`Assistant turn A`), so their original positions (after rows 3 "
        "and 5) are not recoverable."
    ),
    expected=(
        "The merged `SYSTEM` row preserves and displays the three source "
        "messages' `metadata` (same `Metadata` section every other role "
        "gets) — or, when system messages are non-contiguous, renders each "
        "in place so mid-stream order is visible."
    ),
    extra=(
        "**Note:** collapsing all system messages into one top-of-list row "
        "is *intentional* (`messages.ts:62-105`, since the initial commit). "
        "The bug is the **side-effect**: the synthetic row hard-codes "
        "`metadata: null` and a fixed id, so user-authored system metadata "
        "is silently discarded and an agent that injects reminder system "
        "prompts mid-conversation cannot be debugged from this view — you "
        "can't tell *when* the model saw each injection."
    ),
)


@solver
def build_interleaved() -> Solver:
    async def solve(state: TaskState, _generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        state.messages = [
            ChatMessageSystem(
                content=(
                    "🟦 SYSTEM MSG #1 — should appear at position 1 (before "
                    "the first user turn). If #2 and #3 are concatenated "
                    "below this line inside the SAME grey box, F10.7 confirmed."
                ),
                metadata={"sentinel": "F10.7_SYSTEM_1_METADATA"},
            ),
            ChatMessageUser(content=DESC),
            ChatMessageAssistant(
                model="mockllm/model",
                content="Assistant turn A — system msg #2 should appear AFTER me.",
            ),
            ChatMessageSystem(
                content=(
                    "🟦 SYSTEM MSG #2 — should appear at position 4, AFTER "
                    "'Assistant turn A' and BEFORE 'User turn B'. NOT merged "
                    "at the top."
                ),
                metadata={"sentinel": "F10.7_SYSTEM_2_METADATA"},
            ),
            ChatMessageUser(
                content=(
                    "User turn B — system msg #2 should be ABOVE me. "
                    "(My metadata renders below; the SYSTEM row's does not.)"
                ),
                metadata={
                    "sentinel": "F10.7_USER_B_METADATA — shown; system metadata is not"
                },
            ),
            ChatMessageAssistant(
                model="mockllm/model",
                content="Assistant turn B — system msg #3 should appear AFTER me.",
            ),
            ChatMessageSystem(
                content=(
                    "🟦 SYSTEM MSG #3 — should be the LAST row in the "
                    "conversation (position 7). NOT merged at the top."
                ),
                metadata={"sentinel": "F10.7_SYSTEM_3_METADATA"},
            ),
        ]
        return state

    return solve


@task
def f10_7_system_messages_merged_hoisted() -> Task:
    return Task(
        name="F10.7_system_messages_merged_hoisted",
        dataset=[
            Sample(
                id="F10.7",
                input=DESC,  # placeholder; solver replaces messages wholesale
                target="n/a",
                metadata={"finding_id": "F10.7"},
            )
        ],
        solver=build_interleaved(),
    )
