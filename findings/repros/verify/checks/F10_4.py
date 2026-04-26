"""F10.4 — Citation <sup> numbers don't match the footnote list.

Where: Messages tab → assistant turn with two ContentText blocks, each with
two UrlCitation. Buggy claim: BLOCK 2 superscripts restart at 1 while the
footnote list runs 1–4.

Source check (MessageContent.tsx:320-371): consecutive ContentText blocks are
collapsed into ONE `collect()` run. Within that run, *end-cites* (no positional
``cited_text=[start,end]``) use a shared ``++citeCount`` → 1,2,3,4. Only
*positional* cites use ``positionalCites.length - i`` (per-block, no citeCount
offset). The repro uses ``UrlCitation(cited_text="cited text for X")`` —
strings, so all cites are end-cites → numbering is correct.
"""

import re

from harness import VerifyResult, ViewerSession

BATCH = "10-chat"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F10.4", tab="messages")
    session.wait_settled(ms=600)

    # Inline superscripts. The bug-description markdown also produces a
    # <sup> via the `<sup>` literal in the title — filter to numeric-only.
    sups = [
        s
        for s in session.page.locator("#messages-contents sup").all_inner_texts()
        if re.fullmatch(r"[\d, ]+", s)
    ]
    if not sups:
        return VerifyResult(
            "INCONCLUSIVE",
            evidence=f"<sup> texts: {session.page.locator('sup').all_inner_texts()}",
            notes="No numeric <sup> elements found in messages tab.",
        )

    # Footnote list: MessageCitations renders <span>{index+1}</span> + link.
    text = session.text_of("#messages-contents")
    foot_order = []
    for label in ["CITE-A", "CITE-B", "CITE-C", "CITE-D"]:
        m = re.search(rf"\n(\d+)\n\[{re.escape(label)}", text)
        foot_order.append((label, m.group(1) if m else "?"))

    inline = ",".join(sups)  # e.g. "1,2,3,4" or "1,2,1,2"
    foot = " ".join(f"{n}={lbl}" for lbl, n in foot_order)
    evidence = f"inline <sup>: [{inline}] | footnotes: [{foot}]"

    # Mismatch = any inline number repeats while footnotes run 1..4, OR the
    # max inline number ≠ number of footnote entries.
    inline_nums = re.findall(r"\d+", inline)
    foot_nums = [n for _, n in foot_order]
    if inline_nums == ["1", "2", "3", "4"] and foot_nums == ["1", "2", "3", "4"]:
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=evidence,
            notes=(
                "Superscripts run 1,2,3,4 and match footnotes 1..4 exactly. "
                "REPRO IS WRONG: it uses string `cited_text` → all citations "
                "are non-positional end-cites, which share `++citeCount` "
                "across coalesced blocks (correct). The per-block-reset bug "
                "only fires for *positional* cites (`cited_text=[start,end]`) "
                "via `positionalCites.length - i`. Finding is valid for "
                "positional cites; this .eval does not exercise that branch."
            ),
        )
    if len(set(inline_nums)) < len(inline_nums) or inline_nums != foot_nums:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes="Inline superscripts disagree with footnote numbering.",
        )
    return VerifyResult("INCONCLUSIVE", evidence=evidence)
