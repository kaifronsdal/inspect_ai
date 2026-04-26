# Description Accuracy Protocol

You own ONE repro. Your job is **not** to verify whether the bug exists (that's done) — it's to make the repro's `bug_description` text **factually accurate** against what's actually on screen, so a human opening the `.eval` is never confused or misled.

The user has found multiple repros where the banner says things like "click the Summary tab" when there IS no Summary tab, or "expand X" when X isn't expandable. Fix all such inaccuracies.

## Inputs

- Finding ID, batch dir, port number
- Prior verdict from `findings/repros/verify/per-finding/<ID>.md`

## Required reading

1. `findings/repros/verify/per-finding/<ID>.md` — the prior verdict + evidence
2. `findings/repros/tasks/<batch>/<ID>_*.py` — the task file (contains `DESC = bug_description(...)`)
3. `findings/repros/_common.py` — `bug_description()` signature, `emit_bug_banner()`
4. `findings/repros/verify/harness.py` — `ViewerSession` API

## Steps

### 1. Open and observe

Start `ViewerSession(log_dir="findings/repros/logs/<batch>", port=<port>)`. Navigate to the sample's Transcript tab under DEFAULT filter.

**Take a full-page screenshot** to `findings/repros/verify/artifacts/accuracy/<ID>-before.png` and READ it with the Read tool.

### 2. Check the banner is visible

Is the `INFO: BUG-REPRO` panel visible and expanded near the top? If it's hidden inside a collapsed `SUB-AGENT: BANNER` span (the `chain()` problem), you MUST fix the task file: move `emit_bug_banner(DESC)` into the body of the main solver instead of using a separate `chain(banner(), ...)` step. If the task only uses `solver=generate()` with no custom solver, replace it with:
```python
@solver
def repro_solver():
    async def solve(state, generate):
        emit_bug_banner(DESC)
        return await generate(state)
    return solve
```

### 3. Audit every statement in the description

Read the current `DESC` text (in the task .py file). For EACH claim in `where_to_look`, `observed`, `expected`, and `extra`:
- Is the navigation path correct? (e.g. "Transcript tab → expand Model Call → click Tools tab" — does each step exist and work?)
- Are tab/panel/button names exactly what appears on screen?
- Are claims about "expandable" / "collapsible" / "has subtabs" / "shows X rows" accurate?
- Are sentinel strings actually present where claimed?
- Does it reference the Debug filter when needed?

Use `inner_text()` / `outerHTML` / screenshot reading to verify each claim. List every inaccuracy.

### 4. Handle verdict-specific cases

- **FALSE_POSITIVE** (F03.2, F03.3, F20.6, F31.6): rewrite `DESC` to LEAD with `**✅ FALSE POSITIVE — NOT A BUG.**` and explain why behavior is correct. Keep `where_to_look` so user can verify it works.
- **BY_DESIGN** (F10.6): lead with `**✅ BY DESIGN — NOT A BUG.**` + design-doc reference.
- **REPRO_BROKEN / scout-only** (F10.2, F11.8): lead with `**⚠️ SCOUT-ONLY — not reproducible in inspect viewer.**`
- **CONFIRMED_MINOR**: keep as bug but add `**Note:** impact is minor — <reason>` in `extra`.

### 5. Rewrite and regenerate

Edit the task file's `DESC = bug_description(...)` call with corrected text. Keep it concise — accurate beats comprehensive. Then:
```bash
rm findings/repros/logs/<batch>/*<ID>-*.eval   # use <ID>- pattern to avoid F20.1 matching F20.14
./findings/repros/run.sh findings/repros/tasks/<batch>/<ID>_*.py <batch>
```

### 6. Re-verify

Reopen the new `.eval`, screenshot to `findings/repros/verify/artifacts/accuracy/<ID>-after.png`, READ it, confirm:
- Banner visible at top under Default filter (not inside collapsed sub-agent)
- Every navigation step in `where_to_look` works as written
- `observed` matches what's on screen

### 7. Output

Write `findings/repros/verify/accuracy/<ID>.md`:
```markdown
# <ID> — Description Accuracy

**Verdict (unchanged):** <from per-finding/>
**Banner visible at Default:** yes/no → fixed
**Inaccuracies found:** N

## Inaccuracies fixed
1. "<old text>" → "<new text>" — <why>
2. ...

## Before/after screenshots
- before: artifacts/accuracy/<ID>-before.png
- after: artifacts/accuracy/<ID>-after.png
```

## Gotchas

- Run from `cd /home/ubuntu/GitHub/inspect_ai/findings/repros/verify && uv run --with playwright python ...`
- Use `with ViewerSession(...) as s:` for cleanup
- `find_log("F20.1")` matches `F20.14` — use `"F20.1-"` or full slug
- Port collision: add 100 and retry
- Clean up any `_tmp*.py` you create
