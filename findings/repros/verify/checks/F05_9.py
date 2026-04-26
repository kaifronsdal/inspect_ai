"""F05.9 — SandboxEventView ExecView ``=== null`` guard misses ``undefined``.

Repro: SandboxEvent(action="exec") with ``cmd`` omitted (Python None →
``exclude_none`` → JSON key absent → JS ``undefined``). The guard
``if (event.cmd === null) return undefined`` does NOT fire for ``undefined``,
so a "Command" heading + empty ``<pre>`` renders.
"""

from checks._util import show_all_events
from harness import VerifyResult, ViewerSession

BATCH = "01-events"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F05.9", tab="transcript", log="F05.9-sandbox")
    show_all_events(session)

    panel = session.event_panel("Sandbox")
    if panel.count() == 0:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=session.text_of("#transcript-contents")[:300],
            notes="No Sandbox event panel found after clearing filter.",
        )
    chev = panel.locator("i.bi-chevron-right")
    if chev.count():
        chev.first.click()
        session.wait_settled(network_idle=False)

    text = panel.inner_text()
    # The repro's output string is rendered under Result; the cmd <pre> should
    # be empty. Inspect HTML: the first <pre> under the Command section.
    pres = panel.locator("pre").all_inner_texts()
    has_command_heading = "COMMAND" in text.upper().split("\n")
    # First <pre> is the cmd cell.
    cmd_pre = pres[0] if pres else "<no-pre>"

    evidence = (
        f"panel text:\n"
        + "\n".join(ln for ln in text.splitlines() if ln.strip())[:350]
        + f"\n--- first <pre> (cmd) text: {cmd_pre!r}"
    )

    if has_command_heading and cmd_pre.strip() == "":
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "`Command` heading rendered with an EMPTY <pre> — the "
                "`event.cmd === null` guard did not catch `undefined`."
            ),
        )
    if not has_command_heading:
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=evidence,
            notes="No Command heading — guard appears to handle undefined.",
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=evidence,
        notes=f"Command heading present but <pre> shows {cmd_pre!r} — not empty.",
    )
