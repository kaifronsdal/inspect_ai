# Sample Display, Scores, Status, Error, Print

**Reviewer scope:** `apps/inspect/src/app/samples/` (top-level + `scores/`, `error/`, `status/`, `scans/`, `print/`, `descriptor/`, `list/columns.tsx`); cross-referenced against `packages/inspect-common/src/types/generated.ts` and `src/inspect_ai/log/_log.py`.
**Date:** 2026-04-22

---

## Summary

The sample-display layer is generally solid, but there is significant divergence between the three places a sample is rendered (list row → summary header → detail tab → print page). The summary header silently drops `limit`/`error`/`time` whenever it receives a `SampleSummary` (which is always, in `SampleDisplay`). The Scoring tab uses a different score-descriptor path than the list and header, so the same score can render differently. The Print route renders nothing for the Error/Retries tabs and uses the Copy icon. A surprising amount of dead code accumulated in the descriptor layer (`compare`, `selectedScore`, `ScorerDescriptor.scores/explanation/metadata`, `FlatSampleErrorView`, `SampleScores.module.css`).

---

## Findings

### F20.1 — `SampleSummaryView` drops `limit`, `error`, `time` for `SampleSummary` inputs

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/SampleSummaryView.tsx:76-83`
- **Category:** consistency / fallback-hiding-errors

**Description:**
`resolveSample()` only reads `limit`, `working_time`, `total_time`, and `error` when `isEvalSample(sample)` is true (i.e. `"store" in sample`). But the only caller, `SampleDisplay.tsx:466`, passes `selectedSampleSummary` (type `SampleSummary`), which never has `store`. So these branches are always `undefined` in practice, even though `SampleSummary` carries `limit?: string` and `error?: string`.

**Evidence:**
```ts
const limit = isEvalSample(sample) ? sample.limit?.type : undefined;
const working_time = isEvalSample(sample) ? sample.working_time : undefined;
const total_time = isEvalSample(sample) ? sample.total_time : undefined;
...
const error = isEvalSample(sample) ? sample.error?.message : undefined;
```

**Why it matters / impact:**
The sample list shows a Limit column and a Status/error column (`columns.tsx:206-285`), but when you open the sample, the header above the tabs never shows Limit, Time, or Error — they only appear in the Metadata/Error tabs. The `limitSize > 0` guard at line 185 is computed from the summaries, so the column would be allocated but never populated. Users see less information in the detail header than in the list row above it.

**Suggested fix:**
Read `limit`/`error` from the `SampleSummary` shape too: `isEvalSample(sample) ? sample.limit?.type : sample.limit`, and `isEvalSample(sample) ? sample.error?.message : sample.error`. (`total_time`/`working_time` would need to be added to the client `SampleSummary` interface — they exist on the generated `EvalSampleSummary`.)

---

### F20.2 — Print route renders blank page for Error and Retries tabs

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/print/SamplePrintView.tsx:163-190`
- **Category:** correctness / consistency

**Description:**
`SamplePrintView` switches on `view` (`?view=` query param) but only handles `kSampleTranscriptTabId`, `kSampleMessagesTabId`, `kSampleScoringTabId`, `kSampleMetdataTabId`, `kSampleJsonTabId`. The Print button in `SampleDisplay.tsx:257-266` passes `effectiveSelectedTab` unconditionally — so if the user is on the **Error** or **Retries** tab and hits Print/Ctrl+P, the print window opens, the MutationObserver settles, and `window.print()` fires on a page containing only the heading.

**Why it matters / impact:**
User gets a near-empty printout with no indication of why. Auto-close (`window.close()`) means they can't even inspect the page.

**Suggested fix:**
Either add Error/Retries cases to `SamplePrintView`, or have `printSampleUrl` map unknown tabs to `transcript`.

---

### F20.3 — Print button uses the Copy icon

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/SampleDisplay.tsx:438-443`
- **Category:** styling

**Description:**
The Print toolbar button uses `icon={ApplicationIcons.copy}` (`bi bi-copy`). There is no `ApplicationIcons.print` defined in `appearance/icons.ts`.

**Why it matters / impact:**
Two adjacent buttons (the Copy dropdown and the Print button) both show the copy glyph. Confusing.

**Suggested fix:**
Add `print: "bi bi-printer"` to `ApplicationIcons` and use it.

---

### F20.4 — Scoring tab uses a different descriptor than list/header → inconsistent score rendering

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/scores/SampleScores.tsx:17-21` vs `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/list/columns.tsx:304-306`
- **Category:** consistency

**Description:**
In the sample **list** and **header**, scores render via `evalDescriptor.score(sample, label).render()` — the descriptor is chosen once from the distribution of values across **all** samples. In the **Scoring tab**, `SampleScores` builds a fresh descriptor from the single value:

**Evidence:**
```ts
const scorerDescriptor = getScoreDescriptorForValues(
  [scoreData.value],
  [typeof scoreData.value]
);
return scorerDescriptor?.render(scoreData.value);
```

**Why it matters / impact:**
The categorizer ladder in `ScoreDescriptor.tsx` is value-set sensitive. Example: an eval with 12 distinct string scores → list uses `otherScoreDescriptor` (RenderedContent); Scoring tab sees one value → `categoricalScoreDescriptor` (plain `String()`). Or a numeric eval with values `{0,1}` matches the second categorizer (`numericScoreDescriptor`) only when *both* 0 and 1 are present (`values.length === 2`); a single `1` falls through to the generic numeric branch — same renderer here, but the contract is fragile. The same score value can look different in the header pill vs the Scoring grid.

**Suggested fix:**
Have `SampleScoresGrid` use `evalDescriptor.score(evalSample, {scorer, name: scorer})?.render()` so all three views share one renderer.

---

### F20.5 — Scoring tab omits `target`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/scores/SampleScoresView.tsx:48-85`
- **Category:** event-display

**Description:**
The Scoring tab shows **Input** (with choices) and a grid of Scorer/Answer/Score/Explanation. `sample.target` is never rendered, even though it's the value the answer is compared against.

**Why it matters / impact:**
A reviewer reading the Scoring tab cannot tell whether the score is correct without flipping back to the Transcript or header.

---

### F20.6 — `EvalSampleLimit.limit` (numeric value) never displayed

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/SampleSummaryView.tsx:76,185-191`
- **Category:** event-display

**Description:**
`EvalSampleLimit` is `{type, limit: number}`. Only `.type` is shown ("token", "message", …). The numeric threshold that was hit is not surfaced anywhere outside the raw JSON tab.

**Why it matters / impact:**
"Limit: token" tells you which limit, not what the limit was. Low impact since the value is in the JSON tab.

---

### F20.7 — `ScorerDescriptor.scores()` / `.explanation()` / `.metadata()` are dead code

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/descriptor/samplesDescriptor.tsx:183-262`
- **Category:** dead-code

**Description:**
`selectedScorerDescriptor()` is only ever invoked for `.answer()` (`SampleSummaryView.tsx:74`, `SamplesTab.tsx:113`). The `scores()`, `explanation()`, and `metadata()` methods (≈70 lines, including the dict-of-scores special-casing at 216-259) are never called. Additionally `SamplesDescriptor.selectedScore` (line 352) is never called anywhere.

**Why it matters / impact:**
The `scores()` body also contains a latent crash: line 213 `sample.scores[scoreLabel.scorer].value` dereferences without checking the scorer key exists. Dead code with a landmine.

**Suggested fix:**
Delete `scores`/`explanation`/`metadata` from `ScorerDescriptor` and `selectedScore` from `SamplesDescriptor`; collapse `selectedScorerDescriptor` to a plain `selectedAnswer(sample)` helper.

---

### F20.8 — `ScoreDescriptor.compare()` is dead code

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/descriptor/types.ts:37`; all `descriptor/score/*.tsx`
- **Category:** dead-code

**Description:**
Every score descriptor implements `compare(a, b)` but no call site exists. Sorting now goes through ag-grid `valueGetter` (`columns.tsx:294`). `min`/`max` and `categories` *are* used (by `sample-tools/filters.ts`), but `compare` is not.

---

### F20.9 — `FlatSampleErrorView.tsx` and `SampleScores.module.css` are unused

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/error/FlatSampleErrorView.tsx`; `.../scores/SampleScores.module.css`
- **Category:** dead-code

**Description:**
`FlatSampleError` is exported but never imported anywhere in the monorepo. `SampleScores.module.css` (`.grid` class) is never imported by `SampleScores.tsx`.

---

### F20.10 — `SampleErrorView` has unused `align` and `style` props

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/error/SampleErrorView.tsx:10-23`
- **Category:** dead-code

**Description:**
`align` is accepted, defaulted to `"center"`, then never used. `style` is declared on the props interface but not destructured or applied. The single call site (`SampleSummaryView.tsx:221`) passes neither.

---

### F20.11 — `SampleScoresGrid`: `as any as SampleSummary` cast and "metadataa" id typo

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/scores/SampleScoresGrid.tsx:89,117`
- **Category:** code-smell

**Evidence:**
```tsx
<SampleScores sample={evalSample as any as SampleSummary} scorer={scorer} />
...
<RecordTree id={`${scorer}-metadataa`} ... />
```

**Why it matters / impact:**
The double cast papers over the fact that `SampleScores` only needs `{scores}` — see F20.4 for the deeper fix. `metadataa` is harmless (only used as a state key) but sloppy.

---

### F20.12 — `SampleScoresGrid` row separators only appear when metadata is present

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/scores/SampleScoresGrid.tsx:103-131`
- **Category:** styling / consistency

**Description:**
A `<div className={styles.separator}>` is emitted only inside the `Object.keys(metadata).length > 0` branch. With multiple scorers where some have metadata and some don't, the grid alternates between separated and run-together rows.

---

### F20.13 — `ListScoreDescriptor`: unreachable guard + "non-lisß" typo

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/descriptor/score/ListScoreDescriptor.tsx:20-25`
- **Category:** code-smell

**Evidence:**
```ts
(score as []).forEach((value) => {
  if (!Array.isArray(score)) {
    throw new Error("Unexpected use of list score descriptor for non-lisß object");
  }
```

**Why it matters / impact:**
The check is inside `forEach`, so if `score` weren't an array we'd have already thrown on `.forEach`. The guard is dead and the message contains a stray `ß`. (Same dead-guard pattern in `ObjectScoreDescriptor.tsx:44`, though there it at least narrows the type for line 49.)

---

### F20.14 — Object/List score descriptors mis-format `0` and `false`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/descriptor/score/ObjectScoreDescriptor.tsx:51-57`; `ListScoreDescriptor.tsx:27-33`
- **Category:** correctness

**Evidence:**
```ts
const formattedValue =
  value && isNumeric(value)
    ? formatPrettyDecimal(...)
    : String(value);
```

**Why it matters / impact:**
`value && …` short-circuits for `0` and `false`, so `0` renders as `"0"` (unformatted) while `0.5` renders via `formatPrettyDecimal`. For dict scores where some keys are `0` and others `0.333…`, the column is visually inconsistent. Also `parseFloat(value === true ? "1" : value)` is reached only when `value` is truthy and numeric — so the `true → "1"` branch is dead given `isNumeric(true)` is likely false; either way booleans bypass the formatter.

---

### F20.15 — `messagesFromEvents` can crash on empty `choices`; uses `Iterator.toArray()`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/messagesFromEvents.ts:30,37`
- **Category:** correctness

**Evidence:**
```ts
const outputMessage = e.output.choices[0].message;
...
return messages.values().toArray();
```

**Why it matters / impact:**
A `ModelEvent` with `output.choices = []` (e.g. an aborted/empty completion that didn't set `error`) throws `Cannot read properties of undefined (reading 'message')`. Separately, `MapIterator.prototype.toArray()` is an ES2025 iterator helper — fine in current Chrome/Edge/Firefox but `Array.from(messages.values())` is the conventional, fully-portable spelling.

---

### F20.16 — `kSampleMetdataTabId` constant is misspelled

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/constants.ts:25`
- **Category:** code-smell

**Description:**
`kSampleMetdataTabId` (missing the second "a") is used in `SampleDisplay.tsx` and `SamplePrintView.tsx`. The string value (`"metadata"`) is correct, so this is purely a source-level typo.

---

### F20.17 — `SampleDisplay.module.css`: duplicate `.padded` rule, unused classes

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/SampleDisplay.module.css:20-23,49-51,37-43`
- **Category:** dead-code / styling

**Description:**
`.padded` is defined twice (line 20: `padding-left:0.8em; margin-top:0.4em` and line 49: `padding:1em`). The second silently overrides the first. `.timePanel` (lines 37-43) is unused. `styles.transcriptContainer` is referenced at `SampleDisplay.tsx:485` but no `.transcriptContainer` rule exists in the module → resolves to `undefined` and `clsx` drops it.

---

### F20.18 — `SampleScoresView.module.css` has many orphaned classes

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/scores/SampleScoresView.module.css`
- **Category:** dead-code

**Description:**
`.label`, `.scoreTable`, `.bottomBorder`, `.headerScore`, `.targetValue`, `.answerValue`, `.scoreValue`, `.noLeft`, `.noTop` are not referenced from `SampleScoresView.tsx`. Only `.container`, `.wordBreak`, `.scoreCard`, `.scores` are used. Likely leftovers from a previous table-based layout.

---

### F20.19 — Error card key contains stray `}`

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/SampleDisplay.tsx:609`
- **Category:** code-smell

**Evidence:**
```tsx
<Card key={`sample-error}`}>
```

The literal key string is `"sample-error}"`. Harmless (single child) but clearly a typo.

---

### F20.20 — Cancelled samples render redundant Error + Status columns in header

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/SampleSummaryView.tsx:218-233`
- **Category:** consistency

**Description:**
When a full `EvalSample` with a `CancelledError` is shown, `fields.error` is the message and `fields.cancelled` is true → the header pushes **both** an Error column (rendering `SampleErrorView` with the grey-styled "CancelledError") and a Status column reading "Cancelled". (In practice this is masked by F20.1 because the caller passes a `SampleSummary`, but the logic is wrong if/when an `EvalSample` is passed.)

**Suggested fix:**
Skip the Error column when `fields.cancelled` is true.

---

### F20.21 — `inputString` drops non-text content silently (images, audio, reasoning)

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-common/src/utils/inputString.ts:18-24`
- **Category:** event-display

**Description:**
`inputString()` flattens `ChatMessage[]` input to text by mapping non-`text` content blocks to `""`. A sample whose input is a single image therefore renders as an empty Input cell in the list, header, and Scoring tab.

**Why it matters / impact:**
Multimodal evals show blank inputs in every summary surface. A `[image]`/`[audio]` placeholder would communicate that content exists.

---

### F20.22 — `booleanScoreDescriptor` uses literal `"boolean"` instead of `kScoreTypeBoolean`

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/descriptor/score/BooleanScoreDescriptor.tsx:10`
- **Category:** consistency

**Description:**
All other descriptors use the `kScoreType*` constants from `constants.ts`; this one hard-codes `"boolean"`. `filters.ts:26` compares against `kScoreTypeBoolean`, which happens to be `"boolean"`, so it works — but it's the only descriptor not using the constant.

---

### F20.23 — `samplesDescriptor` calls `Object.keys()` on potentially primitive `value`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/descriptor/samplesDescriptor.tsx:127-133`
- **Category:** correctness

**Evidence:**
```ts
if (scoreLabel.scorer !== scoreLabel.name) {
  return (
    Object.keys(sample.scores).includes(scoreLabel.scorer) &&
    Object.keys(sample.scores[scoreLabel.scorer].value).includes(scoreLabel.name)
  );
}
```

**Why it matters / impact:**
When `scorer !== name` (sub-score selected), this assumes `value` is an object. `Score.value` may be `string | number | boolean | array | object`. `Object.keys(42)` → `[]` (wrong but harmless); `Object.keys("ab")` → `["0","1"]` (could spuriously match a numeric `name`). Not a crash, but type-unsound and could mis-filter the value set used to pick a descriptor.

---

### F20.24 — `EvalSample` fields never surfaced in any UI tab

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/SampleDisplay.tsx:670-796` (metadata builder)
- **Category:** event-display

**Description:**
The Metadata tab covers `invalidation`, `model_usage`, `total_time`/`working_time`, `metadata`, `store`. Fields on `EvalSample` that are never rendered outside the raw JSON tab: `sandbox`, `files`, `setup`, `output` (the final `ModelOutput`), `role_usage`, `started_at`, `completed_at`. Most are debug-only, but `role_usage` parallels `model_usage` and `started_at`/`completed_at` are user-relevant.

---

### F20.25 — Print view omits the sample summary header

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/print/SamplePrintView.tsx:152-161`
- **Category:** consistency

**Description:**
The interactive view always renders `<SampleSummaryView>` (input/target/answer/score row) above the tab content. The print view renders only the eval heading + "Sample {id} (Epoch {epoch})", then the tab body. A printed transcript has no input/target/score context.

---

### F20.26 — Typos in comments

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/descriptor/samplesDescriptor.tsx:208,227`
- **Category:** code-smell

**Description:**
"standlone" → "standalone" (line 208); double space "are  scores" (line 227).

---

### F20.27 — `SampleScannerPicker` label lowercase "scanner:" inconsistent with other labels

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/scans/SampleScannerPicker.tsx:25`
- **Category:** styling

**Description:**
Label text is `scanner:` (lowercase, trailing colon). Elsewhere in the sample view, labels use the `text-style-label` class which uppercases (e.g. "Scorer", "Input", "Target"). Minor visual inconsistency in the scans sidebar header.

---

## Files reviewed

- [x] `SampleDisplay.tsx` — main tabbed view; Print icon wrong; stray `}` key; missing `.transcriptContainer` CSS
- [x] `SampleDisplay.module.css` — duplicate `.padded`; unused `.timePanel`
- [x] `SampleSummaryView.tsx` — drops summary fields; redundant cancelled column
- [x] `SampleSummaryView.module.css` — ok
- [x] `SampleDetailComponent.tsx` — ok; clean keyboard handling
- [x] `InlineSampleDisplay.tsx` — ok
- [x] `SampleJSONView.tsx` — ok (size guard)
- [x] `SampleRetriedErrors.tsx` — ok; well-structured collapse state
- [x] `SamplesTools.tsx` — ok
- [x] `sampleDataAdapter.ts` — ok
- [x] `messagesFromEvents.ts` — `choices[0]` crash; `.toArray()`
- [x] `scores/SampleScoresView.tsx` — no Target shown
- [x] `scores/SampleScoresGrid.tsx` — `as any` cast; "metadataa"; uneven separators
- [x] `scores/SampleScores.tsx` — divergent descriptor path
- [x] `scores/SampleScores.module.css` — unused file
- [x] `scores/SampleScoresView.module.css` — many dead classes
- [x] `error/SampleErrorView.tsx` — unused `align`/`style` props
- [x] `error/FlatSampleErrorView.tsx` — entirely unused
- [x] `error/error.ts` — ok (relies on `repr(ex)` paren format from Python)
- [x] `status/sampleStatus.tsx` — ok; consistent icon/colors
- [x] `print/SamplePrintView.tsx` — missing Error/Retries; missing summary header
- [x] `scans/SampleScansSidebar.tsx` — ok
- [x] `scans/SampleScannerPicker.tsx` — lowercase label
- [x] `scans/scanReferences.ts` — ok; well-documented
- [x] `descriptor/samplesDescriptor.tsx` — large dead-code block; `Object.keys` on primitive
- [x] `descriptor/types.ts` — `compare` dead
- [x] `descriptor/score/*.tsx` — list "lisß" typo; 0/false formatting; literal "boolean"
- [x] `list/columns.tsx` — ok; cross-referenced for consistency with header
- [x] `list/SampleList.tsx` / `SampleFooter.tsx` — ok

## Open questions / needs verification

- F20.1: confirm there is no other call site that passes a full `EvalSample` to `SampleSummaryView` (grep found none, but the type union suggests there once was).
- F20.15: verify `Iterator.prototype.toArray` is in the project's TS lib target / browserslist; if `lib: ["ESNext"]` it type-checks but may need a polyfill for older Safari.
- F20.24: is `role_usage` intentionally omitted from the Usage card, or just forgotten when the field was added on the Python side?
