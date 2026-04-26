# Cross-Cutting Consistency Audit

**Reviewer scope:** Inconsistencies BETWEEN subsystems — same concept rendered differently in different parts of the UI. Compared `apps/inspect/src/app/{log-list,log-view,samples,samples-panel}` against `packages/inspect-components/src/{transcript,chat,usage,content}` and `packages/react/src/components`. Existing per-area findings (01–70) were skimmed first; only NEW cross-area inconsistencies (or material extensions of existing ones) are listed here.
**Date:** 2026-04-22

---

## Summary

The viewer has at least four parallel rendering stacks (log-list grid, single-log sample list, multi-log samples grid, transcript event panels) that each re-derive how to present scores, timestamps, durations, statuses, and errors. Because the shared `@tsmono/util` formatters are shadowed by an app-local `utils/format.ts`, and because the transcript's `ScoreValue` component bypasses the descriptor system entirely, the same datum routinely appears in two or three formats within a single screen. Collapse affordances and empty-state components are similarly forked. Most of these are LOW/MEDIUM polish issues, but F90.4 (wrong status semantics) and F90.5 (sample error tab drops the message) are user-facing data losses.

---

## Findings

### F90.1 — Same screen, two timestamp formats: event panels vs everything app-side

- **Severity:** MEDIUM
- **Location:** `packages/inspect-components/src/transcript/ScoreEventView.tsx:6,36` (and every `*EventView.tsx`, `EventTimingPanel.tsx:4`, `OutlineRow.tsx:6`) vs `apps/inspect/src/app/samples/SampleSummaryView.tsx:15`, `apps/inspect/src/app/samples/SampleDisplay.tsx:57,551`, `apps/inspect/src/app/log-list/grid/columns/hooks.tsx:9`
- **Category:** consistency

**Description:**
F30.18 noted the duplicate `formatDateTime` definitions. The cross-cutting impact is that **both run on the same screen**: every transcript event panel imports `formatDateTime` from `@tsmono/util` (12-hour, locale-default, 2-digit year — e.g. `04/22/26, 3:45:12 PM`), while the sample header above it, the Metadata-tab "Time" card, the log-list "Completed" column, and the Task tab import the app-local shadow (`sv-SE` — `2026-04-22 15:45:12`). The Messages tab is fed the **app-local** formatter via `display.formatDateTime` (SampleDisplay.tsx:551), so within one sample-detail view: header = sv-SE, Messages tab = sv-SE, Transcript tab = 12-hour locale.

**Evidence:**
```ts
// packages/util/src/format.ts:144  — used by all *EventView.tsx
export function formatDateTime(date: Date): string {
  // Intl.DateTimeFormat: "04/22/26, 3:45:12 PM"
}
// apps/inspect/src/utils/format.ts:28 — used by SampleSummaryView, SampleDisplay, log-list
export function formatDateTime(date: Date): string {
  return date.toLocaleString("sv-SE"); // "2026-04-22 15:45:12"
}
```

**Why it matters / impact:**
A user reading the sample header sees `2026-04-22 15:45:12`, scrolls into the transcript and every event subtitle says `04/22/26, 3:45:12 PM`. The two strings are not obviously the same instant; AM/PM vs 24-hour and 2- vs 4-digit year look like different timezones at a glance.

**Suggested fix:**
Delete `apps/inspect/src/utils/format.ts:formatDateTime` and have `@tsmono/util` adopt the sv-SE format (per the comment that "all surveyed users were OK with that format").

---

### F90.2 — Sub-minute durations rendered with three different precisions

- **Severity:** LOW
- **Location:** `apps/inspect/src/utils/format.ts:6-8` vs `packages/util/src/format.ts:33-35` vs `packages/util/src/format.ts:173-181` (`formatDurationShort`)
- **Category:** consistency

**Description:**
Three duration formatters coexist for the same concept:

| Surface | Function | 5.34 s renders as | 125 s renders as |
|---|---|---|---|
| Sample header "Time" / "Working time" tooltip / Metadata-tab Time card / log-list "Duration" | app-local `formatTime` | `5.3 sec` | `2 min 5 sec` |
| Event-panel title (`formatTitle`), `EventTimingPanel`, outline tooltip | `@tsmono/util` `formatTime` | `5 sec` | `2 min 5 sec` |
| Timeline `AgentCardView` / minimap selection | `formatDurationShort` | `5s` | `2m` |

Additionally the app-local variant always emits `… min 0 sec` for whole minutes; the util variant suppresses zero-valued trailing units.

**Why it matters / impact:**
Within one sample-detail view, the header pill says `5.3 sec`, the transcript event title for the same span says `5 sec`, and the timeline card says `5s`. The sample-level "Working" time on the Metadata tab uses a different formatter than the per-event "Working Time" rows directly below it in the Transcript tab.

---

### F90.3 — Transcript `ScoreEvent`/`ScoreEditEvent` bypass the score-descriptor system

- **Severity:** MEDIUM
- **Location:** `packages/inspect-components/src/transcript/ScoreValue.tsx:18-26` vs `apps/inspect/src/app/samples/descriptor/score/{BooleanScoreDescriptor.tsx:14-26,PassFailScoreDescriptor.tsx:42-73,NumericScoreDescriptor.tsx:30-32}`
- **Category:** consistency

**Description:**
The sample list, sample-detail header, and Scoring tab all render score values through `ScoreDescriptor.render()` (colored circle badges for `true`/`false`/`C`/`I`/`P`, `formatDecimalNoTrailingZeroes` for numerics). The transcript's `ScoreEventView` / `ScoreEditEventView` render the **same** `score.value` through `ScoreValue → renderScore`, which does:

**Evidence:**
```tsx
export const renderScore = (value: JsonValue, maxRows?: number): ReactNode => {
  if (Array.isArray(value)) return value.join(", ");
  else if (isRecord(value) && typeof value === "object")
    return <MetaDataGrid entries={value} maxRows={maxRows} />;
  else return String(value);   // ← booleans, "C"/"I", numbers all plain text
};
```

**Why it matters / impact:**
A boolean score appears as a green/red circled `true`/`false` badge in the header pill and as bare `true` text in the Score event right below it; a pass/fail `"I"` is a red badge in one place and a plain `I` in the other; `0.6666666666` is unrounded in the event but trimmed in the header. F20.4 already covered the Scoring-tab divergence; this is a **fourth** independent renderer for the same value. (Extends F20.4 / F21.10.)

**Suggested fix:**
Either thread `evalDescriptor` into the transcript renderer via context, or move the descriptor `render()` implementations into `inspect-components` so `ScoreValue` can call them.

---

### F90.4 — Multi-log `SamplesGrid` "Status" column shows the **log's** status, not the sample's

- **Severity:** MEDIUM
- **Location:** `apps/inspect/src/app/samples-panel/SamplesPanel.tsx:183` + `apps/inspect/src/app/samples-panel/samples-grid/hooks.tsx:151-159` vs `apps/inspect/src/app/samples/list/columns.tsx:80-99`
- **Category:** correctness / consistency

**Description:**
The single-log `SampleList` derives a per-sample status from `sampleStatus(completed, error)` and renders `SampleStatusIcon`. The multi-log `SamplesGrid` populates each row's `status` from `logDetail.status` — the **parent log's** terminal status — and renders it as a plain text cell with no `cellRenderer`.

**Evidence:**
```ts
// SamplesPanel.tsx:178-195  (per-sample row construction)
logDetail.sampleSummaries.forEach((sampleSummary) => {
  const row: SampleRow = {
    ...
    status: logDetail.status,        // ← log-level, identical for every sample
    error: sampleSummary.error,      // per-sample error IS captured…
    completed: sampleSummary.completed || false,
```

**Why it matters / impact:**
In a successful eval where 3/100 samples errored, all 100 rows show `success` in the Status column of the multi-log grid; the same samples show a red error icon in the single-log Samples tab. Conversely, in a cancelled run, every sample row says `cancelled` even for samples that completed before cancellation. The per-sample `error`/`completed` fields are already on the row object — they're just not used for this column.

**Suggested fix:**
Compute `status: sampleStatus(sampleSummary.completed, sampleSummary.error)` and reuse `SampleStatusIcon` as the `cellRenderer`.

---

### F90.5 — Sample "Error" tab omits `error.message`; log "Error" tab shows it

- **Severity:** MEDIUM
- **Location:** `apps/inspect/src/app/samples/SampleDisplay.tsx:607-623` vs `apps/inspect/src/app/log-view/error/TaskErrorPanel.tsx:29-44`
- **Category:** consistency / event-display

**Description:**
Both render the same `EvalError` shape (`{message, traceback, traceback_ansi}`). `TaskErrorCard` shows the `message` in an `ExpandablePanel` followed by the ANSI traceback. The sample-detail Error tab renders **only** the ANSI traceback:

**Evidence:**
```tsx
// SampleDisplay.tsx — sample-level
<Card key={`sample-error}`}>
  <CardHeader label={`Sample Error`} />
  <CardBody>
    <ANSIDisplay output={sample.error.traceback_ansi} ... />
  </CardBody>
</Card>
// TaskErrorPanel.tsx — log-level
<CardHeader icon={ApplicationIcons.error} label={`Task Failed`} />
<CardBody>
  <ExpandablePanel ...><RenderedContent entry={{..., value: error.message}} /></ExpandablePanel>
  <ANSIDisplay output={error.traceback_ansi} ... />
</CardBody>
```

**Why it matters / impact:**
For sample errors whose traceback is empty or whose message contains context not in the traceback (e.g. "ToolException: rate limited after 5 retries (request_id=…)"), the sample Error tab shows nothing useful while the log-level Error tab would. The two cards also disagree on header icon (present vs absent) and label ("Task Failed" vs "Sample Error" — see F90.6).

---

### F90.6 — Error-status label vocabulary differs across the four surfaces that show it

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/log-view/title-view/StatusPanel.tsx:26` ("Task Failed") vs `apps/inspect/src/app/log-list/grid/columns/hooks.tsx:200-206` (tooltip = raw `"error"` / `errorMessage`) vs `apps/inspect/src/app/samples/list/columns.tsx:281` (`"cancelled"` lowercase / raw error string / `"ok"` / `"running"`) vs `apps/inspect/src/app/samples/SampleSummaryView.tsx:229-232` ("Cancelled" Title-Case)
- **Category:** consistency

**Description:**
The same four-state lifecycle is labeled differently everywhere it appears:

| Surface | error | cancelled | running | ok |
|---|---|---|---|---|
| Title-bar `StatusPanel` | "Task Failed" | "Cancelled" | "Running" | (results panel) |
| Log-list grid tooltip | full `errorMessage` / `"error"` | `"cancelled"` | `"started"` | `"success"` |
| Single-log sample list "Status" column | full raw error string | `"cancelled"` | `"running"` | `"ok"` |
| Sample-detail header | `errorType()` (e.g. `"TimeoutError"`) under label "Error" | `"Cancelled"` under label "Status" | — | — |

**Why it matters / impact:**
"Task Failed" / "error" / "TimeoutError" all describe the same status on adjacent screens. The log-list says `started` where the title bar says `Running`. The sample-list "Status" column says lowercase `cancelled` while the sample-detail header right above it says Title-Case `Cancelled`. (Icon-level inconsistency is already F30.2/F61.11; this is the **label** layer.)

---

### F90.7 — `kModelNone` ("none/none") is suppressed in the title bar but rendered verbatim everywhere else

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/log-view/title-view/PrimaryBar.tsx:74` vs `apps/inspect/src/app/log-list/grid/columns/hooks.tsx:160-161`, `apps/inspect/src/app/samples-panel/SamplesPanel.tsx:182`, `apps/inspect/src/app/plan/ModelCard.tsx:24,57`
- **Category:** consistency

**Description:**
`PrimaryBar` guards `evalSpec.model !== kModelNone` before rendering the model name. The log-list "Model" column, multi-log samples-grid "Model" column, and Models-tab `ModelCard` all render the raw string with no such guard, so an eval that used only `model_roles` (model = `"none/none"`) shows a blank in the title bar, `none/none` in the log list, `none/none` in the samples grid, and a "main → none/none" row in the Models tab.

**Why it matters / impact:**
`none/none` is a sentinel, not a model. One surface treats it as such; three surfaces leak it.

---

### F90.8 — "Running" rendered as animated `PulsingDots` for samples but a static `bi-stars` icon for logs

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/samples/status/sampleStatus.tsx:58-64` vs `apps/inspect/src/app/log-list/grid/columns/hooks.tsx:223-224` and `apps/inspect/src/app/log-view/title-view/RunningStatusPanel.tsx:19`
- **Category:** consistency

**Description:**
`SampleStatusIcon` returns `<PulsingDots subtle={false} />` for `status === "running"`. The log-list grid and the title-bar `RunningStatusPanel` use `ApplicationIcons.running` = `"bi bi-stars"` (a static stars glyph).

**Why it matters / impact:**
Two visually unrelated affordances ("✨" vs "•••" pulsing) communicate the same state on adjacent surfaces. A user who learns "stars = running" from the log list won't recognise the pulsing dots in the sample list as the same thing — and vice versa. (Related to but distinct from F30.2/F61.11, which cover error/cancelled icons.)

---

### F90.9 — Three collapse-affordance vocabularies coexist within one transcript view

- **Severity:** LOW
- **Location:** `packages/inspect-components/src/transcript/event/EventPanel.tsx:21-22,161` vs `packages/inspect-components/src/content/IconsContext.tsx:28-29` (RecordTree) vs `packages/react/src/components/ExpandablePanel.tsx:127,145`
- **Category:** collapse-expand / consistency

**Description:**
Within a single rendered Transcript tab:
- **Event panels & outline rows**: outline chevrons — `bi-chevron-right` (collapsed) / `bi-chevron-down` (expanded), click target = chevron + title row.
- **`RecordTree`** (used inside ScoreEvent metadata, ChatMessage metadata, MetaDataGrid, etc.): **filled carets** — `bi-caret-right-fill` / `bi-caret-down-fill`.
- **`ExpandablePanel`** (used inside ChatMessage body, SecondaryBar, ToolOutput): bare-text **`more...` / `less...`** button, no icon.

**Why it matters / impact:**
A user has to learn three separate "this is expandable" signals to read one transcript. The filled carets and outline chevrons are easy to confuse with each other; the `more...` link is easy to miss because it carries no icon at all.

---

### F90.10 — `TranscriptIcons.expand` is chevron-**up**; "Show all messages" therefore points the wrong way

- **Severity:** LOW
- **Location:** `packages/inspect-components/src/transcript/icons.ts:19` + `packages/inspect-components/src/transcript/ModelEventView.tsx:130-134` vs `packages/inspect-components/src/transcript/event/EventPanel.tsx:161` and `packages/inspect-components/src/transcript/timeline/components/TimelineSwimLanes.tsx:429`
- **Category:** collapse-expand / consistency

**Description:**
`TranscriptIcons.expand = "bi bi-chevron-up"`. `ModelEventView` uses it as the icon next to the "Show all messages" link — an **expand** action — so the link reads `︿ Show all messages`. Everywhere else in the transcript, chevron-up means "collapse" (`TimelineSwimLanes` collapse toggle, `ApplicationIcons.collapse.up`) and chevron-down means "expand" (`EventPanel` open state, `ApplicationIcons.expand.down`).

**Evidence:**
```tsx
// icons.ts
expand: "bi bi-chevron-up",
// ModelEventView.tsx
<i className={clsx(TranscriptIcons.expand, styles.showAllIcon)} />
Show all messages
```

**Why it matters / impact:**
The one place `TranscriptIcons.expand` is consumed inverts the chevron-direction convention used by every other expander in the same view.

---

### F90.11 — Three empty-state treatments; `LogView` renders a literally blank panel

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/log-view/LogView.tsx:95` + `packages/react/src/components/EmptyPanel.tsx:7-15` vs `apps/inspect/src/app/samples/scores/SampleScoresGrid.tsx:30` vs `apps/inspect/src/app/log-view/tabs/SamplesTab.tsx:130` (and 6 other `NoContentsPanel` callers)
- **Category:** consistency / styling

**Description:**
- Most empty states use `NoContentsPanel` (icon + centered text, e.g. "No samples", "No sample metadata available").
- `SampleScoresGrid` uses `<EmptyPanel>No Sample Selected</EmptyPanel>` — text only, and per F60.12 `EmptyPanel.css` is never imported so it has **no styling at all**.
- `LogView.tsx:95` uses `<EmptyPanel />` with **no children** — when there's no `evalSpec` the user sees a completely blank pane with no message.

The wording is also inconsistent: "No samples" (sentence case), "No Sample Selected" (Title Case), "Scoring data not available", "JSON not available", "JSON too large to display", "No events to display.", "starting...." (4 dots).

**Why it matters / impact:**
A blank `LogView` is indistinguishable from a load failure. Mixing `EmptyPanel` (unstyled, no icon) with `NoContentsPanel` (styled, icon) for semantically identical states gives some empty screens a polished look and others a "did the app crash?" look.

---

### F90.12 — Sample-ID column header is `"Id"` in two views, `"Sample ID"` in the third

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/samples/list/columns.tsx:103` and `apps/inspect/src/app/samples/SampleSummaryView.tsx:120` (`"Id"`) vs `apps/inspect/src/app/samples-panel/samples-grid/hooks.tsx:121` (`"Sample ID"`)
- **Category:** consistency

**Description:**
The single-log sample list and the sample-detail header label the id column `Id` (lower-d). The multi-log samples grid labels it `Sample ID` (upper-D). For the same field, three other places in the app spell it `ID` (TaskTab `"Task ID"`, `"Run ID"`).

**Why it matters / impact:**
Minor, but `Id` reads as a typo next to `Task ID`/`Run ID` on adjacent tabs, and the two sample grids — which are meant to feel like the same table at different scopes — disagree on the column name.

---

### F90.13 — "Working time" labelled four different ways across surfaces

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/samples/SampleSummaryView.tsx:172` (`"Working time:"`) vs `apps/inspect/src/app/samples/SampleDisplay.tsx:751` (`"Working"`) vs `packages/inspect-components/src/transcript/event/EventTimingPanel.tsx:57` (`"Working Time"`) vs `packages/inspect-components/src/transcript/event/utils.ts:95` (`"@ working time:"`)
- **Category:** consistency

**Description:**
The same `working_time`/`working_start` concept is labelled `Working time` (sentence case) in the sample-header tooltip, `Working` (single word) in the Metadata-tab Time card, `Working Time` (Title Case) as a section header in `EventTimingPanel`, and `@ working time:` (lowercase, prefixed) in the event-panel hover subtitle.

**Why it matters / impact:**
A user trying to correlate the sample-level working time with a per-event working time has to recognise four spellings of the same field. (F31.12 covered intra-TaskTab casing; this is the cross-surface case for the timing labels.)

---

### F90.14 — Metric/score precision: `formatPrettyDecimal` for headlines, `formatDecimalNoTrailingZeroes` for samples, `toFixed(3)` for the multi-log grid

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/log-view/title-view/ResultsPanel.tsx:225`, `ScoreGrid.tsx:71`, `log-list/grid/columns/hooks.tsx:177,542` (all `formatPrettyDecimal`) vs `apps/inspect/src/app/samples/descriptor/score/NumericScoreDescriptor.tsx:31` (`formatDecimalNoTrailingZeroes`) vs `apps/inspect/src/app/samples-panel/samples-grid/hooks.tsx:208` (`value.toFixed(3)`)
- **Category:** consistency

**Description:**
A numeric score/metric of `1` renders as `1.0` in the log-list headline-score column and the title-bar `ResultsPanel` (because `formatPrettyDecimal` forces ≥1 decimal), as `1` in the single-log sample list / sample header (because `formatDecimalNoTrailingZeroes` strips the trailing zero), and as `1.000` in the multi-log samples grid. A value of `0.123456789` renders as `0.123` (headline), `0.123456789` (sample list — `formatDecimalNoTrailingZeroes` does not cap decimals), and `0.123` (multi-log).

**Why it matters / impact:**
Clicking from the log list (`accuracy 0.875`) into the Samples tab (`0.875` per row) into the multi-log Samples panel (`0.875`) is fine, but `1` ↔ `1.0` ↔ `1.000` for an integer-valued metric makes the three views look like they computed different things. (Extends F21.10, which covered only the two sample grids; this adds the headline-metric path.)

---

### F90.15 — Token counts: locale-grouped everywhere except the timeline (`1.2k`) and compaction event (`tokens_before` raw key)

- **Severity:** INFO
- **Location:** `packages/inspect-components/src/usage/ModelUsagePanel.tsx:125`, `transcript/event/utils.ts:110`, `apps/inspect/src/app/log-list/grid/columns/hooks.tsx:383` (all `formatNumber`) vs `packages/inspect-components/src/transcript/timeline/swimlaneLayout.ts:150-157` (`formatTokenCount` → `"48.5k"`) vs `packages/inspect-components/src/transcript/CompactionEventView.tsx:25-28` (snake_case key → `MetaDataGrid`)
- **Category:** consistency

**Description:**
`ModelUsagePanel`, the model-event title, and the log-list "Tokens" column all use `formatNumber` (locale-grouped: `12,345`). The timeline swimlane uses a private `formatTokenCount` that abbreviates (`12.3k`, `1.2M`). `CompactionEventView` pushes `tokens_before`/`tokens_after` into a `MetaDataGrid` under their **snake_case** keys, so the compaction panel shows `tokens_before  12,345` while the model event two rows up shows `input  12,345` (lowercase) and `Output  4,321` (Title Case — see F04.9).

**Why it matters / impact:**
Mostly cosmetic; the timeline abbreviation is intentional for space. Noting it here because `formatTokenCount` is private to `swimlaneLayout.ts` and would drift if a second caller wanted "compact tokens".

---

## Files reviewed

- [x] `packages/util/src/format.ts` — canonical formatters
- [x] `apps/inspect/src/utils/format.ts` — app-local shadows of three util formatters
- [x] `apps/inspect/src/app/log-list/grid/columns/hooks.tsx` — log-list status / tokens / dates / scores
- [x] `apps/inspect/src/app/log-view/title-view/{PrimaryBar,StatusPanel,RunningStatusPanel,SecondaryBar,ResultsPanel,ScoreGrid,ModelRolesView}.tsx`
- [x] `apps/inspect/src/app/log-view/error/TaskErrorPanel.tsx`
- [x] `apps/inspect/src/app/log-view/tabs/{ErrorTab,TaskTab,SamplesTab,RunningNoSamples}.tsx`
- [x] `apps/inspect/src/app/samples/{SampleSummaryView,SampleDisplay,SampleRetriedErrors}.tsx`
- [x] `apps/inspect/src/app/samples/status/sampleStatus.tsx` + `.module.css`
- [x] `apps/inspect/src/app/samples/error/{SampleErrorView.tsx,error.ts}`
- [x] `apps/inspect/src/app/samples/list/columns.tsx`
- [x] `apps/inspect/src/app/samples/scores/{SampleScores,SampleScoresGrid}.tsx`
- [x] `apps/inspect/src/app/samples/descriptor/score/*.tsx`
- [x] `apps/inspect/src/app/samples-panel/{SamplesPanel.tsx,samples-grid/hooks.tsx}`
- [x] `apps/inspect/src/app/appearance/icons.ts`
- [x] `packages/inspect-components/src/transcript/{ScoreValue,ScoreEventView,ScoreEditEventView,ErrorEventView,ModelEventView,CompactionEventView,icons}.tsx`
- [x] `packages/inspect-components/src/transcript/event/{EventPanel,EventTimingPanel,utils}.ts(x)`
- [x] `packages/inspect-components/src/transcript/outline/OutlineRow.tsx`
- [x] `packages/inspect-components/src/transcript/timeline/{swimlaneLayout.ts,components/TimelineSwimLanes.tsx}`
- [x] `packages/inspect-components/src/usage/{ModelUsagePanel,TokenTable,UsageCard}.tsx`
- [x] `packages/inspect-components/src/chat/ChatMessage.tsx`
- [x] `packages/inspect-components/src/content/IconsContext.tsx`
- [x] `packages/react/src/components/{ExpandablePanel,EmptyPanel,NoContentsPanel,ErrorPanel}.tsx`

## Open questions / needs verification

- F90.4: confirm `SamplesGrid` "Status" is intended to be per-sample (the column sits between per-sample `Input` and per-sample score columns, so log-level status looks accidental).
- F90.10: `TranscriptIcons.expand` may have been intended for a different (now-removed) caller; only `ModelEventView` consumes it today.
- F90.1: scout app (`apps/scout`) imports `formatDateTime` from `@tsmono/util` — if the util version is changed to sv-SE, scout's dates will change too. Verify that's acceptable before consolidating.
