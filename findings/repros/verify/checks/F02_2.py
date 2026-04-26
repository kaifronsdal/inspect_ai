"""F02.2 + F02.3 — injectScorersSpan: synthetic 'Scorers' wrapper never receives
its children (key mismatch) and only the first scorer is collected.

The repro emits two root-level ``type="scorer"`` spans (no real ``scorers``
wrapper). Expected: a ``Scorers`` group containing both. Buggy: both scorers
land at root depth 0, no ``Scorers`` wrapper.

Evidence comes from the outline tree's ``data-depth`` attributes.
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
    session.goto_sample("F02.2", tab="transcript")
    session.wait_settled(ms=400)

    rows = _outline(session)
    if not rows:
        return VerifyResult(
            verdict="INCONCLUSIVE", evidence="", notes="No outline rows rendered."
        )

    tree = "\n".join(f"d{d}: {'  ' * d}{label}" for d, label in rows)

    # Where do the two scorer spans land?
    one = next(((d, t) for d, t in rows if "scorer_one" in t.lower()), None)
    two = next(((d, t) for d, t in rows if "scorer_two" in t.lower()), None)
    wrapper = next(((d, t) for d, t in rows if t.lower() == "scorers"), None)

    if one is None or two is None:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=tree,
            notes="Could not find scorer_ONE / scorer_TWO rows in the outline.",
        )

    # Expected (fixed): a 'scorers' wrapper at d0 with both scorers at d1.
    if wrapper and one[0] > wrapper[0] and two[0] > wrapper[0]:
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=tree,
            notes="Both scorer spans are nested under a 'scorers' wrapper.",
        )

    # Bug: no wrapper, both at depth 0.
    return VerifyResult(
        verdict="CONFIRMED",
        evidence=tree,
        notes=(
            f"scorer_ONE at depth {one[0]}, scorer_TWO at depth {two[0]}, "
            f"'scorers' wrapper present={wrapper is not None}. The synthetic "
            f"wrapper is keyed by id=kBeginScorerId but children re-parented to "
            f"kScorersSpanId → lookup misses → wrapper empty → filterEmpty strips "
            f"it (F02.2). Second scorer escapes collection entirely (F02.3)."
        ),
    )
