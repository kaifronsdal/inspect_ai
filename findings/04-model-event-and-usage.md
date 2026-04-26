# ModelEvent Rendering & Token-Usage Display

**Reviewer scope:** `packages/inspect-components/src/usage/**`, `packages/inspect-components/src/transcript/ModelEventView.tsx`, `transcript/event/{EventPanel,EventSection,EventTimingPanel,utils}.ts*`, cross-referenced against `inspect-common/types/generated.ts` (`ModelEvent`, `ModelOutput`, `ModelUsage`, `ModelCall`, `GenerateConfig`) and Python `model/_model_output.py`, `event/_model.py`.
**Date:** 2026-04-22

---

## Summary

ModelEventView is functional but drops several backend fields silently (`retries`, `cache`, `traceback`, `total_cost`, `stop_reason`, `output.error`, `metadata`). The Summary-tab message-collection logic has an off-by-one slice bug that hides preceding user/system messages whenever input ends with an assistant (compaction) message. The Tools tab is hidden when exactly one tool is defined (`> 1` instead of `> 0`). `ModelUsagePanel` has inconsistent label casing, renders `0` as blank, and never surfaces `total_cost`. Several minor typos (`text-sixe-small`), dead fields (`bordered`), and dead CSS classes were found.

---

## Findings

### F04.1 — Summary tab drops preceding messages when input ends with assistant message

- **Severity:** HIGH
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ModelEventView.tsx:67-86`
- **Category:** correctness

**Description:**
When the last input message is `assistant` (e.g. a compaction message), the code sets `offset = -1` and then calls `event.input.slice(offset)`. `Array.slice(-1)` returns **only the last element**, not "everything except the last". The subsequent reverse-scan therefore iterates over `[assistantMsg]`, immediately hits the `else { break; }` branch, and collects nothing. The Summary tab shows only the trailing assistant message and the model output — the user/system messages that immediately preceded it are silently dropped.

**Evidence:**
```tsx
let offset: number | undefined = undefined;
const lastMessage = event.input.at(-1);
if (lastMessage?.role === "assistant") {
  userMessages.push(lastMessage);
  offset = -1;
}
for (const msg of event.input.slice(offset).reverse()) {
  if ((msg.role === "user" && !msg.tool_call_id) || msg.role === "system" || ...) {
    userMessages.unshift(msg);
  } else {
    break;
  }
}
```

**Why it matters / impact:**
After a compaction, the Summary view loses the user prompt that triggered the model call. Users must switch to the "All" tab to see what was actually sent.

**Suggested fix:**
`event.input.slice(0, offset).reverse()` (with `offset` remaining `undefined` or `-1`).

---

### F04.2 — Tools tab hidden when exactly one tool is defined

- **Severity:** HIGH
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ModelEventView.tsx:198`
- **Category:** event-display

**Description:**
The Tools tab is gated on `event.tools.length > 1`. With exactly one tool, the tab (and the `tool_choice` display inside it) is never rendered.

**Evidence:**
```tsx
{event.tools.length > 1 && (
  <div data-name="Tools" className={styles.container}>
    <ToolsConfig tools={event.tools} toolChoice={event.tool_choice} />
  </div>
)}
```

**Why it matters / impact:**
Single-tool agents (very common — e.g. `bash`-only, `submit`-only) show no tool definition and no `tool_choice` anywhere in the event UI.

**Suggested fix:**
`event.tools.length > 0`.

---

### F04.3 — ToolChoiceView renders literal `` `$name()` `` instead of `name()`

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ModelEventView.tsx:312`
- **Category:** correctness

**Description:**
JSX text does not interpret backticks as template literals. The expression renders a literal backtick, a literal `$`, the function name, `()`, and a closing backtick.

**Evidence:**
```tsx
const ToolChoiceView: FC<ToolChoiceViewProps> = ({ toolChoice }) => {
  if (typeof toolChoice === "string") {
    return toolChoice;
  } else {
    return <code>`${toolChoice.name}()`</code>;
  }
};
```

**Why it matters / impact:**
When `tool_choice` is a forced function, the UI shows `` `$my_tool()` `` instead of `my_tool()`.

**Suggested fix:**
`<code>{toolChoice.name}()</code>`.

---

### F04.4 — `total_cost` is never displayed

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/usage/ModelUsagePanel.tsx:10-17` (and all consumers)
- **Category:** event-display

**Description:**
`ModelUsage.total_cost` exists in the schema (`generated.ts:2126`) and Python (`_model_output.py:40`), but `ModelUsageData` omits it and `ModelUsagePanel` never renders it. No other component in `usage/` or `ModelEventView` surfaces cost.

**Evidence:**
```ts
export interface ModelUsageData {
  input_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;
  reasoning_tokens?: number | null;
  input_tokens_cache_read?: number | null;
  input_tokens_cache_write?: number | null;
}
// no total_cost
```

**Why it matters / impact:**
Cost is the single most actionable usage metric; it is computed on the backend and silently dropped by the viewer everywhere (per-event, per-sample, per-eval Models tab).

**Suggested fix:**
Add `total_cost` to `ModelUsageData` and render a "Cost" row (formatted as currency) in `ModelUsagePanel`.

---

### F04.5 — `event.retries` and `event.cache` never displayed

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ModelEventView.tsx`
- **Category:** event-display

**Description:**
`ModelEvent.retries: int | None` (number of API retry attempts) and `ModelEvent.cache: "read" | "write" | None` (Inspect-level model-response cache hit/miss) are present in the schema (`generated.ts:2025,2055`) but read nowhere in the renderer.

**Why it matters / impact:**
Users debugging flaky model calls cannot see that a call was retried N times. Users debugging cached evals cannot tell whether a given output came from the cache or a live API call — this directly affects interpretation of `output.time` and token billing.

**Suggested fix:**
Show a small badge in the event title (e.g. "cached", "3 retries") and/or rows in the "All" tab.

---

### F04.6 — Model error traceback (`traceback` / `traceback_ansi`) not rendered

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ModelEventView.tsx:150-153`
- **Category:** event-display

**Description:**
On error, only `event.error` (a one-line string) is shown. `event.traceback` and `event.traceback_ansi` are present on the schema (`generated.ts:2067-2069`) but never rendered. By contrast, `ErrorEventView.tsx:32` does render `error.traceback_ansi`.

**Why it matters / impact:**
Model-provider exceptions (timeouts, malformed responses, SDK bugs) lose their stack trace in the UI. Users must open the raw log file to debug.

**Suggested fix:**
When `event.traceback_ansi` is set, render it below the error string using the same `ANSIDisplay` pattern as `ErrorEventView`.

---

### F04.7 — `output.error` and `stop_reason` not displayed

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ModelEventView.tsx:46-48,150`
- **Category:** event-display

**Description:**
`ModelOutput.error` (content-moderation refusal text, `_model_output.py:163`) is distinct from `ModelEvent.error` and is never read. `ChatCompletionChoice.stop_reason` (`stop` / `max_tokens` / `model_length` / `content_filter` / `tool_calls` / `unknown`) is also never surfaced — only `choice.message` is extracted.

**Why it matters / impact:**
A truncated completion (`max_tokens` / `model_length`) or content-filter refusal is indistinguishable from a normal completion in the UI. This is a frequent debugging need.

**Suggested fix:**
Render `stop_reason` per choice when ≠ `"stop"` and ≠ `"tool_calls"`; render `output.error` in the Error section if present.

---

### F04.8 — Zero-valued token counts render as blank

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/usage/ModelUsagePanel.tsx:124-126`
- **Category:** correctness / fallback-hiding-errors

**Description:**
The truthiness check `row.value ? formatNumber(row.value) : ""` treats `0` as falsy, so a legitimate `0` (e.g. `input_tokens: 0` on a fully-cached request, or `output_tokens: 0` on an error) renders as an empty cell rather than "0".

**Evidence:**
```tsx
<div className={styles.col3}>
  {row.value ? formatNumber(row.value) : ""}
</div>
```

**Why it matters / impact:**
Users see a blank where they expect a number and may assume the field is missing/unsupported rather than genuinely zero.

**Suggested fix:**
`row.value !== undefined && row.value !== null ? formatNumber(row.value) : ""`.

---

### F04.9 — Inconsistent label casing in ModelUsagePanel

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/usage/ModelUsagePanel.tsx:44,59,66,74,82,94`
- **Category:** consistency

**Description:**
Row labels mix title-case, lowercase, and snake_case: `"Reasoning"`, `"input"`, `"cache_read"`, `"cache_write"`, `"Output"`, `"Total"`. The `text-style-label` class uppercases them at render time so the visual impact is masked, but the raw inconsistency leaks into snapshots, copy-paste, and screen readers.

**Suggested fix:**
Normalise to `"Input"`, `"Cache read"`, `"Cache write"`, etc.

---

### F04.10 — Typo `text-sixe-small` in TokenTable header

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/usage/TokenTable.tsx:51,61`
- **Category:** styling

**Description:**
Two `<th>` elements use class `"text-sixe-small"` instead of `"text-size-small"`. The class does not exist, so the intended font sizing is not applied to the "Model" / "Usage" column headers.

**Evidence:**
```tsx
<th className={clsx(styles.tableH, "text-sixe-small", "text-style-label", ...)}>
```

---

### F04.11 — TokenHeader `colSpan={3}` mismatches 2-column body

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/usage/TokenTable.tsx:32-46`
- **Category:** dead-code / code-smell

**Description:**
The first header row is `<td></td><td colSpan={3}>Tokens</td>` (4 logical columns), but the second header row and `TokenRow` only emit 2 `<td>` cells. Vestigial from an older multi-column layout (input/output/total). Browsers tolerate it but the markup is misleading.

---

### F04.12 — `bordered` field on `ModelUsageRow` is set but never read

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/usage/ModelUsagePanel.tsx:28,47,84,101-130`
- **Category:** dead-code

**Description:**
`ModelUsageRow.bordered` is declared and set `true` on the Reasoning and Output rows, but the render loop never references `row.bordered`. (The same is true of `EventTimingPanelRow.bordered` in `EventTimingPanel.tsx:19`.)

---

### F04.13 — Dead CSS classes

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ModelEventView.module.css:18-20`; `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/usage/UsageCard.module.css:10-14`
- **Category:** dead-code

**Description:**
`.tools` in `ModelEventView.module.css` and `.col1` in `UsageCard.module.css` are defined but never referenced from their corresponding `.tsx` files.

---

### F04.14 — `formatTitle` `role` param is dead; title logic duplicated

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/event/utils.ts:101-117`; `ModelEventView.tsx:96-98`
- **Category:** dead-code / consistency

**Description:**
`formatTitle(title, total_tokens, working_start, role?)` has a `role` param that no caller passes (grep confirms 5 call sites, none pass arg 4). Separately, `ModelEventView.tsx:96-98` re-implements the exact `Model Call (${role}): ${model}` string already provided by `eventTitle()` at `utils.ts:31-33` — drift risk.

---

### F04.15 — `event.metadata` and `output.metadata` not displayed

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ModelEventView.tsx`
- **Category:** event-display

**Description:**
`ModelEvent.metadata` (`generated.ts:2046`) and `ModelOutput.metadata` (`generated.ts:2095`) are arbitrary provider/user metadata dicts. Neither is rendered in any tab. `MetaDataGrid` is already imported and used for `config`, so adding a "Metadata" section would be trivial.

---

### F04.16 — Timeline token aggregation recomputes total instead of using `total_tokens`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/timeline/core.ts:340-352`
- **Category:** consistency

**Description:**
`getEventTokens()` returns `input + cache_read + cache_write + output`, ignoring `usage.total_tokens` and `usage.reasoning_tokens`. The ModelEvent title (`ModelEventView.tsx:41`) uses `usage.total_tokens` directly. If a provider reports `total_tokens` that differs from the component sum (or counts reasoning separately), timeline aggregates and per-event titles will disagree.

**Evidence:**
```ts
const inputTokens = usage.input_tokens ?? 0;
const cacheRead = usage.input_tokens_cache_read ?? 0;
const cacheWrite = usage.input_tokens_cache_write ?? 0;
const outputTokens = usage.output_tokens ?? 0;
return inputTokens + cacheRead + cacheWrite + outputTokens;
```

**Suggested fix:**
Prefer `usage.total_tokens` when present; fall back to the sum.

---

### F04.17 — `formatTitle` third param means "duration" for ModelEvent but "start offset" elsewhere

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/event/utils.ts:104`; `ModelEventView.tsx:42,108`; `BranchEventView.tsx:34`; `CompactionEventView.tsx:38`
- **Category:** consistency

**Description:**
The param is named `working_start`. `ModelEventView` passes `event.output.time` (call **duration**). `ToolEventView` passes `event.working_time` (**duration**). `BranchEventView`/`CompactionEventView` pass `event.working_start` (**offset from sample start**). All are formatted identically with `formatTime()`, so "(5 sec)" in a model title means "took 5s" while "(5 sec)" in a branch title means "at t=5s". Not a rendering bug, but a naming/semantics hazard.

---

### F04.18 — APIView ignores `ModelCall.time` and `ModelCall.error`

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ModelEventView.tsx:222-241`
- **Category:** event-display

**Description:**
`APIView` renders only `call.request` and `call.response` JSON. `ModelCall.time` (per-attempt wall time, `generated.ts:2002`) and `ModelCall.error` (`generated.ts:1992`) are not shown. Secret redaction is handled server-side (`_model_call.py` filter), so no redaction concern in the viewer.

---

### F04.19 — `EventTimingPanel` docstring says "Renders the ModelUsagePanel component"

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/event/EventTimingPanel.tsx:23-25`
- **Category:** code-smell

**Description:**
Copy-paste docstring; should say "EventTimingPanel".

---

## Files reviewed

- [x] `packages/inspect-components/src/usage/ModelUsagePanel.tsx` — core token grid; casing, zero-handling, missing cost, dead `bordered`
- [x] `packages/inspect-components/src/usage/ModelUsagePanel.module.css` — ok
- [x] `packages/inspect-components/src/usage/TokenTable.tsx` — typo `text-sixe-small`, colSpan mismatch
- [x] `packages/inspect-components/src/usage/TokenTable.module.css` — ok
- [x] `packages/inspect-components/src/usage/ModelTokenTable.tsx` — thin wrapper; ok
- [x] `packages/inspect-components/src/usage/UsageCard.tsx` — dead `.col1`
- [x] `packages/inspect-components/src/usage/UsageCard.module.css` — dead `.col1`
- [x] `packages/inspect-components/src/usage/index.ts` — ok
- [x] `packages/inspect-components/src/transcript/ModelEventView.tsx` — slice bug, `>1` bug, ToolChoice render bug, dropped fields
- [x] `packages/inspect-components/src/transcript/ModelEventView.module.css` — dead `.tools`
- [x] `packages/inspect-components/src/transcript/event/EventPanel.tsx` — collapse/tab infra; no model-specific issues
- [x] `packages/inspect-components/src/transcript/event/EventSection.tsx` — ok
- [x] `packages/inspect-components/src/transcript/event/EventTimingPanel.tsx` — wrong docstring, dead `bordered`
- [x] `packages/inspect-components/src/transcript/event/utils.ts` — dead `role` param, duplicated title logic
- [x] `packages/inspect-components/src/transcript/timeline/core.ts:340-352` — token-sum drift
- [x] `packages/inspect-common/src/types/generated.ts` (ModelEvent/ModelOutput/ModelUsage/ModelCall/GenerateConfig) — schema reference
- [x] `src/inspect_ai/model/_model_output.py` — Python `ModelUsage` reference (confirms `total_cost`)
- [x] `src/inspect_ai/event/_model.py` — Python `ModelEvent` reference (confirms `retries`, `cache`, `traceback*`)
- [x] `apps/inspect/src/app/log-view/tabs/ModelsTab.tsx` — UsageCard consumer; inherits F04.4
- [x] `apps/inspect/src/app/samples/SampleDisplay.tsx:724-736` — ModelTokenTable consumer; inherits F04.4

## Open questions / needs verification

- F04.1: confirm with a real compaction-containing log that the Summary tab indeed drops the preceding user message (logic analysis is unambiguous, but a screenshot would help prioritise).
- F04.4: is `total_cost` intentionally suppressed in the viewer (e.g. because cost calc is provisional), or just forgotten? No comment found either way.
- F04.16: verify whether any current provider populates `total_tokens` ≠ `input + cache_r + cache_w + output` (e.g. providers that count reasoning separately from output).
