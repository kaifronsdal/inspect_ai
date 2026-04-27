# 50-state — state-management bugs needing cross-navigation

These findings can't be demonstrated by opening a static `.eval` — they need
the viewer driven through a navigation sequence (sample A → interact →
sample B) and/or the live Zustand store / IndexedDB inspected. Each comes
with a **Playwright interaction script** that prints a self-contained
PASS/FAIL report.

## Prerequisites

```bash
cd ~/GitHub/inspect_ai
uv run --with playwright playwright install chromium   # one-time
```

The verify scripts spin up `inspect view` on **port 7872** — kill anything
already on that port first.

---

## F50.3 — collapse / property-bag state leaks across samples

| | |
|---|---|
| **Verdict** | **CONFIRMED (partial)** — unbounded growth confirmed; positional cross-sample leak **not reproduced** (see below) |
| **Task file** | `F50.3_collapse_leaks_across_samples.py` |
| **`.eval`** | `findings/repros/logs/50-state/*_F50.3-*.eval` (2 samples: `F50.3-A`, `F50.3-B`) |
| **Verify** | `F50.3_verify.py` |

### Generate the log

```bash
./findings/repros/run.sh \
    findings/repros/tasks/50-state/F50.3_collapse_leaks_across_samples.py \
    50-state
```

### Run the interaction repro

```bash
uv run --with playwright python \
    findings/repros/tasks/50-state/F50.3_verify.py
```

### What it does

1. Injects a fake `__REDUX_DEVTOOLS_EXTENSION__` so the Zustand
   `devtools()` middleware mirrors every store update into
   `window.__zustate` (browser-mode `inspect view` has no localStorage
   persistence, so we read the live store instead).
2. Opens sample **F50.3-A** → clicks the **All** sub-tab pill on the Model
   Call panel. This writes `app.propertyBags[<event-uuid-A>].selectedNav`.
3. Hash-navigates (no page reload) to sample **F50.3-B**.
4. Snapshots the store: the entry for sample A's UUID is **still there** —
   `prepareForSampleLoad` only deletes `propertyBags["scrollPosition"]` /
   `["listPosition"]` (sampleSlice.ts:207-208), nothing else.
5. Navigates back to A — the `All` pill is still selected, proving the
   stale entry is live state.

Screenshots land in
`findings/repros/verify/artifacts/50-state/F50.3-{A-after-click,B,A-return}.png`.

### What this *refines* about the finding

| Sub-claim | Status | Why |
|---|---|---|
| `app.propertyBags` per-event entries never cleared on sample switch → grow unbounded | **CONFIRMED** | Stale UUID-keyed entry survives A→B; only `scrollPosition`/`listPosition` are swept. In VS Code mode this is also persisted on every debounced write. |
| Positional keys collide between samples → visible UI leak | **NOT REPRODUCED** | Transcript `eventNodeId` is `event.uuid` (`treeify.ts:134`), not positional, so sample B's panel shows its own default. |
| `sample.collapsedIdBuckets` never cleared | **moot — dead state** | No caller outside `sampleSlice.ts`; `useCollapsibleIds` writes to `app.propertyBags`, not this map. |
| `RecordTree` collapse state leaks (Metadata tab) | **self-healing** | `RecordTree.tsx:70-74` clears its own bucket on unmount; tab/sample switch unmounts it. |

**Recommendation:** keep F50.3 as MEDIUM but reword: drop the
"positional collision" example, lead with the unbounded-growth /
persisted-forever claim.

---

## F50.9 — IndexedDB cache key mismatch (write relative, read absolute)

| | |
|---|---|
| **Verdict** | **FALSE_POSITIVE** (latent code-smell only — downgrade to INFO) |
| **Verify** | `F50.9_indexeddb_cache_miss.py` |
| **`.eval`** | reuses any log in `findings/repros/logs/50-state/` |

### Run

```bash
uv run --with playwright python \
    findings/repros/tasks/50-state/F50.9_indexeddb_cache_miss.py
```

### What it does

Cold-deep-links to `#/logs/<bare-filename>/samples` (the "relative
`logFileName` from URL routing" case the finding cites), waits for
`syncLog()` to populate IndexedDB, then via `page.evaluate()`:

- reads the key actually written to the `log_details` object store,
- reads `state.logs.{logDir,selectedLogFile}` from Zustand,
- re-implements `utils/uri.ts isUri()`/`join()` and computes the
  `logAbsPath` that the **read** branch would use on the next call,
- compares the two; reloads and counts rows (a real mismatch would
  produce a duplicate row under the other key).

### Why it's a false positive

The source asymmetry in `logSlice.ts:195-247` is real (read via
`logAbsPath`, miss-path write via `logFileName`). But the **only** caller
is `App.tsx:105 loadLog(selectedLogFile)`, and `selectedLogFile` is set by
`logsSlice.ts setSelectedLogFile:382-385` which performs the **same**
`isUri()`/`join()` resolution first. So `logFileName` arriving at `syncLog`
is always already an absolute `file://` URI → `isUri(logFileName)` is true
→ `logAbsPath === logFileName`. Read key == write key; cache hits; no
duplicate rows.

The bug would fire if a future caller passed a relative path to `syncLog`
directly, or if `setSelectedLogFile` ran while `state.logs.logDir` was
still `undefined` (race) — neither happens today. Worth fixing for
hygiene; not a live bug.
