"""F05.5 — ScoreEditEventView hides edited value when it is 0/False/"".

Repro emits three ScoreEditEvents with value=0, value=False, value="". The
truthy check ``{event.edit.value ? … : ""}`` drops the Value row entirely.
"""

from harness import VerifyResult, ViewerSession

BATCH = "01-events"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F05.5", tab="transcript", log="F05.5-score")

    panels = session.page.locator('[id^="event-panel-"]').filter(
        has_text="Edit Score"
    )
    n = panels.count()
    if n < 3:
        # Expand any collapsed solver span first.
        for chev in session.page.locator("i.bi-chevron-right").all():
            chev.click()
            session.wait_settled(network_idle=False)
        panels = session.page.locator('[id^="event-panel-"]').filter(
            has_text="Edit Score"
        )
        n = panels.count()
    if n == 0:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=session.text_of("#transcript-contents")[:300],
            notes="No Edit Score panels found in transcript.",
        )

    rows: list[tuple[int, bool, str]] = []
    for i in range(n):
        p = panels.nth(i)
        chev = p.locator("i.bi-chevron-right")
        if chev.count():
            chev.first.click()
            session.wait_settled(network_idle=False)
        text = p.inner_text()
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        has_value_label = "VALUE" in lines
        # The line right after VALUE, if present.
        after = ""
        if has_value_label:
            j = lines.index("VALUE")
            after = lines[j + 1] if j + 1 < len(lines) else ""
        rows.append((i, has_value_label, after))

    hidden = [i for i, has, _ in rows if not has]
    evidence = "\n".join(
        f"Edit[{i}]: VALUE label present={has}; cell={after!r}" for i, has, after in rows
    )

    if len(hidden) == n:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                f"All {n} Edit Score panels omit the VALUE row entirely — "
                "falsy values (0/False/'') hidden by truthy check."
            ),
        )
    if hidden:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=f"{len(hidden)}/{n} panels hide the Value row (partial).",
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=evidence,
        notes="Every Edit Score panel shows a Value row (falsy handled).",
    )
