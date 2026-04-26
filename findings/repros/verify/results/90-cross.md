# Browser-verify results — `90-cross` batch

**Date:** 2026-04-24
**Logs served:** `findings/repros/logs/90-cross/` (10 `.eval` files)
**Port:** 7581
**Runner:** `uv run --with playwright python findings/repros/verify/verify_one.py F90.1 F90.2 F90.3 F90.4 F90.5 F90.7 F90.14 F80.10 --port 7581`

## Verdict counts

| Verdict | Count |
|---|---|
| CONFIRMED | **8** |
| NOT_REPRODUCED | 0 |
| FALSE_POSITIVE | 0 |
| INCONCLUSIVE | 0 |

All eight repros demonstrate their claimed bugs in the live viewer. No false positives.

---

## Per-finding results

### F90.1 — Two timestamp formats on one screen — **CONFIRMED**

| Surface | Extracted text |
|---|---|
| Transcript event-panel tooltip (`formatTiming` → `@tsmono/util` `formatDateTime`) | `04/23/26, 4:57:46 AM` |
| Transcript EventTimingPanel "Clock Time → Start" | `04/23/26, 4:57:46 AM` |
| Log-list "Completed" column (app-local `formatDateTime`) | `2026-04-23 04:57:46` |

12-hour `MM/DD/YY` locale vs sv-SE `YYYY-MM-DD` 24-hour for the same instant.

> **Minor location correction to the finding:** the sample-detail header (`SampleSummaryView`) and Metadata-tab Time card do **not** render a datetime — they render durations via `formatTime`. The app-local `formatDateTime` callers actually visible in the UI are the log-list "Completed" column (`hooks.tsx:265`) and the Messages-tab `display.formatDateTime` (`SampleDisplay.tsx:551`). The core claim (two coexisting `formatDateTime` shapes) is correct and reproduces; only the "sample header" example surface in the prose is inaccurate.

---

### F90.2 — Three duration precisions — **CONFIRMED**

| Surface | Extracted text |
|---|---|
| Metadata-tab Time card "Working" (app-local `formatTime`) | `2.8 sec` |
| Metadata-tab Time card "Total" | `2.9 sec` |
| Log-list "Duration" column (app-local) | `3.0 sec` |
| Transcript EventTimingPanel "Working Time → Start" (`@tsmono/util` `formatTime`) | `3 sec` |

App-side renders 1-decimal (`2.8 sec` / `3.0 sec`); transcript-side rounds to integer (`3 sec`). The third format (`formatDurationShort` → `3s`) lives in the timeline swimlane and was not extracted, but two divergent formatters on one sample is sufficient.

---

### F90.3 — ScoreEvent bypasses score-descriptor — **CONFIRMED**

| Surface | Rendered HTML |
|---|---|
| Sample-header Score cell | `<span class="_circle_qymy9_1 text-size-small _green_qymy9_12">true</span>` |
| Transcript ScoreEvent "Score" row | `<div class="">true</div>` |

Header uses `BooleanScoreDescriptor` → green-circle badge classes. Transcript `ScoreValue` does `String(value)` → bare unstyled `<div>`.

---

### F90.4 — Multi-log SamplesGrid Status = log status, not sample status — **CONFIRMED**

Multi-log Samples grid row for `sampleId='F90.4-errored'`:

| Column | Value |
|---|---|
| `status` | `success` |
| `error` | `RuntimeError('F90.4: deliberate per-sample error. The parent log still has status=success …')` |

The per-sample `error` field is populated on the row, yet `status` reads `success` (the parent log's terminal status). Single-log Samples tab for the same sample shows the red error icon.

---

### F90.5 — Sample Error tab omits `error.message` — **CONFIRMED**

Sample → Error tab → card body direct children:

```
['_ansiDisplayContainer_1749m_1 text-size-small _ansi_1si8b_29']
```

Only the `ANSIDisplay` traceback — no `ExpandablePanel` / `RenderedContent` for `error.message` above it. Sentinel `F90.5_ERROR_MESSAGE_SHOULD_BE_VISIBLE` is present in the tab text but **only inside the ANSI traceback block** (as Python's `RuntimeError: <msg>` final line); it does not appear outside the ANSI block. `TaskErrorPanel` (log-level) renders message + traceback; the sample-level card does traceback only.

---

### F90.7 — `kModelNone` (`"none/none"`) leaks outside PrimaryBar — **CONFIRMED**

| Surface | Shows `none/none`? |
|---|---|
| Title bar (`PrimaryBar`) | **No** — shows `WORKER:mockllm/model` instead (guard `!== kModelNone` works) |
| Log-list "Model" column | **Yes** — cell text = `none/none` |
| Models tab `ModelCard` | **Yes** — `EVAL → MODEL → none/none` |

One surface treats the sentinel as such; two leak it verbatim.

---

### F90.14 — Numeric score `1.0` formatted three ways — **CONFIRMED**

| Surface | Extracted text |
|---|---|
| Title-bar headline metric (`formatPrettyDecimal`) | `1.0` |
| Log-list "Score" column (`formatPrettyDecimal`) | `1.0` |
| Sample-header Score pill (`formatDecimalNoTrailingZeroes`) | `1` |
| Multi-log Samples grid `score_returns_one_point_zero` (`toFixed(3)`) | `1.000` |

Three distinct renderings — `1` / `1.0` / `1.000` — of the identical underlying value.

---

### F80.10 — Tiny score 1.234e-7 collapses to `"0.000"` — **CONFIRMED**

| Surface | Extracted text |
|---|---|
| Title-bar headline metric (`formatPrettyDecimal`) | `0.000` |
| Log-list "Score" column (`formatPrettyDecimal`) | `0.000` |
| Sample-header Score pill (`formatDecimalNoTrailingZeroes`) | `0.000000` |

All three are indistinguishable from a true-zero score. (For contrast, the transcript ScoreEvent — which uses `String(value)` per F90.3 — correctly shows `1.234e-7`.)

---

## Selector / harness notes for this batch

- **Multi-log Samples grid segment** is `<button class="_segment_*" aria-pressed>` (not a `NavPill` `data-target` button). Locate via `button[aria-pressed]` filtered by text `"Samples"`.
- **Multi-log grid row lookup**: every F90.4 row's `input` cell contains the literal string `"F90.4-errored"` from the bug-description markdown, so `has_text="F90.4-errored"` on `.ag-row` matches the wrong row. Filter on the `sampleId` cell instead: `.ag-row:has(.ag-cell[col-id="sampleId"]:has-text("F90.4-errored"))`.
- **Score event panel lookup**: `event_panel("Score")` matches the Model Call panel (bug-description bleed). Iterate panels and match the **title label**'s exact text instead.
- **`find_log("F90.1")`** is ambiguous (also matches `F90.14-*`). Use `log="F90.1-two"`.
- **F90.1 location correction** noted above — does not change the verdict.

## Files

- Checks: `findings/repros/verify/checks/F90_1.py`, `F90_2.py`, `F90_3.py`, `F90_4.py`, `F90_5.py`, `F90_7.py`, `F90_14.py`, `F80_10.py`
- Raw JSON: `findings/repros/verify/results/90-cross.json`
