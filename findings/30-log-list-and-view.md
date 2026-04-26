# Log List / Log Grid + Log View Header

**Reviewer scope:** `apps/inspect/src/app/log-list/**`, `apps/inspect/src/app/log-view/` (top-level + `error/` + `title-view/`, excluding `tabs/`). Cross-referenced `EvalLog`/`EvalSpec`/`EvalResults`/`EvalStats` in `packages/inspect-common/src/types/generated.ts` and `src/inspect_ai/log/_log.py`.
**Date:** 2026-04-22

---

## Summary

The log-list grid is a recently-reworked AG-Grid surface with per-log preview rows, dynamic per-metric columns, and folder grouping. The log-view header (`TitleView`) renders task/model identity, status badges, and a score summary. Overall structure is sound, but there are several **correctness bugs around column data** (metric-name collisions across scorers, wrong folder item counts, broken filename-timestamp parsing), a **visible icon inconsistency** between the list status column and the detail-view status panel, and a fair amount of **dead code** (`RunningPanel`, `displayIndex`, `itemCount`, `__VIEWER_COMMIT__`). The `SecondaryBar` silently hides itself for any non-`success` log, which removes useful context (dataset/config/duration) for errored and cancelled runs.

---

## Findings

### F30.1 — Per-metric score columns collide when multiple scorers share a metric name

- **Severity:** HIGH
- **Location:** `apps/inspect/src/app/log-list/grid/columns/hooks.tsx:43-63` and `apps/inspect/src/app/log-list/grid/LogListGrid.tsx:204-215`
- **Category:** correctness

**Description:**
Dynamic score columns are keyed solely by `metricName` (e.g. `score_accuracy`). Both the column-discovery loop and the row-population loop iterate every `EvalScore` in `results.scores` and write into `row[\`score_${metricName}\`]`, so when two scorers each report an `accuracy` metric the **last scorer iterated silently wins** and the column header gives no hint which scorer it came from.

**Evidence:**
```ts
// LogListGrid.tsx
for (const evalScore of details.results.scores) {
  if (evalScore.metrics) {
    for (const [metricName, metric] of Object.entries(evalScore.metrics)) {
      row[`score_${metricName}`] = metric.value;   // overwritten per scorer
    }
  }
}
// hooks.tsx
for (const [metricName, metric] of Object.entries(evalScore.metrics)) {
  scoreTypes[metricName] = typeof metric.value;    // same key collision
}
```

**Why it matters / impact:**
For any eval with >1 scorer (extremely common — e.g. `match` + `model_graded_qa`, or multiple `f1`/`accuracy` reducers), the grid shows a single "accuracy" column whose value is whichever scorer happened to be last in the array. Users comparing logs across the grid will be comparing apples to oranges without knowing it.

**Suggested fix:**
Key by `${evalScore.name}/${metricName}` (matching how `ScoreAgGrid` and `toDisplayScorers` keep scorer identity), and use that as the header.

---

### F30.2 — Status icons differ between log-list grid and log-detail header

- **Severity:** MEDIUM
- **Location:** `apps/inspect/src/app/log-list/grid/columns/hooks.tsx:218-244` vs `apps/inspect/src/app/log-view/title-view/StatusPanel.tsx:12-29`
- **Category:** consistency

**Description:**
The grid status cell and the title-view status panel use different icon sets for the same `EvalStatus` values:

| Status      | Grid (`hooks.tsx`)                                 | Title view (`StatusPanel.tsx`)                     |
|-------------|----------------------------------------------------|----------------------------------------------------|
| `error`     | `ApplicationIcons.error` → `bi-exclamation-circle-fill` | `ApplicationIcons.logging.error` → `bi-x-circle`   |
| `cancelled` | `ApplicationIcons.cancelled` → `bi-x-circle`       | `ApplicationIcons.logging.info` → `bi-info-square` |

So `bi-x-circle` means "cancelled" in the list but "error" in the detail header, and the detail header shows an *info* icon for a cancelled run.

**Why it matters / impact:**
Users learn the icon vocabulary from the list, then see contradictory iconography one click deeper. The cancelled→info-square mapping is also semantically wrong on its own.

**Suggested fix:**
Use `ApplicationIcons.error` / `ApplicationIcons.cancelled` in `StatusPanel.tsx` to match the grid (and the sample-level status rendering).

---

### F30.3 — Folder `itemCount` is computed against the wrong directory

- **Severity:** MEDIUM
- **Location:** `apps/inspect/src/app/log-list/LogsPanel.tsx:217-227`
- **Category:** correctness

**Description:**
When building a `FolderLogItem`, `itemCount` filters `logFiles` by `file.name.startsWith(dirname(name))` — but `name` is the full path of the *first file encountered inside that folder*, so `dirname(name)` is that file's **immediate parent**, not the top-level folder being displayed.

**Evidence:**
```ts
itemCount: logFiles.filter((file) =>
  file.name.startsWith(dirname(name))   // dirname of the deep file, not the folder row
).length,
```

**Why it matters / impact:**
For a folder containing multiple sub-directories (`logs/run1/a/x.eval`, `logs/run1/b/y.eval`), the count shown for `run1` will be the number of files under `logs/run1/a` only. (The value is currently propagated into `LogListRow.itemCount` but not rendered — see F30.14 — so the bug is latent today; it will surface the moment someone wires the count into the UI.)

**Suggested fix:**
Filter by `file.name.startsWith(dirWithSlash + dirName + "/")`.

---

### F30.4 — `SecondaryBar` is hidden entirely unless `status === "success"`

- **Severity:** MEDIUM
- **Location:** `apps/inspect/src/app/log-view/title-view/SecondaryBar.tsx:45-47`
- **Category:** event-display

**Description:**
```ts
if (!evalSpec || status !== "success") {
  return null;
}
```
For `error`, `cancelled`, and `started` logs the entire secondary bar — Dataset, Scorer(s), Config (task_args + plan config), Duration, Invalidation — is suppressed.

**Why it matters / impact:**
When triaging a failed or cancelled run, the dataset name, task args, and elapsed duration are exactly what you want to see in the header. All of that data is present on the `EvalSpec`/`EvalStats` regardless of status. Only the scorer summary is genuinely success-gated.

**Suggested fix:**
Render the bar for all statuses; gate only the scorer cell (or duration when `completed_at` is empty).

---

### F30.5 — "Folder-first" sort comparator doesn't keep folders first, and is only applied to two columns

- **Severity:** MEDIUM
- **Location:** `apps/inspect/src/app/shared/gridComparators.ts:11-32` and `apps/inspect/src/app/log-list/grid/columns/hooks.tsx:275,557`
- **Category:** correctness

**Description:**
`createFolderFirstComparator` returns `-1` for folder-vs-file. AG-Grid multiplies comparator output by `-1` for descending sorts, so folders end up **last** when the user reverses the sort — contradicting the docstring "Always put folders first". Separately, only the `completedAt` column and the dynamic scorer columns use this wrapper; sorting by Task, Model, Score, Status, Tokens, etc. uses the default comparator and will interleave folders with files.

**Why it matters / impact:**
In `logs` mode the folder rows jump to the top, the bottom, or the middle of the grid depending on which column header the user clicked and in which direction — there is no stable position.

**Suggested fix:**
Accept `isDescending` (5th comparator arg) and re-invert the folder branch; apply the wrapper uniformly via `defaultColDef.comparator` rather than per-column.

---

### F30.6 — `ViewerOptionsButton` assigns the forwarded ref to two elements

- **Severity:** MEDIUM
- **Location:** `apps/inspect/src/app/log-list/ViewerOptionsButton.tsx:23-33`
- **Category:** correctness

**Description:**
The `forwardRef<HTMLButtonElement>` ref is attached to both the `<button>` and the child `<i>`:
```tsx
<button ref={ref} ...>
  <i ref={ref} className={...} />
</button>
```
The `<i>` mount runs second and overwrites `ref.current` with an `HTMLElement` that is *not* a button.

**Why it matters / impact:**
`ApplicationNavbar` passes this ref to `ViewerOptionsPopover` as `positionEl`. The popover therefore anchors to the 16-px icon glyph rather than the button hit-area; and any future caller treating the ref as `HTMLButtonElement` (e.g. `.disabled`, `.click()`) gets the wrong element.

**Suggested fix:**
Drop the second `ref={ref}`.

---

### F30.7 — `parseLogFileName` produces an `Invalid Date` for the timestamp it extracts

- **Severity:** LOW
- **Location:** `apps/inspect/src/utils/evallog.ts:3-30`
- **Category:** correctness

**Description:**
The regex captures `2024-01-15T14-30-00+00-00` (dashes in place of colons, matching the on-disk filename format) and feeds it directly to `Date.parse`, which returns `NaN` (verified in V8). The returned `timestamp` is therefore always `Invalid Date` when the regex matches.

**Why it matters / impact:**
The grid currently only consumes `.name` from this helper, so the bug is latent — but the field exists on the public return type and will silently misbehave the moment someone uses it (e.g. for a "Started" column fallback when `stats.started_at` is missing).

**Suggested fix:**
Rewrite `T14-30-00+00-00` → `T14:30:00+00:00` before `Date.parse`.

---

### F30.8 — `completedAt` column sorts on the formatted display string

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/log-list/grid/columns/hooks.tsx:256-276`
- **Category:** code-smell

**Description:**
`valueGetter` returns `formatDateTime(new Date(completed))` (a localized `sv-SE` string). The custom comparator then re-parses that string with `new Date(a)`. This works today only because `sv-SE` happens to emit `YYYY-MM-DD HH:mm:ss`, which V8 parses heuristically; it is not a spec-guaranteed round-trip. `cellDataType: "date"` is also declared, but the cell value is a string.

**Why it matters / impact:**
Fragile coupling between the display formatter and the sort comparator. If `formatDateTime` is ever changed (or a non-Chromium engine is used), date sort silently degrades to lexical sort.

**Suggested fix:**
Have `valueGetter` return the raw ISO string (or a `Date`), and move display formatting to `valueFormatter`.

---

### F30.9 — `ModelRolesView` `singleLine` flag is inverted relative to its comment

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/log-view/title-view/ModelRolesView.tsx:18-35`
- **Category:** code-smell

**Description:**
```ts
// Render as a single line if there is only a single model role
const singleLine = Object.keys(roles).length !== 1;
```
The variable is `true` when there is **not** exactly one role, and it controls whether `styles.grid` is applied. Either the comment or the variable name is wrong; the rendered behaviour (grid layout for multi-role, inline for single) may be the intended one but the code reads backwards.

---

### F30.10 — Headline "Score" column has no scorer/metric attribution

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/log-list/grid/LogListGrid.tsx:184` and `apps/inspect/src/client/utils/type-utils.ts:27-38`
- **Category:** consistency

**Description:**
`LogListRow.score` is `preview.primary_metric.value`, where `primary_metric` = first metric of `results.scores[0]`. The column header is just "Score". When two logs in the list use different scorers (or different first metrics), the "Score" column compares unrelated numbers with no visual cue. The detail view's `ResultsPanel` always labels metrics by name; the list does not.

**Suggested fix:**
Set `tooltipValueGetter` to `primary_metric.name` (it's already on `LogPreview`), or render `name: value`.

---

### F30.11 — `useLogListColumns` is invoked twice per render with a state-mutating side effect

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/log-list/LogsPanel.tsx:250` and `apps/inspect/src/app/log-list/grid/LogListGrid.tsx:95`
- **Category:** code-smell / perf

**Description:**
Both `LogsPanel` (for the column-selector popover) and its child `LogListGrid` call `useLogListColumns(mode)`. The hook contains a `useEffect` that writes to `logsActions.setLogsColumnVisibility` whenever a new scorer column appears (`hooks.tsx:66-84`). That side effect therefore fires twice, and the (non-trivial) `scorerMap`/`allColumns` memos are computed twice per render.

**Suggested fix:**
Compute columns once in `LogsPanel` and pass them as a prop to `LogListGrid`.

---

### F30.12 — `ScoreGrid` renders arrays of `<tr>/<th>/<td>` with no React keys

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/log-view/title-view/ScoreGrid.tsx:37-112`
- **Category:** code-smell

**Description:**
`cells.push(<th ...>)`, `rows.push(<tr>...)`, and `subTables.push(<>...</>)` all omit `key=`. React will warn on every header render and may mis-reconcile when score groups change (e.g. live running metrics arriving via polling).

---

### F30.13 — Dead exports and unused props in title-view / log-list

- **Severity:** LOW
- **Location:**
  - `apps/inspect/src/app/log-view/title-view/StatusPanel.tsx:32-40` — `RunningPanel` is exported but never imported (superseded by `RunningStatusPanel`).
  - `apps/inspect/src/app/log-view/title-view/RunningStatusPanel.tsx:11` — `displayMetrics?: RunningMetric[]` prop is declared but never read.
  - `apps/inspect/src/app/log-list/ViewerOptionsPopover.tsx:13` — `__VIEWER_COMMIT__` is declared but never rendered.
  - `apps/inspect/src/app/log-view/title-view/PrimaryBar.tsx:130-132` — hidden `<div id="task-created">` containing `evalSpec.created`; not referenced by any selector/test in-repo.
- **Category:** dead-code

---

### F30.14 — `itemCount` and `displayIndex` are carried on `LogListRow` but never rendered

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/log-list/grid/columns/types.ts:7,14`, `apps/inspect/src/app/log-list/grid/LogListGrid.tsx:171-174,187`, `apps/inspect/src/app/log-list/LogItem.ts:9`
- **Category:** dead-code

**Description:**
`LogListRow.itemCount` is populated from `FolderLogItem.itemCount` but no column reads it. `LogListRow.displayIndex` is read from `item.displayIndex`, which `LogsPanel` never sets (only `SamplesPanel` does), so it is always `undefined` here.

---

### F30.15 — `started_at` populated inconsistently between the two `LogPreview` builders

- **Severity:** LOW
- **Location:** `apps/inspect/src/client/utils/type-utils.ts:20` vs `apps/inspect/src/client/database/utils.ts:27`
- **Category:** consistency

**Description:**
`toLogPreview` sets `started_at: header.stats?.started_at` (wall-clock start). `toLogOverview` sets `started_at: evalSpec.created` (spec-creation timestamp). Both feed the same `LogPreview` shape used by the list. The grid currently only reads `completed_at`, but anything that later reads `started_at` will get different semantics depending on which code path produced the preview.

---

### F30.16 — `InvalidationStatus` swallows date-parse errors

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/log-view/title-view/SecondaryBar.tsx:259-265`
- **Category:** fallback-hiding-errors

**Description:**
```ts
try { return formatDateTime(new Date(timestamp)); }
catch { return timestamp; }
```
`new Date(bad)` does not throw — it returns `Invalid Date`, which `formatDateTime` (→ `toLocaleString`) renders as `"Invalid Date"`. The `catch` is unreachable and gives a false sense of safety; a malformed `ProvenanceData.timestamp` will surface as the literal string `Invalid Date` in the tooltip.

---

### F30.17 — Minor text/label issues

- **Severity:** LOW
- **Location:** multiple
- **Category:** styling

**Description:**
- `UnscoredSamplesView.tsx:20-21` — "Nan" → "NaN" (twice).
- `RunningStatusPanel.tsx:27` — `Running ({sampleCount} samples)` has no singular form (`1 samples`). `StatusPanel.tsx:59` gets this right.
- `LogView.tsx:45` — local `intoTabConfig` (typo for `infoTabConfig`).
- `ViewerOptionsPopover.tsx:136` — success/error styling chosen via `clearMessage.includes("success")` string match; brittle if copy is edited.

---

### F30.18 — Duplicate `formatTime`/`formatDateTime`/`formatDuration` implementations

- **Severity:** INFO
- **Location:** `apps/inspect/src/utils/format.ts` vs `packages/util/src/format.ts`
- **Category:** consistency

**Description:**
The log-list grid imports `formatDateTime`/`formatTime`/`formatDuration` from the **app-local** `utils/format.ts` (sv-SE date, always-shows-seconds duration). `@tsmono/util` exports same-named functions with different behaviour (locale-default 12-hour date, zero-suppressing duration). Other surfaces in the viewer import from `@tsmono/util`. Date and duration strings will therefore differ between the log list and other panels.

---

### F30.19 — `path` column is redundant in folder-grouped mode

- **Severity:** INFO
- **Location:** `apps/inspect/src/app/log-list/grid/LogListGrid.tsx:189` + `LogsPanel.tsx:200-202`
- **Category:** consistency

**Description:**
In `mode === "logs"`, `FileLogItem.name` is set to the bare filename (`fileOrFolderName`), and `LogListRow.path` is set to that same `item.name`. So if a user un-hides the "Path" column in logs mode they see an exact duplicate of "File Name". Only in `tasks` mode does `path` carry the relative directory path.

---

## Files reviewed

- [x] `app/log-list/LogItem.ts` — item union types; `displayIndex` unused here (F30.14)
- [x] `app/log-list/LogListFooter.tsx` — count + spinner footer; clean
- [x] `app/log-list/LogsPanel.tsx` — folder grouping, pending tasks, progress; F30.3, F30.11
- [x] `app/log-list/ViewerOptionsButton.tsx` — F30.6 double ref
- [x] `app/log-list/ViewerOptionsPopover.tsx` — DB stats panel; F30.13, F30.17
- [x] `app/log-list/grid/LogListGrid.tsx` — AG-Grid host, find-in-grid; F30.1, F30.11, F30.14
- [x] `app/log-list/grid/PreformattedTooltip.tsx` — inline-styled tooltip; fine
- [x] `app/log-list/grid/columns/hooks.tsx` — column defs; F30.1, F30.2, F30.5, F30.8
- [x] `app/log-list/grid/columns/types.ts` — `[key: string]: any` escape hatch for score cols
- [x] `app/log-list/grid/columns/columns.module.css` — status colour classes
- [x] `app/log-view/LogView.tsx` — tab host; F30.17 typo
- [x] `app/log-view/LogViewContainer.tsx` — route → store sync; clean
- [x] `app/log-view/LogViewLayout.tsx` — find-band + navbar shell; clean
- [x] `app/log-view/LogSampleDetailView.tsx` — sample deep-link route; clean
- [x] `app/log-view/types.ts` — `TabDescriptor`
- [x] `app/log-view/error/TaskErrorPanel.tsx` — ANSI traceback card; clean
- [x] `app/log-view/title-view/TitleView.tsx` — composes Primary+Secondary
- [x] `app/log-view/title-view/PrimaryBar.tsx` — task/model/status; F30.13 hidden div
- [x] `app/log-view/title-view/SecondaryBar.tsx` — F30.4, F30.16
- [x] `app/log-view/title-view/StatusPanel.tsx` — F30.2, F30.13
- [x] `app/log-view/title-view/RunningStatusPanel.tsx` — F30.13, F30.17
- [x] `app/log-view/title-view/ResultsPanel.tsx` — primary-metric picker + modal trigger
- [x] `app/log-view/title-view/ScoreGrid.tsx` — F30.12
- [x] `app/log-view/title-view/ScoreAgGrid.tsx` — modal score table; clean
- [x] `app/log-view/title-view/ModelRolesView.tsx` — F30.9
- [x] `app/log-view/title-view/UnscoredSamplesView.tsx` — F30.17
- [x] `app/shared/gridComparators.ts` — F30.5
- [x] `utils/evallog.ts` — F30.7
- [x] `utils/format.ts` — F30.18
- [x] `client/utils/type-utils.ts`, `client/database/utils.ts` — F30.15

## Open questions / needs verification

- **F30.4**: Was hiding `SecondaryBar` for non-success a deliberate product decision, or a leftover from before `EvalStats`/`task_args` were available on errored logs? Git history check would help.
- **F30.13**: `#task-created` hidden div in `PrimaryBar` — possibly consumed by an external e2e test or browser extension? Grep in parent repos before deleting.
- `PrimaryBar.tsx:109-128` renders **both** `ResultsPanel` and `ErroredPanel` when `status === "error" && config.continue_on_fail`. Layout-wise they sit side by side in `.taskStatus`; verify this doesn't overflow on narrow viewports.
