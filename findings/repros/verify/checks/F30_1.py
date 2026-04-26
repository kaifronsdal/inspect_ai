"""F30.1 — Per-metric score columns collide when scorers share a metric name.

Where: Log-list grid (root URL). Two F30.1 logs each have ``scorer_alpha``
(accuracy=0.0) + ``scorer_beta`` (accuracy=1.0). Bug: the grid keys dynamic
score columns by bare metric name (``score_accuracy``), so only ONE accuracy
column exists and the last scorer iterated (beta → 1.0) silently wins.

Dynamic score columns are hidden by default — open the "Choose Columns"
popover to count how many ``accuracy`` entries exist, then enable it and read
the cell value.
"""

from harness import VerifyResult, ViewerSession

BATCH = "30-loglist"


def check(session: ViewerSession) -> VerifyResult:
    session.goto("/logs")
    session.wait_settled(ms=800)

    # 1. Open the column-selector and count `accuracy` checkboxes.
    session.page.get_by_role("button", name="Choose Columns").click()
    session.wait_settled(ms=400, network_idle=False)
    labels = session.page.locator("label").all_inner_texts()
    acc_labels = [l for l in labels if "accuracy" in l.lower()]

    # 2. Enable the accuracy column(s) so we can read cell values.
    for lbl in acc_labels:
        session.page.locator("label").filter(has_text=lbl).first.click()
        session.wait_settled(ms=200, network_idle=False)
    session.page.keyboard.press("Escape")
    session.wait_settled(ms=300, network_idle=False)

    # 3. Read header col-ids + an F30.1 row's score_accuracy cell.
    headers = session.page.locator(".ag-header-cell").evaluate_all(
        "els => els.map(e => e.getAttribute('col-id'))"
    )
    acc_cols = [h for h in headers if h and "accuracy" in h.lower()]
    f301_row = (
        session.page.locator(".ag-center-cols-container .ag-row")
        .filter(has_text="F30.1")
        .first
    )
    cell_map = (
        f301_row.locator(".ag-cell").evaluate_all(
            "els => Object.fromEntries(els.map(c => "
            "[c.getAttribute('col-id'), c.innerText]))"
        )
        if f301_row.count()
        else {}
    )

    evidence = (
        f"Column-selector accuracy entries: {acc_labels}; "
        f"grid accuracy col-ids: {acc_cols}; "
        f"F30.1 row score_accuracy={cell_map.get('score_accuracy')!r}, "
        f"score={cell_map.get('score')!r}"
    )

    if len(acc_labels) == 1 and len(acc_cols) == 1:
        # Collision: scorer_alpha→0.0 and scorer_beta→1.0 collapse to one col.
        # Last-iterated (beta) wins → cell shows 1.0; headline `score`
        # (first metric of scores[0] = alpha) shows 0.0.
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "Only one `accuracy` column despite two scorers each reporting "
                "accuracy. Cell value 1.0 = scorer_beta (last in array); "
                "scorer_alpha's 0.0 is overwritten. Header gives no scorer hint."
            ),
        )
    if len(acc_labels) >= 2 or len(acc_cols) >= 2:
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=evidence,
            notes="Two accuracy columns present — collision appears fixed.",
        )
    return VerifyResult(
        verdict="INCONCLUSIVE",
        evidence=evidence,
        notes="No accuracy column found at all — column selector layout changed?",
    )
