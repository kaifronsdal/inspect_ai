"""F02.5 — reduceDepth recursion hard-codes ``1``, breaking handoff unwrap.

After ``skipThisNode`` runs on a handoff span, the resulting ToolEvent and its
direct child (the agent span) end up at the **same** depth — visually the agent
sits flush with its parent tool call instead of indented under it.

Evidence: x-offset of the ``TOOL: TRANSFER_TO_SUBAGENT`` panel vs. the
``AGENT:`` panel directly below it. Same x → bug.
"""

from harness import VerifyResult, ViewerSession

BATCH = "02-transform"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F02.5", tab="transcript")
    session.wait_settled(ms=400)

    panels = session.page.evaluate(
        """() => {
            const out = [];
            document.querySelectorAll('[id^="event-panel-"]').forEach(p => {
                const r = p.getBoundingClientRect();
                const t = (p.innerText || '').split('\\n')[0].slice(0, 80);
                out.push([Math.round(r.x * 10) / 10, t]);
            });
            return out;
        }"""
    )
    pretty = "\n".join(f"x={x:7.1f}  {t}" for x, t in panels)

    tool = next(((x, t) for x, t in panels if t.startswith("TOOL:")), None)
    agent = next(
        ((x, t) for x, t in panels if t.startswith("AGENT:") and "INDENTED" in t),
        None,
    )

    if tool is None or agent is None:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=pretty,
            notes="Could not locate TOOL: / AGENT: panels in transcript.",
        )

    same_indent = abs(tool[0] - agent[0]) < 1.0
    if same_indent:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=pretty,
            notes=(
                f"TOOL panel at x={tool[0]}, AGENT panel (its child) at "
                f"x={agent[0]} — identical indent. skipThisNode → "
                f"reduceDepth(children, 2) over-reduces the first level."
            ),
        )

    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=pretty,
        notes=(
            f"AGENT panel (x={agent[0]}) is indented relative to TOOL "
            f"(x={tool[0]}) — depths look correct."
        ),
    )
