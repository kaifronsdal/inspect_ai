# Inspect Viewer Code Review — Executive Summary

**Review date:** 2026-04-22 · **Agents:** 19 review + 1 verification + 1 inventory · **Files reviewed:** ~580 TS/TSX/CSS + 10 Python

---

## 1. Overview

A multi-agent review covered the full Inspect viewer stack: Python backend (`src/inspect_ai/_view/*.py`), the React monorepo (`ts-mono/apps/inspect`, `packages/{inspect-components,react,inspect-common,util,theme,scout-components}`), and cross-cutting consistency between them.

**539 raw finding IDs** were logged across 22 area files. After de-duplication (`92-duplicate-index.md`) there are **~493 unique findings**:


| Severity   | Raw | Unique (post-dedup)                    |
| ---------- | --- | -------------------------------------- |
| **HIGH**   | 20  | **14** (after verification downgrades) |
| **MEDIUM** | 122 | ~113                                   |
| **LOW**    | 268 | ~246                                   |
| **INFO**   | 129 | ~120                                   |


All 19 HIGH findings reachable at verification time were independently re-read (`91-high-severity-verification.md`): **17 CONFIRMED, 2 PARTIAL** (bug real, severity overstated → MEDIUM), **0 REFUTED**. Five randomly-sampled MEDIUM findings were also spot-checked: 5/5 confirmed.

---

## Browser verification

**53** findings have minimal `.eval` repros under [`repros/`](repros/README.md). Each was opened in `inspect view` via Playwright, screenshotted, and independently re-verified by a dedicated agent against the cited source — see [`repros/verify/VERIFICATION.md`](repros/verify/VERIFICATION.md) and per-finding evidence at [`repros/verify/per-finding/`](repros/verify/per-finding/).

A further **15** findings now have **non-`.eval` repros** (pytest / tsx / node / Playwright / post-processed `.eval`) covering the Python HTTP backend, pure-function TS bugs, and cross-navigation Zustand state — see [`repros/README.md` § Non-.eval repros](repros/README.md#non-eval-repros). Nine perf / race-condition findings with no executable artifact are documented in [`repros/DOCUMENTED_ONLY.md`](repros/DOCUMENTED_ONLY.md).

| Verdict | Count |
|---|---|
| CONFIRMED (`.eval`) | 39 |
| CONFIRMED_MINOR (`.eval`; recommend severity downgrade) | 13 |
| QUESTIONABLE_DESIGN (F10.6 — documented but undesirable) | 1 |
| CONFIRMED (non-`.eval` — pytest/tsx/node/playwright) | 12 + 1 partial (F50.3) |
| CONFIRMED scout-only (vitest) | 2 (F10.2, F11.8) |
| Documented-only (perf/race) | 9 |
| NOT_REPRODUCIBLE_VIA_EVAL | 0 |
| **Removed / FALSE_POSITIVE** | **6 + 1** |

**Removed** — repros deleted, findings should be dropped from this set (see [`repros/REMOVED.md`](repros/REMOVED.md)):
- **F03.2** (timeline checkbox double-toggle) — FALSE_POSITIVE: both handlers fire, but `setStoredKinds` reads a stale render closure so two synchronous calls compute the *same* next state → single toggle, no flicker. Code smell only.
- **F03.3** (swimlane `/`-in-span-name breadcrumb) — FALSE_POSITIVE: phantom prefixes are dropped by the `if (layout)` guard; real ancestors are always hit. The "breadcrumbs show gaps" impact cannot occur as described.
- **F20.6** (limit value never displayed) — FALSE_POSITIVE: the transcript `SampleLimitEvent` panel renders `event.message` which includes `limit: 12,345`; the "nowhere outside JSON" claim is wrong.
- **F31.6** (sample count → 0 when `epochs` unset) — FALSE_POSITIVE: `eval_config_defaults()` ensures `config.epochs` is never null in any real log, so `(epochs || 0)` always evaluates ≥1. Code smell only.
- **F50.9** (IndexedDB cache key mismatch) — FALSE_POSITIVE: source asymmetry (read via `logAbsPath`, write via `logFileName`) is real, but the only caller `App.tsx loadLog(selectedLogFile)` always receives a path already resolved to a `file://` URI by `setSelectedLogFile`, so read key == write key. Latent code-smell → downgrade to INFO.
- **F10.2** / **F11.8** — scout-only: both gated on `collapseToolMessages: false`, which only `apps/scout` sets. Inspect renders the data correctly. Source bugs at `ChatMessage.tsx:116-129` are real → re-scope to scout and downgrade (HIGH→MEDIUM, MEDIUM→LOW respectively). A vitest unit-test repro is provided at [`repros/tasks/10-chat/F10.2_F11.8_scout_only.md`](repros/tasks/10-chat/F10.2_F11.8_scout_only.md).

**Refinements from non-`.eval` verification:**
- **F31.13** (Task tab `START 1970-01-01`) — moved from NOT_REPRODUCIBLE → **CONFIRMED**: a post-processed `.eval` with `stats.started_at = ""` reproduces it; navbar additionally shows `DURATION = NaN days NaN hr …`.
- **F50.3** (collapse/property-bag state leaks across samples) — **CONFIRMED partial**: unbounded `app.propertyBags` growth across sample navigation is real and persisted; the "positional-key collision causes visible UI leak" sub-claim is **wrong** (transcript node ids are `event.uuid`, not positional). Reword finding accordingly.

**F10.6** (`<think>`/`<internal>` stripped silently) — reclassified from BY_DESIGN to **QUESTIONABLE_DESIGN** per user feedback: the stripping is documented in `design/migration/chat-migration.md` and asserted by e2e test (PR #2324), but silently discarding text from the rendered view without any marker is still undesirable. Repro retained.

**Severity downgrades recommended** (full rationale in [`VERIFICATION.md`](repros/verify/VERIFICATION.md#severity-downgrades-recommended)):

| ID | From → To | Reason |
|---|---|---|
| F02.2/F02.3 | MEDIUM → LOW | Path dead for all logs since 2025-05-23; cosmetic enhancement no-op |
| F02.5 | MEDIUM → LOW | `unwrap_handoff` doesn't fire on real `handoff()` output |
| F03.4 | MEDIUM → LOW | Scroll-jump is `apps/scout`-only; inspect just highlights |
| F04.2 | HIGH → MEDIUM | Tool def still visible in All tab |
| F05.4 | MEDIUM → LOW | Common 1-tool `use_tools()` case works |
| F05.11 | LOW → INFO | `id` already on screen ×2; sandbox is Debug-only + rarely per-sample |
| F05.12 | LOW → INFO | No event view except Compaction renders `BaseEvent.metadata` |
| F10.1 | HIGH → MEDIUM | Requires malformed message list no agent loop produces |
| F11.3 | HIGH → LOW | `call_tools()` always list-wraps; unreachable from real tools |
| F11.7 | MEDIUM → LOW | Python truncation preamble IS shown; only byte counts lost |
| F20.5 | LOW → INFO | Pinned header already shows Target on same screen |
| F31.1 | HIGH → MEDIUM | Reachable via JSON tab; trivial fix |
| F40.5 | MEDIUM → LOW | `web_search` renderer is orphaned legacy; near-zero incidence |
| F80.10 | MEDIUM → LOW | Headline `0.000` is plain rounding; only `noTrailingZeroes` is a real defect |

---

## 2. Top Issues

### Correctness bugs (wrong data shown / crashes)


| ID        | Title                                              | Location                                  | Impact                                                                               |
| --------- | -------------------------------------------------- | ----------------------------------------- | ------------------------------------------------------------------------------------ |
| **F03.1** | `setPath` only descends when key is missing        | `transcript/state/StateEventView.tsx:292` | State/Store event diffs are structurally wrong for any multi-segment JSON-patch path |
| **F01.1** | `slice(-1)` drops preceding messages               | `transcript/ModelEventView.tsx:67`        | Summary tab loses user prompt after compaction                                       |
| **F01.3** | `"UNCHANGED"` sentinel rendered as score value     | `transcript/ScoreEditEventView.tsx:50`    | Score-edit panel shows literal "UNCHANGED" as if it were the new score               |
| **F50.1** | `isLargeSample()` always returns `true`            | `state/store_filter.ts:31`                | Every sample stored in non-reactive ref; rehydration always forces reload            |
| **F11.3** | Single content-object tool result JSON-stringified | `chat/tools/ToolCallView.tsx:273`         | Tool returning bare `ContentImage` renders as raw JSON blob, not `<img>`             |
| **F40.1** | RecordTree default-collapse never executes         | `content/RecordTree.tsx:87`               | All metadata/store trees mount fully expanded; `defaultExpandLevel` is a no-op       |
| **F30.1** | Metric columns collide across scorers              | `log-list/grid/LogListGrid.tsx:204`       | Multi-scorer evals: last scorer silently overwrites "accuracy" column                |
| **F51.1** | `pending_log_promise` returns wrong log under race | `client/api/client-api.ts:98`             | Concurrent JSON-log requests can show log A's transcript for log B                   |
| **F70.2** | `stream_log_bytes` raises for >50 MB non-S3 files  | `_view/common.py:251`                     | "Download log" 500s for large local/Azure `.eval` files                              |


### Data not shown (silent drops)


| ID        | Title                                                      | Location                             | Impact                                                                    |
| --------- | ---------------------------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------- |
| **F10.1** | Orphan tool messages silently dropped                      | `chat/messages.ts:46`                | Tool result with no preceding assistant turn vanishes from transcript     |
| **F10.2** | Standalone tool messages hide `error`                      | `chat/ChatMessage.tsx:116`           | Toggling `collapseToolMessages` off hides the very error you're debugging |
| **F11.1** | Tool errors styled identically to success                  | `transcript/ToolEventView.tsx:110`   | Failed tool calls indistinguishable from successful ones in transcript    |
| **F90.4** | `SamplesGrid` "Status" shows log status, not sample status | `samples-panel/SamplesPanel.tsx:183` | Errored samples show "success" in multi-log grid                          |


### Security


| ID        | Title                                         | Location                               | Impact                                                               |
| --------- | --------------------------------------------- | -------------------------------------- | -------------------------------------------------------------------- |
| **F70.1** | Lazy `map()` skips path validation (aiohttp)  | `_view/server.py:295`                  | `/api/log-headers` reads arbitrary paths when no auth token set      |
| **F70.3** | `startswith` path-prefix bypass               | `_view/fastapi_server.py:501`          | `/home/u/logs-private/*` passes when log dir is `/home/u/logs`       |
| **F70.4** | Destructive delete exposed via HTTP GET       | `_view/fastapi_server.py:149`          | `<img src=".../log-delete/...">` on a malicious page deletes logs    |
| **F31.5** | Breadcrumb width measurement uses `innerHTML` | `navbar/useBreadcrumbTruncation.ts:49` | Directory name containing `<img onerror=...>` injected into live DOM |


### Consistency (same data, different rendering)


| ID        | Title                                                             | Impact                                                                     |
| --------- | ----------------------------------------------------------------- | -------------------------------------------------------------------------- |
| **F90.1** | Two timestamp formats on the same screen                          | Event subtitles use 12-hour locale; sample header uses `sv-SE` 24-hour     |
| **F90.3** | Four independent score-value renderers                            | Boolean score is a green badge in header, plain `true` in transcript event |
| **F30.2** | `bi-x-circle` means "cancelled" in list, "error" in detail header | Icon vocabulary contradicts itself one click deep                          |


---

## 3. Thematic Patterns


| Pattern                                                                                                                               | Count                  | Example IDs                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- | -------------------------------------------------------------------------------------------------------------- |
| **Undefined `styles.X` references** — TSX reads a CSS-module class that doesn't exist; `clsx` silently drops it                       | ~30                    | F10.15, F11.12, F60.8, F81.13–18                                                                               |
| **Dead CSS rules / orphaned `.module.css` files**                                                                                     | ~80 selectors, 6 files | F61.18, F81.19–30, F20.18, F31.16                                                                              |
| **Duplicate util implementations with drift** — same-named function in `@tsmono/util` and `apps/inspect/utils/` with different output | 7 modules              | F80.4, F80.8, F80.9, F52.9, F30.18                                                                             |
| **Falsy `                                                                                                                             |                        | `/ truthy checks hiding`0`/`false`/`""`**                                                                      |
| **Schema fields never rendered** — Python emits, viewer ignores                                                                       | ~25 fields             | F04.4 (`total_cost`), F04.5 (`retries`/`cache`), F11.7 (`truncated`), F01.7 (`modified`), F31.1 (`EvalConfig`) |
| **Hand-coded type unions drifted from generated schema**                                                                              | 3                      | F51.2, F52.8, F05.7                                                                                            |
| `**stopPropagation` on `change` doesn't stop bubbling `click`** → double-toggle                                                       | 3+                     | F03.2, F52.18, `SelectScorer` (21 open-q)                                                                      |
| **Forwarded `ref` assigned to two elements**                                                                                          | 2                      | F30.6, F52.1                                                                                                   |
| **Four parallel icon registries with copy-pasted defaults**                                                                           | —                      | F61.9, F61.10, F61.12                                                                                          |
| **Copy-pasted JSDoc / wrong docstrings**                                                                                              | ~10                    | F04.19, F11.22, F40.25, F31.15, F80.14                                                                         |
| **Missing React `key` on mapped fragments**                                                                                           | ~6                     | F11.13, F30.12, F40.22, F01.18                                                                                 |
| **a11y: `<a>`/`<div>` as button without `role`/`tabIndex`/keyboard**                                                                  | ~8                     | F31.26, F52.18, F60.15–18, F10.18                                                                              |


---

## 4. Per-Area Index


| File                                  | Area                                            | Count | H / M / L / I       |
| ------------------------------------- | ----------------------------------------------- | ----- | ------------------- |
| `01-transcript-event-renderers.md`    | Per-event renderers + EventPanel primitives     | 30    | 3 / 7 / 16 / 4      |
| `02-transcript-transform-pipeline.md` | treeify / flatten / fixups                      | 20    | 0 / 5 / 8 / 7       |
| `03-transcript-outline-timeline.md`   | Outline, timeline, swimlanes, state-diff        | 23    | 1 / 4 / 11 / 7      |
| `04-model-event-and-usage.md`         | ModelEventView + token-usage panels             | 19    | 2 / 6 / 8 / 3       |
| `05-minor-event-renderers.md`         | State/Store/Score/Approval/Sandbox/etc. views   | 15    | 1 / 3 / 8 / 3       |
| `10-chat-message-rendering.md`        | ChatMessage, MessageContent, citations          | 21    | 2 / 4 / 11 / 4      |
| `11-tool-call-rendering.md`           | ToolCallView, ToolOutput, ServerToolCall        | 25    | 2 / 7 / 12 / 4      |
| `20-sample-display-scores.md`         | SampleDisplay, SampleSummary, scores, print     | 27    | 0 / 3 / 16 / 8      |
| `21-sample-list-descriptors.md`       | Sample list/grid, score descriptors, filters    | 28    | 0 / 5 / 15 / 8      |
| `30-log-list-and-view.md`             | Log-list grid, title-view header                | 19    | 1 / 5 / 11 / 2      |
| `31-log-tabs-plan-navbar.md`          | Task/Info/JSON tabs, plan, navbar, breadcrumbs  | 28    | 1 / 4 / 14 / 9      |
| `40-content-renderers.md`             | RenderedContent, RecordTree, Markdown, ANSI     | 27    | 1 / 6 / 12 / 8      |
| `50-state-and-routing.md`             | Zustand store, slices, routing, URL parsing     | 22    | 2 / 6 / 8 / 6       |
| `51-data-loading-clients.md`          | API clients, IndexedDB, remote zip, replication | 28    | 1 / 8 / 13 / 6      |
| `52-app-shell-flow.md`                | main.tsx, App.tsx, error boundary, flow panel   | 22    | 0 / 6 / 10 / 6      |
| `60-base-react-components.md`         | `@tsmono/react` components + hooks              | 45    | 0 / 6 / 29 / 10     |
| `61-theme-icons-appearance.md`        | base.css, icon registries, dark mode            | 30    | 0 / 8 / 16 / 6      |
| `62-scout-components-overlap.md`      | scout-components ↔ inspect overlap              | 6     | 0 / 0 / 4 / 2       |
| `70-python-view-backend.md`           | server.py, fastapi_server.py, common.py         | 25    | 2 / 6 / 10 / 7      |
| `80-utilities-formatting.md`          | `@tsmono/util`, app utils, inspect-common utils | 23    | 1 / 9 / 9 / 4       |
| `81-dead-code-inventory.md`           | Mechanical dead-export / dead-CSS sweep         | 31    | 0 / 0 / 17 / 14     |
| `90-cross-cutting-consistency.md`     | Same-concept-different-rendering audit          | 15    | 0 / 4 / 10 / 1      |
| `91-high-severity-verification.md`    | Independent re-verification of all HIGHs        | —     | (verification only) |
| `92-duplicate-index.md`               | De-duplication table                            | —     | (index only)        |


---

## 5. Recommended Next Steps

1. **Security pass on Python backend** (1–2 hrs): F70.1 (one-line fix), F70.3, F70.4, F70.2. These are the only findings with potential for data exfiltration/destruction.
2. **Fix the 14 standing HIGH bugs** (~1 day): each is a localized 1–10 line fix with a clear suggested patch in its finding. Prioritize F03.1, F01.1, F01.3, F11.1, F30.1, F50.1 as user-visible-daily.
3. **Consolidate duplicated utilities** (~0.5 day): delete `apps/inspect/src/utils/{format,uri,html,json-worker,react}.ts` after upstreaming differences into `@tsmono/util`. Unblocks F90.1/F90.2 and removes ~400 LOC + 160 KB of duplicated JSON5 blob.
4. **Enable `typescript-plugin-css-modules`** or equivalent lint: would have caught all ~30 undefined `styles.X` refs and ~80 dead CSS rules at build time.
5. **Add exhaustiveness checks** on `event.event` switches and the hand-coded `Event` union (F02.12, F51.2) so new Python event types fail loudly instead of rendering blank.
6. **Dead-code purge** per `81-dead-code-inventory.md` (~1500 LOC across 12 dead files + ~80 dead CSS selectors). Low risk, high signal-to-noise improvement.
7. **Unify score rendering** through a single descriptor path (F20.4 / F21.10 / F90.3 / F90.14) and status icons through `ApplicationIcons` (F30.2 / F61.11 / F90.8).

---

## 6. Formatting Issues

All 22 numbered findings files (01–90) follow `TEMPLATE.md` structure: each has a Summary, Findings with Severity/Location/Category, and a Files-reviewed checklist. No malformed files were found.

Minor deviations (acceptable):

- `81-dead-code-inventory.md` leads with inventory tables (§1–§5) before the Findings section — by design for a mechanical sweep.
- `91-high-severity-verification.md` uses Verdict/Evidence/Reasoning instead of Severity/Category — by design for a verification report.
- `62-scout-components-overlap.md` is brief (6 findings) but structurally complete.

