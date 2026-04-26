"""F11.2 — `ToolCallError.type` is never displayed.

Where: Messages tab → ``restricted_op`` tool result. The repro sets
``error=ToolCallError(type='permission', message='Only error.message is …')``.
The viewer reads only ``.message``; ``.type`` ('permission') should appear as a
prefix or label but doesn't.

The repro is tricky to verify by text-grep because both the description AND
the error.message body mention the word 'permission'. So we check whether the
rendered output is **prefixed** with the type — i.e. whether anything other
than ``error.message`` itself appears between the function-name header and
the message text.
"""

from harness import VerifyResult, ViewerSession

BATCH = "11-tools"

MSG_HEAD = "Only error.message is shown"  # first words of error.message


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F11.2", tab="messages", log="F11.2-")
    session.wait_settled(ms=600)

    text = session.text_of("#messages-contents")
    # Isolate the assistant+tool row (row "2") to avoid description bleed.
    if "\n2\n" not in text or MSG_HEAD not in text:
        return VerifyResult(
            "INCONCLUSIVE", evidence=text[-300:], notes="Tool result row not found."
        )
    row2 = text[text.rfind("\n2\n") :]

    # The collapsed-path output is: function header line, then error.message.
    # If `.type` were rendered, we'd see e.g. "permission:" / "Error
    # (permission):" between "restricted_op" and the message head.
    idx_fn = row2.find("restricted_op", row2.find("restricted_op") + 1)
    # ^ second occurrence = the function-call header (first is in the
    #   "Calling restricted_op…" assistant text)
    if idx_fn < 0:
        idx_fn = row2.find("restricted_op")
    idx_msg = row2.find(MSG_HEAD)
    gap = row2[idx_fn + len("restricted_op") : idx_msg]

    type_shown = "permission" in gap.lower()

    evidence = (
        f"between function header and error.message: {gap!r} (type_shown={type_shown})"
    )

    if not type_shown:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "Nothing but whitespace separates the function header from "
                "error.message — `error.type='permission'` is not rendered "
                "as a prefix, badge, or label."
            ),
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=evidence,
        notes="error.type appears as a prefix on the rendered error.",
    )
