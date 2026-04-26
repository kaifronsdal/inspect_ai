# Transcript Outline & Timeline

**Reviewer scope:** `inspect-components/src/transcript/outline/`, `transcript/timeline/` (incl. `components/`, `hooks/`), `transcript/state/`, top-level `TranscriptLayout`, `TranscriptVirtualList*`, `TranscriptViewNodes`, `TimelineSelectContext`, `types.ts`, `icons.ts`
**Date:** 2026-04-22

---

## Summary

The outline + timeline subsystem is large and generally well-structured (good test coverage on the pure pipeline modules). However, there is one **HIGH** correctness bug in `StateEventView.setPath` that produces wrong diffs for any multi-segment JSON path, a **MEDIUM** double-toggle bug in `TimelineOptionsPopover` that makes checkbox clicks no-ops, and a cluster of sync/label/dead-code issues. Swimlane row keys are built by joining span names with `/`, which collides with package-qualified names and corrupts breadcrumbs. Several CSS classes and one whole pipeline function (`classifyBranches`) are vestigial.

---

## Findings

### F03.1 — `setPath` does not advance `current` when key already exists → wrong state diffs

- **Severity:** HIGH
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/state/StateEventView.tsx:292-308`
- **Category:** correctness

**Description:**
The `current = current[key]` advance is *inside* the `if (!(key in current))` block. When `initializeArrays()` (called immediately before `setPath`) has already created the intermediate key, the loop skips advancing and writes the final value at the wrong nesting level.

**Evidence:**
```ts
for (let i = 0; i < keys.length - 1; i++) {
  const key = keys[i];
  if (key && !(key in current)) {
    const nextKey = keys[i + 1];
    if (nextKey) {
      current[key] = isArrayIndex(nextKey) ? [] : {};
    }
    current = current[key] as Record<string, unknown>; // ← only runs on first creation
  }
}
```

**Why it matters / impact:**
For an `add` op with path `/messages/0` after `initializeArrays` has created `{messages: []}`, `setPath` writes `target["0"] = value` instead of `target.messages[0] = value`. The rendered diff in the "State Updated" / "Store Updated" panels is structurally incorrect for any change whose path has ≥2 segments and shares a prefix with a previously-initialized path.

**Suggested fix:**
Move `current = current[key]` outside the `if` block (and guard for `key` being defined).

---

### F03.2 — Timeline-options checkboxes double-toggle when clicked directly

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/timeline/components/TimelineOptionsPopover.tsx:54-114`
- **Category:** correctness

**Description:**
Each row has `onClick={() => toggle()}` on the wrapper `<div>` *and* `onChange={(e) => { e.stopPropagation(); toggle(); }}` on the `<input>`. `stopPropagation()` on a `change` event does **not** stop the native `click` event from bubbling, so clicking the checkbox itself fires both handlers → toggles twice → net no-op. Clicking the label area works (only the div onClick fires).

**Evidence:**
```tsx
<div className={styles.row} onClick={() => config.toggleMarkerKind(kind)}>
  <input
    type="checkbox"
    checked={checked}
    onChange={(e) => {
      e.stopPropagation();
      config.toggleMarkerKind(kind);
    }}
  />
```

**Why it matters / impact:**
Users who click precisely on the checkbox (rather than the surrounding label text) see the box flicker and revert. Affects all four options: Errors, Compaction, Utility agents, Branches, and Fork-relative.

**Suggested fix:**
Change `onChange` to `onClick` with `e.stopPropagation()`, or use `readOnly` + only the wrapper handler.

---

### F03.3 — Swimlane row keys use `/` as separator but span names may contain `/`

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/timeline/swimlaneRows.ts:207,273-275,404,459` and `TimelineSwimLanes.tsx:57` (`buildBreadcrumbs`)
- **Category:** correctness / consistency

**Description:**
Row keys are built as `` `${parentKey}/${displayName.toLowerCase()}` ``. Span names from inspect frequently contain `/` (package-qualified: `inspect_ai/react`, see `parsePackageName`). Such names produce keys like `main/inspect_ai/react` which `buildBreadcrumbs` then splits on `/` into 3 segments, looks up `main/inspect_ai` (doesn't exist), and drops it. The `visibleLayouts` ancestor-collapse check (`TimelineSwimLanes.tsx:237-245`) and `parentKeys` computation (`:188-199`) similarly mis-parse these keys.

**Why it matters / impact:**
For agents/solvers with package-qualified names, breadcrumbs show gaps, and expand/collapse can mis-associate parent rows. `getParentKeyFromBranch` and `kBranchKeyPattern` are also vulnerable if a span name contains the substring `/branch-`.

**Suggested fix:**
Use a separator that cannot appear in names (e.g. `\x1f`) or store ancestry as an array.

---

### F03.4 — Outline toggle click also triggers select + navigate

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/outline/OutlineRow.tsx:64-73`
- **Category:** collapse-expand

**Description:**
The chevron `<div className={styles.toggle} onClick={...}>` does not call `e.stopPropagation()`. Clicking it bubbles to the row's `onClick`, which calls `onSelect` **and** `onNavigateToEvent`.

**Why it matters / impact:**
Collapsing/expanding an outline node also scrolls the main transcript to that node and changes the selected highlight. Users who only wanted to peek at children get yanked to a new scroll position.

**Suggested fix:**
`onClick={(e) => { e.stopPropagation(); ... }}` on the toggle div (matches `TimelineSwimLanes.handleChevronClick` which does stop propagation).

---

### F03.5 — Outline → transcript navigation silently fails when target is collapsed in transcript

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/TranscriptViewNodes.tsx:146-162` + `TranscriptLayout.tsx:792-806`
- **Category:** collapse-expand / fallback-hiding-errors

**Description:**
Outline collapse state (`collapseState.outline`) and transcript collapse state (`collapseState.transcript`) are independent. `scrollToEvent` searches `flattenedNodes` (built from `collapsedTranscript`). If the clicked outline node's target is hidden inside a collapsed transcript parent, `findIndex` returns -1, then the DOM-querySelector fallback also finds nothing → silent no-op.

**Why it matters / impact:**
After a user "Collapse All"s the transcript and then clicks an outline child (e.g. a sub-span), nothing happens with no feedback.

**Suggested fix:**
Before scrolling, walk ancestors of `eventId` in `eventNodes` and call `onCollapseTranscript(ancestorId, false)` for any collapsed ancestor; or at minimum scroll to the nearest visible ancestor.

---

### F03.6 — `classifyBranches` is a no-op

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/timeline/core.ts:1036-1053`
- **Category:** dead-code

**Description:**
The function recurses through the span tree but performs no mutation or classification — the body is pure traversal. It's invoked at `core.ts:1666` and `:1706` as part of the build pipeline.

**Why it matters / impact:**
Wasted tree walk on every timeline build; misleading name suggests it does something.

---

### F03.7 — `noScorerChildren` visitor never resets, leaks into subsequent siblings

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/outline/tree-visitors.ts:36-66`
- **Category:** correctness

**Description:**
`inScorers`/`inScorer`/`currentDepth` are closure state that is set when a scorer span begins but never cleared. Any node *after* the scorer at `currentDepth + 1` is also stripped, even if it belongs to a different (non-scorer) parent.

**Why it matters / impact:**
In practice scorers are last so this rarely bites, but a transcript with `scorers` followed by another top-level span would have that span's first-level children removed from the outline.

---

### F03.8 — `TimelineSelector` chevron icon missing `bi` base class

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/timeline/components/TimelineSelector.tsx:56`
- **Category:** styling

**Description:**
`<i className={clsx("bi-chevron-down", styles.chevron)} />` — every other icon in the package uses `"bi bi-chevron-down"`. Without the `bi` class the Bootstrap Icons font-family/baseline rules don't apply.

**Why it matters / impact:**
Dropdown chevron may render with wrong font metrics or not at all (depends on whether the `bi` class is what carries `font-family`).

---

### F03.9 — `labelForOutlineNode` (width measurement) diverges from `labelForNode` (display)

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/outline/useOutlineWidth.ts:117-138` vs `OutlineRow.tsx:149-205`
- **Category:** consistency

**Description:**
The width-measurement copy doesn't lowercase agent/branch names, doesn't handle `kSandboxSignalName` → "sandbox events", and doesn't handle `approval` decisions. The displayed label is `parsePackageName(labelForNode(node)).module`; the measured label is `parsePackageName(labelForOutlineNode(node)).module`.

**Why it matters / impact:**
Outline column width can be slightly under/over-sized when agent names have mixed case or when sandbox/approval nodes appear (though approval is filtered out before measurement, sandbox is filtered too — so only the case-mismatch is live). Low impact, but the duplication invites future drift.

**Suggested fix:**
Export `labelForNode` and reuse it in `useOutlineWidth`.

---

### F03.10 — Unused `_font` parameter and stale CSS classes in outline

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/outline/useOutlineWidth.ts:48`, `TranscriptOutline.module.css:1-6,15-18`, `TranscriptOutline.tsx:255`
- **Category:** dead-code

**Description:**
- `_font` parameter is never read.
- `.node` and `.panel` in `TranscriptOutline.module.css` are not referenced anywhere.
- `styles.eventPadding` is referenced (`TranscriptOutline.tsx:255`) but not defined in the CSS module → resolves to `undefined`, so the padding row gets `class=""`.

---

### F03.11 — `styles.first` and `.parallelBadge` are dead

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/TranscriptVirtualListComponent.tsx:141` / `TranscriptVirtualListComponent.module.css`; `timeline/components/TimelineSwimLanes.module.css:256-259`
- **Category:** dead-code

**Description:**
`styles.first` is read in the TSX but no `.first` rule exists in the CSS (so `paddingClass` is always `undefined`). `.parallelBadge` is defined in CSS but never used in TSX.

---

### F03.12 — `showBranches` parameter threaded through `collectFromContent` but never branched on

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/timeline/timelineEventNodes.ts:305,345,401,538`
- **Category:** dead-code

**Description:**
`collectFromContent` accepts `showBranches` and passes it on recursion but never reads it for any conditional. Branches are emitted unconditionally. Either the option should gate the trailing branch emission, or the parameter should be removed.

---

### F03.13 — `summarizeNode` exported but unused; `buildContentItems` / `computeSwimlaneRows` only used in tests

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/outline/OutlineRow.tsx:207-277`; `timeline/contentItems.ts`; `timeline/swimlaneRows.ts:98-133`
- **Category:** dead-code

**Description:**
`summarizeNode` (popover-style metadata grid) is exported from `transcript/index.ts` but has zero call sites in the monorepo. `buildContentItems` and the non-flat `computeSwimlaneRows` are exported and tested but not used by any component (the live path uses `computeFlatSwimlaneRows` + `collectRawEvents`). May be intentional public API for `scout`, but worth confirming.

---

### F03.14 — Hard-coded `kRowHeight = 18` duplicates CSS `--swimlane-row-height`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/timeline/components/TimelineSwimLanes.tsx:1104` vs `TimelineSwimLanes.module.css:2`
- **Category:** code-smell / styling

**Description:**
`BranchConnectorLine` computes SVG y-coordinates from a JS constant that must stay in sync with the CSS variable. Changing row height in CSS will misalign connector lines.

---

### F03.15 — `flatTree` visitor path mutates `parentNode.children` per-sibling

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/transform/flatten.ts:28-38`
- **Category:** code-smell / correctness

**Description:**
Inside the visitor loop, `parentNode.children = visitorResult` overwrites the parent's *entire* children array with the result for *one* child, on every iteration. The final parent.children ends up holding only the last sibling's visitor output. Nothing currently depends on `parentNode.children` being correct after visited flattening (the outline only uses the returned flat list, and `node.children.length > 0` check in `OutlineRow` reads from the per-node copy at `:46`), but this is a footgun.

Additionally, `{ ...node }` (line 26) spreads an `EventNode` class instance into a plain object, losing the prototype.

---

### F03.16 — Token count may double-count cache tokens for some providers

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/timeline/core.ts:340-352`
- **Category:** event-display

**Description:**
`getEventTokens` returns `input_tokens + cache_read + cache_write + output_tokens` and ignores `usage.total_tokens`. Anthropic reports `input_tokens` excluding cache (so summing is right), but other providers fold cache into `input_tokens` (so this double-counts). The swimlane "tokens" column and AgentCard token badge are affected.

---

### F03.17 — `makeTurns` passthrough for `logger`/`info` is unreachable

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/outline/tree-visitors.ts:105-120`
- **Category:** dead-code

**Description:**
Both call sites (`TranscriptOutline.tsx:158-160`, `TranscriptViewNodes.tsx:126-128`) apply `removeNodeVisitor("logger")` and `removeNodeVisitor("info")` *before* `makeTurns` runs, so the `kTurnPassthroughEvents` branch is never taken.

---

### F03.18 — Error markers are collected but the icon is never rendered

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/timeline/components/TimelineSwimLanes.tsx:1205`
- **Category:** event-display / consistency

**Description:**
`MarkerGlyph` looks up `markerIcons[marker.kind]` but then renders `{marker.kind !== "error" && <i className={icon} />}`. Error markers therefore render as a 1px CSS line (`.markerError::after`) with no icon — `icons.error` is computed but unused. Likely intentional (the red tick is the design), but the dead icon lookup is misleading.

---

### F03.19 — `getBranchPrefix` only matches when branch row name is literally "Branch N"

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/timeline/timelineEventNodes.ts:119-129` and `core.ts:216-221`
- **Category:** event-display

**Description:**
`deriveBranchLabel` returns the first child span's name when one exists (e.g. `"Refactor"`), not `"Branch 1"`. `getBranchPrefix` then fails its `/^Branch (\S+)$/i` regex and returns `""`. Nested branches under such a row are labelled `"Branch 1"`, `"Branch 2"` instead of `"Branch 1.1"`, `"Branch 1.2"`. Contrast with `swimlaneRows.ts:545-555` which threads `branchPrefix` correctly through `flattenChildren` regardless of display name.

---

### F03.20 — Outline `running` dots can attach to a collapsed/synthetic node

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/outline/TranscriptOutline.tsx:265`
- **Category:** event-display

**Description:**
`running={running && index === outlineNodeList.length - 1}` puts the pulsing dots on whatever survived `collapseScoring(collapseTurns(makeTurns(...)))` last — typically `"scoring"` or `"N turns"`. If scoring hasn't started yet but the model is mid-generation, the dots correctly land on the turns node; but if a `score` event arrives while still running, dots move to "scoring" even though the agent loop may still be active. Minor.

---

### F03.21 — `TimelineSelector` uses `key={tl.name}` — collisions if two timelines share a name

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/timeline/components/TimelineSelector.tsx:63`
- **Category:** code-smell

**Description:**
Server-provided timelines aren't guaranteed unique names. Use index or `name+index`.

---

### F03.22 — `TranscriptOutline` writes `--outline-width` on an ancestor it doesn't own

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/outline/TranscriptOutline.tsx:186-198`
- **Category:** code-smell

**Description:**
The effect walks up the DOM to the nearest `display: grid` ancestor and sets an inline-style CSS var on it. There's no cleanup, so unmounting the outline leaves a stale `--outline-width` on the parent grid. In `TranscriptLayout` the grid is `.container` which also reads `var(--outline-width, 180px)` from CSS — when the outline is collapsed (unmounted) the stale value persists but the column template switches to `22px` so it's masked. Still, mutating ancestor inline style without cleanup is fragile.

---

### F03.23 — Outline label `parsePackageName(...).module` drops everything before the first `/`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/outline/OutlineRow.tsx:47` + `packages/util/src/python.ts:7-13`
- **Category:** event-display

**Description:**
`parsePackageName("a/b/c")` returns `{package:"a", module:"b"}` (`.split("/", 2)` discards `"c"`). For a span named e.g. `inspect_ai/tool/web_search`, the outline shows `"tool"`, losing the actual tool name. The transcript event renderer (e.g. `SpanEventView`) does not apply `parsePackageName`, so outline and transcript titles diverge.

---

## Files reviewed

- [x] `outline/OutlineRow.tsx` / `.module.css` — toggle propagation, label/icon logic, dead `summarizeNode`
- [x] `outline/TranscriptOutline.tsx` / `.module.css` — virtuoso, scroll-track sync, width side-effect, dead CSS
- [x] `outline/tree-visitors.ts` — `noScorerChildren` state leak, dead passthrough
- [x] `outline/useOutlineWidth.ts` — label divergence, dead `_font`
- [x] `timeline/core.ts` — `classifyBranches` no-op, token sum, module-level `branchFromSpanMap`
- [x] `timeline/contentItems.ts` — only used by tests
- [x] `timeline/markers.ts` — OK
- [x] `timeline/swimlaneLayout.ts` — OK; `debugRowSpan` dev-only
- [x] `timeline/swimlaneRows.ts` — `/` key separator, `computeSwimlaneRows` test-only
- [x] `timeline/syntheticNodes.ts` — fixture data only
- [x] `timeline/timeMapping.ts` — `GAP_PERCENT=0` makes gap-width math redundant but harmless
- [x] `timeline/timelineEventNodes.ts` — dead `showBranches` param, `getBranchPrefix` regex
- [x] `timeline/components/AgentCardView.tsx` / css — OK
- [x] `timeline/components/TimelineIconsContext.tsx` — OK
- [x] `timeline/components/TimelineMinimap.tsx` / css — OK
- [x] `timeline/components/TimelineOptionsPopover.tsx` / css — double-toggle bug
- [x] `timeline/components/TimelineSelector.tsx` / css — missing `bi` class, name-as-key
- [x] `timeline/components/TimelineSwimLanes.tsx` / css — breadcrumb `/` split, `kRowHeight` dup, dead `.parallelBadge`, error icon unused
- [x] `timeline/hooks/*` — `useActiveTimeline`, `useEventNodes`, `useTimeline`, `useTimelineConfig`, `useTimelinesArray`, `useTranscriptTimeline` — OK
- [x] `state/StateDiffView.tsx` — OK
- [x] `state/StateEventView.tsx` — **`setPath` bug**
- [x] `state/StateEventRenderers.tsx` — OK
- [x] `TranscriptLayout.tsx` / css — outline ↔ transcript collapse independence
- [x] `TranscriptVirtualList.tsx` — OK
- [x] `TranscriptVirtualListComponent.tsx` / css — dead `styles.first`
- [x] `TranscriptViewNodes.tsx` — `scrollToEvent` silent fail on collapsed target
- [x] `TimelineSelectContext.ts`, `types.ts`, `icons.ts` — OK
- [x] `transform/flatten.ts` — visitor parent-children mutation
- [x] `hooks/useListPositionManager.ts`, `useStickySwimLaneHeight.ts`, `useStickyObserver.ts` — OK

## Open questions / needs verification

- F03.1: confirm with a real multi-segment `JsonChange` path that the diff panel renders incorrectly (likely masked because most state changes are single-segment `/messages` or `/output` replacements).
- F03.13: are `buildContentItems` / `computeSwimlaneRows` / `summarizeNode` consumed by `apps/scout` or external packages? If not, candidates for removal.
- F03.16: confirm whether inspect normalizes `usage` such that `input_tokens` always excludes cache; if so this is a non-issue.
