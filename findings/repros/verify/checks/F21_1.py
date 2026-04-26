"""F21.1 — score column sorts with ag-grid's default (alphabetical), not
the descriptor's semantic ``compare()``.

Where: per-log Samples list → click the score column header.

Repro: 4 samples with pass/fail values C, P, I, N. Semantic order
(``passFailScoreDescriptor.compare``) is C → P → I → N. Alphabetical is
C → I → N → P. After one ascending-sort click we read row order via
``row-index`` (ag-grid recycles DOM nodes so DOM order ≠ visual order).
"""

from harness import VerifyResult, ViewerSession

BATCH = "20-samples"


def _row_order(session: ViewerSession) -> list[tuple[str, str]]:
    rows = session.page.locator(".ag-center-cols-container .ag-row")
    by_idx: dict[int, tuple[str, str]] = {}
    for i in range(rows.count()):
        r = rows.nth(i)
        ridx = int(r.get_attribute("row-index"))
        rid = r.locator('.ag-cell[col-id="id"]').inner_text()
        rscore = r.locator('.ag-cell[col-id="score-0"]').inner_text()
        by_idx[ridx] = (rid, rscore)
    return [by_idx[k] for k in sorted(by_idx)]


def check(session: ViewerSession) -> VerifyResult:
    # F21.1 substring matches F21.10 — disambiguate.
    session.goto_log("F21.1-", tab="samples")
    session.wait_settled()

    score_hdr = session.page.locator('.ag-header-cell[col-id="score-0"]')
    if score_hdr.count() == 0:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence="(no .ag-header-cell[col-id=score-0])",
            notes="Score column header not found in sample list.",
        )

    score_hdr.first.click()
    session.wait_settled(network_idle=False, ms=400)
    order = _row_order(session)
    score_seq = [s for _id, s in order]

    semantic = ["C", "P", "I", "N"]
    alphabetical = ["C", "I", "N", "P"]

    evidence = f"after sort-asc click, (id, score) order: {order}"

    if score_seq == alphabetical:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "Pass/fail scores sort C, I, N, P (alphabetical) instead of the "
                "semantic C, P, I, N order encoded in "
                "passFailScoreDescriptor.compare(). columns.tsx supplies no "
                "comparator to ag-grid so the descriptor's compare() is dead."
            ),
        )
    if score_seq == semantic:
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=evidence,
            notes="Scores sort in semantic C→P→I→N order — comparator is wired.",
        )
    if score_seq == list(reversed(alphabetical)):
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes="First click sorted descending-alphabetical (P, N, I, C).",
        )
    return VerifyResult(
        verdict="INCONCLUSIVE",
        evidence=evidence,
        notes="Sort order is neither alphabetical nor semantic — re-check.",
    )
