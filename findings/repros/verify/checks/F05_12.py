"""F05.12 — BranchEventView discards ``event.metadata``.

Repro: BranchEvent with metadata containing a MARKER string. The view builds
``data`` from ``from_span``/``from_message`` only and never merges
``event.metadata``. Sentinel "IF THIS METADATA IS NOT VISIBLE" appears only in
``event.metadata.MARKER`` (the bug-description text uses different wording).
"""

from checks._util import show_all_events
from harness import VerifyResult, ViewerSession

BATCH = "01-events"

SENTINEL = "IF THIS METADATA IS NOT VISIBLE IN THE BRANCH EVENT"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F05.12", tab="transcript", log="F05.12-branch")
    show_all_events(session)

    panel = session.event_panel("Branch")
    if panel.count() == 0:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=session.text_of("#transcript-contents")[:300],
            notes="Branch event panel not found after clearing filter.",
        )
    chev = panel.locator("i.bi-chevron-right")
    if chev.count():
        chev.first.click()
        session.wait_settled(network_idle=False)

    text = panel.inner_text()
    has_from_span = "from_span" in text or "FROM_SPAN" in text
    has_marker = SENTINEL in text
    has_branch_reason = "branch_reason" in text

    evidence = (
        "--- Branch panel text ---\n"
        + "\n".join(ln for ln in text.splitlines() if ln.strip())[:350]
        + f"\nfrom_span shown: {has_from_span}; metadata MARKER shown: {has_marker}"
    )

    if has_from_span and not has_marker and not has_branch_reason:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "Only from_span/from_message rendered; event.metadata "
                "(branch_reason/branch_index/MARKER) absent. Source confirms "
                "BranchEventView.tsx never reads event.metadata."
            ),
        )
    if has_marker or has_branch_reason:
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=evidence,
            notes="event.metadata is rendered in the Branch panel.",
        )
    return VerifyResult(
        verdict="INCONCLUSIVE",
        evidence=evidence,
        notes="Neither from_span nor metadata visible — repro may not have landed.",
    )
