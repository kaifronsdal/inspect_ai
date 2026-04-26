# Log-View Tabs, Plan Display, Navbar, Shared

**Reviewer scope:** `apps/inspect/src/app/log-view/tabs/`, `apps/inspect/src/app/plan/`, `apps/inspect/src/app/navbar/`, `apps/inspect/src/app/shared/`; cross-referenced against `EvalSpec`/`EvalPlan`/`EvalConfig`/`EvalRevision`/`EvalDataset` in `packages/inspect-common/src/types/generated.ts`
**Date:** 2026-04-22

---

## Summary

The log-view tab set (Samples / Task / Models / Info / Error / JSON) is structurally sound but has notable data-coverage gaps: `EvalConfig` is computed but never rendered, solver step params and `EvalPlan.finish` are dropped, and several `EvalSpec`/`EvalRevision` fields (`dirty`, `task_file`, `task_version`, `approval`, etc.) are unreachable from any tab except raw JSON. There is one active correctness bug (the JSON-tab "Copy JSON" feedback never fires because it queries a CSS class that no longer exists in `ToolButton`), one likely XSS vector in breadcrumb width-measurement, several dead props/CSS modules, and a typo'd DOM id containing a backtick. Label casing drifts between Title Case and snake_case within the Task tab.

---

## Findings

### F31.1 — `EvalConfig` is built but never rendered in Task tab

- **Severity:** HIGH
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/log-view/tabs/TaskTab.tsx:54-59`
- **Category:** event-display / dead-code

**Description:**
`TaskTab` copies every key of `evalSpec.config` into a local `config` record, then never references it. The Task tab therefore shows Task ID, Run ID, revision, packages, sandbox, timing, and `task_args` — but never `EvalConfig` (epochs, limit, message_limit, token_limit, time_limit, max_samples, fail_on_error, retry_on_error, approval, etc.).

**Evidence:**
```ts
const config: Record<string, unknown> = {};
Object.entries(evalSpec?.config || {}).forEach((entry) => {
  const key = entry[0];
  const value = entry[1];
  config[key] = value;
});
// `config` never used after this point
```

**Why it matters / impact:**
Users cannot see eval-level configuration (epochs, sample limits, concurrency caps, approval policy) anywhere in the structured UI — only in the raw JSON tab. The dead loop also suggests a regression: a "Config" card was likely removed without removing the prep code.

**Suggested fix:**
Render a `<Card><CardHeader label="Config"/><MetaDataGrid entries={config}/></Card>` block when `Object.keys(config).length > 0`, or delete the dead loop.

---

### F31.2 — Solver step params are never displayed

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/plan/SolverDetailView.tsx:24-27`
- **Category:** event-display

**Description:**
`SolversDetailView` renders each `EvalPlanStep` via `<DetailStep name={step.solver} />` and omits `params`. `DetailStep` accepts and renders a `params` prop (used by `ScorerDetailView`), but the solver path never passes it. `EvalPlanStep.params` and `params_passed` are therefore invisible.

**Evidence:**
```tsx
<DetailStep
  name={step.solver}
  className={clsx(styles.items, "text-size-small")}
/>
```

**Why it matters / impact:**
The Info-tab "Solvers" column shows only solver names with arrows between them; users can't see how each solver was parameterised (e.g. `generate(tool_choice=...)`, `react(max_turns=...)`). Scorers in the same card *do* show params, so the asymmetry looks like a bug.

**Suggested fix:**
Pass `params={step.params}` (or `params_passed`) to `DetailStep`.

---

### F31.3 — `EvalPlan.finish` and `EvalPlan.name` are never surfaced

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/plan/PlanDetailView.tsx:26` (and related: `SolverDetailView.tsx`)
- **Category:** event-display

**Description:**
`PlanDetailView` reads only `plan?.steps`. The optional `finish` step (a final `EvalPlanStep`) and the plan `name` are ignored. `plan.config` (a `GenerateConfig`) is also unused here — it appears only in `SecondaryBar` merged with `task_args` under the generic label "Config".

**Why it matters / impact:**
Tasks that define a `finish` solver have it silently omitted from the solver chain diagram.

**Suggested fix:**
Append `plan.finish` as the last `DetailStep` in `SolversDetailView`.

---

### F31.4 — JSON-tab "Copy JSON" feedback never fires (broken DOM query)

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/log-view/tabs/JsonTab.tsx:51-68` (and related: `packages/react/src/components/ToolButton.tsx:32-36`)
- **Category:** correctness

**Description:**
`copyFeedback` queries `e.currentTarget.querySelector(".task-btn-copy-content")` to find the button label, but `ToolButton` renders the label as a bare text node (`{label}`) with no wrapping element or class. `textEl` is always `null`, so the "Copied!" feedback and icon swap never run. Only the ClipboardJS copy itself (via `data-clipboard-target`) works.

**Evidence:**
```ts
const textEl = e.currentTarget.querySelector(".task-btn-copy-content");
const iconEl = e.currentTarget.querySelector("i.bi");
if (textEl) {  // always falsy
  ...
```

**Why it matters / impact:**
Clicking "Copy JSON" gives no visual confirmation; users may click repeatedly or assume copy failed.

**Suggested fix:**
Either wrap the label in `ToolButton` with a stable class, or replace `copyFeedback` with the shared `CopyButton` component pattern, or use local React state for feedback instead of DOM mutation.

---

### F31.5 — Breadcrumb width measurement injects path text via `innerHTML`

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/navbar/useBreadcrumbTruncation.ts:49-51,79-86`
- **Category:** correctness / code-smell

**Description:**
To measure breadcrumb width, the hook builds `<li>` elements by string-interpolating `segment.text` into `innerHTML`. Path segments come from `currentPath.split("/")` plus the log dir. A directory name containing `<`, `>`, or `&` would (a) produce a different measured width than the rendered `<Link>{segment.text}</Link>`, and (b) inject markup into the live DOM (the test element is appended to the visible container, only hidden by `visibility:hidden`).

**Evidence:**
```ts
testElement.innerHTML = segments
  .map((segment) => `<li class="breadcrumb-item">${segment.text}</li>`)
  .join("");
```

**Why it matters / impact:**
Filesystem paths are user-controlled. While script execution via `innerHTML` is blocked by browsers, `<img onerror=...>` is not. At minimum the width calculation is wrong for paths containing HTML metacharacters.

**Suggested fix:**
Build the `<li>` nodes with `document.createElement` + `textContent`, or escape `segment.text` before interpolation.

---

### F31.6 — `evalSampleCount` collapses to 0 when `epochs` is unset

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/log-view/tabs/SamplesTab.tsx:89-92`
- **Category:** correctness / fallback-hiding-errors

**Description:**
The expected-total computation multiplies by `(selectedLogDetails?.eval.config.epochs || 0)`. `EvalConfig.epochs` is optional/nullable; when not set (single-epoch eval), the product is `0`, so `SampleList` receives `totalItemCount={0}` for an eval that has samples.

**Evidence:**
```ts
return (
  (limitCount || selectedLogDetails?.eval.dataset.samples || 0) *
  (selectedLogDetails?.eval.config.epochs || 0)
);
```

**Why it matters / impact:**
Progress display ("N of M") will show "of 0" for single-epoch runs that omit `epochs` in config. `SampleList` elsewhere defaults `epochs || 1` (`SampleList.tsx:78`); this site does not.

**Suggested fix:**
Default to `1`, not `0`.

---

### F31.7 — Backtick typo in DOM id `task-metadata`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/plan/PlanCard.tsx:45`
- **Category:** code-smell

**Description:**
`<CardBody id={"task-metadata`"}>` — the id literal contains a stray backtick character. The rendered attribute is ``id="task-metadata`"``.

**Why it matters / impact:**
Any selector targeting `#task-metadata` will miss. Harmless today (nothing queries it) but clearly a typo.

---

### F31.8 — Duplicate DOM id `task-card-config`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/log-view/tabs/TaskTab.tsx:127,167`
- **Category:** correctness / a11y

**Description:**
Both the "Task Info" `CardBody` and the "Task Args" `CardBody` use `id="task-card-config"`. When task args are present, two elements share the same id.

**Why it matters / impact:**
Invalid HTML; breaks any future `getElementById`/`aria-labelledby` use.

---

### F31.9 — `SolverDetailView` references `styles.items` but CSS defines `.item`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/plan/SolverDetailView.tsx:16,26` (and related: `SolverDetailView.module.css:7`)
- **Category:** styling / dead-code

**Description:**
TSX uses `styles.items` (plural). The CSS module exports `.item` (singular). `styles.items` is `undefined`, so `clsx` drops it and `margin-bottom: 0` is never applied. The `.item` rule is dead.

**Suggested fix:**
Rename one side to match.

---

### F31.10 — Revision link assumes GitHub; `dirty` flag not shown

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/log-view/tabs/TaskTab.tsx:69-78` (and related: `packages/util/src/git.ts:4-9`)
- **Category:** correctness / event-display

**Description:**
`ghCommitUrl` rewrites only `git@github.com:` and assumes `${origin}/commit/${sha}` URL shape. For GitLab/Bitbucket/self-hosted origins the link 404s (GitLab uses `/-/commit/`). Separately, `EvalRevision.dirty` is never displayed, so users can't see that the eval was run from a dirty working tree.

**Why it matters / impact:**
Broken links for non-GitHub repos; reproducibility-relevant `dirty` bit hidden.

**Suggested fix:**
Render commit as plain text when origin is not recognised; append `(dirty)` or a warning icon when `revision.dirty === true`.

---

### F31.11 — Package list always labelled "Inspect"

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/log-view/tabs/TaskTab.tsx:80-90`
- **Category:** consistency

**Description:**
`evalSpec.packages` is a generic `Record<string,string>` of package→version (may include `inspect_ai`, `inspect_evals`, third-party plugins). The Task tab labels the row "Inspect" regardless of how many packages or what they are.

**Evidence:**
```ts
if (names.length === 1) {
  taskInformation["Inspect"] = names[0];
} else {
  taskInformation["Inspect"] = names;
}
```

**Suggested fix:**
Label it "Packages".

---

### F31.12 — Task tab label casing is inconsistent

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/log-view/tabs/TaskTab.tsx:64-104`
- **Category:** consistency

**Description:**
Within the same `taskInformation` grid: `"Task ID"`, `"Run ID"`, `"Git Revision"`, `"Inspect"` use Title Case, while `"tags"`, `"sandbox"`, `"sandbox_config"` use lower/snake_case. The adjacent timing grid uses `"Start"`/`"End"`/`"Duration"` (Title Case).

**Why it matters / impact:**
Same card, two casing conventions.

---

### F31.13 — Start/End/Duration show epoch-0 dates when stats missing

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/log-view/tabs/TaskTab.tsx:107-110,135-145`
- **Category:** fallback-hiding-errors

**Description:**
`new Date(evalStats?.started_at || 0)` falls back to `1970-01-01T00:00:00Z` when `evalStats` is undefined or `started_at` is `""` (which the schema explicitly allows: `string | ""`). The Task tab then renders "Start: Jan 1, 1970" / "Duration: 0 sec" instead of omitting the rows.

**Why it matters / impact:**
Misleading data displayed for running/incomplete evals. The Models tab guards on `evalStatus !== "started"` for usage; the Task tab does not for timing.

**Suggested fix:**
Render the timing grid only when `evalStats?.started_at` is truthy.

---

### F31.14 — Dead/unused props on tab components

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/log-view/tabs/InfoTab.tsx:58-68`, `ErrorTab.tsx:26-31`, `JsonTab.tsx:71-80`
- **Category:** dead-code

**Description:**
- `InfoTabProps` declares `evalStats` and `samples` — never passed by `useInfoTabConfig`, never destructured. Conversely `evalError` is passed in `componentProps` but absent from `InfoTabProps` and never read.
- `ErrorTabProps` declares `scrollRef` — destructured signature omits it; never used in body.
- `JsonTabProps` declares `selected` — computed and passed by the hook, never read by `JsonTab`.

**Why it matters / impact:**
Props drift makes the hook/component contract misleading; suggests partially-refactored code.

---

### F31.15 — Stale "Individual hook for Info tab" comment on every tab

- **Severity:** INFO
- **Location:** `ErrorTab.tsx:8`, `ModelsTab.tsx:10`, `TaskTab.tsx:18`
- **Category:** code-smell

**Description:**
`useErrorTabConfig`, `useModelsTab`, and `useTaskTabConfig` are each preceded by the comment `// Individual hook for Info tab` — copy-pasted from `InfoTab.tsx` and never updated.

---

### F31.16 — Empty/dead CSS modules

- **Severity:** INFO
- **Location:** `tabs/InfoTab.module.css`, `tabs/ModelsTab.module.css`, `navbar/ViewSegmentedControl.module.css`
- **Category:** dead-code

**Description:**
All three files are empty (1 line). `InfoTab.tsx` and `ModelsTab.tsx` don't import their modules; `ViewSegmentedControl.tsx` doesn't import its module either.

---

### F31.17 — Dead CSS rules in `PlanDetailView.module.css`

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/plan/PlanDetailView.module.css:16-22,43-49`
- **Category:** dead-code

**Description:**
`.oneCol`, `.twoCol`, and `.row` are defined but never referenced from `PlanDetailView.tsx`. Additionally `.floatingCol`/`.wideCol` set `flex: 0 1 1` / `flex: 1 1 1` (invalid third value — `flex-basis` cannot be unitless `1`; browsers ignore the whole declaration) on children of a CSS *grid*, where `flex` has no effect anyway.

---

### F31.18 — Undefined CSS-module references in `Navbar.tsx` and `ColumnSelectorPopover.tsx`

- **Severity:** INFO
- **Location:** `navbar/Navbar.tsx:114,122` (`styles.pathLink`, `styles.pathSegment`); `shared/ColumnSelectorPopover.tsx:125` (`styles.popover`)
- **Category:** dead-code / styling

**Description:**
These class names are read from the CSS module but no matching selectors exist in `Navbar.module.css` / `ColumnSelectorPopover.module.css`. `clsx` silently drops the `undefined`.

---

### F31.19 — `createFolderFirstComparator` ignores sort direction

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/shared/gridComparators.ts:14-32`
- **Category:** correctness

**Description:**
The comparator returns `-1` for folders unconditionally. AG-Grid passes `isDescending` as the 5th argument so comparators can keep pinned groups stable; this implementation drops it. When the user sorts a column descending, folders move to the *bottom* despite the docstring promising "folders are always displayed first, regardless of sort order".

**Evidence:**
```ts
if (itemA.type !== itemB.type) {
  return itemA.type === "folder" ? -1 : 1;
}
```

**Suggested fix:**
Accept the 5th `isDescending` arg and return `isDescending ? 1 : -1` for the folder case.

---

### F31.20 — `RunningNoSamples` ellipsis count mismatch

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/log-view/tabs/RunningNoSamples.tsx:13-15`
- **Category:** consistency

**Description:**
The visually-hidden a11y text reads `starting...` (3 dots); the visible text reads `starting....` (4 dots). Also lower-case "starting" is inconsistent with other status strings in the app.

---

### F31.21 — `useJsonTabConfig` re-stringifies entire log header on every store update

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/log-view/tabs/JsonTab.tsx:22-47`
- **Category:** perf

**Description:**
`JSON.stringify(header, null, 2)` runs inside `useMemo` keyed on `[selectedLogFile, logDetails, selectedTab]`. Because `selectedTab` is in the dep array, switching between *any* two tabs (e.g. Samples → Task) re-serialises the entire header object even though the JSON tab isn't visible and `logDetails` hasn't changed. For large headers (`kJsonMaxSize` = 10 MB) this is a noticeable main-thread stall on every tab click.

**Suggested fix:**
Drop `selectedTab` from the memo deps (the `selected` prop it feeds is unused per F31.14), or stringify lazily inside `JsonTab` only when rendered.

---

### F31.22 — `DatasetDetailView` null-checks `dataset` after dereferencing it

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/plan/DatasetDetailView.tsx:18-28`
- **Category:** code-smell / fallback-hiding-errors

**Description:**
`Object.entries(dataset)` runs unconditionally on line 20; the `if (!dataset || ...)` guard on line 23 can never observe `!dataset` without having already thrown. The "No dataset information available" branch fires only when every field is `null`/filtered — but since `EvalDataset` fields are all optional and `MetaDataGrid` will happily render `null` values, the practical effect is a grid of `name: null / location: null / ...` rather than the intended fallback.

**Why it matters / impact:**
Fallback text effectively unreachable; null fields render as empty cells. Also `sample_ids` is silently dropped with no UI affordance to view it (intentional per the comment, but means dataset `sample_ids` is unreachable outside JSON).

---

### F31.23 — Stray `{" "}` text node after `TaskErrorCard`

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/log-view/tabs/ErrorTab.tsx:43`
- **Category:** code-smell

**Description:**
`<TaskErrorCard ... />{" "}` — trailing literal space inside the padded container. Harmless but clearly accidental.

---

### F31.24 — `ScorerDetailView` mutates and shadows the `params` prop

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/plan/ScorerDetailView.tsx:21-23`
- **Category:** code-smell

**Description:**
`params = { ...params, ["scores"]: scores };` reassigns a function parameter. Works because of the spread, but shadowing props is a lint smell and `["scores"]` is a needlessly computed key.

---

### F31.25 — `EvalSpec` fields not reachable from any structured tab

- **Severity:** INFO
- **Location:** `packages/inspect-common/src/types/generated.ts:1477-1558` vs. `app/log-view/tabs/*` + `app/plan/*`
- **Category:** event-display

**Description:**
Cross-referencing the schema against all tab renderers, the following `EvalSpec` fields have no structured display (JSON tab only): `created`, `eval_id`, `eval_set_id`, `task_file`, `task_version`, `task_registry_name`, `task_attribs`, `task_args_passed`, `solver` / `solver_args` / `solver_args_passed` (top-level, distinct from `plan.steps`), `metrics` (definitions), `scorers` (definitions — only `results.scores` are shown). From `EvalLog`: `version`, `reductions`, `log_updates`, `invalidated` (the latter is shown in `SecondaryBar` but not in any tab body).

**Why it matters / impact:**
Mostly acceptable — JSON tab is the catch-all. Flagging for completeness; `task_file` and `created` in particular would be cheap, useful additions to the Task Info card.

---

### F31.26 — `ColumnSelectorPopover` uses `<a>` without `href` for buttons

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/shared/ColumnSelectorPopover.tsx:132-168`
- **Category:** a11y

**Description:**
"All" / "None" toggles are `<a onClick=...>` with no `href`, no `role="button"`, no keyboard handler. They are not focusable and not announced as actionable by screen readers.

**Suggested fix:**
Use `<button type="button">` styled as a link.

---

### F31.27 — Breadcrumb truncation appends test element to observed container

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/navbar/useBreadcrumbTruncation.ts:46,111-125`
- **Category:** perf / code-smell

**Description:**
`measureAndTruncate` is the `ResizeObserver` callback and also runs `container.appendChild(testElement)` / `removeChild` on the *observed* container. The test element is `position:absolute` so it shouldn't change layout size, but mutating the observed node inside its own observer callback is fragile and is the canonical trigger for "ResizeObserver loop completed with undelivered notifications" console warnings. The function also calls `setTruncatedData` inside a loop (line 92) and again after the loop (line 104) — the loop body's last successful iteration already set the right value, so the post-loop branch is only needed when no iteration succeeded; logic is correct but convoluted.

**Suggested fix:**
Append the test element to `document.body` instead of the observed container, and compute the final result before a single `setTruncatedData` call.

---

### F31.28 — `LogView` typo `intoTabConfig`

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/log-view/LogView.tsx:45`
- **Category:** code-smell

**Description:**
`const intoTabConfig = useInfoTabConfig(...)` — should be `infoTabConfig`. (Out of strict scope but adjacent to the reviewed hooks.)

---

## Files reviewed

- [x] `app/log-view/tabs/ErrorTab.tsx` — stray whitespace, unused scrollRef, copy-pasted comment
- [x] `app/log-view/tabs/InfoTab.tsx` — dead props (evalStats/samples/evalError)
- [x] `app/log-view/tabs/InfoTab.module.css` — empty, dead
- [x] `app/log-view/tabs/JsonTab.tsx` — broken copy feedback, perf re-stringify, unused `selected`
- [x] `app/log-view/tabs/JsonTab.module.css` — ok
- [x] `app/log-view/tabs/ModelsTab.tsx` — copy-pasted comment; otherwise ok
- [x] `app/log-view/tabs/ModelsTab.module.css` — empty, dead
- [x] `app/log-view/tabs/RunningNoSamples.tsx` — ellipsis mismatch
- [x] `app/log-view/tabs/RunningNoSamples.module.css` — ok
- [x] `app/log-view/tabs/SamplesTab.tsx` — `epochs || 0` bug
- [x] `app/log-view/tabs/TaskTab.tsx` — dead `config`, dup id, label casing, 1970 fallback, packages label, gh-only link
- [x] `app/log-view/tabs/TaskTab.module.css` — ok
- [x] `app/log-view/tabs/types.ts` — ok
- [x] `app/plan/DatasetDetailView.tsx` — null-check after deref; sample_ids hidden
- [x] `app/plan/DatasetDetailView.module.css` — ok
- [x] `app/plan/DetailStep.tsx` — ok
- [x] `app/plan/DetailStep.module.css` — ok
- [x] `app/plan/ModelCard.tsx` — `as any as` casts (acceptable), otherwise ok
- [x] `app/plan/ModelCard.module.css` — ok
- [x] `app/plan/PlanCard.tsx` — backtick in id
- [x] `app/plan/PlanDetailView.tsx` — drops `plan.finish`/`plan.name`/`plan.config`
- [x] `app/plan/PlanDetailView.module.css` — dead `.oneCol`/`.twoCol`/`.row`; invalid `flex` shorthand
- [x] `app/plan/ScorerDetailView.tsx` — param reassignment
- [x] `app/plan/ScorerDetailView.module.css` — ok
- [x] `app/plan/SolverDetailView.tsx` — drops `step.params`; `styles.items` typo
- [x] `app/plan/SolverDetailView.module.css` — `.item` dead due to typo
- [x] `app/navbar/ApplicationNavbar.tsx` — ok
- [x] `app/navbar/Navbar.tsx` — undefined `styles.pathLink`/`pathSegment`
- [x] `app/navbar/Navbar.module.css` — ok
- [x] `app/navbar/NavbarButton.tsx` — ok (thin wrapper)
- [x] `app/navbar/NavbarButton.module.css` — ok
- [x] `app/navbar/ViewSegmentedControl.tsx` — ok
- [x] `app/navbar/ViewSegmentedControl.module.css` — empty, dead
- [x] `app/navbar/useBreadcrumbTruncation.ts` — innerHTML injection, ResizeObserver self-mutation
- [x] `app/shared/ColumnSelectorPopover.tsx` — `<a>` without href; undefined `styles.popover`
- [x] `app/shared/ColumnSelectorPopover.module.css` — ok
- [x] `app/shared/agGrid.ts` — ok
- [x] `app/shared/gridCells.module.css` — ok
- [x] `app/shared/gridComparators.ts` — folder-first ignores `isDescending`
- [x] `app/shared/gridKeyboardNavigation.ts` — ok
- [x] `app/shared/gridUtils.ts` — ok
- [x] `app/shared/sample.ts` — ok

## Open questions / needs verification

- F31.1: Was there previously a "Config" card on the Task tab that was removed? `git log -p TaskTab.tsx` would confirm whether the dead `config` loop is a regression or never-finished work.
- F31.6: Need to confirm whether the backend always populates `config.epochs` even for single-epoch runs — if it does, the `|| 0` is harmless in practice (but still wrong as a default).
- F31.19: Verify in the running app that sorting a log-list column descending actually moves folders to the bottom (depends on whether AG-Grid negates the comparator result or expects the comparator to handle it).
