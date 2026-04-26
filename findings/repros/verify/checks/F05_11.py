"""F05.11 — SampleInitEventView omits ``sample.sandbox`` and ``sample.id``.

Repro: Sample with id="DISTINCTIVE-SAMPLE-ID-⚠️-F05.11", sandbox="local",
files+setup populated. CONFIRMED if the Sample Init panel shows Files/Setup/
Target but no row for sandbox type or sample id.

The default event filter HIDES sample_init, so we clear it first.
"""

from checks._util import show_all_events
from harness import VerifyResult, ViewerSession

BATCH = "01-events"

SAMPLE_ID = "DISTINCTIVE-SAMPLE-ID-⚠️-F05.11"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample(SAMPLE_ID, tab="transcript", log="F05.11-sample")
    show_all_events(session)

    # The treeify pipeline wraps SampleInit in an "init" span; expand it so the
    # inner SampleInit panel (title="Sample") mounts.
    init_span = session.page.locator('[id^="event-panel-"]').filter(has_text="Init")
    chev = init_span.first.locator("i.bi-chevron-right")
    if chev.count():
        chev.first.click()
        session.wait_settled(network_idle=False)

    # SampleInit title is just "Sample". Find the panel whose first line is
    # exactly SAMPLE (not "SOLVER:" etc.).
    panels = session.page.locator('[id^="event-panel-"]')
    init_panel = None
    for i in range(panels.count()):
        first = panels.nth(i).inner_text().split("\n", 1)[0].strip().upper()
        if first == "SAMPLE":
            init_panel = panels.nth(i)
            break
    if init_panel is None:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=str(
                [
                    panels.nth(i).inner_text().split("\n", 1)[0]
                    for i in range(panels.count())
                ]
            ),
            notes="Sample Init panel not found even after clearing event filter.",
        )
    chev = init_panel.locator("i.bi-chevron-right")
    if chev.count():
        chev.first.click()
        session.wait_settled(network_idle=False)

    subtabs = init_panel.locator('button[role="tab"]').all_inner_texts()
    # Gather text across all sub-tabs (Sample / Metadata).
    full_text = ""
    if subtabs:
        for t in subtabs:
            init_panel.get_by_role("tab", name=t).first.click()
            session.wait_settled(network_idle=False)
            full_text += "\n" + init_panel.inner_text()
    else:
        full_text = init_panel.inner_text()

    # The bug-description text (which is the sample.input → user message →
    # rendered in the ChatView) contains the words "sandbox", "id", "local",
    # and the distinctive sample id. We must therefore check for STRUCTURED
    # labels, not free text.
    labels = {
        raw.strip().upper()
        for raw in init_panel.locator(".text-style-label").all_inner_texts()
    }
    # Also collect EventSection titles (rendered as label-styled headings).
    section_titles = {
        raw.strip().upper()
        for raw in init_panel.locator("[class*='EventSection']").all_inner_texts()
    }

    has_sandbox = "SANDBOX" in labels or any("SANDBOX" in t for t in section_titles)
    has_id = "ID" in labels or "SAMPLE ID" in labels
    has_files = "FILES" in full_text.upper().split("\n")
    has_setup = "SETUP" in full_text.upper().split("\n")

    evidence = (
        f"sub-tabs: {subtabs}\n"
        f"label cells: {sorted(labels)}\n"
        f"Files section: {has_files}; Setup section: {has_setup}\n"
        f"Sandbox label/section: {has_sandbox}; ID label: {has_id}"
    )

    if not has_sandbox and not has_id:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "Files & Setup are shown; no structured Sandbox or ID row. "
                "Source confirms SampleInitEventView.tsx never reads "
                "`event.sample.sandbox` or `event.sample.id`."
            ),
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=evidence,
        notes=f"Sandbox shown={has_sandbox}, ID shown={has_id}.",
    )
