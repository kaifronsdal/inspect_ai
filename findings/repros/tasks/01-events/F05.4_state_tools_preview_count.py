r"""Repro for F05.4 — StateEvent "Tools" preview never fires when ≥2 tools added at once.

This file produces **two** State Updated events in one sample so the bug is
self-evident by side-by-side comparison:

  1. **CONTROL** — adds 1 tool  → 1× ``add /tools/0`` op → preview FIRES
                   (panel has **Summary / Diff** sub-tab pills)
  2. **BUG**     — adds 3 tools → 3× ``add /tools/N`` ops → preview SKIPPED
                   (panel shows raw diff only, no sub-tab pills)

The "Tools preview" is what ``generatePreview`` in ``StateEventView.tsx``
returns when a StateEvent's changes match the ``add_tools`` change-type
signature in ``StateEventRenderers.tsx`` — a friendly grid of
``tool_name(arg, …)`` chips under a **Tools** label, rendered as the
**Summary** tab. Without it the panel has only one child (the raw
jsondiffpatch view) and therefore no tab pills at all.

Synthetic ``StateEvent``\ s are pushed directly via ``transcript()._event()``
(same approach as F01.2) so both events are siblings inside one solver span —
using ``solver=[a, b]`` would wrap each in an agent-card and change the
rendering path.

Run:
    ./findings/repros/run.sh findings/repros/tasks/01-events/F05.4_state_tools_preview_count.py 01-events
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai._util.json import JsonChange  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.event._state import StateEvent  # noqa: E402
from inspect_ai.log._transcript import transcript  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

DESC = bug_description(
    finding_id="F05.4",
    title='StateEvent "Tools" preview never fires when ≥2 tools added in one event',
    where_to_look=(
        "Transcript tab → switch the **Events** filter to **Debug** "
        "(state events are hidden by default). There are TWO **State "
        "Updated** events. Expand both."
    ),
    observed=(
        "**Inconsistent.** The 1-tool event (CONTROL) shows "
        "**Summary / Diff** sub-tab pills — preview fired. The "
        "3-tool event (BUG) shows only the raw JSON diff with no "
        "sub-tab pills — preview skipped — even though it is the "
        "same kind of state change."
    ),
    expected=(
        "Both events should render the friendly **Tools** preview "
        "(a `tool_name(arg, …)` chip per added tool under a "
        "**Tools** label) as the Summary tab."
    ),
    extra=(
        "Root cause: `generatePreview` (`StateEventView.tsx:119-169`) "
        "checks `matchingOps === requiredMatchCount`. The `add_tools` "
        "signature (`StateEventRenderers.tsx:64-74`) has ONE pattern "
        "(`/tools/(\\d+)`), so `requiredMatchCount = 1`; three adds "
        "give `matchingOps = 3`; `3 !== 1` → no preview.\n\n"
        "Fix: `matchingOps >= requiredMatchCount`, or track "
        "per-pattern satisfaction.\n\n"
        "**NB** the 1-tool Summary tab body is itself **empty** (no "
        "tool chips) — that is the *separate* F05.1 `setPath` brace "
        "bug corrupting `resolvedState.tools`. The mere **presence** "
        "of the Summary tab pill is what proves the preview fired "
        "here; don't expect content in it.\n\n"
        "**Note:** impact is minor — state events are hidden behind "
        "the Debug filter; the Summary body the 3-tool case is "
        "missing would be blank anyway until F05.1 is fixed; and the "
        "common `use_tools()` path (which also replaces "
        "`tool_choice`) hits the separate `use_tools` signature "
        "where the preview *does* fire. Cosmetic, one-character fix."
    ),
)


def _tool_def(name: str, arg: str) -> dict[str, object]:
    """A minimal serialised ToolInfo dict (what ``state_jsonable`` would emit)."""
    return {
        "name": name,
        "description": f"{name} — synthetic tool for F05.4 repro",
        "parameters": {
            "type": "object",
            "properties": {arg: {"type": "integer", "description": "an integer"}},
            "required": [arg],
        },
    }


@solver
def two_state_events() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        del generate

        # ── CONTROL: 1 tool added ───────────────────────────────────────────
        # matchingOps = 1, requiredMatchCount = 1 → preview FIRES.
        transcript().info(
            "▼ **CONTROL (1 tool)** — the **State Updated** event below adds "
            "exactly one tool. `generatePreview` matches the `add_tools` "
            "signature (`matchingOps == requiredMatchCount == 1`) so the panel "
            "gets a **Summary** tab in addition to **Diff**."
        )
        transcript()._event(
            StateEvent(
                changes=[
                    JsonChange(op="add", path="/tools/0", value=_tool_def("alpha_tool", "x")),
                ]
            )
        )

        # ── BUG: 3 tools added ──────────────────────────────────────────────
        # matchingOps = 3, requiredMatchCount = 1 → preview SKIPPED.
        transcript().info(
            "▼ **BUG (3 tools)** — the **State Updated** event below adds "
            "three tools in one go. Same op pattern × 3 → "
            "`matchingOps(3) !== requiredMatchCount(1)` → no Summary tab, "
            "only the raw JSON diff. **Same operation, inconsistent rendering.**"
        )
        transcript()._event(
            StateEvent(
                changes=[
                    JsonChange(op="add", path="/tools/0", value=_tool_def("beta_tool", "x")),
                    JsonChange(op="add", path="/tools/1", value=_tool_def("gamma_tool", "y")),
                    JsonChange(op="add", path="/tools/2", value=_tool_def("delta_tool", "z")),
                ]
            )
        )

        return state

    return solve


@task
def f05_4_state_tools_preview_count() -> Task:
    return Task(
        name="F05.4_state_tools_preview_count",
        dataset=[Sample(id="F05.4", input=DESC, target="n/a")],
        solver=two_state_events(),
    )
