# Documented-only findings (perf & race conditions)

These are real bugs from the [code review findings](../SUMMARY.md) that **cannot be demonstrated with a static `.eval` log file**. Reproducing them requires either a perf harness (large synthetic input + DevTools profiler / `performance.now()` timing) or a fake-timer / interleaving harness (vitest `vi.useFakeTimers()`, mocked `postMessage`, mocked IndexedDB latency).

Each entry below has been re-verified against the current source (2026-04-27) — line numbers are accurate as of `daf8cebd3`.

See also: [`NOT_REPRODUCIBLE.md`](NOT_REPRODUCIBLE.md) for findings that fall outside `.eval` scope for *structural* reasons (closed unions, live-streaming-only paths, HTTP layer).

---

## F21.5 — `filterSamples` re-compiles the filtrex expression once per sample

**Severity:** MEDIUM
**Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/sample-tools/filters.ts:255-260, 335-341`
**Category:** perf
**Original finding:** [`../21-sample-list-descriptors.md`](../21-sample-list-descriptors.md#f215--filtersamples-re-compiles-the-filtrex-expression-once-per-sample)

### What the bug is
`filterSamples` calls `filterExpression(...)` inside `samples.filter(...)`, and `filterExpression` calls `compileExpression(filterValue, {...})` on every invocation. The expression string is identical for every sample, so for a 10 000-sample log the same filtrex grammar is lexed/parsed/compiled 10 000 times per filter evaluation.

```ts
const result = samples.filter((sample) => {
  if (filterValue) {
    const { matches, error: sampleError } = filterExpression(
      evalDescriptor, sample, filterValue          // ← compiles inside, per-sample
    );
```

### Why no static repro
This is throughput, not correctness — a small `.eval` renders fine; the defect is only visible as keystroke→render latency on logs with thousands of samples.

### How to reproduce
1. Generate a large log: `uv run inspect eval examples/popularity --model mockllm/model --limit 1 --epochs 10000 --log-dir /tmp/perf-f21.5` (or any task with ≥5 000 samples).
2. `uv run inspect view --log-dir /tmp/perf-f21.5`, open the log, go to the **Samples** tab.
3. Open Chrome DevTools → Performance, start recording, type `accuracy > 0.5` in the filter input, stop recording after the list updates.
4. In the flame chart look for the `filterSamples` frame: the bulk of self-time is in `compileExpression` / Jison parser internals, repeated `samples.length` times.
5. Quantitative check: wrap line 255 with `console.time("compile")`/`console.timeEnd("compile")` and sum — expect ≥1 ms × N samples on a cold V8.

### Suggested fix
Hoist `compileExpression(filterValue, …)` outside the `.filter` loop (it is pure on `filterValue`). Pass the per-sample data via the variable bag (`expression({…vars, __sample: sample})`) and have `customProp` / `extraFunctions` read from `__sample` instead of closing over `sample`.

---

## F40.7 — `ANSIDisplay` re-parses output on every render

**Severity:** MEDIUM
**Location:** `src/inspect_ai/_view/ts-mono/packages/react/src/components/AnsiDisplay.tsx:22-23, 26-77`
**Category:** perf
**Original finding:** [`../40-content-renderers.md`](../40-content-renderers.md#f407--ansidisplay-re-parses-output-on-every-render) (duplicate: [F60.43](../60-base-react-components.md#f6043--ansidisplay-does-heavy-parse-on-every-render-with-no-memoization))

### What the bug is
`new ANSIOutput()` + `processOutput(output)` + `getUniformBackgroundColor()` (a second full pass over `outputLines`) run unconditionally in the render body. Toggling the **show raw** button (`setShowRaw`) re-renders → re-parses the entire ANSI stream. There is no virtualization, so a 10 k-line tool output also produces ≥10 k DOM nodes per render.

```tsx
const [showRaw, setShowRaw] = useState(false);
const ansiOutput = new ANSIOutput();
ansiOutput.processOutput(output);                       // ← every render
// ...
const uniformBackgroundColor = getUniformBackgroundColor();  // ← second full scan
```

### Why no static repro
A `.eval` with a large ANSI tool output renders *eventually*; the bug is the freeze on every parent re-render / raw-toggle, which needs a wall-clock measurement against a multi-thousand-line payload.

### How to reproduce
1. Build a repro task whose tool returns `"\x1b[31mline\x1b[0m\n" * 20000` (20 k coloured lines) — the existing `findings/repros/_common.py` helpers can emit a `ToolEvent` with that `output`.
2. Open in `inspect view` → Transcript → expand the tool event so `ANSIDisplay` mounts.
3. Open DevTools → Performance, start recording, click the **`</>` show raw** toggle once.
4. Observe: a single long task dominated by `ANSIOutput.processOutput` and `getUniformBackgroundColor`, even though `output` did not change.
5. React DevTools Profiler will show `ANSIDisplay` self-time ≫ children commit time on every toggle.

### Suggested fix
Wrap the parse + background-colour scan in `useMemo(() => {…}, [output])`. Longer-term, virtualize `outputLines` (the component already renders a flat list of `<div>` per line, so `react-virtuoso` drops in cleanly).

---

## F02.13 — `TranscriptOutline` rebuilds arrays / Sets on every render and scroll tick

**Severity:** LOW
**Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/outline/TranscriptOutline.tsx:205, 213` and `packages/react/src/hooks/useScrollTrack.ts:64, 121-139`
**Category:** perf
**Original finding:** [`../02-transcript-transform-pipeline.md`](../02-transcript-transform-pipeline.md#f0213--transcriptoutline-recomputes-elementids-and-outlineids-set-on-every-renderscroll)

### What the bug is
`elementIds = allNodesList.map(n => n.id)` is computed in the render body (no `useMemo`) and passed to `useScrollTrack`. Because `useScrollTrack`'s effect depends on `elementIds` by identity, the scroll listener + 1 s interval are torn down and re-attached on **every** outline render. Inside the scroll callback, `findNearestOutlineAbove` builds `new Set(outlineNodeList.map(...))` from scratch on each invocation, and `useScrollTrack` itself builds `new Set(elementIds)` per tick.

```tsx
const elementIds = allNodesList.map((node) => node.id);          // L205, no useMemo
const findNearestOutlineAbove = useCallback((targetId) => {
  // ...
  const outlineIds = new Set(outlineNodeList.map((n) => n.id));   // L213, per scroll tick
```

### Why no static repro
Visible only as scroll jank / GC pressure on transcripts with thousands of events; small repro logs scroll smoothly.

### How to reproduce
1. Generate a log with ~5 000 transcript events (e.g. an agent loop with `--max-messages 2500` against `mockllm/model` using `custom_outputs` to keep it bounded).
2. Open the sample → Transcript tab so the outline mounts.
3. DevTools → Performance → record while scrolling the transcript continuously for ~5 s.
4. In the bottom-up view, filter for `Set` / `findNearestOutlineAbove` / `findTopmostVisibleElement` — allocation count scales with scroll-tick × event count. The `useEffect` cleanup in `useScrollTrack.ts:132-138` also fires on every render (visible as repeated `removeEventListener`/`clearInterval` in the event log).

### Suggested fix
`useMemo` `elementIds` on `[allNodesList]`; hoist `outlineIds` into a `useMemo` on `[outlineNodeList]` and capture it in the `findNearestOutlineAbove` closure. In `useScrollTrack`, build `elementIdSet` once via `useMemo([elementIds])`.

---

## F70.9 — Blocking synchronous I/O inside `async def` handlers

**Severity:** MEDIUM
**Location:** `src/inspect_ai/_view/fastapi_server.py:314-316, 337-343, 390-398, 430-438`; `src/inspect_ai/_view/common.py:212-214, 454, 474-475`
**Category:** perf / async-correctness
**Original finding:** [`../70-python-view-backend.md`](../70-python-view-backend.md#f709--blocking-filesystem-io-inside-async-handlers)

### What the bug is
Several FastAPI/aiohttp `async def` handlers call synchronous fsspec / sqlite operations directly — `read_eval_set_info`, `fs.exists`, `fs.read_bytes`, `fs.info` (via `size_in_mb`), `fs.rm`, `SampleBuffer.get_samples`/`get_sample_data`. Each of these blocks the uvicorn event loop for the full round-trip.

```python
mapped_dir = await _map_file(request, flow_dir)
fs = filesystem(mapped_dir)
flow_file = f"{mapped_dir}{fs.sep}flow.yaml"
if fs.exists(flow_file):              # ← blocking S3 HEAD on the event loop
    bytes = fs.read_bytes(flow_file)  # ← blocking S3 GET on the event loop
```

### Why no static repro
Not observable when serving local-disk logs (sub-millisecond syscalls). Requires a high-latency backend (S3/Azure or an artificially-slowed fsspec implementation) plus concurrent requests so that one blocked handler visibly stalls another.

### How to reproduce
1. Point the viewer at an S3 bucket in a far region (or wrap `LocalFileSystem` with `time.sleep(2)` in `_open`/`_info` and register it as a custom fsspec protocol).
2. Start `uv run inspect view --log-dir s3://… --port 7575`.
3. In one terminal: `curl 'http://127.0.0.1:7575/flow?dir=<sub>'` (triggers the blocking `fs.exists`/`fs.read_bytes`).
4. While that hangs, in a second terminal: `time curl 'http://127.0.0.1:7575/events'` — the trivial `/events` poll waits the full S3 latency before responding, proving the loop is blocked.
5. Alternatively run `python -X dev` / `PYTHONASYNCIODEBUG=1` and watch for `Executing <Task …> took X.XXX seconds` slow-callback warnings.

### Suggested fix
Wrap each sync call in `anyio.to_thread.run_sync(...)`, or switch to the existing `async_filesystem()` helper (`_async_*` fsspec methods) and an async sample-buffer accessor.

---

## F50.7 — `ReplicationService` flush early-return can strand the last batch

**Severity:** MEDIUM
**Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/state/sync/replicationService.ts:141-201` (throttle setup at `:54-61`)
**Category:** race
**Original finding:** [`../50-state-and-routing.md`](../50-state-and-routing.md#f507--replicationservice-flush-can-strand-pending-updates)

### What the bug is
`flushPreviewBatch` / `flushDetailBatch` early-return when `_flushing*` is already `true`, **without rescheduling**. If the in-flight `await this._database.writeLogPreviews(...)` takes longer than the 100 ms throttle window, the trailing-edge throttle fires `flushPreviewBatch` again, hits the guard, and discards the trigger. Entries added to `_pendingPreviewUpdates` during the await then sit in the buffer until the *next* `onComplete` — which never arrives if the sync just finished.

```ts
private async flushPreviewBatch() {
  if (this._flushingPreview) {
    return;                              // ← drops the trigger; no reschedule
  }
  this._flushingPreview = true;
  try {
    const updates = { ...this._pendingPreviewUpdates };
    this._pendingPreviewUpdates = {};
    // ... await this._database.writeLogPreviews(...)   ← can exceed 100 ms
  } finally { this._flushingPreview = false; }
}
```

### Why no static repro
Requires a specific interleaving: IndexedDB write latency > 100 ms **and** the final work-queue `onComplete` arriving inside that window. Real browsers hit this nondeterministically; a `.eval` cannot drive it.

### How to reproduce
Vitest with fake timers and a controllable IndexedDB mock:
1. Mock `_database.writeLogPreviews` to return `new Promise(r => setTimeout(r, 500))`.
2. `vi.useFakeTimers()`; call `service.processingChanged`-style `onComplete` once → leading-edge throttle fires `flushPreviewBatch`, sets `_flushingPreview = true`, awaits.
3. Advance timers 50 ms; call `onComplete` again with a *new* preview (the "last" item) → it goes into `_pendingPreviewUpdates`, throttle schedules trailing call.
4. Advance timers to 100 ms → trailing throttle fires, `flushPreviewBatch` sees `_flushingPreview === true`, returns.
5. Advance timers to 500 ms → first write resolves, `finally` clears the flag.
6. Assert `_pendingPreviewUpdates` is **non-empty** and `_applicationContext.updateLogPreviews` was never called with the second item.

### Suggested fix
After the `finally` block, check `Object.keys(this._pendingPreviewUpdates).length > 0` and call `this._throttledFlushPreviewBatch()` again (same for `Detail`). Alternatively replace the boolean guard with a "dirty" flag that the in-flight flush re-checks before exiting.

---

## F51.7 — JSON-RPC request IDs use `Math.random()` — collision leaks promises

**Severity:** MEDIUM
**Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/client/api/vscode/jsonrpc.ts:120-131`
**Category:** race
**Original finding:** [`../51-data-loading-clients.md`](../51-data-loading-clients.md#f517--json-rpc-request-ids-use-mathrandom--collision-leaks-promises)

### What the bug is
Each outbound request generates `Math.floor(Math.random() * 1e6)` and stores `{resolve, reject}` in a `Map` keyed by that integer. If two concurrent requests draw the same id, the second `requests.set(id, …)` overwrites the first; when the response arrives it resolves the *second* promise and the first never settles. There is no timeout, so the caller (e.g. the parallel chunk fetcher in `remoteLogFile`) hangs forever.

```ts
return new Promise((resolve, reject) => {
  const requestId = Math.floor(Math.random() * 1e6);
  requests.set(requestId, { resolve, reject });   // ← clobbers on collision
  target.postMessage({ jsonrpc, id: requestId, method, params });
});
```

### Why no static repro
The defect is probabilistic (≈ p² × 5 × 10⁻⁷ per concurrent pair via birthday bound) and only reachable inside the VS Code webview transport — `inspect view` over HTTP never enters this code path.

### How to reproduce
Vitest unit test with a mocked PRNG:
1. `vi.spyOn(Math, "random").mockReturnValueOnce(0.123456).mockReturnValueOnce(0.123456)` so two consecutive calls produce the same `requestId`.
2. Build a fake `PostMessageTarget` whose `postMessage` echoes `{id, result: params}` back via the registered `onMessage` listener after a microtask.
3. Fire `transport.request("a", 1)` and `transport.request("b", 2)` concurrently.
4. Assert: the second promise resolves with `2`; the first promise is still pending after `await vi.runAllTimersAsync()` (and `requests.size === 0`, proving the handler was overwritten, not queued).

### Suggested fix
Replace the random id with a module-level monotonic counter (`let nextId = 0; const requestId = ++nextId;`). Optionally add a per-request timeout that `reject`s and deletes the map entry.

---

## F60.x — Per-render churn in `LiveVirtualList` and friends

**Severity:** LOW
**Category:** perf
**Original findings:** [`../60-base-react-components.md`](../60-base-react-components.md) — F60.28, F60.36, F60.37 (F60.43 is the `ANSIDisplay` duplicate covered by F40.7 above)

### What the bug is
Three independent per-render allocations in the shared `packages/react` library that compound when a transcript is open:

- **F60.36** — `packages/react/src/components/LiveVirtualList.tsx:372-378, 461-464`: `Footer` is declared inside the render body and passed via `components={{ Footer, ...components }}`. New component identity + new `components` object every render → Virtuoso remounts the footer on every parent render.
- **F60.37** — `packages/react/src/components/LiveVirtualList.tsx:218-223` and `packages/react/src/hooks/useScrollDirection.ts:121-123`: to detect when `scrollRef.current` becomes non-null, both attach a `MutationObserver` to **`document.body` with `subtree: true`**. Every DOM mutation anywhere on the page (including Virtuoso's own item churn while scrolling) fires every registered `sync()` callback.
- **F60.28** — `packages/react/src/components/ExtendedFindContext.tsx:117-123`: `contextValue` is a fresh object literal each render, so every consumer of `ExtendedFindContext` (including every `LiveVirtualList`) re-renders whenever the provider re-renders, even though the four contained callbacks are stable `useCallback`s.

```tsx
// F60.37
const observer = new MutationObserver(sync);
observer.observe(document.body, { childList: true, subtree: true });
```

### Why no static repro
Each is a constant-factor overhead per render / per DOM mutation. On a small `.eval` the cost is negligible; the impact only shows up as scroll-time CPU on large transcripts with multiple virtual lists mounted (transcript + outline + samples list).

### How to reproduce
1. Open any moderately large agent log (≥1 000 transcript events) in `inspect view`.
2. **F60.37**: DevTools → Performance → record while scrolling the transcript for 5 s. In the flame chart, search for `MutationObserver` / the `sync` closure — it fires once per Virtuoso row mount/unmount × number of observers (one per `LiveVirtualList` instance + one per `useScrollDirection` consumer). With 3+ lists mounted this is hundreds of callbacks per second of scrolling.
3. **F60.36 / F60.28**: React DevTools → Profiler → enable "Record why each component rendered" → record while typing in the find bar. `Footer` shows "parent component rendered" on every keystroke and is *remounted* (not re-rendered); `LiveVirtualList` shows "context changed" pointing at `ExtendedFindContext`.

### Suggested fix
- F60.36: hoist `Footer` to module scope (read `showProgress` from a prop or context), and `useMemo` the `components` object on `[components, showProgress]`.
- F60.37: replace the body-wide `MutationObserver` with a callback ref on the scroll container (`ref={el => setScrollParent(el)}`).
- F60.28: wrap `contextValue` in `useMemo([extendedFindTerm, registerVirtualList, countAllMatches, registerMatchCounter])`.
