"""Repro for F05.11 — SampleInitEventView omits `sample.sandbox` and `sample.id`.

Run:
    ./findings/repros/run.sh findings/repros/tasks/01-events/F05.11_sample_init_omits_sandbox_id.py 01-events
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
    finding_id="F05.11",
    title="SampleInitEventView never shows `sample.sandbox` or `sample.id`",
    where_to_look=(
        "Transcript tab → set the **Events** filter (top right) to **Debug** "
        "→ expand the **Init** span (first row) → look at the **Sample** "
        "panel's **SAMPLE** sub-tab"
    ),
    observed=(
        "The SAMPLE sub-tab shows section headings **Files** / **Setup** / "
        "**Target** (and a separate **Metadata** sub-tab), but **no section "
        "for `sandbox`** (which is `local` here) and **no section for `id`** "
        "(`DISTINCTIVE-SAMPLE-ID-⚠️-F05.11`)."
    ),
    expected=(
        "A **Sandbox** section showing `type: local` (the per-sample "
        "`SandboxEnvironmentSpec`). These are the only structural `Sample` "
        "fields the view omits."
    ),
    extra=(
        "**Note:** impact is minor — `sample.id` is already displayed in the "
        "dialog header (top right) and in the **ID** column of the summary "
        "row above the tabs, so only `sample.sandbox` is genuinely missing, "
        "and per-sample sandbox overrides are uncommon.\n\n"
        "Verify the data is present via the sample **JSON** tab → `events` → "
        "the `sample_init` event → `sample.sandbox` is "
        '`{type: "local", config: null}` and `sample.id` is the distinctive '
        "string.\n\n"
        "(A `local` sandbox is used so no Docker is required. The setup "
        "script and file are included so the panel has visible Files/Setup "
        "sections for contrast.)"
    ),
)


@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        return await generate(state)

    return solve


@task
def f05_11_sample_init_omits_sandbox_id() -> Task:
    sample = Sample(
        id="DISTINCTIVE-SAMPLE-ID-⚠️-F05.11",
        input=DESC,
        target="n/a",
        sandbox="local",
        files={"hello.txt": "hello from F05.11 — Files IS shown; Sandbox is NOT"},
        setup="echo 'setup script — Setup IS shown; Sandbox is NOT'",
        metadata={"finding_id": "F05.11"},
    )
    return Task(
        name="F05.11_sample_init_omits_sandbox_id",
        dataset=[sample],
        solver=repro_solver(),
    )
