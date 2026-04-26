"""F05.1 — StateEventView ``setPath`` writes to wrong depth → phantom top-level key.

Repro: replace ``/metadata/LOOK_HERE/nested_key`` BEFORE→AFTER. With the brace
bug, ``setPath`` writes ``target.LOOK_HERE.nested_key`` (top-level) instead of
``target.metadata.LOOK_HERE.nested_key``.

We inspect the rendered jsondiffpatch HTML: the ``<li>`` whose property-name is
``LOOK_HERE`` should be nested *inside* the ``<li>`` for ``metadata``. With the
bug it appears as a top-level sibling.
"""

from checks._util import show_all_events
from harness import VerifyResult, ViewerSession

BATCH = "01-events"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F05.1", tab="transcript", log="F05.1-state")
    show_all_events(session)

    panel = session.event_panel("State Updated")
    if panel.count() == 0:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=session.text_of("#transcript-contents")[:300],
            notes="State Updated panel not found even after clearing event filter.",
        )
    # Expand and switch to Diff tab if there are sub-tabs.
    chev = panel.locator("i.bi-chevron-right")
    if chev.count():
        chev.first.click()
        session.wait_settled(network_idle=False)
    subtabs = panel.locator('button[role="tab"]').all_inner_texts()
    if any(t.strip().lower() == "diff" for t in subtabs):
        panel.get_by_role("tab", name="Diff").first.click()
        session.wait_settled(network_idle=False)

    # jsondiffpatch HTML formatter emits property names in
    # <div class="jsondiffpatch-property-name">key</div>.
    # Find the LOOK_HERE node and check whether any ancestor property-name is
    # "metadata".
    look = panel.locator(".jsondiffpatch-property-name").filter(
        has_text="LOOK_HERE"
    )
    if look.count() == 0:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=panel.inner_text()[:400],
            notes="LOOK_HERE key not found in diff output.",
        )

    # The element containing the BEFORE→AFTER change (i.e. with nested_key under it).
    target = None
    for i in range(look.count()):
        node = look.nth(i)
        # Is the change ("AFTER") rendered under this node's parent <li>?
        parent_li = node.locator("xpath=ancestor::li[1]")
        if "AFTER" in parent_li.inner_text():
            target = node
            break
    if target is None:
        target = look.first

    ancestor_names = target.evaluate(
        "el => { const out=[]; let n=el.closest('li');"
        " while (n) { n = n.parentElement?.closest('li');"
        "   if (n) { const p=n.querySelector(':scope > .jsondiffpatch-property-name');"
        "     if (p) out.push(p.textContent); } } return out; }"
    )

    diff_text = panel.inner_text()
    snippet = "\n".join(
        ln for ln in diff_text.splitlines() if ln.strip()
    )[:400]

    evidence = (
        f"LOOK_HERE ancestor property-names (inner→outer): {ancestor_names}\n"
        f"--- diff text ---\n{snippet}"
    )

    nested_under_metadata = "metadata" in ancestor_names

    if not nested_under_metadata:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "The BEFORE→AFTER change for LOOK_HERE.nested_key is rendered "
                "at the TOP LEVEL of the diff, not under `metadata`. setPath "
                "brace bug confirmed."
            ),
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=evidence,
        notes="LOOK_HERE is correctly nested under `metadata` in the diff.",
    )
