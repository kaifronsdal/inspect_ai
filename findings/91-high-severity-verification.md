# HIGH-Severity Verification

**Verifier scope:** Independent re-read of every finding marked HIGH across findings files 01–05, 10–11, 30–31, 40, 50–51, 70. Each cited location was opened and surrounding context (callers, type definitions) traced. Five MEDIUM findings were also spot-checked.
**Date:** 2026-04-22

---

## F01.1 — `ModelEventView` drops preceding user/system messages when input ends with an assistant message

**Verdict:** CONFIRMED
**Evidence:** `inspect-components/src/transcript/ModelEventView.tsx:67-86`
```tsx
let offset: number | undefined = undefined;
const lastMessage = event.input.at(-1);
if (lastMessage?.role === "assistant") {
  userMessages.push(lastMessage);
  offset = -1;
}
for (const msg of event.input.slice(offset).reverse()) {
```
**Reasoning:** `Array.prototype.slice(-1)` returns a one-element array containing only the last item. The reversed loop then visits the assistant message first, fails the `user|system|tool` test, and `break`s — so `userMessages` ends up holding only the trailing assistant message. The intended `slice(0, offset)` semantics are not achieved. Reachable on any model call whose input ends with an assistant (compaction) message.

---

## F01.2 — `ToolChoiceView` renders literal `` `$ `` characters around function name

**Verdict:** CONFIRMED
**Evidence:** `inspect-components/src/transcript/ModelEventView.tsx:312`
```tsx
return <code>`${toolChoice.name}()`</code>;
```
**Reasoning:** JSX children are not template literals. The parser sees: text node `` `$ ``, JSX expression `{toolChoice.name}`, text node `` ()` ``. For `tool_choice = {name: "bash"}` the rendered text is `` `$bash()` ``. Reachable whenever `tool_choice` is an object (forced function), gated only by F04.2 (`tools.length > 1`).

---

## F01.3 — `ScoreEditEventView` renders the `"UNCHANGED"` sentinel as real data for `value` and `explanation`

**Verdict:** CONFIRMED
**Evidence:** `inspect-components/src/transcript/ScoreEditEventView.tsx:50-74` and `inspect-common/src/types/generated.ts:2380-2406`
```tsx
{event.edit.value ? (
  <Fragment>... <ScoreValue score={event.edit.value} /> ...</Fragment>
) : ""}
...
<RenderedText markdown={event.edit.explanation || ""} />
```
**Reasoning:** Schema confirms `ScoreEdit.value` / `.explanation` default to the literal string `"UNCHANGED"`. The view checks `kUnchangedSentinel` only for `answer` (L63) and `metadata` (L118). `"UNCHANGED"` is truthy, so `<ScoreValue score="UNCHANGED"/>` renders, and explanation renders the literal text as markdown. Reachable for any edit that leaves value or explanation untouched.

---

## F03.1 — `setPath` does not advance `current` when key already exists → wrong state diffs

**Verdict:** CONFIRMED
**Evidence:** `inspect-components/src/transcript/state/StateEventView.tsx:292-308`
```ts
for (let i = 0; i < keys.length - 1; i++) {
  const key = keys[i];
  if (key && !(key in current)) {
    ...
    current = current[key] as Record<string, unknown>;   // inside the if
  }
}
```
**Reasoning:** `current = current[key]` is inside the `!(key in current)` guard. When `initializeArrays()` (called immediately before, L313-334) has already created the intermediate key, the loop never advances `current`, so the final write lands at the wrong depth. Affects every multi-segment `JsonChange` path that shares a prefix with a prior change in the same event. Same bug independently reported as F05.1 and F50.2 — all three are the same line.

---

## F04.1 — Summary tab drops preceding messages when input ends with assistant message

**Verdict:** CONFIRMED (duplicate of F01.1)
**Evidence:** Same code as F01.1 above.
**Reasoning:** Independent re-derivation of F01.1 by a second reviewer; both point to the same `slice(offset)` / `slice(-1)` bug. See F01.1.

---

## F04.2 — Tools tab hidden when exactly one tool is defined

**Verdict:** PARTIAL
**Evidence:** `inspect-components/src/transcript/ModelEventView.tsx:198`
```tsx
{event.tools.length > 1 && (
  <div data-name="Tools" className={styles.container}>
```
**Reasoning:** The off-by-one is real and reachable — single-tool agents show no Tools tab. However, the same finding is reported in `01-transcript-event-renderers.md` as **F01.4 (MEDIUM)**, and MEDIUM seems more appropriate: it hides one informational tab, does not corrupt or crash anything, and the tool definition is still visible in raw JSON. **Bug confirmed; HIGH severity overstated.**

---

## F05.1 — `setPath` only descends into newly-created keys

**Verdict:** CONFIRMED (duplicate of F03.1)
**Evidence:** Same code as F03.1 above.
**Reasoning:** Third independent report of the same `setPath` brace bug. The expanded impact analysis (multi-segment paths like `/messages/0/content`) is accurate.

---

## F10.1 — Orphan tool messages are silently dropped

**Verdict:** CONFIRMED
**Evidence:** `inspect-components/src/chat/messages.ts:46-54` and `ChatMessageRow.tsx:96-101`
```ts
if (resolved.role === "tool") {
  if (resolvedMessages.length > 0) {
    const msg = resolvedMessages[resolvedMessages.length - 1];
    msg.toolMessages.push(resolved);   // any role
  }
  // else: dropped
}
```
**Reasoning:** `resolveMessages` attaches tool messages to whatever entry precedes them (regardless of role); `ChatMessageRow` only renders `toolMessages` when `resolvedMessage.message.role === "assistant"` (and `tool_calls` is non-empty). So a tool message following a user/system message, or appearing first, is collected but never rendered. Reachable for malformed/reordered conversations — the exact debugging case where the viewer matters. Note: only applies when `collapseToolMessages !== false` (the default); the `false` path in `ChatView.tsx:41-46` does render tool messages standalone (but then hits F10.2).

---

## F10.2 — Standalone tool messages never show `error` and drop most content types

**Verdict:** CONFIRMED
**Evidence:** `inspect-components/src/chat/ChatView.tsx:38-46` → `ChatMessage.tsx:43,116-126`
```tsx
const isNonTaskTool = message.role === "tool" && message.function !== "Task";
...
{isNonTaskTool ? (
  <ToolOutput output={
    typeof message.content === "string" ? message.content
      : message.content.filter((c) => c.type === "text" || c.type === "image")
  } />
) : ...}
```
**Reasoning:** When `collapseToolMessages: false`, `ChatView` bypasses `resolveMessages` and emits each tool message as its own `ResolvedMessage`, which `ChatMessageRow` renders via `<ChatMessage>`. The `isNonTaskTool` branch never reads `message.error` and pre-filters content to text|image only, even though `ToolOutput` itself handles `document`/`data`/`reasoning`. The collapsed path (`resolveToolMessage`, `ChatMessageRow.tsx:228-231`) **does** substitute `error.message` — confirmed inconsistency between the two render modes.

---

## F11.1 — Tool errors rendered identically to successful output

**Verdict:** CONFIRMED
**Evidence:** `inspect-components/src/transcript/ToolEventView.tsx:110` and `chat/ChatMessageRow.tsx:228-231`
```tsx
output={event.error?.message || event.result || ""}
```
**Reasoning:** Both render paths flatten `ToolCallError` to `.message` and feed it through the same `output` prop as success results. No `error` prop, styling, icon, or label is applied downstream in `ToolCallView`. A `timeout` failure renders as a plain grey `<pre>` indistinguishable from a tool that printed text. Contrast with `ServerToolCall.tsx` which does style errors distinctly.

---

## F11.3 — Single content-object outputs are JSON-stringified instead of rendered

**Verdict:** CONFIRMED
**Evidence:** `inspect-components/src/chat/tools/ToolCallView.tsx:240-293` and `inspect-common/src/types/generated.ts:2869`
```tsx
if (Array.isArray(output)) { return output; }
else { return [{ type: "tool", content: [{ type: "text",
  text: typeof output === "object" ? JSON.stringify(output) : String(output), ... }] }]; }
```
**Reasoning:** `normalizeContent`'s parameter type explicitly includes bare `ContentText | ContentImage | ContentAudio | ContentVideo | ContentDocument` (not array-wrapped), and the schema confirms `ToolEvent.result` can be a single content object. Such a value fails `Array.isArray`, hits the `else`, and is `JSON.stringify`'d into a text blob — a `ContentImage` renders as `{"type":"image","image":"data:..."}` instead of an `<img>`. Reachable from `ToolEventView.tsx:110` when a tool returns a bare content object.

---

## F30.1 — Per-metric score columns collide when multiple scorers share a metric name

**Verdict:** CONFIRMED
**Evidence:** `apps/inspect/src/app/log-list/grid/columns/hooks.tsx:43-63` and `LogListGrid.tsx:204-215`
```ts
for (const [metricName, metric] of Object.entries(evalScore.metrics)) {
  scoreTypes[metricName] = typeof metric.value;     // hooks.tsx
  row[`score_${metricName}`] = metric.value;         // LogListGrid.tsx
}
```
**Reasoning:** Both column discovery and row population iterate every `EvalScore` and key by bare `metricName`. With two scorers that each report `accuracy`, the inner loop overwrites `row.score_accuracy` and `scoreTypes.accuracy` — last scorer wins, header gives no attribution. Multi-scorer evals are common; the grid silently shows the wrong scorer's value with no indication.

---

## F31.1 — `EvalConfig` is built but never rendered in Task tab

**Verdict:** PARTIAL
**Evidence:** `apps/inspect/src/app/log-view/tabs/TaskTab.tsx:54-179`
```ts
const config: Record<string, unknown> = {};
Object.entries(evalSpec?.config || {}).forEach((entry) => {
  config[entry[0]] = entry[1];
});
// `config` never referenced again; component renders Task Info / Early Stopping / Task Args only
```
**Reasoning:** Verified the dead loop and that no `<Card>` consumes `config` — `EvalConfig` (epochs, limits, approval, fail_on_error, etc.) is indeed unreachable from the Task tab. **Bug confirmed.** However, HIGH feels generous: the data is still available in the JSON tab and the SecondaryBar shows a merged config summary; this is a missing-display / dead-code regression rather than data corruption. MEDIUM would be more consistent with how other "field not surfaced" findings are rated (e.g. F04.5, F31.2).

---

## F40.1 — RecordTree default-collapse logic never executes

**Verdict:** CONFIRMED
**Evidence:** `packages/react/src/hooks/useCollapsibleIds.ts:29-31` and `inspect-components/src/content/RecordTree.tsx:87-108,243`
```ts
return [(entries || {}) as Record<string, boolean>, collapseId, clearIds];   // never undefined
...
useEffect(() => {
  if (collapsedIds) { return; }   // {} is truthy → always early-returns
  ...
});
...
if (!collapsedIds) { return null; }   // unreachable
```
**Reasoning:** `useCollapsibleIds` coalesces `entries` to `{}`, so `collapsedIds` is never falsy. The default-collapse effect (`depth >= defaultExpandLevel || childCount > 5`) is therefore dead, and so is the flash-prevention guard at L243. Every `RecordTree` mounts fully expanded regardless of `defaultExpandLevel`. Reachable everywhere `RecordTree` is used (sample metadata, store, ContentDataView, score metadata).

---

## F50.1 — `isLargeSample()` always returns `true`

**Verdict:** CONFIRMED
**Evidence:** `apps/inspect/src/state/store_filter.ts:19-31` and `state/sampleSlice.ts:128-155`
```ts
export function isLargeSample(sample: EvalSample): boolean {
  if (storeKeys > 5000) return true;
  if (estimatedMessageSize > 250000) return true;
  return true;   // ← bug
}
```
**Reasoning:** Final `return true` makes the function unconditional. `sampleSlice.setSelectedSample` uses the result to choose between reactive state (`selectedSampleObject`) and a module ref (`selectedSampleRef`); because `isLarge` is always `true`, every sample goes into the ref, `sampleInState` is always `false`, and the threshold checks are wasted compute. The downstream impact (non-reactive sample, forced reload after rehydrate) described in the finding is accurate.

---

## F50.2 — `setPath()` only descends when key is missing

**Verdict:** CONFIRMED (duplicate of F03.1)
**Evidence:** Same code as F03.1 above.
**Reasoning:** Same bug, fourth independent report (F03.1 / F05.1 / F50.2 are the same line of code).

---

## F51.1 — `pending_log_promise` returns wrong log under concurrent requests

**Verdict:** CONFIRMED
**Evidence:** `apps/inspect/src/client/api/client-api.ts:98-127`
```ts
if (!cached || log_file !== current_path || !current_log) {
  if (pending_log_promise) {
    return pending_log_promise;   // no log_file comparison
  }
  pending_log_promise = api.get_log_contents(log_file, 100).then(...);
```
**Reasoning:** A single module-scoped `pending_log_promise` is reused regardless of which `log_file` it was created for. A second caller requesting a different file while the first is in flight receives the first file's contents. Only affects legacy `.json` logs (`.eval` files use `remoteEvalFile`), but the race is real and the fix is trivial.

---

## F70.1 — `map()` is lazy: log-header path validation never runs (aiohttp)

**Verdict:** CONFIRMED
**Evidence:** `src/inspect_ai/_view/server.py:291-296` and `:69-71`
```python
files = [normalize_uri(file) for file in files]
map(validate_log_file_request, files)   # iterator never consumed
return await log_headers_response(files)
```
**Reasoning:** `map()` returns a lazy iterator that is discarded; `validate_log_file_request` (which raises `HTTPUnauthorized` if the file is outside `log_dir` when no `authorization` is set) is never invoked. Every other endpoint in this file calls it directly. The FastAPI variant validates correctly. Genuine path-confinement bypass on the aiohttp fallback server.

---

## F70.2 — `stream_log_bytes` raises `ValueError` for large non-S3 files

**Verdict:** CONFIRMED
**Evidence:** `src/inspect_ai/_view/common.py:251-269`
```python
if not fs.is_async() or not fs.is_s3():
    ...
    if request_size <= stream_threshold_bytes:
        bs = await get_log_bytes(log_file, start, end)
        return BytesIO(bs)
    # >50MB non-S3 falls through

connection = async_connection(log_file)
if not isinstance(connection, S3FileSystem):
    raise ValueError("Expected S3FileSystem")
```
**Reasoning:** When the filesystem is not S3 and `request_size > 50MB`, control falls past the early-return and hits the S3-only assertion. `/api/log-download` for any local/Azure `.eval` >50 MB will 500. Reachable in the most common (local-filesystem) deployment.

---

# MEDIUM Spot-Checks (5 randomly chosen)

## F02.1 — Sandbox grouping is a no-op in span-based logs

**Verdict:** CONFIRMED
**Evidence:** `inspect-components/src/transcript/transform/fixups.ts:124-138,182-200` and `treeify.ts:152-170`
**Reasoning:** `createSpanBegin` builds the synthetic wrapper with `parent_id: null`, `id: "${name}-begin"`. The wrapped sandbox events are pushed unmodified (`result.push(...pendingSandboxEvents)`) — they keep their original `span_id`. `resolveParentForEvent` parents non-span events by `span_id` lookup, so each sandbox event lands under its original span, not the wrapper. The wrapper ends up empty and is stripped by `filterEmpty`.

## F03.2 — Timeline-options checkboxes double-toggle when clicked directly

**Verdict:** CONFIRMED
**Evidence:** `inspect-components/src/transcript/timeline/components/TimelineOptionsPopover.tsx:57-73`
**Reasoning:** Both the wrapping `<div onClick>` and the `<input onChange>` call `config.toggleMarkerKind(kind)`. `e.stopPropagation()` is on the **change** event, which does not suppress the **click** event bubbling to the div. Clicking the checkbox glyph fires both → net no-op. Same pattern repeated for utility/branches/fork-relative toggles.

## F04.8 — Zero-valued token counts render as blank

**Verdict:** CONFIRMED
**Evidence:** `inspect-components/src/usage/ModelUsagePanel.tsx:124-126`
```tsx
<div className={styles.col3}>{row.value ? formatNumber(row.value) : ""}</div>
```
**Reasoning:** `0` is falsy → empty string. A legitimate `input_tokens: 0` (fully cached) or `output_tokens: 0` (error) renders blank instead of `0`.

## F30.6 — `ViewerOptionsButton` assigns the forwarded ref to two elements

**Verdict:** CONFIRMED
**Evidence:** `apps/inspect/src/app/log-list/ViewerOptionsButton.tsx:23-34`
```tsx
<button ref={ref} ...>
  <i ref={ref} className={...} />
</button>
```
**Reasoning:** The `<i>` mounts after the `<button>` and overwrites `ref.current` with an `HTMLElement` that is not an `HTMLButtonElement`. The popover anchored to this ref positions against the icon glyph, and any caller assuming `HTMLButtonElement` semantics gets the wrong element.

## F40.3 — `MarkdownRenderQueue.cancel()` marks the wrong queued task

**Verdict:** CONFIRMED
**Evidence:** `packages/react/src/components/MarkdownDiv.tsx:219-235`
```ts
const cancel = () => {
  cancelled = true;
  const index = this.queue.findIndex((t) => !t.cancelled);
  if (index !== -1 && this.queue[index]) {
    this.queue[index].cancelled = true;   // first non-cancelled task globally
  }
};
```
**Reasoning:** `cancel` is defined outside the Promise executor scope, so `queueTask` (L219) is not capturable; instead it finds the first non-cancelled task in the entire queue. When component A unmounts while B's task is queued ahead, A's cleanup cancels B's task. The closure `cancelled` flag mostly masks the symptom, but `processQueue`'s skip-cancelled optimisation will skip the wrong job.

---

# Summary Table

| ID | Verdict | Notes |
|---|---|---|
| F01.1 | CONFIRMED | `slice(-1)` returns only last element; preceding user/system msgs dropped |
| F01.2 | CONFIRMED | JSX text node, not template literal — renders `` `$name()` `` |
| F01.3 | CONFIRMED | `"UNCHANGED"` sentinel leaks into value/explanation display |
| F03.1 | CONFIRMED | `current = current[key]` inside `!(key in current)` guard |
| F04.1 | CONFIRMED | Duplicate of F01.1 |
| F04.2 | PARTIAL | Real `> 1` off-by-one; HIGH overstated (F01.4 rates same bug MEDIUM) |
| F05.1 | CONFIRMED | Duplicate of F03.1 |
| F10.1 | CONFIRMED | Tool msgs attached to any-role predecessor; only rendered under assistant |
| F10.2 | CONFIRMED | `collapseToolMessages:false` path drops `error` + filters to text/image |
| F11.1 | CONFIRMED | Error message piped through same `output` prop as success; no styling |
| F11.3 | CONFIRMED | Bare `ContentImage` (valid per schema) hits `JSON.stringify` fallback |
| F30.1 | CONFIRMED | Column key = bare `metricName`; last scorer in array wins |
| F31.1 | PARTIAL | Dead `config` loop confirmed; HIGH generous for "field not shown" |
| F40.1 | CONFIRMED | `useCollapsibleIds` returns `{}` (truthy) → default-collapse effect dead |
| F50.1 | CONFIRMED | Final `return true` unconditional; every sample stored in ref |
| F50.2 | CONFIRMED | Duplicate of F03.1 |
| F51.1 | CONFIRMED | In-flight promise reused without comparing `log_file` |
| F70.1 | CONFIRMED | `map()` lazy iterator discarded; path-confinement check never runs |
| F70.2 | CONFIRMED | Non-S3 >50 MB falls through to `isinstance(S3FileSystem)` assertion |
| **— MEDIUM spot-checks —** | | |
| F02.1 | CONFIRMED | Synthetic span `parent_id:null`, sandbox events keep original `span_id` |
| F03.2 | CONFIRMED | `stopPropagation` on `change` doesn't stop `click` bubbling to wrapper |
| F04.8 | CONFIRMED | `row.value ?` truthy check hides `0` |
| F30.6 | CONFIRMED | Same `ref` on `<button>` and child `<i>` |
| F40.3 | CONFIRMED | `findIndex` over global queue, not the enqueued task |

**Totals:** 19 HIGH findings checked → 17 CONFIRMED, 2 PARTIAL (severity overstated), 0 REFUTED. 5 MEDIUM spot-checks → 5 CONFIRMED.

**De-duplication note:** F01.1 ≡ F04.1; F03.1 ≡ F05.1 ≡ F50.2; F04.2 ≡ F01.4 (rated MEDIUM in 01). After de-dup there are **14 unique HIGH-candidate bugs**, of which 12 stand as HIGH and 2 (F04.2, F31.1) are recommended downgrade to MEDIUM.
