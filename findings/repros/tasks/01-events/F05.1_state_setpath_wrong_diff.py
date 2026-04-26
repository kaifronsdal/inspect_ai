"""Repro for F05.1 — StateEventView `setPath` only descends into newly-created keys → wrong diff.

Run:
    ./findings/repros/run.sh findings/repros/tasks/01-events/F05.1_state_setpath_wrong_diff.py 01-events
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

DESC = bug_description(
    finding_id="F05.1",
    title="StateEventView `setPath` brace bug → diff shows phantom top-level key",
    where_to_look=(
        "**⚠️ REQUIRES DEBUG FILTER** — Transcript tab → click the **Events: "
        "Default** dropdown (top right) → select **Debug** → scroll to the "
        "**State Updated** panel (below this INFO panel). Its body is a JSON "
        "diff tree — there are no sub-tabs."
    ),
    observed=(
        "The diff tree is `{ LOOK_HERE: { nested_key: <strike>BEFORE</strike> "
        "AFTER } }` — `LOOK_HERE` is rendered as the **top-level / root key**. "
        "The `metadata` key does **not appear anywhere** in the diff."
    ),
    expected=(
        "The change should appear at `metadata → LOOK_HERE → nested_key` "
        "(the actual JSON-Pointer path `/metadata/LOOK_HERE/nested_key`). "
        "There should be NO top-level `LOOK_HERE` key."
    ),
    extra=(
        "Root cause (`StateEventView.tsx:292-308`): `current = current[key]` is "
        "INSIDE the `if (!(key in current))` block. `initializeArrays()` runs "
        "first and creates `target.metadata = {LOOK_HERE: {}}`; then `setPath` "
        "sees `'metadata' in target`, skips the body, never advances `current`, "
        "and writes `target['LOOK_HERE']['nested_key']` at the wrong depth. "
        "Both before/after objects end up with an identical empty "
        "`metadata.LOOK_HERE = {}`, so jsondiffpatch elides `metadata` "
        "entirely.\n\n"
        "Same bug as F03.1 / F50.2.\n\n"
        "**To verify the raw op is correct:** sample JSON tab → search for "
        "`\"event\": \"state\"` → `changes[0].path` is "
        "`/metadata/LOOK_HERE/nested_key`."
    ),
)


@solver
def mutate_nested_metadata() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        del generate
        # Sample.metadata seeds state.metadata with {"LOOK_HERE": {"nested_key": "BEFORE"}}.
        # Mutating only the leaf produces a single JSON-patch op:
        #   {op: "replace", path: "/metadata/LOOK_HERE/nested_key",
        #    value: "AFTER (...)", replaced: "BEFORE (...)"}
        # which is a 3-segment path → triggers the setPath brace bug.
        state.metadata["LOOK_HERE"]["nested_key"] = (
            "AFTER (this value should appear under metadata → LOOK_HERE → nested_key)"
        )
        return state

    return solve


@task
def f05_1_state_setpath_wrong_diff() -> Task:
    return Task(
        name="F05.1_state_setpath_wrong_diff",
        dataset=[
            Sample(
                id="F05.1",
                input=DESC,
                target="n/a",
                metadata={
                    "LOOK_HERE": {
                        "nested_key": (
                            "BEFORE (this value should appear under "
                            "metadata → LOOK_HERE → nested_key)"
                        ),
                    },
                },
            )
        ],
        solver=mutate_nested_metadata(),
    )
