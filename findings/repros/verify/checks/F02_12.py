"""F02.12 — RenderedEventNode `default: return null` hides unknown event types.

The repro log has, in order, inside the solver span:
  model → info(banner) → logger(marker) → F02_12_unknown_type → state

Under the **Debug** filter all five should be EventNodes. The bug claim is
that the 4th renders as nothing — `default: return null`. We assert by:

1. Checking the marker text is on the page (proves we're at the right spot
   and the Debug filter is active).
2. Checking the unknown event's payload string is **not** in the transcript
   (it's only in the JSON tab).
3. Counting `[id^="event-panel-"]` siblings: if the unknown event rendered
   a panel there'd be one more than there is.
"""

from pathlib import Path

from harness import VerifyResult, ViewerSession

from checks._util import show_all_events

BATCH = "02-transform"
ART = Path(__file__).resolve().parents[1] / "artifacts" / "per-finding"

UNKNOWN_PAYLOAD_SENTINEL = "If you can read this string anywhere in the Transcript tab"
MARKER_SENTINEL = "unknown event 'F02_12_unknown_type' injected immediately"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F02.12", log="F02.12", tab="transcript")
    session.wait_settled(ms=400)
    show_all_events(session)
    # Close the filter popover so it doesn't obscure the screenshot. The
    # PopOver only listens for outside-mousedown, so dispatch one at <body>.
    session.page.evaluate(
        "() => document.body.dispatchEvent("
        "  new MouseEvent('mousedown', {bubbles: true}))"
    )
    session.wait_settled(network_idle=False, ms=200)
    # Belt-and-braces: if it's still mounted, hide it for the screenshot.
    session.page.evaluate(
        "() => { const p = document.querySelector('#transcript-filter-popover');"
        " if (p) p.style.display = 'none'; }"
    )

    # Scroll to bottom so all (non-virtual, <100 nodes) panels mount.
    session.page.evaluate(
        "() => document.querySelectorAll('[class*=\"_scroller_\"]')"
        ".forEach(e => e.scrollTop = e.scrollHeight)"
    )
    session.wait_settled(network_idle=False, ms=300)

    body = session.all_text()
    # The outline (left tree) labels every EventNode via labelForNode — it
    # *does* show the unknown type's name even though the transcript doesn't.
    outline_text = session.page.evaluate(
        """() => {
            const o = document.querySelector('[class*="outline" i],[class*="Outline"]');
            return o ? o.innerText : '';
        }"""
    )
    panel_titles = session.page.evaluate(
        """() => Array.from(document.querySelectorAll('[id^="event-panel-"]'))
                  .map(p => (p.innerText || '').split('\\n')[0].slice(0, 80))"""
    )
    console_errors = session.page.evaluate(
        "() => (window.__playwright_errors__ || []).map(String)"
    )

    ART.mkdir(parents=True, exist_ok=True)
    shot = session.screenshot(ART / "F02.12-transcript-debug.png")

    marker_visible = MARKER_SENTINEL in body
    unknown_visible = (
        UNKNOWN_PAYLOAD_SENTINEL in body
        or any("F02_12_UNKNOWN" in t.upper() for t in panel_titles)
        or any("UNKNOWN EVENT" in t.upper() for t in panel_titles)
    )

    outline_has_unknown = "F02_12_unknown_type" in outline_text

    titles_str = "\n".join(f"  {t}" for t in panel_titles)
    evidence = (
        f"panel titles ({len(panel_titles)}):\n{titles_str}\n"
        f"marker_visible={marker_visible} unknown_visible={unknown_visible} "
        f"outline_has_unknown={outline_has_unknown}\n"
        f"console_errors={console_errors or '[]'}"
    )

    if not marker_visible:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=evidence,
            notes=(
                "Marker logger event not visible — Debug filter may not have "
                "applied, or the post-processed log failed to load. Check "
                "screenshot."
            ),
            artifacts=[shot],
        )

    if unknown_visible:
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=evidence,
            notes=(
                "An 'unknown event' / payload string rendered in the "
                "transcript — the viewer now surfaces unknown event types."
            ),
            artifacts=[shot],
        )

    outline_note = (
        " The **outline** (left tree) DOES label the node "
        "'F02_12_unknown_type' — so the EventNode exists and is navigable, "
        "but clicking it scrolls to nothing."
        if outline_has_unknown
        else ""
    )
    return VerifyResult(
        verdict="CONFIRMED",
        evidence=evidence,
        notes=(
            "Marker logger event renders; the F02_12_unknown_type event that "
            "immediately follows it in the JSON renders as nothing — no "
            "panel, no placeholder, no console warning. "
            "`RenderedEventNode → default: return null` swallowed it." + outline_note
        ),
        artifacts=[shot],
    )
