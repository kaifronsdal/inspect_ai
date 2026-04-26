# Data Loading & API Client Layer

**Reviewer scope:** `apps/inspect/src/client/**` (api/view-server, api/vscode, api/static-http, api/shared, database/, remote/, storage/, utils/) and `apps/inspect/src/scoring/**`; cross-referenced against `src/inspect_ai/_view/inspect-openapi.json` and `state/sync/replicationService.ts`.
**Date:** 2026-04-22

---

## Summary

The client layer multiplexes three transport backends (FastAPI view-server, VS Code JSON-RPC, static-HTTP file hosting) behind a common `LogViewAPI` → `ClientAPI` adapter. The abstraction is sound, but the three backends drift on return shapes in several places, and the adapter's in-memory caching has a real race condition. The IndexedDB cache (`database/`) swallows nearly every error path by design, which is mostly fine for a cache but does make it hard to surface corruption. The hand-coded `EventData` union has fallen out of sync with the generated schema. The `scoring/` directory contains only pure metric-display helpers — there is **no** score-edit submission client; that surface area does not exist in this layer.

---

## Findings

### F51.1 — `pending_log_promise` returns wrong log under concurrent requests

- **Severity:** HIGH
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/client/api/client-api.ts:98-127`
- **Category:** correctness / race-condition

**Description:**
`get_log()` deduplicates in-flight fetches via a single module-scoped `pending_log_promise`, but the dedup check does not compare `log_file`. If caller A requests `logA.json` and (before it resolves) caller B requests `logB.json`, B is handed A's promise and receives A's contents.

**Evidence:**
```ts
if (!cached || log_file !== current_path || !current_log) {
  if (pending_log_promise) {
    return pending_log_promise;   // ← no check that it's for the same log_file
  }
  pending_log_promise = api.get_log_contents(log_file, 100).then(...);
```

**Why it matters / impact:**
Legacy `.json` logs only (`.eval` files take a different path), but for those, rapid navigation between two JSON logs can show the wrong transcript. Also, on resolve it writes `current_log = log; current_path = log_file;` using the *first* caller's `log_file`, so the cache is keyed correctly for A but B silently consumes A's data.

**Suggested fix:**
Track the in-flight `log_file` alongside the promise and only reuse when it matches; otherwise chain a new fetch.

---

### F51.2 — Hand-coded `EventData.event` union missing `ScoreEditEvent`, `SpanBeginEvent`, `SpanEndEvent`

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/client/api/types.ts:116-139`
- **Category:** correctness / consistency

**Description:**
`EventData` is hand-coded (per the comment, because generated `EventData.event` is `JsonValue`). Its union includes 17 event types but omits `ScoreEditEvent`, `SpanBeginEvent`, and `SpanEndEvent`, all of which are present in the canonical generated `Event` union (`packages/inspect-common/src/types/generated.ts:1578`).

**Evidence:**
```ts
event:
  | SampleInitEvent | SampleLimitEvent | SandboxEvent | StateEvent
  | BranchEvent | CompactionEvent | StoreEvent | ModelEvent | ToolEvent
  | ApprovalEvent | InputEvent | ScoreEvent | ErrorEvent | LoggerEvent
  | InfoEvent | StepEvent | SubtaskEvent;
  // missing: ScoreEditEvent, SpanBeginEvent, SpanEndEvent
```

**Why it matters / impact:**
Streamed sample data (`/pending-sample-data`) for running evals carries span events on virtually every request and score-edit events when scores are edited. Downstream code that switches on `event.event` will see these as type-uncovered, encouraging `as any` or causing exhaustiveness checks to lie.

**Suggested fix:**
Add the three missing members; ideally derive from the generated `Event` alias instead of re-listing.

---

### F51.3 — VSCode `get_logs` returns `[]` instead of `LogFilesResponse` on empty response

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/client/api/vscode/api-vscode.ts:67-78`
- **Category:** consistency / correctness

**Description:**
The `LogViewAPI.get_logs` contract is `Promise<LogFilesResponse>` (`{files, response_type}`), but the VSCode backend returns a bare `[]` when the JSON-RPC response is falsy.

**Evidence:**
```ts
const get_logs = async (mtime, clientFileCount) => {
  const response = await vscodeClient(kMethodEvalLogFiles, [...]);
  if (response) { return JSON5.parse(response); }
  else { return []; }   // ← shape violation
};
```

**Why it matters / impact:**
`replicationService._syncImpl()` calls `serverLogs.files.length` and `response.response_type === "full"` — both throw / mis-evaluate on `[]`. In VS Code with an empty log dir the replication sync would crash with "Cannot read properties of undefined (reading 'length')".

**Suggested fix:**
Return `{ files: [], response_type: "full" }`.

---

### F51.4 — `LogRoot` shape inconsistent across backends (`logs` vs `files`)

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/client/api/types.ts:308-312`, `view-server/api-view-server.ts:62-72`, `vscode/api-vscode.ts:40-56`, `static-http/api-static-http.ts:72-93`
- **Category:** consistency

**Description:**
`LogRoot` is declared as `{ logs: LogHandle[]; log_dir?; abs_log_dir? }`. Only static-http honours this. view-server's `get_log_root` returns the server's `LogListingResponse` (`{log_dir, files}` — no `logs`, no `abs_log_dir`). vscode's legacy-array branch returns `{log_dir: "", files: parsed}`. The fallback in `client-api.ts:get_logs` reads `logRoot?.logs || []`, which silently yields `[]` for view-server/vscode.

**Why it matters / impact:**
Currently masked because (a) view-server and vscode both implement `get_logs` directly so the fallback is dead, and (b) `logsSlice.ts:191` only reads `root.log_dir`/`root.abs_log_dir`. But it's a landmine: anyone who reads `root.logs` from a non-static backend gets `undefined` despite the type saying it's required.

**Suggested fix:**
Normalise to `LogRoot` in each backend (map `files` → `logs`), or change `LogRoot` to use `files`.

---

### F51.5 — Detail-queue index misalignment when a fetch fails

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/state/sync/replicationService.ts:101-128`
- **Category:** correctness / fallback-hiding-errors

**Description:**
The `_detailQueue` worker maps each input to either a `LogDetails` or `undefined`, then **filters out** `undefined`, then `onComplete` zips the filtered results back against the *unfiltered* `inputs` by index.

**Evidence:**
```ts
const details = await Promise.all(logHandles.map(async (log) => {
  try { return await this._api!.get_log_details(log.name); }
  catch { return undefined; }
}));
const allResults = details.filter((d) => d !== undefined);
return allResults;
...
onComplete: async (details, inputs) => {
  inputs.forEach((log, i) => {
    if (details[i]) this._pendingDetailUpdates[log.name] = details[i];
  });
```

**Why it matters / impact:**
With `batchSize: 1` (current config) this never triggers. But the code is structurally wrong — bumping `batchSize` would silently cache log B's details under log A's path whenever a middle item fails. Combined with the bare `catch {}` (error fully swallowed, not even logged), this is a latent data-corruption bug.

**Suggested fix:**
Don't filter; let `onComplete` skip `undefined` entries. Log the swallowed error.

---

### F51.6 — `joinURI` collapses `://` in absolute URLs

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/client/api/static-http/fetch.ts:128-132`
- **Category:** correctness / url-construction

**Description:**
`joinURI` strips leading *and* trailing slashes from every segment before joining with `/`. When the first segment is an absolute URL (`https://host/dir`), the regex doesn't touch it (no leading slash), but `get_log_dir_handle` (api-static-http.ts:94-97) builds `currentDirUrl` via `window.location.origin + ...` and then `joinURI(currentDirUrl, log_dir)` — and `fetchManifest` does `log_dir + "/listing.json"` without `joinURI`, while `get_log_root` uses `joinURI(log_dir, key)`. If `log_dir` itself is absolute (`https://cdn/.../logs`), `joinURI` leaves it intact, but if `log_dir` is `"/logs"` (root-relative), `joinURI` strips the leading `/` → produces `logs/file.eval` (relative) instead of `/logs/file.eval`.

**Evidence:**
```ts
export function joinURI(...segments: string[]): string {
  return segments
    .map((segment) => segment.replace(/(^\/+|\/+$)/g, ""))
    .join("/");
}
```

**Why it matters / impact:**
A static deployment with `log_dir: "/logs"` (absolute path on same origin) will fetch `logs/listing.json` relative to the *current page path*, not the root. Works only when the viewer is served from `/`.

**Suggested fix:**
Preserve a single leading `/` on the first segment; or use `new URL()` for absolute bases.

---

### F51.7 — JSON-RPC request IDs use `Math.random()` — collision leaks promises

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/client/api/vscode/jsonrpc.ts:120-131`
- **Category:** correctness

**Description:**
Each request generates `Math.floor(Math.random() * 1e6)` and stores `{resolve, reject}` in a `Map` keyed by that ID. A collision (≈1 in 1M per concurrent pair, but the viewer fires bursts of `get_log_summaries`/`get_log_bytes`) overwrites the earlier handler, so the earlier promise never settles.

**Evidence:**
```ts
const requestId = Math.floor(Math.random() * 1e6);
requests.set(requestId, { resolve, reject });
```

**Why it matters / impact:**
A leaked promise in `remoteEvalFile`'s parallel chunk fetcher hangs the whole sample load forever with no error. There is also no timeout on JSON-RPC requests, so the failure mode is "spinner forever".

**Suggested fix:**
Monotonic counter (`let nextId = 0; ++nextId`). Consider a per-request timeout that rejects and deletes from the map.

---

### F51.8 — `get_log_summaries` index mapping breaks when static-http drops missing entries

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/client/api/client-api.ts:273-294` and `static-http/api-static-http.ts:177-203`
- **Category:** correctness / consistency

**Description:**
`client-api.get_log_summaries` splits inputs into eval vs JSON files, fetches JSON-file summaries via `api.get_log_summaries(Object.keys(json_files))`, then re-indexes results with `json_files[Object.keys(json_files)[i]]`. The static-http backend silently **omits** files not found in the manifest (no placeholder), so the returned array can be shorter than the input — every result after the first miss is assigned the wrong original index.

**Evidence:**
```ts
// static-http
files.forEach((file) => {
  const fileKey = keys.find((key) => file.endsWith(key));
  if (fileKey) { result.push(manifest[fileKey]); }   // else: dropped
});
```

**Why it matters / impact:**
Log list rows show another log's task/model/metric. Only triggers in static-http mode with JSON (non-`.eval`) logs and a stale manifest, but the failure is silent.

**Suggested fix:**
Backends must return an array of the same length as input (with `undefined` placeholders), or return a `Record<file, preview>`.

---

### F51.9 — Stale cached `remoteEvalFile` never refreshed after `SampleNotFoundError` retry

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/client/api/client-api.ts:76-93`, `188-218`
- **Category:** perf / code-smell

**Description:**
`remoteEvalFile(log_file, cached)` only writes to `loadedEvalFile` when `cached === true`. On `SampleNotFoundError` the retry calls `fetchSample(false)`, which opens a fresh remote zip (with the up-to-date central directory) but does **not** replace the stale cached one. Every subsequent sample click first hits the stale cache, gets `SampleNotFoundError`, then re-downloads the full central directory again.

**Why it matters / impact:**
For a large `.eval` file that grew after first open, every sample navigation pays an extra round-trip + central-directory parse. No incorrect data, just wasted bandwidth/latency.

**Suggested fix:**
After a successful uncached open, update `loadedEvalFile`.

---

### F51.10 — VSCode storage `getItem` crashes on first run (state is `undefined`)

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/client/storage/index.ts:12-18`
- **Category:** correctness

**Description:**
`vscodeApi.getState()` returns `undefined` until something has been stored. The code does `JSON5.parse(state)` with no null guard; `JSON5.parse(undefined)` throws `SyntaxError: JSON5: invalid character 'u'`.

**Evidence:**
```ts
getItem: (_name: string) => {
  const state = vscodeApi.getState() as string;
  const deserialized = JSON5.parse(state) as {...};
  return deserialized;
},
```

**Why it matters / impact:**
Depends on whether the Zustand/Redux persist layer wraps `getItem` in a try/catch. If it doesn't, first launch in VS Code throws during store rehydration.

**Suggested fix:**
`if (!state) return undefined;` before parse.

---

### F51.11 — `staticHttpApi` only replaces the *first* space with `+`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/client/api/static-http/api-static-http.ts:27-28`
- **Category:** url-construction

**Description:**
`.replace(" ", "+")` is non-global. A `log_dir` or `log_file` containing two or more spaces is only partially encoded.

**Evidence:**
```ts
const resolved_log_dir = log_dir?.replace(" ", "+");
const resolved_log_path = log_file ? log_file.replace(" ", "+") : undefined;
```

**Why it matters / impact:**
Paths with multiple spaces 404. Also, `+` is only valid as space in `application/x-www-form-urlencoded` query strings, not in path segments — `encodePathParts` (already used downstream) is the right tool; this pre-replace is both incomplete and arguably wrong.

---

### F51.12 — `manifestPromise` cached even on rejection — permanent failure

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/client/api/static-http/api-static-http.ts:50-61`
- **Category:** fallback-hiding-errors

**Description:**
`fetchManifest` does not pass a `handleError`, so a 404/403/network error on `listing.json` rejects. `getManifest` stores the promise in `manifestPromise` *before* it settles and never clears it on rejection. All later calls re-await the same rejected promise.

**Why it matters / impact:**
Transient network blip → static viewer never recovers without page reload. Also, since `get_log_summaries` and `get_log_root` both call `getManifest`, the whole listing UI is dead.

**Suggested fix:**
`.catch(e => { manifestPromise = undefined; throw e; })`, and pass a 404 handler so missing manifest yields `{}` rather than throwing.

---

### F51.13 — `clearCacheForFile` calls in replication sync are not awaited

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/state/sync/replicationService.ts:334-336`, `390-392`, `416-418`
- **Category:** correctness / race-condition

**Description:**
Three call sites fire-and-forget `this._database?.clearCacheForFile(...)`. Immediately afterwards, `writeLogs(updatedLogs)` and `findMissingPreviews/Details` run. Dexie operations are queued per-table so the practical risk is low, but `findMissingPreviews` may read a record that's about to be deleted → skips re-fetch → stale preview persists for one cycle.

**Suggested fix:**
`await Promise.all(toInvalidate.map(f => this._database?.clearCacheForFile(f.name)))`.

---

### F51.14 — Zstd worker init failure is cached forever; blob URL never revoked

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/client/remote/zstd-worker.ts:116-151`
- **Category:** fallback-hiding-errors / perf

**Description:**
`workerInitPromise` is set once and never cleared. If init rejects (e.g. CSP blocks the blob URL, or `fzstd` eval throws), every subsequent zstd file >1MB rejects with the same error — there is no retry and no fallback to synchronous `decompressZstdSync`. `blobURL` is created but never `URL.revokeObjectURL`'d.

**Suggested fix:**
On init rejection, null out `workerInitPromise`/`zstdWorker` and fall back to sync decompress for that call.

---

### F51.15 — `fetchRange` does not check `response.ok`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/util/src/http.ts:4-14` (consumed by `client/remote/remoteZipFile.ts` and `static-http/api-static-http.ts:160`)
- **Category:** fallback-hiding-errors

**Description:**
`fetchRange` reads `response.arrayBuffer()` unconditionally. A 404/500/416 returns an HTML error page as bytes; `openRemoteZipFile` then tries to parse it as a ZIP EOCD record and throws the misleading "End of central directory record not found" instead of surfacing the actual HTTP error.

**Suggested fix:**
`if (!response.ok) throw new Error(...)` before reading body.

---

### F51.16 — `download_file` forces `text/plain` MIME for binary content

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/client/api/shared/api-shared.ts:14-17`
- **Category:** correctness

**Description:**
Non-data-URL inputs (including `Blob`, `ArrayBuffer`, `Uint8Array`) are wrapped in `new Blob([filecontents], { type: "text/plain" })`. For an existing `Blob` this discards its real MIME type; for binary buffers it mislabels them.

**Why it matters / impact:**
Browsers may add `.txt` extension or open instead of download depending on OS settings. Minor.

---

### F51.17 — Unreachable `else` branch in `fetchFile` / `fetchTextFile`

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/client/api/static-http/fetch.ts:19-28`, `44-53`
- **Category:** dead-code

**Description:**
`if (response.ok)` covers 200-299; `else if (response.status !== 200)` is therefore always true in the else branch; the trailing `else { throw ... }` is unreachable. Also the error message has a stray `)` — `` `${status}: ${message})` ``.

---

### F51.18 — Duplicated `toLogPreview` implementations (one subtly different)

- **Severity:** LOW
- **Location:** `client/utils/type-utils.ts:5-38`, `client/api/view-server/api-view-server.ts:175-200`, `client/database/utils.ts:3-31`
- **Category:** dead-code / consistency

**Description:**
Three near-identical `EvalHeader → LogPreview` mappers. `database/utils.ts:toLogOverview` is **never imported anywhere** (dead). `api-view-server.ts:toLogPreview` computes `Object.values(header.results?.scores || {})` — `scores` is an *array*, so `Object.values` happens to work but is needlessly different from the canonical `client/utils/type-utils.ts` version. `database/utils.ts:toLogOverview` uses `evalSpec.created` for `started_at` instead of `stats?.started_at` (different semantics).

**Suggested fix:**
Delete `database/utils.ts`; have view-server import from `client/utils/type-utils.ts`.

---

### F51.19 — `readCompleteLog` is dead and acknowledges its own type-unsafety

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/client/remote/remoteLogFile.ts:312-337`
- **Category:** dead-code

**Description:**
`readCompleteLog` is exported on `RemoteLogFile` but has no callers. It carries a `// TODO: This needs review` comment and an `as EvalLog` cast over a partial object. Safe to delete.

---

### F51.20 — Stale comment: `MAX_SAMPLE_SIZE_BYTES` says 512MB but value is 2GB

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/client/remote/remoteLogFile.ts:29-32`
- **Category:** code-smell

**Evidence:**
```ts
// Maximum uncompressed sample size (512MB). ...
const MAX_SAMPLE_SIZE_BYTES = 2048 * 1024 * 1024;
```

---

### F51.21 — VSCode `get_log_summaries` returns raw headers, not `LogPreview[]`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/client/api/vscode/api-vscode.ts:127-134` vs `view-server/api-view-server.ts:212-223`
- **Category:** consistency

**Description:**
`LogViewAPI.get_log_summaries` is typed `Promise<LogPreview[]>`. view-server fetches `EvalHeader[]` and maps through `toLogPreview`. vscode just `JSON5.parse(response)` and returns whatever the extension sent. If the VS Code extension sends `EvalHeader[]` (matching the server endpoint it proxies), the result lacks `primary_metric`, `started_at`, etc. and has extra fields. Downstream `replicationService` writes this into IndexedDB under the `LogPreview` schema.

**Why it matters / impact:**
Log list in VS Code may show blank metric/started columns for `.json` logs. (Needs verification against the extension's actual payload.)

---

### F51.22 — `readLogSummary` drops `version` from header

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/client/remote/remoteLogFile.ts:289-307`
- **Category:** consistency

**Description:**
`readLogSummary` builds a `LogDetails` from `header` but omits `version: header.version`, while the JSON-log path in `client-api.ts:163-175` and the `LogDetails` interface both include it. Any consumer branching on `details.version` will see `undefined` for `.eval` files.

---

### F51.23 — IndexedDB read errors swallowed to `null` / `{}` / full-input

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/client/database/service.ts:98-133`, `153-178`, `180-200`, `231-246`, `249-272`, `274-294`
- **Category:** fallback-hiding-errors

**Description:**
Every read method wraps the body in `try { ... } catch (error) { log.error(...); return <empty>; }`. This is intentional (cache-miss semantics), but it means a corrupted IndexedDB or quota error is indistinguishable from "nothing cached" — replication will re-fetch everything every page load with only a `console.error` to indicate why. Note that `findMissingPreviews`/`findMissingDetails` return the *full input list* on error, which is the safe choice. Flagging as INFO since it matches the project's stated "fail fast" preference inversely but is reasonable for a cache.

---

### F51.24 — `writeLogPreviews` silently mis-aligns when arrays differ in length

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/client/database/service.ts:136-151`
- **Category:** correctness

**Description:**
`writeLogPreviews(previews, filePaths)` zips by index with no length check. Combined with F51.8 (static-http dropping entries), a short `previews` array writes `{file_path: filePaths[n], preview: undefined}` for trailing entries — Dexie stores `undefined` and later `readLogPreviews` returns it as a "hit", suppressing re-fetch.

---

### F51.25 — `flushPreviewBatch` swallows DB write errors with bare `.catch(() => {})`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/state/sync/replicationService.ts:157-159`, `218`
- **Category:** fallback-hiding-errors

**Description:**
`writeLogPreviews(...).catch(() => {})` and `Promise.all([countRows...]).catch(() => {})` discard all errors with no log. Contrast `flushDetailBatch` which does *not* catch (so a write failure there would throw inside `throttle` and likely be lost too, but at least surfaces in devtools).

---

### F51.26 — `jsonRpcPostMessageServer` exported but unused in inspect app

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/client/api/vscode/jsonrpc.ts:137-168`
- **Category:** dead-code

**Description:**
The server half of the JSON-RPC transport is defined here but only the client half is used in `apps/inspect`. (A copy in `apps/scout` is independent.) Either dead or intended for re-export to the VS Code extension — worth confirming.

---

### F51.27 — `scoring/` contains no client/API code; map is misleading

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/scoring/metrics.ts`, `scores.ts`, `types.ts`
- **Category:** code-smell

**Description:**
Per the codebase map this directory was expected to hold "score input form, retry logic, API calls". It contains only pure display helpers (`metricDisplayName`, `groupScorers`, `expandGroupedMetrics`). There is no score-edit submission path, no optimistic update, no rollback — `ScoreEditEvent` is read-only in this app. The OpenAPI spec also has no score-write endpoint. Noting so reviewers don't search for it.

---

### F51.28 — `view-server` `get_log_dir_handle` missing — all view-server users share one IndexedDB

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/apps/inspect/src/client/api/client-api.ts:386-393`
- **Category:** consistency

**Description:**
Only static-http implements `get_log_dir_handle`. For view-server and vscode the adapter falls back to `log_dir || "default_log_dir"`. With view-server, `log_dir` is whatever the server reports (often an absolute path), so two different log dirs do get different DB names — fine. But if `log_dir` is `undefined` (server didn't return one), every session shares `InspectAI_default_log_dir` and the cache mixes logs from unrelated directories.

---

## Files reviewed

- [x] `client/api/types.ts` — interface defs; hand-coded EventData drift (F51.2)
- [x] `client/api/index.ts` — backend resolution; clean
- [x] `client/api/client-api.ts` — adapter + caching; F51.1, F51.8, F51.9
- [x] `client/api/shared/api-shared.ts` — download helper; F51.16
- [x] `client/api/view-server/api-view-server.ts` — F51.4, F51.18
- [x] `client/api/view-server/request.ts` — clean; good ApiError surfacing
- [x] `client/api/vscode/api-vscode.ts` — F51.3, F51.4, F51.21
- [x] `client/api/vscode/jsonrpc.ts` — F51.7, F51.26
- [x] `client/api/static-http/api-static-http.ts` — F51.6, F51.11, F51.12
- [x] `client/api/static-http/fetch.ts` — F51.6, F51.17
- [x] `client/remote/remoteLogFile.ts` — F51.19, F51.20, F51.22
- [x] `client/remote/remoteZipFile.ts` — F51.15 (via fetchRange); ZIP64 parsing looks correct
- [x] `client/remote/decompression.ts` — clean
- [x] `client/remote/zstd-worker.ts` — F51.14
- [x] `client/remote/zstd-worker-code.ts` — embedded blob; no issues
- [x] `client/database/index.ts` — re-exports; aliases `LogFileRecord` etc. (legacy names)
- [x] `client/database/manager.ts` — version-mismatch recreate duplicates `resolveDBName` logic inline (line 41-43); minor
- [x] `client/database/schema.ts` — clean
- [x] `client/database/service.ts` — F51.23, F51.24
- [x] `client/database/utils.ts` — dead (F51.18)
- [x] `client/database/database.test.ts` — adequate coverage
- [x] `client/storage/index.ts` — F51.10
- [x] `client/utils/type-utils.ts` — canonical toLogPreview
- [x] `scoring/metrics.ts`, `scores.ts`, `types.ts` — pure helpers; F51.27
- [x] `state/sync/replicationService.ts` — F51.5, F51.13, F51.25 (cross-ref only)
- [x] `inspect-openapi.json` — endpoint shapes cross-checked

## Open questions / needs verification

- F51.10: does the Redux-persist/Zustand layer wrap `storage.getItem` in try/catch? If yes, downgrade to INFO.
- F51.21: what does the VS Code extension actually return for `eval_log_headers`? If it already returns `LogPreview[]`, downgrade to INFO.
- F51.7: is there a known max concurrency for VS Code requests? With `MAX_PARALLEL_CHUNKS=10` × multiple files the birthday-collision odds are still tiny but non-zero.
- F51.28: does the FastAPI `/log-dir` endpoint ever return `undefined` in practice?
