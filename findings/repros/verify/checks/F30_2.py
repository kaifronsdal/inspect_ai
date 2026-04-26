"""F30.2 — Status icons differ between log-list grid and log-detail header.

The F30.2 log has ``status="error"``. Compare the ``<i>`` class in the grid's
Status cell against the ``<i>`` class in the title-bar StatusPanel.

Finding claims:
  list  → ``ApplicationIcons.error``        = ``bi-exclamation-circle-fill``
  title → ``ApplicationIcons.logging.error`` = ``bi-x-circle``
"""

from pathlib import Path

from harness import VerifyResult, ViewerSession

BATCH = "30-loglist"

ART = Path(__file__).resolve().parents[1] / "artifacts"


def check(session: ViewerSession) -> VerifyResult:
    artifacts: list[str] = []

    # --- list-view icon ---
    session.goto("/logs")
    session.wait_settled(ms=800)
    row = session.page.locator(".ag-row").filter(has_text="F30.2").first
    if not row.count():
        return VerifyResult("INCONCLUSIVE", "F30.2 row not found in log list")
    list_icon = row.locator(".ag-cell[col-id='status'] i").first.evaluate(
        "el => el.className"
    )
    artifacts.append(
        session.screenshot(ART / "F30.2-list-status.png", selector=".ag-root-wrapper")
    )

    # --- detail-header icon ---
    session.goto_log("F30.2")
    session.wait_settled(ms=500)
    title_icons = session.page.locator("nav.navbar [class*='statusIcon']").evaluate_all(
        "els => els.map(e => e.className)"
    )
    artifacts.append(
        session.screenshot(ART / "F30.2-detail-header.png", selector="nav.navbar")
    )
    title_icon = title_icons[0] if title_icons else ""

    def bi(cls: str) -> set[str]:
        return {c for c in cls.split() if c.startswith("bi-")}

    list_bi = bi(list_icon)
    title_bi = bi(title_icon)

    evidence = (
        f"list status <i> classes: {sorted(list_bi)}; "
        f"detail header <i> classes: {sorted(title_bi)}"
    )

    if not title_bi:
        return VerifyResult("INCONCLUSIVE", evidence, artifacts=artifacts)

    if list_bi != title_bi:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "Same `error` status renders with two different glyphs: "
                f"list={sorted(list_bi)} vs header={sorted(title_bi)}. "
                "`bi-x-circle` means 'cancelled' in the list but 'error' in the header."
            ),
            artifacts=artifacts,
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=evidence,
        notes="Icons match — inconsistency appears fixed.",
        artifacts=artifacts,
    )
