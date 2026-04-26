"""F90.2 — Sub-minute durations rendered with different precisions.

Compare the same ~2.8 s working-time across:
  (A) Metadata-tab Time card → app-local `formatTime` → `2.8 sec` (1 decimal).
  (B) Transcript → 2nd Model event → ALL sub-tab → EventTimingPanel
      "Working Time → Start" → `@tsmono/util formatTime` → `3 sec` (rounded int).
  (C) Log-list "Duration" column → app-local → `3.0 sec` (1 decimal).

If (A)/(C) carry a decimal and (B) is a bare integer, two formatters coexist
→ CONFIRMED. (Third format `Ns` from timeline isn't checked here — two
divergent formatters is sufficient evidence.)
"""

import re

from harness import VerifyResult, ViewerSession

BATCH = "90-cross"

RE_ONE_DEC = re.compile(r"^\d+\.\d sec$")  # "2.8 sec"
RE_INT_SEC = re.compile(r"^\d+ sec$")  # "3 sec"


def check(session: ViewerSession) -> VerifyResult:
    # --- (A) Metadata-tab Time card ---------------------------------------
    session.goto_sample("F90.2", log="F90.2", tab="metadata")
    md = session.text_of("#metadata-contents")
    m = re.search(r"Working:\s*\n\s*(\S[^\n]*)", md)
    md_working = m.group(1).strip() if m else ""
    m = re.search(r"Total:\s*\n\s*(\S[^\n]*)", md)
    md_total = m.group(1).strip() if m else ""

    # --- (B) EventTimingPanel Working Time → Start (2nd model event) ------
    session.goto_sample("F90.2", log="F90.2", tab="transcript")
    session.click_event_subtab("All", in_event="Model Call", nth=1)
    panel = session.event_panel("Model Call", nth=1)
    timing = panel.locator(".tab-pane.active").inner_text()
    # The Working Time section comes after "WORKING TIME"; pull the START row.
    m = re.search(r"WORKING TIME[\s\S]*?START\s*\n\s*(\S[^\n]*)", timing)
    panel_start = m.group(1).strip() if m else ""

    # --- (C) Log-list Duration column for this log ------------------------
    session.goto("/logs")
    session.page.wait_for_timeout(800)
    row = session.page.locator(".ag-row").filter(has_text="F90.2_three_duration")
    dur = row.locator('.ag-cell[col-id="duration"]').first.inner_text().strip()

    evidence = (
        f"Metadata Time card Working = {md_working!r}, Total = {md_total!r}; "
        f"EventTimingPanel WorkingTime Start = {panel_start!r}; "
        f"log-list Duration = {dur!r}"
    )

    if not (md_working and panel_start):
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=evidence,
            notes="Could not extract one of the duration strings.",
        )

    app_decimal = bool(RE_ONE_DEC.fullmatch(md_working)) or bool(
        RE_ONE_DEC.fullmatch(dur)
    )
    util_int = bool(RE_INT_SEC.fullmatch(panel_start))

    if app_decimal and util_int:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "App-side surfaces (Metadata Time card, log-list Duration) "
                "render `N.N sec` with 1 decimal; transcript EventTimingPanel "
                "renders the same elapsed time as bare-int `N sec`. Two "
                "duration formatters coexist on one sample."
            ),
        )
    if md_working == panel_start or (
        RE_INT_SEC.fullmatch(md_working) and util_int
    ) or (RE_ONE_DEC.fullmatch(panel_start) and app_decimal):
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=evidence,
            notes="App-side and transcript-side durations use the same precision.",
        )
    return VerifyResult(
        verdict="INCONCLUSIVE",
        evidence=evidence,
        notes="Duration strings didn't match either expected pattern.",
    )
