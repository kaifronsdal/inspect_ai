"""Repro for F02.2 + F02.3 — injectScorersSpan key mismatch & stops after first scorer.

The two bugs share one trigger (legacy-shaped log: `type="scorer"` spans present,
no `type="scorers"` wrapper) so one .eval demonstrates both.

Run:
    ./findings/repros/run.sh findings/repros/tasks/02-transform/F02.2_F02.3_scorers_span_injection.py 02-transform
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.event import InfoEvent, SpanBeginEvent, SpanEndEvent  # noqa: E402
from inspect_ai.event._score import ScoreEvent  # noqa: E402
from inspect_ai.log import transcript  # noqa: E402
from inspect_ai.scorer import Score  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

DESC = bug_description(
    finding_id="F02.2",
    title="injectScorersSpan: synthetic 'Scorers' wrapper never receives its children (key mismatch + only-first-scorer)",
    where_to_look=(
        "Transcript tab → look at the **root level** of the event list; "
        "also see the outline tree on the left."
    ),
    observed=(
        "`scorer_ONE_…` and `scorer_TWO_…` both render as **top-level "
        "siblings** (depth 0 in the outline, same indent as the solver). "
        "There is **no** `Scorers` group node wrapping them — it was created "
        "empty and stripped by `filterEmpty`."
    ),
    expected=(
        "A single `Scorers` group node at root containing **both** "
        "`scorer_ONE_…` and `scorer_TWO_…` as children."
    ),
    extra=(
        "**Note:** impact is minor — only affects pre-May-2025 logs. Since "
        "2025-05-23 inspect emits a real `type=\"scorers\"` span and "
        "`injectScorersSpan` short-circuits; this fixup path is dead for "
        "modern logs.\n\n"
        "**F02.2** — the synthetic wrapper has `id: kBeginScorerId` but "
        "children are re-parented to `kScorersSpanId`; `treeifyWithSpans` "
        "keys `spanNodes` by `event.id`, so the lookup misses → scorer ONE "
        "falls to root and the wrapper is empty.\n\n"
        "**F02.3** — after flushing scorer ONE, `hasCollectedScorers=true` "
        "permanently disables collection, so scorer TWO is never wrapped.\n\n"
        "*(The sample shows an intentional error — that is just to suppress "
        "the modern `scorers` span so the legacy fixup path runs.)*"
    ),
)


def _scorer_span(span_id: str, name: str) -> tuple[SpanBeginEvent, SpanEndEvent]:
    """Build a root-level (parent_id=None) scorer span begin/end pair.

    span_id is set explicitly == id so it matches what the real `span()` cm
    would have produced, and parent_id=None so the span sits at root — the
    shape `injectScorersSpan` is meant to fix up.
    """
    return (
        SpanBeginEvent(id=span_id, span_id=span_id, parent_id=None, type="scorer", name=name),
        SpanEndEvent(id=span_id, span_id=span_id),
    )


@solver
def emit_legacy_scorer_spans() -> Solver:
    """Emit two root-level `type="scorer"` spans, then raise.

    Raising (with `fail_on_error=False`) prevents the eval loop from opening
    its own `span(name="scorers")` wrapper — giving us the legacy log shape
    that `injectScorersSpan` is supposed to repair.
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        # --- scorer ONE -----------------------------------------------------
        begin1, end1 = _scorer_span(
            "scorer1_id", "scorer_ONE_should_be_under_Scorers_wrapper"
        )
        transcript()._event(begin1)
        transcript()._event(
            InfoEvent(
                source="repro",
                data="F02.2: this scorer's parent_id is rewritten to "
                "kScorersSpanId, but the synthetic wrapper is keyed in "
                "spanNodes by kBeginScorerId — lookup misses, scorer lands at root.",
                span_id="scorer1_id",
            )
        )
        transcript()._event(
            ScoreEvent(score=Score(value=1.0, answer="one"), target=["n/a"], span_id="scorer1_id")
        )
        transcript()._event(end1)

        # --- scorer TWO -----------------------------------------------------
        begin2, end2 = _scorer_span(
            "scorer2_id", "scorer_TWO_should_ALSO_be_under_Scorers_wrapper"
        )
        transcript()._event(begin2)
        transcript()._event(
            InfoEvent(
                source="repro",
                data="F02.3: hasCollectedScorers is now true, so this second "
                "scorer is never collected — it passes straight through and "
                "is not even *attempted* to be wrapped.",
                span_id="scorer2_id",
            )
        )
        transcript()._event(
            ScoreEvent(score=Score(value=0.0, answer="two"), target=["n/a"], span_id="scorer2_id")
        )
        transcript()._event(end2)

        # Prevent the real `span("scorers")` wrapper from being emitted —
        # otherwise injectScorersSpan short-circuits and the bug is hidden.
        raise RuntimeError(
            "Intentional error: skip the modern `scorers` wrapper so "
            "injectScorersSpan runs (F02.2 / F02.3 repro)."
        )

    return solve


@task
def f02_2_f02_3_scorers_span_injection() -> Task:
    return Task(
        name="F02.2_F02.3_scorers_span_injection",
        dataset=[Sample(id="F02.2", input=DESC, target="n/a")],
        solver=emit_legacy_scorer_spans(),
        fail_on_error=False,
    )
