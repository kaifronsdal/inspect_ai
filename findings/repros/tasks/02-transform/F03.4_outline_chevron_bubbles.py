"""Repro for F03.4 — Outline expand/collapse chevron click bubbles to row → also selects.

Uses **plain** ``span(name)`` (no ``type=``) so the outline renders real
expandable rows with chevrons. ``type='agent'`` triggers swimlane mode where
agent spans become leaf agent-cards (no chevron).

**Re-audited 2026-04-24:** The original finding claims the chevron click
"also scrolls the main transcript". That is **false** in the inspect app —
``onNavigateToEvent`` is only wired up by ``apps/scout``
(``TimelineEventsView.tsx:228``); ``apps/inspect`` (``TranscriptPanel.tsx``)
leaves it ``undefined`` and does navigation purely via the ``<Link>`` inside
the label. The chevron is *not* inside the link, so no URL change → no scroll.
What *does* leak through is ``onSelect`` → the row's selection highlight
moves. That is the only observable symptom in inspect.

Run:
    ./findings/repros/run.sh findings/repros/tasks/02-transform/F03.4_outline_chevron_bubbles.py 02-transform
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
    finding_id="F03.4",
    title="Outline chevron click bubbles to row onSelect — selection highlight jumps",
    where_to_look=(
        "Transcript tab → **Outline** (left panel). **(1)** Click the "
        "**label text** of `FIRST_select_me_by_clicking_my_label` — "
        "it becomes bold (selected). **(2)** Now click only the "
        "**▾ chevron** (NOT the label) to the left of "
        "`SECOND_click_my_CHEVRON_not_my_label`."
    ),
    observed=(
        "`SECOND` collapses (chevron flips ▾→▸, `child_a`/`child_b` "
        "disappear) **and** its row becomes bold/selected — the "
        "highlight jumps from `FIRST` to `SECOND`. The chevron's "
        "`onClick` (`OutlineRow.tsx:64-73`) lacks "
        "`e.stopPropagation()`, so the row's `onSelect` also fires. "
        "The transcript pane does **not** scroll — the finding's "
        "original 'scrolls the main transcript' claim does not apply "
        "to the inspect viewer (`onNavigateToEvent` is `undefined` "
        "here; only `apps/scout` wires it)."
    ),
    expected=(
        "Only the outline node collapses. `FIRST` stays selected "
        "(bold); transcript scroll position unchanged."
    ),
    extra=(
        "**Note:** impact is minor — the only observable symptom in "
        "the inspect viewer is the bold selection highlight moving "
        "to the clicked row, which self-corrects on the next scroll "
        "(`useScrollTrack`). The scroll-jump impact is **scout-only**. "
        "Downgraded MEDIUM→LOW."
    ),
)


@solver
def expandable_outline() -> Solver:
    """Two top-level spans; the second has children so it gets a chevron.

    Clicking the *first* span's label puts the selection highlight on it.
    Then clicking the *second* span's **chevron** should only collapse it —
    but the click bubbles to the row's ``onSelect`` and the highlight jumps.
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        async with span("FIRST_select_me_by_clicking_my_label"):
            state = await generate(state)

        async with span("SECOND_click_my_CHEVRON_not_my_label"):
            state = await generate(state)
            async with span("child_a"):
                state = await generate(state)
            async with span("child_b"):
                state = await generate(state)

        # Padding so a hypothetical scroll-jump would be visible (it won't be —
        # see module docstring — but this lets the check measure scrollTop).
        async with span("scroll_padding_BELOW"):
            for i in range(15):
                transcript().info(f"padding {i + 1:02d}/15")
            state = await generate(state)
        return state

    return solve


@task
def f03_4_outline_chevron_bubbles() -> Task:
    return Task(
        name="F03.4_outline_chevron_bubbles",
        dataset=[Sample(id="F03.4", input=DESC, target="n/a")],
        solver=expandable_outline(),
    )
