# Dead-Code & Dead-CSS Inventory

**Reviewer scope:** `apps/inspect/src/`, `packages/inspect-components/src/`, `packages/react/src/`, `packages/inspect-common/src/` (578 files)
**Date:** 2026-04-22

---

## Summary

Systematic mechanical sweep of the four in-scope source roots for (§1) exported symbols with zero importers, (§2) `styles.X` references that resolve to `undefined`, (§3) CSS-module classes never referenced, (§4) orphaned `.module.css` files, and (§5) declared-but-unused component props. All hits were verified with `rg` against the full `ts-mono/` tree (including `apps/scout` and `packages/scout-components`) so that cross-package consumers are not miscounted.

This file is the **consolidated authoritative list**. Roughly half the entries below were already reported piecemeal in earlier findings files; those rows carry a cross-reference instead of a new ID. Rows with a new `F81.x` ID are findings **not previously logged anywhere**.

Method: scripts at `/tmp/css_analysis.py`, `/tmp/dead_exports.py`, `/tmp/unused_props.py` (regex extraction → `rg -w` verification). False positives from `:global()`, spread-merged style objects (`const styles = {...a, ...b}`), prop aliasing (`foo: bar`), and parent-read props (`TabPanel`) were manually filtered.

**Headline numbers (after de-duplication):**
- 18 wholly-dead exported symbols/files **not previously reported** (≈ 480 LOC deletable)
- 9 new undefined `styles.X` references
- 13 CSS modules with new dead rules (≈ 50 dead class selectors)
- 1 new orphaned `.module.css` file
- 2 new unused-prop instances

---

## §1 — Dead exports

Symbols exported from a file in scope with **zero importers** anywhere in `ts-mono/` (excluding the defining file, `index.ts` re-exports, `*.test.*`, `*.stories.*`). "Internal-only" = used in the same file but the `export` keyword is superfluous.

| Symbol | Location | Kind | Status | Ref |
|---|---|---|---|---|
| `LargeModal` (+ `ModalTool`, `ModalTools`, `LargeModal.module.css`) | `apps/inspect/src/components/LargeModal.tsx:38` | component, 183+58 LOC | **dead file** | **F81.1** |
| `sampleDataAdapter` | `apps/inspect/src/app/samples/sampleDataAdapter.ts:5` | function, 33 LOC | **dead file** | **F81.2** |
| `printCircularReferences`, `findDifferences` | `apps/inspect/src/utils/debugging.ts:1,30` | functions, 123 LOC | **dead file** | **F81.3** |
| `createSampleHandle` | `apps/inspect/src/app/shared/sample.ts:40` | function | dead | **F81.4** |
| `firstMetric` | `apps/inspect/src/scoring/metrics.ts:20` | function | dead | **F81.5** |
| `useSamplePopover` | `apps/inspect/src/state/hooks.ts:381` | hook | dead | **F81.6** |
| `supportsLinking` | `apps/inspect/src/app/routing/url.ts:592` | function | dead | **F81.7** |
| `useSampleMessageUrl` | `apps/inspect/src/app/routing/url.ts:417` | hook | dead | **F81.7** |
| `useSampleEventUrl` | `apps/inspect/src/app/routing/url.ts:459` | hook | dead | **F81.7** |
| `kSamplesRouteUrlPattern` | `apps/inspect/src/app/routing/url.ts:292` | const | dead | **F81.7** |
| `sampleLimitMessage` | `packages/inspect-common/src/utils/sampleLimit.ts:6` | function, 21 LOC | **dead file** (only re-exported) | **F81.8** |
| `FetchResponse` | `apps/inspect/src/client/api/types.ts:270` | interface | dead | **F81.9** |
| 7 type aliases (`ChatMessageContent`, `ChatMessages`, `ContentAudioFormat`, `ContentVideoFormat`, `EvalStatsModelUsage`, `JsonChanges`, `ToolInfos`) | `apps/inspect/src/@types/extraInspect.ts` | type aliases | dead | **F81.10** |
| `toTreeItems` (re-export) | `packages/inspect-components/src/content/index.ts:11` | re-export | internal-only; drop from barrel | **F81.11** |
| `ResolvedMessageEvent` (re-export) | `packages/inspect-components/src/transcript/index.ts:56` | re-export | internal-only; drop from barrel | **F81.11** |
| — | — | — | — | — |
| `NavPills` | `packages/react/src/components/NavPills.tsx:18` | component | dead | F60.13 |
| `AsciinemaPlayer` (app copy), `CodePanel`, `MorePopover` | `apps/inspect/src/components/` | components | dead files | F40.16 |
| `RunningPanel` | `apps/inspect/src/app/log-view/title-view/StatusPanel.tsx:32` | component | dead | F30.13 |
| `FlatSampleError` | `apps/inspect/src/app/samples/error/FlatSampleErrorView.tsx` | component | dead file | F20.9 |
| `EventProgressPanel`, `eventTitle` | `packages/inspect-components/src/transcript/` | component / fn | dead (re-export only) | F01.27, F01.9 |
| `summarizeNode`, `buildContentItems`, `computeSwimlaneRows` | `packages/inspect-components/src/transcript/` | functions | test-only | F03.13 |
| `classifyBranches` | `packages/inspect-components/src/transcript/timeline/core.ts` | function | no-op | F03.6 |
| `SUBTASK` | `packages/inspect-components/src/transcript/transform/` | const | dead | F02.20 |
| `printHtml` | `apps/inspect/src/app/utils/print.ts` | function | dead | F52.11 |
| `CurrentLog`, `Logs`, `SampleFilter`, `SampleMode`, `ContentTool`, `RunningSampleData` | `apps/inspect/src/app/types.ts` | types | dead | F52.13 |
| `app/samples/transcript/types.ts` | (whole file) | types | dead file | F52.12 |
| `toLogOverview` | `apps/inspect/src/client/database/utils.ts` | function | dead file | F51.18 |
| `readCompleteLog` | `apps/inspect/src/client/remote/remoteLogFile.ts` | function | dead | F51.19 |
| `jsonRpcPostMessageServer` | `apps/inspect/src/client/api/` | function | dead | F51.26 |
| `useCollapseSampleEvent`, `useSetSelectedLogIndex`, `useDecodedParams`, `useSampleUrl`, `useLogNavigation` (dup) | `apps/inspect/src/state/hooks.ts`, `routing/` | hooks | dead | F50.12 |
| `iconForMimeType` | `apps/inspect/src/app/appearance/icons.ts:11` | function | dead | F61.13 |
| `ApplicationColors` | `apps/inspect/src/app/appearance/colors.ts` | const | dead | F61.14 |
| `kSampleErrorRetriesTabId` | `apps/inspect/src/constants.ts:28` | const | phantom tab | F52.15 |

**Exported but only used in the same file** (drop the `export` keyword — INFO): `ModelTab`, `filterExpression`, `fetchFile`, `findEventForMessage`, `ChatViewVirtualListComponent`, `APIView`, `APICodeCell`, `contentDataRenderers`, `SampleSizeLimitedExceededError`, `ZstdWindowSizeError`, `UnsupportedCompressionError`, `CompressionMethod`, `CompressionMethodType`, `ZipFileEntry`, `decodeUrlParam`, `simpleMarkdownTruncate`, `AllEventTypes`, `LogsPanelMode`, `DistributiveOmit`, `injectReferenceLinks`, `unescapeHtmlForMath`, plus ~20 `*Props` interfaces exported only for the colocated `FC<*Props>`. Tracked collectively as **F81.12**.

**Excluded** (package public entrypoint — may be consumed by out-of-tree submodule parents per `ts-mono/CLAUDE.md`): `apps/inspect/src/index.ts` re-exports `simpleHttpApi`, `createViewServerApi`.

---

## §2 — Undefined `styles.X` references

`styles.X` read in TSX where `.X` is **not defined** in the imported `.module.css`. All resolve to `undefined` and are silently dropped by `clsx`.

| File | Reference | Notes | Ref |
|---|---|---|---|
| `apps/inspect/src/app/log-view/title-view/ScoreGrid.tsx:58` | `styles.headerRow` | no `.headerRow` rule | **F81.13** |
| `apps/inspect/src/app/samples/InlineSampleDisplay.tsx:57` | `styles.body` | only `.container`/`.scroller` defined | **F81.14** |
| `apps/inspect/src/app/samples/SampleDisplay.tsx:476` | `styles.tabPanel` | not in `SampleDisplay.module.css` | **F81.15** (sibling of F20.17) |
| `apps/inspect/src/app/samples/sample-tools/SelectScorer.tsx:73,87` | `styles.link` | CSS has `.links a` descendant, no `.link` | **F81.16** |
| `apps/inspect/src/app/samples/transcript/TranscriptFilter.tsx:45,55,65` | `styles.link` | same `.links a` pattern as above | **F81.16** |
| `apps/inspect/src/app/samples/scores/SampleScoresView.tsx:54` | `styles.container` | not in `SampleScoresView.module.css` | **F81.17** (extends F20.18) |
| `packages/inspect-components/src/transcript/ScoreEventView.tsx:72` | `styles.metadataTree` | CSS defines `.metadata` — typo pair | **F81.18** |
| `packages/inspect-components/src/transcript/ScoreEditEventView.tsx` | `styles.metadataTree` | CSS defines `.metadata` — typo pair | **F81.18** |
| — | — | — | — |
| `apps/inspect/src/app/samples/SampleDisplay.tsx` | `styles.transcriptContainer` | | F20.17 |
| `apps/inspect/src/app/plan/SolverDetailView.tsx` | `styles.items` | CSS has `.item` | F31.9 |
| `apps/inspect/src/app/navbar/Navbar.tsx` | `styles.pathLink`, `styles.pathSegment` | | F31.18 |
| `apps/inspect/src/app/shared/ColumnSelectorPopover.tsx` | `styles.popover` | | F31.18 |
| `packages/inspect-components/src/chat/ChatMessage.tsx` | `styles.userRole` | | F10.15 |
| `packages/inspect-components/src/chat/ChatViewVirtualList.tsx` | `styles.item` | | F10.15 |
| `packages/inspect-components/src/chat/content-data/ContentDataView.tsx` | `styles.data` | | F10.15 |
| `packages/inspect-components/src/chat/content-data/WebSearchResults.tsx` | `styles.label`, `styles.results` | | F10.15 |
| `packages/inspect-components/src/chat/server-tools/ServerToolCall.tsx` | `styles.result`, `styles.type` | | F11.12 |
| `packages/inspect-components/src/chat/tools/ToolInput.tsx` | `styles.bottomMargin` | | F11.12 |
| `packages/inspect-components/src/chat/tools/ToolOutput.tsx` | `styles.ansiOutput` | | F11.12 |
| `packages/inspect-components/src/chat/tools/tool-input/TodoWriteInput.tsx` | `styles.todoItem` | | F11.12 |
| `packages/inspect-components/src/content/MetaDataGrid.tsx` | `styles.nested` | | F40.20 |
| `packages/inspect-components/src/transcript/TranscriptVirtualListComponent.tsx` | `styles.first` | | F03.11 |
| `packages/inspect-components/src/transcript/outline/TranscriptOutline.tsx` | `styles.eventPadding` | | F03.10 |
| `packages/react/src/components/AnsiDisplay.tsx` | `styles.ansiDisplayLine` | | F60.8 |
| `packages/react/src/components/ExpandablePanel.tsx` | `styles.padBottom` | | F60.8 |
| `packages/react/src/components/LabeledValue.tsx` | `styles.labeledValueValue` | | F60.8 |
| `packages/react/src/components/TabSet.tsx` | `moduleStyles.pill` | | F60.8 |

---

## §3 — Dead CSS rules

Class selectors defined in a `.module.css` that are **never referenced** via `styles.X` (or `styles["x"]`) by any importer. `:global()` selectors and rules reachable via spread-merged style objects were excluded.

| CSS module | Dead classes | Ref |
|---|---|---|
| `apps/inspect/src/app/log-view/title-view/TitleView.module.css` | `.navbarBody`, `.navbarBodyContainer`, `.navbarContainer`, `.navbarInnerWrapper`, `.navbarSecondaryContainer`, `.navbarStatus`, `.navbarTaskModel`, `.navbarTaskTitle`, `.navbarToggle` (9 of 10 — only `.navbarWrapper` is used) | **F81.19** |
| `apps/inspect/src/app/log-view/title-view/ResultsPanel.module.css` | `.multiMetricsRows`, `.multiScoreMetricGrid`, `.multiScorer`, `.multiScorerIndent`, `.multiScorerLabel`, `.multiScorerReducer`, `.multiScorerValue`, `.multiScorerValueContent` (8 selectors, ~45 LOC) | **F81.20** |
| `apps/inspect/src/app/log-view/title-view/RunningStatusPanel.module.css` | `.metricsRows`, `.value` | **F81.21** |
| `apps/inspect/src/app/log-view/title-view/PrimaryBar.module.css` | `.toggle` | **F81.22** |
| `apps/inspect/src/app/log-list/ViewerOptionsPopover.module.css` | `.cachedItemsList`, `.content`, `.notSet`, `.statRow`, `.statsSection` | **F81.23** |
| `apps/inspect/src/app/samples/scores/SampleScoresGrid.module.css` | `.heading`, `.padded` | **F81.24** |
| `apps/inspect/src/app/shared/gridCells.module.css` | `.fullWidthHeight` | **F81.25** |
| `packages/inspect-components/src/transcript/LoggerEventView.module.css` | `.jsonPanel` | **F81.26** |
| `packages/inspect-components/src/transcript/SandboxEventView.module.css` | `.contents` (+ `.contents > :last-child`) | **F81.27** |
| `packages/inspect-components/src/transcript/ScoreEventView.module.css` | `.metadata` (typo pair — see F81.18) | **F81.18** |
| `packages/inspect-components/src/transcript/ScoreEditEventView.module.css` | `.metadata` (typo pair — see F81.18) | **F81.18** |
| `packages/inspect-components/src/transcript/TranscriptLayout.module.css` | `.sidebarHeaderIcon` | **F81.28** |
| `packages/react/src/components/LiveVirtualList.module.css` | `.progressText` | **F81.29** |
| — | — | — |
| `apps/inspect/src/app/plan/PlanDetailView.module.css` | `.oneCol`, `.twoCol`, `.row` | F31.17 |
| `apps/inspect/src/app/plan/SolverDetailView.module.css` | `.item` | F31.9 |
| `apps/inspect/src/app/samples/SampleDisplay.module.css` | `.timePanel` | F20.17 |
| `apps/inspect/src/app/samples/descriptor/score/ObjectScoreDescriptor.module.css` | `.padded` | F21.22 |
| `apps/inspect/src/app/samples/scores/SampleScoresView.module.css` | 9 classes | F20.18 |
| `packages/inspect-components/src/chat/ChatViewVirtualList.module.css` | `.list` | F10.15 |
| `packages/inspect-components/src/chat/MessageContent.module.css` | `.data` | F10.15 |
| `packages/inspect-components/src/chat/content-data/WebSearchResults.module.css` | `.webSearch`, `.query` | F10.15 |
| `packages/inspect-components/src/transcript/ModelEventView.module.css` | `.tools` | F04.13 |
| `packages/inspect-components/src/transcript/outline/TranscriptOutline.module.css` | `.node`, `.panel` | F03.10 |
| `packages/inspect-components/src/transcript/timeline/components/TimelineSwimLanes.module.css` | `.parallelBadge` | F03.11 |
| `packages/inspect-components/src/usage/UsageCard.module.css` | `.col1` | F04.13 |
| `packages/react/src/components/ExpandablePanel.module.css` | `.expandableContents`, `.expandableTogglable` | F60.9 |
| `packages/react/src/components/LightboxCarousel.module.css` | `.open`, `.closed`, `.prev`, `.next` | F60.3 |

**False-positive note:** `apps/inspect/src/app/log-list/grid/columns/columns.module.css` (`.started`, `.error`, `.cancelled`, `.success`, `.nameCell`, `.modelCell`, `.scoreCell`, `.dateCell`, `.statusCell`) initially flagged but **is used** — `hooks.tsx:22` does `const styles = { ...sharedStyles, ...localStyles }` and reads via the merged object.

---

## §4 — Orphaned `.module.css` files

Files with **no importer** anywhere in `ts-mono/`.

| File | Size | Ref |
|---|---|---|
| `apps/inspect/src/app/samples-panel/SampleDetailView.module.css` | 32 lines | **F81.30** — sibling `SampleDetailView.tsx` exists and is routed, but never imports its CSS |
| `apps/inspect/src/components/LargeModal.module.css` | 58 lines | **F81.1** — companion to dead `LargeModal.tsx` |
| `apps/inspect/src/app/log-view/tabs/InfoTab.module.css` | 0 lines (empty) | F31.16 |
| `apps/inspect/src/app/log-view/tabs/ModelsTab.module.css` | 0 lines (empty) | F31.16 |
| `apps/inspect/src/app/navbar/ViewSegmentedControl.module.css` | 0 lines (empty) | F31.16 |
| `apps/inspect/src/app/samples/scores/SampleScores.module.css` | 5 lines | F20.9 |

Non-module CSS orphans previously reported: `apps/inspect/src/components/Card.css` (F61.19), `packages/react/src/components/EmptyPanel.css` (F60.12).

---

## §5 — Unused props

Interface props that are declared but never destructured, or destructured but never read in the component body. Aliased destructures (`foo: bar`), parent-read props (`TabPanelProps` — read via `tab.props.X` in `TabSet`), and nested option-object fields (`MetadataGridProps.options.*`) were excluded as false positives.

| Component | Prop | Issue | Ref |
|---|---|---|---|
| `apps/inspect/src/app/log-view/tabs/InfoTab.tsx:61,63` | `evalStats`, `samples` | declared in `InfoTabProps`, never destructured; not passed by `useInfoTabConfig` either | **F81.31** |
| — | — | — | — |
| `apps/inspect/src/app/log-view/title-view/RunningStatusPanel.tsx:11` | `displayMetrics` | declared, never destructured | F30.13 |
| `apps/inspect/src/app/log-view/tabs/JsonTab.tsx` | `selected` | declared, never destructured | F31.14 |
| `apps/inspect/src/app/log-view/tabs/ErrorTab.tsx` | `scrollRef` | declared, never destructured | F31.14 |
| `apps/inspect/src/app/samples/error/SampleErrorView.tsx` | `align`, `style` | declared, never used | F20.10 |
| `packages/inspect-components/src/transcript/state/StateEventView.tsx` | `isStore` | declared, never destructured | F01.26 |
| `packages/inspect-components/src/transcript/state/StateEventRenderers.tsx` | `toolDesc` | declared, never destructured | F05.13 |
| `packages/react/src/components/AsciinemaPlayer.tsx` | `className` | declared, never applied | F60.7 |
| `packages/react/src/components/SegmentedControl.tsx` | `Segment.selectedId` | declared, never read | F60.19 |
| `packages/react/src/components/ComponentIconContext.tsx` | `toggleRight` | required, never consumed | F60.26 |

---

## Findings

### F81.1 — `LargeModal` is a dead component (183 + 58 LOC)

- **Severity:** LOW
- **Location:** `apps/inspect/src/components/LargeModal.tsx`, `apps/inspect/src/components/LargeModal.module.css`
- **Category:** dead-code

**Description:**
`LargeModal`, `ModalTool`, `ModalTools` have zero importers in `ts-mono/`. The 58-line companion CSS module is imported only by the dead TSX. F40.16 catalogued three other dead components in the same directory (`AsciinemaPlayer`, `CodePanel`, `MorePopOver`) but missed this one — `apps/inspect/src/components/` now has **4 of 13** components dead.

**Suggested fix:** Delete both files. `Modal.tsx` in the same dir is the live replacement.

---

### F81.2 — `sampleDataAdapter.ts` is a dead file

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/samples/sampleDataAdapter.ts:5`
- **Category:** dead-code

**Description:**
Single export `sampleDataAdapter()` (33 lines) is never imported.

---

### F81.3 — `utils/debugging.ts` is a dead file

- **Severity:** LOW
- **Location:** `apps/inspect/src/utils/debugging.ts`
- **Category:** dead-code

**Description:**
Both exports (`printCircularReferences`, `findDifferences`, 123 LOC) only reference each other recursively; no external importer. Dev-only helpers that should either be deleted or moved to a dev-tools package.

---

### F81.4 — `createSampleHandle` is dead

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/shared/sample.ts:40-46`
- **Category:** dead-code

**Description:**
The other two exports in the file (`sampleIdsEqual`, `sampleHandlesEqual`) are live; `createSampleHandle` is not.

---

### F81.5 — `firstMetric` is dead

- **Severity:** LOW
- **Location:** `apps/inspect/src/scoring/metrics.ts:20`
- **Category:** dead-code

**Description:**
Never imported. The live equivalent lives in `client/utils/type-utils.ts` (`primary_metric` selection).

---

### F81.6 — `useSamplePopover` hook is dead

- **Severity:** LOW
- **Location:** `apps/inspect/src/state/hooks.ts:381`
- **Category:** dead-code

**Description:**
Returns popover open/close state keyed by `id`; no call sites. F50.12 catalogued four other dead hooks in this file but missed this one.

---

### F81.7 — Four dead routing exports in `url.ts`

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/routing/url.ts:292,417,459,592`
- **Category:** dead-code

**Description:**
`kSamplesRouteUrlPattern`, `useSampleMessageUrl`, `useSampleEventUrl`, `supportsLinking` have zero callers. F50.12 listed `useDecodedParams` and `useSampleUrl` from the same module; these four are additional. Together with `SampleUrlBuilder` / `LogOrSampleRouteParams` (internal-only types) the file is ~100 LOC over-weight.

---

### F81.8 — `packages/inspect-common/src/utils/sampleLimit.ts` is a dead file

- **Severity:** LOW
- **Location:** `packages/inspect-common/src/utils/sampleLimit.ts:6` (re-exported from `utils/index.ts:3`)
- **Category:** dead-code

**Description:**
`sampleLimitMessage` is re-exported through the `inspect-common` barrel but never consumed by any package (inspect, scout, components). The same human-readable strings are open-coded in `SampleLimitEventView.tsx` instead.

---

### F81.9 — `FetchResponse` interface is dead

- **Severity:** INFO
- **Location:** `apps/inspect/src/client/api/types.ts:270`
- **Category:** dead-code

**Description:**
Distinct from `LogFilesFetchResponse` (which is live). No references.

---

### F81.10 — Seven dead type aliases in `@types/extraInspect.ts`

- **Severity:** INFO
- **Location:** `apps/inspect/src/@types/extraInspect.ts`
- **Category:** dead-code

**Description:**
Of the 19 alias exports, 7 are never imported: `ChatMessageContent`, `ChatMessages`, `ContentAudioFormat`, `ContentVideoFormat`, `EvalStatsModelUsage`, `JsonChanges`, `ToolInfos`.

---

### F81.11 — Barrel re-exports with no downstream consumers

- **Severity:** INFO
- **Location:** `packages/inspect-components/src/content/index.ts:11` (`toTreeItems`); `packages/inspect-components/src/transcript/index.ts:56` (`ResolvedMessageEvent`)
- **Category:** dead-code

**Description:**
Both symbols are used inside their own module but the barrel re-export is never imported by `apps/inspect`, `apps/scout`, or any sibling package.

---

### F81.12 — ~21 exports that are file-internal only

- **Severity:** INFO
- **Location:** see §1 list ("Exported but only used in the same file")
- **Category:** dead-code

**Description:**
The `export` keyword is superfluous and inflates the package surface / bundle tree-shaking analysis. No behavioural impact. List: `ModelTab`, `filterExpression`, `fetchFile`, `findEventForMessage`, `ChatViewVirtualListComponent`, `APIView`, `APICodeCell`, `contentDataRenderers`, `SampleSizeLimitedExceededError`, `ZstdWindowSizeError`, `UnsupportedCompressionError`, `CompressionMethod`, `CompressionMethodType`, `ZipFileEntry`, `decodeUrlParam`, `simpleMarkdownTruncate`, `AllEventTypes`, `LogsPanelMode`, `DistributiveOmit`, `injectReferenceLinks`, `unescapeHtmlForMath`.

---

### F81.13 — `ScoreGrid.tsx` references undefined `styles.headerRow`

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/log-view/title-view/ScoreGrid.tsx:58`
- **Category:** styling / dead-code

**Evidence:**
```tsx
const headerRow = (
  <tr className={clsx(styles.headerRow)}>
```
`ScoreGrid.module.css` defines `.table`, `.scorer`, `.value`, `.label`, `.groupSeparator`, `.tableBody`, `.tableSeparator` — no `.headerRow`.

---

### F81.14 — `InlineSampleDisplay.tsx` references undefined `styles.body`

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/samples/InlineSampleDisplay.tsx:57`
- **Category:** styling / dead-code

`InlineSampleDisplay.module.css` defines only `.container` and `.scroller`.

---

### F81.15 — `SampleDisplay.tsx` references undefined `styles.tabPanel`

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/samples/SampleDisplay.tsx:476`
- **Category:** styling / dead-code

F20.17 already documents `styles.transcriptContainer` in this file; `styles.tabPanel` (passed as `tabPanelsClassName`) is a second undefined reference in the same component.

---

### F81.16 — `styles.link` undefined in `SelectScorer` and `TranscriptFilter`

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/samples/sample-tools/SelectScorer.tsx:73,87`; `apps/inspect/src/app/samples/transcript/TranscriptFilter.tsx:45,55,65`
- **Category:** styling / dead-code

**Description:**
Both modules apply `clsx(styles.link, …)` to each `<a>`, but the CSS only defines a descendant rule `.links a { … }` (plural). The descendant selector still matches, so the visual result is correct — but `styles.link` is `undefined`. Either drop the `styles.link` reference or rename the CSS rule to `.link` and apply directly.

---

### F81.17 — `SampleScoresView.tsx` references undefined `styles.container`

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/samples/scores/SampleScoresView.tsx:54`
- **Category:** styling / dead-code

F20.18 catalogued nine dead classes in `SampleScoresView.module.css`; this is the inverse — a class the TSX expects that the CSS does not define.

---

### F81.18 — `.metadata` ↔ `styles.metadataTree` mismatch in score-event views

- **Severity:** LOW
- **Location:** `packages/inspect-components/src/transcript/ScoreEventView.tsx:72` & `.module.css:18`; `packages/inspect-components/src/transcript/ScoreEditEventView.tsx` & `.module.css`
- **Category:** styling / dead-code

**Description:**
TSX reads `styles.metadataTree`; CSS defines `.metadata`. Result: the metadata `RecordTree` gets no module class, and `.metadata` is dead. Appears in both `ScoreEventView` and `ScoreEditEventView` (copy-paste).

**Suggested fix:** rename CSS rule to `.metadataTree`.

---

### F81.19 — `TitleView.module.css`: 9 of 10 classes are dead

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/log-view/title-view/TitleView.module.css` (54 lines)
- **Category:** dead-code

**Description:**
`TitleView.tsx` only reads `styles.navbarWrapper`. The other nine selectors (`.navbarBody`, `.navbarBodyContainer`, `.navbarContainer`, `.navbarInnerWrapper`, `.navbarSecondaryContainer`, `.navbarStatus`, `.navbarTaskModel`, `.navbarTaskTitle`, `.navbarToggle`) are vestiges of the pre-`PrimaryBar`/`SecondaryBar` layout.

---

### F81.20 — `ResultsPanel.module.css`: 8 `.multiScorer*` classes are dead

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/log-view/title-view/ResultsPanel.module.css`
- **Category:** dead-code

**Description:**
`ResultsPanel.tsx` uses 6 classes (`metricsSummary`, `moreButton`, `simpleMetricsRows`, `verticalMetricName/Reducer/Value`). The 8 `multi*` selectors (~45 LOC) were for the multi-scorer inline grid that was replaced by `ScoreGrid` modal.

---

### F81.21 — `RunningStatusPanel.module.css`: `.metricsRows`, `.value` dead

- **Severity:** INFO
- **Location:** `apps/inspect/src/app/log-view/title-view/RunningStatusPanel.module.css`
- **Category:** dead-code

---

### F81.22 — `PrimaryBar.module.css`: `.toggle` dead

- **Severity:** INFO
- **Location:** `apps/inspect/src/app/log-view/title-view/PrimaryBar.module.css`
- **Category:** dead-code

---

### F81.23 — `ViewerOptionsPopover.module.css`: 5 dead classes

- **Severity:** INFO
- **Location:** `apps/inspect/src/app/log-list/ViewerOptionsPopover.module.css`
- **Category:** dead-code

`.cachedItemsList`, `.content`, `.notSet`, `.statRow`, `.statsSection` — left over from a removed cache-stats panel. Of 14 classes, 9 are live.

---

### F81.24 — `SampleScoresGrid.module.css`: `.heading`, `.padded` dead

- **Severity:** INFO
- **Location:** `apps/inspect/src/app/samples/scores/SampleScoresGrid.module.css`
- **Category:** dead-code

---

### F81.25 — `gridCells.module.css`: `.fullWidthHeight` dead

- **Severity:** INFO
- **Location:** `apps/inspect/src/app/shared/gridCells.module.css:56-59`
- **Category:** dead-code

Verified across all four importers (`LogListGrid.tsx`, `columns/hooks.tsx` via spread-merge, `SamplesGrid.tsx`, `samples-grid/hooks.tsx`).

---

### F81.26 — `LoggerEventView.module.css`: `.jsonPanel` dead

- **Severity:** INFO
- **Location:** `packages/inspect-components/src/transcript/LoggerEventView.module.css:8`
- **Category:** dead-code

---

### F81.27 — `SandboxEventView.module.css`: `.contents` dead

- **Severity:** INFO
- **Location:** `packages/inspect-components/src/transcript/SandboxEventView.module.css:1-7`
- **Category:** dead-code

---

### F81.28 — `TranscriptLayout.module.css`: `.sidebarHeaderIcon` dead

- **Severity:** INFO
- **Location:** `packages/inspect-components/src/transcript/TranscriptLayout.module.css:150`
- **Category:** dead-code

---

### F81.29 — `LiveVirtualList.module.css`: `.progressText` dead

- **Severity:** INFO
- **Location:** `packages/react/src/components/LiveVirtualList.module.css:9`
- **Category:** dead-code

---

### F81.30 — `SampleDetailView.module.css` is orphaned

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/samples-panel/SampleDetailView.module.css` (32 lines)
- **Category:** dead-code / styling

**Description:**
`SampleDetailView.tsx` is live (routed via `SamplesRouter.tsx:29`) but does **not** import its sibling CSS module. If the 32 lines of layout rules were ever intended to apply, they currently do not — verify whether `SampleDetailView` is missing styling before deleting.

---

### F81.31 — `InfoTabProps.evalStats` and `.samples` are unused

- **Severity:** INFO
- **Location:** `apps/inspect/src/app/log-view/tabs/InfoTab.tsx:61,63`
- **Category:** dead-code

**Description:**
Both fields are declared on `InfoTabProps` but the destructure omits them, and `useInfoTabConfig` (`InfoTab.tsx:18-55`, the only constructor of the props object) never sets them. F31.14 already flagged `JsonTabProps.selected` and `ErrorTabProps.scrollRef` in the same directory; these two extend that list.

---

## Files reviewed

- [x] All 143 `*.module.css` under scope — full class-level cross-reference
- [x] All 981 named exports under scope — `rg -w` against full `ts-mono/`
- [x] All `FC<*Props>` components under scope — destructure ↔ interface diff

## Open questions / needs verification

- **F81.8** (`sampleLimitMessage`) and **F81.11** (`toTreeItems`, `ResolvedMessageEvent`) are in `packages/` barrels. Per `ts-mono/CLAUDE.md` this monorepo is consumed as a git submodule by the VS Code extension; an out-of-tree consumer could import these. Grep parent repos before deleting.
- **F81.30**: `SampleDetailView.module.css` has 32 lines of layout CSS that are never applied. Is `/samples` route visually correct without it, or is this a regression where the import was accidentally dropped?
- **F81.12** (internal-only exports): some `*Props` interfaces are exported as a documentation/convention pattern. Decide whether to enforce "no superfluous `export`" or leave as style choice.
