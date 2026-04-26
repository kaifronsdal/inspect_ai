"""Repro for F10.4 — citation superscript numbers don't match the footnote list.

Run:
    ./findings/repros/run.sh findings/repros/tasks/10-chat/F10.4_citation_numbering_mismatch.py 10-chat
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.model import (  # noqa: E402
    ChatMessageAssistant,
    ContentText,
    UrlCitation,
)
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

DESC = bug_description(
    finding_id="F10.4",
    title="Citation superscript numbers don't match the footnote list",
    where_to_look=(
        "**Messages tab** → the assistant message (turn 2). "
        "Compare the inline superscript numbers in the text "
        "against the numbered citation list directly below it."
    ),
    observed=(
        "Inline superscripts in BLOCK 2 restart from 1 — the four "
        "sups read ¹ ² ¹ ² — while the citation list below is "
        "numbered 1–4. Footnotes 3 and 4 (CITE-C, CITE-D) have no "
        "matching inline ³ or ⁴."
    ),
    expected=(
        "Inline superscripts run 1, 2, 3, 4 across both blocks "
        "and line up 1-for-1 with footnotes CITE-A … CITE-D."
    ),
    extra=(
        "Each citation title is self-labelling (e.g. "
        "`CITE-C (should be #3)`) so any mismatch is obvious. The "
        "inline sups are plain numbers with no anchor/link — the "
        "number is the *only* way to correlate text with source. "
        "Root cause: superscripts are numbered per-text-block in "
        "`MessageContent.tsx`; the list in `MessageCitations.tsx` "
        "is numbered over the flattened array."
    ),
)


def cite(label: str, url_slug: str, span: tuple[int, int]) -> UrlCitation:
    """Build a *positional* UrlCitation (cited_text is a [start,end] span).

    The viewer's superscript generator only resets per-block for *positional*
    cites — non-positional end-cites share `++citeCount` across coalesced
    blocks and number correctly. So `cited_text` MUST be a tuple, not a string.
    """
    return UrlCitation(
        title=f"[{label}] Expected footnote = {label}",
        url=f"https://example.invalid/{url_slug}",
        cited_text=span,
    )


@solver
def inject_cited_assistant() -> Solver:
    async def solve(state: TaskState, _generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        # TWO ContentText blocks, each with TWO citations.
        # The footnote list flatMaps to [A, B, C, D] → numbered 1..4.
        # The inline <sup> generator resets per text-block (and uses
        # positionalCites.length - i for positional cites), so block 2
        # restarts at 1 instead of continuing at 3.
        state.messages.append(
            ChatMessageAssistant(
                model="mockllm/model",
                source="generate",
                content=[
                    ContentText(
                        # spans:    [0..............................39][40........61]
                        text=(
                            "BLOCK 1: Paris is the capital of France."
                            " It sits on the Seine."
                            " ← inline superscripts should read 1, 2."
                        ),
                        citations=[
                            cite("CITE-A (should be #1)", "cite-a", (0, 40)),
                            cite("CITE-B (should be #2)", "cite-b", (40, 62)),
                        ],
                    ),
                    ContentText(
                        text=(
                            "BLOCK 2: Berlin is the capital of Germany."
                            " It sits on the Spree."
                            " ← inline superscripts should read 3, 4 "
                            "(NOT 1, 2 again)."
                        ),
                        citations=[
                            cite("CITE-C (should be #3)", "cite-c", (0, 42)),
                            cite("CITE-D (should be #4)", "cite-d", (42, 64)),
                        ],
                    ),
                ],
            )
        )
        return state

    return solve


@task
def f10_4_citation_numbering_mismatch() -> Task:
    return Task(
        name="F10.4_citation_numbering_mismatch",
        dataset=[Sample(id="F10.4", input=DESC, target="n/a")],
        solver=inject_cited_assistant(),
    )
