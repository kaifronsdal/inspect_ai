"""F10.1 — Orphan tool messages are silently dropped.

Where: Messages tab. The repro inserts a `role=tool` message between two user
turns (no preceding assistant). `resolveMessages` (messages.ts) attaches it to
the preceding USER row's `toolMessages`; `ChatMessageRow` only renders
`toolMessages` for assistant rows → the orphan vanishes.
"""

from harness import VerifyResult, ViewerSession

BATCH = "10-chat"

# Full sentinel from the repro task. The bug-description table only quotes the
# first 40 chars (`…IF THIS L…`), so the tail is unique to the actual rendered
# tool message.
SENTINEL_TAIL = "IF THIS LINE IS MISSING FROM THE MESSAGES TAB, THE BUG IS CONFIRMED"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F10.1", tab="messages")
    session.wait_settled(ms=600)

    text = session.text_of("#messages-contents")

    # Sanity: both flanking user turns must be present, otherwise the repro
    # didn't load.
    if "Second user turn" not in text or "Third user turn" not in text:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=text[:400],
            notes="Flanking user turns not found — repro messages didn't load.",
        )

    # The orphan tool message would render between them. Check for the unique
    # sentinel tail (NOT the 40-char prefix that also appears in the
    # description table).
    orphan_visible = SENTINEL_TAIL in text or "orphaned_tool" in text

    # Extract the slice between the two user turns for evidence.
    i2 = text.find("Second user turn")
    i3 = text.find("Third user turn")
    between = text[i2 : i3 + 20]

    if not orphan_visible:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=f"Between user turns 2 and 3: {between!r}",
            notes=(
                "The orphan tool message (function=orphaned_tool, sentinel "
                f"tail {SENTINEL_TAIL[:30]}…) is absent from the Messages tab. "
                "It was attached to the preceding USER row and never rendered."
            ),
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=f"Between user turns 2 and 3: {between!r}",
        notes="Orphan tool message IS rendered — bug appears fixed.",
    )
