# App Shell, Flow, and Top-Level Wiring

**Reviewer scope:** `apps/inspect/src/{main.tsx, index.ts, constants.ts}`, `apps/inspect/src/app/{App.tsx, AppErrorBoundary.tsx, types.ts}`, `apps/inspect/src/app/flow/**`, `apps/inspect/src/app/utils/**`, `apps/inspect/src/app/samples/transcript/**`
**Date:** 2026-04-22

---

## Summary

The app-shell layer is small and mostly sound: bootstrap (`main.tsx`) → store init → hash restore → `<App>` → `<RouterProvider>`. However, it carries significant tech-debt: a duplicated `Event` union that has drifted from the canonical schema, a duplicated `uri.ts` that has diverged from `@tsmono/util`, several dead exports/files, and a Flow panel with no loading/error/empty states. The error boundary is non-recoverable and sits *inside* the router layout, so route changes after a crash cannot reset it. The transcript wrapper (`TranscriptPanel.tsx`) is well-structured and matches the `TranscriptLayout` contract; the only mismatch is that filtering events *before* passing them in strips `span_begin/end` pairing, which the upstream tree-builder relies on (mitigated only because spans are not in the filter list).

---

## Findings

### F52.1 — `FlowButton` assigns the same forwarded ref to two different elements

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/flow/FlowButton.tsx:32-43`
- **Category:** correctness

**Description:**
`forwardRef<HTMLButtonElement, ...>` receives `ref` and attaches it to **both** the `<button>` and the child `<i>`. The second assignment wins, so callers expecting an `HTMLButtonElement` actually get an `HTMLElement` (the `<i>`).

**Evidence:**
```tsx
<button ref={ref} type="button" ... >
  <i
    ref={ref}
    className={clsx(ApplicationIcons.flow, styles.viewerOptions)}
  />
</button>
```

**Why it matters / impact:**
Any consumer using the ref for positioning (e.g. a popover anchored to the button) will anchor to the icon instead, and the static type (`HTMLButtonElement`) lies. Currently no caller passes a ref, so it's latent — but the `forwardRef` wrapper exists *only* to enable this, so the API is broken at birth.

**Suggested fix:**
Remove `ref={ref}` from the `<i>`. Or, since no caller uses the ref and `FlowButtonProps` is empty, drop `forwardRef` entirely.

---

### F52.2 — `useFlowServerData` has no error handling; flow fetch failures are unhandled rejections

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/flow/hooks.ts:10-19`
- **Category:** fallback-hiding-errors

**Description:**
`fetchFlow` awaits `api?.get_flow(dir)` with no `try/catch`. If the server returns 4xx/5xx or the network fails, the promise rejects unhandled. Nothing surfaces to the UI; `state.logs.flow` keeps its previous value (stale data from a different directory).

**Evidence:**
```ts
const fetchFlow = async () => {
  const flowStr = await api?.get_flow(dir);
  updateFlowData(dir, flowStr);
};
if (dir !== flowDir) {
  fetchFlow();
}
```

**Why it matters / impact:**
On `FlowPanel`, the user sees either a blank `<pre>` or the *previous* directory's `flow.yaml` with no indication anything went wrong. On `LogsPanel`/`SamplesPanel`, a stale `flow` value can keep showing the FlowButton for a directory that has no flow file.

**Suggested fix:**
Wrap in `try/catch`, on failure call `updateFlowData(dir, undefined)` and surface via `state.app.status.error` (the same path `App.tsx` uses for log-load errors).

---

### F52.3 — `FlowPanel` has no loading / empty / error state

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/flow/FlowPanel.tsx:41-53`
- **Category:** consistency / event-display

**Description:**
The panel renders `<pre><code>{flow}</code></pre>` unconditionally. While the fetch is in flight, `flow` is `undefined` → empty grey box. If `get_flow` returns `undefined` (no `flow.yaml` in dir, which the VSCode and static-http impls always do), the panel stays permanently blank with no "No flow configuration found" message.

**Why it matters / impact:**
User deep-links to `/logs/<dir>/flow.yaml` for a directory without a flow file → sees a navbar over an empty panel. Indistinguishable from "still loading" or "fetch failed". Every other panel in the app uses `EmptyPanel` / `MessageBand` / `ProgressBar` for these states.

**Suggested fix:**
Track `loading` locally; render `<ProgressBar>` while loading, `<EmptyPanel>` when `flow === undefined` after load, `<ErrorPanel>` on error.

---

### F52.4 — `FlowPanel` syntax highlighting does not refresh when navigating between flow files

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/flow/FlowPanel.tsx:35-50` (interacts with `packages/react/src/hooks/usePrismHighlight.ts:11-18`)
- **Category:** correctness

**Description:**
`usePrismHighlight` sets `data-highlighted="true"` on the `<code>` element after first highlight and skips it forever after. Because `FlowPanel` is rendered by `RouteDispatcher` for *any* `*.yaml` path, navigating from `/logs/a/flow.yaml` to `/logs/b/flow.yaml` re-uses the same `<code>` DOM node. React updates the text content, but `data-highlighted` persists, so Prism never re-runs — the second file renders as plain unhighlighted text.

**Suggested fix:**
Add `key={flowDir}` to the `<code>` (or `<pre>`) element so React remounts it on navigation.

---

### F52.5 — `App.tsx` legacy `task_file` param: `replace(" ", "+")` only replaces the first space

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/App.tsx:206`
- **Category:** correctness

**Evidence:**
```ts
const resolvedLogPath = logPath ? logPath.replace(" ", "+") : logPath;
```

**Why it matters / impact:**
`String.replace` with a string pattern is non-global. A `task_file` containing multiple spaces (S3 keys, Windows paths) will only have the first one fixed → 404 on load. Comment says "Replace spaces" (plural).

**Suggested fix:**
`logPath.replaceAll(" ", "+")` or `logPath.replace(/ /g, "+")`.

---

### F52.6 — `AppErrorBoundary` is non-recoverable and never reset on navigation

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/AppErrorBoundary.tsx:14-48` and `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/routing/AppRouter.tsx:60-71`
- **Category:** correctness

**Description:**
The boundary has no `reset()` and no `key` tied to `location.pathname`. Once `hasError: true`, it renders `<ErrorPanel>` forever — the user can change the URL hash, click browser back, etc., and nothing happens (the boundary sits *inside* `AppLayout`, above `<Outlet>`, so route changes never remount it). The only escape is a full page reload.

**Why it matters / impact:**
A render crash in one sample's transcript permanently bricks the session even though every other sample/log is fine. There is also no "Reload" / "Go home" affordance in the error UI.

**Suggested fix:**
Either give `<AppErrorBoundary key={location.pathname}>` so navigation resets it, or add a "Try again" button that calls `this.setState({ hasError: false })`.

---

### F52.7 — `AppErrorBoundary` typo + wrong console level

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/AppErrorBoundary.tsx:27,42`
- **Category:** code-smell

**Description:**
`componentDidCatch` logs with `console.log` (should be `console.error`). The fallback-of-the-fallback message reads "An unknown error with no additional information **occured**" — misspelled "occurred". `getDerivedStateFromError` always sets `error`, so the misspelled branch is also effectively dead.

---

### F52.8 — Duplicate `Event` union in `app/types.ts` has drifted from generated schema

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/types.ts:173-190`
- **Category:** correctness / consistency

**Description:**
`app/types.ts` re-declares `export type Event = SampleInitEvent | ... | SubtaskEvent` instead of re-exporting the canonical `Event` from `@tsmono/inspect-common`. The local copy is **missing `SpanBeginEvent`, `SpanEndEvent`, and `ScoreEditEvent`** (compare `packages/inspect-common/src/types/generated.ts:1578`). It is consumed by `state/sampleSlice.ts` (`runningEvents: Event[]`) and `state/samplePolling.ts`.

**Why it matters / impact:**
Streaming/polled samples that emit `span_begin`/`span_end`/`score_edit` are stored in an array whose static type forbids them. Today this only loses type-checking (the runtime values are still pushed), but any future `switch` over this union will silently drop those cases.

**Suggested fix:**
Delete the local union; `export type { Event } from "@tsmono/inspect-common"`.

---

### F52.9 — `apps/inspect/src/utils/uri.ts` duplicates `@tsmono/util/uri.ts` and the two have diverged

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/utils/uri.ts` vs `src/inspect_ai/_view/ts-mono/packages/util/src/uri.ts`
- **Category:** code-smell / consistency

**Description:**
`App.tsx:32` imports `isUri` from the **local** `../utils/uri.ts`, which is a near-verbatim copy of the package version. They have already diverged: local `directoryRelativeUrl` encodes per-segment when no `dir` is given, package version `encodeURIComponent`s the whole string (turns `/` into `%2F`); local `join` lacks the `./` stripping the package version has. The monorepo CLAUDE.md explicitly says `@tsmono/util` is the barrel-export source of truth.

**Why it matters / impact:**
Same function name, two behaviours. `App.tsx` uses local; `apps/scout` uses package. Anyone moving code between them gets a different result for `directoryRelativeUrl("a/b")`.

**Suggested fix:**
Reconcile into `@tsmono/util` and delete the app-local copy.

---

### F52.10 — `ClipboardJS` is re-instantiated on every dependency change with no cleanup

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/App.tsx:225-236`
- **Category:** perf / code-smell

**Description:**
`new ClipboardJS(".clipboard-button,.copy-button")` runs inside the `loadLogsAndState` effect, whose dep array includes `onMessage` (which changes whenever `logDir` / `rehydrated` change). Each run attaches a fresh document-level click delegate; none are `.destroy()`ed.

**Why it matters / impact:**
Minor memory/handler leak; in long VSCode sessions with many `backgroundUpdate` messages this stacks listeners. Also, ClipboardJS init is unrelated to log loading — it belongs in a one-shot mount effect.

**Suggested fix:**
Move to a separate `useEffect(() => { const c = new ClipboardJS(...); return () => c.destroy(); }, [])`.

---

### F52.11 — Dead code: `printHtml` is never called

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/utils/print.ts:9-43`
- **Category:** dead-code

**Description:**
Only `printHeadingHtml` is imported (by `SamplePrintView.tsx`). `printHtml` — which opens a popup and `document.write`s into it — is unused. It also hard-codes `href="./assets/index.css"`, which would break under a different Vite base or in VSCode webview.

**Suggested fix:**
Delete `printHtml`.

---

### F52.12 — Dead file: `app/samples/transcript/types.ts`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/transcript/types.ts`
- **Category:** dead-code

**Description:**
This file re-exports transcript types from `@tsmono/inspect-components/transcript` "so that a single import path covers both shared and local types," but **nothing imports from it**. `TranscriptPanel.tsx` imports directly from `@tsmono/inspect-components/transcript`.

**Suggested fix:**
Delete the file (or actually use it as the indirection point it claims to be).

---

### F52.13 — Dead types in `app/types.ts`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/types.ts:201-239`
- **Category:** dead-code

**Description:**
`CurrentLog`, `Logs`, `SampleFilter`, `SampleMode`, `ContentTool`, `RunningSampleData` are defined but never imported anywhere. `ContentTool` in particular shadows the real `ContentTool` exported from `@tsmono/inspect-components/chat` with a *narrower* `content` shape — a trap waiting to happen. `AppState.logsSampleView` (line 70) is also dead: a setter exists in `appSlice.ts:368` but nothing reads or calls it.

---

### F52.14 — `kSampleMetdataTabId` typo propagated through app

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/constants.ts:25`
- **Category:** code-smell

**Description:**
`kSampleMetdataTabId` (missing the second "a" in Metadata). Imported by `SampleDisplay.tsx` and `SamplePrintView.tsx`. The string value `"metadata"` is correct, only the symbol name is wrong. Similarly, `routing/url.ts:290` defines `kLogsRoutUrlPattern` (missing "e"), which `AppRouter.tsx:23` has to alias on import: `kLogsRoutUrlPattern as kLogsRouteUrlPattern`.

**Suggested fix:**
Rename both at the definition site.

---

### F52.15 — `kSampleErrorRetriesTabId` is a phantom tab

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/constants.ts:28,38`
- **Category:** dead-code / correctness

**Description:**
`kSampleErrorRetriesTabId = "retry-errors"` is included in `kSampleTabIds` (which `routing/url.ts:150` uses to validate URL tab segments) but no `<TabPanel id="retry-errors">` exists in `SampleDisplay.tsx`. So `/logs/.../sample/1/1/retry-errors` parses as a "valid" route that selects a tab that is never rendered.

---

### F52.16 — `BooleanScoreDescriptor` uses string literal instead of `kScoreTypeBoolean`

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/descriptor/score/BooleanScoreDescriptor.tsx:10`
- **Category:** consistency

**Description:**
Every other descriptor (`PassFail`, `Categorical`, `Numeric`, `Object`, `List`, `Other`) imports its `kScoreType*` constant from `constants.ts`. `BooleanScoreDescriptor` hard-codes `scoreType: "boolean"`. The constant `kScoreTypeBoolean` exists and is used elsewhere (`filters.ts`, `completions.ts`).

---

### F52.17 — `restoreHash` in `main.tsx` has redundant branches

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/main.tsx:61-77`
- **Category:** code-smell

**Evidence:**
```ts
if (storedHash.startsWith("/")) {
  window.location.hash = storedHash;
} else if (storedHash.startsWith("#")) {
  window.location.hash = storedHash;
} else {
  window.location.hash = "#" + storedHash;
}
```

**Description:**
Branches 1 and 2 are identical. Since the `location.hash` setter normalises the leading `#`, all three branches produce equivalent results — the whole block reduces to `window.location.hash = storedHash`.

---

### F52.18 — `TranscriptFilter` preset links are `<a>` without `href` — not keyboard-accessible

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/transcript/TranscriptFilter.tsx:43-71`
- **Category:** a11y

**Description:**
"Default | Debug | None" are `<a onClick={...}>` with no `href`, so they are not focusable and cannot be activated via keyboard. The checkbox rows below have a `<div onClick>` wrapping an `<input type="checkbox">`, which double-fires when the checkbox itself is clicked (row `onClick` toggles, then checkbox `onChange` toggles back) — verify, but the row click reads `filtered.includes(eventType)` *before* the state update so it actually works; still, two handlers on nested elements is fragile.

**Suggested fix:**
Use `<button type="button">` for the preset links. Wrap each row in a `<label>` so clicking anywhere toggles the native checkbox without a second JS handler.

---

### F52.19 — `TranscriptPanel` filters events *before* tree-building, which can orphan spans

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/transcript/TranscriptPanel.tsx:105-112` and `hooks.ts:9`
- **Category:** event-display

**Description:**
`filteredEvents` is computed with `events.filter(e => !filteredEventTypes.includes(e.event))` and passed to `TranscriptLayout`, which then runs `treeify`/`flatten`. `AllEventTypes` deliberately excludes `span_begin`/`span_end` (with a `// TODO:` asking why), which is what currently keeps the tree intact — if a future event type were structural, filtering it pre-transform would corrupt the hierarchy. The design intent (filter is a *display* filter, not a structural one) is implicit and fragile.

**Suggested fix:**
Either document the invariant ("only leaf events may appear in `eventTypes`"), or move filtering inside `TranscriptLayout` so it runs *after* treeification (hide nodes, don't drop them).

---

### F52.20 — `tests/routing/url.test.ts` re-declares `kSampleTabIds` / `kWorkspaceTabs` instead of importing

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/tests/routing/url.test.ts:11-21` vs `constants.ts:12-40`
- **Category:** consistency

**Description:**
The test file has its own literal arrays. They are already out of sync: the test omits `retry-errors`. Adding a tab to `constants.ts` will not be exercised by the route-parsing tests.

---

### F52.21 — `FlowButton` / `TranscriptPanel` lack `displayName`; `FlowButtonProps` is an empty interface

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/flow/FlowButton.tsx:10-47`, `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/transcript/TranscriptPanel.tsx:65`
- **Category:** code-smell

**Description:**
`forwardRef`/`memo` wrappers without `.displayName` show up as `Anonymous` / `Memo` in React DevTools. `export interface FlowButtonProps {}` triggers `@typescript-eslint/no-empty-interface` under strict rules and signals the `forwardRef` wrapper is over-engineered (see F52.1).

---

### F52.22 — `main.tsx`: `let capabilities` should be `const`

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/main.tsx:17`
- **Category:** code-smell

**Description:**
The binding is never reassigned (only its properties are mutated). Also "Inititialize" on line 41 is misspelled.

---

## Files reviewed

- [x] `src/main.tsx` — bootstrap; restoreHash redundancy, `let` capabilities
- [x] `src/index.ts` — library entry; clean
- [x] `src/constants.ts` — tab/score IDs; typo + phantom tab
- [x] `src/vite-env.d.ts` — clean
- [x] `src/app/App.tsx` — host-message wiring, legacy URL params, ClipboardJS leak
- [x] `src/app/App.css` — print + icon masks; clean
- [x] `src/app/AppErrorBoundary.tsx` — no recovery, typo, console.log
- [x] `src/app/types.ts` — duplicate `Event` union (drifted), several dead types
- [x] `src/app/flow/FlowButton.tsx` — duplicate ref, empty props
- [x] `src/app/flow/FlowButton.module.css` — clean
- [x] `src/app/flow/FlowPanel.tsx` — no loading/empty state, re-highlight bug
- [x] `src/app/flow/FlowPanel.module.css` — clean
- [x] `src/app/flow/hooks.ts` — no error handling
- [x] `src/app/utils/print.ts` — `printHtml` dead, hardcoded asset path
- [x] `src/app/samples/transcript/TranscriptPanel.tsx` — well-structured wrapper; matches `TranscriptLayout` contract
- [x] `src/app/samples/transcript/TranscriptFilter.tsx` — a11y on preset links
- [x] `src/app/samples/transcript/TranscriptFilter.module.css` — clean
- [x] `src/app/samples/transcript/hooks.ts` — TODO comment on span exclusion; pre-transform filtering
- [x] `src/app/samples/transcript/types.ts` — dead re-export file

## Open questions / needs verification

- **F52.18 double-fire:** Confirm in browser whether clicking directly on the `<input type="checkbox">` inside the `.row` div fires both `div.onClick` and `input.onChange` and whether the net result is correct (it appears to cancel out, but only by accident of reading stale `filtered`).
- **F52.4:** Reproduce by navigating between two directories that both contain a `flow.yaml` without an intermediate non-flow route.
- **`language-yml` vs `language-yaml`:** PrismJS aliases `yml` → `yaml` so this should work, but worth confirming the bundled Prism build includes the alias (couldn't locate `node_modules/prismjs` in the workspace to verify).
