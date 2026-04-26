"""F80.10 — formatPrettyDecimal / formatDecimalNoTrailingZeroes collapse 1.234e-7 to "0.000".

Score is exactly 1.234e-7 (non-zero). Check:
  (1) Title-bar headline metric (`formatPrettyDecimal`) → `"0.000"`.
  (2) Sample-header Score pill (`formatDecimalNoTrailingZeroes`) → `"0.000000"`.
  (3) Log-list Score column (`formatPrettyDecimal`) → `"0.000"`.

CONFIRMED if any of these renders as a string of zeros (indistinguishable
from a true 0). NOT_REPRODUCED if all surfaces show a non-zero digit or
exponential form.
"""

import re

from harness import VerifyResult, ViewerSession

BATCH = "90-cross"

RE_ALL_ZEROS = re.compile(r"^0(\.0+)?$")  # "0", "0.0", "0.000", "0.000000"


def check(session: ViewerSession) -> VerifyResult:
    # --- (3) log-list Score column ----------------------------------------
    session.goto("/logs")
    session.page.wait_for_timeout(800)
    row = session.page.locator(".ag-row").filter(has_text="F80.10_tiny_score")
    loglist_score = (
        row.locator('.ag-cell[col-id="score"]').first.inner_text().strip()
        if row.count()
        else ""
    )

    # --- (1) headline + (2) sample-header ---------------------------------
    session.goto_log("F80.10", tab="samples")
    body = session.all_text()
    m = re.search(r"\bMEAN\b\s*\n?\s*([0-9.eE+\-]+)", body)
    headline = m.group(1) if m else ""

    hdr = session.page.locator('[id^="sample-heading-"]').first
    score_cell = hdr.locator('[class*="_centerValue_"]').last
    sample_hdr_score = score_cell.inner_text().strip()

    values = {
        "headline (formatPrettyDecimal)": headline,
        "log-list score (formatPrettyDecimal)": loglist_score,
        "sample-header (formatDecimalNoTrailingZeroes)": sample_hdr_score,
    }
    evidence = " | ".join(f"{k} = {v!r}" for k, v in values.items())

    extracted = {k: v for k, v in values.items() if v}
    if not extracted:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=evidence,
            notes="No score values extracted.",
        )

    zeroed = {k: v for k, v in extracted.items() if RE_ALL_ZEROS.fullmatch(v)}
    nonzero = {
        k: v
        for k, v in extracted.items()
        if not RE_ALL_ZEROS.fullmatch(v)
    }

    if zeroed:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                f"Score 1.234e-7 (non-zero) renders as all-zeros on "
                f"{len(zeroed)}/{len(extracted)} surface(s): "
                f"{', '.join(f'{k}={v!r}' for k, v in zeroed.items())} — "
                f"indistinguishable from a true zero score."
            ),
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=evidence,
        notes=(
            f"All surfaces show non-zero digits or exponential form: "
            f"{', '.join(f'{k}={v!r}' for k, v in nonzero.items())}."
        ),
    )
