"""Repro for F02.4 — unwrapNode only adjusts immediate-child depth, not descendants.

Run:
    ./findings/repros/run.sh findings/repros/tasks/02-transform/F02.4_unwrap_main_grandchild_depth.py 02-transform
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
    finding_id="F02.4",
    title="unwrapNode (type='main') only re-depths direct children; grandchildren render one indent too deep",
    where_to_look=(
        "**Outline (left panel)** or transcript: compare the left "
        "edge of `REFERENCE_correct_depth_2` against "
        "`BUGGY_GRANDCHILD_should_be_depth_2`. They are logically "
        "at the same level (both grandchildren of the solver root) "
        "so their left edges should align."
    ),
    observed=(
        "`BUGGY_GRANDCHILD_should_be_depth_2` is indented **one "
        "extra step** (~16 px transcript / ~9.6 px outline) to the "
        "right of `REFERENCE_correct_depth_2`. Likewise "
        "`BUGGY_CHILD_depth_1` aligns with `REFERENCE_correct_depth_1` "
        "(unwrap fixed *it*), but its children jump straight to "
        "depth 3 — depth 2 is skipped."
    ),
    expected=(
        "`BUGGY_GRANDCHILD_should_be_depth_2` left-aligned with "
        "`REFERENCE_correct_depth_2` (both at depth 2); every "
        "parent→child indent step the same width."
    ),
    extra=(
        "`unwrapNode` (transform.ts) does `child.depth = node.depth` "
        "for direct children only, with no recursion. Contrast with "
        "`discardNode` which correctly uses recursive `reduceDepth`. "
        "Note: no Python code path currently emits `type='main'` — "
        "this repro creates one explicitly to exercise the transformer."
    ),
)


@solver
def nested_under_main() -> Solver:
    """Create a REFERENCE subtree alongside a type='main' subtree for side-by-side indent comparison.

    The `unwrap_main` transformer removes the `type='main'` wrapper and sets
    each *direct* child's depth to the wrapper's depth — but does **not**
    recurse, so grandchildren keep their original (now too-deep) depth.

    Layout (logical depth → rendered depth):
        solver root (d0)
        ├─ REFERENCE_correct_depth_1            d1 → d1 ✓
        │   ├─ info(...)                        d2 → d2 ✓
        │   └─ REFERENCE_correct_depth_2        d2 → d2 ✓
        └─ WRAPPER type="main" (unwrapped away)
            └─ BUGGY_CHILD_depth_1              d2 → d1 ✓ (unwrap sets it)
                ├─ info(...)                    d3 → d3 ✗ (should be d2)
                └─ BUGGY_GRANDCHILD_..._depth_2 d3 → d3 ✗ (should be d2)
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        # --- REFERENCE subtree: NOT inside type="main", so depths are correct.
        async with span("REFERENCE_correct_depth_1"):
            transcript().info(
                "REFERENCE: my children render at correct depth 2. Compare "
                "REFERENCE_correct_depth_2 below against BUGGY_GRANDCHILD "
                "further down — same logical level, BUGGY is one indent deeper."
            )
            async with span("REFERENCE_correct_depth_2"):
                transcript().info("REFERENCE grandchild content (correct depth 3).")

        # --- BUGGY subtree: wrapped in type="main" → unwrapNode mis-depths it.
        async with span("WRAPPER_type_main_gets_unwrapped", type="main"):
            async with span("BUGGY_CHILD_depth_1"):
                transcript().info(
                    "BUG: I should render at depth 2 (same indent as "
                    "REFERENCE_correct_depth_2 above) but I render at depth 3 — "
                    "everything under BUGGY_CHILD is one level too deep."
                )
                async with span("BUGGY_GRANDCHILD_should_be_depth_2"):
                    transcript().info("BUGGY grandchild content.")
                    state = await generate(state)
        return state

    return solve


@task
def f02_4_unwrap_main_grandchild_depth() -> Task:
    return Task(
        name="F02.4_unwrap_main_grandchild_depth",
        dataset=[Sample(id="F02.4", input=DESC, target="n/a")],
        solver=nested_under_main(),
    )
