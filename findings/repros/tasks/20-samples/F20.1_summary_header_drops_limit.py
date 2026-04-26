"""Repro for F20.1 — SampleSummaryView drops limit/error/time for SampleSummary inputs.

Run:
    ./findings/repros/run.sh findings/repros/tasks/20-samples/F20.1_summary_header_drops_limit.py 20-samples
"""

from __future__ import annotations

import sys
from pathlib import Path

# make findings/repros/_common.py importable
sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

DESC = bug_description(
    finding_id="F20.1",
    title="SampleSummaryView header drops `limit` / `error` / `time` fields",
    where_to_look=(
        "Open this sample → look at the **summary header row** directly "
        "above the Transcript / Messages / Scoring tabs."
    ),
    observed=(
        "The header shows only **ID / Input / Target** — there is **no Limit "
        "column** and **no Time column**, even though this sample hit "
        "`message_limit=2` (see the *Message Limit Exceeded* event below, "
        "and `limit.type: \"message\"` in the JSON tab)."
    ),
    expected=(
        "Header should include a **Limit** column showing `message` (and "
        "ideally total/working time). `SampleSummary` carries "
        "`limit?: string` but `resolveSample()` only reads it when "
        "`isEvalSample(sample)` is true — which it never is, because the "
        "caller passes a `SampleSummary`."
    ),
    extra=(
        "Source asymmetry: the multi-sample list view "
        "(`list/columns.tsx`) reads `limit` directly off `SampleSummary` "
        "with no guard, while this detail header gates the same field "
        "behind `isEvalSample()` (`SampleSummaryView.tsx:76`). This repro "
        "is single-sample so there is no list grid to compare against — "
        "verify the data exists via the JSON tab."
    ),
)


@solver
def hit_message_limit() -> Solver:
    """Generate in a loop so the message_limit fires."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        # message_limit=2 → after the first generate (user + assistant = 2 msgs)
        # the second generate trips the limit and the sample records
        # EvalSampleLimit(type="message", limit=2).
        for _ in range(5):
            state = await generate(state)
        return state

    return solve


@task
def f20_1_summary_header_drops_limit() -> Task:
    return Task(
        name="F20.1_summary_header_drops_limit",
        dataset=[Sample(id="F20.1", input=DESC, target="n/a")],
        solver=hit_message_limit(),
        message_limit=2,
    )
