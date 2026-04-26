"""F03.4 — Outline chevron click bubbles to row → selects (but does NOT scroll).

Re-audited 2026-04-24 against the regenerated plain-span repro. The original
finding claims the chevron click "scrolls the main transcript". That is
**false** in ``apps/inspect``: ``TranscriptPanel.tsx`` passes no
``outline.onNavigateToEvent`` (only ``apps/scout`` does —
``TimelineEventsView.tsx:228``), and the chevron sits *outside* the
``<Link>`` wrapper, so the URL doesn't change either. What *does* leak is
``onSelect`` → the selection highlight jumps.

This check therefore asserts:
  CONFIRMED  ⇔ chevron click changes ``selected`` state but NOT scrollTop/URL.
The verdict is reported as CONFIRMED (the bubbling defect is real) with a
note that the finding's scroll-impact claim is overstated for inspect.
"""

from harness import VerifyResult, ViewerSession

BATCH = "02-transform"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F03.4", log="F03.4", tab="transcript")
    session.wait_settled(ms=600)
    page = session.page

    rows = page.locator('[class*="_eventRow_"][data-unsearchable]')
    second = rows.filter(has_text="SECOND_click_my_CHEVRON").first
    first = rows.filter(has_text="FIRST_select_me").first

    if second.count() == 0 or first.count() == 0:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence="FIRST/SECOND outline rows not found",
            notes="Regenerated repro structure missing — re-run run.sh.",
        )

    chevron = second.locator('[class*="_toggle_"] i').first
    if chevron.count() == 0:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence="SECOND row has no chevron",
            notes="Outline row has no children → no toggle. Repro broken.",
        )

    # Step 1: select FIRST (so a selection-jump is observable).
    first.locator("a, [class*='_eventLink_']").first.click()
    session.wait_settled(network_idle=False, ms=300)

    # Scroll the transcript to the bottom so a scroll-jump would be measurable.
    scroller = page.locator('[class*="_scroller_"]').first
    page.evaluate(
        "() => document.querySelectorAll('[class*=_scroller_]')"
        ".forEach(e => e.scrollTop = e.scrollHeight)"
    )
    session.wait_settled(network_idle=False, ms=300)

    sel_second_before = "_selected_" in (second.get_attribute("class") or "")
    scroll_before = scroller.evaluate("e => e.scrollTop")
    url_before = page.url

    # Step 2: click ONLY the chevron <i>.
    chevron.click(force=True, position={"x": 3, "y": 3})
    session.wait_settled(network_idle=False, ms=400)

    sel_second_after = "_selected_" in (second.get_attribute("class") or "")
    scroll_after = scroller.evaluate("e => e.scrollTop")
    url_after = page.url
    child_a_gone = rows.filter(has_text="child_a").count() == 0

    evidence = (
        f"selected SECOND before/after: {sel_second_before}→{sel_second_after}; "
        f"scrollTop {scroll_before}→{scroll_after}; "
        f"url_changed={url_before != url_after}; collapsed={child_a_gone}"
    )

    selection_jumped = (not sel_second_before) and sel_second_after
    scrolled = abs(scroll_after - scroll_before) > 20

    if selection_jumped and not scrolled and url_before == url_after:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "Chevron click bubbled to row onClick → onSelect fired "
                "(highlight jumped to SECOND). Transcript did NOT scroll and "
                "URL did NOT change — the finding's 'scrolls the main "
                "transcript' claim is FALSE for apps/inspect "
                "(onNavigateToEvent is undefined; only apps/scout wires it). "
                "Recommend downgrade MEDIUM→LOW: selection-highlight jump "
                "only, scout-only scroll impact."
            ),
        )
    if selection_jumped and scrolled:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes="Chevron click bubbled AND scrolled — full finding confirmed.",
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=evidence,
        notes="Chevron click did not change selection — bubbling not observed.",
    )
