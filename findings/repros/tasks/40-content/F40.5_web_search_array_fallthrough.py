"""Repro for F40.5 — `web_search` record renderer returns an array → falls through to JSON.

The renderer matches on ``entry.name === "web_search"`` (i.e. a metadata KEY
named ``web_search``) with a value of shape ``{query, results: [{url, summary}]}``.
It returns ``{ rendered: ReactNode[] }``; the dispatcher then checks
``isValidElement(rendered)`` — false for arrays — and falls through to the
``JSON.stringify`` fallback.

Run:
    ./findings/repros/run.sh findings/repros/tasks/40-content/F40.5_web_search_array_fallthrough.py 40-content
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

# Exact shape RenderedContent.tsx:254-283 expects:
#   canRender: typeof entry.value === "object" && entry.name === "web_search"
#   render:    entry.value.query, entry.value.results[].{url,summary}
_WEB_SEARCH_RECORD = {
    "query": "F40.5 should render as a search-result list, NOT raw JSON",
    "results": [
        {
            "url": "https://example.com/result-1",
            "summary": "First result summary — if you can read this as a "
            "formatted link+summary pair, the bug is FIXED.",
        },
        {
            "url": "https://example.com/result-2",
            "summary": "Second result summary.",
        },
    ],
}

DESC = bug_description(
    finding_id="F40.5",
    title="web_search record renderer returns array → fails isValidElement → JSON fallback",
    where_to_look=(
        "**Transcript** tab → set the **Events** filter (top-right) to "
        "**Debug** → expand the **Init** span → in the **Sample** panel "
        "that appears, click its **Metadata** sub-tab → look at the "
        "`web_search` row."
    ),
    observed=(
        "The `web_search` row's value is a single `<span>` containing "
        "the raw `JSON.stringify(...)` of the record — one long line "
        'starting `{"query":"F40.5 should render...`. No links.'
    ),
    expected=(
        "A formatted block: a search-icon + the query text, followed by "
        "two clickable URL links each with its summary underneath. "
        "Fix: wrap the returned array in a `<Fragment>` or relax the "
        "dispatcher guard to `rendered !== undefined`."
    ),
    extra=(
        "**Note:** impact is minor — this `web_search` renderer is "
        "orphaned legacy code. Real web-search server-tool results are "
        "rendered by `ServerToolCall.tsx` and never reach "
        "`RenderedContent`; the only live path here is `MetaDataGrid` "
        "with a metadata key *literally* named `web_search`, which real "
        "evals don't produce. Source: "
        "`packages/inspect-components/src/content/RenderedContent.tsx:254` "
        "(renderer) and `:73` (the failing `isValidElement` guard)."
    ),
)


@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        return await generate(state)

    return solve


@task
def f40_5_web_search_array_fallthrough() -> Task:
    return Task(
        name="F40.5_web_search_array_fallthrough",
        dataset=[
            Sample(
                id="F40.5",
                input=DESC,
                target="n/a",
                # Key MUST be exactly "web_search" for canRender() to match.
                metadata={"web_search": _WEB_SEARCH_RECORD},
            )
        ],
        solver=repro_solver(),
    )
