"""Repro for F10.6 — `<think>` blocks in plain string content are silently stripped.

Run:
    ./findings/repros/run.sh findings/repros/tasks/10-chat/F10.6_think_tags_stripped_silently.py 10-chat
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.model import ChatMessageAssistant  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

HIDDEN_SENTINEL = (
    "F10.6_HIDDEN_REASONING — IF YOU CAN READ THIS the bug is FIXED; "
    "if it is missing with no '[hidden]' marker, F10.6 is CONFIRMED."
)

DESC = bug_description(
    finding_id="F10.6",
    title="<think>/<internal> in plain string content is stripped with no indicator",
    where_to_look="**Messages tab** → row **#2** (the assistant message).",
    observed=(
        "Row #2 begins directly with *'Visible answer: the capital of "
        "France is Paris.'* The `<think>` block that precedes it in the "
        f"raw content (sentinel `{HIDDEN_SENTINEL[:25]}…`) is absent — "
        "no Reasoning header, no '[hidden]'/'[redacted]' placeholder, "
        "nothing."
    ),
    expected=(
        "Either render the `<think>` body (e.g. promote it to the "
        "collapsible **Reasoning** block used for `ContentReasoning`), "
        "or leave a visible marker that content was removed."
    ),
    extra=(
        "**Status:** this strip *is documented as intentional* — "
        "`design/migration/chat-migration.md` lists `<think>` under "
        "'Internal tag stripping', and `apps/scout/e2e/"
        "chat-components.spec.ts` asserts the body is hidden. The tags "
        "are agent-bridge serialisation envelopes, normally lifted into "
        "`ContentReasoning` before reaching the renderer.\n\n"
        "**However**, silently dropping `<think>` content with **no "
        "marker at all** is questionable: a user pasting model output "
        "that contains literal `<think>` tags (e.g. raw DeepSeek-R1 / "
        "QwQ text) loses that content with zero indication. "
        "`purgeInternalContainers` (`MessageContent.tsx`) removes the "
        "element from the rendered DOM and leaves nothing behind.\n\n"
        "**Cross-check:** **JSON tab** → `messages[1].content` — the "
        "raw string contains the full sentinel inside `<think>` tags."
    ),
)


@solver
def inject_think_text() -> Solver:
    async def solve(state: TaskState, _generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        # Plain *string* content (NOT ContentReasoning). Open-weights models
        # commonly emit raw <think>…</think> wrappers in their text output.
        state.messages.append(
            ChatMessageAssistant(
                model="mockllm/model",
                source="generate",
                content=(
                    f"<think>{HIDDEN_SENTINEL}</think>\n"
                    "Visible answer: the capital of France is Paris.\n\n"
                    "↑ The raw content has a think-tag block ABOVE this "
                    "line containing the sentinel "
                    "`F10.6_HIDDEN_REASONING …`. If this paragraph is "
                    "the first thing you see — with no Reasoning header "
                    "and no redaction marker — the viewer silently "
                    "deleted it."
                ),
            )
        )
        return state

    return solve


@task
def f10_6_think_tags_stripped_silently() -> Task:
    return Task(
        name="F10.6_think_tags_stripped_silently",
        dataset=[Sample(id="F10.6", input=DESC, target="n/a")],
        solver=inject_think_text(),
    )
