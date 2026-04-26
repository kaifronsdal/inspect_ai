"""F20.14 — Object/List score descriptors skip the numeric formatter for `0`.

Where: sample list → ``list_scorer`` score column. Value is
``[0.0, 0.333333, 1.0]``.

Buggy code (ObjectScoreDescriptor.tsx / ListScoreDescriptor.tsx)::

    value && isNumeric(value) ? formatPrettyDecimal(...) : String(value)

For ``0`` the ``&&`` short-circuits → ``"0"``; for ``1`` it formats →
``"1.0"``; for ``0.333333`` → ``"0.333"``. The cell shows the inconsistency
side-by-side.
"""

import re

from harness import VerifyResult, ViewerSession

BATCH = "20-samples"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_log("F20.14", tab="samples")
    session.wait_settled()

    cells = session.page.locator('.ag-cell[col-id="score-0"]')
    if cells.count() == 0:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence="(no score-0 cells found in sample list)",
            notes="Sample list did not render — repro may be single-sample.",
        )
    cell_text = cells.first.inner_text().strip()

    # Parse the [a, b, c] list.
    m = re.match(r"\[\s*([^,\]]+),\s*([^,\]]+),\s*([^,\]]+)\s*\]", cell_text)
    if not m:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=f"score cell text: {cell_text!r}",
            notes="List-score cell did not match `[a, b, c]` shape.",
        )
    zero_tok, third_tok, one_tok = (m.group(i).strip() for i in (1, 2, 3))

    evidence = (
        f"list_scorer cell: {cell_text!r}  →  "
        f"zero={zero_tok!r}, third={third_tok!r}, one={one_tok!r}"
    )

    # Bug: one_tok formatted with decimal ("1.0") but zero_tok not ("0").
    one_has_dec = "." in one_tok
    zero_has_dec = "." in zero_tok

    if one_has_dec and not zero_has_dec:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                "0 renders unformatted while 1 → '1.0' and 0.333333 → "
                "'0.333' via formatPrettyDecimal. The `value && isNumeric` "
                "short-circuit drops 0 (and `false`) onto the String() path."
            ),
        )
    if one_has_dec == zero_has_dec:
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=evidence,
            notes="0 and 1 are formatted consistently.",
        )
    return VerifyResult(
        verdict="INCONCLUSIVE",
        evidence=evidence,
        notes="Unexpected formatting pattern.",
    )
