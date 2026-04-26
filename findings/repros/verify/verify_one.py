#!/usr/bin/env python3
"""Run a single finding's browser-based verification check.

Usage::

    cd /home/ubuntu/GitHub/inspect_ai
    uv run --with playwright python findings/repros/verify/verify_one.py F01.2
    uv run --with playwright python findings/repros/verify/verify_one.py F01.2 F04.2 F40.1
    uv run --with playwright python findings/repros/verify/verify_one.py --batch 01-events

Each finding ``Fxx.y`` is checked by ``checks/Fxx_y.py`` which must export::

    BATCH: str                                  # log subdir, e.g. "01-events"
    def check(session: ViewerSession) -> VerifyResult: ...

``check()`` receives an already-started :class:`ViewerSession` pointing at
``findings/repros/logs/<BATCH>/`` and is responsible for navigating to the
right place and returning a verdict. The runner handles server lifecycle,
port allocation, and result reporting.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import REPO_ROOT, VerifyResult, ViewerSession, port_for_batch  # noqa: E402

CHECKS_DIR = HERE / "checks"
ARTIFACTS_DIR = HERE / "artifacts"


def _module_name(finding_id: str) -> str:
    # F01.2 -> F01_2 (dots aren't valid in module names)
    return finding_id.replace(".", "_").replace("-", "_")


def load_check(finding_id: str) -> tuple[str, callable]:
    """Import ``checks/<finding_id>.py`` and return ``(BATCH, check)``."""
    mod_file = CHECKS_DIR / f"{_module_name(finding_id)}.py"
    if not mod_file.exists():
        raise FileNotFoundError(
            f"No check script for {finding_id}: expected {mod_file}\n"
            f"Available: {sorted(p.stem for p in CHECKS_DIR.glob('F*.py'))}"
        )
    spec = importlib.util.spec_from_file_location(f"checks.{mod_file.stem}", mod_file)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "BATCH") or not hasattr(mod, "check"):
        raise AttributeError(
            f"{mod_file} must define BATCH: str and check(session) -> VerifyResult"
        )
    return mod.BATCH, mod.check


def run_one(finding_id: str, *, port: int | None = None) -> VerifyResult:
    batch, check_fn = load_check(finding_id)
    log_dir = REPO_ROOT / "findings" / "repros" / "logs" / batch
    use_port = port or port_for_batch(batch)
    try:
        with ViewerSession(log_dir, port=use_port) as session:
            result = check_fn(session)
            if not isinstance(result, VerifyResult):
                raise TypeError(f"check() must return VerifyResult, got {type(result)}")
            return result
    except Exception as e:  # noqa: BLE001  — we want a verdict, not a crash
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence="",
            notes=f"check raised {type(e).__name__}: {e}\n{traceback.format_exc()}",
        )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("finding_ids", nargs="*", help="e.g. F01.2 F04.2")
    p.add_argument("--batch", help="run every check whose BATCH matches this")
    p.add_argument("--port", type=int, help="override server port")
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = p.parse_args(argv)

    finding_ids: list[str] = list(args.finding_ids)
    if args.batch:
        for f in sorted(CHECKS_DIR.glob("F*.py")):
            spec = importlib.util.spec_from_file_location(f"checks.{f.stem}", f)
            assert spec and spec.loader
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if getattr(mod, "BATCH", None) == args.batch:
                finding_ids.append(f.stem.replace("_", ".", 1))
    if not finding_ids:
        p.error("specify at least one finding_id or --batch")

    results: dict[str, dict] = {}
    exit_code = 0
    for fid in finding_ids:
        result = run_one(fid, port=args.port)
        results[fid] = result.to_dict()
        if result.verdict == "INCONCLUSIVE":
            exit_code = 1
        if not args.json:
            _print_human(fid, result)

    if args.json:
        print(json.dumps(results, indent=2))
    return exit_code


def _print_human(fid: str, r: VerifyResult) -> None:
    bar = "=" * 72
    print(f"\n{bar}\n{fid}: {r.verdict}\n{bar}")
    if r.evidence:
        print(f"evidence:\n{_indent(r.evidence)}")
    if r.notes:
        print(f"notes:\n{_indent(r.notes)}")
    if r.artifacts:
        print(f"artifacts: {r.artifacts}")


def _indent(s: str, n: int = 2) -> str:
    pad = " " * n
    return "\n".join(pad + line for line in s.splitlines())


if __name__ == "__main__":
    sys.exit(main())
