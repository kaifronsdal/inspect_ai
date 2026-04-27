r"""Repro for F02.12 — RenderedEventNode `default: return null` hides unknown event types.

This finding can't be reproduced by a plain ``@task`` because the Python
``Event`` union is closed — there is no way to emit an event whose ``.event``
discriminator is unknown to the *current* viewer build. So this script:

1. Runs a tiny mockllm eval to produce a clean base ``.eval``.
2. Cracks the zip open, injects three things into sample 1's event list:
   - an ``info`` event carrying the bug-description banner,
   - a *known* ``logger`` event placed immediately before the unknown one
     (so you can see exactly where the gap is),
   - a synthetic event with ``"event": "F02_12_unknown_type"``.
3. Writes the result to ``findings/repros/logs/02-transform/`` under a fixed
   filename (idempotent — re-running overwrites it).

Run::

    cd /home/ubuntu/GitHub/inspect_ai
    env -u UV_EXCLUDE_NEWER -u INSPECT_TELEMETRY -u INSPECT_API_KEY_OVERRIDE -u INSPECT_REQUIRED_HOOKS \\
      uv run --frozen python findings/repros/tasks/02-transform/F02.12_unknown_event_type.py

What to look for in ``inspect view``: open the sample → Transcript tab →
switch the **Events** filter to **Debug**. You will see the
``LOGGER`` marker event ("⬇ unknown event injected immediately after this")
followed by … nothing. The ``F02_12_unknown_type`` event that sits right
after it in ``samples/F02.12_epoch_1.json`` is silently dropped by the
``default: return null`` arm of ``RenderedEventNode``
(``transcript/TranscriptVirtualList.tsx:248``). No console error, no
"unknown event" placeholder.
"""

from __future__ import annotations

import json
import sys
import tempfile
import uuid as _uuid
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(Path(__file__).parents[2]))
from _common import bug_description  # noqa: E402

# Importing this monkey-patches ``zipfile`` to handle ZIP_ZSTANDARD (method 93),
# which is what the .eval recorder uses.
from inspect_ai._util.zipfile import zipfile_compress_kwargs  # noqa: E402

LOG_DIR = REPO_ROOT / "findings" / "repros" / "logs" / "02-transform"
OUT_NAME = "F02.12-unknown-event-type.eval"

DESC = bug_description(
    finding_id="F02.12",
    title="`RenderedEventNode` `default: return null` silently hides unknown event types",
    where_to_look=(
        "Transcript tab → switch the **Events** filter to **Debug** (funnel "
        "button top-right). Find the **LOGGER** event whose message reads "
        "`⬇ unknown event injected immediately after this`. The very next "
        'event in the underlying JSON has `"event": "F02_12_unknown_type"` '
        "— but nothing renders between the LOGGER marker and the panel that "
        "follows it."
    ),
    observed=(
        "The `F02_12_unknown_type` event renders as **nothing** — no panel, "
        "no placeholder, no console warning. Open the sample-level **JSON** "
        "tab and search for `F02_12_unknown_type` to confirm the event is "
        "present in the log; it just falls through "
        "`RenderedEventNode → default: return null` "
        "(`TranscriptVirtualList.tsx:248`)."
    ),
    expected=(
        'Either a visible "Unknown event type: F02_12_unknown_type" '
        "placeholder panel, or a compile-time `satisfies never` exhaustiveness "
        "check that makes the omission impossible."
    ),
    extra=(
        "This log was **post-processed** — the unknown event was injected by "
        "`findings/repros/tasks/02-transform/F02.12_unknown_event_type.py` "
        "after the eval ran, because the Python `Event` union is closed and "
        "cannot emit an unknown discriminator at runtime. This simulates a "
        "new event type being added on the Python side "
        "(`event/_event.py`) without a matching `case` in the viewer."
    ),
)


def _base_task():
    """Tiny one-sample task — just enough to give us an event list to inject into."""
    from inspect_ai import Task
    from inspect_ai.dataset import Sample
    from inspect_ai.solver import Generate, Solver, TaskState, solver

    @solver
    def trivial() -> Solver:
        async def solve(state: TaskState, generate: Generate) -> TaskState:
            return await generate(state)

        return solve

    return Task(
        name="F02.12_unknown_event_type",
        dataset=[Sample(id="F02.12", input=DESC, target="n/a")],
        solver=trivial(),
    )


def _generate_base_eval(tmp_dir: Path) -> Path:
    """Run the base task → return path to the produced .eval file."""
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


def _inject_unknown_event(src: Path, dst: Path) -> None:
    """Copy ``src`` zip → ``dst``, rewriting the sample JSON to add events."""
    sample_member = "samples/F02.12_epoch_1.json"

    with zipfile.ZipFile(src, "r") as zin:
        members = zin.namelist()
        if sample_member not in members:
            cands = [m for m in members if m.startswith("samples/")]
            raise RuntimeError(f"{sample_member} not in base eval; found {cands}")
        sample = json.loads(zin.read(sample_member))
        payloads: dict[str, bytes] = {m: zin.read(m) for m in members}

    events: list[dict] = sample["events"]

    # Anchor the injected events inside the solver span so they render at the
    # same depth as the model call (i.e. visibly, not buried under sample_init).
    # The solver span is the span_begin whose `type` is "solver"; fall back to
    # the model event's span if the schema shifts.
    anchor_span: str | None = None
    anchor_idx: int = len(events)
    anchor_ts: str = events[-1]["timestamp"]
    for i, ev in enumerate(events):
        if ev.get("event") == "model":
            anchor_span = ev.get("span_id")
            anchor_idx = i + 1  # immediately after the model call
            anchor_ts = ev["timestamp"]
            break
    if anchor_span is None:
        raise RuntimeError(
            "no model event found in base eval — cannot anchor injection"
        )

    def mk_uuid() -> str:
        return _uuid.uuid4().hex[:22]

    banner_event = {
        "uuid": mk_uuid(),
        "span_id": anchor_span,
        "timestamp": anchor_ts,
        "working_start": 0.0,
        "event": "info",
        "source": "bug-repro",
        "data": DESC,
    }
    marker_event = {
        "uuid": mk_uuid(),
        "span_id": anchor_span,
        "timestamp": anchor_ts,
        "working_start": 0.0,
        "event": "logger",
        "message": {
            "name": "F02.12",
            "level": "warning",
            "created": 0.0,
            "filename": "F02.12_unknown_event_type.py",
            "module": "F02.12",
            "lineno": 0,
            "message": (
                "⬇ unknown event 'F02_12_unknown_type' injected immediately "
                "after this — if you cannot see a panel for it below, the "
                "viewer's `default: return null` swallowed it."
            ),
        },
    }
    unknown_event = {
        "uuid": mk_uuid(),
        "span_id": anchor_span,
        "timestamp": anchor_ts,
        "working_start": 0.0,
        # The whole point: a discriminator value the viewer's switch has no
        # `case` for. Reaches RenderedEventNode → default → null.
        "event": "F02_12_unknown_type",
        "payload": (
            "If you can read this string anywhere in the Transcript tab, "
            "F02.12 is FIXED. If you can only find it in the JSON tab, "
            "F02.12 is CONFIRMED."
        ),
    }

    events[anchor_idx:anchor_idx] = [banner_event, marker_event, unknown_event]
    payloads[sample_member] = json.dumps(sample).encode("utf-8")

    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    with zipfile.ZipFile(dst, "w", **zipfile_compress_kwargs) as zout:
        for member in members:
            zout.writestr(member, payloads[member])


def main() -> None:
    # Idempotent: nuke any prior F02.12 logs (timestamped or fixed-name).
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    for stale in LOG_DIR.glob("*F02.12*"):
        stale.unlink()

    with tempfile.TemporaryDirectory(prefix="f02_12_base_") as tmp:
        base = _generate_base_eval(Path(tmp))
        out = LOG_DIR / OUT_NAME
        _inject_unknown_event(base, out)

    print(f"wrote {out}")
    print("verify: open in `inspect view`, sample F02.12 → Transcript → Debug filter")


if __name__ == "__main__":
    main()
