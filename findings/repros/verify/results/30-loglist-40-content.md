# Browser-verify results — `30-loglist` + `40-content` batches

**Log dirs:** `findings/repros/logs/30-loglist/` (8 .eval), `findings/repros/logs/40-content/` (2 .eval)
**Port:** 7580
**Checks:** `findings/repros/verify/checks/F30_*.py`, `F31_*.py`, `F40_*.py`
**Runner:** `uv run --with playwright python findings/repros/verify/verify_one.py F30.1 F30.2 F30.4 F31.1 F31.2 F31.3 F31.6 F40.1 F40.5 --port 7580`

## Verdict counts

| Verdict | Count |
|---|---|
| CONFIRMED | 7 |
| FALSE_POSITIVE | 1 |
| NOT_REPRODUCED | 0 |
| INCONCLUSIVE | 1 |

---

## Per-finding results

### F30.1 — Per-metric score columns collide on shared metric name &nbsp; **CONFIRMED**

**Where:** log-list grid (root `#/logs`), "Choose Columns" popover + `score_accuracy` column
**Evidence:** `Column-selector accuracy entries: ['accuracy']; grid accuracy col-ids: ['score_accuracy']; F30.1 row score_accuracy='1.0', score='0.0'`

Two scorers (`scorer_alpha` accuracy=0.0, `scorer_beta` accuracy=1.0) collapse to a
single `accuracy` column. The popover offers exactly one `accuracy` checkbox; the
enabled column shows `1.0` (last scorer iterated wins, overwriting alpha's `0.0`).
The headline `score` column shows `0.0` (first metric of `scores[0]`), so the same
row displays `0.0` and `1.0` for "accuracy" with no scorer attribution.
`row[\`score_${metricName}\`]` overwrite at `LogListGrid.tsx:204` /
`hooks.tsx:55`.

---

### F30.2 — Status icons differ between list grid and detail header &nbsp; **CONFIRMED**

**Where:** log-list Status cell vs `nav.navbar` StatusPanel for the errored F30.2 log
**Evidence:** `list status <i> classes: ['bi-exclamation-circle-fill']; detail header <i> classes: ['bi-x-circle']`
**Artifacts:** `artifacts/F30.2-list-status.png`, `artifacts/F30.2-detail-header.png`

Same `status="error"`: list uses `ApplicationIcons.error` (`bi-exclamation-circle-fill`),
header `StatusPanel.tsx:25` uses `ApplicationIcons.logging.error` (`bi-x-circle`).
`bi-x-circle` is what the *list* uses for `cancelled`, so the same glyph means two
different things one click apart.

---

### F30.4 — `SecondaryBar` hidden for non-success logs &nbsp; **CONFIRMED**

**Where:** `nav.navbar` for errored F30.4 vs successful F31.1
**Evidence:**
```
error-log navbar:   'F30.4_secondary_bar_hidden_ERROR … TASK FAILED (1 SAMPLE)'
success-log navbar: 'F31.1_eval_config_not_rendered … ACCURACY 0.0 STDERR 0.0 DATASET 1 x 7 samples SCORER match DURATION 0.0 sec'
```
**Artifacts:** `artifacts/F30.4-error-header.png`, `artifacts/F30.4-success-header.png`

Errored log's header has no `DATASET` / `SCORER` / `DURATION` row; the success log
right next to it does. `task_args.distinctive_arg='F30.4_TASK_ARG'` is in the .eval
but suppressed by the `status !== "success"` guard at `SecondaryBar.tsx:45`.

---

### F31.1 — `EvalConfig` is built but never rendered &nbsp; **CONFIRMED**

**Where:** Task tab + Info tab
**Evidence:** `Task-tab matches: {message_limit: False, token_limit: False, '999999': False, fail_on_error: False}; Info-tab matches: {…all False}`

`.eval` has `epochs=7, message_limit=42, token_limit=999999, fail_on_error=0.5`
(verified via `read_eval_log`). None appear in the Task or Info tab. `TaskTab.tsx:54-59`
copies `evalSpec.config` into a local `config` record that is never read.

---

### F31.2 — Solver step params never displayed &nbsp; **CONFIRMED**

**Where:** Info tab → `#task-plan-card-body` → Solvers column
**Evidence:** `Plan card text: 'DATASET … SOLVERS parameterised_solver SCORER includes'`

Solvers column shows the bare name `parameterised_solver`; the params
`my_param='F31.2_SHOULD_BE_VISIBLE'`, `threshold=0.777`, `retries=3` (present in
`plan.steps[0].params`) are absent. `SolverDetailView.tsx:24-27` calls
`<DetailStep name={step.solver}/>` without `params=`. (The adjacent Scorer column
*does* render `includes` — but with no visible params either; `includes()` has only
a default `ignore_case` arg, so the asymmetry isn't visually obvious here.)

---

### F31.3 — `EvalPlan.name` never surfaced; `EvalPlan.finish` claim is FALSE &nbsp; **CONFIRMED (partial)**

*(Re-audited 2026-04-24 after manual user test; repro regenerated.)*

**Where:** Info tab + Task tab → `#task-plan-card-body`
**Evidence:** `plan.name 'F31.3_PLAN_NAME_SHOULD_APPEAR_SOMEWHERE' on Info tab: False, on Task tab: False; finish solver in Solvers card: True; Plan card text: 'DATASET … SOLVERS generate f31_3_finish_solver SCORER match'`
**Artifacts:** `artifacts/reaudit2/F31.3-info-tab.png`

The finding bundles two claims:

| Claim | Verdict | Why |
|---|---|---|
| `plan.name` never shown | **CONFIRMED** | Ctrl-F for the sentinel on Info AND Task tabs → 0 hits. `PlanDetailView.tsx:26` reads only `plan?.steps`; the column header is the hard-coded literal `"Solvers"` (`:41`). |
| `plan.finish` "silently omitted from the solver chain diagram" | **FALSE_POSITIVE** | `f31_3_finish_solver` **is** in the Solvers diagram. Root cause: `_eval/task/log.py:361-362` does `if plan.finish: eval_plan.steps.append(eval_plan_step(plan.finish))` — the Python writer duplicates `finish` into `steps` before the log is written. `read_eval_log` confirms `plan.steps = [generate, f31_3_finish_solver]` AND `plan.finish = f31_3_finish_solver`. The viewer iterating `steps` is therefore sufficient; the finding's suggested fix ("append `plan.finish` as the last `DetailStep`") would **duplicate** the entry. |

**Recommend:** keep F31.3 for `plan.name` only; drop the `plan.finish` half (or
reword to "`plan.finish` is redundant data — viewer correctly ignores it").

---

### F31.6 — `evalSampleCount` collapses to 0 when `epochs` unset &nbsp; **FALSE_POSITIVE**

**Where:** Samples tab → `SampleFooter`
**Evidence:** `footer strings on Samples tab: ['3 Samples']`

Footer correctly shows `3 Samples`, not `0`. The repro deliberately omits
`epochs=`, but the resulting `.eval` has `config.epochs: 1` anyway:

```python
# src/inspect_ai/log/_log.py:73-84
def eval_config_defaults() -> EvalConfigDefaults:
    return {"epochs": 1, "epochs_reducer": ["mean"], ...}

# src/inspect_ai/_eval/task/log.py:174-176 — applied before the log is written
for name, value in eval_config_defaults().items():
    if getattr(eval_config, name, None) is None:
        setattr(eval_config, name, value)
```

So `config.epochs` is **never** null/undefined in any real log, and
`(config.epochs || 0)` at `SamplesTab.tsx:91` always evaluates to `≥ 1`. The
finding's own open-question anticipated this: *"Need to confirm whether the backend
always populates `config.epochs` even for single-epoch runs — if it does, the
`|| 0` is harmless in practice."* It does. The `|| 0` is a code smell (should be
`|| 1` for defence-in-depth) but produces no observable bug. **Downgrade to
INFO/code-smell.**

---

### F40.1 — RecordTree default-collapse never fires &nbsp; **CONFIRMED**

**Where:** Sample → Metadata tab (`#metadata-contents`)
**Evidence:** `Without any clicks, Metadata tab already shows deep leaf ('L7_leaf' present=True) and wide leaf ('child_11' present=True).`
**Artifacts:** `artifacts/F40.1-metadata.png`

(Re-run of the existing check — still CONFIRMED.) 7-level-deep and 12-child-wide
branches both render fully expanded on mount; the `if (collapsedIds) return;`
guard treats `{}` as truthy so `defaultCollapsedIds` is never computed.

---

### F40.5 — `web_search` renderer array fails `isValidElement` &nbsp; **INCONCLUSIVE** (repro broken)

**Where:** Sample → Metadata tab; Transcript → Sample Init
**Evidence:** `[metadata tab] raw-json=False, formatted-links=0; [collapsed] value cell: 'Object(2)'; [transcript] event-panel titles: ['SOLVER: GENERATE', 'MODEL CALL: …']`

The repro puts `{"web_search": {query, results:[…]}}` in `sample.metadata`, but
**neither surface routes the object through the `web_search` renderer**:

1. **Sample Metadata tab** uses `RecordTree`, which flattens objects into child
   rows. The `web_search` row's `item.value` is the *string* `"Object(2)"`
   (`RecordTree.tsx:365`), so when collapsed `RenderedContent` receives
   `{name:"web_search", value:"Object(2)"}` and `web_search.canRender`'s
   `typeof entry.value === "object"` check fails.
2. **Transcript → Sample Init → Metadata sub-tab** (the repro's stated target,
   which uses `MetaDataGrid` → `RenderedContent` with the real object) is
   unreachable: the transcript renders no `Sample Init` panel for this
   span-based log — only `SOLVER: GENERATE` and `MODEL CALL` panels appear.

The **source defect is real** — `RenderedContent.tsx:73` does
`isValidElement(rendered)` which is `false` for the `ReactNode[]` returned at
`:281`, falling through to `JSON.stringify`. But the repro `.eval` cannot
demonstrate it. This matches the finding's own open question: *"confirm whether
any current eval log actually emits `name === 'web_search'` entries through
`RenderedContent` — if not, the renderer is doubly dead."*

**Repro fix needed:** route the record through a `MetaDataGrid` consumer that the
transcript actually renders — e.g. `LoggerEventView` (a `transcript._log()` /
`logger.info({"web_search": {...}})` event) or score metadata. Regenerating the
`.eval` is required; not attempted here.

---

## Files

- Checks: `findings/repros/verify/checks/F30_1.py`, `F30_2.py`, `F30_4.py`,
  `F31_1.py`, `F31_2.py`, `F31_3.py`, `F31_6.py`, `F40_1.py`, `F40_5.py`
- Artifacts: `findings/repros/verify/artifacts/F30.2-*.png`, `F30.4-*.png`,
  `F40.1-metadata.png`
