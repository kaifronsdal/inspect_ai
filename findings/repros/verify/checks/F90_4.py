"""F90.4 — Multi-log SamplesGrid 'Status' column shows the LOG's status, not the sample's.

Log A has `fail_on_error=False` and contains sample `F90.4-errored` which
raises a RuntimeError. The log finishes with status=success.

In the multi-log Samples grid (root → "Samples" segment), the row for
`F90.4-errored` should show Status=error (per-sample). The bug populates
Status from `logDetail.status` → `success` for every row from log A.
"""

from harness import VerifyResult, ViewerSession

BATCH = "90-cross"


def check(session: ViewerSession) -> VerifyResult:
    session.goto("/logs")
    session.page.wait_for_timeout(1200)

    # Click the "Samples" segment button (not a NavPill — uses aria-pressed).
    seg = session.page.locator('button[aria-pressed]').filter(has_text="Samples")
    if seg.count() == 0:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence="",
            notes="Could not find the 'Samples' segment button on /logs.",
        )
    seg.first.click()
    session.wait_settled()
    session.page.wait_for_timeout(1500)

    # Find the F90.4-errored row by its sampleId cell (NOT by row text — every
    # F90.4 row's Input column contains the string "F90.4-errored" from the
    # bug description, so has_text on the row matches the wrong one).
    row = session.page.locator(".ag-row").filter(
        has=session.page.locator('.ag-cell[col-id="sampleId"]', has_text="F90.4-errored")
    )
    if row.count() == 0:
        # ag-grid is virtualised — try scrolling.
        session.page.locator(".ag-body-viewport").first.evaluate(
            "el => el.scrollTo(0, el.scrollHeight)"
        )
        session.page.wait_for_timeout(500)
        row = session.page.locator(".ag-row").filter(
            has=session.page.locator(
                '.ag-cell[col-id="sampleId"]', has_text="F90.4-errored"
            )
        )
    if row.count() == 0:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence="",
            notes="F90.4-errored row not found in multi-log Samples grid.",
        )

    status = row.first.locator('.ag-cell[col-id="status"]').inner_text().strip()
    error = row.first.locator('.ag-cell[col-id="error"]').inner_text().strip()
    sample_id = row.first.locator('.ag-cell[col-id="sampleId"]').inner_text().strip()

    evidence = (
        f"multi-log grid row sampleId={sample_id!r}: "
        f"Status cell = {status!r}; Error cell = {error[:90]!r}"
    )

    sample_errored = bool(error)  # per-sample error string is populated

    if sample_errored and status.lower() == "success":
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "Per-sample Error cell carries the RuntimeError, yet the "
                "Status cell says 'success' — it's the parent log's status, "
                "not the sample's."
            ),
        )
    if sample_errored and status.lower() in {"error", "failed"}:
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=evidence,
            notes="Multi-log grid Status now reflects per-sample error.",
        )
    if not sample_errored:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=evidence,
            notes="Repro sample F90.4-errored has no Error recorded — repro broken.",
        )
    return VerifyResult("INCONCLUSIVE", evidence, notes=f"Unexpected status {status!r}.")
