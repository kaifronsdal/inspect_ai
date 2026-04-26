"""Repro for F01.1 — ModelEventView Summary tab drops preceding messages when input ends with assistant.

Run:
    ./findings/repros/run.sh findings/repros/tasks/01-events/F01.1_model_summary_drops_preceding.py 01-events
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
    ModelOutput,
    get_model,
)
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

MOCK = "mockllm/model"

DESC = bug_description(
    finding_id="F01.1",
    title="ModelEventView Summary tab drops preceding messages when input ends with an assistant message",
    where_to_look=(
        "Transcript tab → **Model Call: mockllm/model** panel (below this banner) → "
        "**Summary** subtab (selected by default)"
    ),
    observed=(
        "Summary shows only two ASSISTANT cards: the trailing assistant input message "
        "and the model output. The ⚠️ system message and ⚠️ user message are MISSING."
    ),
    expected=(
        "Summary should show all messages preceding the trailing assistant — "
        "`[system (⚠️), user, user (⚠️), assistant, output]` (5 cards)."
    ),
    extra=(
        "Root cause: `event.input.slice(offset)` with `offset = -1` returns only "
        "the last element, not 'everything except the last'. Fix: "
        "`event.input.slice(0, offset)`.\n\n"
        "**To verify:** click the **All** subtab on the same panel — the ⚠️ system "
        "and ⚠️ user messages ARE present in the raw input. They are only missing "
        "from Summary."
    ),
)


@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        # Append a trailing assistant message so event.input ends with role="assistant".
        # The user/system messages BEFORE it should appear in the Summary tab — but
        # F01.1 drops them because `event.input.slice(-1)` returns only the last item.
        state.messages.append(
            ChatMessageAssistant(
                content=(
                    "**[trailing assistant / compaction-style message]**\n\n"
                    "Because this assistant message is the LAST entry in `event.input`, "
                    "the Summary tab sets `offset = -1` and then iterates "
                    "`event.input.slice(-1)` — which is just this message. The user "
                    "and system messages above never get collected."
                ),
                model=MOCK,
            )
        )
        return await generate(state)

    return solve


@task
def f01_1_model_summary_drops_preceding() -> Task:
    sample = Sample(
        id="F01.1",
        input=[
            ChatMessageSystem(
                content=(
                    "⚠️ **SYSTEM MESSAGE — IF YOU CANNOT SEE THIS IN THE SUMMARY TAB, "
                    "BUG F01.1 IS CONFIRMED** ⚠️"
                )
            ),
            ChatMessageUser(content=DESC),
            ChatMessageUser(
                content=(
                    "⚠️ **USER MESSAGE — IF YOU CANNOT SEE THIS IN THE SUMMARY TAB, "
                    "BUG F01.1 IS CONFIRMED** ⚠️\n\n"
                    "(This message immediately precedes the trailing assistant message "
                    "in `event.input`; the Summary tab is supposed to crawl back and "
                    "include it.)"
                )
            ),
        ],
        target="n/a",
        metadata={"finding_id": "F01.1"},
    )

    return Task(
        name="F01.1_model_summary_drops_preceding",
        dataset=[sample],
        solver=repro_solver(),
        model=get_model(
            MOCK,
            custom_outputs=[
                ModelOutput.from_content(MOCK, "**[model output]** — end of summary."),
            ],
        ),
    )
