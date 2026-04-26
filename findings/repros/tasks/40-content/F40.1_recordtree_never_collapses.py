"""Repro for F40.1 — RecordTree default-collapse logic never executes.

Creates deeply-nested + wide sample metadata. ``RecordTree`` is supposed to
collapse nodes whose ``depth >= defaultExpandLevel`` or ``childCount > 5`` on
mount, but the guard ``if (collapsedIds) return;`` always short-circuits
because ``useCollapsibleIds`` returns ``{}`` (truthy), never ``undefined``.

Run:
    ./findings/repros/run.sh findings/repros/tasks/40-content/F40.1_recordtree_never_collapses.py 40-content
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.scorer import (  # noqa: E402
    Score,
    Scorer,
    Target,
    accuracy,
    scorer,
)
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

# 7 levels deep — well past any plausible defaultExpandLevel
_DEEP = {
    "L1": {
        "L2": {
            "L3": {
                "L4": {
                    "L5": {
                        "L6": {
                            "L7_leaf": (
                                "DEEP — this branch should be COLLAPSED by "
                                "default (depth >= defaultExpandLevel)"
                            ),
                        }
                    }
                }
            }
        }
    },
    # > 5 children — should also be collapsed by default (childCount > 5)
    "wide_branch": {
        f"child_{i:02d}": f"one of 12 siblings — parent should be collapsed"
        for i in range(12)
    },
}

DESC = bug_description(
    finding_id="F40.1",
    title="RecordTree default-collapse never fires — always fully expanded",
    where_to_look=(
        "Open the sample → **Metadata** tab → scroll to the **METADATA** "
        "card. Also: **Transcript** tab → in the **Score** event, click the "
        "**Metadata** sub-tab pill."
    ),
    observed=(
        "The `deep_tree.L1.L2.L3.L4.L5.L6.L7_leaf` branch is fully "
        "expanded on first render, and so is `wide_branch` (12 children). "
        "No node is collapsed by default."
    ),
    expected=(
        "Branches deeper than `defaultExpandLevel` and branches with "
        ">5 children should mount **collapsed**. The effect that "
        "computes `defaultCollapsedIds` is dead because "
        "`useCollapsibleIds` returns `{}` (truthy) instead of "
        "`undefined`, so `if (collapsedIds) return;` always early-exits."
    ),
)


@solver
def stuff_metadata() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        state = await generate(state)
        # state.metadata feeds the sample-dialog Metadata tab (RecordTree)
        state.metadata["deep_tree"] = _DEEP
        return state

    return solve


@scorer(metrics=[accuracy()])
def metadata_scorer() -> Scorer:
    """Score with the same nested metadata so the ScoreEvent's RecordTree
    (Transcript → Score event → Metadata) also exhibits the bug."""

    async def score(_state: TaskState, _target: Target) -> Score:
        return Score(value=1.0, answer="x", metadata={"deep_tree": _DEEP})

    return score


@task
def f40_1_recordtree_never_collapses() -> Task:
    return Task(
        name="F40.1_recordtree_never_collapses",
        dataset=[
            Sample(
                id="F40.1",
                input=DESC,
                target="n/a",
                # SampleInit Metadata tab → MetaDataGrid path
                metadata={"deep_tree": _DEEP},
            )
        ],
        solver=stuff_metadata(),
        scorer=metadata_scorer(),
    )
