"""F04.8 — ModelUsagePanel renders zero-valued token counts as blank cells.

Where: Transcript → Model Call event → **All** sub-tab → Usage section.
The repro sets ``input_tokens=0`` / ``input_tokens_cache_write=0`` /
``reasoning_tokens=0`` (and non-zero output/cache_read/total for contrast).

Buggy pattern: ``{row.value ? formatNumber(row.value) : ""}`` — truthy check
hides legitimate ``0``.

This check also exercises ``click_event_subtab`` (which F01.2 couldn't reach).
"""

import re

from harness import VerifyResult, ViewerSession

BATCH = "01-events"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F04.8", tab="transcript")
    session.click_event_subtab("All", in_event="Model Call")

    panel = session.event_panel("Model Call")
    # Usage section is inside the active tab-pane of the model event panel.
    text = panel.locator(".tab-pane.active").inner_text()

    # Evidence: pull "<label> <value>" pairs from the usage rows.
    # ModelUsagePanel renders a 2-col grid: label cell, value cell.
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    usage_labels = {
        "input",
        "output",
        "total",
        "reasoning",
        "cache_read",
        "cache_write",
    }
    rows: dict[str, str] = {}
    for i, ln in enumerate(lines):
        # Label cells are short single tokens (CSS-uppercased); skip prose.
        if ln.lower() not in usage_labels:
            continue
        val = lines[i + 1] if i + 1 < len(lines) else ""
        # Value cell is either a number or blank; if next line is another
        # label, the value cell rendered empty.
        rows[ln] = val if re.fullmatch(r"[\d,.\-—]+", val) else ""

    if not rows:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=text[:400],
            notes="Could not locate usage rows in the All tab.",
        )

    zero_labels = [k for k, v in rows.items() if v.strip() in {"", "-", "—"}]
    nonzero_labels = [k for k, v in rows.items() if v.strip() not in {"", "-", "—"}]

    evidence = " | ".join(f"{k}={v!r}" for k, v in rows.items())

    if zero_labels and nonzero_labels:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                f"Rows {zero_labels} render blank while {nonzero_labels} render "
                f"numbers — falsy-zero check confirmed."
            ),
        )
    if not zero_labels:
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=evidence,
            notes="Every usage row (including the 0-valued ones) shows a number.",
        )
    return VerifyResult(
        verdict="INCONCLUSIVE",
        evidence=evidence,
        notes="All rows blank — repro usage may not have been recorded.",
    )
