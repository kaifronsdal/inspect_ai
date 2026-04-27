# Inspect Viewer Code Review & Repro Playbook

A self-contained guide for orchestrating a multi-agent code review of the Inspect AI viewer, building minimal `.eval` reproduction logs for each bug found, and rigorously verifying those repros against the live viewer with Playwright.

This document assumes:
- You are an **orchestrator** agent that dispatches subagents and consolidates results — you do not investigate yourself.
- Working directory is the `inspect_ai` repo root with the viewer frontend submodule checked out (`git submodule update --init --recursive`).
- `uv` is the Python runner; mockllm only, never real model APIs.

---

## Table of contents

1. [Principles](#principles)
2. [Phase 1 — Code review](#phase-1--code-review)
3. [Phase 2 — Build repros](#phase-2--build-repros)
4. [Phase 3 — Browser verification](#phase-3--browser-verification)
5. [Phase 4 — Description accuracy](#phase-4--description-accuracy)
6. [Phase 5 — Cleanup & consolidation](#phase-5--cleanup--consolidation)
7. [Appendix A — Repro cookbook](#appendix-a--repro-cookbook)
8. [Appendix B — Verification cookbook](#appendix-b--verification-cookbook)
9. [Appendix C — Lessons & anti-patterns](#appendix-c--lessons--anti-patterns)

---

## Principles

- **Phases are guidelines, not a fixed pipeline.** The orchestrator should loop, branch, and backtrack as evidence demands. If a consolidation agent flags something suspicious, dispatch a targeted re-investigation. If the user (or a verification agent) finds a repro that "looks fine", spawn a focused agent to root-cause that one finding — re-read source, rebuild the repro, re-verify — rather than trusting the prior verdict. Any phase can be re-run on a subset: re-review one subsystem after a related bug surfaces elsewhere; re-verify a handful of findings whose evidence type proved unreliable; rebuild a batch of repros after discovering a shared flaw in how they were constructed. Treat the wave structure as a default traversal, not a one-way conveyor.
- **Orchestrator never investigates.** Dispatch subagents for all reading, writing, and verification. The orchestrator only: sets up directory structure, writes shared protocol docs, batches agents, cleans temp files between waves, consolidates, and **decides what to dispatch next** based on results so far.
- **Narrow scope per agent.** One subsystem, one finding, or one file per agent. Broad scopes produce shallow results.
- **Standard output format.** Every agent writes to a predetermined path in a predetermined format. Orchestrator provides a template.
- **Adversarial verification.** Assume prior verdicts and descriptions may be wrong. Re-read source. Measure, don't infer.
- **Self-explanatory repros.** Every `.eval` must tell a human opening it what bug to look for, where, and what correct behavior would be — without any external docs.
- **Side-by-side comparison.** Wherever possible, the repro shows the correct case next to the buggy case in the same log.
- **Clean between waves.** Subagents leave `_tmp*.py` and `__pycache__` everywhere. Sweep after each wave.
- **Unique ports per parallel agent.** `inspect view` kills whatever is on its port; parallel verification agents must each use a distinct port (e.g. `7600 + index`).

### When to loop back

Dispatch a **targeted re-run** (one or a few agents, not a whole wave) whenever:
- A verification verdict contradicts a user spot-check or another agent's result → root-cause that one finding end-to-end (source → repro → verify).
- A class of evidence turns out to be unreliable (e.g. structural verdicts based only on text-match) → re-verify every finding that relied on that evidence type, using a stronger channel.
- A repro-construction pattern is discovered to be flawed (e.g. banner hidden by solver composition) → sweep all repros for the same flaw, fix, regenerate.
- A false-positive reveals a guard/default elsewhere in the codebase → re-check sibling findings that may share the same guard.
- Consolidation surfaces a duplicate or contradiction between two findings → dispatch one agent to reconcile.
- A new area of concern emerges mid-process → run a fresh Phase-1-style review scoped to just that area.

The cost of a targeted re-run is small; the cost of a wrong verdict propagating into the final report is large.

---

## Phase 1 — Code review

### Setup (orchestrator)

```bash
git fetch origin && git pull origin main
git submodule update --init --recursive
mkdir -p findings
```

Write `findings/README.md` with a file-numbering scheme (assign a numeric range to each major subsystem so finding IDs are sortable and non-colliding — e.g. `01–09` for one area, `10–19` for the next; reserve `90–99` for cross-cutting/verification/indices) and the severity scale:

| Severity | Meaning |
|---|---|
| HIGH | Correctness bug, wrong data shown, crash, security |
| MEDIUM | Misleading display, silent fallback, significant smell |
| LOW | Minor inconsistency, dead code, naming |
| INFO | Observation, not necessarily a problem |

Write `findings/TEMPLATE.md`:

```markdown
# [Area Name]
**Reviewer scope:** [files/dirs reviewed]

## Summary
[2–4 sentences]

## Findings

### F##.# — [Title]
- **Severity:** HIGH | MEDIUM | LOW | INFO
- **Location:** `path/to/file.tsx:123`
- **Category:** correctness | event-display | consistency | collapse-expand | dead-code | fallback-hiding-errors | code-smell | styling

**Description:** [what is wrong]
**Evidence:**
```[snippet ≤15 lines]```
**Impact:** [what the user sees]
**Suggested fix:** [optional]

## Files reviewed
- [ ] `path/one.tsx`
```

### Wave 1.0 — Codebase map (1 agent)

Dispatch one Explore agent to write `findings/00-codebase-map.md`. Required coverage:
1. Directory-by-directory breakdown of every source root (apps + packages)
2. The primary data → UI pipelines: for each major data type the viewer renders, trace source-of-truth type definition → generated/shared TS types → transform layer → renderer component. List every variant in each discriminated union and which component renders it.
3. State management: where UI state (collapse/expand, selection, filters) lives; what reads/writes it
4. Data loading: how the app fetches data (client backends, caching, store)
5. Key shared abstractions: reusable components/hooks that many other components depend on
6. Any `CLAUDE.md` / `AGENTS.md` / `design/*.md` docs in the repo — read and summarize constraints

This file is read by every subsequent review agent. It also informs how the orchestrator splits subsystems for Wave 1.1+.

### Waves 1.1–1.4 — Subsystem reviews (~20 agents, parallel batches of 5–7)

Each agent gets:
- A scope (specific directory or component set)
- Required reading: `findings/00-codebase-map.md`, `findings/TEMPLATE.md`
- Output path: `findings/NN-area-name.md`
- Finding ID prefix: `FNN.#`

**What every review agent looks for:**
1. **Correctness** — does each renderer display all relevant fields from its type? Cross-reference TS type against Python source-of-truth. Optional fields handled?
2. **Coverage** — is there a renderer for every variant in the union? Anything falling through to a default that loses info?
3. **Wrong data** — wrong field, wrong label, wrong format (timestamps, durations, sizes)?
4. **Inconsistency** — same concept rendered differently in two places (label text, styling, layout)?
5. **Collapse/expand** — sensible defaults? Consistent?
6. **Fallbacks hiding errors** — `?.`, `||`, `??`, `try/catch` that swallow malformed data?
7. **Dead code** — unused exports (verify with `rg`), unreachable branches, commented-out code
8. **Code smell** — duplication, magic strings, prop drilling
9. **Text/labels** — every user-visible string: typos, capitalization, terminology drift
10. **a11y / perf** where relevant

**How to split subsystems:** Use the codebase map from Wave 1.0 to carve ~15–25 scopes. Good boundaries:
- One agent per renderer family (e.g. all event-type views; all message-content views; all tool-call views)
- One agent per transform/pipeline layer (raw data → tree/list structure)
- One agent per top-level UI surface (list view; detail view; navigation; tabs)
- One agent per infrastructure layer (state store; routing; data clients; backend)
- One agent per shared library (base UI components; theme/icons; utilities)
- Separate agents for "the big complex component" vs "all the small simple components" in the same area — depth matters more than file count
- Keep scopes small enough that the agent reads every file line-by-line (typically ≤30 files)

### Wave 1.5 — Cross-cutting + verification (3–4 agents, parallel)

- **`90` Cross-cutting consistency:** find every place that renders scores / timestamps / durations / errors / model names / token counts / status; cite both sides of each inconsistency with `file:line`.
- **`81` Dead-code sweep:** mechanical inventory — unused exports (verify with `rg`), `styles.X` references with no matching `.X` rule, dead CSS rules, orphaned `.module.css`, unused props.
- **`91` HIGH-severity verification:** independent agent re-reads source at the cited `file:line` for every HIGH finding → CONFIRMED / REFUTED / PARTIAL with evidence.

### Wave 1.6 — Consolidate (1 agent)

- Read all `findings/*.md`
- Build `92-duplicate-index.md` (canonical ID → duplicate IDs table)
- Write `SUMMARY.md`: counts by severity (after dedup), top ~15 issues, thematic patterns, per-area index, recommended next steps
- Update `findings/README.md` with full Contents table

---

## Phase 2 — Build repros

**Goal:** for every finding that is a *bug* (not pure code-style/dead-code/naming), produce a minimal artifact that demonstrates it. The default vehicle is a `.eval` log opened in `inspect view`, but the agent should pick whatever vehicle best demonstrates the specific bug — a timing script for perf, an interaction script for click-sequence bugs, a backend request script, a unit test, etc.

### Setup (orchestrator)

```bash
mkdir -p findings/repros/{tasks,logs}
# one subdir per batch — name batches after the subsystem ranges from Phase 1
# (e.g. tasks/01-<area>/, tasks/10-<area>/, ...)
```

Write `findings/repros/_common.py` and `findings/repros/run.sh` from [Appendix A](#appendix-a--repro-cookbook).
Write `findings/repros/HOWTO.md` pointing at Appendix A.
Write `findings/repros/NOT_REPRODUCIBLE.md` with header: `| Finding ID | What was attempted | Why no repro vehicle works |` — this file should stay short; most things are reproducible *somehow*.

### Waves 2.1–2.6 — Batch repro builders (~6 agents, parallel)

Group findings by batch directory. Each agent gets:
- A list of finding IDs with one-line bug summary + key trigger hint
- Required reading: Appendix A of this doc, `_common.py`, the relevant `findings/NN-*.md`
- Output: `tasks/<batch>/F##.#_<slug>.py` → `logs/<batch>/*.eval`

**Per finding, the agent must:**
1. Write a task file using the template in Appendix A.
2. The `Sample.input` AND a top-of-solver `emit_bug_banner(DESC)` InfoEvent both contain `bug_description(...)` text with: ID, title, **where to look** (exact navigation), **observed (bug)**, **expected**.
3. Use mockllm only. If a field can't be set via mockllm (e.g. `ModelEvent.retries`), emit the event directly via `transcript()._event(...)`.
4. Where the bug is "X is missing" or "X is wrong", include a **correct/control case** in the same log so the user can compare side-by-side.
5. Generate: `./findings/repros/run.sh tasks/<batch>/<file>.py <batch>`. Verify `.eval` exists and >1KB.
6. **If a `.eval` file isn't the right vehicle**, reason about what IS and build that instead — e.g. a `.sh` timing script for a perf bug, a standalone Playwright script that performs the triggering interaction, a `curl` sequence against the backend, a pytest unit test against the specific function. Put it in `tasks/<batch>/F##.#_<slug>.<ext>` with a companion `F##.#_<slug>.md` explaining how to run it and what to observe. Only append to `NOT_REPRODUCIBLE.md` after genuinely attempting alternatives and explaining why none demonstrate the issue.

### Wave 2.7 — Complete + index (1 agent)

- Generate any missing `.eval` files; fix runtime failures (read error → read inspect_ai source → fix → retry, max 3 attempts)
- Dedupe `.eval` files (one per task slug, 2 for multi-log tasks)
- Write `INVENTORY.md`: `| Finding ID | Task file | .eval file(s) | Size | Status |`
- Write `repros/README.md` with view command + per-finding index table

---

## Phase 3 — Browser verification

**Goal:** open every `.eval` in the live viewer, navigate to the bug location, and determine whether the bug actually reproduces.

### Setup (orchestrator)

```bash
uv run --with playwright playwright install chromium
mkdir -p findings/repros/verify/{checks,results,artifacts,per-finding}
```

Write `findings/repros/verify/harness.py` from [Appendix B](#appendix-b--verification-cookbook).
Write `findings/repros/verify/PER_FINDING_PROTOCOL.md` (the per-finding agent instructions — see Appendix B §B.4).

### Wave 3.0 — Discover viewer routes & selectors (1 agent)

Selectors, hash-router URL patterns, tab/button labels, and default-filter behavior are implementation details that change between viewer versions — discover them fresh rather than relying on stale documentation.

Dispatch one agent to:
1. Read the viewer's routing source (search for `createHashRouter`, `useParams`, route pattern constants) → derive the URL shape for: log list, log-level tabs, sample-level tabs, deep-link to event/message.
2. Read 3–4 key component sources (event panel, tab set, outline row, sample list/grid) → identify stable selector hooks (prefer `data-*` attrs, `role=`, `id=` over CSS-module hashes).
3. Open one repro `.eval` in a `ViewerSession`, dump `page.content()` and `page.accessibility.snapshot()`, and confirm the selectors actually match.
4. Determine whether any default filter/collapse hides event types relevant to repros, and how to disable it.
5. Fill in the `goto_*` method bodies in `harness.py` and write `findings/repros/verify/SELECTORS.md` (table: target → URL pattern / selector / notes). Prove end-to-end on 2–3 findings.

Per-finding agents read `SELECTORS.md` instead of hardcoded values.

### Wave 3.1 — Per-finding verification (one agent per finding, batches of ~15)

Each agent gets: one finding ID, batch dir, unique port (`7600 + index`).

**Each agent must:**
1. Read: the original finding (`findings/NN-*.md` § F##.#), the cited source line, the repro task `.py`, the harness, `SELECTORS.md`, the prior verdict if any.
2. Open `ViewerSession(log_dir, port)`, navigate to the bug location (disable any default filter/collapse that hides the target — see `SELECTORS.md`).
3. **Screenshot** to `artifacts/per-finding/<ID>-page.png` and `<ID>-panel.png`.
4. **Read the screenshot** with the multimodal Read tool. Describe what you see in your own words.
5. Extract evidence through **at least two independent channels** from the toolbox in §B.3 (text + structure + position/style/count as appropriate). If channels disagree, resolve the disagreement before issuing a verdict.
6. Compare against the finding's claim AND the repro's `bug_description`.
7. Verdict + write `per-finding/<ID>.md` listing what each channel showed.

**Verdicts:**

| Verdict | Meaning |
|---|---|
| `CONFIRMED` | Bug visible exactly as described; a reasonable user would consider it a bug |
| `CONFIRMED_MINOR` | Reproduces but trivial impact / debug-mode-only / synthetic-only / unreachable in normal use → recommend severity downgrade |
| `FALSE_POSITIVE` | Page shows correct behavior AND source re-read confirms finding misread the code |
| `BY_DESIGN` | Behavior matches "observed" but is documented intentional (design doc, e2e test, git history) |
| `REPRO_BROKEN` | `.eval` doesn't reach the code path; underlying finding may still be valid — say whether source supports it |
| `INCONCLUSIVE` | Cannot determine; explain blocker |

### Wave 3.2 — Consolidate verdicts (1 agent)

Write `verify/VERIFICATION.md`: summary counts, full table, false-positive analysis, severity-downgrade recommendations.

**Orchestrator review:** read the consolidated verdicts. If any cluster looks suspicious (e.g. every structural-depth finding came back CONFIRMED with thin evidence, or several FALSE_POSITIVEs share a pattern that might itself be wrong), dispatch targeted re-audit agents on that cluster before proceeding to Phase 4. Don't treat the wave output as final just because every agent returned a result.

---

## Phase 4 — Description accuracy

**Goal:** ensure every statement in each repro's `bug_description` is factually accurate against the live DOM. Users found many repros with wrong tab names, nonexistent "expand" steps, etc.

### Wave 4.1 — Per-finding accuracy audit (one agent per finding, batches of ~15)

Each agent gets: one finding ID, batch dir, unique port (`7800 + index`), prior verdict.

**Each agent must:**
1. Open the repro under **Default** filter. Screenshot `before.png`. Read it.
2. **Banner check:** is the bug-repro InfoEvent visible and expanded near the top? If hidden (e.g. inside a collapsed wrapper span produced by solver composition), restructure the solver so the banner emits at the top level.
3. **Sentence-by-sentence audit** of `where_to_look` / `observed` / `expected` / `extra`:
   - Does every navigation step exist and work?
   - Are tab/panel/button names exactly what's on screen (including casing — viewer uppercases via CSS)?
   - Are "expand" / "click" / "has subtabs" claims true?
   - Are sentinel strings present where claimed?
4. **Verdict-specific framing:**
   - FALSE_POSITIVE → lead with `**✅ FALSE POSITIVE — NOT A BUG.**` + why
   - REPRO_BROKEN/scout-only → lead with `**⚠️ SCOUT-ONLY — does not reproduce in inspect viewer.**`
   - CONFIRMED_MINOR → add `**Note:** impact is minor — <reason>` to `extra`
5. Rewrite `DESC`, regenerate `.eval`, screenshot `after.png`, re-verify every step.
6. Write `accuracy/<ID>.md` listing each fix.

---

## Phase 5 — Cleanup & consolidation

### Wave 5.1 — Delete non-issues + finalize (1 agent)

1. **Delete** repros with verdict FALSE_POSITIVE or REPRO_BROKEN(scout-only) — task `.py`, `.eval`, check script. Record in `repros/REMOVED.md` with reason + link to evidence.
2. **Keep** BY_DESIGN repros only if the user has indicated the design is questionable (otherwise delete).
3. Regenerate `INVENTORY.md` from disk.
4. Update `repros/README.md`, `verify/VERIFICATION.md`, `findings/SUMMARY.md` with final counts.
5. Sweep all `_tmp*.py`, `__pycache__`.
6. Verify: every `.eval` has a matching task `.py`; counts consistent across all index docs.

---

# Appendix A — Repro cookbook

## A.1 Directory & naming

```
findings/repros/
  _common.py
  run.sh
  HOWTO.md, README.md, INVENTORY.md, NOT_REPRODUCIBLE.md, REMOVED.md
  tasks/<batch>/F##.#_<slug>.py
  logs/<batch>/<timestamp>_<task-name>_<hash>.eval
```

Name `<batch>` directories after the Phase-1 subsystem ranges (e.g. `01-<area>`, `10-<area>`, `90-cross`).

## A.2 Run command

`findings/repros/run.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
TASK="$1"; BATCH="$2"
unset UV_EXCLUDE_NEWER INSPECT_TELEMETRY INSPECT_API_KEY_OVERRIDE INSPECT_REQUIRED_HOOKS
uv run inspect eval "$TASK" \
  --model mockllm/model \
  --log-dir "findings/repros/logs/$BATCH" \
  --log-format eval \
  --no-score-display
```

## A.3 `_common.py`

```python
"""Shared helpers for viewer bug-repro tasks."""
from textwrap import dedent
from inspect_ai.log import transcript

TINY_PNG_DATA_URI = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAX+"
    "XxJgAAAABJRU5ErkJggg=="
)

def bug_description(
    *,
    finding_id: str,
    title: str,
    where_to_look: str,
    observed: str,
    expected: str,
    finding_file: str,
    extra: str = "",
) -> str:
    body = dedent(f"""\
        # VIEWER BUG REPRO — {finding_id}
        {title}

        | | |
        |---|---|
        | **Where to look** | {where_to_look} |
        | **Observed (bug)** | {observed} |
        | **Expected** | {expected} |
        | **Finding file** | `{finding_file}` |
        """)
    if extra:
        body += f"\n{extra}\n"
    return body

def emit_bug_banner(desc: str) -> None:
    """Emit description as InfoEvent so it's the first visible panel in Transcript."""
    transcript().info(desc, source="bug-repro")
```

## A.4 mockllm patterns

```python
from inspect_ai.model import (
    get_model, ModelOutput, ModelUsage, ChatMessageAssistant,
    ChatMessageUser, ChatMessageTool, ChatMessageSystem,
)
from inspect_ai.model._call_tools import ToolCall  # or from inspect_ai.tool
from inspect_ai._util.content import ContentText, ContentImage, ContentReasoning, ContentData

# Scripted assistant outputs (consumed as ONE iterator across all generate() calls in all samples)
model = get_model("mockllm/model", custom_outputs=[
    ModelOutput.from_content(model="mockllm", content="response 1"),
    ModelOutput.from_content(model="mockllm", content=[
        ContentReasoning(reasoning="thinking..."),
        ContentText(text="response 2"),
    ]),
    ModelOutput.for_tool_call(model="mockllm", tool_name="my_tool",
                              tool_arguments={"x": 1}, id="call_1"),
])

# Set usage / stop_reason / error on a ModelOutput
out = ModelOutput.from_content(model="mockllm", content="truncated...")
out = out.model_copy(update={
    "usage": ModelUsage(input_tokens=0, output_tokens=50, total_tokens=50,
                        input_tokens_cache_read=100),
    "stop_reason": "max_tokens",
    "error": "F04.7_OUTPUT_ERROR_SENTINEL — content filtered",
})

# Task-level model overrides CLI --model
Task(..., model=model)
```

## A.5 Direct event emission

When mockllm can't produce a field naturally (e.g. `ModelEvent.retries`, `ToolEvent.truncated`, `SandboxEvent`):

```python
from inspect_ai.log import transcript
from inspect_ai.log._transcript import ModelEvent, ToolEvent, SandboxEvent, StateEvent
from inspect_ai.util import span, store

# Inside async def solve(state, generate):
transcript().info("text or markdown", source="label")          # InfoEvent
transcript()._event(ModelEvent(model="mockllm", input=[...],     # any event type
                               output=..., retries=3, cache="read", ...))
async with span("name", type="..."): ...                         # SpanBegin/End
store().set("key", value)                                        # StoreEvent (auto)
state.metadata["k"] = v                                           # StateEvent (auto on solver return)
```

**StateEvent JSON-patch shape:** mutating `state.tools`/`state.metadata` produces `op:"add"|"replace"` ops at paths like `/tools/0`, `/metadata/key/nested`. To target a specific change-type signature, emit `StateEvent(changes=[JsonChange(op="add", path="/tools/0", value=...)])` directly.

## A.6 Message & tool construction

```python
from inspect_ai.tool import ToolCall, ToolCallError, ToolCallContent, ToolCallView

ChatMessageTool(
    content=[ContentText(text="..."), ContentImage(image=TINY_PNG_DATA_URI)],
    tool_call_id="call_1",
    function="my_tool",
    error=ToolCallError(type="permission", message="..."),
    # type Literal: parsing|timeout|unicode_decode|permission|file_not_found|
    #               is_a_directory|limit|approval|unknown
)

ChatMessageAssistant(
    content="text",
    tool_calls=[ToolCall(
        id="call_1", function="my_tool", arguments={"x": 1},
        view=ToolCallContent(title="custom title", format="text", content="# raw"),
    )],
)
```

## A.7 Scorers & score edits

```python
from inspect_ai.scorer import scorer, Score, Target, mean, metric, score_edit
from inspect_ai.solver import TaskState

@scorer(metrics=[mean()])
def my_scorer():
    async def score(state: TaskState, target: Target) -> Score:
        # Param names MUST be exactly `state` and `target` (protocol requirement).
        del state, target
        return Score(value=True, answer="x", explanation="...", metadata={"k": "v"})
    return score

# In a solver, after scoring:
score_edit("my_scorer", value=0, explanation="edited")  # → ScoreEditEvent
```

## A.8 Banner pattern (CRITICAL)

The bug description must be the first thing a human sees when they open the repro under default viewer settings (no filter changes, no expanding). `InfoEvent` is a good vehicle: rendered as markdown, expanded by default, and not hidden by typical default filters — but **verify this** for the current viewer build (Wave 3.0 checks which event types the default filter hides).

```python
@solver
def repro_solver():
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)            # FIRST line — InfoEvent at top of transcript
        # ... rest of solver
        return await generate(state)
    return solve
```

After generating, **open the `.eval` and confirm the banner is visible without any clicks**. If it's hidden (e.g. wrapped in a collapsed sub-span because of how the solver is composed, or filtered out), restructure until it isn't. Common fix: emit inline in the main solver body rather than via a separate composed/chained solver step.

## A.9 Multi-log & status=error

```python
# Multi-log: define multiple @task in one file → run.sh emits one .eval per @task
@task
def F30_1_a(): return Task(...)
@task
def F30_1_b(): return Task(...)

# status=error log: raise inside solver, set fail_on_error=False on Task to keep eval going,
# or omit it to fail the whole eval (non-zero exit but .eval still written)
```

## A.10 Complete task template

```python
"""F##.# — <one-line title>"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2]))  # findings/repros/

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.model import get_model, ModelOutput
from inspect_ai.solver import solver, Generate, TaskState
from _common import bug_description, emit_bug_banner

DESC = bug_description(
    finding_id="F##.#",
    title="<title>",
    where_to_look="Transcript tab → <exact navigation>. Switch Events filter to **Debug** if needed.",
    observed="<exactly what you will see — verified against DOM>",
    expected="<what correct behavior looks like>",
    finding_file="findings/##-*.md",
    extra="<optional: minor-impact note, root cause, control-case explanation>",
)

@solver
def repro_solver():
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        emit_bug_banner(DESC)
        # ... trigger the bug ...
        return await generate(state)
    return solve

@task
def F##_#_<slug>():
    return Task(
        dataset=[Sample(id="F##.#", input=DESC, target="n/a")],
        solver=repro_solver(),
        model=get_model("mockllm/model", custom_outputs=[
            ModelOutput.from_content(model="mockllm", content="(output)"),
        ]),
    )
```

---

# Appendix B — Verification cookbook

## B.1 `harness.py` skeleton

```python
"""Playwright harness for inspect view verification."""
import subprocess, time, socket, sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from playwright.sync_api import sync_playwright, Page

@dataclass
class VerifyResult:
    verdict: str  # CONFIRMED|CONFIRMED_MINOR|FALSE_POSITIVE|BY_DESIGN|REPRO_BROKEN|INCONCLUSIVE
    evidence: str
    notes: str = ""

class ViewerSession:
    def __init__(self, log_dir: str, port: int = 7575):
        self.log_dir = log_dir
        self.port = port
        self.base = f"http://localhost:{port}"
        self._proc = None
        self._pw = None
        self._browser = None
        self.page: Page | None = None

    def __enter__(self):
        self._proc = subprocess.Popen(
            ["uv", "run", "inspect", "view", "--log-dir", self.log_dir,
             "--port", str(self.port), "--no-browser"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(60):
            try:
                with socket.create_connection(("localhost", self.port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.25)
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        self.page = self._browser.new_page(viewport={"width": 1400, "height": 1000})
        self.page.set_default_timeout(15000)
        return self

    def __exit__(self, *_):
        try:
            if self._browser: self._browser.close()
            if self._pw: self._pw.stop()
        finally:
            if self._proc:
                self._proc.terminate()
                try: self._proc.wait(timeout=5)
                except subprocess.TimeoutExpired: self._proc.kill()

    # --- navigation ---
    # Route patterns are discovered in Wave 3.0 and filled in here.
    # Prefer deep-linking via hash URL over click sequences (more reliable).
    def goto(self, hash_path: str):
        self.page.goto(f"{self.base}/#{hash_path}")
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(300)

    def goto_log_list(self): ...
    def goto_sample(self, log_filename: str, sample_id, epoch=1, tab="transcript"): ...
    def goto_log_tab(self, log_filename: str, tab: str): ...

    # --- extraction ---
    def text_of(self, selector: str) -> str:
        return self.page.locator(selector).first.inner_text()

    def html_of(self, selector: str) -> str:
        return self.page.locator(selector).first.evaluate("el => el.outerHTML")

    def screenshot(self, path: str, selector: str | None = None):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        if selector:
            self.page.locator(selector).first.screenshot(path=path)
        else:
            self.page.screenshot(path=path, full_page=True)

    def find_log(self, slug_prefix: str) -> str:
        """Find .eval filename in log_dir whose slug starts with slug_prefix.
        Use 'F20.1-' not 'F20.1' to avoid matching F20.14."""
        for p in Path(self.log_dir).glob("*.eval"):
            if slug_prefix in p.name:
                return p.name
        raise FileNotFoundError(slug_prefix)
```

Run check scripts via:
```bash
cd findings/repros/verify
uv run --with playwright python -c "from harness import ViewerSession; ..."
```

## B.2 Routes, selectors, and default filters

These are viewer-implementation-specific and change between versions. They are **discovered in Wave 3.0** and written to `findings/repros/verify/SELECTORS.md`, which per-finding agents read. The discovery agent should produce:

- **URL route table** — hash path for: log list root, multi-log aggregate view, log-level tabs, sample-level tabs, deep-link query params. Derived from the router source.
- **Selector table** — for each commonly-targeted element (tab buttons, tab content panes, event panels, sub-tab pills, outline rows, list/grid rows + cells, filter inputs, column picker): a stable selector. Prefer `data-*` / `role=` / `id=` over CSS-module class hashes (which change per build).
- **Default-hidden content** — any filter, collapse default, or lazy-mount that hides content a repro targets, plus the helper to disable it (e.g. `show_all_events(session)` that clicks the relevant control).

## B.3 Extraction toolbox + multi-modal verification

**Verify each claim through at least two independent channels.** A single signal is easy to misread (selector matched the wrong element, screenshot cropped the relevant part, text-match hit the bug_description instead of the UI). Pick channels that fail differently — if they agree, the verdict is solid; if they disagree, investigate before concluding.

| Method | Returns | Best for | Failure mode it's robust against |
|---|---|---|---|
| `page.screenshot()` → **Read the .png** (multimodal) | Rendered pixels | Visual bugs (icons, colors, badges, layout, "does this look wrong to a human") | Selector matched wrong element; CSS hides text that's still in DOM |
| `locator.inner_text()` | Visible text (post-CSS-transform, e.g. uppercased) | Presence/absence of strings; label/tab-name verification | Visual styling you can't see in text; off-screen/clipped content still returns |
| `locator.evaluate("el => el.outerHTML")` | Raw HTML | Tag-level checks (`<h1>` present?); class-name comparison between two elements | Classes present but unstyled; dynamic content not yet mounted |
| `locator.bounding_box()` | `{x, y, width, height}` | Depth/indent/alignment bugs — measure deltas, derive indent unit empirically from two known-adjacent siblings | Doesn't tell you *what* is at that position |
| `locator.get_attribute("data-*")` / `aria-*` / `role` | Semantic attribute value | Depth (`data-depth`), sort state (`aria-sort`), selection (`aria-selected`), grid visual order (`row-index`) — without pixel math | Attribute may be stale or not set by this component |
| `locator.count()` | Number of matches | "Zero sub-tabs", "no chevron exists", "3 rows rendered not 5" | Over-broad selector inflates count |
| `locator.evaluate("el => getComputedStyle(el).<prop>")` | Computed CSS value | Color/font/visibility claims ("is this red?", "is this `display:none`?") | — |
| `page.evaluate(js)` | Arbitrary | Instrument handlers (did onClick fire twice?); read `scrollTop` before/after; read app state from `window` | — |
| `page.url` | Current hash route | Did navigation happen? Did deep-link param change? | — |
| `page.accessibility.snapshot(root=locator)` | a11y tree (roles, names, hierarchy) | Structured-text view of a region when you don't have a precise selector; verifying ARIA roles/labels | Huge if unscoped; gaps where app's a11y is incomplete |
| `page.content()` | Full page HTML | Last-resort grep when you can't locate something | Very large; includes hidden/template content |

**Triangulation patterns:**

- **"X is missing"** → (1) `inner_text()` of the container doesn't contain X, (2) screenshot read confirms X not visible, (3) source-of-truth (JSON tab / `read_eval_log`) confirms X *is* in the data. All three needed — (1)+(2) alone could mean wrong container; (1)+(3) alone could mean X is rendered as an icon.
- **"X looks the same as Y"** (e.g. error vs success styling) → (1) screenshot read: visually identical?, (2) `outerHTML` diff: same classes?, (3) `getComputedStyle`: same color/background? Any one disagreeing means they *are* distinguished somehow.
- **"X is at wrong depth/position"** → (1) `bounding_box().x` delta vs a known-correct sibling, (2) `get_attribute("data-depth")` or equivalent, (3) screenshot read with a reference element in frame. Pixel measurement alone is fragile to viewport/zoom.
- **"Clicking X does/doesn't do Y"** → record state *before* (url, scrollTop, target `inner_text`, relevant attribute), click, record *after*, diff. Screenshot before/after for the visual record.
- **"Label/tab name is wrong"** → (1) `inner_text()` exact string, (2) screenshot read (catches CSS uppercasing), (3) `get_attribute("aria-label")` if present.

**Core loop per claim:**

```python
PANEL = "<selector from SELECTORS.md>"

# 1. Visual channel
s.screenshot("artifacts/per-finding/F##.#-panel.png", selector=PANEL)
#    → Read the .png with the multimodal Read tool; describe what you SEE (not what you expect)

# 2. Text/structure channels
panel_text = s.text_of(PANEL)
panel_html = s.html_of(PANEL)

# 3. Whatever third channel fits the claim type (bounding_box / count / attribute / computed style)

# 4. State the claim, state what each channel showed, state whether they agree.
#    If they disagree: your selector or your understanding is wrong — resolve before issuing a verdict.
```

## B.4 Per-finding verification protocol (give to each agent)

```markdown
You own ONE finding. Be adversarial — assume prior verdicts/descriptions may be wrong.

1. Read: original finding (file:line claim), cited source line, repro task .py, harness.
2. Open ViewerSession(log_dir, port=<unique>). Navigate to bug location. Debug filter if needed.
3. Screenshot full page + relevant panel. READ the screenshots (multimodal). Describe what you see.
4. Extract inner_text/outerHTML of the relevant element.
5. Compare: what does the finding claim? what does the repro's description claim? what's actually on screen?
6. Verdict (CONFIRMED / CONFIRMED_MINOR / FALSE_POSITIVE / BY_DESIGN / REPRO_BROKEN / INCONCLUSIVE).
7. Write per-finding/<ID>.md with evidence. Clean up _tmp*.py.
```

## B.5 Gotchas (methodology, not implementation-specific)

- **Finding-ID prefix collisions** — `find_log("F20.1")` also matches `F20.14`. Always match on `"<ID>-"` or `"<ID>_"`.
- **CSS text-transform** — `inner_text()` returns the *rendered* casing (often uppercased); text-match locators may match either. Compare case-insensitively.
- **Lazy mounting** — tab/pane content is often only mounted when active. Click/select before reading.
- **Virtualized lists recycle DOM** — after sort/scroll, DOM order ≠ visual order. Read the row-index attribute the grid library exposes.
- **bug_description text bleeds into selectors** — `:has-text("Score")` matches the description panel too. Anchor on structural selectors or exact title-label text, not substring.
- **SPA navigation settling** — wait for `networkidle` plus a short buffer after each route change.
- **Port collision** — `inspect view` may kill whatever is on its port. Parallel agents MUST use distinct ports.
- **status=error logs** — task exits non-zero but the `.eval` is still written; that's expected.

---

# Appendix C — Lessons & anti-patterns

## C.1 Repro design

| Anti-pattern | Why it fails | Fix |
|---|---|---|
| Compare two equally-wrong things | Both shifted by the bug → look flush → "looks correct" | Add a **reference sibling outside the buggy subtree** at the correct position |
| Show only the buggy case | User can't tell if the rendering is wrong without seeing the working variant | Include the **control case in the same log** next to the buggy case |
| Banner emitted from a composed/chained sub-solver | Viewer may wrap each sub-solver in a collapsed span → banner hidden | Emit banner **inline** in the main solver body; verify it's visible without clicks |
| Span `type=` chosen without checking how that type renders | Some span types render as flat cards / different layouts, defeating nesting demos | Check how each span type renders before using it; default to no `type=` for plain nesting |
| Sentinel string contains the claimed-missing value | Ctrl-F finds it in the description itself → "it IS shown" | Keep sentinels OUT of the description text; or use values that only the buggy code path produces |
| "Ctrl-F for `12345`" when UI shows `12,345` | Thousands separator → 0 matches → false confidence | State the **exact rendered string** including formatting |

## C.2 Verification

| Anti-pattern | Why it fails | Fix |
|---|---|---|
| Single-channel evidence | One signal is easy to misread (wrong selector, description-bleed, off-screen content) | **Triangulate** ≥2 independent channels per claim (§B.3); resolve disagreements before verdict |
| Verdict from text-presence alone for structural bugs | "X is in inner_text" doesn't prove correct position/depth | Measure `bounding_box()` + read semantic depth attribute + screenshot |
| Trusting the repro's `observed` text | If the description is wrong, the check confirms a wrong claim | Re-read the **original finding** + **source line**, not just the repro |
| Confirming "field not shown" without checking elsewhere | Field might be shown in a different tab/panel | Search **all** tabs/panels + JSON tab before declaring missing |
| Marking CONFIRMED for unreachable code paths | Bug exists in source but no production data triggers it | Use **CONFIRMED_MINOR** with "synthetic-only" / "legacy-only" / "scout-only" note |

## C.3 Common false-positive patterns

- **Code looks wrong but a guard/default elsewhere makes it unreachable** — e.g. `(epochs || 0)` is dead because Python always writes `epochs >= 1`; double-fire handlers compute identical state from stale closure → idempotent.
- **"Field never shown" but it's in the event message text** — e.g. `SampleLimitEvent.limit` is in `event.message` ("limit: 12,345").
- **Behavior is documented intentional** — check `design/*.md`, e2e tests, git blame on the line. (But: documented ≠ desirable; flag for user judgment.)
- **Buggy code path is sibling-app-only** — a shared component has a prop that only a different app in the monorepo sets; the app under review takes a different (working) path. The bug is real in source but not observable here.

## C.4 Description accuracy checklist

Before regenerating any `.eval`, verify against live DOM:
- [ ] Every tab/panel/button name matches on-screen text (including CSS uppercasing)
- [ ] No "expand X" where X has no chevron
- [ ] No "click Y tab" where Y is a section, not a tab
- [ ] Navigation starts from where the user reads the banner (inside a sample → may need "close this sample first")
- [ ] Any required filter/expand step is stated explicitly if the target is hidden by default
- [ ] Sentinel strings actually present/absent where claimed
- [ ] `observed` describes what's on screen, not what the source code does internally
- [ ] FALSE_POSITIVE / scout-only / minor-impact framing applied per verdict

---

*End of playbook.*
