"""F02.4 — unwrapNode (type='main') only re-depths direct children;
grandchildren render one indent too deep.

Evidence: outline ``data-depth`` sequence — if the ``main`` wrapper at depth N
is unwrapped, CHILD should land at N and GRANDCHILD at N+1. The bug leaves
GRANDCHILD at N+2 (a depth gap).
"""

from harness import VerifyResult, ViewerSession

BATCH = "02-transform"


def _outline(session: ViewerSession) -> list[tuple[int, str]]:
    rows = []
    labels = session.page.locator('[class*="_eventRow_"][data-unsearchable] [data-depth]')
    for i in range(labels.count()):
        el = labels.nth(i)
        d = int(el.get_attribute("data-depth") or "-1")
        rows.append((d, el.inner_text().strip()))
    return rows


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F02.4", tab="transcript")
    session.wait_settled(ms=400)

    rows = _outline(session)
    tree = "\n".join(f"d{d}: {'  ' * d}{label}" for d, label in rows)

    child = next(
        ((d, t) for d, t in rows if "CHILD_after_unwrap" in t), None
    )
    grandchild = next(
        ((d, t) for d, t in rows if "GRANDCHILD" in t), None
    )

    if child is None or grandchild is None:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=tree,
            notes="Could not find CHILD or GRANDCHILD in outline.",
        )

    delta = grandchild[0] - child[0]
    if delta == 1:
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=tree,
            notes="GRANDCHILD is exactly one level under CHILD — depth correct.",
        )

    return VerifyResult(
        verdict="CONFIRMED",
        evidence=tree,
        notes=(
            f"CHILD depth={child[0]}, GRANDCHILD depth={grandchild[0]} — "
            f"gap of {delta} (should be 1). unwrapNode set CHILD.depth = "
            f"main.depth but did not recurse into GRANDCHILD."
        ),
    )
