# Transcript Transform Pipeline

**Reviewer scope:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/transform/` (all files), `transcript/hooks/` (all files), `transcript/types.ts`, `transcript/outline/tree-visitors.ts`, `transcript/TranscriptViewNodes.tsx`, `transcript/TranscriptVirtualList.tsx`, `transcript/outline/TranscriptOutline.tsx`, `timeline/hooks/useEventNodes.ts`; cross-referenced against `inspect-common/src/types/generated.ts`, `inspect_ai/event/_span.py`, `inspect_ai/event/_event.py`, `inspect_ai/util/_span.py`.
**Date:** 2026-04-22

---

## Summary

The transform pipeline (raw `Event[]` → `EventNode` tree → flattened render list) is structurally sound for the happy path of modern span-based logs, but contains several broken legacy/fixup code paths that silently produce wrong tree shapes rather than failing. The two synthetic-span injectors (`groupSandboxEvents`, `injectScorersSpan`) are both broken in span mode: they create wrapper spans whose `id`/`parent_id` don't line up with how `treeifyWithSpans` resolves parents, so the wrappers end up empty and are stripped by `filterEmpty`. Several depth-adjustment helpers (`unwrapNode`, `reduceDepth`, `skipThisNode`) have off-by-one/non-recursive bugs that cause visible mis-indentation. There is also a cluster of dead code (unused `flush`, `parentOverride`, `SUBTASK`) and `?? null` fallbacks that silently re-parent orphaned events to root with no diagnostic.

---

## Findings

### F02.1 — Sandbox grouping is a no-op in span-based logs

- **Severity:** MEDIUM
- **Location:** `transcript/transform/fixups.ts:118-163`, `transcript/transform/fixups.ts:182-200` (related: `transcript/transform/treeify.ts:56-59`, `transcript/transform/treeify.ts:152-170`)
- **Category:** correctness

**Description:**
`groupSandboxEvents` wraps consecutive `sandbox` events in a synthetic `span_begin`/`span_end` pair, but the synthetic span has `parent_id: null` and `id: "${name}-begin"`, and the wrapped sandbox events are pushed **unmodified** — they retain their original `span_id`. `treeifyWithSpans` parents non-span events by `span_id` and span-begin events by `parent_id`/`id`, so: (a) the synthetic wrapper becomes a root node keyed as `"${name}-begin"`; (b) every sandbox event is parented to its *original* enclosing span, not the wrapper; (c) the wrapper has zero children and is then removed by `filterEmpty` in `useEventNodes.ts`.

**Evidence:**
```ts
// fixups.ts:124-138
const pushPendingSandboxEvents = () => {
  ...
  result.push(createSpanBegin(kSandboxSignalName, timestamp, null));
  result.push(...pendingSandboxEvents);          // <-- span_id unchanged
  result.push(createSpanEnd(kSandboxSignalName, timestamp));
};
// treeify.ts:164-166
const spanId = (event as { span_id?: string | null }).span_id;
return spanNodes.get(spanId) ?? null;            // <-- resolves to original parent
```

**Why it matters / impact:**
In any log that uses spans (all logs since ~2024), consecutive sandbox events render individually under their real parent instead of being collapsed into a single "Sandbox Events" group. The whole `kSandboxSignalName` machinery (special-cased in `SpanEventView`, `StepEventView`, `OutlineRow`, `event/utils.ts`) is dead weight for modern logs. Users see N separate sandbox rows where they should see one collapsible group.

**Suggested fix:**
Rewrite each sandbox event's `span_id` to the synthetic span's `id` before pushing, and set the synthetic span's `parent_id` to the first sandbox event's original `span_id`. Also give each synthetic group a unique `id` (currently every group reuses `"${kSandboxSignalName}-begin"`).

---

### F02.2 — `injectScorersSpan` synthetic span keyed by wrong field

- **Severity:** MEDIUM
- **Location:** `transcript/transform/treeify.ts:179-214` (related: `treeify.ts:57-59`, `treeify.ts:156-160`)
- **Category:** correctness

**Description:**
The synthetic "scorers" wrapper is created with `id: kBeginScorerId` and `span_id: kScorersSpanId`. `treeifyWithSpans` registers span nodes in `spanNodes` keyed by `event.id` (`kBeginScorerId`), but the re-parented scorer span is given `parent_id: kScorersSpanId`. `resolveParentForEvent` looks up `spanNodes.get(parentId)` → `spanNodes.get(kScorersSpanId)` → `undefined` → root.

**Evidence:**
```ts
const beginSpan: SpanBeginEvent = {
  name: "scorers",
  id: kBeginScorerId,            // <-- stored in spanNodes under this key
  span_id: kScorersSpanId,
  ...
};
const scoreEvents = collectedScorerEvents.map((event) => ({
  ...event,
  parent_id: event.event === "span_begin"
    ? event.parent_id || kScorersSpanId   // <-- looked up by this key
    : null,
}));
```

**Why it matters / impact:**
For legacy logs (scorer spans present, no `scorers` wrapper), the injected wrapper never receives its children. The wrapper renders empty (then stripped by `filterEmpty`), and scorer spans land at root. The fixup is silently broken.

**Suggested fix:**
Set `id: kScorersSpanId` on the synthetic begin event (or reparent children to `kBeginScorerId`).

---

### F02.3 — `injectScorersSpan` only wraps the first scorer; subsequent scorers escape

- **Severity:** MEDIUM
- **Location:** `transcript/transform/treeify.ts:238-264`
- **Category:** correctness

**Description:**
After the first scorer span's `span_end` is hit, `flushCollected()` runs and sets `hasCollectedScorers = true`. The guard `!hasCollectedScorers` on line 247 then prevents `collecting` from ever being set again, so the 2nd…Nth scorer spans pass straight through to `results` without being wrapped. Additionally, `event.parent_id || kScorersSpanId` (line 210) preserves any non-null original `parent_id`, so even the first scorer is only re-parented when its original `parent_id` was falsy.

**Evidence:**
```ts
if (event.event === SPAN_BEGIN && event.type === TYPE_SCORER && !hasCollectedScorers) {
  collecting = event.span_id ?? null;
}
...
if (event.event === SPAN_END && event.span_id === collecting) {
  collecting = null;
  results.push(...flushCollected());    // sets hasCollectedScorers = true
  results.push(event);
}
```

**Why it matters / impact:**
A multi-scorer eval viewed from a legacy log shows one synthetic "scorers" group containing scorer #1, with scorers #2…N as siblings outside it — the opposite of the stated intent ("injects a scorer span around top level scorer events").

**Suggested fix:**
Collect *all* consecutive `type === "scorer"` spans before flushing once; force `parent_id = kScorersSpanId` unconditionally on collected `span_begin` events.

---

### F02.4 — `unwrapNode` only adjusts immediate-child depth, not descendants

- **Severity:** MEDIUM
- **Location:** `transcript/transform/transform.ts:203-208` (related: `transform.ts:79-83`)
- **Category:** event-display

**Description:**
`unwrapNode` (used by `unwrap_main`) sets `child.depth = node.depth` for direct children only; grandchildren keep their original depth. Since `transformTree` runs depth-first (children already processed), a `main` span at depth 0 with child at depth 1 and grandchild at depth 2 becomes: child→0, grandchild→2 (gap). Contrast with `discardNode` which correctly uses recursive `reduceDepth`.

**Evidence:**
```ts
const unwrapNode = (node: EventNode): EventNode[] => {
  return node.children.map((child) => {
    child.depth = node.depth;     // no recursion
    return child;
  });
};
```

**Why it matters / impact:**
`depth` directly drives left-padding in `TranscriptVirtualListComponent.tsx:178` and `OutlineRow.tsx:57`. If a `type === "main"` span ever appears (none found in current Python emitters — see F02.18), the entire subtree below depth-1 renders one indent level too deep.

**Suggested fix:**
Replace body with `return reduceDepth(node.children, 1);` (after fixing F02.5).

---

### F02.5 — `reduceDepth` recursion hard-codes `1`, breaking `skipThisNode`

- **Severity:** MEDIUM
- **Location:** `transcript/transform/transform.ts:216-238`
- **Category:** event-display

**Description:**
`reduceDepth(nodes, depth)` reduces top-level nodes by `depth` but always recurses with `1`, so deeper levels are reduced by 1 regardless. `skipThisNode` (handoff unwrap) calls `reduceDepth(newNode.children, 2)` and also sets `newNode.depth = node.depth`. Net effect for a handoff at depth D: tool→D, tool.children→D+2−2=D (same as parent!), tool.grandchildren→D+3−1=D+2 (skips D+1).

**Evidence:**
```ts
const skipThisNode = (node: EventNode): EventNode => {
  const newNode = { ...node.children[0] };
  newNode.depth = node.depth;
  newNode.children = reduceDepth(newNode.children || [], 2);  // <-- 2, then 1, 1, ...
  return newNode as EventNode;
};
const reduceDepth = (nodes, depth = 1) => nodes.map((node) => {
  if (node.children.length > 0) node.children = reduceDepth(node.children, 1); // ignores depth
  node.depth = node.depth - depth;
  return node;
});
```

**Why it matters / impact:**
Handoff agent transcripts render with the tool node and its immediate children at the *same* indent, then grandchildren jump two levels right. Visually broken nesting in the transcript view for `type === "handoff"` spans.

**Suggested fix:**
Either pass `depth` through the recursion, or change `skipThisNode` to `reduceDepth(newNode.children, 1)` (since the tool moves D+1→D, children should move D+2→D+1, i.e. delta 1).

---

### F02.6 — `flatTree` writes `parentNode.children = visitorResult` per-child (dead/misleading)

- **Severity:** LOW
- **Location:** `transcript/transform/flatten.ts:28-37`
- **Category:** code-smell

**Description:**
Inside the per-child loop, after each visitor runs, the *single child's* result is assigned to `parentNode.children`, clobbering all siblings. This assignment is then immediately overwritten by the caller (`pendingNode.children = children` at line 47), so it has no observable effect — but it reads as a serious bug and obscures intent.

**Evidence:**
```ts
for (const pendingNode of pendingNodes) {
  const visitorResult = visitor.visit(pendingNode);
  if (parentNode) {
    parentNode.children = visitorResult;   // overwritten for every sibling, then by caller
  }
  allResults.push(...visitorResult);
}
```

**Why it matters / impact:**
No runtime impact today, but anyone modifying `flatTree` (e.g. removing the post-assignment at line 47) would silently lose all-but-last siblings.

**Suggested fix:**
Delete lines 32-34.

---

### F02.7 — `flatTree` visitor path mutates `.children` to flattened descendants; no-visitor path doesn't

- **Severity:** LOW
- **Location:** `transcript/transform/flatten.ts:40-51` vs `flatten.ts:60-65`
- **Category:** consistency

**Description:**
With visitors: `pendingNode.children = children` where `children` is the *fully flattened descendant list* (not just immediate children). Without visitors: `node.children` is left untouched (original tree). `OutlineRow.tsx:67,114` reads `node.children.length` to decide whether to show an expand toggle — so outline nodes (visitor path) report descendant count while transcript nodes (no-visitor path) report immediate-child count.

**Why it matters / impact:**
Subtle behavioural divergence between the two `flatTree` code paths for the same tree. Works today by coincidence (both are non-zero iff the other is), but undocumented and surprising.

**Suggested fix:**
Either don't reassign `.children` in the visitor branch, or document that `flatTree` returns nodes whose `.children` is the flattened-descendant list.

---

### F02.8 — Orphaned `span_id` / `parent_id` silently reparented to root

- **Severity:** LOW
- **Location:** `transcript/transform/treeify.ts:152-170`, `treeify.ts:75-79`
- **Category:** fallback-hiding-errors

**Description:**
`resolveParentForEvent` returns `spanNodes.get(parentId) ?? null` and `spanNodes.get(spanId) ?? null`. An event referencing a non-existent span (corrupted log, out-of-order stream, or — as in F02.1/F02.2 — a buggy synthetic span) is silently placed at root with no console warning. `treeifyWithSteps` similarly swallows unmatched `end` via the `if (stack.length > 0)` guard in `popStack`.

**Why it matters / impact:**
Malformed transcripts render "fine" but with wrong structure, making the underlying data bug invisible. This masked F02.1 and F02.2.

**Suggested fix:**
`console.warn` when a lookup misses (dev builds only is fine).

---

### F02.9 — `groupSandboxEvents` uses *last* event's timestamp for the begin marker

- **Severity:** LOW
- **Location:** `transcript/transform/fixups.ts:125-126`
- **Category:** correctness

**Description:**
Both the synthetic begin and end events use `pendingSandboxEvents[length-1].timestamp`. The begin marker should use the *first* event's timestamp so the group's apparent start time and duration are correct in the timeline.

**Evidence:**
```ts
const timestamp = pendingSandboxEvents[pendingSandboxEvents.length - 1]?.timestamp || "";
result.push(createSpanBegin(kSandboxSignalName, timestamp, null));  // begin == end timestamp
```

---

### F02.10 — `noScorerChildren` visitor never resets state

- **Severity:** LOW
- **Location:** `transcript/outline/tree-visitors.ts:36-66`
- **Category:** correctness

**Description:**
Closure flags `inScorers` / `inScorer` / `currentDepth` are set on entry but never cleared. After the scorers section, any later node at `depth === currentDepth + 1` is dropped from the outline. In practice scoring is the last phase so this doesn't fire, but a log with post-scoring spans (e.g. `score_edit` injected into a sibling span) would lose outline rows.

---

### F02.11 — `flatTree` calls `visitor.flush()` once *per sibling* instead of once at end

- **Severity:** LOW
- **Location:** `transcript/transform/flatten.ts:54-59`
- **Category:** correctness / dead-code

**Description:**
The flush loop is *inside* `for (const node of eventNodes)`, so a visitor with buffered state would be flushed N times. No current visitor implements `flush`, so this is latent. `TreeNodeVisitor.flush` and `TreeNodeTransformer.flush` (`transform.ts:64-71,167`) are both unused — remove or move the call outside the loop.

---

### F02.12 — `RenderedEventNode` `default: return null` hides unknown event types

- **Severity:** LOW
- **Location:** `transcript/TranscriptVirtualList.tsx:248-250`
- **Category:** fallback-hiding-errors

**Description:**
The switch over `node.event.event` has cases for 19 of the 20 members of the `Event` union (no `span_end` case — correct, it's stripped in treeify) plus `default: return null`. A new event type added on the Python side (`event/_event.py`) but forgotten here renders as nothing, with no warning. The `eventTypeValues` array in `types.ts:71-92` is kept in sync manually with no compile-time exhaustiveness check.

**Suggested fix:**
Add a `satisfies never` exhaustiveness check or render a visible "unknown event" placeholder.

---

### F02.13 — `TranscriptOutline` recomputes `elementIds` and `outlineIds` Set on every render/scroll

- **Severity:** LOW
- **Location:** `transcript/outline/TranscriptOutline.tsx:205`, `TranscriptOutline.tsx:213`
- **Category:** perf

**Description:**
`const elementIds = allNodesList.map((node) => node.id)` runs on every render (not memoized) and is passed to `useScrollTrack`, likely causing the hook to re-subscribe each render. Inside `findNearestOutlineAbove`, `new Set(outlineNodeList.map(...))` is rebuilt on every scroll callback. For transcripts with 10k+ events this is O(n) allocation per scroll tick.

**Suggested fix:**
Wrap `elementIds` in `useMemo([allNodesList])`; hoist `outlineIds` into a `useMemo([outlineNodeList])`.

---

### F02.14 — `parentOverride` parameter is never passed

- **Severity:** INFO
- **Location:** `transcript/transform/treeify.ts:37-53,62`
- **Category:** dead-code

**Description:**
`processEvent` in `treeifyWithSpans` accepts an optional `parentOverride`, with branching on `parentOverride !== undefined`, but the only call site is `events.forEach((event) => processEvent(event))`. The whole override path is unreachable.

---

### F02.15 — `TreeNodeVisitor.visit` `parent` parameter never supplied

- **Severity:** INFO
- **Location:** `transcript/transform/flatten.ts:4`, `flatten.ts:31`
- **Category:** dead-code

**Description:**
Interface declares `visit: (node, parent?) => EventNode[]` but `flatTree` calls `visitor.visit(pendingNode)` without the second arg. No visitor reads it. Remove from interface or wire it up.

---

### F02.16 — `kCollapsibleEventTypes` mixes span-type constants with event-type constants

- **Severity:** INFO
- **Location:** `transcript/types.ts:38-43`
- **Category:** code-smell

**Description:**
The array is compared against `node.event.event` (the discriminator), but uses `TYPE_TOOL` / `TYPE_SUBTASK` (span-`type` constants) instead of `TOOL` / `SUBTASK` (event-`event` constants). They happen to share the string values `"tool"` / `"subtask"` so it works, but it conflates two distinct namespaces and would break if either constant were ever changed.

---

### F02.17 — Shallow-spread of `EventNode` instances drops class prototype

- **Severity:** INFO
- **Location:** `transcript/transform/transform.ts:190`, `transform.ts:217`, `transcript/transform/flatten.ts:26`
- **Category:** code-smell

**Description:**
`{ ...node.children[0] }` produces a plain object, not an `EventNode` instance, then is force-cast `as EventNode`. `EventNode` currently has no methods so nothing breaks, but adding a method to the class would silently fail on these clones.

---

### F02.18 — `unwrap_main` transformer likely dead

- **Severity:** INFO
- **Location:** `transcript/transform/transform.ts:79-83`
- **Category:** dead-code

**Description:**
Matches `span_begin` with `type === "main"`. No Python code path emits a span with `type="main"` (`rg` over `src/inspect_ai/**/*.py`; the only `"main"` is `TimelineSpan(name="main", span_type=None)` in `_timeline.py`, which is not a transcript event). Either remove or document the producer.

---

### F02.19 — `collapseSampleInit` shadows imported `hasSpans`

- **Severity:** INFO
- **Location:** `transcript/transform/fixups.ts:63-65` (vs `fixups.ts:8`)
- **Category:** code-smell

**Description:**
A local `const hasSpans = events.some(...)` shadows the imported `hasSpans` util and re-implements it (also checking `span_end`, which the util doesn't). Use the shared util.

---

### F02.20 — `SUBTASK` constant exported but unused

- **Severity:** INFO
- **Location:** `transcript/transform/utils.ts:9`, `transcript/index.ts:35`
- **Category:** dead-code

**Description:**
`SUBTASK` is defined and re-exported from the package barrel but has zero consumers in the monorepo (only `TYPE_SUBTASK` is used). Same string value, redundant export.

---

## Files reviewed

- [x] `transcript/transform/treeify.ts` — span/step tree builders, scorer-span injector
- [x] `transcript/transform/transform.ts` — post-tree transformers (unwrap/elevate/discard)
- [x] `transcript/transform/fixups.ts` — pending-event collapse, sample_init step inject, sandbox grouping
- [x] `transcript/transform/flatten.ts` — tree → flat list with collapse + visitors
- [x] `transcript/transform/utils.ts` — string constants, `hasSpans`
- [x] `transcript/hooks/useListPositionManager.ts` — scroll-state lifecycle (no transform concerns found)
- [x] `transcript/hooks/useStickyObserver.ts` — DOM scroll observer (no transform concerns found)
- [x] `transcript/hooks/useStickySwimLaneHeight.ts` — ResizeObserver wrapper (no transform concerns found)
- [x] `transcript/types.ts` — `EventNode` class, `EventType` union, collapse constants
- [x] `transcript/timeline/hooks/useEventNodes.ts` — pipeline entry: fixup → treeify → filterEmpty → defaultCollapse
- [x] `transcript/TranscriptViewNodes.tsx` — `flatTree` consumer, turn-map computation
- [x] `transcript/TranscriptVirtualList.tsx` — `RenderedEventNode` switch (exhaustiveness)
- [x] `transcript/outline/tree-visitors.ts` — outline-only filter visitors
- [x] `transcript/outline/TranscriptOutline.tsx` — `flatTree` consumer (visitor path)
- [x] `inspect-common/src/types/generated.ts` — `SpanBeginEvent`/`SpanEndEvent`/`StepEvent` shapes
- [x] `inspect_ai/event/_span.py`, `_base.py`, `_event.py`, `util/_span.py` — confirmed `span_id` on `SpanBeginEvent` == own `id` (set after `_current_span_id.set(id)`)

## Open questions / needs verification

- **F02.1**: Do current logs actually emit `sandbox` events with non-null `span_id`? If they're always at root (`span_id == null`), the grouping accidentally works because `getEventSpanId` returns `null` → root, and the synthetic wrapper is also at root… but the sandbox events still wouldn't be *children* of the wrapper (both at root as siblings). Needs a real `.eval` log with sandbox events to confirm rendered behaviour.
- **F02.2/F02.3**: Are there logs in the wild old enough to lack a `scorers` span but new enough to have `scorer` spans? If not, `injectScorersSpan` is dead and could be deleted rather than fixed.
- **F02.5**: Verify visually with a `handoff`-type agent eval — indentation under the tool node should be wrong by one level.
- **F02.18**: Does scout (the other ts-mono consumer) inject `type === "main"` spans via `timelineEventNodes.ts`? If so, F02.4 is live.
