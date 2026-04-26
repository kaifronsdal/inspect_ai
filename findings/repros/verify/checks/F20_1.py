"""F20.1 — SampleSummaryView header drops `limit` / `error` / `time`.

Where: Sample detail → the summary header row above the tab strip
(``#sample-heading-*``). The repro hits ``message_limit=2`` so
``SampleSummary.limit == "message"``. The header labels should include
``Limit`` (and ``Time``) but ``resolveSample()`` only reads them when
``isEvalSample(sample)`` (which is never true for the ``SampleSummary``
passed by ``SampleDisplay``).
"""

from harness import VerifyResult, ViewerSession

BATCH = "20-samples"


def check(session: ViewerSession) -> VerifyResult:
    # F20.1 substring also matches F20.14 — disambiguate.
    session.goto_sample("F20.1", log="F20.1-", tab="transcript")

    hdr = session.page.locator('[id^="sample-heading-"]').first
    labels = [
        t.upper() for t in hdr.locator(".text-style-label").all_inner_texts()
    ]
    if not labels:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=hdr.inner_text()[:300],
            notes="No .text-style-label cells found in the sample header.",
        )

    # Confirm the sample really did record a limit (so absence in the header
    # is the bug, not the repro failing to trip it).
    session.goto_sample("F20.1", log="F20.1-", tab="json")
    json_text = session.text_of("#json-contents")
    has_limit_in_data = '"limit":' in json_text and '"message"' in json_text

    evidence = (
        f"header labels: {labels}; "
        f"sample JSON contains limit field: {has_limit_in_data}"
    )

    if not has_limit_in_data:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=evidence,
            notes="Repro did not record a sample limit — regenerate the .eval.",
        )

    if "LIMIT" not in labels and "TIME" not in labels:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "Header shows only Id/Input/Target — no Limit or Time column "
                "even though the sample hit message_limit. resolveSample() "
                "gates these on isEvalSample(), which is false for the "
                "SampleSummary the caller passes."
            ),
        )
    return VerifyResult(
        verdict="NOT_REPRODUCED",
        evidence=evidence,
        notes="Header includes Limit and/or Time — appears fixed.",
    )
