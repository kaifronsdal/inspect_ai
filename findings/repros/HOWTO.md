# HOWTO: build a viewer-bug repro `.eval` file

You are building **minimal** Inspect tasks that, when run against `mockllm/model`,
produce a `.eval` log file demonstrating a specific viewer bug. Someone opening
that log in `inspect view` should be able to **see the bug** and **read what they
are looking for** in the first user message.

> **HARD RULE:** `mockllm/model` only. Never call anthropic / openai / google /
> any real provider. Every snippet below uses mockllm or pure Python construction.

---

## 1. Directory layout & naming

```
findings/repros/
├── _common.py                # shared helpers – import from every task file
├── run.sh                    # wrapper around `inspect eval` that strips bad env
├── HOWTO.md                  # this file
├── README.md                 # index of all repros (final agent fills the table)
├── NOT_REPRODUCIBLE.md       # findings that cannot be shown via a .eval file
├── tasks/
│   ├── example/              # worked example – copy from here
│   │   └── F01.3_score_edit_unchanged_sentinel.py
│   ├── 01-events/            # batch dirs – one per agent
│   ├── 02-transform/
│   ├── 10-chat/
│   ├── 11-tools/
│   ├── 20-samples/
│   ├── 30-loglist/
│   ├── 40-content/
│   └── 90-cross/
└── logs/
    ├── example/              # one log dir per batch, mirrors tasks/
    ├── 01-events/
    └── ...
```

**File naming:** `tasks/<batch>/<finding_id>_<slug>.py`
e.g. `tasks/01-events/F01.3_score_edit_unchanged_sentinel.py`

- `finding_id` — exactly as in `findings/NN-*.md` (e.g. `F01.3`, `F11.12`).
- `slug` — short snake-case summary, ≤ 5 words.
- One file per finding. If two findings share a repro, symlink or note it in
  the second file's docstring and `bug_sample(extra=...)`.

**Batch directories** (create only the one you own):

| Dir            | Findings area                                    |
|----------------|--------------------------------------------------|
| `01-events`    | Transcript event-view rendering (Score, Info, …) |
| `02-transform` | Transform pipeline / outline / tree              |
| `10-chat`      | Chat message rendering                           |
| `11-tools`     | Tool call / tool output rendering                |
| `20-samples`   | Sample list, sample dialog, scores tab           |
| `30-loglist`   | Log listing, header, tabs, multi-log             |
| `40-content`   | Markdown / JSON / image / ANSI content renderers |
| `90-cross`     | Cross-cutting / formatting / misc                |

---

## 2. Running a repro

Always use the wrapper script — it un-sets AISI-platform env vars that break
the local editable install:

```bash
cd /home/ubuntu/GitHub/inspect_ai
./findings/repros/run.sh findings/repros/tasks/<batch>/<file>.py <batch>
```

which expands to:

```bash
cd /home/ubuntu/GitHub/inspect_ai
env -u UV_EXCLUDE_NEWER -u INSPECT_TELEMETRY -u INSPECT_API_KEY_OVERRIDE -u INSPECT_REQUIRED_HOOKS \
  uv run --frozen inspect eval findings/repros/tasks/<batch>/<file>.py \
    --model mockllm/model \
    --log-dir findings/repros/logs/<batch> \
    --log-format eval \
    --display plain
```

**Verify:** `ls -l findings/repros/logs/<batch>/` — file should exist and be
> 1 KB. If it's 0 bytes or missing, the task crashed; scroll up for the
traceback.

**View it:**

```bash
env -u UV_EXCLUDE_NEWER uv run --frozen inspect view --log-dir findings/repros/logs/<batch>
```

---

## 3. The bug-description block (REQUIRED)

Every repro **must** embed a human-readable description as the sample's input
(first user message), so it is the first thing visible in both the *Messages*
and *Transcript* tabs. Use the helper:

```python
from _common import bug_sample

sample = bug_sample(
    finding_id="F01.3",
    title="ScoreEditEventView renders the literal 'UNCHANGED' sentinel",
    where_to_look="Transcript tab → expand the **Score Edit** event",
    observed="Value row shows the string `UNCHANGED` styled like a real score.",
    expected="Value row should be hidden — the edit did not change `value`.",
    extra="Optional free-form markdown with extra context.",
)
```

This renders in the viewer as:

> ## VIEWER BUG REPRO — F01.3
> **ScoreEditEventView renders the literal 'UNCHANGED' sentinel**
>
> | | |
> |---|---|
> | **Where to look** | Transcript tab → expand the **Score Edit** event |
> | **Observed (bug)** | Value row shows the string `UNCHANGED` … |
> | **Expected** | Value row should be hidden … |

If your repro **needs** a specific input shape (e.g. a `list[ChatMessage]` with
images, or 50 samples), build the `Sample` by hand, put `bug_description(...)`
in a `ChatMessageSystem` or `Sample.metadata["bug"]`, and make sure it is
visible *somewhere* obvious in the viewer.

### 3a. Bug banner (REQUIRED)

`Sample.input` is **truncated** in the sample-dialog header, and the
`SampleInit` event that carries it is **filtered out** of the Transcript tab by
default (`kDefaultExcludeEvents`). So a user opening your repro on the
Transcript tab won't see the description unless they switch filters.

Fix: emit the description as an `InfoEvent` at the very top of every solver.
`info` events are *not* in the default exclude list, `InfoEventView` renders
string data as markdown, and the panel is expanded by default — so the banner
is the first readable thing in the transcript.

```python
from _common import bug_description, emit_bug_banner

DESC = bug_description(finding_id="F01.2", title=..., ...)   # module-level

@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)          # ← MUST be the first line
        ...
```

`DESC` is reused as `Sample(input=DESC, ...)` so the (truncated) header still
shows the finding id. If your task has **no custom solver** (e.g. it just uses
`generate()` or `react(...)`), wrap it:

```python
from inspect_ai.solver import chain, generate

solver=chain(banner_solver(), generate())   # banner_solver just calls emit_bug_banner(DESC)
```

---

## 4. Copy-paste task template

Start every repro from this skeleton (it is the cleaned-up `example/F01.3_*.py`):

```python
"""Repro for F##.# — <one-line title>.

Run:
    ./findings/repros/run.sh findings/repros/tasks/<batch>/<this_file>.py <batch>
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
    finding_id="F00.0",
    title="...",
    where_to_look="...",
    observed="...",
    expected="...",
)


@solver
def repro_solver() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)  # ← always first line
        # Do whatever is needed to put the bug-triggering data into the log.
        # Often just:
        state = await generate(state)
        # ... then mutate state / emit events / etc.
        return state

    return solve


@task
def f00_0_short_slug() -> Task:
    return Task(
        name="F00.0_short_slug",
        dataset=[Sample(id="F00.0", input=DESC, target="n/a")],
        solver=repro_solver(),
        # scorer=...,   # optional – only if the bug involves scoring
        # model=...,    # optional – see §5 for scripted mockllm outputs
    )
```

---

## 5. Controlling what the "model" says — `mockllm` patterns

`mockllm/model` (`src/inspect_ai/model/_providers/mockllm.py`) returns
`"Default output from mockllm/model"` forever **unless** you give it a
`custom_outputs` iterable. Each call to `generate()` consumes one item.

### 5a. Pass scripted outputs via `Task(model=...)`

The task-level `model` **overrides** the CLI `--model`, so this is safe:

```python
from inspect_ai.model import get_model, ModelOutput

MOCK = "mockllm/model"

@task
def my_repro() -> Task:
    outputs = [
        ModelOutput.for_tool_call(MOCK, "addition", {"x": 1, "y": 1}),
        ModelOutput.from_content(MOCK, "The answer is 2."),
    ]
    return Task(
        ...,
        solver=react(tools=[addition()]),          # 2 generate() calls
        model=get_model(MOCK, custom_outputs=outputs),
    )
```

> **Gotcha:** `custom_outputs` is consumed as an iterator across **all** samples
> and **all** generate calls. If it runs out, mockllm raises
> `ValueError: custom_outputs ran out of values`. Count your turns. For an
> agent loop, the final output must have `stop_reason != "tool_calls"` (e.g.
> a plain `from_content(...)` or a `submit` tool call) or the loop won't end.

### 5b. `ModelOutput` constructors (`src/inspect_ai/model/_model_output.py`)

```python
from inspect_ai.model import ModelOutput, ChatMessageAssistant
from inspect_ai.model import ContentText, ContentReasoning, ContentImage
from inspect_ai.tool import ToolCall

# Plain text
ModelOutput.from_content("mockllm/model", "hello", stop_reason="stop")

# list[Content] — reasoning + text in one assistant turn
ModelOutput.from_content(
    "mockllm/model",
    [
        ContentReasoning(reasoning="internal chain of thought…"),
        ContentText(text="visible answer"),
    ],
)

# Single tool call (auto-generates id, sets stop_reason="tool_calls")
ModelOutput.for_tool_call(
    "mockllm/model",
    tool_name="bash",
    tool_arguments={"cmd": "ls -la"},
    tool_call_id="call_001",          # optional, else random
    content="I'll list the files.",   # optional assistant text
)

# Full control: multi-tool-call, custom content, etc.
ModelOutput.from_message(
    ChatMessageAssistant(
        model="mockllm/model",
        source="generate",
        content=[ContentReasoning(reasoning="…"), ContentText(text="ok")],
        tool_calls=[
            ToolCall(id="c1", function="read",  arguments={"path": "/a"}),
            ToolCall(id="c2", function="write", arguments={"path": "/b", "data": "x"}),
        ],
    ),
    stop_reason="tool_calls",
)
```

`_common.py` wraps these as `mock_text()`, `mock_tool_call()`, `mock_assistant()`.

### 5c. Making a tool actually execute (→ `ToolEvent`)

To get a real `ToolEvent` + `ChatMessageTool` in the log you need (a) a tool,
(b) a solver that calls it, and (c) a mockllm output that requests it:

```python
from inspect_ai.agent import react
from inspect_ai.tool import Tool, tool

@tool
def addition() -> Tool:
    async def execute(x: int, y: int) -> str:
        """Add two numbers.

        Args:
            x: first
            y: second
        """
        return str(x + y)
    return execute

outputs = [
    ModelOutput.for_tool_call("mockllm/model", "addition", {"x": 1, "y": 1}),
    ModelOutput.for_tool_call("mockllm/model", "submit", {"answer": "2"}),
]
Task(
    ...,
    solver=react(tools=[addition()]),
    model=get_model("mockllm/model", custom_outputs=outputs),
)
```

For a **failing** tool call (→ `ChatMessageTool.error`), either raise inside the
tool body, or have mockllm call a tool that doesn't exist, or call an existing
tool with wrong-typed args.

---

## 6. Constructing chat messages & content directly

Many viewer bugs are about rendering a specific message shape. You don't need
the model to *produce* it — just append it to `state.messages` in a solver:

```python
from inspect_ai.model import (
    ChatMessageSystem, ChatMessageUser, ChatMessageAssistant, ChatMessageTool,
    ContentText, ContentImage, ContentReasoning,
)
from inspect_ai.tool import ToolCall, ToolCallError
from _common import TINY_PNG_DATA_URI

@solver
def inject_messages() -> Solver:
    async def solve(state: TaskState, _generate: Generate) -> TaskState:
        state.messages.extend([
            ChatMessageSystem(content="system prompt with **markdown**"),
            ChatMessageUser(content=[
                ContentText(text="look at this:"),
                ContentImage(image=TINY_PNG_DATA_URI),
            ]),
            ChatMessageAssistant(
                model="mockllm/model",
                content=[
                    ContentReasoning(reasoning="step 1 … step 2 …"),
                    ContentText(text="done."),
                ],
                tool_calls=[ToolCall(id="t1", function="bash", arguments={"cmd": "ls"})],
            ),
            ChatMessageTool(
                tool_call_id="t1",
                function="bash",
                content="file1\nfile2",
                error=ToolCallError(type="timeout", message="exceeded 30s"),
            ),
        ])
        return state
    return solve
```

> **Gotcha:** `ToolCallError.type` is a `Literal` — valid values are
> `"parsing" | "timeout" | "unicode_decode" | "permission" | "file_not_found" |
> "is_a_directory" | "limit" | "approval" | "unknown"`.

> **Gotcha:** mutating `state.messages` inside a solver automatically emits a
> `StateEvent` with the JSON-patch diff — you do **not** need to emit one by
> hand. Same for `state.metadata`, `state.output`, etc.

---

## 7. Emitting transcript events directly

For bugs in event views that are hard to trigger "naturally", push the event
straight onto the transcript:

```python
from inspect_ai.log import transcript
from inspect_ai.util import span, store
from inspect_ai.event import InfoEvent, ScoreEditEvent  # etc.

# InfoEvent (public API)
transcript().info({"key": "value", "n": 42}, source="my-repro")
transcript().info("plain string is also fine")

# Span begin/end + StoreEvent (store changes inside a span are auto-recorded)
async with span("my-phase", type="custom"):
    store().set("counter", 1)
    store().set("blob", {"nested": [1, 2, 3]})
# → SpanBeginEvent, StoreEvent (with JSON-patch), SpanEndEvent

# Any event type — private but stable, used throughout the test suite
transcript()._event(InfoEvent(source="x", data={"raw": True}))
```

`ScoreEvent` is emitted automatically by any `@scorer`. For `ScoreEditEvent`
see the worked example `tasks/example/F01.3_*.py`.

```python
from inspect_ai.scorer import Score, Scorer, Target, accuracy, scorer

@scorer(metrics=[accuracy()])
def trivial_scorer() -> Scorer:
    async def score(_state: TaskState, _target: Target) -> Score:
        return Score(value=1.0, answer="x", explanation="…",
                     metadata={"extra": [1, 2, 3]})
    return score
```

`LoggerEvent`: just `import logging; logging.getLogger(__name__).warning("…")`
inside a solver — Inspect captures it.

`ErrorEvent` / `SampleLimitEvent`: raise inside a solver with
`Task(fail_on_error=False)`, or set `Task(message_limit=1)` and exceed it.

---

## 8. Multi-log repros (e.g. F30.x metric collision)

Some log-listing bugs need ≥ 2 `.eval` files in the same directory. Two options:

1. **Multiple `@task` defs in one file** — `inspect eval file.py` runs every
   `@task` it finds and writes one log per task:

   ```python
   @task
   def f30_1_collision_a() -> Task: ...

   @task
   def f30_1_collision_b() -> Task: ...
   ```

2. **Separate files** with a shared slug prefix, both written to the same
   `logs/<batch>/` dir. Note in each file's `bug_sample(extra=...)` that the
   bug only manifests when *both* logs are present in the listing.

---

## 9. When a finding is NOT reproducible via `.eval`

A `.eval` file is a static snapshot of an eval run. It **cannot** demonstrate:

- **Backend / HTTP-layer bugs** (e.g. F70.x — header parsing, streaming,
  range requests). The bug is in the server ↔ client protocol, not in log
  rendering.
- **Browser-state bugs** (e.g. F51.x — IndexedDB, localStorage, service-worker
  cache). Nothing in the `.eval` controls those.
- **Pure interaction bugs** — keyboard navigation, scroll restoration, focus
  traps, hover tooltips. The log content is irrelevant; any log triggers it.
- **State-persistence-across-navigation** — "filter resets when you click
  back", "selected tab forgotten on reload". Again, any log works.

For these, **do not force a repro**. Instead append a row to
`findings/repros/NOT_REPRODUCIBLE.md`:

```markdown
| F70.2 | HTTP Range header off-by-one — server-side, no .eval involvement | curl repro in finding doc |
```

If a finding is *partially* reproducible (e.g. "the rendering half of this bug
can be shown, the interaction half can't"), build the partial repro and note
the gap in `bug_sample(extra=...)`.

---

## 10. Iteration advice

- **Keep it tiny.** 1 sample, 1–2 model turns. The smaller the log, the easier
  triage is.
- **One bug per file.** Don't bundle.
- If your first attempt doesn't hit the buggy code path, **simplify** — strip
  everything that isn't load-bearing and try again. Read the viewer source
  (`src/inspect_ai/_view/www/src/...`) for the exact field/shape it mishandles,
  then construct exactly that.
- **Don't guess imports.** Everything in this doc was checked against the
  current source. If you need something not shown here, `rg` for it in
  `src/inspect_ai/` and `tests/` first.
- **Verify before moving on:** the `.eval` file exists, is > 1 KB, and
  `./run.sh` exited 0.

---

## 11. Reference — where things live

| What                           | Import                                                                 | Source                                          |
|--------------------------------|------------------------------------------------------------------------|-------------------------------------------------|
| `Task`, `@task`                | `from inspect_ai import Task, task`                                    | `src/inspect_ai/_eval/task/task.py`             |
| `Sample`                       | `from inspect_ai.dataset import Sample`                                | `src/inspect_ai/dataset/_dataset.py`            |
| `@solver`, `TaskState`, `Generate` | `from inspect_ai.solver import ...`                                | `src/inspect_ai/solver/`                        |
| `@scorer`, `Score`, `Target`, `accuracy` | `from inspect_ai.scorer import ...`                          | `src/inspect_ai/scorer/`                        |
| `@tool`, `Tool`, `ToolCall`, `ToolCallError` | `from inspect_ai.tool import ...`                        | `src/inspect_ai/tool/`                          |
| `react`, `agent`, `AgentState` | `from inspect_ai.agent import ...`                                     | `src/inspect_ai/agent/`                         |
| `get_model`, `ModelOutput`     | `from inspect_ai.model import ...`                                     | `src/inspect_ai/model/_model_output.py`         |
| `ChatMessage*`, `Content*`     | `from inspect_ai.model import ...`                                     | `src/inspect_ai/model/_chat_message.py`, `src/inspect_ai/_util/content.py` |
| `transcript()`                 | `from inspect_ai.log import transcript`                                | `src/inspect_ai/log/_transcript.py`             |
| `span()`, `store()`            | `from inspect_ai.util import span, store`                              | `src/inspect_ai/util/_span.py`, `_store.py`     |
| All event classes              | `from inspect_ai.event import ...`                                     | `src/inspect_ai/event/`                         |
| mockllm internals              | —                                                                      | `src/inspect_ai/model/_providers/mockllm.py`    |
| Real-world usage examples      | —                                                                      | `tests/timeline/generate.py` (gold mine)        |
