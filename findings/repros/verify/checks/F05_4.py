"""F05.4 — StateEvent "Tools" preview never fires when ≥2 tools added at once.

The repro emits TWO StateEvents in one sample:
  • CONTROL — 1× ``add /tools/0``  → preview should FIRE  → SUMMARY/DIFF tabs
  • BUG     — 3× ``add /tools/N``  → preview is SKIPPED   → raw diff only

CONFIRMED if: the 1-tool panel has sub-tab pills and the 3-tool panel does not.
"""

from __future__ import annotations

import re

from checks._util import show_all_events
from harness import VerifyResult, ViewerSession

BATCH = "01-events"
ART = "findings/repros/verify/artifacts"


def _state_panels(session: ViewerSession) -> list:
    """Locate State Updated panels by *title* (not body text)."""
    all_panels = session.page.locator('[id^="event-panel-"]')
    out = []
    for i in range(all_panels.count()):
        title = (
            all_panels.nth(i)
            .locator("> div > div")
            .first.inner_text()
            .strip()
            .upper()
        )
        if title.startswith("STATE UPDATED"):
            out.append(all_panels.nth(i))
    return out


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F05.4", tab="transcript", log="F05.4-state")
    show_all_events(session)
    # dismiss the filter popover so screenshots are clean
    session.page.keyboard.press("Escape")
    session.page.locator("body").click(position={"x": 5, "y": 5})
    session.wait_settled(network_idle=False, ms=200)

    # Collapse INIT so the bug-description text doesn't push state events
    # off-screen and doesn't false-match on the words "State Updated".
    init = session.page.locator('[id^="event-panel-"]').filter(
        has_text=re.compile(r"^INIT", re.IGNORECASE)
    )
    for i in range(init.count()):
        ch = init.nth(i).locator("i.bi-chevron-down")
        if ch.count() and ch.first.is_visible():
            ch.first.click()
    session.wait_settled(network_idle=False, ms=200)

    panels = _state_panels(session)
    if len(panels) < 2:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=f"found {len(panels)} State Updated panels (need 2)",
            notes="Repro should emit two StateEvents (1-tool CONTROL + 3-tool BUG).",
        )

    one, three = panels[0], panels[1]
    artifacts: list[str] = []
    for label, p in (("1tool", one), ("3tools", three)):
        ch = p.locator("i.bi-chevron-right")
        if ch.count() and ch.first.is_visible():
            ch.first.click()
            session.wait_settled(network_idle=False, ms=200)
        artifacts.append(session.screenshot(f"{ART}/F05.4-{label}.png", selector=None))
        p.screenshot(path=f"{ART}/F05.4-{label}.png")
        artifacts[-1] = f"{ART}/F05.4-{label}.png"

    one_tabs = one.locator('button[role="tab"]').all_inner_texts()
    three_tabs = three.locator('button[role="tab"]').all_inner_texts()
    three_text = three.inner_text()[:200]

    one_has_summary = any(t.strip().upper() == "SUMMARY" for t in one_tabs)
    three_has_summary = any(t.strip().upper() == "SUMMARY" for t in three_tabs)

    evidence = (
        f"1-tool panel sub-tabs:  {one_tabs}\n"
        f"3-tool panel sub-tabs:  {three_tabs}\n"
        f"3-tool body (first 200): {three_text!r}"
    )

    if one_has_summary and not three_has_summary:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "Preview fires for 1 tool (SUMMARY/DIFF pills present) but not "
                "for 3 tools (raw diff only). `matchingOps === requiredMatchCount` "
                "fails when >1 op matches the single `/tools/\\d+` pattern. "
                "Summary tab body for the 1-tool case is empty — that is the "
                "separate F05.1 setPath bug."
            ),
            artifacts=artifacts,
        )
    if one_has_summary and three_has_summary:
        return VerifyResult(
            verdict="FALSE_POSITIVE",
            evidence=evidence,
            notes="Preview fires for BOTH 1-tool and 3-tool — count check is fine.",
            artifacts=artifacts,
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=evidence,
        notes=(
            "1-tool case has no Summary tab either — preview may be dead code "
            "(real state mutations never produce a matching op pattern)."
        ),
        artifacts=artifacts,
    )
