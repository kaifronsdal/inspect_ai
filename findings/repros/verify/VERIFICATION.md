# Browser Verification Results (Per-Finding Rigorous Pass)

Each of 59 `.eval` repros was opened in `inspect view` via Playwright (headless chromium), navigated to the bug location, screenshotted, and the screenshot + DOM independently inspected by a dedicated agent who re-read the cited source against the rendered page. This supersedes the earlier batch-verification pass and the two re-audits.

Per-finding reports with full evidence + analysis: [`per-finding/`](per-finding/) · Screenshots: [`artifacts/per-finding/`](artifacts/per-finding/)

## Summary

| Verdict | Count | Meaning |
|---|---|---|
| **CONFIRMED** | **39** | Bug visibly reproduces; finding accurate as written |
| **CONFIRMED_MINOR** | **13** | Reproduces, but impact is trivial / debug-only / legacy-only — recommend severity downgrade |
| **QUESTIONABLE_DESIGN** | **1** | F10.6 — documented intentional, but per user feedback the silent-stripping behaviour is still undesirable |
| ~~FALSE_POSITIVE~~ | ~~4~~ → 0 | Repros deleted — see [Deleted](#deleted) |
| ~~REPRO_BROKEN (scout-only)~~ | ~~2~~ → 0 | Repros deleted — see [Deleted](#deleted) |
| NOT_REPRODUCIBLE_VIA_EVAL | 5 | (from [`NOT_REPRODUCIBLE.md`](../NOT_REPRODUCIBLE.md) — backend/state bugs) |

**Total findings with .eval repros remaining:** **53** (39 + 13 + 1)

**History:** 59 originally verified → 6 deleted as non-issues. Net change vs previous batch pass (52/3/3/1): +1 FALSE_POSITIVE (F03.3 promoted from NOT_REPRODUCED), F10.6 reclassified CONFIRMED→BY_DESIGN→QUESTIONABLE_DESIGN, F40.5 resolved INCONCLUSIVE→CONFIRMED_MINOR, 13 CONFIRMED split out as CONFIRMED_MINOR with downgrade rationale.

## Deleted

6 repros (task `.py` + `.eval` + check script) were removed after this pass found them to be non-issues in `apps/inspect`. See [`../REMOVED.md`](../REMOVED.md). The per-finding reports below are retained as evidence of *why* each was rejected.

| ID | Verdict | Reason |
|---|---|---|
| F03.2 | FALSE_POSITIVE | checkbox toggles correctly (stale-closure makes double-fire idempotent) |
| F03.3 | FALSE_POSITIVE | breadcrumb `if (layout)` guard drops phantom prefixes; renders correctly |
| F20.6 | FALSE_POSITIVE | limit value IS shown in `SampleLimitEvent` message ("limit: 12,345") |
| F31.6 | FALSE_POSITIVE | `config.epochs` always ≥1 via `eval_config_defaults()`; `\|\|0` unreachable |
| F10.2 | scout-only | `collapseToolMessages:false` path; inspect renders error correctly |
| F11.8 | scout-only | same gate; `ContentData` renders correctly in inspect |

## Description accuracy pass

All 59 repros' `bug_description` text was audited sentence-by-sentence against live DOM/screenshots; ~200 inaccuracies fixed (wrong tab names, nonexistent "expand" steps, incorrect panel labels). See [`accuracy/<ID>.md`](accuracy/) for the per-finding fix log.

## Why some repros "look normal" on manual inspection

The default transcript event filter (`kDefaultExcludeEvents` in `apps/inspect/src/state/sampleSlice.ts:18`) hides `sample_init`, `sandbox`, `state`, `store`, and `branch` events. Opening one of those repros shows either nothing or *"The currently applied filter hides all events."* until you switch the **Events: Default** filter to **Debug** (which excludes nothing).

Affected repros: **F02.1, F05.1, F05.4, F05.9, F05.11, F05.12, F40.5**.

The Playwright harness handles this automatically via `checks/_util.py::show_all_events()` (the PopOver wrapper is a 0×0 absolutely-positioned div, so the helper mounts the popover then fires the `Debug` link's `onClick` via `page.evaluate`).

## Findings to remove or downgrade

> **Note:** the FALSE_POSITIVE, BY_DESIGN, and REPRO_BROKEN entries below have since been **acted on** — repros deleted ([`../REMOVED.md`](../REMOVED.md)); F10.6 retained as QUESTIONABLE_DESIGN per user feedback. The analysis is preserved for the record.

### FALSE_POSITIVE — remove from findings

| ID | Why |
|---|---|
| **F03.2** | Both handlers fire, but `toggleMarkerKind` reads `storedKinds` from the render closure non-functionally → two synchronous calls compute the *identical* `next` → single toggle. No flicker, no revert. Code smell only. |
| **F03.3** | `buildBreadcrumbs` does probe phantom `/`-split prefixes, but the `if (layout)` guard at `:63` drops misses, and real ancestors are *always* hit (child key = `${parentKey}/${name}`). No gaps possible. The "breadcrumbs show gaps" impact cannot occur as described. |
| **F20.6** | Transcript `SampleLimitEventView` renders `event.message` which includes `limit: 12,345`. The "nowhere outside JSON" claim fails only because the repro Ctrl-F'd `12345` (no comma). |
| **F31.6** | `eval_config_defaults()` ensures `config.epochs >= 1` in every real log; the repro's own JSON shows `"epochs": 1`. `(epochs || 0)` is unreachable. Code smell only (`|| 0` should be `|| 1`). |

### BY_DESIGN — remove from findings

| ID | Why |
|---|---|
| **F10.6** | `<think>`/`<internal>` stripping is documented in `design/migration/chat-migration.md:48`, asserted by e2e test `chat-components.spec.ts:623-654`, and added intentionally in PR #2324. These are bridge-serialisation envelopes (base64 JSON / `reasoning_to_think_tag()` output), not user content. Normal flows lift them into `ContentReasoning` before logging. Reclassify as low-priority enhancement at most. |

### REPRO_BROKEN (scout-only) — re-scope to `apps/scout`

| ID | Why |
|---|---|
| **F10.2** | `ChatMessage.tsx:116-129` (drops `error` + non-text content) is reached only when `collapseToolMessages: false`. Only `apps/scout/.../refs.tsx` sets that; `apps/inspect` defaults it `true` and exposes no toggle. Source bug is real → re-scope to scout, downgrade HIGH→MEDIUM. |
| **F11.8** | Same gate as F10.2. The repro renders via `ToolCallView` (collapsed path), which correctly shows `ContentData`. Source filter at `:121-124` is real → re-scope to scout, downgrade MEDIUM→LOW. |

### Severity downgrades recommended

| ID | From → To | Why |
|---|---|---|
| F02.2 / F02.3 | MEDIUM → LOW | `injectScorersSpan` active path only fires for logs from a ~3-week window (2025-05-02 → 2025-05-23); modern logs short-circuit at `treeify.ts:240`. Failure mode is "cosmetic enhancement no-op", not wrong display. |
| F02.5 | MEDIUM → LOW | `unwrap_handoff` does not fire on real `handoff()` output (`ToolEvent.span_id` captured before tool span opens). Repro had to synthesise the shape. The "+2 jump" sub-claim is not visible. |
| F03.4 | MEDIUM → LOW | Chevron click does select+highlight, but `onNavigateToEvent` is `undefined` in `apps/inspect` → no scroll-jump. Full impact is `apps/scout`-only. |
| F04.2 | HIGH → MEDIUM | One-tool case hides only the Tools sub-tab; tool definition still visible in All tab. (Agrees with `91-high-severity-verification.md`.) |
| F05.4 | MEDIUM → LOW | The "`use_tools()` never fires" impact claim is wrong for the common 1-tool case; preview is also useless until F05.1 is fixed. |
| F05.11 | LOW → INFO | `sample.id` is already shown twice on the same screen (header + summary row). Only `sample.sandbox` is genuinely missing, from a Debug-only panel, for a rarely-used per-sample override. |
| F05.12 | LOW → INFO | `BaseEvent.metadata` is ignored by *every* event view except Compaction; Branch follows the codebase norm. No public API populates it on a BranchEvent. Debug-only panel. |
| F10.1 | HIGH → MEDIUM | Trigger requires a malformed message list no well-formed agent loop produces. Silent UI data-loss but only on already-pathological input. |
| F11.3 | HIGH → LOW | `call_tools()` unconditionally list-wraps bare `Content*` (`_call_tools.py:219-236`), so the natural tool path cannot produce a bare object. When triggered synthetically, output is a RecordTree (image still visible), not raw JSON text. |
| F11.7 | MEDIUM → LOW | The Python-generated truncation preamble *is* shown; only the `(raw, kept)` byte counts from `event.truncated` are lost. "No indication it was truncated" is overstated. |
| F20.5 | LOW → INFO | The header row (pinned above the tabs, same screen) already shows a labelled Target column. No navigation needed to compare Answer↔Target. |
| F31.1 | HIGH → MEDIUM | (Agrees with `91-high-severity-verification.md`.) Fields are reachable via JSON tab; dead-loop fix is trivial. |
| F40.5 | MEDIUM → LOW | The `web_search` renderer is orphaned legacy — real web-search results go through `ServerToolCall.tsx`. Triggering requires a metadata key literally named `web_search` shaped `{query, results}`. Near-zero real-world incidence. |
| F80.10 | MEDIUM → LOW | The headline `formatPrettyDecimal` "0.000" is ordinary 3-dp rounding, not the parsing bug. Only `formatDecimalNoTrailingZeroes` (`1.234e-7` → `"0.000000"`) is a genuine defect, in a regime uncommon for Inspect scores. |

## Full results table

| ID | Verdict | Severity (orig→rec) | Evidence | Report | Screenshot |
|---|---|---|---|---|---|
| F01.1 | CONFIRMED | HIGH | Summary tab = 2× ASSISTANT only; SYSTEM/USER sentinels absent (All tab shows all 5) | [F01.1](per-finding/F01.1.md) | [page](artifacts/per-finding/F01.1-page.png) |
| F01.2 | CONFIRMED | HIGH | Tool Choice cell renders `` `$my_forced_tool()` `` literally | [F01.2](per-finding/F01.2.md) | [page](artifacts/per-finding/F01.2-page.png) |
| F01.3 | CONFIRMED | HIGH | `VALUE → 'UNCHANGED'` · `EXPLANATION → 'UNCHANGED'` shown as real data | [F01.3](per-finding/F01.3.md) | [page](artifacts/per-finding/F01.3-page.png) |
| F02.1 | CONFIRMED | MEDIUM | 3× `SANDBOX:` panels as siblings — no group wrapper | [F02.1](per-finding/F02.1.md) | [page](artifacts/per-finding/F02.1-page.png) |
| F02.2 / F02.3 | CONFIRMED_MINOR | MEDIUM → **LOW** | Both scorers at depth 0, no `scorers` wrapper — but path is dead for all logs since 2025-05-23 | [F02.2](per-finding/F02.2.md) | [page](artifacts/per-finding/F02.2-page.png) |
| F02.4 | CONFIRMED | MEDIUM | Outline `data-depth` 1→3; transcript Δx = 32px vs 16px reference | [F02.4](per-finding/F02.4.md) | [page](artifacts/per-finding/F02.4-page.png) |
| F02.5 | CONFIRMED | MEDIUM → **LOW** | Agent span flush with parent tool — but `unwrap_handoff` doesn't fire on real handoff() output | [F02.5](per-finding/F02.5.md) | [page](artifacts/per-finding/F02.5-page.png) |
| F03.2 | **FALSE_POSITIVE** | ~~MEDIUM~~ | `Compaction` checkbox: True→click→False (single toggle, no flicker) | [F03.2](per-finding/F03.2.md) | [page](artifacts/per-finding/F03.2-page.png) |
| F03.3 | **FALSE_POSITIVE** | ~~MEDIUM~~ | Breadcrumb = correct ancestor chain; `if (layout)` guard drops phantom prefixes; gaps impossible | [F03.3](per-finding/F03.3.md) | [page](artifacts/per-finding/F03.3-page.png) |
| F03.4 | CONFIRMED_MINOR | MEDIUM → **LOW** | Chevron click selects row but `scrollTop` unchanged; scroll-jump is scout-only | [F03.4](per-finding/F03.4.md) | [page](artifacts/per-finding/F03.4-page.png) |
| F03.5 | CONFIRMED | MEDIUM | Collapse parent → click outline child: URL updates, `scrollTop 0→0`, target stays hidden | [F03.5](per-finding/F03.5.md) | [page](artifacts/per-finding/F03.5-page.png) |
| F04.2 | CONFIRMED | HIGH → **MEDIUM** | 1 tool: tabs `[SUMMARY, ALL, API]`; 2 tools: `[…, TOOLS]` appears | [F04.2](per-finding/F04.2.md) | [page](artifacts/per-finding/F04.2-page.png) |
| F04.5 | CONFIRMED | MEDIUM | No `RETRIES`/`CACHE` label anywhere; `event.retries=3`/`cache="read"` invisible | [F04.5](per-finding/F04.5.md) | [page](artifacts/per-finding/F04.5-page.png) |
| F04.7 | CONFIRMED | MEDIUM | `'content filtered'` sentinel + `STOP REASON` absent on Summary/All/API | [F04.7](per-finding/F04.7.md) | [page](artifacts/per-finding/F04.7-page.png) |
| F04.8 | CONFIRMED | MEDIUM | Usage grid: `INPUT='' \| CACHE_READ='100' \| OUTPUT='50'` (zero → blank) | [F04.8](per-finding/F04.8.md) | [page](artifacts/per-finding/F04.8-page.png) |
| F05.1 | CONFIRMED | HIGH | `LOOK_HERE` jsondiffpatch ancestors: `[]` — no `metadata` path | [F05.1](per-finding/F05.1.md) | [page](artifacts/per-finding/F05.1-page.png) |
| F05.4 | CONFIRMED_MINOR | MEDIUM → **LOW** | 1-tool: `[SUMMARY,DIFF]`; 3-tool: raw diff only — but common `use_tools()` case works | [F05.4](per-finding/F05.4.md) | [page](artifacts/per-finding/F05.4-page.png) |
| F05.5 | CONFIRMED | MEDIUM | All 3 Edit Score panels: `VALUE` row absent for `0`/`False`/`""` | [F05.5](per-finding/F05.5.md) | [page](artifacts/per-finding/F05.5-page.png) |
| F05.6 | CONFIRMED_MINOR | LOW | Metadata `data-name` nested inside Summary → no tab; trivial structural fix | [F05.6](per-finding/F05.6.md) | [page](artifacts/per-finding/F05.6-page.png) |
| F05.9 | CONFIRMED_MINOR | LOW | `COMMAND` heading + empty `<pre>`; `=== null` misses `undefined` (defensive-code hygiene) | [F05.9](per-finding/F05.9.md) | [page](artifacts/per-finding/F05.9-page.png) |
| F05.11 | CONFIRMED_MINOR | LOW → **INFO** | No SANDBOX/ID section — but `id` already on screen ×2; sandbox rarely per-sample; Debug-only | [F05.11](per-finding/F05.11.md) | [page](artifacts/per-finding/F05.11-page.png) |
| F05.12 | CONFIRMED_MINOR | LOW → **INFO** | `event.metadata` discarded — but no event view except Compaction renders it; Debug-only | [F05.12](per-finding/F05.12.md) | [page](artifacts/per-finding/F05.12-page.png) |
| F10.1 | CONFIRMED | HIGH → **MEDIUM** | Rows `1/USER, 2/USER, 3/USER`; orphan tool absent — but requires malformed message list | [F10.1](per-finding/F10.1.md) | [page](artifacts/per-finding/F10.1-page.png) |
| F10.2 | **REPRO_BROKEN** | HIGH → **MEDIUM** (scout) | Error IS shown (collapsed path); `collapseToolMessages:false` is scout-only | [F10.2](per-finding/F10.2.md) | [page](artifacts/per-finding/F10.2-page.png) |
| F10.4 | CONFIRMED | MEDIUM | Inline `<sup>` = `[1,2,1,2]` vs footnote list `[1,2,3,4]` | [F10.4](per-finding/F10.4.md) | [page](artifacts/per-finding/F10.4-page.png) |
| F10.6 | **BY_DESIGN** | ~~MEDIUM~~ | `<think>` body stripped, no marker — documented in design doc + e2e test; bridge envelope | [F10.6](per-finding/F10.6.md) | [page](artifacts/per-finding/F10.6-page.png) |
| F10.7 | CONFIRMED | MEDIUM | 5 rows (expected 7); 1 SYSTEM header w/ all 3 bodies; ids/metadata lost | [F10.7](per-finding/F10.7.md) | [page](artifacts/per-finding/F10.7-page.png) |
| F11.1 | CONFIRMED | HIGH | `bad_tool` panel has zero CSS classes `good_tool` lacks; visually identical | [F11.1](per-finding/F11.1.md) | [page](artifacts/per-finding/F11.1-page.png) |
| F11.2 | CONFIRMED | MEDIUM | Gap fn-name↔error.message = `'\n'` only; no `permission:` prefix; `error.type` dropped | [F11.2](per-finding/F11.2.md) | [page](artifacts/per-finding/F11.2-page.png) |
| F11.3 | CONFIRMED_MINOR | HIGH → **LOW** | Bare: RecordTree `type:/image:/detail:`; List: `<img>` — but `call_tools()` always list-wraps | [F11.3](per-finding/F11.3.md) | [page](artifacts/per-finding/F11.3-page.png) |
| F11.4 | CONFIRMED | MEDIUM | `<h1>This line should be PLAIN TEXT…</h1>` rendered; `format='text'` ignored | [F11.4](per-finding/F11.4.md) | [page](artifacts/per-finding/F11.4-page.png) |
| F11.7 | CONFIRMED_MINOR | MEDIUM → **LOW** | No viewer byte-count footer — but Python truncation preamble IS shown | [F11.7](per-finding/F11.7.md) | [page](artifacts/per-finding/F11.7-page.png) |
| F11.8 | **REPRO_BROKEN** | MEDIUM → **LOW** (scout) | `ContentData` IS rendered (collapsed path → ToolCallView); filter is scout-only | [F11.8](per-finding/F11.8.md) | [page](artifacts/per-finding/F11.8-page.png) |
| F11.11 | CONFIRMED | MEDIUM | Approval chrome: `'MODIFIED'` only; `approver`/`modified`/`message` never read | [F11.11](per-finding/F11.11.md) | [page](artifacts/per-finding/F11.11-page.png) |
| F20.1 | CONFIRMED | MEDIUM | Header labels: `[ID, INPUT, TARGET]` only; `isEvalSample()` always false | [F20.1](per-finding/F20.1.md) | [page](artifacts/per-finding/F20.1-page.png) |
| F20.4 | CONFIRMED | MEDIUM | List/header: plain `C`; Scoring tab: green circle badge (descriptor diverges) | [F20.4](per-finding/F20.4.md) | [page](artifacts/per-finding/F20.4-page.png) |
| F20.5 | CONFIRMED_MINOR | LOW → **INFO** | Scoring tab has no Target row — but pinned header above already shows it | [F20.5](per-finding/F20.5.md) | [page](artifacts/per-finding/F20.5-page.png) |
| F20.6 | **FALSE_POSITIVE** | ~~LOW~~ | Transcript shows `limit: 12,345`; "nowhere outside JSON" claim is wrong | [F20.6](per-finding/F20.6.md) | [page](artifacts/per-finding/F20.6-page.png) |
| F20.14 | CONFIRMED | LOW | `list_scorer` cell: `'[0, 0.333, 1.0]'` — `0` un-formatted | [F20.14](per-finding/F20.14.md) | [page](artifacts/per-finding/F20.14-page.png) |
| F21.1 | CONFIRMED | MEDIUM | Sort-asc: `C, I, N, P` (alphabetical); descriptor `compare()` never called | [F21.1](per-finding/F21.1.md) | [page](artifacts/per-finding/F21.1-page.png) |
| F21.2 | CONFIRMED | MEDIUM | Autocomplete: `['undefined', 'category_scorer', …]` | [F21.2](per-finding/F21.2.md) | [page](artifacts/per-finding/F21.2-page.png) |
| F21.10 | CONFIRMED | MEDIUM | Grid: `'C'`/`2.000`/`{"a":1}`; List: circle badge — three format divergences | [F21.10](per-finding/F21.10.md) | [page](artifacts/per-finding/F21.10-page.png) |
| F30.1 | CONFIRMED | HIGH | One `accuracy` column; row shows `1.0` AND `0.0` (last scorer overwrites) | [F30.1](per-finding/F30.1.md) | [page](artifacts/per-finding/F30.1-page.png) |
| F30.2 | CONFIRMED | MEDIUM | List: `bi-exclamation-circle-fill`; Header: `bi-x-circle` for same status | [F30.2](per-finding/F30.2.md) | [page](artifacts/per-finding/F30.2-page.png) |
| F30.4 | CONFIRMED | MEDIUM | Error-log navbar has no DATASET/SCORER/DURATION (success log does) | [F30.4](per-finding/F30.4.md) | [page](artifacts/per-finding/F30.4-page.png) |
| F31.1 | CONFIRMED | HIGH → **MEDIUM** | Task tab: `message_limit`/`token_limit`/`999999` absent; dead config loop | [F31.1](per-finding/F31.1.md) | [page](artifacts/per-finding/F31.1-page.png) |
| F31.2 | CONFIRMED | MEDIUM | Solvers column: bare `parameterised_solver`; `<DetailStep>` called without `params=` | [F31.2](per-finding/F31.2.md) | [page](artifacts/per-finding/F31.2-page.png) |
| F31.3 | CONFIRMED | LOW | `plan.name` sentinel absent on Info+Task tabs (`plan.finish` half is FALSE_POSITIVE) | [F31.3](per-finding/F31.3.md) | [page](artifacts/per-finding/F31.3-page.png) |
| F31.6 | **FALSE_POSITIVE** | ~~MEDIUM~~ | Footer: `'3 Samples'`; JSON shows `epochs: 1`; `\|\| 0` unreachable | [F31.6](per-finding/F31.6.md) | [page](artifacts/per-finding/F31.6-page.png) |
| F40.1 | CONFIRMED | HIGH | `L7_leaf` and `child_11` visible without clicks; `if (collapsedIds) return` | [F40.1](per-finding/F40.1.md) | [page](artifacts/per-finding/F40.1-page.png) |
| F40.5 | CONFIRMED_MINOR | MEDIUM → **LOW** | `web_search` row → raw JSON span (array fails `isValidElement`) — but renderer is orphaned legacy | [F40.5](per-finding/F40.5.md) | [page](artifacts/per-finding/F40.5-page.png) |
| F80.10 | CONFIRMED_MINOR | MEDIUM → **LOW** | List `0.000` / pill `0.000000` — but `0.000` is plain 3-dp rounding; only `noTrailingZeroes` is a real defect | [F80.10](per-finding/F80.10.md) | [page](artifacts/per-finding/F80.10-page.png) |
| F90.1 | CONFIRMED | MEDIUM | `04/23/26, 4:57:46 AM` vs `2026-04-23 04:57:46` on same screen | [F90.1](per-finding/F90.1.md) | [page](artifacts/per-finding/F90.1-page.png) |
| F90.2 | CONFIRMED_MINOR | LOW | `2.8 sec`/`3 sec`/`3.0 sec` — but each is a *different* underlying field; no field rendered two ways | [F90.2](per-finding/F90.2.md) | [page](artifacts/per-finding/F90.2-page.png) |
| F90.3 | CONFIRMED | MEDIUM | Header: green-circle badge; Transcript: bare `<div>true` for same score | [F90.3](per-finding/F90.3.md) | [page](artifacts/per-finding/F90.3-page.png) |
| F90.4 | CONFIRMED | MEDIUM | Row `F90.4-errored`: status=`success`, error populated | [F90.4](per-finding/F90.4.md) | [page](artifacts/per-finding/F90.4-page.png) |
| F90.5 | CONFIRMED | MEDIUM | Card body children: only `[ANSIDisplay]`; `error.message` only inside traceback | [F90.5](per-finding/F90.5.md) | [page](artifacts/per-finding/F90.5-page.png) |
| F90.7 | CONFIRMED | LOW | Title bar: hidden; log-list/ModelCard: `none/none` leaks | [F90.7](per-finding/F90.7.md) | [page](artifacts/per-finding/F90.7-page.png) |
| F90.14 | CONFIRMED | LOW | `1.0` / `1` / `1.000` for same value across three surfaces | [F90.14](per-finding/F90.14.md) | [page](artifacts/per-finding/F90.14-page.png) |

## Repro fixes made during verification

| ID | File | Change |
|---|---|---|
| F01.2 | `tasks/01-events/F01.2_tool_choice_literal_dollar.py` | Rewrote to push synthetic `ModelEvent` via `transcript()._event()` with 2× `ToolInfo` (original hit F04.2 and hid the Tools tab). `.eval` regenerated. |
| F02.4 | `tasks/02-transform/F02.4_unwrap_main_grandchild_depth.py` | Added a REFERENCE subtree alongside the BUG subtree so the depth jump is visible by direct comparison; rewrote `observed`/`expected` text. `.eval` regenerated. |
| F03.4 / F03.5 | `tasks/02-transform/F03.{4,5}_*.py` | Rewritten with plain `span(name)` (no `type=`); F03.5 adds 20 InfoEvent padding. `.eval` regenerated; checks rewritten. F03.4 check now also asserts `scrollTop`/URL unchanged. |
| F05.4 | `tasks/01-events/F05.4_state_tools_preview_count.py` | Rebuilt to emit two synthetic `StateEvent`s (1-tool CONTROL + 3-tool BUG) for side-by-side comparison. `.eval` regenerated. |
| F10.4 | `tasks/10-chat/F10.4_citation_numbering_mismatch.py` | `cited_text="…"` → `cited_text=(start, end)` tuples (positional cites). `.eval` regenerated. |
| F31.3 | `tasks/30-loglist/F31.3_plan_name_finish_hidden.py` | Refocused on `plan.name` only; `extra` text documents why `plan.finish` half is FALSE_POSITIVE. `.eval` regenerated. |
| F40.5 | `checks/F40_5.py` | Check script fixed to call `show_all_events()` + expand `Init` span + click `Metadata` sub-tab (was navigation failure, not unreachability). |

## Running verification yourself

```bash
cd findings/repros/verify
uv run --with playwright python verify_one.py F01.1
# or all:
for f in checks/F*.py; do id=$(basename "$f" .py | tr _ .); uv run --with playwright python verify_one.py "$id"; done
```

Per-finding rigorous reports: [`per-finding/`](per-finding/). Earlier batch-pass evidence dumps (superseded but retained): [`results/`](results/). Re-audit history: [`REAUDIT.md`](REAUDIT.md).
