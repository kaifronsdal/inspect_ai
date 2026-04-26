"""F90.1 — Same screen, two timestamp formats: event panels vs app-side.

Compare:
  (A) Transcript event-panel timestamp (EventTimingPanel "Clock Time → Start"
      row, and the panel-title tooltip) — `@tsmono/util` formatDateTime →
      `MM/DD/YY, h:mm:ss AM` (12-hour, 2-digit year).
  (B) Log-list "Completed" column — app-local formatDateTime →
      `YYYY-MM-DD HH:mm:ss` (sv-SE, 24-hour, 4-digit year).

Both render the same underlying instant. If the two strings have different
shapes (one has AM/PM, one is ISO-like) → CONFIRMED.
"""

import re

from harness import VerifyResult, ViewerSession

BATCH = "90-cross"

# 12-hour locale: "04/23/26, 4:57:46 AM"
RE_LOCALE_12H = re.compile(r"\d{1,2}/\d{1,2}/\d{2},?\s+\d{1,2}:\d{2}:\d{2}\s*[AP]M")
# sv-SE: "2026-04-23 04:57:46"
RE_SVSE = re.compile(r"\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}")


def check(session: ViewerSession) -> VerifyResult:
    # --- (A) transcript event-panel timestamp ------------------------------
    session.goto_sample("F90.1", log="F90.1-two", tab="transcript")
    # Tooltip on the Model Call panel header (formatTiming → util formatDateTime)
    panel = session.event_panel("Model Call")
    tooltip = panel.locator("> div").first.get_attribute("title") or ""
    # Visible text: EventTimingPanel "Clock Time → Start" inside the ALL sub-tab
    session.click_event_subtab("All", in_event="Model Call")
    timing_text = panel.locator(".tab-pane.active").inner_text()
    m = re.search(r"START\s*\n\s*(\S[^\n]*)", timing_text)
    timing_start = m.group(1).strip() if m else ""

    # --- (B) log-list "Completed" column ----------------------------------
    session.goto("/logs")
    session.page.wait_for_timeout(800)
    row = session.page.locator(".ag-row").filter(has_text="F90.1_two_datetime")
    completed_cell = row.locator('.ag-cell[col-id="completedAt"]').first
    completed = completed_cell.inner_text().strip()

    evidence = (
        f"event-panel tooltip = {tooltip.splitlines()[0]!r}; "
        f"EventTimingPanel Start = {timing_start!r}; "
        f"log-list Completed = {completed!r}"
    )

    panel_is_12h = bool(RE_LOCALE_12H.search(tooltip) or RE_LOCALE_12H.search(timing_start))
    panel_is_svse = bool(RE_SVSE.fullmatch(timing_start) or RE_SVSE.search(tooltip))
    list_is_svse = bool(RE_SVSE.fullmatch(completed))
    list_is_12h = bool(RE_LOCALE_12H.fullmatch(completed))

    if not timing_start or not completed:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=evidence,
            notes="Could not extract one of the two timestamps.",
        )

    if panel_is_12h and list_is_svse:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "Two formats on adjacent surfaces: transcript event panel uses "
                "12-hour MM/DD/YY locale; log-list Completed column uses sv-SE "
                "YYYY-MM-DD 24-hour. Same instant, different shapes."
            ),
        )
    if (panel_is_svse and list_is_svse) or (panel_is_12h and list_is_12h):
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=evidence,
            notes="Both surfaces use the same timestamp format.",
        )
    return VerifyResult(
        verdict="INCONCLUSIVE",
        evidence=evidence,
        notes="Timestamp formats didn't match either expected pattern.",
    )
