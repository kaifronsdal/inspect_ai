r"""Repro for F31.13 — Start/End/Duration show epoch-0 dates when stats missing.

``TaskTab.tsx:107-110,135-145`` reads timing as
``new Date(evalStats?.started_at || 0)`` — so an empty/missing
``stats.started_at`` falls back to ``new Date(0)`` → **Jan 1, 1970**.

Earlier analysis noted ``started_at`` is unconditionally set by the recorder
on a *completed* eval, so this can't be triggered by a normal ``@task``. But
the schema declares ``started_at: string | ""`` (and an interrupted/streamed
log can lack ``stats`` entirely), so the *viewer-side* fallback is the bug
under test. This script:

1. Runs a tiny mockllm eval to get a clean base ``.eval``.
2. Rewrites ``header.json`` so ``stats.started_at = ""`` and
   ``stats.completed_at = ""`` (the schema-permitted empty value).
3. Writes the result to ``findings/repros/logs/30-loglist/`` under a fixed
   filename (idempotent).

Run::

    cd /home/ubuntu/GitHub/inspect_ai
    env -u UV_EXCLUDE_NEWER -u INSPECT_TELEMETRY -u INSPECT_API_KEY_OVERRIDE -u INSPECT_REQUIRED_HOOKS \\
      uv run --frozen python findings/repros/tasks/30-loglist/F31.13_missing_started_at.py

What to look for in ``inspect view``: open the log → **Task** tab →
**Task Info** card → right-hand timing grid. **Start** and **End** read
something like ``Jan 1, 1970, 12:00:00 AM`` (locale-dependent); **Duration**
reads ``0 sec``. If instead the rows are *omitted* or show the real run time
(falling back to ``eval.created`` or similar), this finding is a
FALSE_POSITIVE.
"""

from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description  # noqa: E402

# Importing this monkey-patches ``zipfile`` to handle ZIP_ZSTANDARD (method 93).
from inspect_ai._util.zipfile import zipfile_compress_kwargs  # noqa: E402

LOG_DIR = REPO_ROOT / "findings" / "repros" / "logs" / "30-loglist"
OUT_NAME = "F31.13-missing-started-at.eval"

DESC = bug_description(
    finding_id="F31.13",
    title="Task tab shows `Jan 1, 1970` Start/End when `stats.started_at` is empty",
    where_to_look=(
        "Close this sample → click the log-level **Task** tab → **Task Info** "
        "card → right-hand grid (Start / End / Duration)."
    ),
    observed=(
        "**Start** and **End** render as the Unix epoch — e.g. "
        "`Jan 1, 1970, 12:00:00 AM` (or your locale's equivalent of "
        "`1970-01-01T00:00:00Z`); **Duration** is `0 sec`. The viewer is "
        "displaying `new Date(0)` because `header.json → stats.started_at` "
        'is `""` in this (post-processed) log.'
    ),
    expected=(
        "Either omit the Start/End/Duration rows entirely when "
        "`evalStats?.started_at` is falsy, or fall back to `eval.created`. "
        "Showing 1970 is misleading data."
    ),
    extra=(
        "This log was **post-processed** — `stats.started_at` / "
        '`stats.completed_at` were overwritten with `""` (which the schema '
        "explicitly permits) by "
        "`findings/repros/tasks/30-loglist/F31.13_missing_started_at.py`. "
        "A normally-completed eval always sets these, so the bug only "
        "surfaces for running/interrupted/hand-edited logs.\n\n"
        "If the Task tab does **not** show 1970, mark this finding "
        "FALSE_POSITIVE — there is a fallback we missed."
    ),
)


def _base_task():
    from inspect_ai import Task
    from inspect_ai.dataset import Sample
    from inspect_ai.log import transcript
    from inspect_ai.solver import Generate, Solver, TaskState, solver

    @solver
    def trivial() -> Solver:
        async def solve(state: TaskState, generate: Generate) -> TaskState:
            transcript().info(DESC, source="bug-repro")
            return await generate(state)

        return solve

    return Task(
        name="F31.13_missing_started_at",
        dataset=[Sample(id="F31.13", input=DESC, target="n/a")],
        solver=trivial(),
    )


def _generate_base_eval(tmp_dir: Path) -> Path:
    from inspect_ai import eval as inspect_eval

    logs = inspect_eval(
        _base_task(),
        model="mockllm/model",
        log_dir=str(tmp_dir),
        log_format="eval",
        display="none",
    )
    src = Path(logs[0].location)
    if not src.exists():
        raise RuntimeError(f"eval() reported {src} but it does not exist")
    return src


def _null_started_at(src: Path, dst: Path) -> None:
    """Copy ``src`` zip → ``dst``, rewriting header.json so stats timestamps are empty."""
    with zipfile.ZipFile(src, "r") as zin:
        members = zin.namelist()
        payloads: dict[str, bytes] = {m: zin.read(m) for m in members}

    header = json.loads(payloads["header.json"])
    if "stats" not in header:
        raise RuntimeError("base eval header has no 'stats' — schema changed?")
    # Schema is `string | ""` so empty-string is the canonical falsy value;
    # `|| 0` in TaskTab.tsx treats it identically to undefined.
    header["stats"]["started_at"] = ""
    header["stats"]["completed_at"] = ""
    payloads["header.json"] = json.dumps(header).encode("utf-8")

    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    with zipfile.ZipFile(dst, "w", **zipfile_compress_kwargs) as zout:
        for member in members:
            zout.writestr(member, payloads[member])


def main() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    for stale in LOG_DIR.glob("*F31.13*"):
        stale.unlink()

    with tempfile.TemporaryDirectory(prefix="f31_13_base_") as tmp:
        base = _generate_base_eval(Path(tmp))
        out = LOG_DIR / OUT_NAME
        _null_started_at(base, out)

    print(f"wrote {out}")
    print("verify: open in `inspect view` → Task tab → check Start/End for 1970")


if __name__ == "__main__":
    main()
