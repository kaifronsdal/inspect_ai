"""F03.5 — Outline → transcript navigation silently fails when target is inside
a collapsed transcript parent.

Re-audited 2026-04-24 against the regenerated plain-span repro
(``span(name)`` with no ``type=`` — the previous ``type='agent'`` repro
flattened to swimlane cards and was unusable).

Mechanism: clicking an outline label follows a ``<Link>`` → URL gains
``?event=<uuid>`` → ``TranscriptVirtualListComponent.useEffect[initialEventId]``
runs ``flattenedNodes.findIndex(...)`` where ``flattenedNodes`` honours
``collapsedTranscript`` → ``-1`` → ``initialEventIndex=undefined`` → no
scroll, no auto-expand.
"""

from harness import VerifyResult, ViewerSession

BATCH = "02-transform"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F03.5", log="F03.5", tab="transcript")
    session.wait_settled(ms=800)
    page = session.page

    # Precondition: level4 panel is nested under level1 (greater x-offset).
    panel_x = page.evaluate(
        """() => {
            const out = {};
            document.querySelectorAll('[id^="event-panel-"]').forEach(p => {
                const t = (p.innerText || '').split('\\n')[0];
                if (/LEVEL[14]/.test(t)) out[t.slice(0,25)] = Math.round(p.getBoundingClientRect().x);
            });
            return out;
        }"""
    )

    # Step 1: collapse level1 in the TRANSCRIPT.
    l1 = page.locator('[id^="event-panel-"]').filter(has_text="LEVEL1_COLLAPSE_ME").first
    chevron = l1.locator("i.bi-chevron-down").first
    if chevron.count() == 0:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=f"panel_x={panel_x}",
            notes="level1 transcript-panel collapse chevron not found.",
        )
    chevron.click()
    session.wait_settled(network_idle=False, ms=400)

    l4_hidden = (
        page.locator('[id^="event-panel-"]')
        .filter(has_text="LEVEL4_CLICK_ME")
        .count()
        == 0
    )
    if not l4_hidden:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=f"panel_x={panel_x}; l4_hidden={l4_hidden}",
            notes="Collapsing level1 did not hide level4 — nesting precondition not met.",
        )

    # Step 2: click level4 in the OUTLINE (the <a> link directly).
    rows = page.locator('[class*="_eventRow_"][data-unsearchable]')
    l4_row = rows.filter(has_text="level4_CLICK_ME").first
    if l4_row.count() == 0:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence="level4 outline row not found",
            notes="Outline missing level4 — repro broken.",
        )

    scroller = page.locator('[class*="_scroller_"]').first
    scroll_before = scroller.evaluate("e => e.scrollTop")
    url_before = page.url

    link = l4_row.locator("a").first
    (link if link.count() else l4_row.locator("[data-depth]")).click()
    session.wait_settled(network_idle=False, ms=600)

    scroll_after = scroller.evaluate("e => e.scrollTop")
    url_after = page.url
    l4_visible = (
        page.locator('[id^="event-panel-"]')
        .filter(has_text="LEVEL4_CLICK_ME")
        .count()
        > 0
    )

    evidence = (
        f"panel_x={panel_x}; after collapse l4_hidden={l4_hidden}; "
        f"outline-click → url_changed={url_before != url_after}, "
        f"scrollTop {scroll_before}→{scroll_after}, l4_visible={l4_visible}"
    )

    if url_before != url_after and not l4_visible and abs(scroll_after - scroll_before) < 5:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "Outline click updated the URL (?event=<level4-uuid>) but the "
                "transcript neither auto-expanded level1 nor scrolled. "
                "TranscriptVirtualListComponent resolves initialEventId "
                "against the post-collapse flattenedNodes → -1 → no-op."
            ),
        )

    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=evidence,
        notes=(
            f"l4_visible={l4_visible}, Δscroll={scroll_after - scroll_before}. "
            "Either auto-expand or scroll-to-nearest-ancestor now works."
        ),
    )
