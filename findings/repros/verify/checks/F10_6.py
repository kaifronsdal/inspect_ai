r"""F10.6 — `<think>` blocks in plain text are stripped with no marker.

Where: Messages tab → assistant turn whose string content starts with
``<think>SENTINEL</think>\\nVisible answer: …``.

Buggy source (MessageContent.tsx:142-151): ``purgeInternalContainers`` regex-
deletes ``<think>…</think>`` before passing to RenderedText. No placeholder.
"""

from harness import VerifyResult, ViewerSession

BATCH = "10-chat"

# The description quotes only the first 30 chars (`F10.6_HIDDEN_REASONING — IF YO…`).
# The full sentinel tail is unique to the actual rendered <think> body.
SENTINEL_TAIL = "IF YOU CAN READ THIS the bug is FIXED"
VISIBLE_ANCHOR = "Visible answer: the capital of France is Paris"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F10.6", tab="messages")
    session.wait_settled(ms=600)

    text = session.text_of("#messages-contents")
    if VISIBLE_ANCHOR not in text:
        return VerifyResult(
            "INCONCLUSIVE",
            evidence=text[-400:],
            notes="Assistant turn ('Visible answer: …') not found.",
        )

    # Isolate the assistant row (row "2") to avoid description-table bleed.
    row2 = text[text.rfind("\n2\n") :]

    think_visible = SENTINEL_TAIL in row2
    # Any redaction marker that the viewer might add.
    markers = ["[hidden", "[redacted", "[internal", "(hidden", "internal content"]
    marker_visible = any(m.lower() in row2.lower() for m in markers)

    evidence = f"assistant row: {row2.strip()[:250]!r}"

    if not think_visible and not marker_visible:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "The <think>…</think> body is gone and no '[hidden]' / "
                "'[internal]' marker took its place — silent deletion."
            ),
        )
    if think_visible:
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=evidence,
            notes="<think> content is rendered verbatim — bug fixed.",
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=evidence,
        notes=f"Stripped, but a redaction marker IS shown ({row2!r}).",
    )
