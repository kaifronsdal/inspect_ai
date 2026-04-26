"""F04.5 — ModelEvent `retries` and `cache` never displayed.

Repro injects a synthetic ModelEvent with retries=3, cache="read". Neither
field is read by ModelEventView.tsx. We assert no `text-style-label` element
inside the event panel reads "Retries" or "Cache" (cache_read / cache_write
usage rows are NOT what we're looking for — those are token-cache, not the
inspect response-cache flag).
"""

from harness import VerifyResult, ViewerSession

BATCH = "01-events"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F04.5", tab="transcript", log="F04.5-model")
    panel = session.event_panel("Model Call")

    subtabs = session.event_subtabs("Model Call")
    labels: set[str] = set()
    title = panel.inner_text().split("\n", 1)[0]

    for tab in subtabs:
        session.click_event_subtab(tab, in_event="Model Call")
        for raw in panel.locator(".text-style-label").all_inner_texts():
            labels.add(raw.strip().upper())

    # Bug-description text and the input message contain the words "retries"/
    # "cache" — those are inside chat-message bodies, not .text-style-label
    # cells, so they don't pollute `labels`.
    has_retries_label = any(lb in {"RETRIES", "RETRY"} for lb in labels)
    has_cache_label = "CACHE" in labels or "CACHED" in labels
    title_mentions = "RETR" in title.upper() or "CACHE" in title.upper()

    evidence = (
        f"panel title: {title!r}\n"
        f"label cells across {subtabs}: {sorted(labels)}\n"
        f"Retries label present: {has_retries_label}; "
        f"Cache label present: {has_cache_label}"
    )

    if not has_retries_label and not has_cache_label and not title_mentions:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "No label/row/badge for `retries` or `cache` in any sub-tab. "
                "Source confirms ModelEventView.tsx never reads either field."
            ),
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=evidence,
        notes="A retries/cache indicator was found — finding may be fixed.",
    )
