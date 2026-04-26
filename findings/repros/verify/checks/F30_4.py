"""F30.4 — SecondaryBar hidden entirely unless ``status === "success"``.

The F30.4 log has ``status="error"`` and a distinctive task arg
``F30.4_TASK_ARG``. The title-view ``<nav class="navbar">`` should — per the
finding — contain ONLY the PrimaryBar (task/model/status) and NO SecondaryBar
(Dataset / Scorer / Config / Duration).

Compared against a success log (F31.1) in the same batch, whose navbar DOES
contain ``DATASET`` / ``SCORER`` / ``DURATION``.
"""

from pathlib import Path

from harness import VerifyResult, ViewerSession

BATCH = "30-loglist"

ART = Path(__file__).resolve().parents[1] / "artifacts"
SECONDARY_LABELS = ("DATASET", "SCORER", "DURATION")


def check(session: ViewerSession) -> VerifyResult:
    artifacts: list[str] = []

    # Errored log
    session.goto_log("F30.4", tab="samples")
    session.wait_settled(ms=600)
    nav_err = session.text_of("nav.navbar")
    artifacts.append(session.screenshot(ART / "F30.4-error-header.png", selector="nav.navbar"))

    # Success comparator (any successful log in this batch)
    session.goto_log("F31.1", tab="samples")
    session.wait_settled(ms=600)
    nav_ok = session.text_of("nav.navbar")
    artifacts.append(session.screenshot(ART / "F30.4-success-header.png", selector="nav.navbar"))

    err_has = {lbl: lbl in nav_err.upper() for lbl in SECONDARY_LABELS}
    ok_has = {lbl: lbl in nav_ok.upper() for lbl in SECONDARY_LABELS}

    evidence = (
        f"error-log navbar text: {nav_err!r}\n"
        f"success-log navbar text: {nav_ok!r}"
    )[:480]

    if not any(ok_has.values()):
        return VerifyResult(
            "INCONCLUSIVE",
            evidence,
            notes=f"Comparator success log also missing SecondaryBar labels {ok_has} — selector wrong?",
            artifacts=artifacts,
        )

    if not any(err_has.values()) and all(ok_has.values()):
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=evidence,
            notes=(
                f"SecondaryBar labels {SECONDARY_LABELS} absent from errored log's "
                f"header but present on a success log's header. Dataset name, "
                f"task_args (`F30.4_TASK_ARG`) and duration are all in the .eval "
                f"but suppressed by the `status !== 'success'` guard."
            ),
            artifacts=artifacts,
        )
    if any(err_has.values()):
        return VerifyResult(
            "NOT_REPRODUCED",
            evidence,
            notes=f"Errored log header shows {err_has} — SecondaryBar no longer gated on success.",
            artifacts=artifacts,
        )
    return VerifyResult("INCONCLUSIVE", evidence, artifacts=artifacts)
