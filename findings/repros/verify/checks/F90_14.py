"""F90.14 — Numeric score 1.0 formatted three ways across three surfaces.

Score / metric value is exactly 1.0. Compare:
  (1) Title-bar ResultsPanel headline metric + log-list Score column →
      `formatPrettyDecimal` → `"1.0"`.
  (2) Sample-header Score pill (NumericScoreDescriptor) →
      `formatDecimalNoTrailingZeroes` → `"1"`.
  (3) Multi-log Samples grid score column → `value.toFixed(3)` → `"1.000"`.

CONFIRMED if at least two of the three rendered strings differ.
"""

from harness import VerifyResult, ViewerSession

BATCH = "90-cross"


def check(session: ViewerSession) -> VerifyResult:
    # --- (1) headline metric + log-list score -----------------------------
    session.goto("/logs")
    session.page.wait_for_timeout(800)
    row = session.page.locator(".ag-row").filter(has_text="F90.14_numeric_score_precision_A")
    loglist_score = (
        row.locator('.ag-cell[col-id="score"]').first.inner_text().strip()
        if row.count()
        else ""
    )

    session.goto_log("F90.14-numeric-score-precision-A", tab="samples")
    # ResultsPanel headline: a "MEAN" label followed by the value.
    body = session.all_text()
    import re

    m = re.search(r"\bMEAN\b\s*\n?\s*([0-9.eE+\-]+)", body)
    headline = m.group(1) if m else ""

    # --- (2) sample-header Score cell -------------------------------------
    hdr = session.page.locator('[id^="sample-heading-"]').first
    # Score cell is the centred value cell at the end (only centred column).
    score_cell = hdr.locator('[class*="_centerValue_"]').last
    sample_hdr_score = score_cell.inner_text().strip()

    # --- (3) multi-log Samples grid score column --------------------------
    session.goto("/logs")
    session.page.wait_for_timeout(800)
    seg = session.page.locator('button[aria-pressed]').filter(has_text="Samples")
    multilog_score = ""
    if seg.count():
        seg.first.click()
        session.wait_settled()
        session.page.wait_for_timeout(1500)
        mrow = session.page.locator(".ag-row").filter(
            has_text="F90.14_numeric_score_precision_A"
        )
        if mrow.count():
            cell = mrow.first.locator(
                '.ag-cell[col-id="score_returns_one_point_zero"]'
            )
            if cell.count():
                multilog_score = cell.first.inner_text().strip()

    values = {
        "headline (formatPrettyDecimal)": headline,
        "log-list score (formatPrettyDecimal)": loglist_score,
        "sample-header (formatDecimalNoTrailingZeroes)": sample_hdr_score,
        "multi-log grid (toFixed(3))": multilog_score,
    }
    evidence = " | ".join(f"{k} = {v!r}" for k, v in values.items())

    extracted = [v for v in (headline, loglist_score, sample_hdr_score, multilog_score) if v]
    if len(extracted) < 2:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=evidence,
            notes="Fewer than two surfaces extracted — can't compare.",
        )

    distinct = set(extracted)
    if len(distinct) >= 2:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                f"{len(distinct)} distinct renderings of the same value 1.0 "
                f"across {len(extracted)} surfaces: {sorted(distinct)}."
            ),
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=evidence,
        notes=f"All extracted surfaces agree on {distinct.pop()!r}.",
    )
