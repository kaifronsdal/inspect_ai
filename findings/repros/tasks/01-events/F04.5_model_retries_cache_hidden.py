"""Repro for F04.5 — ModelEvent `retries` and `cache` fields never displayed.

Run:
    ./findings/repros/run.sh findings/repros/tasks/01-events/F04.5_model_retries_cache_hidden.py 01-events
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

MOCK = "mockllm/model"

DESC = bug_description(
    finding_id="F04.5",
    title="ModelEvent `retries` and `cache` are never surfaced in any tab",
    where_to_look=(
        "Transcript tab → **Model Call: mockllm/model** panel → "
        "check the title bar and the **Summary** / **All** sub-tabs "
        "(the All tab has USAGE, TIMING, and MESSAGES sections)"
    ),
    observed=(
        "Nothing anywhere indicates `retries: 3` or `cache: \"read\"`. "
        "The title bar, Summary tab, and the USAGE/TIMING sections under "
        "the All tab are all silent — no retries row, no cache row."
    ),
    expected=(
        "A badge or row showing **3 retries** and **cached (read)** — "
        "users debugging flaky calls need to know a request was retried, "
        "and users debugging cached evals need to know the output was "
        "served from cache (which also affects how to interpret "
        "`output.time` and token billing)."
    ),
    extra=(
        "This event was constructed directly (mockllm cannot be coerced "
        "into retrying). Open the sample-level **JSON** tab → search for "
        '`"event": "model"` → confirm `"retries": 3` and `"cache": "read"` '
        "are present in the raw data."
    ),
)


@solver
def emit_model_event_with_retries() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        del generate
        # mockllm never retries and never sets cache, so construct the event by
        # hand and push it onto the transcript directly.
        transcript()._event(
            ModelEvent(
                model=MOCK,
                input=[
                    ChatMessageUser(
                        content=(
                            "This synthetic ModelEvent has `retries=3` and "
                            "`cache='read'` set on the event object."
                        )
                    )
                ],
                tools=[],
                tool_choice="none",
                config=GenerateConfig(),
                output=ModelOutput.from_content(
                    MOCK,
                    "(output served from cache after 3 retries — but the viewer "
                    "won't tell you that)",
                ),
                retries=3,
                cache="read",
            )
        )
        return state

    return solve


@task
def f04_5_model_retries_cache_hidden() -> Task:
    return Task(
        name="F04.5_model_retries_cache_hidden",
        dataset=[Sample(id="F04.5", input=DESC, target="n/a")],
        solver=emit_model_event_with_retries(),
    )
