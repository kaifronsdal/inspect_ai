"""F21.10 — multi-log SamplesGrid and single-log SampleList format the same
score differently.

Compare:
  • multi-log grid (route ``#/samples/``) → ``score_numeric`` cell, dict cell,
    passfail cell
  • single-log list (route ``#/logs/<file>/samples``) → score column for the
    same sample

Divergences claimed by the finding:
  numeric  : ``1.000`` (toFixed(3))    vs  ``1`` (no trailing zeroes)
  dict     : raw JSON blob              vs  key/value grid
  passfail : plain ``C``                vs  coloured circle badge
"""

from harness import VerifyResult, ViewerSession

BATCH = "20-samples"


def check(session: ViewerSession) -> VerifyResult:
    # ---------------- multi-log SamplesGrid --------------------------------
    session.goto("/samples/")
    session.wait_settled(ms=1500)

    grid_rows = session.page.locator(".ag-center-cols-container .ag-row").filter(
        has_text="F21.10"
    )
    if grid_rows.count() == 0:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence="(no F21.10 rows in /samples/ grid)",
            notes=(
                "Multi-log SamplesGrid did not render F21.10 rows — the "
                "/samples/ route may have changed."
            ),
        )
    r0 = grid_rows.first
    cells = r0.locator(".ag-cell")
    grid_cells: dict[str, str] = {}
    for j in range(cells.count()):
        c = cells.nth(j)
        grid_cells[c.get_attribute("col-id") or f"col{j}"] = c.inner_text()
    grid_passfail = grid_cells.get("score_passfail", "")
    grid_numeric = grid_cells.get("score_numeric", "")
    grid_dict = grid_cells.get("score_dictscore", "")
    grid_circle = r0.locator(
        '.ag-cell[col-id="score_passfail"] span[class*="circle"]'
    ).count() > 0

    # ---------------- single-log SampleList --------------------------------
    session.goto_log("F21.10-multilog-a", tab="samples")
    session.wait_settled()
    list_cell = session.page.locator('.ag-cell[col-id="score-0"]').first
    list_passfail = list_cell.inner_text()
    list_circle = list_cell.locator("span[class*='circle']").count() > 0

    evidence = (
        f"multi-log grid: passfail={grid_passfail!r} (circle badge: "
        f"{grid_circle}), numeric={grid_numeric!r}, dict={grid_dict!r} | "
        f"single-log list: passfail={list_passfail!r} (circle badge: "
        f"{list_circle})"
    )

    diverges = []
    if list_circle and not grid_circle:
        diverges.append("passfail: circle badge in list, plain text in grid")
    if "." in grid_numeric and grid_numeric.endswith("000"):
        diverges.append(f"numeric: grid uses .toFixed(3) → {grid_numeric!r}")
    if grid_dict.startswith("{") and ":" in grid_dict:
        diverges.append(f"dict: grid uses raw JSON.stringify → {grid_dict!r}")

    if diverges:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "Two grid implementations format the same scores differently: "
                + "; ".join(diverges)
                + ". SamplesGrid (hooks.tsx) hard-codes value.toFixed(3) / "
                "JSON.stringify instead of reusing the score descriptor."
            ),
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=evidence,
        notes="Both grids render scores with the same formatting.",
    )
