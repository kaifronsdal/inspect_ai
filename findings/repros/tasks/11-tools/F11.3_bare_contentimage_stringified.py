"""Repro for F11.3 — bare ContentImage tool result is JSON.stringify'd.

NOTE: Python's `call_tools` always list-wraps a bare Content* before writing
`ToolEvent.result` (`_call_tools.py:219-236`), so the natural execution path
never emits this shape. However the *log schema* (`ToolResult`) permits it,
and the viewer's `normalizeContent` mishandles it. We construct the
`ToolEvent` directly to produce the schema-valid-but-unwrapped shape.

Run:
    ./findings/repros/run.sh findings/repros/tasks/11-tools/F11.3_bare_contentimage_stringified.py 11-tools
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import TINY_PNG_DATA_URI, bug_description, emit_bug_banner  # noqa: E402

from inspect_ai import Task, task  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.event import ToolEvent  # noqa: E402
from inspect_ai.log import transcript  # noqa: E402
from inspect_ai.model import ContentImage  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402

DESC = bug_description(
    finding_id="F11.3",
    title="Bare ContentImage tool result renders as a key/value RecordTree instead of a plain <img>",
    where_to_look=(
        "**Transcript tab** → compare the two **Tool** panels below: "
        "`TOOL: SCREENSHOT_BARE` (bug) vs `TOOL: SCREENSHOT_LIST` (control). "
        "Both are already expanded — no clicking needed."
    ),
    observed=(
        "`screenshot_bare` output renders as a **key/value tree** — "
        "three rows `type: image` / `image: <tiny thumb>` / `detail: auto` "
        "(the image is still visible, just as the value of the `image:` row). "
        "`screenshot_list` (same image, wrapped in `[...]`) renders as a "
        "single clean `<img>` with no key/value rows."
    ),
    expected=(
        "Both render as a plain `<img>`. `normalizeContent` should wrap a "
        "single Content object in `[obj]` before dispatch."
    ),
    extra=(
        "`ToolCallView.tsx:normalizeContent` only checks `Array.isArray(output)`; "
        "a bare object falls to the `JSON.stringify(output)` branch, and the "
        "resulting JSON string is then re-parsed and shown via the RecordTree "
        "renderer — hence the key/value rows rather than raw JSON text.\n\n"
        "**Note:** impact is minor — this shape is **synthetic-only**. Real "
        "tool execution (`call_tools`, `_call_tools.py:219-236`) always "
        "list-wraps a bare `Content*` before writing `ToolEvent.result`, so "
        "in-tree code never produces it. Only hand-constructed `ToolEvent`s "
        "or external log writers can hit this path. Suggested one-line "
        "defensive fix: `else if (typeof output === \"object\" && \"type\" in "
        "output) return [output];`."
    ),
)


@solver
def emit_bare_image_tool_event() -> Solver:
    async def solve(state: TaskState, _generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        # Bare-object case (the bug):
        transcript()._event(
            ToolEvent(
                id="bare-img-001",
                function="screenshot_bare",
                arguments={},
                result=ContentImage(image=TINY_PNG_DATA_URI),  # NOT a list
            )
        )
        # List-wrapped control (renders correctly):
        transcript()._event(
            ToolEvent(
                id="list-img-001",
                function="screenshot_list",
                arguments={},
                result=[ContentImage(image=TINY_PNG_DATA_URI)],
            )
        )
        return state

    return solve


@task
def f11_3_bare_contentimage_stringified() -> Task:
    return Task(
        name="F11.3_bare_contentimage_stringified",
        dataset=[Sample(id="F11.3", input=DESC, target="n/a")],
        solver=emit_bare_image_tool_event(),
    )
