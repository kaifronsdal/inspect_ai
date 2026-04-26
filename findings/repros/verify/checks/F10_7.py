"""F10.7 — Multiple system messages merged into one synthetic row at the top.

Where: Messages tab. Repro has system msgs at positions 1, 4, 7 interleaved
with user/assistant turns. ``resolveMessages`` (messages.ts:62-105) collects
all system messages and emits ONE merged row at the head.
"""

from harness import VerifyResult, ViewerSession

BATCH = "10-chat"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F10.7", tab="messages")
    session.wait_settled(ms=600)

    text = session.text_of("#messages-contents")

    for s in ("SYSTEM MSG #1", "SYSTEM MSG #2", "SYSTEM MSG #3"):
        if s not in text:
            return VerifyResult(
                "INCONCLUSIVE",
                evidence=text[:300],
                notes=f"Sentinel {s!r} not found — repro messages didn't load.",
            )

    # Count rendered SYSTEM-role headers. Each ChatMessage row prints the role
    # label; CSS-uppercased to "SYSTEM".
    system_headers = text.count("\nSYSTEM\n") + (
        1 if text.startswith("SYSTEM\n") else 0
    )
    # Row numbers: the chat list prints "1", "2", … per row. The last numbered
    # row tells us how many rows total.
    import re

    row_nums = [int(m) for m in re.findall(r"\n(\d+)\n", "\n" + text)]
    max_row = max(row_nums) if row_nums else 0

    # Positional check: in the buggy render, SYSTEM MSG #3 appears BEFORE
    # "Assistant turn A" (because it was hoisted into row 1). System-message
    # bodies themselves quote 'Assistant turn A' so use rfind for the actual
    # assistant row.
    pos_sys3 = text.find("SYSTEM MSG #3")
    pos_asstA = text.rfind("Assistant turn A — system msg #2 should appear AFTER me")
    hoisted = 0 < pos_sys3 < pos_asstA

    evidence = (
        f"SYSTEM role headers={system_headers}, total rows={max_row}, "
        f"SYSTEM#3@{pos_sys3} {'before' if hoisted else 'after'} "
        f"AssistantA@{pos_asstA}"
    )

    if system_headers == 1 and hoisted and max_row < 7:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "All three system messages are concatenated under a single "
                "SYSTEM row at position 1; mid-stream #2 and trailing #3 are "
                f"hoisted above 'Assistant turn A'. Only {max_row} rows "
                "rendered (expected 7)."
            ),
        )
    if system_headers >= 3 and not hoisted:
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=evidence,
            notes="Three separate SYSTEM rows in their original positions.",
        )
    return VerifyResult(
        verdict="CONFIRMED",
        evidence=evidence,
        notes="Partial: system messages merged or reordered.",
    )
