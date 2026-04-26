"""F04.2 — Tools sub-tab hidden when exactly one tool is defined.

Where: Transcript → Model Call event → pill nav in the panel header.

Buggy source (ModelEventView.tsx)::

    {event.tools.length > 1 && <div data-name="Tools">…</div>}

Off-by-one: should be ``> 0``. The repro has exactly one tool
(``the_only_tool``), so a CONFIRMED verdict means the Tools pill is absent.
"""

from harness import VerifyResult, ViewerSession

BATCH = "01-events"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F04.2", tab="transcript")

    subtabs_raw = session.event_subtabs("Model Call")
    subtabs = [t.strip().lower() for t in subtabs_raw]

    if not subtabs:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence="Model Call event has no sub-tab nav at all.",
            notes="EventPanel only renders pills when >1 child — check the repro log.",
        )

    has_tools = "tools" in subtabs
    if not has_tools:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=f"Model-event sub-tabs: {subtabs_raw} — no 'Tools' pill.",
            notes=(
                "event.tools has exactly 1 entry (`the_only_tool`); the "
                "`tools.length > 1` guard hides the tab. Off-by-one confirmed."
            ),
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=f"Model-event sub-tabs: {subtabs_raw}",
        notes="Tools tab is present with a single tool — guard appears fixed.",
    )
