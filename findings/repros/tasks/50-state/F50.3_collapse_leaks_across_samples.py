"""Repro for F50.3 — collapse / property-bag state leaks across samples and grows unbounded.

This .eval contains TWO samples (`F50.3-A`, `F50.3-B`) with deliberately
parallel structure so that positional UI-state keys (e.g. RecordTree node
`"0.0"`, EventPanel pill index 0) collide between them. The bug is *not*
visible in this log alone — it requires navigating A → interact → B in the
viewer. See ``F50.3_verify.py`` for the Playwright script that drives the
interaction and inspects the Zustand store.

Run:
    ./findings/repros/run.sh \
        findings/repros/tasks/50-state/F50.3_collapse_leaks_across_samples.py \
        50-state
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner, mock_text  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.log import transcript  # noqa: E402
from inspect_ai.model import get_model  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

DESC = bug_description(
    finding_id="F50.3",
    title="Per-component UI state (`app.propertyBags`) is never cleared on "
    "sample switch — entries accumulate forever and positional keys leak "
    "across samples",
    where_to_look=(
        "This bug needs **cross-navigation**, not a single static view. "
        "Run `findings/repros/tasks/50-state/F50.3_verify.py` to drive it, "
        "or manually: open sample **F50.3-A** → Transcript tab → on the "
        "**Model Call** panel click the **All** sub-tab pill → press the "
        "next-sample arrow to go to **F50.3-B** → open browser DevTools → "
        "`JSON.parse(localStorage['app-storage']).state.app.propertyBags`."
    ),
    observed=(
        "After switching to sample B, the `propertyBags` entry keyed by "
        "sample A's event UUID (holding `selectedNav`) is **still present** "
        "— nothing on the sample-load path removes it. Every pill click in "
        "every sample ever visited accumulates here and is persisted to "
        "localStorage on every (debounced) write."
    ),
    expected=(
        "`prepareForSampleLoad` should clear per-event property bags (or "
        "keys should be `${logFile}:${sampleId}:${epoch}:`-prefixed and "
        "swept on switch), so only the current sample's UI state is held."
    ),
    extra=(
        "**Source:** `apps/inspect/src/state/sampleSlice.ts` "
        "`prepareForSampleLoad` deletes only `propertyBags['scrollPosition']` "
        "and `propertyBags['listPosition']`; `useLoadSample.ts` calls "
        "`clearCollapsedEvents()` (so transcript chevron-collapse *is* "
        "reset). Everything else — `selectedNav` per EventPanel, RecordTree "
        "collapse buckets, virtuoso state — survives. "
        "`sample.collapsedIdBuckets` is **dead state** (no callers outside "
        "the slice; `useCollapsibleIds` writes to `app.propertyBags` "
        "instead)."
    ),
)


# Identical nested-metadata shape for both samples → RecordTree node ids
# (`"0.0"`, `"1.0.1"`, …) are positional and therefore collide. The *values*
# differ so a leak is visible if it occurs.
def _nested_md(tag: str) -> dict[str, object]:
    return {
        "outer": {
            "inner_a": f"value-{tag}-a",
            "inner_b": f"value-{tag}-b",
            "deep": {"leaf_1": f"deep-{tag}-1", "leaf_2": f"deep-{tag}-2"},
        },
        "second": {"x": f"x-{tag}", "y": f"y-{tag}"},
    }


@solver
def repro_solver(tag: str) -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        # Three info events at fixed positions so transcript shape is
        # identical between samples (positional collapse keys would collide
        # — but note `collapsedEvents` IS cleared on sample switch, so
        # transcript-chevron collapse does *not* leak; the verify script
        # checks this as the negative control).
        transcript().info(f"[{tag}] info event #1", source="repro")
        transcript().info(f"[{tag}] info event #2", source="repro")
        transcript().info(f"[{tag}] info event #3", source="repro")
        # One model call → EventPanel renders Summary / All sub-tab pills.
        # Clicking a pill writes
        #   app.propertyBags[<event-uuid>].selectedNav = "<event-uuid>-nav-pill-N"
        # which is *never* cleared.
        return await generate(state)

    return solve


@task
def f50_3_collapse_leaks_across_samples() -> Task:
    return Task(
        name="F50.3_collapse_leaks_across_samples",
        dataset=[
            Sample(
                id="F50.3-A",
                input=DESC,
                target="n/a",
                metadata=_nested_md("A"),
            ),
            Sample(
                id="F50.3-B",
                input=DESC,
                target="n/a",
                metadata=_nested_md("B"),
            ),
        ],
        solver=repro_solver("sample"),
        model=get_model(
            "mockllm/model",
            custom_outputs=[
                mock_text("(model output for sample A — gives the EventPanel sub-tabs)"),
                mock_text("(model output for sample B — gives the EventPanel sub-tabs)"),
            ],
        ),
    )
