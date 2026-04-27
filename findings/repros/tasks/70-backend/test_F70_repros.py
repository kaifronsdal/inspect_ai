"""Pytest reproductions for findings/70-python-view-backend.md.

These exercise Python server code paths that cannot be demonstrated via a
static ``.eval`` file. Each test asserts the *correct* behaviour, so a
**FAIL** confirms the bug is present and a **PASS** indicates a false
positive (or that the bug has since been fixed).

Run with::

    uv run pytest findings/repros/tasks/70-backend/test_F70_repros.py -v

These tests are intentionally synchronous (own their event loops) so they do
not depend on ``tests/conftest.py``'s anyio collection hook, which is not
visible from the ``findings/`` tree.
"""

from __future__ import annotations

import asyncio
import urllib.parse
from io import BytesIO
from pathlib import Path

import pytest

# ───────────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────────


def _write_minimal_eval_log(path: Path) -> str:
    """Write the smallest valid ``.eval`` log to *path* and return its str path."""
    import inspect_ai.log

    eval_log = inspect_ai.log.EvalLog(
        eval=inspect_ai.log.EvalSpec(
            created="2025-01-01T00:00:00Z",
            task="secret-task",
            task_id="secret-task-id",
            dataset=inspect_ai.log.EvalDataset(),
            model="model",
            config=inspect_ai.log.EvalConfig(),
        )
    )
    inspect_ai.log.write_eval_log(eval_log, str(path), "eval")
    return str(path)


class _AiohttpViewClient:
    """Minimal sync wrapper around an aiohttp ``view_server_app`` for testing.

    Owns its own event loop so the test functions can stay ``def`` (not
    ``async def``) and remain independent of the project conftest.
    """

    def __init__(self, log_dir: str) -> None:
        from aiohttp.test_utils import TestClient as AioTestClient
        from aiohttp.test_utils import TestServer

        from inspect_ai._view.server import view_server_app

        self._loop = asyncio.new_event_loop()
        app = view_server_app(log_dir=log_dir)

        async def _start() -> None:
            self._server = TestServer(app)
            self._client = AioTestClient(self._server)
            await self._client.start_server()

        self._loop.run_until_complete(_start())

    def get(self, path: str) -> tuple[int, bytes]:
        async def _do() -> tuple[int, bytes]:
            resp = await self._client.request("GET", path)
            body = await resp.read()
            return resp.status, body

        return self._loop.run_until_complete(_do())

    def close(self) -> None:
        self._loop.run_until_complete(self._client.close())
        self._loop.close()


# ───────────────────────────────────────────────────────────────────────────
# F70.1 — lazy map() skips path validation on /api/log-headers (aiohttp)
# ───────────────────────────────────────────────────────────────────────────


def test_F70_1_log_headers_validates_paths(tmp_path: Path) -> None:
    """F70.1 — ``map()`` is lazy: log-header path validation never runs.

    File: ``src/inspect_ai/_view/server.py:295``

    The handler does ``map(validate_log_file_request, files)`` and discards
    the iterator, so ``validate_log_file_request`` is never called for any
    requested file.

    Correct behaviour: requesting a header for a file **outside** the
    configured ``log_dir`` (with no ``authorization`` token) must be rejected
    with 401, exactly as the single-file endpoints (``/api/logs/{log}``,
    ``/api/log-size/{log}``, …) do.

    Buggy behaviour: the request succeeds (200) and returns the parsed header
    of an arbitrary on-disk eval file.
    """
    allowed = tmp_path / "allowed"
    forbidden = tmp_path / "forbidden"
    allowed.mkdir()
    forbidden.mkdir()

    # A real eval file *outside* log_dir — if validation is skipped the
    # server will happily read and return its header.
    secret = _write_minimal_eval_log(forbidden / "secret.eval")

    client = _AiohttpViewClient(log_dir=str(allowed))
    try:
        encoded = urllib.parse.quote(secret, safe="")
        status, body = client.get(f"/api/log-headers?file={encoded}")
    finally:
        client.close()

    # Correct: 401 Unauthorized (file is outside log_dir).
    # Bug: 200 OK with the secret task header in the body.
    assert status == 401, (
        f"/api/log-headers served a file outside log_dir "
        f"(status={status}, body contains task name: "
        f"{'secret-task' in body.decode(errors='replace')!r})"
    )


# ───────────────────────────────────────────────────────────────────────────
# F70.2 — stream_log_bytes raises for large non-S3 files
# ───────────────────────────────────────────────────────────────────────────


def test_F70_2_stream_log_bytes_large_local_file(tmp_path: Path) -> None:
    """F70.2 — ``stream_log_bytes`` raises ``ValueError`` for large non-S3 files.

    File: ``src/inspect_ai/_view/common.py:251-269``

    When the backing filesystem is **not** S3 and the requested byte range
    exceeds ``stream_threshold_bytes`` (50 MiB in production), control falls
    through the early-return guard into the S3-only streaming branch, which
    then asserts ``isinstance(connection, S3FileSystem)`` and raises.

    Correct behaviour: a local file of any size is returned (e.g. as a
    ``BytesIO``). The threshold is an *optimisation* gate for S3 streaming,
    not a hard size limit for local files.

    We use a tiny ``stream_threshold_bytes`` so the test does not need to
    create a 50 MiB file on disk — the control-flow bug is identical.
    """
    from inspect_ai._view import common as view_common

    payload = b"x" * 1024
    log_file = tmp_path / "big.eval"
    log_file.write_bytes(payload)

    # Avoid leaking a stale cached "file" connection (bound to a closed loop
    # from another test in this module — see also F70.18).
    view_common._async_connections.clear()

    async def _call() -> object:
        return await view_common.stream_log_bytes(
            str(log_file),
            log_file_size=len(payload),
            stream_threshold_bytes=128,  # << len(payload) → forces "large file" path
        )

    try:
        result = asyncio.run(_call())
    except Exception as ex:  # noqa: BLE001 — we want the assertion message
        pytest.fail(
            f"stream_log_bytes raised {type(ex).__name__}({ex!r}) for a local "
            f"file larger than stream_threshold_bytes; non-S3 backends must "
            f"not fall through to the S3-only streaming branch."
        )

    # If we got here the function returned — sanity-check the bytes.
    assert isinstance(result, BytesIO)
    assert result.read() == payload


# ───────────────────────────────────────────────────────────────────────────
# F70.3 — startswith() path-prefix check matches sibling directories
# ───────────────────────────────────────────────────────────────────────────


def test_F70_3_path_prefix_rejects_sibling_dir_fastapi() -> None:
    """F70.3 — Path-prefix authorization is bypassable via sibling-directory prefix.

    File: ``src/inspect_ai/_view/fastapi_server.py:501-502``

    ``OnlyDirAccessPolicy._validate_log_dir`` uses a bare
    ``file.startswith(self.dir)`` string check. With ``dir="/tmp/logs"`` a
    request for ``/tmp/logs-private/x.eval`` passes because
    ``"/tmp/logs-private".startswith("/tmp/logs")`` is ``True``.

    Correct behaviour: a path in a *sibling* directory whose name shares a
    prefix with ``log_dir`` must be rejected.
    """
    from inspect_ai._view.fastapi_server import OnlyDirAccessPolicy

    policy = OnlyDirAccessPolicy("/tmp/logs")

    # Sanity: a file genuinely under the dir is allowed.
    assert policy._validate_log_dir("/tmp/logs/run.eval") is True

    # Bug: sibling dir sharing the string prefix is incorrectly allowed.
    assert policy._validate_log_dir("/tmp/logs-private/x.eval") is False, (
        "OnlyDirAccessPolicy allowed a file in sibling directory "
        "'/tmp/logs-private' when configured for '/tmp/logs' "
        "(bare str.startswith without trailing separator)"
    )


def test_F70_3_path_prefix_rejects_sibling_dir_aiohttp(tmp_path: Path) -> None:
    """F70.3 — same sibling-prefix bypass on the aiohttp server.

    File: ``src/inspect_ai/_view/server.py:69-71``

    ``validate_log_file_request`` is a closure inside ``view_server_app`` so
    it cannot be unit-tested directly; instead we exercise it through the
    ``/api/log-size/{log}`` endpoint (which *does* call it eagerly, unlike
    F70.1's ``/api/log-headers``).

    Correct behaviour: 401 Unauthorized for a file under
    ``{log_dir}-private/``.
    """
    log_dir = tmp_path / "logs"
    sibling = tmp_path / "logs-private"
    log_dir.mkdir()
    sibling.mkdir()
    secret = _write_minimal_eval_log(sibling / "x.eval")

    client = _AiohttpViewClient(log_dir=str(log_dir))
    try:
        encoded = urllib.parse.quote(secret, safe="")
        status, _ = client.get(f"/api/log-size/{encoded}")
    finally:
        client.close()

    assert status == 401, (
        f"aiohttp validate_log_file_request allowed sibling dir "
        f"'{sibling}' when log_dir='{log_dir}' (got status {status})"
    )


# ───────────────────────────────────────────────────────────────────────────
# F70.4 — destructive delete exposed via HTTP GET
# ───────────────────────────────────────────────────────────────────────────


def test_F70_4_log_delete_is_not_GET_fastapi() -> None:
    """F70.4 — ``/log-delete/{log}`` is registered as HTTP **GET**.

    File: ``src/inspect_ai/_view/fastapi_server.py:149-154``

    A destructive operation (``fs.rm``) must not be reachable via GET: GET is
    defined as safe/idempotent, and exposing deletion on it makes the
    endpoint vulnerable to link prefetch / ``<img src=…>`` CSRF.

    Correct behaviour: the delete route is registered under ``DELETE`` (or at
    least ``POST``), never ``GET``.
    """
    from inspect_ai._view.fastapi_server import view_server_app

    app = view_server_app(default_dir="/tmp")

    delete_routes = [
        r
        for r in app.routes
        if getattr(r, "path", None) == "/log-delete/{log}"
        or "log-delete" in getattr(r, "path", "")
    ]
    assert delete_routes, "could not locate /log-delete route on FastAPI app"

    methods = set().union(*(r.methods for r in delete_routes))
    assert "GET" not in methods, (
        f"FastAPI /log-delete is registered with methods {sorted(methods)}; "
        f"destructive endpoints must not be GET"
    )


def test_F70_4_log_delete_is_not_GET_aiohttp(tmp_path: Path) -> None:
    """F70.4 — ``/api/log-delete/{log}`` is registered as HTTP **GET** (aiohttp).

    File: ``src/inspect_ai/_view/server.py:97-105``

    Same finding as the FastAPI variant, verified by route introspection on
    the aiohttp ``UrlDispatcher``.
    """
    from inspect_ai._view.server import view_server_app

    app = view_server_app(log_dir=str(tmp_path))

    delete_methods = {
        route.method
        for route in app.router.routes()
        if "log-delete" in route.resource.canonical
    }
    assert delete_methods, "could not locate /api/log-delete route on aiohttp app"
    assert "GET" not in delete_methods, (
        f"aiohttp /api/log-delete is registered with methods "
        f"{sorted(delete_methods)}; destructive endpoints must not be GET"
    )
