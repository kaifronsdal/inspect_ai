# Verification — 01-events

**Run:** 2026-04-24 · port 7576 · `uv run --with playwright python findings/repros/verify/verify_one.py --batch 01-events`
**Tally:** 14 CONFIRMED · 0 NOT_REPRODUCED · 0 INCONCLUSIVE · 0 FALSE_POSITIVE

> **Why the user's manual spot-check "looked normal":** the default transcript event filter (`kDefaultExcludeEvents` in `apps/inspect/src/state/sampleSlice.ts:18`) hides `sample_init`, `sandbox`, `state`, `store`, and `branch` events. Five of the 14 repros (F05.1/F05.4/F05.9/F05.11/F05.12) target exactly those event types — opening the log shows either nothing or "The currently applied filter hides all events." until the filter is switched to **Debug**. The harness now does this automatically (`checks/_util.py::show_all_events`).

| ID | Verdict | Evidence (key snippet) | Notes |
|---|---|---|---|
| F01.1 | CONFIRMED | Summary tab = `[ASSISTANT compaction, ASSISTANT output]` only; sentinel "IF YOU CANNOT SEE THIS IN THE SUMMARY TAB" present in **All** tab, absent in **Summary** | `event.input.slice(-1)` drops preceding user/system msgs |
| F01.2 | CONFIRMED | Tool Choice cell: `` '`$my_forced_tool()`' `` ; `<code>` = `` ['`$my_forced_tool()`'] `` | **Repro fixed** — see Details. Literal `` ` `` + `$` rendered |
| F01.3 | CONFIRMED | `VALUE → 'UNCHANGED'` · `ANSWER → 'edited-answer-only'` · `EXPLANATION → 'UNCHANGED'` | Sentinel leaks for value & explanation; answer correctly guarded |
| F04.2 | CONFIRMED | Model-event sub-tabs: `['SUMMARY', 'ALL', 'API']` — no `Tools` pill | `tools.length > 1` off-by-one with exactly 1 tool |
| F04.5 | CONFIRMED | Label cells across `[SUMMARY, ALL]`: `[CLOCK TIME, MESSAGES, START, TIMESTAMP, TIMING, USAGE, WORKING TIME, …]` — no `RETRIES` / `CACHE` | `event.retries=3` & `event.cache="read"` invisible everywhere |
| F04.7 | CONFIRMED | sentinel `'content filtered'` (output.error) absent from all sub-tabs; no `STOP REASON` / `MAX_TOKENS` label | `stop_reason="max_tokens"` & `output.error` never surfaced |
| F04.8 | CONFIRMED | `INPUT='' \| CACHE_READ='100' \| OUTPUT='50' \| TOTAL='150'` | `input_tokens=0` renders blank; non-zero rows render numbers |
| F05.1 | CONFIRMED | Diff: `LOOK_HERE → nested_key → "BEFORE" → "AFTER"` with **no** `metadata` ancestor (jsondiffpatch ancestors of `LOOK_HERE` = `[]`) | Change rendered at top level instead of `metadata/LOOK_HERE/nested_key`. `setPath` brace bug |
| F05.4 | CONFIRMED | 1-tool panel sub-tabs: `['SUMMARY', 'DIFF']`; 3-tool panel sub-tabs: `[]` (raw diff `0 → {"name":"beta_tool",…}`) | **Repro rebuilt** — see Details. Preview fires for 1 tool, skipped for 3. |
| F05.5 | CONFIRMED | All 3 Edit Score panels: `VALUE label present=False` | `value=0`/`False`/`""` → truthy check hides Value row entirely |
| F05.6 | CONFIRMED | Edit Score sub-tabs: `[]`; metadata MARKER visible inline; (contrast) Score event sub-tabs: `['EXPLANATION', 'METADATA']` | `<div data-name="Metadata">` nested inside Summary → never a tab |
| F05.9 | CONFIRMED | Panel: `SANDBOX: EXEC \n COMMAND \n RESULT …`; first `<pre>` (cmd) text: `''` | `=== null` guard misses `undefined`; empty `<pre>` under Command heading |
| F05.11 | CONFIRMED | sub-tabs: `[SAMPLE, METADATA]`; Files: ✓ Setup: ✓; **Sandbox label: ✗ ID label: ✗** | `sample.sandbox` (`local`) and `sample.id` never read by SampleInitEventView |
| F05.12 | CONFIRMED | Panel: `BRANCH (0 SEC) \n FROM_SPAN origin-span-id-12345 \n FROM_MESSAGE origin-message-id-abcde`; metadata MARKER absent | `event.metadata` (branch_reason/branch_index/MARKER) discarded |

## Details

### Harness change — `checks/_util.py::show_all_events()`

The transcript "Events: Default" filter excludes `sample_init`, `sandbox`, `state`, `store`, `branch`. The popover presets are **Default / Debug / None** where **Debug = exclude nothing** and **None = exclude everything** (`hooks.ts:51-61`). The PopOver wrapper is a 0×0 absolutely-positioned div, so Playwright treats the links as invisible; the helper clicks the toggle button (to mount the popover children) then fires the `Debug` link's `onClick` via `page.evaluate`. Used by F05.1, F05.4, F05.9, F05.11, F05.12.

### F01.1 — ModelEventView Summary drops preceding messages

Checked: Transcript → Model Call → **Summary** vs **All** sub-tabs.
```
Summary tab contains sentinel: False
All tab contains sentinel:     True
--- Summary tab ---
ASSISTANT
[trailing assistant / compaction-style message]
…
ASSISTANT
[model output] — end of summary.
```
The repro's input is `[system(SENTINEL), user(desc), user(SENTINEL), assistant]`. Summary shows only `[assistant, output]`. Source `ModelEventView.tsx:74` confirms `event.input.slice(offset)` with `offset=-1`.

### F01.2 — ToolChoiceView renders literal `` `$ ``

**Repro fixed.** The original repro used `state.tool_choice = ToolFunction(...)` + `generate()`, but inspect filters `event.tools` down to the single forced tool before logging → `tools.length == 1` → F04.2 hides the Tools tab → unreachable (the prior check returned `INCONCLUSIVE`). Rewrote `tasks/01-events/F01.2_tool_choice_literal_dollar.py` to push a synthetic `ModelEvent` directly via `transcript()._event()` with two `ToolInfo` entries and `tool_choice=ToolFunction(name="my_forced_tool")`, then regenerated the `.eval`.

```
Tool Choice cell: '`$my_forced_tool()`'
<code> elements: ['`$my_forced_tool()`']
```
Source `ModelEventView.tsx:312`: `` return <code>`${toolChoice.name}()`</code>; `` — JSX parses as text `` `$ `` + expr `{toolChoice.name}` + text `` ()` ``.

### F01.3 — ScoreEditEventView renders "UNCHANGED" sentinel

Checked: Transcript → **Edit Score** event (no sub-tabs). Parsed line-after-label:
```
VALUE → 'UNCHANGED'
ANSWER → 'edited-answer-only'
EXPLANATION → 'UNCHANGED'
```
Avoided false-match on `provenance.reason` (which also contains the word UNCHANGED) by anchoring on the line immediately following each label. Source `ScoreEditEventView.tsx:50,73` confirms only `answer` (L63) and `metadata` (L118) check `kUnchangedSentinel`.

### F04.2 — Tools tab hidden with exactly one tool

```
Model-event sub-tabs: ['SUMMARY', 'ALL', 'API'] — no 'Tools' pill.
```
Source `ModelEventView.tsx:198`: `{event.tools.length > 1 && (…)}`.

### F04.5 — `event.retries` / `event.cache` never displayed

Checked every `.text-style-label` element across all sub-tabs (chat-message bodies are excluded from this selector, so the input-message text "retries=3" doesn't pollute):
```
panel title: 'MODEL CALL: MOCKLLM/MODEL'
label cells: [ASSISTANT, CLOCK TIME, MESSAGES, START, TIMESTAMP, TIMING, USAGE, USER, WORKING TIME, …]
Retries label present: False; Cache label present: False
```
`rg 'event\.retries|event\.cache' ModelEventView.tsx` → 0 matches.

### F04.7 — `stop_reason` / `output.error` not displayed

Sentinel `'content filtered'` (unique to `output.error`; the bug-description uses an ellipsis) is absent from Summary, All, and API tabs. No `STOP REASON` / `MAX_TOKENS` / `TRUNCATED` label cell exists.
```
sub-tabs checked: ['SUMMARY', 'ALL', 'API']
output.error sentinel ('content filtered') visible: False
stop_reason label/badge visible: False
```

### F04.8 — zero-valued usage rows render blank

```
INPUT='' | CACHE_READ='100' | OUTPUT='50' | TOTAL='150'
```
`input_tokens=0` → blank cell. Source `ModelUsagePanel.tsx:124`: `{row.value ? formatNumber(row.value) : ""}`.

### F05.1 — `setPath` brace bug → diff at wrong depth

Repro mutates `state.metadata["LOOK_HERE"]["nested_key"]` → patch path `/metadata/LOOK_HERE/nested_key`. After switching to Debug filter and expanding the State Updated panel:
```
LOOK_HERE jsondiffpatch ancestors: []
--- diff ---
STATE UPDATED
LOOK_HERE
nested_key
"BEFORE (this value should appear under metadata → LOOK_HERE → nested_key)"
"AFTER (this value should appear under metadata → LOOK_HERE → nested_key)"
```
`LOOK_HERE` appears at the top level of the diff with no `metadata` parent. The unchanged `metadata: {LOOK_HERE: {}}` branch is suppressed by jsondiffpatch (both sides identical). Source `StateEventView.tsx:292-302` — `current = current[key]` is inside the `if (!(key in current))` block.

### F05.4 — Tools preview never fires for ≥2 tool adds

**Repro rebuilt** so the bug is self-evident by comparison: the task now emits two synthetic `StateEvent`s (via `transcript()._event()`) inside one solver — a 1-tool CONTROL and a 3-tool BUG. After Debug filter:
```
1-tool panel sub-tabs:  ['SUMMARY', 'DIFF']
3-tool panel sub-tabs:  []
3-tool body: STATE UPDATED \n 0 \n { "name": "beta_tool", … } \n 1 \n { … } \n 2 \n { … }
```
Screenshots: [`artifacts/F05.4-1tool.png`](../artifacts/F05.4-1tool.png), [`artifacts/F05.4-3tools.png`](../artifacts/F05.4-3tools.png), [`artifacts/F05.4-full.png`](../artifacts/F05.4-full.png).

**What the "Tools preview" is:** when `generatePreview` (`StateEventView.tsx:105-180`) matches the `add_tools` change-type signature (`StateEventRenderers.tsx:64-74` — one `add` pattern `/tools/(\d+)`), it returns `renderTools(...)` — a grid of `<code>tool_name(arg, …)</code>` chips under a **TOOLS** label. That becomes the panel's `<div data-name="Summary">` child, so `EventPanel` renders **SUMMARY / DIFF** sub-tab pills. With no preview, the panel has only the `StateDiffView` child → no pills, raw jsondiffpatch only.

**Why the count matters:** `requiredMatchCount = signature.add.length + signature.replace.length + signature.remove.length` counts *patterns* (=1); `matchingOps` counts *changes that matched a pattern*. 1 add → `1 === 1` → preview. 3 adds → `3 !== 1` → no preview. Source `StateEventView.tsx:165`.

**Bonus interaction:** the 1-tool Summary tab body is *empty* — `synthesizeComparable` corrupts `resolvedState.tools` via the F05.1 `setPath` brace bug (writes `after["0"]` instead of `after.tools[0]`), so `renderTools` finds `tools.length === 0` and emits an empty grid. The pills' presence alone proves F05.4; the empty body is F05.1's fault.

### F05.5 — falsy edited score value hidden

Three ScoreEditEvents with `value=0`, `value=False`, `value=""`:
```
Edit[0]: VALUE label present=False
Edit[1]: VALUE label present=False
Edit[2]: VALUE label present=False
```
Source `ScoreEditEventView.tsx:50`: `{event.edit.value ? <Fragment>…<ScoreValue …/></Fragment> : ""}`.

### F05.6 — ScoreEdit Metadata not a separate tab

```
Edit Score sub-tabs: []
metadata MARKER visible inline in body: True
(contrast) Score event sub-tabs: ['EXPLANATION', 'METADATA']
```
The Edit Score panel has no pill nav (single direct child); the `MARKER` text from `edit.metadata` renders inline at the bottom. The sibling Score event correctly shows a separate `METADATA` tab. Source `ScoreEditEventView.tsx:39,118-127` — `<div data-name="Metadata">` is a child of `<div data-name="Summary">`, not of `EventPanel`.

### F05.9 — SandboxEvent ExecView `=== null` misses `undefined`

```
SANDBOX: EXEC
COMMAND
RESULT
(stdout from a sandbox exec whose cmd field was omitted)
(exited with code 1)
--- first <pre> (cmd) text: ''
```
`Command` heading + empty `<pre>` rendered. Source `SandboxEventView.tsx:57`: `if (event.cmd === null) { return undefined; }` — `.eval` recorder serialises with `exclude_none=True` so `cmd` arrives as `undefined`.

### F05.11 — SampleInit omits `sample.sandbox` / `sample.id`

After Debug filter, expanded the `INIT` span wrapper to mount the inner `Sample` panel. Checked `.text-style-label` cells across both sub-tabs:
```
sub-tabs: ['SAMPLE', 'METADATA']
label cells: ['FINDING_ID', 'METADATA', 'SAMPLE']
Files section: True; Setup section: True
Sandbox label/section: False; ID label: False
```
Files / Setup / Target / Metadata all rendered; no `Sandbox` or `ID` row. Source `SampleInitEventView.tsx:30-108` never reads `event.sample.sandbox` or `event.sample.id`. (Free text from the bug-description message contains "sandbox"/"local"/the id, but those are inside the ChatView body, not label cells.)

### F05.12 — BranchEvent discards `event.metadata`

```
BRANCH (0 SEC)
FROM_SPAN     origin-span-id-12345
FROM_MESSAGE  origin-message-id-abcde
```
Sentinel `IF THIS METADATA IS NOT VISIBLE IN THE BRANCH EVENT` (from `event.metadata.MARKER`) absent; `branch_reason` / `branch_index` absent. Source `BranchEventView.tsx:23-29` builds `data` from `from_span`/`from_message` only.

## Files written / modified

| Path | Purpose |
|---|---|
| `findings/repros/verify/checks/_util.py` | `show_all_events()` — switch transcript filter to Debug |
| `findings/repros/verify/checks/F01_1.py` | new |
| `findings/repros/verify/checks/F01_2.py` | updated (better evidence capture) |
| `findings/repros/verify/checks/F01_3.py` | new |
| `findings/repros/verify/checks/F04_5.py` | new |
| `findings/repros/verify/checks/F04_7.py` | new |
| `findings/repros/verify/checks/F05_1.py` | new |
| `findings/repros/verify/checks/F05_4.py` | new |
| `findings/repros/verify/checks/F05_5.py` | new |
| `findings/repros/verify/checks/F05_6.py` | new |
| `findings/repros/verify/checks/F05_9.py` | new |
| `findings/repros/verify/checks/F05_11.py` | new |
| `findings/repros/verify/checks/F05_12.py` | new |
| `findings/repros/tasks/01-events/F01.2_tool_choice_literal_dollar.py` | **repro fixed** — synthetic ModelEvent with 2× ToolInfo |
| `findings/repros/logs/01-events/…F01.2-tool-choice-literal-dollar….eval` | **regenerated** |
| `findings/repros/tasks/01-events/F05.4_state_tools_preview_count.py` | **repro rebuilt** — two synthetic StateEvents (1-tool CONTROL vs 3-tool BUG) |
| `findings/repros/logs/01-events/…F05.4-state-tools-preview-count….eval` | **regenerated** |
| `findings/repros/verify/checks/F05_4.py` | updated — compares both panels' sub-tabs |
| `findings/repros/verify/artifacts/F05.4-{1tool,3tools,full}.png` | new |
