"""Repro for F02.5 — reduceDepth recursion hard-codes `1`, breaking handoff unwrap.

Hand-emits a span/event tree matching what `unwrap_handoff` expects
(handoff span → tool span → ToolEvent + agent span → …). NOTE: this is
NOT the shape current `handoff()` actually emits — the real ToolEvent's
`span_id` is captured before the tool span opens, so `unwrap_handoff`
never matches on fresh logs. This repro forces the match by setting
`ToolEvent(span_id=TOOL)` so the buggy `reduceDepth` path is reachable.

Run:
    ./findings/repros/run.sh findings/repros/tasks/02-transform/F02.5_handoff_reducedepth_hardcoded.py 02-transform
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.event import (  # noqa: E402
    InfoEvent,
    SpanBeginEvent,
    SpanEndEvent,
    ToolEvent,
)
from inspect_ai.log import transcript  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402
from inspect_ai.util._span import current_span_id  # noqa: E402

DESC = bug_description(
    finding_id="F02.5",
    title="reduceDepth recursion hard-codes `1` → handoff agent span renders at SAME indent as its parent ToolEvent",
    where_to_look=(
        "Transcript tab (Default filter). Find the `TOOL: TRANSFER_TO_SUBAGENT` "
        "panel and compare its left edge to the "
        "`AGENT: AGENT_SPAN_SHOULD_BE_INDENTED_UNDER_TOOL_NOT_FLUSH_WITH_IT` "
        "panel directly below it."
    ),
    observed=(
        "The `AGENT: …` panel sits at the **same** left indent as "
        "`TOOL: TRANSFER_TO_SUBAGENT` (its parent) — they look like siblings. "
        "The agent's children (`INFO: REPRO`, `STEP: INNER_WORK_…`) then sit "
        "one indent step right of the agent."
    ),
    expected=(
        "The `AGENT: …` panel should be **one** indent level under the tool "
        "call, and its children one further level under that — a smooth "
        "+1 / +1 staircase."
    ),
    extra=(
        "`skipThisNode` (transform.ts) calls `reduceDepth(children, 2)` but "
        "`reduceDepth` always recurses with hard-coded `1`, so the first "
        "child level is over-reduced by one and the agent ends up flush "
        "with the tool.\n\n"
        "**Note:** impact is minor — `unwrap_handoff` does **not** fire on "
        "logs produced by current `handoff()` (the real `ToolEvent.span_id` "
        "is captured before the tool span opens, so the matcher fails). "
        "This repro hand-builds the matching shape; only legacy logs or a "
        "future `span_id` fix would hit this in practice."
    ),
)


@solver
def emit_handoff_tree() -> Solver:
    """Hand-roll the span tree a handoff() call would emit.

    Shape (matches `_call_tools.py:444-448` + `:546`):
        span(type="handoff")            ← removed by unwrap_handoff / skipThisNode
          span(type="tool")             ← collapsed into ToolEvent by unwrap_tools
            ToolEvent(agent="…")        ← becomes the new node at handoff's depth
            span(type="agent")          ← BUG: ends up at SAME depth as ToolEvent
              InfoEvent                 ← renders one indent right of agent
              span("inner")
                InfoEvent
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        parent = current_span_id()  # the solver span

        HOFF = "hoff_span"
        TOOL = "tool_span"
        AGENT = "agent_span"
        INNER = "inner_span"

        ev = transcript()._event
        # handoff span
        ev(SpanBeginEvent(id=HOFF, span_id=HOFF, parent_id=parent, type="handoff", name="subagent"))
        # tool span
        ev(SpanBeginEvent(id=TOOL, span_id=TOOL, parent_id=HOFF, type="tool", name="transfer_to_subagent"))
        # ToolEvent — must have .agent set so unwrap_handoff's 1-child branch matches
        ev(
            ToolEvent(
                id="call_1",
                function="transfer_to_subagent",
                arguments={},
                result="The subagent says hi.",
                agent="subagent",
                span_id=TOOL,
            )
        )
        # agent span — after unwrap this SHOULD be one level under the ToolEvent
        ev(
            SpanBeginEvent(
                id=AGENT,
                span_id=AGENT,
                parent_id=TOOL,
                type="agent",
                name="AGENT_span_SHOULD_BE_INDENTED_UNDER_tool_NOT_FLUSH_WITH_IT",
            )
        )
        ev(
            InfoEvent(
                source="repro",
                data="I am a child of the AGENT span above. The bug is that "
                "the AGENT span is flush with the TOOL panel instead of "
                "indented under it.",
                span_id=AGENT,
            )
        )
        ev(
            SpanBeginEvent(
                id=INNER,
                span_id=INNER,
                parent_id=AGENT,
                name="inner_work_SHOULD_BE_2_LEVELS_UNDER_tool",
            )
        )
        ev(InfoEvent(source="repro", data="deepest node", span_id=INNER))
        ev(SpanEndEvent(id=INNER, span_id=INNER))
        ev(SpanEndEvent(id=AGENT, span_id=AGENT))
        ev(SpanEndEvent(id=TOOL, span_id=TOOL))
        ev(SpanEndEvent(id=HOFF, span_id=HOFF))

        # one real generate so the solver span isn't empty after transforms
        state = await generate(state)
        return state

    return solve


@task
def f02_5_handoff_reducedepth_hardcoded() -> Task:
    return Task(
        name="F02.5_handoff_reducedepth_hardcoded",
        dataset=[Sample(id="F02.5", input=DESC, target="n/a")],
        solver=emit_handoff_tree(),
    )
