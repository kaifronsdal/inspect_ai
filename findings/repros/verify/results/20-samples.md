# Browser-verify results — `20-samples` batch

**Log dir:** `findings/repros/logs/20-samples/` (9 .eval files)
**Port:** 7579
**Checks:** `findings/repros/verify/checks/F20_*.py`, `F21_*.py`
**Runner:** `uv run --with playwright python findings/repros/verify/verify_one.py F20.1 F20.4 F20.5 F20.6 F20.14 F21.1 F21.2 F21.10 --port 7579`

## Verdict counts

| Verdict | Count |
|---|---|
| CONFIRMED | 7 |
| FALSE_POSITIVE | 1 |
| NOT_REPRODUCED | 0 |
| INCONCLUSIVE | 0 |

---

## Per-finding results

### F20.1 — `SampleSummaryView` drops `limit` / `error` / `time` &nbsp; **CONFIRMED**

**Where:** sample-detail header `#sample-heading-*`
**Evidence:** `header labels: ['ID', 'INPUT', 'TARGET']; sample JSON contains limit field: True`

Header shows only Id / Input / Target — no Limit or Time column even though
the sample hit `message_limit=2` (verified present in the sample JSON).
`resolveSample()` (`SampleSummaryView.tsx:76-83`) gates these fields on
`isEvalSample(sample)`, which is always false for the `SampleSummary` that
`SampleDisplay.tsx:466` passes.

---

### F20.4 — Scoring tab uses different descriptor than list/header &nbsp; **CONFIRMED**

**Where:** sample `should_be_C` — list cell vs header vs Scoring tab
**Evidence:**
```
list cell uses circle badge: False
header uses circle badge: False
Scoring tab uses circle badge: True
  → <span class="text-size-small _circle_1iagp_1 _green_1iagp_12">C</span>
```

Value-set `{C, I, X}` → list & header pick `categoricalScoreDescriptor`
(plain `String(score)`). Scoring tab calls `getScoreDescriptorForValues([C],
["string"])` → `passFailScoreDescriptor` → coloured circle badge. Same value
renders three different ways depending on which surface you're looking at.

---

### F20.5 — Scoring tab omits `target` &nbsp; **CONFIRMED**

**Where:** Scoring tab (`#scoring-contents`)
**Evidence:** `Scoring-tab labels: ['INPUT', 'SCORER', 'ANSWER', 'SCORE', 'EXPLANATION']; target sentinel present in header row: True`

The Scoring tab has an `Input` heading and the Scorer/Answer/Score/Explanation
grid but no `Target` row. The target sentinel
`F20.5_TARGET_SHOULD_APPEAR_IN_SCORING_TAB` is visible in the *header row
above the tabs* (proving the sample carries one) but absent as a labelled
field on the tab itself.

---

### F20.6 — `EvalSampleLimit.limit` numeric value never displayed &nbsp; **FALSE_POSITIVE**

**Where:** sample-detail (header + transcript)
**Evidence:**
```
SampleLimitEvent panel text:
  'TOKEN LIMIT EXCEEDED\nToken limit exceeded. value: 20,000; limit: 12,345'
header labels: ['ID', 'INPUT', 'TARGET']
```

The finding states *"The numeric threshold that was hit is not surfaced
anywhere outside the raw JSON tab."* This is **factually wrong**: the
transcript's `SampleLimitEventView` renders `eventNode.event.message`
([`SampleLimitEventView.tsx:71`](../../../src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/SampleLimitEventView.tsx)),
and the Python-generated message string includes the threshold formatted as
`limit: 12,345`. The repro's "Ctrl-F for `12345`" instruction misses it only
because of the thousands separator.

The finding's *narrower* claim — that `SampleSummaryView.tsx:76` reads only
`.type` and not `.limit` — is true at the source level, but cannot be
observed in the live viewer because **F20.1** means the header renders no
Limit column at all (labels = `['ID', 'INPUT', 'TARGET']`). If F20.1 is
fixed first, F20.6's narrow claim should be re-verified; the broad
"nowhere outside JSON" claim should be dropped from the finding regardless.

---

### F20.14 — Object/List score descriptors mis-format `0` &nbsp; **CONFIRMED**

**Where:** sample list, `list_scorer` column
**Evidence:** `list_scorer cell: '[0, 0.333, 1.0]'  →  zero='0', third='0.333', one='1.0'`

`0` falls through `value && isNumeric(value)` to `String(value)` → `"0"`,
while `1.0` and `0.333333` reach `formatPrettyDecimal` → `"1.0"` / `"0.333"`.
Same effect visible in the dict-score key/value grid on the Scoring tab
(`zero → 0`, `one → 1.0`).

---

### F21.1 — Score column sorts alphabetically, not semantically &nbsp; **CONFIRMED**

**Where:** sample list → click score-column header
**Evidence:**
```
after sort-asc click, (id, score) order:
  [('expect_rank_1_C', 'C'),
   ('expect_rank_3_I', 'I'),
   ('expect_rank_4_N', 'N'),
   ('expect_rank_2_P', 'P')]
```

Pass/fail sorts `C, I, N, P` (alphabetical) instead of the semantic
`C, P, I, N` order encoded in `passFailScoreDescriptor.compare()`.
`columns.tsx:288-313` supplies a `valueGetter` but no `comparator`, so
ag-grid's default lexical sort is used and every descriptor's `compare()` is
dead code.

---

### F21.2 — Categorical filter completions show `undefined` &nbsp; **CONFIRMED**

**Where:** sample list → filter input → type `category_scorer == `
**Evidence:**
```
autocomplete items: ['undefined', 'category_scorer', 'epoch', 'has_error',
  'has_retries', 'id', 'error_contains', 'input_contains', 'target_contains',
  'abs', 'ceil', 'floor', ...]
```

The RHS-value section of the dropdown is the literal string `undefined`; the
real category values `good` / `bad` / `ugly` are absent.
`categoricalScoreDescriptor.tsx:10` stores `categories: values` (raw
strings); `filters.ts:182-185` reads `(cat as Record<string, unknown>).val`
which is `undefined` on a string. (Only one `undefined` entry appears — the
three duplicates collapse — but the shape mismatch is the same.)

---

### F21.10 — Multi-log `SamplesGrid` vs single-log `SampleList` formatting &nbsp; **CONFIRMED**

**Where:** `#/samples/` (multi-log grid) vs `#/logs/<file>/samples` (single-log list)
**Evidence:**
```
multi-log grid : passfail='C' (circle badge: False),
                 numeric='2.000',
                 dict='{"a":1,"b":0}'
single-log list: passfail='C' (circle badge: True)
```

Three independent divergences observed for the same sample:
- **passfail** — circle badge in `SampleList`, plain `'C'` in `SamplesGrid`.
- **numeric** — `2.000` in grid (`value.toFixed(3)`, `hooks.tsx:208`); the
  single-log descriptor would render `2` (`formatDecimalNoTrailingZeroes`).
- **dict** — raw `'{"a":1,"b":0}'` JSON blob in grid (`JSON.stringify`,
  `hooks.tsx:206`); single-log uses `objectScoreDescriptor`'s key/value grid.

---

## FALSE_POSITIVE summary

| ID | Claim that is wrong | What the viewer actually does | Source |
|---|---|---|---|
| F20.6 | "The numeric threshold … is not surfaced anywhere outside the raw JSON tab." | Transcript `SampleLimitEvent` panel shows `limit: 12,345` via `event.message`. | `packages/inspect-components/src/transcript/SampleLimitEventView.tsx:71` |
