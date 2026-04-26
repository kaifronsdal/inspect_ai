"""F40.5 — ``web_search`` renderer returns array → fails ``isValidElement`` → JSON fallback.

Repro puts a ``web_search`` key (``{query, results:[...]}``) in
``sample.metadata``. Finding claims that wherever this flows through
``RenderedContent``, the custom renderer's ``ReactNode[]`` is rejected by
``isValidElement`` and the dispatcher falls through to ``JSON.stringify``.

Surfaces probed:
  1. Sample → Metadata tab (RecordTree).
  2. Transcript → Sample Init event → Metadata sub-tab (MetaDataGrid).

CONFIRMED iff a raw ``{"query":...}`` JSON string appears (the fallback
``<span>{JSON.stringify(value)}</span>`` output) where a formatted
search-icon + ``<a>`` links block was expected.
"""

from harness import VerifyResult, ViewerSession

BATCH = "40-content"

RAW_JSON_MARKER = '{"query":'
FORMATTED_LINK = "https://example.com/result-1"


def check(session: ViewerSession) -> VerifyResult:
    notes: list[str] = []

    # ---- Surface 1: sample Metadata tab (RecordTree) -------------------
    session.goto_sample("F40.5", tab="metadata")
    session.wait_settled(ms=500)
    md_text = session.text_of("#metadata-contents")
    md_links = session.page.locator(
        "#metadata-contents a[href*='example.com']"
    ).count()
    notes.append(
        f"[metadata tab] raw-json={RAW_JSON_MARKER in md_text}, "
        f"formatted-links={md_links}, contains 'web_search'={'web_search' in md_text}"
    )

    # Collapse the web_search node so RecordTree passes its summary value
    # through RenderedContent.
    ws_row = (
        session.page.locator(".record-tree-key")
        .filter(has_text="web_search")
        .first
    )
    if ws_row.count():
        ws_row.locator("i").first.click()
        session.wait_settled(ms=300, network_idle=False)
    md_collapsed = session.text_of("#metadata-contents")
    notes.append(
        f"[metadata tab, web_search collapsed] value cell: "
        f"{md_collapsed.split('web_search:')[-1].strip()[:60]!r}"
    )

    # ---- Surface 2: Transcript → Sample Init → Metadata sub-tab --------
    session.goto_sample("F40.5", tab="transcript")
    session.wait_settled(ms=500)
    panel_titles = session.page.locator('[id^="event-panel-"]').evaluate_all(
        "els => els.map(e => e.innerText.split('\\n')[0])"
    )
    notes.append(f"[transcript] event-panel titles: {panel_titles}")

    # Any surface produced raw JSON?
    if RAW_JSON_MARKER in md_text or RAW_JSON_MARKER in md_collapsed:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence="; ".join(notes)[:480],
            notes="web_search record rendered as raw JSON.stringify fallback.",
        )

    # Any surface produced the formatted renderer output?
    if md_links > 0:
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence="; ".join(notes)[:480],
            notes="web_search rendered as formatted links — renderer output now accepted.",
        )

    # Neither: repro never reaches the web_search renderer with the object.
    return VerifyResult(
        verdict="INCONCLUSIVE",
        evidence="; ".join(notes)[:480],
        notes=(
            "Repro does not reach the bug location. (a) Sample Metadata tab uses "
            "RecordTree, which flattens objects to child rows and only passes the "
            "summary string 'Object(2)' to RenderedContent on collapse — "
            "`typeof 'Object(2)' === 'object'` is false so web_search.canRender "
            "never matches. (b) The Transcript view does not render a Sample Init "
            "event panel for this span-based log, so the SampleInitEventView → "
            "MetaDataGrid path is unreachable. "
            "Source defect IS real (RenderedContent.tsx:73 — "
            "`isValidElement([])===false`; web_search renderer at :260 returns "
            "ReactNode[]), but no surface in the live viewer routes a "
            "`{name:'web_search', value:object}` entry through it. Matches the "
            "finding's own open question: renderer may be 'doubly dead'."
        ),
    )
