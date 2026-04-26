"""F21.2 — categorical-score filter completions show `undefined`.

Where: per-log Samples list → filter expression input (CodeMirror). Type
``category_scorer == `` and inspect the autocomplete tooltip.

Repro: 3 distinct string scores ``good`` / ``bad`` / ``ugly`` (none of
C/I/P/N) → ``categoricalScoreDescriptor`` whose ``categories`` is the raw
string array. ``filters.ts`` reads ``(cat as Record).val`` → ``undefined``.
"""

from harness import VerifyResult, ViewerSession

BATCH = "20-samples"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_log("F21.2", tab="samples")
    session.wait_settled()

    cm = session.page.locator(".cm-content")
    if cm.count() == 0:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence="(no .cm-content found)",
            notes="Filter expression input not present on Samples tab.",
        )

    cm.first.click()
    session.page.keyboard.type("category_scorer == ")
    session.wait_settled(network_idle=False, ms=500)

    tooltip = session.page.locator(".cm-tooltip-autocomplete")
    if tooltip.count() == 0:
        # Explicit completion request.
        session.page.keyboard.press("Control+Space")
        session.wait_settled(network_idle=False, ms=500)
        tooltip = session.page.locator(".cm-tooltip-autocomplete")

    if tooltip.count() == 0:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence="(no .cm-tooltip-autocomplete shown)",
            notes="Autocomplete dropdown never appeared after typing.",
        )

    items = tooltip.first.locator("li").all_inner_texts()
    has_undefined = any("undefined" in it for it in items)
    has_real = any(v in items for v in ('"good"', '"bad"', '"ugly"', "good", "bad", "ugly"))

    evidence = f"autocomplete items: {items[:12]}"

    if has_undefined and not has_real:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "Completion list contains 'undefined' and none of the real "
                "category values (good/bad/ugly). categoricalScoreDescriptor "
                "stores raw strings in `categories`; filters.ts reads "
                "`(cat as Record).val` → undefined."
            ),
        )
    if has_real and not has_undefined:
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=evidence,
            notes="Real category values appear in completions; no 'undefined'.",
        )
    return VerifyResult(
        verdict="CONFIRMED" if has_undefined else "INCONCLUSIVE",
        evidence=evidence,
        notes=(
            "Mixed: 'undefined' present alongside real values."
            if has_undefined
            else "Neither 'undefined' nor real values in completions."
        ),
    )
