# 70-backend — Python view-server bug reproductions

Pytest reproductions for the Python backend findings in
[`findings/70-python-view-backend.md`](../../../70-python-view-backend.md)
that **cannot** be demonstrated via a static `.eval` file because they live
in HTTP-handler / helper code paths.

Each test asserts the *correct* behaviour, so:

- **FAIL** ⇒ bug confirmed (the assertion describes the observed wrong behaviour)
- **PASS** ⇒ false positive, or bug has since been fixed

## Run

```bash
uv run python -m pytest findings/repros/tasks/70-backend/test_F70_repros.py -v
```

> Use `python -m pytest` (not bare `pytest`) so the project venv — and
> therefore the in-tree `inspect_ai` package — is on `sys.path`.

The tests are synchronous (each owns its own event loop) so they run from
the `findings/` tree without needing `tests/conftest.py`'s anyio hook.

## Status (as of 2026-04-27, `main` @ 56516cce7)

| Test | Finding | Result | Observed |
|---|---|---|---|
| `test_F70_1_log_headers_validates_paths` | [F70.1](../../../70-python-view-backend.md#f701--map-is-lazy-log-header-path-validation-never-runs-aiohttp) | **FAIL → confirmed** | `GET /api/log-headers?file=<outside-log_dir>` returns **200** with the parsed header (`secret-task` leaked in body); expected **401**. |
| `test_F70_2_stream_log_bytes_large_local_file` | [F70.2](../../../70-python-view-backend.md#f702--stream_log_bytes-raises-valueerror-for-large-non-s3-files) | **FAIL → confirmed** | `stream_log_bytes()` on a local file with `request_size > stream_threshold_bytes` raises `ValueError('Expected S3FileSystem')`. |
| `test_F70_3_path_prefix_rejects_sibling_dir_fastapi` | [F70.3](../../../70-python-view-backend.md#f703--path-prefix-authorization-is-bypassable-via-sibling-directory-prefix) | **FAIL → confirmed** | `OnlyDirAccessPolicy("/tmp/logs")._validate_log_dir("/tmp/logs-private/x.eval")` returns `True`. |
| `test_F70_3_path_prefix_rejects_sibling_dir_aiohttp` | F70.3 | **FAIL → confirmed** | `GET /api/log-size/<logs-private/x.eval>` with `log_dir=…/logs` returns **200**; expected **401**. |
| `test_F70_4_log_delete_is_not_GET_fastapi` | [F70.4](../../../70-python-view-backend.md#f704--destructive-delete-exposed-via-http-get) | **FAIL → confirmed** | FastAPI `/log-delete/{log}` route methods = `{'GET'}`. |
| `test_F70_4_log_delete_is_not_GET_aiohttp` | F70.4 | **FAIL → confirmed** | aiohttp `/api/log-delete/{log}` route methods = `{'GET', 'HEAD'}`. |

**6 / 6 fail — all four findings confirmed, no false positives.**

## What each test does

### F70.1 — `server.py:295`
Stands up the aiohttp `view_server_app` (no `authorization` token) with
`log_dir=<tmp>/allowed`, writes a real `.eval` file to `<tmp>/forbidden`,
then requests it via `/api/log-headers?file=…`. Because
`map(validate_log_file_request, files)` is a lazy iterator that is never
consumed, the handler reads and returns the forbidden file's header.

### F70.2 — `common.py:251-269`
Calls `stream_log_bytes()` on a 1 KiB local file with
`stream_threshold_bytes=128` (functionally equivalent to a >50 MiB file with
the production 50 MiB threshold). The non-S3 branch falls through past the
`request_size <= threshold` early return into the S3-only streaming code,
which raises `ValueError("Expected S3FileSystem")`.

### F70.3 — `fastapi_server.py:501-502` / `server.py:69-71`
Two variants:
- **fastapi**: direct unit test of `OnlyDirAccessPolicy._validate_log_dir`.
- **aiohttp**: end-to-end via `/api/log-size/{log}` (which *does* call
  `validate_log_file_request` eagerly), with `log_dir=…/logs` and a target
  in sibling `…/logs-private`.

Both demonstrate that bare `str.startswith` without a trailing separator
treats `/a/logs-private` as inside `/a/logs`.

### F70.4 — `fastapi_server.py:149-154` / `server.py:97-105`
Pure route-table introspection on each app factory: locates the
`log-delete` route and asserts `"GET"` is not among its methods. It is.

## When a fix lands

Once a finding is fixed in `src/`, the corresponding test will flip to
**PASS**. At that point either delete the test or move it (with the
docstring trimmed) into `tests/_view/test_view_server.py` as a regression
guard.
