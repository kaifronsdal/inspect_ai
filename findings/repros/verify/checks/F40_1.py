"""F40.1 — RecordTree default-collapse never fires (always fully expanded).

Where: Sample → Metadata tab. The repro stuffs ``state.metadata["deep_tree"]``
with a 7-level-deep branch and a 12-child wide branch. Correct behaviour
would mount with deep / wide branches collapsed, so their leaf values would
**not** be present in the tab's ``inner_text`` until the user clicks expand.

Bug: ``useCollapsibleIds`` returns ``{}`` (truthy) so the
``if (collapsedIds) return;`` guard always early-exits and nothing is ever
collapsed-by-default → every leaf is visible immediately.
"""

from pathlib import Path

from harness import VerifyResult, ViewerSession

BATCH = "40-content"

# Sentinel strings from the repro task that should be hidden behind a
# collapsed node on first render.
DEEP_LEAF = "L7_leaf"
DEEP_LEAF_VALUE = "DEEP — this branch should be COLLAPSED"
WIDE_LEAF = "child_11"  # last of 12 siblings


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F40.1", tab="metadata")

    # The Metadata tab content lives in #metadata-contents (TabSet pattern).
    md_text = session.text_of("#metadata-contents")

    if "deep_tree" not in md_text:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=md_text[:400],
            notes="`deep_tree` key not found in Metadata tab — repro metadata didn't land.",
        )

    deep_visible = DEEP_LEAF in md_text or DEEP_LEAF_VALUE in md_text
    wide_visible = WIDE_LEAF in md_text

    artifacts: list[str] = []
    shot = Path(__file__).resolve().parents[1] / "artifacts" / "F40.1-metadata.png"
    artifacts.append(session.screenshot(shot, selector="#metadata-contents"))

    if deep_visible and wide_visible:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=(
                f"Without any clicks, Metadata tab already shows deep leaf "
                f"({DEEP_LEAF!r} present={deep_visible}) and wide leaf "
                f"({WIDE_LEAF!r} present={wide_visible})."
            ),
            notes=(
                "RecordTree mounts fully expanded — default-collapse heuristic "
                "(depth >= defaultExpandLevel, childCount > 5) never ran."
            ),
            artifacts=artifacts,
        )
    if not deep_visible and not wide_visible:
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=f"Neither {DEEP_LEAF!r} nor {WIDE_LEAF!r} visible on mount.",
            notes="Deep + wide branches are collapsed by default — bug appears fixed.",
            artifacts=artifacts,
        )
    return VerifyResult(
        verdict="CONFIRMED",
        evidence=(
            f"{DEEP_LEAF!r} visible={deep_visible}, {WIDE_LEAF!r} visible={wide_visible}"
        ),
        notes="Partial: one heuristic fires, the other doesn't.",
        artifacts=artifacts,
    )
