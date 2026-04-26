# State Management & Routing

**Reviewer scope:** `apps/inspect/src/state/**` (all 21 files incl. `sync/`), `apps/inspect/src/app/routing/**` (all 7 files), `apps/inspect/src/app/types.ts`, `packages/react/src/state/ComponentStateContext.tsx`, `packages/react/src/hooks/useProperty.ts`, `packages/inspect-components/src/transcript/state/**`
**Date:** 2026-04-22

---

## Summary

The store is **Zustand** (with `immer` + `persist` + `devtools` middleware), not Redux — four slices (`app`, `log`, `logs`, `sample`) sharing a single store. Routing uses `react-router-dom` hash routing with hand-rolled regex parsers because React Router decodes `%2F`. Overall architecture is sound, but there is **significant dead state** (~8 fields/actions never read or never written), one **HIGH** correctness bug (`isLargeSample` always returns true so samples are never stored in reactive state), and several **MEDIUM** issues around collapse-state leakage, side-effects-in-render, and replication batching that can drop updates. Tab selection is duplicated between store and URL with effect-based sync (drift risk). The `transcript/state/` directory is *not* state management — it renders `StateEvent` JSON diffs — but contains a real traversal bug in `setPath`.

---

## Findings

### F50.1 — `isLargeSample()` always returns `true`

- **Severity:** HIGH
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/state/store_filter.ts:19-31`
- **Category:** correctness

**Description:**
The function checks two thresholds and returns `true` if either is exceeded — then unconditionally returns `true` at the end. The final line should be `return false`.

**Evidence:**
```ts
export function isLargeSample(sample: EvalSample): boolean {
  const storeKeys = countKeys(sample.store);
  if (storeKeys > 5000) {
    return true;
  }
  const estimatedMessageSize = estimateSize(sample.messages);
  if (estimatedMessageSize > 250000) {
    return true;
  }
  return true;   // ← bug
}
```

**Why it matters / impact:**
`sampleSlice.setSelectedSample` uses this to decide whether to put the sample in Zustand state (`selectedSampleObject`) or in a module-level ref (`selectedSampleRef`). Because it always reports "large", **every** sample goes into the ref, `state.sample.selectedSampleObject` is always `undefined`, and `sampleInState` is always `false`. Consequences:
- `getSelectedSample()` is never reactive — components reading the sample via the action won't re-render when it changes (this is currently masked by the `sample_identifier` change triggering re-renders).
- `handleRehydrate` always increments `sampleNeedsReload`, forcing a reload after every rehydration even for tiny samples that *were* persisted.
- The threshold checks (and `countKeys`) are dead weight executed on every sample load.

**Suggested fix:**
Change final `return true` → `return false`.

---

### F50.2 — `setPath()` only descends when key is missing

- **Severity:** HIGH
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/state/StateEventView.tsx:292-308`
- **Category:** correctness | event-display

**Description:**
The traversal `current = current[key]` is *inside* the `if (!(key in current))` block. When the intermediate key already exists (e.g. second JSON-patch change sharing a parent), `current` does not advance, so the final write lands at the wrong depth.

**Evidence:**
```ts
for (let i = 0; i < keys.length - 1; i++) {
  const key = keys[i];
  if (key && !(key in current)) {
    const nextKey = keys[i + 1];
    if (nextKey) {
      current[key] = isArrayIndex(nextKey) ? [] : {};
    }
    current = current[key] as Record<string, unknown>;   // ← only when key absent
  }
}
const lastKey = keys[keys.length - 1];
if (lastKey) { current[lastKey] = value; }
```

**Why it matters / impact:**
For a `StateEvent` with changes `[/messages/0, /messages/1]`, the second `setPath` finds `messages` already in `current` (the root), skips traversal, and writes `current["1"] = value` on the **root** instead of `current.messages[1]`. This produces a malformed before/after object → wrong diff displayed in the State/Store event viewer.

**Suggested fix:**
Move `current = current[key]` outside the `if`.

---

### F50.3 — Collapse / property-bag state leaks across samples and grows unbounded

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/state/sampleSlice.ts:172-210`, `appSlice.ts:93-95`
- **Category:** collapse-expand | perf

**Description:**
On sample change, only `sample.collapsedEvents` is cleared (`clearCollapsedEvents` in `useLoadSample.ts:120`) and only the `scrollPosition` / `listPosition` property bags (`prepareForSampleLoad` lines 207-208). The following are **never** cleared on sample or log change:
- `sample.collapsedIdBuckets` (RecordTree collapse state, keyed by node-tree id)
- `app.collapsed` (defined but unused — see F50.10)
- `app.messages` (MessageBand visibility — partially cleared per-id by `useMessageVisibility`, but only for mounted ids)
- `app.propertyBags` for every other bag: `selectedNav` (EventPanel pill selection), `collapse-state-scope` (outline/scores collapsed per logPath), `sidebar-widths`, virtuoso state from `useVirtuosoState`, etc.

Keys are eventNode IDs / component IDs which are **positional** (e.g. `event-node-3`), not sample-qualified.

**Why it matters / impact:**
1. **Cross-sample leakage**: open sample A, expand a `RecordTree` node at id `tree-3-2`; navigate to sample B → if B has a node at the same id it inherits A's expand state.
2. **Memory growth**: a user paging through 500 samples in a long session accumulates thousands of property-bag entries that are never GC'd; all of this is also persisted to localStorage on every (debounced) write.

**Suggested fix:**
Clear `collapsedIdBuckets` and per-event property bags in `prepareForSampleLoad`; or scope keys with `${logFile}:${sampleId}:${epoch}:` prefix and use `removeByPrefix` on switch.

---

### F50.4 — `useFilteredSamples` dispatches store actions inside `useMemo`

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/state/hooks.ts:142-179`
- **Category:** correctness | code-smell

**Description:**
`setFilterError(error)` / `clearFilterError()` are Zustand mutations called from inside a `useMemo` body — a side effect during render.

**Evidence:**
```ts
return useMemo(() => {
  const { result, error, allErrors } = ...;
  if (error && allErrors) {
    setFilterError(error);          // ← store write during render
  } else {
    clearFilterError();
  }
  ...
}, [evalDescriptor, sampleSummaries, filter, setFilterError, clearFilterError]);
```

**Why it matters / impact:**
React reserves the right to discard/re-run memo bodies. Under StrictMode this fires twice; if `setFilterError` ever changes a value the selector depends on it would loop. It currently "works" because `clearFilterError` setting `undefined → undefined` is a no-op, but it's fragile and violates render purity.

**Suggested fix:**
Move the error dispatch into a `useEffect` keyed on `error`/`allErrors`.

---

### F50.5 — `useMessageVisibility` first-render guard broken for the second effect

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/state/hooks.ts:294-325`
- **Category:** correctness

**Description:**
A single `isFirstRender` ref guards two `useEffect`s. Effect #1 sets `isFirstRender.current = false` on first run. Effect #2 then checks the same ref — which is already `false` — so it does **not** skip on first render.

**Evidence:**
```ts
useEffect(() => {                        // effect 1 (selectedLogFile)
  if (isFirstRender.current) {
    isFirstRender.current = false;
    return;
  }
  clearVisible(id);
}, [selectedLogFile, ...]);

useEffect(() => {                        // effect 2 (selectedSampleHandle)
  if (isFirstRender.current) {           // ← already false
    return;
  }
  if (scope === "sample") clearVisible(id);
}, [selectedSampleHandle, ...]);
```

**Why it matters / impact:**
`MessageBand` with `scope="sample"` clears its persisted visibility on first mount, defeating the rehydration of "user dismissed this banner". The user re-sees a banner they already dismissed.

**Suggested fix:**
Separate refs per effect, or use a generation counter / `usePrevious` on the dependency.

---

### F50.6 — `clearListPosition` / `clearVisibleRange` mix immer-draft read with return-replacement

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/state/appSlice.ts:228-270`
- **Category:** correctness | consistency

**Description:**
Every other action mutates the immer draft (`state.app.x = y`). These two instead **spread the draft** and `return { app: {...} }` from the producer. With `zustand/middleware/immer`, returning a value from the producer is passed to immer's `produce` as the result; spreading a draft (`{...state.app}`) copies *draft proxies* for nested objects (`propertyBags`, `collapsed`, etc.) into the returned plain object.

**Evidence:**
```ts
clearListPosition: (name: string) => {
  set((state) => {
    const newListPositions = { ...state.app.listPositions };
    delete newListPositions[name];
    return {
      app: { ...state.app, listPositions: newListPositions },
    };
  });
},
```

**Why it matters / impact:**
Risk of revoked-proxy errors or stale references after immer finalizes; also bypasses immer's structural sharing. The `set` parameter is typed `(fn: (state) => void) => void`, so the return value isn't even type-checked. `clearListPosition` is called on every sample load (`useLoadSample.ts:78`).

**Suggested fix:**
Use draft mutation like everywhere else: `delete state.app.listPositions[name]`.

---

### F50.7 — ReplicationService flush can strand pending updates

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/state/sync/replicationService.ts:141-201`
- **Category:** correctness

**Description:**
`flushPreviewBatch`/`flushDetailBatch` early-return when `_flushingPreview`/`_flushingDetail` is true, without rescheduling. If `onComplete` adds entries to `_pendingPreviewUpdates` while a flush is in flight, the throttled call fires, sees `_flushingPreview === true`, returns, and the new entries sit in the buffer until the *next* batch arrives (which may never happen at end of sync).

**Evidence:**
```ts
private async flushPreviewBatch() {
  if (this._flushingPreview) {
    return;                                // ← drops the trigger, no reschedule
  }
  this._flushingPreview = true;
  try {
    const updates = { ...this._pendingPreviewUpdates };
    this._pendingPreviewUpdates = {};
    ...
  } finally { this._flushingPreview = false; }
}
```

**Why it matters / impact:**
The last few log previews/details fetched during a sync may never reach the store or IndexedDB, leaving rows stuck on "loading" until the next manual sync.

**Suggested fix:**
After `finally`, if `Object.keys(this._pendingPreviewUpdates).length > 0` re-invoke the throttled flush.

---

### F50.8 — ReplicationService `_detailQueue` worker/onComplete index misalignment (latent)

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/state/sync/replicationService.ts:101-128`
- **Category:** correctness

**Description:**
The worker filters out `undefined` results (`details.filter(d => d !== undefined)`), then `onComplete` zips `inputs[i] → details[i]`. If any item in a batch failed, indices shift and the wrong file is associated with the wrong details.

**Why it matters / impact:**
Currently masked by `batchSize: 1`. If anyone bumps batch size, log details would be cached under wrong filenames.

**Suggested fix:**
Don't filter; keep `undefined` placeholders, or build a `Record<name, details>` in the worker.

---

### F50.9 — `syncLog` cache uses inconsistent path keys (abs vs relative)

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/state/logSlice.ts:185-269`
- **Category:** correctness

**Description:**
The cached-read path computes `logAbsPath` and reads/background-refreshes via that; the cache-miss path fetches via raw `logFileName` and writes to the DB under `logFileName`. So the cache is written under one key and read under another.

**Evidence:**
```ts
const logAbsPath = !isUri(logFileName) ? join(logFileName, logDir) : logFileName;
...
const cachedInfo = await dbService.readLogDetailsForFile(logAbsPath);   // read: ABS
...
api.get_log_details(logAbsPath).then((d) => { dbService.writeLogDetail(logAbsPath, d) ... })
...
// miss path:
const logDetails = await api.get_log_details(logFileName);              // RELATIVE
dbService.writeLogDetail(logFileName, logDetails)                       // write: RELATIVE
```

**Why it matters / impact:**
For relative `logFileName` (the common case from URL routing), cache lookups never hit on the fresh-load path → IndexedDB cache is effectively bypassed for `syncLog`, and two entries accumulate per file.

---

### F50.10 — Dead state: `app.collapsed`, `app.scrollPositions`, `app.visibleRanges`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/state/appSlice.ts:53-54,90-92,206-278`; `app/types.ts:52-58`
- **Category:** dead-code

**Description:**
`getCollapsed`/`setCollapsed`, `getScrollPosition`/`setScrollPosition`, `getVisibleRange`/`setVisibleRange`/`clearVisibleRange` are defined but **never called anywhere** outside the slice. Transcript collapse uses `sample.collapsedEvents`; scroll uses `propertyBags["scrollPosition"]`; virtuoso uses `propertyBags["listPosition"]` (via `useVirtuosoState`). The `app.listPositions` map is also written only via `clearListPosition` (delete) and never via `setListPosition`.

**Why it matters / impact:**
~80 lines of slice + 3 persisted state fields that do nothing. The codebase-map doc (00-codebase-map.md §5) is wrong about where collapse lives — it points readers here.

---

### F50.11 — Dead state: `logs.pendingRequests`, `app.logsSampleView`, `logs.listing.selectedRowIndex`, `log.scores`

- **Severity:** LOW
- **Location:** `logsSlice.ts:77,403-406,470-474`; `appSlice.ts:97,368-372`; `logSlice.ts:84,174-176,182`
- **Category:** dead-code

**Description:**
- `logs.pendingRequests: Map<...>` — initialized to `new Map()`, never read or written. Also: a `Map` in persisted Zustand state will not survive JSON serialization (it becomes `{}`).
- `app.logsSampleView` / `setLogsSampleView` — never read, never called.
- `logs.listing.selectedRowIndex` / `setSelectedRowIndex` — never read, never called.
- `log.scores` / `setScores` — never written; only read by `resetFiltering` (line 182), so `resetFiltering` always sets `selectedScores = undefined`.
- `logsActions.getAllCachedSamples` / `queryCachedSamples` — never called.

---

### F50.12 — Dead / duplicate hooks

- **Severity:** LOW
- **Location:** `state/hooks.ts:265-279,347-379`; `routing/url.ts:33-47`; `routing/logNavigation.ts`; `routing/sampleNavigation.ts:18-92,186-204`
- **Category:** dead-code | consistency

**Description:**
- `useCollapseSampleEvent` (hooks.ts:265) — unused.
- `useSetSelectedLogIndex` (hooks.ts:347) — unused.
- `useDecodedParams` (url.ts:33) — unused.
- `useSampleUrl` (sampleNavigation.ts:46) — unused (duplicates `useSampleNavigation.getSampleUrl`).
- `useSampleNavigation.nextSample/previousSample/firstSample/lastSample` — unused; `navigateSampleIndex` updates store but **not** URL, so if these were ever wired up they'd desync URL↔state.
- **`useLogNavigation` is defined twice** — once in `logNavigation.ts` (used by `LogView.tsx`) and again in `sampleNavigation.ts` (unused). The used one calls `useParams<{logPath}>()` which **cannot** match the splat route `*` and so `logPath` is always `undefined` → it always falls through to the `loadedLog` branch.

---

### F50.13 — Tab selection duplicated between store and URL

- **Severity:** LOW
- **Location:** `appSlice.ts:86-89,168-205`; `app/log-view/LogViewContainer.tsx:123-125`; `app/samples/SampleDetailComponent.tsx:115-122`; `routing/url.ts` (`tabId`/`sampleTabId`)
- **Category:** consistency

**Description:**
Workspace/sample tab is parsed from the URL (`useLogRouteParams().tabId`/`sampleTabId`) AND stored in `app.tabs.{workspace,sample}`. `LogViewContainer` and `SampleDetailComponent` run effects to copy URL→store; `useLogNavigation.selectTab` does store→URL via `navigate`. `setSelectedLogDetails` (logSlice.ts:137) and `setSelectedSample` (sampleSlice.ts:160) also write tabs directly without navigating.

**Why it matters / impact:**
Two sources of truth synced by effects → transient mismatch on every navigation (one render with stale `app.tabs.workspace` before the effect fires). When `setSelectedLogDetails` forces `kLogViewInfoTabId` it does **not** update the URL, so back-button / refresh restores the wrong tab.

**Suggested fix:**
Derive tab from URL only; drop `app.tabs`.

---

### F50.14 — `logSlice.initialState` contains fields not in `LogState`

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/state/logSlice.ts:71-85`
- **Category:** dead-code

**Description:**
`selectedSampleId: undefined` and `selectedSampleEpoch: undefined` are in `initialState` but the `LogState` type (types.ts:120-134) has `selectedSampleHandle` instead. The object is untyped so TS doesn't catch it.

---

### F50.15 — `useRefreshLog` doesn't await the refresh

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/state/hooks.ts:27-46`
- **Category:** correctness

**Description:**
`refreshLog()` returns a Promise but is called fire-and-forget; `setLoading(false)` runs immediately, and the `try/catch` cannot catch async errors.

**Evidence:**
```ts
try {
  setLoading(true);
  refreshLog();          // ← not awaited
  resetFiltering();
  setLoading(false);     // ← fires before refresh completes
} catch (e) { ... }      // ← never catches
```

---

### F50.16 — Debounced persist `setItem` can lose final write

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/state/store.ts:74-83`
- **Category:** correctness

**Description:**
`storageImplementation.setItem` is wrapped in `debounce(..., 1000)`. There's no `flush()` on `cleanup()` or `beforeunload`, so the last second of state changes before tab close / VS Code panel disposal is dropped.

---

### F50.17 — `O(n)` key lookups via `Object.keys().includes()`

- **Severity:** INFO
- **Location:** `appSlice.ts:110,217,244`
- **Category:** perf | code-smell

**Description:**
`getBoolRecord`, `getListPosition`, `getVisibleRange` do `Object.keys(record).includes(name)` instead of `name in record`. These run inside Zustand selectors that fire on every store update.

---

### F50.18 — Falsy `||` checks on `sampleId` / `sampleEpoch` that can be `0`

- **Severity:** LOW
- **Location:** `routing/url.ts:338,443-444,485-486`
- **Category:** correctness

**Description:**
`useSampleUrlBuilder` line 338: `if (sampleId && sampleEpoch && ...)` — both typed `string | number | undefined`; numeric `0` is falsy. `useSampleMessageUrl`/`useSampleEventUrl`: `sampleId || urlSampleId` falls through on `0`. (`baseUrl`/`logSamplesUrl` correctly use `!== undefined`.)

**Why it matters / impact:**
A sample with `id === 0` or `epoch === 0` builds the wrong deep-link URL (no-sample form, or falls back to URL params). Route *parsing* is safe because parsed values are strings (`"0"` is truthy).

---

### F50.19 — `syncEvalSetInfo` return type lies

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/state/logsSlice.ts:44,340-350`
- **Category:** code-smell

**Description:**
Declared `Promise<EvalSet | undefined>` but the body sets state and returns `undefined` always (`info` is fetched but not returned). Also the early `return undefined` after `console.error("API not initialized")` is the same fallback-hiding-errors pattern repeated in `syncLogPreviews`, `initLogDir`, `syncLogs`.

---

### F50.20 — ReplicationService `count` field never read; `stopReplication` never called

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/state/sync/replicationService.ts:509-517,248-252`
- **Category:** dead-code

**Description:**
`private count = 0` is incremented in `queueLogDetails` but never read. `stopReplication()` and `clearData()` have no callers.

---

### F50.21 — Typos in exported identifiers

- **Severity:** INFO
- **Location:** `logSlice.ts:324` (`initalializeLogSlice`); `url.ts:290` (`kLogsRoutUrlPattern`); `hooks.ts:547` (`LogHandleWithretried`)
- **Category:** code-smell

**Description:**
`initalializeLogSlice` (sic) is imported as-is in `store.ts:13`. `kLogsRoutUrlPattern` is renamed at the import site (`AppRouter.tsx:23`) rather than fixed at source. `LogHandleWithretried` should be `LogHandleWithRetried`.

---

### F50.22 — `RouteDispatcher` and `TasksRouter` are 95% duplicated

- **Severity:** INFO
- **Location:** `routing/RouteDispatcher.tsx` vs `routing/TasksRouter.tsx`
- **Category:** consistency | code-smell

**Description:**
The two files are byte-for-byte identical except `<LogsPanel />` vs `<LogsPanel mode="tasks" />`. Any fix to one (e.g. F50.18-style check, new file extension) must be applied to both.

---

## Files reviewed

- [x] `state/store.ts` — Zustand create + persist + immer; debounced storage
- [x] `state/store_filter.ts` — `isLargeSample` bug; persist filters
- [x] `state/appSlice.ts` — UI state; many dead actions
- [x] `state/logSlice.ts` — selected log; cache key mismatch
- [x] `state/logsSlice.ts` — log list; replication wiring; dead actions
- [x] `state/sampleSlice.ts` — sample + collapse state; ref-based large-sample storage
- [x] `state/hooks.ts` — derived selectors; side-effects in useMemo
- [x] `state/componentStateAdapter.ts` — bridges Zustand → ComponentStateContext
- [x] `state/log.ts` — `useUnloadLog`
- [x] `state/utils.ts` — `mergeSampleSummaries`
- [x] `state/scoring.ts` — scorer derivation; `_log` param unused
- [x] `state/sampleUtils.ts` — sample migration
- [x] `state/useLoadLog.ts` — URL → log selection
- [x] `state/useLoadSample.ts` — sample loader with generation guard
- [x] `state/usePollSample.ts` — running-sample polling hook
- [x] `state/logPolling.ts` — pending-samples polling
- [x] `state/samplePolling.ts` — event-stream polling
- [x] `state/samplePollingInstance.ts` — singleton holder
- [x] `state/clientEvents.ts` / `clientEventsService.ts` — refresh-evals polling
- [x] `state/sync/replicationService.ts` — IndexedDB ↔ API sync
- [x] `app/routing/AppRouter.tsx` — hash router + urlHash tracking
- [x] `app/routing/RouteDispatcher.tsx` / `TasksRouter.tsx` / `SamplesRouter.tsx`
- [x] `app/routing/url.ts` — manual regex param parsing
- [x] `app/routing/logNavigation.ts` / `sampleNavigation.ts` — duplicate `useLogNavigation`
- [x] `app/types.ts` — state shape definitions
- [x] `packages/react/src/state/ComponentStateContext.tsx` — context contract
- [x] `packages/react/src/hooks/useProperty.ts` — propertyBag hook
- [x] `packages/inspect-components/src/transcript/state/*` — StateEvent diff rendering (not store state)

## Open questions / needs verification

- **F50.6**: empirically verify whether returning `{app: {...draft}}` from the immer producer leaks revoked proxies — I traced the semantics but did not reproduce in a debugger.
- **F50.3**: confirm what bag names `useProperty` is called with across `inspect-components` (e.g. `EventPanel` `selectedNav`) to size the leak.
- **F50.13**: confirm whether any consumer relies on `app.tabs.*` being readable *before* the URL effect fires (would block removing the duplication).
- `logNavigation.ts` `useParams<{logPath}>()` — verify it really yields `undefined` on the `/logs/*` splat (I believe so; the route only defines `*`, not `:logPath`).
