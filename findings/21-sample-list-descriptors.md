# Sample List, Descriptors, and Filter/Sort Tools

**Reviewer scope:** `apps/inspect/src/app/samples/list/`, `apps/inspect/src/app/samples/descriptor/`, `apps/inspect/src/app/samples/sample-tools/`, `apps/inspect/src/app/samples-panel/` (incl. `samples-grid/`); cross-referenced `client/api/types.ts`, `state/hooks.ts`, `inspect-common/types/generated.ts`
**Date:** 2026-04-23

---

## Summary

The sample list/grid is built on ag-grid with a parallel "descriptor" subsystem that sniffs score-value types (boolean / numeric / pass-fail / categorical / object / list / other) to pick a renderer and comparator. The type-detection heuristics are reasonable but fragile at the edges (mixed types, first-value-wins). A surprising amount of the descriptor API is **dead code** — every `ScoreDescriptor.compare()`, `ScorerDescriptor.scores()/explanation()/metadata()`, and `SamplesDescriptor.selectedScore` are never invoked, so score-column sorting silently falls back to ag-grid's default lexical sort. There is also a `categories` shape mismatch that breaks autocomplete for categorical-string scores, and the two grid implementations (`SampleList` vs `SamplesGrid`) format the same data inconsistently.

---

## Findings

### F21.1 — `ScoreDescriptor.compare` is never called; score columns sort with ag-grid default

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/list/columns.tsx:288-314`; comparators defined in `descriptor/score/*.tsx`
- **Category:** correctness / dead-code

**Description:**
Every score descriptor (`booleanScoreDescriptor`, `passFailScoreDescriptor`, `numericScoreDescriptor`, `categoricalScoreDescriptor`, `objectScoreDescriptor`, `listScoreDescriptor`, `otherScoreDescriptor`) carefully implements a `compare(a, b)` function, but a repo-wide search shows **zero call sites**. The score column definition in `columns.tsx` supplies only a `valueGetter` and no `comparator`, so ag-grid sorts the raw `ScoreValue` with its default comparator.

**Evidence:**
```tsx
// columns.tsx:288-313 — no comparator supplied
scoreLabels.forEach((label, i) => {
  columns.push({
    headerName: label,
    colId: `score-${i}`,
    valueGetter: (params) => {
      ...
      return samplesDescriptor.evalDescriptor.score(
        params.data.data, selectedScores[i]
      )?.value;
    },
    cellRenderer: (...) => { ... },
  });
});
```

**Why it matters / impact:**
- Pass/fail scores (`"C"`, `"P"`, `"I"`, `"N"`) sort alphabetically (C < I < N < P) instead of the intended semantic order (C → P → I → N) encoded in `passFailScoreDescriptor.compare`.
- Object/array score values are compared as `[object Object]` strings → effectively random order.
- `compareWithNan` handling for numeric NaN is unused.

**Suggested fix:**
Wire the descriptor's comparator into the column def:
```ts
comparator: (a, b) => samplesDescriptor.evalDescriptor
  .scoreDescriptor(selectedScores[i])
  ?.compare({ value: a, render: () => null }, { value: b, render: () => null }) ?? 0
```
…or change `compare` signature to take raw values and pass it directly.

---

### F21.2 — `categories` shape mismatch breaks filter completions for categorical scores

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/descriptor/score/CategoricalScoreDescriptor.tsx:10` vs `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/sample-tools/filters.ts:182-185`
- **Category:** correctness

**Description:**
`ScoreDescriptor.categories` is typed `Array<Object>` (vague). `passFailScoreDescriptor` and `objectScoreDescriptor` populate it with `{val, text}` objects; `categoricalScoreDescriptor` populates it with **raw string values**. The consumer in `sampleFilterItems()` always reads `.val`:

**Evidence:**
```ts
// CategoricalScoreDescriptor.tsx
return { scoreType: kScoreTypeCategorical, categories: values, ... };

// filters.ts:182-185
categories = descriptor.categories.map((cat) => {
  const val = (cat as Record<string, unknown>).val;   // undefined for strings
  return valueToString(val);
});
```

**Why it matters / impact:**
For any string-valued score with <10 distinct values that isn't C/I/P/N, the filter-expression autocomplete suggests `undefined`, `undefined`, … as RHS values, and the tooltip reads `categories: undefined undefined undefined`. The user cannot discover valid values via completion.

**Suggested fix:**
Normalise `categories` to `{val, text}[]` in `categoricalScoreDescriptor`, or make the consumer handle both shapes. Tighten the `ScoreDescriptor.categories` type from `Array<Object>` to `{val: unknown; text: string}[]`.

---

### F21.3 — `ScorerDescriptor.scores()`, `.explanation()`, `.metadata()` are dead code

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/descriptor/samplesDescriptor.tsx:183-261`
- **Category:** dead-code

**Description:**
`scorerDescriptor()` builds an object with `metadata()`, `explanation()`, `answer()`, `scores()`. Repo-wide, only `.answer()` is ever called (`SamplesTab.tsx:113`, `SampleSummaryView.tsx:74`). The 60-line `scores()` closure (which walks score dicts deciding whether keys are "real" sub-scores) is unreachable, as are `scoreExplanation`/`scoreMetadata` helpers.

**Why it matters / impact:**
~80 LOC of untested logic that someone may assume is exercised. The "is this a dict of sub-scores?" heuristic at lines 222-249 is non-trivial and would need review if ever hooked up.

**Suggested fix:**
Delete `scores()`, `explanation()`, `metadata()`, and the supporting `scoreExplanation`/`scoreMetadata` helpers, or wire them to the detail view if that was the intent.

---

### F21.4 — `SamplesDescriptor.selectedScore` is dead code

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/descriptor/samplesDescriptor.tsx:23,352-355`
- **Category:** dead-code

**Description:**
Exported on the public `SamplesDescriptor` interface but never read anywhere (only `evalDescriptor`, `messageShape`, `selectedScorerDescriptor` are consumed).

---

### F21.5 — `filterSamples` re-compiles the filtrex expression once per sample

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/sample-tools/filters.ts:255-260, 335-341`
- **Category:** perf

**Description:**
`filterExpression()` calls `compileExpression(filterValue, {...})` and is itself called inside `samples.filter(...)`. For an eval with 10 000 samples the same expression string is lexed/parsed/compiled 10 000 times on every keystroke (after the 200 ms debounce).

**Evidence:**
```ts
export const filterSamples = (...) => {
  const result = samples.filter((sample) => {
    if (filterValue) {
      const { matches, error: sampleError } = filterExpression(
        evalDescriptor, sample, filterValue   // compiles inside, per-sample
      );
```

**Why it matters / impact:**
Noticeable lag on large logs; the `extraFunctions` capture `sample` so can't be hoisted as-is, but `compileExpression` itself is pure on `filterValue` and could be hoisted once with per-sample functions injected via the `vars` object or closures rebound.

**Suggested fix:**
Compile once outside the loop; pass sample-dependent data via the variable bag rather than closing over `sample` in `extraFunctions`. (filtrex `extraFunctions` can read from a per-call argument: `expression({...vars, __sample: sample})`.)

---

### F21.6 — `descriptor.filterable` accessed before the `!descriptor` guard

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/sample-tools/filters.ts:153-171`
- **Category:** code-smell / fallback-hiding-errors

**Description:**
```ts
const descriptor = evalDescriptor.scoreDescriptor(scoreLabel);
if (descriptor.filterable === false) { return; }   // ← deref before null check
const scoreType = descriptor?.scoreType;           // ← optional-chain after deref
if (!descriptor) { items.push({...}); return; }    // ← unreachable
```
In practice `getScoreDescriptorForValues` always falls through to `otherScoreDescriptor()` so `descriptor` is never undefined, making the `if (!descriptor)` branch dead. But the ordering is illogical and the dead branch misleads readers.

**Suggested fix:**
Drop the `if (!descriptor)` block and the `?.` on line 160, or move the null guard first.

---

### F21.7 — Type detection only inspects `types[0]`; mixed-type scores misclassified

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/descriptor/score/ScoreDescriptor.tsx:84,91`
- **Category:** correctness

**Description:**
The numeric and object categorizers test `types[0] === "number"` / `types[0] === "object"` without checking `types.length === 1`. `types` is built from `new Set(values.map(v => typeof v))`, which preserves insertion (= sample) order. So whether a mixed `["string","number"]` score is treated as numeric or "other" depends on which sample appears first in the log.

**Why it matters / impact:**
Non-deterministic rendering/formatting across runs of the same task when one sample errors and stores a string while others store numbers.

**Suggested fix:**
Replace `types[0] === "number"` with `types.every(t => t === "number")` (or `types.includes("number") && !types.includes("object")` if mixed should still be numeric).

---

### F21.8 — Object/list detection only inspects `values[0]`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/descriptor/score/ScoreDescriptor.tsx:92`
- **Category:** correctness

**Description:**
`if (values.length > 0 && Array.isArray(values[0]))` — if the first sample's score is `[1,2]` and the second is `{a:1}`, the whole column gets `listScoreDescriptor`, whose `render` does `(score as []).forEach(...)` → on the dict sample it iterates nothing (or throws if the runtime's `forEach` is strict). Same first-value-wins fragility as F21.7.

---

### F21.9 — `errorSize` is computed from `errorType()` but the column renders the full message

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/descriptor/samplesDescriptor.tsx:327-333` vs `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/list/columns.tsx:281`
- **Category:** consistency

**Description:**
`messageShape.errorSize` is `errorType(sample.error).length` (e.g. `"TimeoutError"` → 12), and the Status column width is `errorSize * 26`. But the cell renders `error ? error : s` — the **full** error string. The column is therefore always sized for the short type name while showing the long message; everything is clipped to ~1 word.

**Suggested fix:**
Render `errorType(error)` in the Status column (matching the tooltip which already shows the full message), or size the column from the full message length.

---

### F21.10 — `SamplesGrid` (multi-log) and `SampleList` (single-log) format the same data differently

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples-panel/samples-grid/hooks.tsx:183-219` vs `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/list/columns.tsx`
- **Category:** consistency

**Description:**
The two grids are independent implementations:

| Aspect | `SampleList` (single log) | `SamplesGrid` (multi-log) |
|---|---|---|
| Numeric score format | `formatDecimalNoTrailingZeroes` → `1` → `"1"` | `value.toFixed(3)` → `1` → `"1.000"` |
| Dict-valued score | drills into sub-keys via `ScoreLabel`; renders key/value grid | `JSON.stringify(value)` raw |
| Pass/fail render | colored circle badge | plain string `"C"` |
| Input join | `inputString(...).join(" ")` | `inputString(...).join("\n")` |
| Sample ID sort | native value (numeric IDs sort numerically) | `String(id)` → always lexical (`"10" < "2"`) |
| Score type detection | full categorizer over all samples | last-write-wins `typeof` (hooks.tsx:50) |

**Why it matters / impact:**
A user switching between the "Logs → samples" panel and the per-log Samples tab sees the same score rendered three different ways (badge vs `1.000` vs `1`). Dict scores are readable in one view and `{"foo":1,"bar":0}` blobs in the other.

**Suggested fix:**
Have `SamplesGrid` reuse `getScoreDescriptorForValues` (it already exists and is used by `SampleScores.tsx`) for both `valueFormatter` and `comparator`.

---

### F21.11 — `SamplesGrid` score-type map uses last-sample-wins

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples-panel/samples-grid/hooks.tsx:44-56`
- **Category:** correctness

**Description:**
```ts
for (const sample of details.sampleSummaries) {
  if (sample.scores) {
    for (const [name, score] of Object.entries(sample.scores)) {
      scoreTypes[name] = typeof score.value;   // overwritten every iteration
    }
  }
}
```
The last sample iterated determines whether the column gets `agNumberColumnFilter` or `agTextColumnFilter`. With mixed types this is non-deterministic across log appends.

---

### F21.12 — `ListScoreDescriptor`: misplaced array guard, unreachable throw, and typo

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/descriptor/score/ListScoreDescriptor.tsx:20-25`
- **Category:** code-smell

**Evidence:**
```ts
(score as []).forEach((value) => {
  if (!Array.isArray(score)) {
    throw new Error(
      "Unexpected use of list score descriptor for non-lisß object"
    );
  }
```
- The check is inside `.forEach`, so if `score` is not array-like, `.forEach` throws *before* the guard runs.
- It checks `score` (outer) per item instead of once.
- "non-lisß" is a typo for "non-list".

---

### F21.13 — `ScorerTypes` type is wrong (values vs. typeof-strings)

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/descriptor/score/ScoreDescriptor.tsx:12-17`
- **Category:** code-smell

**Description:**
`type ScorerTypes = string | number | boolean | object` is used as the element type of `uniqScoreTypes`, but that array is built from `typeof scoreValue`, which yields the **string literals** `"string" | "number" | "boolean" | "object"`. The `types[0] === "boolean"` comparisons only typecheck because `string` is in the union by accident. Should be `type ScorerTypeName = "string" | "number" | "boolean" | "object"`.

---

### F21.14 — Tokenizer only recognises double-quoted strings; help text uses single quotes

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/sample-tools/sample-filter/tokenize.ts:16-17` vs `SampleFilter.tsx:40`
- **Category:** consistency

**Description:**
`TOKEN_PATTERNS.STRING: /^"[^"]*"/` does not match `'...'`. filtrex itself accepts single quotes, and the help tooltip explicitly suggests `id == 'sample123'`. With single quotes, syntax highlighting and post-literal autocomplete (`logicalOpCompletions`) don't fire, though the filter still evaluates.

**Suggested fix:**
Add `/^'[^']*'/` to the string pattern, or change the tooltip example to double quotes.

---

### F21.15 — `KEYWORDS.sort()` mutates the exported constant

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/sample-tools/sample-filter/tokenize.ts:39-41`
- **Category:** code-smell

**Description:**
`KEYWORDS.sort((a, b) => countSpaces(b) - countSpaces(a))` sorts the array exported from `language.ts` **in place**. `completions.ts:386` then iterates the mutated order. Harmless today (same elements), but a future consumer assuming declaration order would be surprised. Use `[...KEYWORDS].sort(...)`.

---

### F21.16 — Side effects (`setFilterError`) inside `useMemo` in `useFilteredSamples`

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/state/hooks.ts:142-156` (drives `SampleList` items)
- **Category:** code-smell

**Description:**
`useFilteredSamples` calls `setFilterError(error)` / `clearFilterError()` from inside a `useMemo` body. React does not guarantee `useMemo` runs once per dependency change, and calling a store setter during render can trigger re-renders mid-render. In StrictMode dev this fires twice. Should be split into a `useEffect` for the setter and a `useMemo` for the result.

---

### F21.17 — `Math.min/max(...values)` may exceed call-stack on very large evals

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/descriptor/score/NumericScoreDescriptor.tsx:16-17`
- **Category:** perf

**Description:**
`Math.min(...onlyNumeric)` spreads every unique numeric score value as a function argument. For continuous scores on 100k+ samples, all values are unique → 100k arguments → "Maximum call stack size exceeded" in V8 (limit ~65k–120k). Use `values.reduce((m,v)=>Math.min(m,v), Infinity)`.

---

### F21.18 — `font-family: "Consola Regular"` is not a real font

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/descriptor/score/BooleanScoreDescriptor.module.css:2`, `PassFailScoreDescriptor.module.css:2`
- **Category:** styling

**Description:**
Likely intended `"Consolas"`. As written it never matches and falls back to the inherited font, so the "monospace badge" intent is silently lost.

---

### F21.19 — `SampleFooter` always pluralises "Samples"

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/list/SampleFooter.tsx:35-37`
- **Category:** styling

**Description:**
`` `${sampleCount} Samples` `` renders "1 Samples" when filtered to a single row. `SamplesPanel`'s footer (`LogListFooter`) already handles singular/plural; this one doesn't.

---

### F21.20 — `filterModel` read directly in render body without memo/subscription

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples-panel/SamplesPanel.tsx:217-219`
- **Category:** code-smell

**Description:**
```ts
const filterModel = gridRef.current?.api?.getFilterModel() || {};
const filteredFields = Object.keys(filterModel);
const hasFilter = filteredFields.length > 0;
```
Reads imperative grid state during render with no dependency tracking. `hasFilter` (which controls the "Reset Filters" button) is stale until something else re-renders the component. Works only because `onStateUpdated` happens to call `setGridState` → store update → re-render.

---

### F21.21 — `setTimeout(10)` race when toggling "Show Retried Logs"

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples-panel/SamplesPanel.tsx:246-252`
- **Category:** code-smell

**Description:**
Relies on a 10 ms delay for ag-grid to finish reflow before reading `getDisplayedRowCount()`. Fragile; ag-grid exposes `onModelUpdated` for this.

---

### F21.22 — `ObjectScoreDescriptor.module.css` `.padded` class is unused

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/descriptor/score/ObjectScoreDescriptor.module.css:8-10`
- **Category:** dead-code

---

### F21.23 — `BooleanScoreDescriptor` uses literal `"boolean"` instead of `kScoreTypeBoolean`

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/descriptor/score/BooleanScoreDescriptor.tsx:10`
- **Category:** consistency

**Description:**
Every other descriptor imports its `kScoreType*` constant; this one hard-codes the string. `filters.ts:26` compares against `kScoreTypeBoolean`, so a future rename of the constant would silently break boolean coercion.

---

### F21.24 — `uniqScoreValues` Set does not dedupe object/array values

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/descriptor/samplesDescriptor.tsx:112-148`
- **Category:** perf / code-smell

**Description:**
`new Set(samples.map(...scoreValue...))` uses reference equality, so for object/array scores every sample contributes a "unique" entry. `objectScoreDescriptor` then re-deduplicates via `JSON.stringify`. The outer `Set` is thus a no-op for non-primitive scores and the variable name `uniqScoreValues` is misleading. For 50k samples with dict scores this builds a 50k-element array, JSON-stringifies each, then Sets again.

---

### F21.25 — `scoreVariables` iterates array score values as if they were dicts

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/sample-tools/filters.ts:95-102`
- **Category:** correctness

**Description:**
`if (typeof score.value === "object")` is true for arrays; `Object.entries([0.1, 0.2])` yields `[["0", 0.1], ["1", 0.2]]`, so filter variables `scorer.0`, `scorer.1` are registered. Harmless (nobody types those) but list scores were intended to be `filterable: false`. Add `&& !Array.isArray(score.value)`.

---

### F21.26 — `scorerDescriptor().scores()` renders the **whole dict** for every sub-key

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/descriptor/samplesDescriptor.tsx:229-236`
- **Category:** correctness (latent — currently dead per F21.3)

**Description:**
When a dict score's keys match known score names, the code maps `names → {name, rendered: () => myScoreDescriptor.render(scoreVal)}` — passing the **entire dict** `scoreVal` to render for every key, instead of `scoreVal[name]`. If this method is ever wired up, every sub-score row would render the full key/value grid instead of its own value.

---

### F21.27 — `var` declarations in `filters.ts`

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/sample-tools/filters.ts:172-173`
- **Category:** code-smell

**Description:**
`var tooltip` / `var categories` — should be `let`. Only file in scope using `var`.

---

### F21.28 — `optionalColumnsHaveAnyData` lookup with non-optional keys relies on `undefined !== false`

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples-panel/samples-grid/hooks.tsx:280-282`
- **Category:** code-smell

**Description:**
```ts
const isVisible =
  (columnVisibility[field] ?? optionalColumnsHaveAnyData[field]) !== false;
```
For base columns (`task`, `model`, …) and the `created` optional column, `optionalColumnsHaveAnyData[field]` is `undefined`, so visibility defaults to `undefined !== false` → `true`. Works, but `created` ends up default-visible while the comment/effect at lines 59-76 suggests optional columns should default to data-dependent. If `created` was meant to default hidden, it doesn't.

---

## Files reviewed

- [x] `app/samples/list/SampleList.tsx` — ag-grid wrapper; follow-output, warnings, keyboard nav
- [x] `app/samples/list/columns.tsx` — column defs; F21.1, F21.9
- [x] `app/samples/list/SampleFooter.tsx` — F21.19
- [x] `app/samples/list/SampleList.module.css` / `SampleFooter.module.css`
- [x] `app/samples/descriptor/samplesDescriptor.tsx` — core; F21.3, F21.4, F21.9, F21.24, F21.26
- [x] `app/samples/descriptor/types.ts` — `categories?: Array<Object>` weak typing (F21.2)
- [x] `app/samples/descriptor/score/ScoreDescriptor.tsx` — categorizer chain; F21.7, F21.8, F21.13
- [x] `app/samples/descriptor/score/BooleanScoreDescriptor.tsx` — F21.18, F21.23
- [x] `app/samples/descriptor/score/CategoricalScoreDescriptor.tsx` — F21.2
- [x] `app/samples/descriptor/score/NumericScoreDescriptor.tsx` — F21.17
- [x] `app/samples/descriptor/score/PassFailScoreDescriptor.tsx` — F21.1 (compare unused), F21.18
- [x] `app/samples/descriptor/score/ObjectScoreDescriptor.tsx` — F21.22, F21.24
- [x] `app/samples/descriptor/score/ListScoreDescriptor.tsx` — F21.12
- [x] `app/samples/descriptor/score/OtherScoreDescriptor.tsx`
- [x] `app/samples/sample-tools/filters.ts` — F21.2, F21.5, F21.6, F21.25, F21.27
- [x] `app/samples/sample-tools/SelectScorer.tsx` — checkbox click fires twice (row onClick + input onChange both call `handleToggle`; `e.stopPropagation()` on `change` doesn't stop the bubbling `click`) — minor, not numbered
- [x] `app/samples/sample-tools/sample-filter/SampleFilter.tsx`
- [x] `app/samples/sample-tools/sample-filter/completions.ts`
- [x] `app/samples/sample-tools/sample-filter/language.ts`
- [x] `app/samples/sample-tools/sample-filter/tokenize.ts` — F21.14, F21.15
- [x] `app/samples-panel/SamplesPanel.tsx` — F21.20, F21.21
- [x] `app/samples-panel/SampleDetailView.tsx`
- [x] `app/samples-panel/samples-grid/SamplesGrid.tsx`
- [x] `app/samples-panel/samples-grid/hooks.tsx` — F21.10, F21.11, F21.28
- [x] `app/samples-panel/samples-grid/types.ts`
- [x] `state/hooks.ts:75-180` (cross-ref) — F21.16
- [x] `client/api/types.ts:100-146` (cross-ref) — `SampleSummary`, `BasicSampleData`
- [x] `packages/inspect-common/src/types/generated.ts:2360-2375` (cross-ref) — `Score.value` union

## Open questions / needs verification

- **F21.1** — was there a previous custom-sort UI (e.g. a "Sort by score" dropdown) that consumed `compare`, since removed? `git log -S compare descriptor/` would confirm whether this is vestigial vs. never-wired.
- **F21.10** — is `SamplesGrid` intended to eventually replace `SampleList`, or are both permanent? Determines whether to unify formatting or just fix the newer one.
- **SelectScorer double-toggle** — needs runtime check: clicking the checkbox `<input>` directly may toggle on then immediately off (onChange + parent row onClick both call `handleToggle`). Clicking the label area works fine.
- **F21.28** — confirm with design whether `created` column should default hidden in the multi-log samples grid.
