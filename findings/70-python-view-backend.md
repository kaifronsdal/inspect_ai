# Python View Backend

**Reviewer scope:** `src/inspect_ai/_view/*.py` (server.py, fastapi_server.py, common.py, view.py, schema.py, _openapi.py, _dist.py, notify.py, azure.py, fastapi_prereqs.py); cross-referenced against `inspect-openapi.json` and `ts-mono/apps/inspect/src/client/api/view-server/*.ts`
**Date:** 2026-04-22

---

## Summary

The viewer backend ships two parallel HTTP implementations (aiohttp in `server.py`, FastAPI in `fastapi_server.py`) that share helpers in `common.py`. Overall structure is sound and the FastAPI variant is cleaner, but the two have diverged in several places (Azure handling, range-clamping, error mapping). There is one clear security bug (lazy `map()` skips path validation), one correctness bug that breaks large non-S3 downloads, several path-prefix authorization weaknesses, and a fair amount of dead code. Many async handlers do blocking filesystem I/O which will stall the event loop under load.

---

## Findings

### F70.1 — `map()` is lazy: log-header path validation never runs (aiohttp)

- **Severity:** HIGH
- **Location:** `src/inspect_ai/_view/server.py:295`
- **Category:** correctness / security

**Description:**
`map(validate_log_file_request, files)` creates a lazy iterator that is never consumed, so `validate_log_file_request` is never actually called for any file in `/api/log-headers`.

**Evidence:**
```python
@routes.get("/api/log-headers")
async def api_log_headers(request: web.Request) -> web.Response:
    files = request.query.getall("file", [])
    files = [normalize_uri(file) for file in files]
    map(validate_log_file_request, files)          # <- no-op
    return await log_headers_response(files)
```

**Why it matters / impact:**
When the aiohttp server is run without an `authorization` token (default `inspect view`), this is the only line of defence confining reads to `log_dir`. With it disabled, a client can pass `?file=/etc/passwd` or any `.eval`/`.json` path on disk and have the server attempt to read and return its parsed header. The FastAPI variant validates correctly (`fastapi_server.py:358-365`), so this only affects the aiohttp fallback path — which is still the default when fastapi/uvicorn aren't installed.

**Suggested fix:**
`for f in files: validate_log_file_request(f)`.

---

### F70.2 — `stream_log_bytes` raises `ValueError` for large non-S3 files

- **Severity:** HIGH
- **Location:** `src/inspect_ai/_view/common.py:251-269`
- **Category:** correctness

**Description:**
When the file is not S3 **and** the requested range exceeds `stream_threshold_bytes` (50 MB), the code falls through the `if request_size <= stream_threshold_bytes` early-return and lands on the S3-only code path, which then asserts `isinstance(connection, S3FileSystem)` and raises.

**Evidence:**
```python
if not fs.is_async() or not fs.is_s3():
    ...
    if request_size <= stream_threshold_bytes:
        bs = await get_log_bytes(log_file, start, end)
        return BytesIO(bs)
    # >50MB local/azure file falls through here

connection = async_connection(log_file)
if not isinstance(connection, S3FileSystem):
    raise ValueError("Expected S3FileSystem")
```

**Why it matters / impact:**
`/api/log-download/{log}` and `/api/log-bytes/{log}` will 500 for any local or Azure `.eval` file larger than 50 MB. Large eval logs are common; this breaks "Download log" in the viewer for the most common (local) deployment.

**Suggested fix:**
For non-S3 backends, always return `BytesIO(await get_log_bytes(...))` regardless of size (or add a real local streaming path). The `if request_size <= stream_threshold_bytes` guard should not allow fall-through for non-S3.

---

### F70.3 — Path-prefix authorization is bypassable via sibling-directory prefix

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/fastapi_server.py:501-502`, `src/inspect_ai/_view/server.py:69-71`
- **Category:** security / correctness

**Description:**
Both `OnlyDirAccessPolicy._validate_log_dir` and the aiohttp `validate_log_file_request` use `file.startswith(self.dir) and ".." not in file`. A bare `startswith` on a string (not a path) matches sibling directories that share a prefix.

**Evidence:**
```python
def _validate_log_dir(self, file: str) -> bool:
    return file.startswith(self.dir) and ".." not in file
```

**Why it matters / impact:**
If the configured log dir is `/home/u/logs`, a request for `/home/u/logs-private/x.eval` passes (`"/home/u/logs-private".startswith("/home/u/logs")` → True). The `".."` check doesn't help here. Real-world impact is limited because the server typically binds to `127.0.0.1`, but it defeats the stated intent of `OnlyDirAccessPolicy`.

**Suggested fix:**
Normalize both sides and compare with `os.path.commonpath` / ensure trailing separator before `startswith`; or use `Path(file).resolve().is_relative_to(Path(dir).resolve())` for local paths.

---

### F70.4 — Destructive delete exposed via HTTP GET

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/fastapi_server.py:149-154`, `src/inspect_ai/_view/server.py:97-105`
- **Category:** correctness / security

**Description:**
`/log-delete/{log}` is a `GET` that calls `fs.rm(log_file)` unconditionally.

**Why it matters / impact:**
GET should be safe/idempotent. A prefetching browser, link-preview bot, or `<img src="http://127.0.0.1:7575/api/log-delete/...">` on a malicious page could silently delete eval logs (no CSRF protection, no auth in default mode). The TS client never calls this endpoint (see F70.14), so changing the verb is low-risk.

**Suggested fix:**
Change to `DELETE` (or `POST`) and require confirmation/authorization. Consider removing entirely if unused.

---

### F70.5 — `header-only=undefined` crashes `get_log_file`

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/common.py:145` ↔ `ts-mono/apps/inspect/src/client/api/view-server/api-view-server.ts:162`
- **Category:** correctness / consistency

**Description:**
The TS client builds the URL via template literal: `` `/logs/${...}?header-only=${headerOnly}` ``. When `headerOnly` is `undefined` (the parameter is optional), the query string becomes `header-only=undefined`. The Python side then runs `int("undefined")` → `ValueError`.

**Evidence:**
```python
header_only_mb = int(header_only_param) if header_only_param is not None else None
```

**Why it matters / impact:**
In FastAPI this surfaces as an opaque 500; in aiohttp it's caught by `log_file_response`'s broad `except Exception` and returned as `500 reason="File not found"` (misleading). The only current call site (`client-api.ts:111`) always passes `100`, so it's latent — but any new caller using the optional signature will hit it.

**Suggested fix:**
Either guard on the TS side (`headerOnly !== undefined ? ... : ""`), or on the Python side treat non-numeric `header-only` as `None`.

---

### F70.6 — FastAPI `view_server` lacks Azure path handling that aiohttp has

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/fastapi_server.py:524-527` vs `src/inspect_ai/_view/server.py:425-434`
- **Category:** consistency / correctness

**Description:**
The aiohttp `view_server` deliberately skips `fs.info(log_dir).name` for Azure paths (with a comment "Don't call fs.info(); keep original URI") and wraps existence checks with `azure_debug_exists` / `azure_runtime_hint`. The FastAPI `view_server` unconditionally does `log_dir = fs.info(log_dir).name`.

**Why it matters / impact:**
For `az://` / `abfs://` log dirs under FastAPI (now the default per `_should_use_fastapi`), `fs.info().name` may strip the scheme or raise on auth probes — the exact failure modes the aiohttp branch was patched to avoid. Azure users who upgrade and pick up FastAPI will regress.

**Suggested fix:**
Port the `is_azure_path` branch from `server.py:425-434` into `fastapi_server.py:view_server`.

---

### F70.7 — `/log-download` bypasses Authorization header

- **Severity:** MEDIUM
- **Location:** `ts-mono/apps/inspect/src/client/api/view-server/api-view-server.ts:356-366` ↔ `src/inspect_ai/_view/fastapi_server.py:464-474`
- **Category:** correctness

**Description:**
`download_log` triggers the download by injecting an `<a href>` and clicking it. Anchor navigation cannot carry custom `Authorization` headers, but `authorization_middleware` rejects any request without the exact header value.

**Why it matters / impact:**
When `inspect view` is started with `--authorization`, the "Download log" button returns 401. (Same applies to the aiohttp `authorize` middleware.)

**Suggested fix:**
Either exempt `/api/log-download/*` from header auth and accept a signed query token, or stream via `fetch()` + `Blob` so the `headerProvider` is applied.

---

### F70.8 — `parse_log_token` raises `RuntimeError` → opaque 500

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/common.py:111-121`
- **Category:** fallback-hiding-errors / correctness

**Description:**
A malformed `If-None-Match` header raises `RuntimeError` (and `float()`/`int()` may raise `ValueError`), which neither server maps to a 4xx. Also note the order-of-operations: `log_token.find("-")` is checked **before** the `W/"…"` wrapper is stripped, so a token of `W/"bogus"` passes the `-` check (because `W/` itself contains no `-`? it doesn't — actually `W/"bogus"` has no `-` so it raises correctly; but `W/"abc"` with no dash → raises with the wrapped string in the message).

**Why it matters / impact:**
A bad client (or proxy that rewrites ETags) turns a cache-validation hint into a 500. Should degrade to "no etag → full response".

**Suggested fix:**
Wrap parsing in `try/except (ValueError, RuntimeError): return (0.0, 0)` at the call sites, or return `(0.0, 0)` on parse failure inside the helper.

---

### F70.9 — Blocking filesystem I/O inside async handlers

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/fastapi_server.py:314-316` (`read_eval_set_info`), `:337-343` (`fs.exists`/`fs.read_bytes` for flow), `:390-398` (`buffer.get_samples`), `:430-438` (`buffer.get_sample_data`); `src/inspect_ai/_view/common.py:212-214` (`delete_log`), `:454` (`size_in_mb` → sync `fs.info`), `:474-475` (`eval_log_info_async` → sync `fs.exists`/`fs.info`)
- **Category:** perf / async-correctness

**Description:**
Multiple `async def` handlers call synchronous fsspec / sqlite operations directly. `read_eval_set_info`, `fs.read_bytes`, `fs.exists`, `fs.rm`, `size_in_mb`, and `SampleBuffer.get_samples`/`get_sample_data` are all blocking.

**Why it matters / impact:**
A single slow S3/Azure round-trip in `/flow` or `/eval-set` stalls **every** concurrent request on the uvicorn event loop, including the 1 Hz `/events` poll. With several browser tabs open against a remote bucket this manifests as multi-second UI freezes.

**Suggested fix:**
Wrap sync calls in `anyio.to_thread.run_sync(...)`, or use the existing `async_connection()` / `async_filesystem()` helpers consistently.

---

### F70.10 — `log_file_response` catches all exceptions and reports "File not found"

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/server.py:483-491`
- **Category:** fallback-hiding-errors

**Description:**
```python
except Exception as error:
    logger.exception(error)
    return web.Response(status=500, reason="File not found")
```
Any error — JSON decode, permission denied, S3 throttle, the `int("undefined")` from F70.5 — is reported to the client as "File not found" with status 500 (not 404).

**Why it matters / impact:**
Misleading error surfaced in the UI; status/reason mismatch. The FastAPI equivalent (`fastapi_server.py:128-132`) only catches `FileNotFoundError` → 404, which is correct; the two implementations disagree.

**Suggested fix:**
Catch `FileNotFoundError` → 404; let everything else propagate (or return 500 with the real message).

---

### F70.11 — `_walk_without_detail` swallows all listing errors

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/common.py:521-524`
- **Category:** fallback-hiding-errors

**Description:**
```python
try:
    entries = await fs._ls(current, detail=True)
except Exception:
    continue
```
Any per-directory failure (auth, throttle, network) is silently skipped with no log line.

**Why it matters / impact:**
Users see an incomplete log list with no indication anything went wrong. Contradicts project guideline "fail fast and loud".

**Suggested fix:**
At minimum `logger.warning("Skipping %s: %s", current, ex)`; consider re-raising for non-NotFound errors.

---

### F70.12 — Dead code in `server.py`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/server.py:461-480` (`eval_set_response`), `:494-512` (`log_bytes_response`)
- **Category:** dead-code

**Description:**
`eval_set_response()` and `log_bytes_response()` are defined at module scope but never called anywhere in the repo (verified via grep). The active handlers inline equivalent logic.

**Suggested fix:**
Delete both. `log_bytes_response` in particular duplicates `get_log_bytes` and could drift.

---

### F70.13 — `_openapi.py` monkey-patches FastAPI internals without restoration

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/_openapi.py:55-59`
- **Category:** code-smell

**Description:**
`v2.GenerateJsonSchema = _CustomJsonSchemaGenerator` permanently mutates `fastapi._compat.v2` for the lifetime of the process. It also imports from a private module (`fastapi._compat`).

**Why it matters / impact:**
Only run from `schema.py` as a CLI script today, so process-global mutation is harmless in practice. But if anything else in-process generates an OpenAPI schema after this call, it inherits the patched semantics. Private-module import is brittle across FastAPI versions.

**Suggested fix:**
Save/restore the original in a `try/finally`, and add a comment pinning the FastAPI version assumption.

---

### F70.14 — Endpoints unused by the TS client

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/fastapi_server.py:134-138` (`/log-size`), `:149-154` (`/log-delete`)
- **Category:** dead-code

**Description:**
Grep of `ts-mono/apps/inspect/src/` finds no callers of `/log-size` or `/log-delete`. `/log-size` may be kept for the VS Code extension or external integrations, but `/log-delete` (see F70.4) appears entirely orphaned.

---

### F70.15 — `loaded_time` query param sent by client, ignored by server

- **Severity:** INFO
- **Location:** `ts-mono/apps/inspect/src/client/api/view-server/api-view-server.ts:45` ↔ `src/inspect_ai/_view/fastapi_server.py:369-377`, `src/inspect_ai/_view/server.py:298-306`
- **Category:** consistency / dead-code

**Description:**
The client appends `loaded_time` to every `/events` poll; neither server reads it.

**Suggested fix:**
Drop from the client, or document why it's reserved.

---

### F70.16 — aiohttp `/api/log-bytes` doesn't clamp range; FastAPI does

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/server.py:107-127` vs `src/inspect_ai/_view/fastapi_server.py:166-198`
- **Category:** consistency / correctness

**Description:**
FastAPI `api_log_bytes` fetches `file_size`, returns 416 if `start >= file_size`, and clamps `end` to `file_size - 1`. The aiohttp version passes `start`/`end` straight through to `get_log_bytes` with no validation — a request with `start > size` will return whatever `_cat_file` does (often empty bytes with a misleading `Content-Length`), and non-integer params raise an uncaught `ValueError` from `int(start_param)`.

**Suggested fix:**
Port the clamping/416 logic into the aiohttp handler, and wrap `int()` in the existing `query_param_required` helper instead of bare `int(...)`.

---

### F70.17 — `Content-Disposition` filename not sanitized

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/fastapi_server.py:213-219`, `src/inspect_ai/_view/server.py:140-147`
- **Category:** correctness

**Description:**
`filename = f"{Path(file).stem}.eval"` is interpolated directly into `Content-Disposition: attachment; filename="…"`. `file` is client-controlled (after `normalize_uri` → unquote). A filename containing `"` or CR/LF would produce a malformed header; non-ASCII filenames need RFC 5987 `filename*=` encoding.

**Why it matters / impact:**
Low — eval log filenames are machine-generated timestamps, so unlikely in practice. But it's a header-injection foot-gun if log naming ever becomes user-influenced.

**Suggested fix:**
Use `starlette`'s built-in quoting or `email.utils.quote` / `urllib.parse.quote` and emit `filename*=UTF-8''…`.

---

### F70.18 — `async_connection` cache ignores `fs_options` and pins event loop

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/common.py:334-352`
- **Category:** code-smell / correctness

**Description:**
The module-global `_async_connections` cache is keyed by protocol only. Two S3 paths needing different `fs_options` (e.g. `anon=True` vs credentialed) share one connection. The cached instance is also bound to `asyncio.get_event_loop()` at first call; if the loop is later replaced (tests, multiple `anyio.run` calls) subsequent awaits fail with "attached to a different loop". `asyncio.get_event_loop()` is also deprecated in 3.12+ when no loop is running. Finally, `return _async_connections.get(protocol)` is typed `Optional[...]` though it can never be `None` at that point.

**Suggested fix:**
Key the cache on `(protocol, frozenset(options.items()))`, use `asyncio.get_running_loop()`, and index with `[]` not `.get()`.

---

### F70.19 — `generate_direct_urls` is unreachable from the public `view()` entrypoint

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/view.py:25-81`, `src/inspect_ai/_view/fastapi_server.py:521`
- **Category:** dead-code

**Description:**
Both `view_server` functions accept `generate_direct_urls`, but `view()` (the only public/CLI entrypoint) never forwards it and `_cli/view.py` exposes no flag. The presigned-URL feature in `get_log_info` is therefore only reachable by importing `view_server` directly.

---

### F70.20 — `notify.py` writes signal file non-atomically

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/notify.py:19-34`
- **Category:** correctness

**Description:**
`view_notify_eval` opens `last-eval-result` with `"w"` and writes JSON in-place. A concurrent reader (the VS Code extension reads this file's *contents*, not just mtime) can observe a truncated/partial JSON. `view_last_eval_time()` only reads `st_mtime` so the HTTP `/events` path is unaffected.

**Suggested fix:**
Write to a temp file in the same dir and `os.replace()`.

---

### F70.21 — Mutable default arguments (`fs_options: dict = {}`)

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/common.py:88,296,381,462`; `fastapi_server.py:90,520`; `server.py:55,417`; `view.py:32`
- **Category:** code-smell

**Description:**
Shared mutable default dict across calls. None of the current bodies mutate it, so no live bug, but it's a well-known Python footgun and `ruff` (B006) would normally flag it.

---

### F70.22 — `aliased_path` leaks/mishandles non-local paths

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/common.py:481-486`
- **Category:** code-smell

**Description:**
`aliased_path` does a raw `str.startswith(os.path.expanduser("~"))`. On Windows the home dir uses `\` while incoming paths may be `/`-normalized, so aliasing silently never applies. Conversely if `~` expands to `/root` and the log dir is `/rootlogs`, the prefix matches spuriously (no separator check). Cosmetic only — affects the string shown in the UI header.

---

### F70.23 — `AccessPolicy` is a `Protocol` but `OnlyDirAccessPolicy` calls `super().__init__()`

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/fastapi_server.py:496-499`
- **Category:** code-smell

**Description:**
`AccessPolicy(Protocol)` has no `__init__`; `super().__init__()` resolves to `object.__init__` which is harmless but misleading — suggests `AccessPolicy` is a base class rather than a structural protocol.

---

### F70.24 — Duplicate `request_log_dir` resolution boilerplate (aiohttp)

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/server.py:170-178, 185-192, 204-211, 232-239, 257-264`
- **Category:** code-smell

**Description:**
The same 8-line "if authorization → allow `?log_dir` override → normalize_uri" block is copy-pasted across five handlers. The FastAPI version factors this differently but still repeats the `log_dir or default_dir` + sub_dir join in `/eval-set` and `/flow`.

**Suggested fix:**
Extract a `resolve_request_log_dir(request) -> str` helper.

---

### F70.25 — `stream_log_bytes` docstring says `end` is exclusive; implementation treats it as inclusive

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/common.py:244` vs `:274` and `get_log_bytes:220`
- **Category:** correctness / documentation

**Description:**
Docstring: "`end`: The end byte position to download to (exclusive)." But the S3 path builds `Range: bytes={start}-{end}` (inclusive per RFC 7233), and the non-S3 path delegates to `get_log_bytes` which does `end + 1` before calling `read_bytes`/`_cat_file`. Both callers (`fastapi_server.py:176-179`, `server.py:137`) pass an inclusive end. The docstring is wrong.

**Why it matters / impact:**
Off-by-one risk for any new caller who trusts the docstring.

---

## Files reviewed

- [x] `src/inspect_ai/_view/server.py` — aiohttp app; lazy-map bug, dead helpers, divergence from FastAPI
- [x] `src/inspect_ai/_view/fastapi_server.py` — FastAPI app; missing Azure handling, GET-delete, blocking I/O
- [x] `src/inspect_ai/_view/common.py` — shared helpers; large-file streaming bug, etag parsing, async cache
- [x] `src/inspect_ai/_view/view.py` — entrypoint; clean, minor unreachable-param note
- [x] `src/inspect_ai/_view/schema.py` — type-gen script; fine
- [x] `src/inspect_ai/_view/_openapi.py` — monkey-patches private FastAPI module
- [x] `src/inspect_ai/_view/_dist.py` — LFS resolver; fine
- [x] `src/inspect_ai/_view/notify.py` — non-atomic write
- [x] `src/inspect_ai/_view/azure.py` — string-match auth detection; acceptable
- [x] `src/inspect_ai/_view/fastapi_prereqs.py` — trivial; fine
- [x] `src/inspect_ai/_view/inspect-openapi.json` — skimmed; matches FastAPI routes
- [x] `ts-mono/apps/inspect/src/client/api/view-server/api-view-server.ts` — cross-referenced
- [x] `ts-mono/apps/inspect/src/client/api/view-server/request.ts` — cross-referenced

## Open questions / needs verification

- F70.2: confirm whether any deployment actually serves >50 MB local `.eval` files via `/log-download` (vs the client reading via `/log-bytes` ranges, which caps at <50 MB chunks and would dodge the bug).
- F70.6: verify `fs.info(az://...).name` actually strips the scheme on current `adlfs` — the aiohttp comment implies it does but I did not reproduce.
- F70.14: check whether the VS Code extension or `inspect_scout` calls `/log-size` or `/log-delete` before removing.
- F70.7: confirm whether any hosted deployment uses `authorization=` with the download button.
