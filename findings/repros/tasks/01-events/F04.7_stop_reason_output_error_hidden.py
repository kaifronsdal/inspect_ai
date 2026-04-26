"""Repro for F04.7 — `output.stop_reason` and `output.error` never surfaced.

Run:
    ./findings/repros/run.sh findings/repros/tasks/01-events/F04.7_stop_reason_output_error_hidden.py 01-events
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.model import ModelOutput, get_model  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

MOCK = "mockllm/model"

DESC = bug_description(
    finding_id="F04.7",
    title="ModelOutput `stop_reason` and `output.error` are never displayed",
    where_to_look=(
        "Transcript tab → **Model Call: mockllm/model** panel → check both "
        "the **Summary** and **All** sub-tabs"
    ),
    observed=(
        "The ASSISTANT message just… ends mid-sentence. No `max_tokens` "
        "badge or chip, no indication the completion was truncated. The "
        "`output.error` refusal text (`⚠️ PROVIDER REFUSAL …`) appears "
        "nowhere in the panel — the All sub-tab shows only Usage / Timing / "
        "Messages sections."
    ),
    expected=(
        "`stop_reason` shown when ≠ `stop`/`tool_calls` (e.g. a "
        "'truncated: max_tokens' chip on the assistant message). "
        "`output.error` rendered alongside the output (the existing Error "
        "section only reads `event.error`, not `event.output.error`)."
    ),
    extra=(
        "This is `ModelOutput.error`, **not** `ModelEvent.error` — they "
        "are different fields. `event.error` IS rendered; "
        "`event.output.error` is not. (Caveat: `output.error` does paint "
        "a red marker on the timeline strip above, but never appears in "
        "the event panel itself.)\n\n"
        "Verify the data is present in the sample **JSON** tab: the model "
        "event's `output.choices[0].stop_reason` is `\"max_tokens\"` and "
        "`output.error` is the ⚠️ string."
    ),
)


@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        return await generate(state)

    return solve


@task
def f04_7_stop_reason_output_error_hidden() -> Task:
    # A ModelOutput with stop_reason="max_tokens" and a content-moderation
    # error string. Neither is rendered anywhere in ModelEventView.
    truncated = ModelOutput.from_content(
        model=MOCK,
        content=(
            "This completion was truncated mid-sentence because the model hit "
            "max_tokens, and the provider also returned a content-moderation "
            "error — but you wouldn't know either of those things from"
        ),
        stop_reason="max_tokens",
        error="⚠️ PROVIDER REFUSAL: content filtered (output.error field) ⚠️",
    )

    return Task(
        name="F04.7_stop_reason_output_error_hidden",
        dataset=[Sample(id="F04.7", input=DESC, target="n/a")],
        solver=repro_solver(),
        model=get_model(MOCK, custom_outputs=[truncated]),
    )
