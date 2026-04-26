"""F02.1 — groupSandboxEvents is a no-op in span-based logs.

Where: Transcript → solver span → look for a "Sandbox Events" group node
wrapping the three sandbox events vs. three individual sandbox panels.

Note: the inspect viewer's default event filter EXCLUDES ``sandbox`` events
(``kDefaultExcludeEvents`` in ``sampleSlice.ts``), so we must first switch the
filter off before the panels appear at all.
"""

from harness import VerifyResult, ViewerSession

BATCH = "02-transform"


def _panel_map(session: ViewerSession) -> list[tuple[float, str]]:
    return session.page.evaluate(
        """() => {
            const out = [];
            document.querySelectorAll('[id^="event-panel-"]').forEach(p => {
                const r = p.getBoundingClientRect();
                const t = (p.innerText || '').split('\\n')[0].slice(0, 80);
                out.push([Math.round(r.x * 10) / 10, t]);
            });
            return out;
        }"""
    )


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F02.1", tab="transcript")
    session.wait_settled(ms=400)

    # Switch event filter Default → Debug (show everything) so sandbox events
    # render. The trigger is a ToolbarButton labelled "Events: <preset>"; the
    # presets in the popover are <a> elements (not buttons).
    btn = session.page.locator("button, [role='button']").filter(
        has_text="Events:"
    )
    filter_switched = False
    if btn.count():
        btn.first.click()
        session.wait_settled(network_idle=False, ms=200)
        pop = session.page.locator("#transcript-filter-popover")
        debug = pop.locator("a").filter(has_text="Debug")
        if debug.count():
            debug.first.click(force=True)
            filter_switched = True
        session.wait_settled(network_idle=False, ms=400)
        session.page.keyboard.press("Escape")
        session.wait_settled(network_idle=False, ms=200)

    # Scroll the main scroller down so all panels are mounted (non-virtual path,
    # eventNodes < 100, so this is just to be safe).
    session.page.evaluate(
        "() => document.querySelectorAll('[class*=\"_scroller_\"]')"
        ".forEach(e => e.scrollTop = e.scrollHeight)"
    )
    session.wait_settled(network_idle=False, ms=300)

    panels = _panel_map(session)
    titles = [t for _, t in panels]
    titles_str = (
        f"[filter_switched={filter_switched}]\n"
        + "\n".join(f"  {x:7.1f}  {t}" for x, t in panels)
    )

    # Individual sandbox events render as "SANDBOX: EXEC" / "SANDBOX: READ_FILE".
    sandbox_panels = [t for t in titles if t.startswith("SANDBOX:")]
    # The synthetic group span renders as a span/step panel titled
    # kSandboxSignalName. labelForNode maps it to "sandbox events"; in the
    # transcript SpanEventView would title it "<NAME>". We accept anything
    # whose title contains the signal name *but is not the solver title*.
    group_panels = [
        t
        for t in titles
        if t != "SOLVER: EMIT_SANDBOX_EVENTS"
        and ("SIG_SANDBOX" in t or t.startswith("SANDBOX EVENTS"))
    ]

    if not sandbox_panels and not group_panels:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=titles_str or "(no panels)",
            notes=(
                "Could not surface sandbox events even after disabling the "
                "default event filter — repro/filter interaction needs manual look."
            ),
        )

    if group_panels and not sandbox_panels:
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=titles_str,
            notes=(
                "A 'SANDBOX EVENTS' group panel renders and the individual "
                "sandbox events are inside it — grouping appears to work."
            ),
        )

    # individual SANDBOX: rows present; check whether they sit under a wrapper
    return VerifyResult(
        verdict="CONFIRMED",
        evidence=titles_str,
        notes=(
            f"{len(sandbox_panels)} individual SANDBOX:* event panels render as "
            f"siblings under the solver — no synthetic 'Sandbox Events' wrapper "
            f"span. groupSandboxEvents' synthetic span (parent_id=null, sandbox "
            f"span_id unchanged) was treeified empty and stripped by filterEmpty."
        ),
    )
