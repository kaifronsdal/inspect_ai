"""F11.3 — Bare ContentImage tool result is JSON.stringify'd, not rendered as <img>.

Where: Transcript tab → two Tool events: ``screenshot_bare`` (result is a bare
ContentImage object) vs ``screenshot_list`` (same image, list-wrapped).

Buggy source (ToolCallView.tsx:normalizeContent): ``if (Array.isArray(output))
return output; else … JSON.stringify(output)``. The bare object falls to the
stringify branch.

Nuance discovered during verification: the stringified JSON is then handed to
``ToolTextOutput`` which detects valid JSON and re-renders it via
``JsonMessageContent`` (RecordTree). So the *visible* result is a key/value
tree (`type: image / image: <img> / detail: auto`), not the raw JSON text the
finding describes — but it is still NOT a clean ``<img class="contentImage">``
like the list-wrapped control.
"""

from harness import VerifyResult, ViewerSession

BATCH = "11-tools"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F11.3", tab="transcript", log="F11.3-")
    session.wait_settled(ms=800)

    bare = session.event_panel("screenshot_bare")
    ctrl = session.event_panel("screenshot_list")
    if bare.count() == 0 or ctrl.count() == 0:
        return VerifyResult(
            "INCONCLUSIVE",
            evidence="",
            notes="screenshot_bare / screenshot_list panels not found.",
        )

    bare_html = bare.evaluate("el => el.outerHTML")
    ctrl_html = ctrl.evaluate("el => el.outerHTML")
    bare_text = bare.inner_text()

    # Control: list-wrapped → rendered as a content image.
    ctrl_is_img = "_contentImage_" in ctrl_html and "record-tree-key" not in ctrl_html

    # Bug signatures for the bare case:
    raw_json = '{"type":"image"' in bare_text or '"image":"data:' in bare_text
    record_tree = "record-tree-key" in bare_html or (
        "type:" in bare_text and "detail:" in bare_text
    )
    clean_img = "_contentImage_" in bare_html and not record_tree and not raw_json

    evidence = (
        f"bare: raw_json_text={raw_json}, record_tree={record_tree}, "
        f"clean_contentImage={clean_img} | control: clean_contentImage={ctrl_is_img}"
    )

    if clean_img:
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=evidence,
            notes="Bare ContentImage renders as a content image, same as control.",
        )
    if not ctrl_is_img:
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=evidence,
            notes="Control (list-wrapped) didn't render as <img> either.",
        )
    if raw_json:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes="Bare object stringified to literal JSON text, as the finding describes.",
        )
    # record_tree path — still confirms the underlying normalizeContent bug,
    # but the finding's description of *observed* behaviour is inaccurate.
    return VerifyResult(
        verdict="CONFIRMED",
        evidence=evidence + f" | bare panel text: {bare_text!r}",
        notes=(
            "Bare ContentImage is NOT rendered as a content image — it goes "
            "through normalizeContent's JSON.stringify branch (bug confirmed). "
            "However, the *visible* output is a RecordTree (JsonMessageContent "
            "re-parses the JSON string), not the raw "
            '`{"type":"image",…}` text the finding\'s Observed section claims. '
            "Net effect is the same: the user sees `type:/image:/detail:` "
            "key-value rows instead of an inline image like the list-wrapped "
            "control."
        ),
    )
