"""Playwright harness for verifying viewer-bug repro .eval files.

Spins up ``inspect view`` against a log directory, drives a headless
Chromium at it, and exposes high-level navigation + extraction helpers
so per-finding check scripts stay tiny.

Typical use::

    from harness import ViewerSession, VerifyResult

    with ViewerSession("findings/repros/logs/01-events", port=7576) as v:
        v.goto_sample("F01.2", tab="transcript")
        v.click_event_subtab("Tools", in_event="Model Call")
        text = v.event_panel_text("Model Call")
        ...

All selectors / URL patterns here were derived from the viewer source —
see HOWTO.md in this directory for the full reference table.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import Any, Literal

from playwright.sync_api import Browser, Locator, Page, Playwright, sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[3]

# Env vars set by the AISI platform that break the local editable install /
# inspect view server. Mirror findings/repros/run.sh.
_STRIP_ENV = {
    "UV_EXCLUDE_NEWER",
    "INSPECT_TELEMETRY",
    "INSPECT_API_KEY_OVERRIDE",
    "INSPECT_REQUIRED_HOOKS",
}

# Sample-dialog tab ids (constants.ts: kSampleTabIds)
SAMPLE_TABS = {
    "transcript",
    "messages",
    "scoring",
    "metadata",
    "error",
    "retries",
    "retry-errors",
    "json",
}

# Log-level (workspace) tab ids (constants.ts: kWorkspaceTabs)
LOG_TABS = {"samples", "json", "info", "models", "task", "error"}

Verdict = Literal["CONFIRMED", "NOT_REPRODUCED", "INCONCLUSIVE", "FALSE_POSITIVE"]


@dataclass
class VerifyResult:
    """Outcome of a single finding check.

    Attributes:
        verdict: One of CONFIRMED (bug visible), NOT_REPRODUCED (bug not
            visible — viewer behaves correctly), INCONCLUSIVE (couldn't tell —
            e.g. UI element missing entirely), FALSE_POSITIVE (the *finding
            description* is wrong about what the viewer does).
        evidence: Text extracted from the page that justifies the verdict.
            Keep it short (< 500 chars) — quote the load-bearing fragment.
        notes: Free-form context: what was checked, gotchas, next steps.
        artifacts: Paths to screenshots / HTML dumps written for this check.
    """

    verdict: Verdict
    evidence: str
    notes: str = ""
    artifacts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "evidence": self.evidence,
            "notes": self.notes,
            "artifacts": self.artifacts,
        }


# ---------------------------------------------------------------------------
# ViewerSession
# ---------------------------------------------------------------------------


class ViewerSession:
    """Context manager: ``inspect view`` server + headless Chromium page.

    Args:
        log_dir: Directory of ``.eval`` files to serve. Relative paths are
            resolved against the repo root.
        port: TCP port for the view server. **Each parallel agent must use a
            distinct port** — recommended ``7575 + batch_num``.
        viewport: Browser viewport ``(width, height)``. Some bugs are
            layout-sensitive; default is a comfortable desktop size.
        startup_timeout_s: How long to poll for the server before giving up.
    """

    def __init__(
        self,
        log_dir: str | Path,
        port: int = 7575,
        *,
        viewport: tuple[int, int] = (1400, 1000),
        startup_timeout_s: float = 30.0,
    ) -> None:
        log_dir_path = Path(log_dir)
        if not log_dir_path.is_absolute():
            log_dir_path = REPO_ROOT / log_dir_path
        self.log_dir: Path = log_dir_path.resolve()
        if not self.log_dir.is_dir():
            raise FileNotFoundError(f"log_dir does not exist: {self.log_dir}")
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"
        self._viewport = viewport
        self._startup_timeout_s = startup_timeout_s

        self._proc: subprocess.Popen[bytes] | None = None
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None
        self._current_log: str | None = None

    # -- lifecycle ---------------------------------------------------------

    def __enter__(self) -> "ViewerSession":
        self._start_server()
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        self._page = self._browser.new_page(
            viewport={"width": self._viewport[0], "height": self._viewport[1]}
        )
        # Generous default — virtualised lists can be slow on first load.
        self._page.set_default_timeout(15_000)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        for closer in (
            lambda: self._browser and self._browser.close(),
            lambda: self._pw and self._pw.stop(),
            self._stop_server,
        ):
            try:
                closer()
            except Exception:
                pass

    @property
    def page(self) -> Page:
        """Raw Playwright ``Page`` for custom interactions the helpers don't cover."""
        assert self._page is not None, "ViewerSession not entered"
        return self._page

    # -- server management -------------------------------------------------

    def _start_server(self) -> None:
        env = {k: v for k, v in os.environ.items() if k not in _STRIP_ENV}
        self._proc = subprocess.Popen(
            [
                "uv",
                "run",
                "--frozen",
                "inspect",
                "view",
                "--log-dir",
                str(self.log_dir),
                "--port",
                str(self.port),
                "--host",
                "127.0.0.1",
            ],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        deadline = time.monotonic() + self._startup_timeout_s
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                out = (
                    self._proc.stdout.read().decode(errors="replace")
                    if self._proc.stdout
                    else ""
                )
                raise RuntimeError(
                    f"`inspect view` exited (code={self._proc.returncode}) before serving:\n{out}"
                )
            try:
                urllib.request.urlopen(f"{self.base_url}/", timeout=1)
                return
            except Exception:
                time.sleep(0.3)
        self._stop_server()
        raise RuntimeError(f"`inspect view` did not become ready on port {self.port}")

    def _stop_server(self) -> None:
        proc = self._proc
        if proc is None:
            return
        self._proc = None
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=5)
        except Exception:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                pass

    # -- log-file resolution ----------------------------------------------

    def find_log(self, pattern: str) -> str:
        """Resolve a finding id / glob fragment to a single log filename.

        ``find_log("F01.2")`` → ``"2026-04-24T...F01.2-...eval"``.
        Raises if zero or >1 match (ambiguity is a check-script bug).
        """
        matches = sorted(
            p.name for p in self.log_dir.glob("*.eval") if pattern in p.name
        )
        if len(matches) == 0:
            raise FileNotFoundError(f"No .eval in {self.log_dir} matches {pattern!r}")
        if len(matches) > 1:
            raise ValueError(
                f"{len(matches)} .eval files match {pattern!r}: {matches}. "
                "Use a longer pattern."
            )
        return matches[0]

    # -- navigation --------------------------------------------------------

    def goto(self, hash_path: str, *, settle: bool = True) -> None:
        """Navigate to ``{base_url}/#{hash_path}`` and wait for the app to settle."""
        url = f"{self.base_url}/#{hash_path.lstrip('#')}"
        self.page.goto(url, wait_until="domcontentloaded")
        if settle:
            self.wait_settled()

    def goto_log(self, log: str, tab: str | None = None) -> None:
        """Navigate to a log's top-level view.

        Args:
            log: Filename or finding-id fragment (resolved via :meth:`find_log`).
            tab: One of :data:`LOG_TABS` (``samples`` / ``info`` / ``json`` …).
        """
        fname = log if log.endswith(".eval") else self.find_log(log)
        self._current_log = fname
        path = f"/logs/{self._enc(fname)}"
        if tab:
            assert tab in LOG_TABS, (
                f"unknown log tab {tab!r}; valid: {sorted(LOG_TABS)}"
            )
            path += f"/{tab}"
        self.goto(path)

    def goto_sample(
        self,
        sample_id: str | int,
        epoch: int = 1,
        *,
        log: str | None = None,
        tab: str = "transcript",
        event: str | None = None,
        message: str | None = None,
    ) -> None:
        """Deep-link to a sample tab.

        Args:
            sample_id: Sample id as recorded in the log (the repro convention
                is the finding id, e.g. ``"F01.2"``).
            epoch: Sample epoch (default 1).
            log: Filename / fragment. Defaults to the last log navigated to,
                or — if ``sample_id`` looks like a finding id — that finding's
                log.
            tab: One of :data:`SAMPLE_TABS`.
            event: Event-node uuid → opens the Transcript tab scrolled to and
                expanding that event (``?event=<uuid>``).
            message: Message id → opens the Messages tab scrolled to that
                message (``?message=<id>``).
        """
        assert tab in SAMPLE_TABS, (
            f"unknown sample tab {tab!r}; valid: {sorted(SAMPLE_TABS)}"
        )
        if log is None:
            log = self._current_log or (
                self.find_log(str(sample_id)) if isinstance(sample_id, str) else None
            )
            if log is None:
                raise ValueError("goto_sample: pass log=, or call goto_log() first")
        fname = log if log.endswith(".eval") else self.find_log(log)
        self._current_log = fname

        sid = urllib.parse.quote(str(sample_id), safe="")
        path = f"/logs/{self._enc(fname)}/samples/sample/{sid}/{epoch}/{tab}"
        if event:
            path += f"?event={event}"
        elif message:
            path += f"?message={message}"
        self.goto(path)

    def click_tab(self, tab_name: str) -> None:
        """Click a sample-level tab (Transcript / Messages / Scoring / Metadata / JSON).

        Prefer ``goto_sample(tab=...)`` for deep-linking; use this only when
        the bug is *about* tab-click behaviour.
        """
        # Sample-tab buttons have id == tab id (e.g. id="transcript").
        tab_id = tab_name.lower().replace(" ", "-")
        btn = self.page.locator(f'button[role="tab"]#{tab_id}')
        if btn.count() == 0:
            # Fall back to text match (workspace tabs / unknown).
            btn = self.page.get_by_role("tab", name=tab_name, exact=True)
        btn.first.click()
        self.wait_settled()

    # -- transcript-event helpers -----------------------------------------

    def event_panel(self, title_contains: str, *, nth: int = 0) -> Locator:
        """Locate a transcript event panel by its visible title.

        ``event_panel("Model Call")`` → the first ``#event-panel-*`` whose
        text contains ``Model Call`` (case-insensitive).
        """
        loc = self.page.locator('[id^="event-panel-"]').filter(has_text=title_contains)
        if loc.count() == 0:
            # Titles are uppercased via CSS text-transform; inner_text reports
            # the transformed text. Try uppercase too.
            loc = self.page.locator('[id^="event-panel-"]').filter(
                has_text=title_contains.upper()
            )
        return loc.nth(nth)

    def event_panel_text(self, title_contains: str, *, nth: int = 0) -> str:
        return self.event_panel(title_contains, nth=nth).inner_text()

    def event_subtabs(self, title_contains: str, *, nth: int = 0) -> list[str]:
        """List sub-tab titles in an event panel's pill nav.

        e.g. ``["Summary", "All", "Tools", "API"]``. Returns ``[]`` if the
        panel has no nav (single-child events don't render one).
        """
        panel = self.event_panel(title_contains, nth=nth)
        return panel.locator('button[role="tab"]').all_inner_texts()

    def click_event_subtab(self, subtab: str, *, in_event: str, nth: int = 0) -> None:
        """Click a sub-tab pill (Summary / All / Tools / API / …) inside an event panel."""
        panel = self.event_panel(in_event, nth=nth)
        # CSS text-transform:uppercase means rendered text is upper; the
        # accessible name remains the source text, so try both.
        btn = panel.get_by_role("tab", name=subtab)
        if btn.count() == 0:
            btn = panel.get_by_role("tab", name=subtab.upper())
        btn.first.click()
        self.wait_settled(network_idle=False)

    def expand_event(self, title_contains: str, *, nth: int = 0) -> None:
        """Click an event panel's collapse chevron to expand it (if collapsed)."""
        panel = self.event_panel(title_contains, nth=nth)
        chevron = panel.locator("i.bi-chevron-right").first
        if chevron.count() and chevron.is_visible():
            chevron.click()
            self.wait_settled(network_idle=False)

    def collapse_event(self, title_contains: str, *, nth: int = 0) -> None:
        panel = self.event_panel(title_contains, nth=nth)
        chevron = panel.locator("i.bi-chevron-down").first
        if chevron.count() and chevron.is_visible():
            chevron.click()
            self.wait_settled(network_idle=False)

    # -- extraction --------------------------------------------------------

    def text_of(self, selector: str) -> str:
        """``inner_text`` of the first element matching a CSS selector."""
        return self.page.locator(selector).first.inner_text()

    def html_of(self, selector: str) -> str:
        """``outerHTML`` of the first element matching a CSS selector."""
        return self.page.locator(selector).first.evaluate("el => el.outerHTML")

    def all_text(self) -> str:
        """Full visible text of ``<body>`` — for grep-style "is X anywhere?" checks."""
        return self.page.locator("body").inner_text()

    def a11y_of(self, selector: str | None = None) -> dict[str, Any]:
        """Accessibility-tree snapshot, optionally scoped to a selector.

        Prefer :meth:`text_of` — the a11y tree is large and noisy. Use this
        only when role / state matters (checked, expanded, selected, …).
        """
        root = self.page.locator(selector).first.element_handle() if selector else None
        snap = self.page.accessibility.snapshot(root=root, interesting_only=True)
        return snap or {}

    def screenshot(self, path: str | Path, selector: str | None = None) -> str:
        """Write a PNG screenshot of the page (or a selector) and return its path."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if selector:
            self.page.locator(selector).first.screenshot(path=str(path))
        else:
            self.page.screenshot(path=str(path), full_page=True)
        return str(path)

    def dump_html(self, path: str | Path, selector: str = "body") -> str:
        """Write the outerHTML of ``selector`` to ``path`` for offline triage."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.html_of(selector), encoding="utf-8")
        return str(path)

    # -- waiting -----------------------------------------------------------

    def wait_settled(self, *, network_idle: bool = True, ms: int = 250) -> None:
        """Wait for the SPA to settle.

        ``networkidle`` covers the API fetches the router triggers on
        navigation; the trailing ``wait_for_timeout`` lets React commit and
        the virtualised list measure itself.
        """
        if network_idle:
            try:
                self.page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:
                pass
        self.page.wait_for_timeout(ms)

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _enc(segment: str) -> str:
        # The viewer's encodePathParts() URI-encodes each /-separated segment.
        # For a bare filename that's equivalent to quote().
        return urllib.parse.quote(segment, safe="")


# ---------------------------------------------------------------------------
# Per-batch port allocation helper
# ---------------------------------------------------------------------------

_BATCH_PORTS: dict[str, int] = {
    "01-events": 7576,
    "02-transform": 7577,
    "10-chat": 7578,
    "11-tools": 7579,
    "20-samples": 7580,
    "30-loglist": 7581,
    "40-content": 7582,
    "90-cross": 7583,
    "example": 7584,
}


def port_for_batch(batch: str) -> int:
    """Stable port for a batch dir so parallel agents don't collide.

    Unknown batches hash into 7590–7599.
    """
    return _BATCH_PORTS.get(batch, 7590 + (abs(hash(batch)) % 10))


__all__ = [
    "ViewerSession",
    "VerifyResult",
    "Verdict",
    "SAMPLE_TABS",
    "LOG_TABS",
    "port_for_batch",
    "REPO_ROOT",
]


if __name__ == "__main__":
    # Quick self-test: open the example log's transcript tab and print it.
    with ViewerSession("findings/repros/logs/example", port=7599) as v:
        v.goto_sample("F01.3", tab="transcript")
        print(
            json.dumps(
                {
                    "tabs": v.page.locator('button[role="tab"]').all_inner_texts(),
                    "panels": v.page.locator('[id^="event-panel-"]').count(),
                },
                indent=2,
            )
        )
