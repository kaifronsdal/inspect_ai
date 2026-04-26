"""Repro for F20.4 — Scoring tab uses a fresh single-value descriptor ≠ list/header.

Run:
    ./findings/repros/run.sh findings/repros/tasks/20-samples/F20.4_scoring_tab_descriptor_diverges.py 20-samples
"""

from __future__ import annotations

import sys
from pathlib import Path

# make findings/repros/_common.py importable
sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.scorer import Score, Scorer, Target, accuracy, scorer  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

DESC = bug_description(
    finding_id="F20.4",
    title="Scoring tab builds a fresh single-value descriptor ≠ list/header descriptor",
    where_to_look=(
        "Open sample `should_be_C` → click the **Scoring** tab. Compare three "
        "renderings of the same score: (1) the **SCORE** column in the sample "
        "header (top-right, above the tab bar), (2) the **SCORE** column in the "
        "Scoring tab's scorer grid below, (3) back out to the **Samples** list "
        "and check its **SCORE** column. Repeat for `should_be_I`."
    ),
    observed=(
        "For `should_be_C` / `should_be_I`: the sample header and the Samples "
        "list render `C` / `I` as **plain black text** (categorical descriptor "
        "— full value-set `{C, I, X}` contains a non-pass/fail value). But the "
        "**Scoring tab** grid renders the same `C` / `I` as a **green / red "
        "circle badge** (pass/fail descriptor — it categorises from the single "
        "value `[C]` or `[I]` only). Header and badge are visible side-by-side."
    ),
    expected=(
        "All three views should pick the same descriptor from the same "
        "value-set and therefore render the score identically."
    ),
    extra=(
        "Root cause: `SampleScores.tsx` calls "
        "`getScoreDescriptorForValues([scoreData.value], [typeof scoreData.value])` "
        "instead of reusing `evalDescriptor.score(...)`. The categorizer ladder "
        "is value-**set** sensitive: `{C, I, X}` → categorical (plain `String`); "
        "`{C}` alone → passFail (badge). Sample `should_be_X` happens to match "
        "(plain `X` everywhere) because `[X]` falls through passFail too."
    ),
)


@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        return await generate(state)

    return solve


@scorer(metrics=[accuracy()])
def divergent_scorer() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        # target encodes the score value: "C", "I", or "X"
        return Score(value=target.text, answer=target.text)

    return score


@task
def f20_4_scoring_tab_descriptor_diverges() -> Task:
    samples = [
        Sample(id="should_be_C", input=DESC, target="C"),
        Sample(id="should_be_I", input=DESC, target="I"),
        Sample(id="should_be_X", input=DESC, target="X"),
    ]
    return Task(
        name="F20.4_scoring_tab_descriptor_diverges",
        dataset=samples,
        solver=repro_solver(),
        scorer=divergent_scorer(),
    )
