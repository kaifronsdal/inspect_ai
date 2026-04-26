"""Repro for F05.6 — ScoreEditEventView Metadata `data-name` nested inside Summary → never a tab.

Run:
    ./findings/repros/run.sh findings/repros/tasks/01-events/F05.6_score_edit_metadata_not_tab.py 01-events
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.event import ScoreEditEvent  # noqa: E402
from inspect_ai.log import ProvenanceData, transcript  # noqa: E402
from inspect_ai.scorer import (  # noqa: E402
    Score,
    ScoreEdit,
    Scorer,
    Target,
    accuracy,
    scorer,
)
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

DESC = bug_description(
    finding_id="F05.6",
    title="ScoreEditEventView Metadata is nested inside Summary → never appears as a tab",
    where_to_look=(
        "Transcript tab → **Edit Score** panel → look at the top-right of "
        "the header (where sub-tab pills go). Then compare with the "
        "**Score** panel directly below."
    ),
    observed=(
        "Edit Score panel has **NO sub-tab pills** (no tab strip rendered "
        "at all — the nav container is empty). The metadata grid "
        "(`edited_by`, `edit_reason`, …, `MARKER`) renders **inline below "
        "the Provenance section, unlabeled**. Contrast: the **Score** "
        "panel below DOES have `EXPLANATION | METADATA` pills."
    ),
    expected=(
        "Two sub-tab pills `SUMMARY | METADATA` in the Edit Score header, "
        "with the metadata grid on its own tab — mirroring how "
        "`ScoreEventView` puts metadata behind a `METADATA` pill."
    ),
    extra=(
        "**Note:** impact is minor — the metadata IS fully visible, just "
        "appended unlabeled instead of tabbed. No data loss; cosmetic / "
        "consistency only.\n\n"
        "Root cause: `EventPanel` discovers tabs by reading `data-name` on "
        "**direct children** and only renders the pill strip when there "
        "are ≥2. In `ScoreEditEventView` the `<div data-name=\"Metadata\">` "
        "is a child of `<div data-name=\"Summary\">`, not of `EventPanel`, "
        "so EventPanel sees one child → renders no pills."
    ),
)


@solver
def emit_edit_with_metadata() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        del generate
        transcript()._event(
            ScoreEditEvent(
                score_name="repro_scorer",
                edit=ScoreEdit(
                    value=0.5,
                    explanation="Edit with a metadata dict attached.",
                    metadata={
                        "edited_by": "human-reviewer-42",
                        "edit_reason": "partial credit",
                        "confidence": 0.9,
                        "MARKER": (
                            "⚠️ this metadata block should be behind its OWN "
                            "'Metadata' tab pill, not appended unlabeled below Provenance"
                        ),
                    },
                    provenance=ProvenanceData(
                        author="repro-harness",
                        reason="F05.6: metadata tab nesting",
                    ),
                ),
            )
        )
        return state

    return solve


@scorer(metrics=[accuracy()])
def repro_scorer() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        del state, target
        return Score(
            value=1.0,
            answer="x",
            metadata={"NOTE": "ScoreEventView correctly shows THIS as a Metadata tab"},
        )

    return score


@task
def f05_6_score_edit_metadata_not_tab() -> Task:
    return Task(
        name="F05.6_score_edit_metadata_not_tab",
        dataset=[Sample(id="F05.6", input=DESC, target="n/a")],
        solver=emit_edit_with_metadata(),
        scorer=repro_scorer(),
    )
