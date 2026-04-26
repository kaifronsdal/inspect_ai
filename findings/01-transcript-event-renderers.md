# Transcript Event Renderers

**Reviewer scope:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/event/` (all files) + all `*EventView.tsx` renderers in `transcript/` that consume them. Cross-referenced against `inspect-common/src/types/generated.ts` and `inspect_ai/event/*.py`.
**Date:** 2026-04-22

---

## Summary

The `event/` subdirectory contains the shared panel/nav/section primitives; the actual per-event renderers live one level up in `transcript/`. Both were reviewed. Overall structure is sound, but there are several genuine display bugs (wrong data shown, fields silently dropped due to off-by-one slicing or truthy checks), a sentinel-handling bug in score edits, significant duplication between `SpanEventView`/`StepEventView`, and a large consistency gap where ~half the renderers don't receive `eventCallbacks` and so cannot show deep-link URLs. Several exported helpers (`eventTitle`, `EventProgressPanel`, `formatTitle`'s `role` param) have no callers anywhere in the monorepo.

---

## Findings

### F01.1 — `ModelEventView` drops preceding user/system messages when input ends with an assistant message

- **Severity:** HIGH
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ModelEventView.tsx:67-86`
- **Category:** correctness

**Description:**
When the last input message is an assistant message (compaction case), `offset` is set to `-1` and the loop iterates `event.input.slice(offset)`. `Array.slice(-1)` returns **only the last element**, not "everything except the last element". The loop therefore re-visits the assistant message, hits the `else { break; }` branch immediately, and never collects the user/system messages that precede it.

**Evidence:**
```tsx
let offset: number | undefined = undefined;
const lastMessage = event.input.at(-1);
if (lastMessage?.role === "assistant") {
  userMessages.push(lastMessage);
  offset = -1;
}
for (const msg of event.input.slice(offset).reverse()) {   // slice(-1) → [lastMessage]
  if ((msg.role === "user" && !msg.tool_call_id) || ...) {
    userMessages.unshift(msg);
  } else { break; }
}
```

**Why it matters / impact:**
The "Summary" tab shows only `[assistant compaction msg, output]` instead of `[...preceding user/system, assistant, output]`. The comment at L53 explicitly says preceding user messages should be shown.

**Suggested fix:**
`event.input.slice(0, offset).reverse()` (with `offset` left `undefined` → slice to end; `-1` → exclude last).

---

### F01.2 — `ToolChoiceView` renders literal `` `$ `` characters around function name

- **Severity:** HIGH
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ModelEventView.tsx:308-313`
- **Category:** correctness

**Description:**
JSX child is a template literal whose backticks and `$` are inside the JSX text, not delimiting it.

**Evidence:**
```tsx
return <code>`${toolChoice.name}()`</code>;
```

**Why it matters / impact:**
For `tool_choice: {name: "bash"}` the user sees `` `$bash()` `` instead of `bash()`.

**Suggested fix:**
`return <code>{toolChoice.name}()</code>;`

---

### F01.3 — `ScoreEditEventView` renders the `"UNCHANGED"` sentinel as real data for `value` and `explanation`

- **Severity:** HIGH
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ScoreEditEventView.tsx:50-74`
- **Category:** correctness

**Description:**
Per `generated.ts:2380-2406`, `ScoreEdit.value`, `.answer`, `.explanation`, `.metadata` all default to the string `"UNCHANGED"`. The view checks `kUnchangedSentinel` only for `answer` (L63) and `metadata` (L118). For `value` it does `event.edit.value ? <ScoreValue score={event.edit.value}/>` — the string `"UNCHANGED"` is truthy, so `<ScoreValue>` renders the literal text **UNCHANGED** as if it were the new score. `explanation` is rendered as markdown without any sentinel check.

**Why it matters / impact:**
A score edit that changes only the explanation will display "Value: UNCHANGED" as if the scorer literally returned that string. Misleading data display.

**Suggested fix:**
Guard `value` and `explanation` against `kUnchangedSentinel` the same way `answer` is.

---

### F01.4 — Tools tab hidden when model has exactly one tool

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ModelEventView.tsx:198`
- **Category:** event-display

**Evidence:**
```tsx
{event.tools.length > 1 && (
  <div data-name="Tools" ...>
```

**Why it matters / impact:**
A model call with a single tool shows no Tools tab; the tool definition and `tool_choice` are invisible. Almost certainly meant `> 0` / `>= 1`.

---

### F01.5 — `eventCallbacks` not threaded to most renderers → no deep-link copy button

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/TranscriptVirtualList.tsx:71-246`
- **Category:** consistency

**Description:**
`RenderedEventNode` passes `eventCallbacks` only to `model`, `state`, `store`, `span_begin`, `step`, `subtask`, `tool`. The other 12 cases (`sample_init`, `sample_limit`, `info`, `branch`, `compaction`, `logger`, `score`, `score_edit`, `input`, `error`, `approval`, `sandbox`) call their view without it, so `EventPanel` falls back to `eventCallbacks ?? {}` → `getEventUrl` undefined → copy-link button never appears.

**Why it matters / impact:**
Users can deep-link to a model event but not to an error, sandbox, or score event. Inconsistent UX with no obvious rationale.

---

### F01.6 — `ScoreEditEventView` never shows `score_name`

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ScoreEditEventView.tsx:31-38` (vs schema `generated.ts:2426`)
- **Category:** event-display

**Description:**
`ScoreEditEvent.score_name` (which scorer was edited) is the most identifying field on the event. It is read by `eventText.ts:211` for search, but the rendered panel title is the constant `"Edit Score"` and the body never mentions which score.

**Why it matters / impact:**
With multiple scorers, users cannot tell which score was edited from the transcript view.

---

### F01.7 — `ApprovalEventView` drops `approver`, `message`, `call`, `modified`

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ApprovalEventView.tsx:22-30` (vs schema `generated.ts:372-407`)
- **Category:** event-display

**Description:**
Only `decision` (as label/icon) and `explanation` are shown. `approver` (who approved), `message` (prompt shown to approver), and `modified` (the rewritten tool call when decision == "modify") are silently discarded. `eventText.ts:272` indexes `approver` for search but the view never renders it.

**Why it matters / impact:**
A "Modified" approval gives no way to see what the tool call was modified *to*.

---

### F01.8 — `CompactionEventView`: `tokens_after === 0` hidden; `type` never shown

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/CompactionEventView.tsx:24-29`
- **Category:** fallback-hiding-errors / event-display

**Evidence:**
```tsx
if (event.tokens_before) { data["tokens_before"] = ... }
if (event.tokens_after)  { data["tokens_after"]  = ... }
```

**Why it matters / impact:**
Truthy check hides `0`. A compaction that reduces to 0 tokens shows only `tokens_before`. Separately, `CompactionEvent.type` (`"summary" | "edit" | "trim"`, `generated.ts:685`) is never displayed anywhere.

---

### F01.9 — `eventTitle()` produces wrong/empty titles for `compaction`, `branch`, `state`, `store`

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/event/utils.ts:51-55,88-90`
- **Category:** correctness / dead-code

**Evidence:**
```ts
case "compaction": {
  const source = event.source && event.source !== "inspect" ? event.source : "";
  return "Compaction" + source;   // → "Compactionclaude-code" (no ": ")
}
...
default: return "";               // branch, state, store, span_end fall here
```

**Why it matters / impact:**
Missing `": "` separator vs `CompactionEventView.tsx:33` which has it. `branch` is in `EventType` but has no case → empty title. Note: `eventTitle` is exported from `index.ts:48` but `rg` finds **zero** call sites in the monorepo, so this is also potential dead code (or out-of-sync with the renderers it's supposed to mirror).

---

### F01.10 — `ToolEventView` `useMemo` depends on `event.events` instead of `childNodes`

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ToolEventView.tsx:64-78`
- **Category:** correctness

**Evidence:**
```tsx
const { approvalNode, lastModelNode } = useMemo(() => {
  const approval = childNodes.find(...);
  const lastModel = childNodes.findLast(...);
  return { approvalNode: ..., lastModelNode: ... };
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [event.events]);
```

**Why it matters / impact:**
`event.events` is a legacy `unknown[]` (always `[]` in current logs). The memo never recomputes when `childNodes` changes — the lint suppression hides a real stale-closure bug. If a child approval/model event arrives after first render (running eval), it won't appear in the summary.

---

### F01.11 — `SpanEventView`/`StepEventView` descriptor: unreachable `sample_init` branch + unused `endSpace`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/SpanEventView.tsx:95-114`, `StepEventView.tsx:90-110`
- **Category:** dead-code

**Description:**
`spanDescriptor` receives a `SpanBeginEvent`, so `event.event === "span_begin"` (L99) is always true and the trailing `else { switch (event.name) { case "sample_init": ... } }` is unreachable. Same pattern in `stepDescriptor`. The returned `endSpace` field is never read by any caller. Note `eventTitle()` in `utils.ts:59,70` *does* handle `sample_init` for both, so the title-generation paths have diverged.

---

### F01.12 — `SpanEventView` and `StepEventView` are ~95% copy-pasted

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/SpanEventView.tsx:53-115` vs `StepEventView.tsx:48-110`
- **Category:** code-smell

**Description:**
`summarize()` is byte-identical in both files. `spanDescriptor`/`stepDescriptor` differ only in which field they compare to `kSandboxSignalName` (`span_id` vs `name`). `StepEventView` doesn't memoize `text`/`childIds`; `SpanEventView` does — another drift symptom.

---

### F01.13 — `formatTitle` third parameter is named `working_start` but every caller passes a *duration*

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/event/utils.ts:101-117`
- **Category:** code-smell / consistency

**Description:**
Callers pass: `event.output.time` (ModelEventView:108), `event.working_time` (ToolEventView:89, SubtaskEventView:56), `event.working_start` (BranchEventView:34, CompactionEventView:38). So Model/Tool/Subtask titles show "(N sec)" meaning *elapsed*, while Branch/Compaction titles show "(N sec)" meaning *offset from sample start*. Same parenthetical, different semantics.

**Why it matters / impact:**
User cannot trust what "(4 sec)" means in a panel title; depends on event type. Also the 4th param `role` has no callers (dead).

---

### F01.14 — `LoggerEventView` icon map missing `trace` and `sandbox` levels

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/icons.ts:35-43` vs `generated.ts:1911`
- **Category:** event-display

**Description:**
Schema levels: `debug | trace | http | sandbox | info | warning | error | critical`. Icon map has `notset` (not in schema) and is missing `trace`/`sandbox` → falls back to `TranscriptIcons.info` via `||` at `LoggerEventView.tsx:29`.

---

### F01.15 — `SampleLimitEventView` omits `limit` value and timestamp subtitle

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/SampleLimitEventView.tsx:64-73` (vs schema `generated.ts:2265`)
- **Category:** event-display / consistency

**Description:**
`SampleLimitEvent.limit` (the numeric threshold) is never rendered — only `message`. Also unlike every other `EventPanel` consumer, no `subTitle={formatDateTime(...)}` is passed, so hovering the header shows no timestamp tooltip.

---

### F01.16 — `SubtaskEventView` fork branch uses `title=` instead of `data-name=`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/SubtaskEventView.tsx:31`
- **Category:** correctness

**Evidence:**
```tsx
body.push(<div title="Summary" className={...}>   // should be data-name
```

**Why it matters / impact:**
`EventPanel` reads `props["data-name"]` for tab labels. Because the fork branch only pushes one child it happens to render fine, but the `title` attribute becomes a browser tooltip reading "Summary" on hover, which is noise. The non-fork branch (L41) correctly uses `data-name`.

---

### F01.17 — `SubtaskEventView` label inconsistency: "Inputs" (fork) vs "Input" (subtask)

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/SubtaskEventView.tsx:32` vs `:81`
- **Category:** consistency

---

### F01.18 — `SampleInitEventView` choices use a broken React key

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/SampleInitEventView.tsx:75`
- **Category:** correctness

**Evidence:**
```tsx
<div key={`$choice-{choice}`}>
```

**Why it matters / impact:**
`${choice}` interpolation is malformed → every item gets the literal key `"$choice-{choice}"`. React will warn about duplicate keys for any sample with >1 choice.

---

### F01.19 — `EventTimingPanel`: dead `bordered` field, unreachable `secondary` branch, wrong docstring

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/event/EventTimingPanel.tsx:15-24,104`
- **Category:** dead-code

**Description:**
`EventTimingPanelRow.bordered` is declared but never set or read. `secondary` is set to `false` on every row → `row.secondary ? styles.col2 : styles.col1_3` always takes the false branch; `styles.col2` is unreachable. JSDoc at L23 reads "Renders the ModelUsagePanel component."

---

### F01.20 — `EventTimingPanel` truthy checks hide `working_start === 0`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/event/EventTimingPanel.tsx:55,67,73,79`
- **Category:** fallback-hiding-errors

**Description:**
`if (working_start || working_time)` and `if (working_start)` skip `0`. The very first event in a sample has `working_start === 0` and would lose its "Working Time → Start" row. Same pattern in `formatTiming` (`utils.ts:94`) and `formatTitle` (`utils.ts:109,112`).

---

### F01.21 — `EventPanel` `kDefaultIcon` is unreachable

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/event/EventPanel.tsx:24,166-168`
- **Category:** dead-code

**Evidence:**
```tsx
{icon ? (
  <i className={clsx(icon || kDefaultIcon, ...)} />
) : ""}
```
The `|| kDefaultIcon` is inside an `icon ?` truthy guard.

---

### F01.22 — `EventRow` silently drops children when `title` is falsy

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/event/EventRow.tsx:23-31`
- **Category:** fallback-hiding-errors

**Description:**
`contentEl = title ? <div>...{children}</div> : ""`. If a caller passes `title=""` (e.g. an unexpected approval decision that maps to empty), the entire body including `children` disappears and the card renders empty with no indication anything went wrong.

---

### F01.23 — `EventNavs` uses `nav.title` as React key

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/event/EventNavs.tsx:30`
- **Category:** code-smell

**Description:**
`key={nav.title}` — `nav.id` is available and unique; titles could collide (e.g. two tabs both falling back to `Tab N` is impossible, but two children with the same `data-name` is not).

---

### F01.24 — `ModelEvent` fields never surfaced: `retries`, `cache`, `traceback_ansi`, `output.error`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ModelEventView.tsx` (vs `generated.ts:2025,2055,2067-2069,2093`)
- **Category:** event-display

**Description:**
`event.retries` (number of API retries), `event.cache` (`"read"|"write"`), and `event.traceback_ansi` are not rendered in any tab. `event.error` is shown but `event.output.error` (provider-side refusal text) is not. Retries in particular is useful debugging info that users currently have to find in raw JSON.

---

### F01.25 — `ToolEvent` fields never surfaced: `truncated`, `agent`, `failed`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ToolEventView.tsx` (vs `generated.ts:2836,2855,2875`)
- **Category:** event-display

**Description:**
`truncated: [int, int]` indicates the result was clipped — important context that the displayed output is incomplete, but nothing in the view signals it. `agent` (handoff target) and `failed` are also unrendered.

---

### F01.26 — `StateEventView` declares `isStore` prop but never reads it

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/state/StateEventView.tsx:23,33-38,62`
- **Category:** dead-code

**Description:**
`isStore?: boolean` is in props but not destructured; the component recomputes it from `eventNode.event.event === "store"`. `TranscriptVirtualList.tsx:186-193` doesn't pass it either. Harmless but should be removed.

---

### F01.27 — `EventProgressPanel` and `eventTitle` are exported with no consumers

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/index.ts:48,78`
- **Category:** dead-code

**Description:**
`rg` across `src/` (including `apps/`) finds zero importers. `EventProgressPanel` may be intended for live-running UI in a consumer not in this repo; `eventTitle` duplicates logic that lives inline in each `*EventView` (see F01.9, F01.28).

---

### F01.28 — Approval decision labels duplicated in two places

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ApprovalEventView.tsx:33-48` and `event/utils.ts:16-22`
- **Category:** code-smell

**Description:**
`decisionLabel()` switch and `approvalDecisionLabels` record encode the same five mappings. Same applies to `sampleLimitTitles` (utils.ts:6) vs `resolve_title()` (SampleLimitEventView.tsx:23).

---

### F01.29 — `ScoreEditEventView` subtitle renders `[undefined]` if provenance timestamp missing

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ScoreEditEventView.tsx:27-29`
- **Category:** correctness

**Evidence:**
```tsx
`[${... ? formatDateTime(...) : undefined}] ${author}: ${reason || ""}`
```
The ternary's false arm yields `undefined` which is then interpolated into the string as `"[undefined]"`. Per schema `ProvenanceData.timestamp` is required so this is currently unreachable, but the guard is wrong.

---

### F01.30 — `LoggerEventView` `name` field (logger name) never shown

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/LoggerEventView.tsx:33-44`
- **Category:** event-display

**Description:**
`LoggingMessage.name` (the Python logger name, e.g. `inspect_ai.model`) is not displayed; only `level`, `message`, `filename:lineno`. Minor — filename usually suffices.

---

## Files reviewed

- [x] `transcript/event/EventNav.tsx` — single tab button; fine
- [x] `transcript/event/EventNavs.tsx` — F01.23 (key)
- [x] `transcript/event/EventPanel.tsx` — F01.21 (dead default icon)
- [x] `transcript/event/EventProgressPanel.tsx` — F01.27 (no consumers)
- [x] `transcript/event/EventRow.tsx` — F01.22 (drops children on empty title)
- [x] `transcript/event/EventSection.tsx` — clean
- [x] `transcript/event/EventTimingPanel.tsx` — F01.19, F01.20
- [x] `transcript/event/utils.ts` — F01.9, F01.13
- [x] `transcript/event/*.module.css` — `styles.col2` unreachable (F01.19); otherwise fine
- [x] `transcript/ApprovalEventView.tsx` — F01.7, F01.28
- [x] `transcript/BranchEventView.tsx` — F01.13 (semantics)
- [x] `transcript/CompactionEventView.tsx` — F01.8
- [x] `transcript/ErrorEventView.tsx` — clean (only shows traceback; `error.message` implicit in traceback)
- [x] `transcript/InfoEventView.tsx` — clean
- [x] `transcript/InputEventView.tsx` — clean
- [x] `transcript/LoggerEventView.tsx` — F01.14, F01.30
- [x] `transcript/ModelEventView.tsx` — F01.1, F01.2, F01.4, F01.24
- [x] `transcript/SampleInitEventView.tsx` — F01.18
- [x] `transcript/SampleLimitEventView.tsx` — F01.15
- [x] `transcript/SandboxEventView.tsx` — clean (renders all action variants)
- [x] `transcript/ScoreEditEventView.tsx` — F01.3, F01.6, F01.29
- [x] `transcript/ScoreEventView.tsx` — `model_usage`/`role_usage` not shown (minor)
- [x] `transcript/ScoreValue.tsx` — clean
- [x] `transcript/SpanEventView.tsx` — F01.11, F01.12
- [x] `transcript/StepEventView.tsx` — F01.11, F01.12
- [x] `transcript/SubtaskEventView.tsx` — F01.16, F01.17
- [x] `transcript/ToolEventView.tsx` — F01.10, F01.25
- [x] `transcript/TranscriptVirtualList.tsx` — F01.5; `span_end` correctly returns `null`
- [x] `transcript/state/StateEventView.tsx` — F01.26
- [x] `transcript/types.ts` — event union matches schema
- [x] `transcript/icons.ts` — F01.14
- [x] `inspect-common/src/types/generated.ts` — reference only
- [x] `inspect_ai/log/_transcript.py` + `inspect_ai/event/_event.py` — reference only

## Open questions / needs verification

- F01.5: is omitting `eventCallbacks` from non-container events intentional (perf?) or an oversight? The `EventPanel` deep-link button is gated on `linkingEnabled && getEventUrl`, both of which come from `eventCallbacks`.
- F01.27: `EventProgressPanel` / `eventTitle` may be consumed by an out-of-tree app (ts-mono is a submodule). Verify before deleting.
- F01.13: confirm with product whether Branch/Compaction title parenthetical *should* show offset-from-start (current) or be dropped, since those events have no `working_time`.
