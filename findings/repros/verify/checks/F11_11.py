"""F11.11 — ApprovalEventView drops `approver`, `modified`, `message`.

Where: Transcript tab → Tool event ``write_file`` → inline Approval row.

Source (ApprovalEventView.tsx:22-31)::

    <EventRow title={decisionLabel(event.decision)} icon={…}>
      {event.explanation || ""}
    </EventRow>

Only ``decision`` + ``explanation`` are read. ``event.approver``,
``event.modified``, ``event.message`` are never referenced.

Verification note: every sentinel string in this repro also appears elsewhere
on the page (in the bug-description table, in the explanation text itself, in
the assistant message inside the Model Call panel, and in the tool *output*
since the tool was actually invoked with the modified args). So we scope the
check tightly to the Approval EventRow (``Modified`` + explanation) and assert
that nothing OUTSIDE the explanation surfaces the three fields.
"""

from harness import VerifyResult, ViewerSession

BATCH = "11-tools"

APPROVER = "F11.11_APPROVER_NAME_security_reviewer"
MODIFIED_ARG = "F11.11_MODIFIED_ARG_VALUE_sanitised_path"
EXPLANATION_HEAD = "Rewrote `path` to a sandboxed value."


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F11.11", tab="transcript", log="F11.11-")
    session.wait_settled(ms=800)

    body = session.all_text()

    # The Approval renders as an EventRow titled "Modified" (CSS-uppercased to
    # "MODIFIED") followed by the explanation. It is NOT inside an
    # `[id^=event-panel-]` element, so locate it by text position.
    idx_mod = body.find("\nMODIFIED\n")
    if idx_mod < 0:
        return VerifyResult(
            "INCONCLUSIVE",
            evidence=body[-400:],
            notes="Approval row ('MODIFIED') not found in transcript.",
        )
    # The next event panel after the approval is "MODEL CALL: …".
    idx_next = body.find("MODEL CALL", idx_mod)
    approval_slice = body[idx_mod : idx_next if idx_next > 0 else idx_mod + 1000]

    # The explanation deliberately mentions the approver + modified-arg
    # sentinels. Strip the explanation body so we're only looking at what the
    # *viewer* added (decision label + any extra fields).
    idx_expl = approval_slice.find(EXPLANATION_HEAD)
    chrome_before = approval_slice[: idx_expl if idx_expl > 0 else len(approval_slice)]
    # Anything after the explanation but before the next panel:
    chrome_after = (
        approval_slice[approval_slice.find("F11.11 is confirmed.") + 20 :]
        if "F11.11 is confirmed." in approval_slice
        else ""
    )
    viewer_chrome = (chrome_before + " " + chrome_after).strip()

    approver_shown = APPROVER in viewer_chrome
    modified_shown = MODIFIED_ARG in viewer_chrome or "/etc/passwd" in viewer_chrome
    message_shown = "F11.11_ASSISTANT_MESSAGE" in viewer_chrome

    evidence = (
        f"approval-row chrome (excl. explanation): {viewer_chrome!r} | "
        f"approver={approver_shown} modified={modified_shown} message={message_shown}"
    )

    if not (approver_shown or modified_shown or message_shown):
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "Approval row renders only 'MODIFIED' + explanation. "
                "`event.approver`, `event.modified`, `event.message` are not "
                "surfaced anywhere in the approval UI. (Source confirms: "
                "ApprovalEventView.tsx reads only decision + explanation.)"
            ),
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=evidence,
        notes="One or more of approver/modified/message is shown by the viewer.",
    )
