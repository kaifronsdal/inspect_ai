"""F01.2 — ToolChoiceView renders literal `` `$name()` `` instead of ``name()``.

Where: Transcript → Model Call event → Tools sub-tab → "Tool Choice" row.
The repro forces ``tool_choice = ToolFunction(name="my_forced_tool")``.

Buggy source (ModelEventView.tsx)::

    return <code>`${toolChoice.name}()`</code>;

JSX text ≠ template literal, so the backticks and ``$`` render verbatim.
"""

from harness import VerifyResult, ViewerSession

BATCH = "01-events"


def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F01.2", tab="transcript")

    subtabs = session.event_subtabs("Model Call")
    if not any(t.strip().lower() == "tools" for t in subtabs):
        return VerifyResult(
            verdict="INCONCLUSIVE",
            evidence=f"Model-event sub-tabs: {subtabs}",
            notes=(
                "No 'Tools' sub-tab on the Model Call event. The repro defines "
                "two tools, but `tool_choice=ToolFunction(...)` makes inspect "
                "filter event.tools down to the single forced tool — so F04.2 "
                "(the `> 1` guard) hides the tab and the Tool Choice row is "
                "unreachable. **Repro needs fixing**: use tool_choice='auto' "
                "with 2+ tools, or wait until F04.2 is patched."
            ),
        )

    session.click_event_subtab("Tools", in_event="Model Call")
    panel = session.event_panel("Model Call")
    panel_text = panel.inner_text()

    # The buggy <code> element renders literally "`$my_forced_tool()`".
    # inner_text strips the <code> tag but keeps the backticks and dollar.
    has_literal_dollar = (
        "`$my_forced_tool()`" in panel_text or "$my_forced_tool()" in panel_text
    )
    has_clean = "my_forced_tool()" in panel_text and "$my_forced_tool" not in panel_text

    # Evidence: the <code> element under the Tool Choice row.
    code = panel.locator("code").all_inner_texts()
    lines = [ln.strip() for ln in panel_text.splitlines() if ln.strip()]
    tc_idx = next((i for i, ln in enumerate(lines) if ln.upper() == "TOOL CHOICE"), -1)
    tc_cell = lines[tc_idx + 1] if 0 <= tc_idx < len(lines) - 1 else "<not-found>"
    line = f"Tool Choice cell: {tc_cell!r}; <code> elements: {code}"

    if has_literal_dollar:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=f"Tool Choice row renders: {line!r}",
            notes="Literal backtick + `$` visible — JSX-text-as-template-literal bug confirmed.",
        )
    if has_clean:
        return VerifyResult(
            verdict="NOT_REPRODUCED",
            evidence=f"Tool Choice row renders: {line!r}",
            notes="Renders cleanly as `my_forced_tool()` — bug appears fixed.",
        )
    return VerifyResult(
        verdict="INCONCLUSIVE",
        evidence=f"Tools sub-tab text:\n{panel_text[:500]}",
        notes="Could not find the forced tool name in the Tools tab at all.",
    )
