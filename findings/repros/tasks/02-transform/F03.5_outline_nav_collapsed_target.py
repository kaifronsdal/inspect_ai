"""Repro for F03.5 — clicking an outline node whose target is inside a collapsed transcript parent does nothing.

Uses **plain** ``span(name)`` (no ``type=``) so the transcript renders a real
nested tree with collapsible chevrons. ``type='agent'`` MUST NOT be used —
that triggers swimlane/agent-card mode which flattens children to siblings.

Run:
    ./findings/repros/run.sh findings/repros/tasks/02-transform/F03.5_outline_nav_collapsed_target.py 02-transform
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.log import transcript  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402
from inspect_ai.util import span  # noqa: E402

DESC = bug_description(
    finding_id="F03.5",
    title="Outline → transcript navigation silently fails when target is inside a collapsed transcript parent",
    where_to_look=(
        "Transcript tab. **(1)** In the **transcript** (right panel), "
        "click the chevron on `LEVEL1_COLLAPSE_ME` to **collapse** it. "
        "**(2)** In the **outline** (left panel), click "
        "`level4_CLICK_ME_in_outline`."
    ),
    observed=(
        "Nothing happens — the transcript stays collapsed at "
        "`level1`, does not scroll, gives no feedback. "
        "`TranscriptVirtualListComponent` resolves the new "
        "`?event=` URL against `flattenedNodes` (built honouring "
        "`collapsedTranscript`), `findIndex → -1`, so "
        "`initialEventIndex` stays `undefined`."
    ),
    expected=(
        "Transcript auto-expands `level1`/`level2`/`level3` and "
        "scrolls to `level4_CLICK_ME_in_outline` (or at minimum "
        "scrolls to the nearest visible ancestor)."
    ),
    extra=(
        "Outline collapse state and transcript collapse state are "
        "independent (`collapseState.outline` vs "
        "`collapseState.transcript`). The deep-link resolver only "
        "searches the *post-collapse* flattened list."
    ),
)


@solver
def deep_nesting() -> Solver:
    """Four levels of plain nested spans with a deep navigation target.

    ~20 InfoEvents at level1 (before the nested subtree) push the deep target
    off-screen so a successful auto-scroll would be observable. A model turn
    inside each span makes the span show up in the outline (the outline
    pipeline strips ``info`` events, so each level needs at least one
    non-filtered child).
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        async with span("level1_COLLAPSE_ME"):
            for i in range(20):
                transcript().info(
                    f"Padding {i + 1:02d}/20 — pushes level4 off-screen so a "
                    "successful scroll would be visible."
                )
            state = await generate(state)
            async with span("level2"):
                state = await generate(state)
                async with span("level3"):
                    state = await generate(state)
                    async with span("level4_CLICK_ME_in_outline"):
                        transcript().info(
                            "F03.5 SCROLL TARGET — if you can read this after "
                            "step (2), the bug is fixed."
                        )
                        state = await generate(state)
        return state

    return solve


@task
def f03_5_outline_nav_collapsed_target() -> Task:
    return Task(
        name="F03.5_outline_nav_collapsed_target",
        dataset=[Sample(id="F03.5", input=DESC, target="n/a")],
        solver=deep_nesting(),
    )
