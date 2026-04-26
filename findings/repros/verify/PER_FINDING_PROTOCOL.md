# Per-Finding Rigorous Verification Protocol

You are verifying ONE bug repro. Previous batch verification produced several wrong CONFIRMED verdicts (broken repros, misleading instructions, overstated findings). Be **adversarial**: assume the previous verdict may be wrong; assume the repro's embedded `bug_description` may be misleading; assume the original finding may have misread the source.

## Inputs you receive

- A finding ID (e.g. `F02.4`)
- A unique port number
- The batch dir name

## Required reading (in this order)

1. The original finding: grep for your ID in `findings/*.md` (e.g. `rg -A 30 "F02\.4 " findings/0*.md findings/1*.md findings/2*.md findings/3*.md findings/4*.md findings/8*.md findings/9*.md`). Understand the EXACT claim and cited `file:line`.
2. The cited source code at `file:line` in `src/inspect_ai/_view/ts-mono/...`. Does the code actually do what the finding says?
3. The repro task: `findings/repros/tasks/<batch>/<ID>_*.py`. What does its `bug_description` claim you'll observe?
4. The harness: `findings/repros/verify/harness.py` and `findings/repros/verify/HOWTO.md`.
5. Prior verdict: `findings/repros/verify/VERIFICATION.md` row for your ID.

## Verification steps

1. Start a `ViewerSession(log_dir="findings/repros/logs/<batch>", port=<your_port>)`.
2. Navigate to the log + sample + tab + event where the bug should appear. If the bug needs the Debug event filter, switch to it (`checks/_util.py::show_all_events()`).
3. **Take a full-page screenshot** to `findings/repros/verify/artifacts/per-finding/<ID>-page.png`. If the bug is in a specific panel, also screenshot just that panel to `<ID>-panel.png`.
4. **Read the screenshot yourself** (you are multimodal — use the Read tool on the .png). Describe in your own words what you see.
5. Extract `inner_text()` and/or `outerHTML` of the relevant element.
6. **Compare against the claim:**
   - What does the repro's `bug_description.observed` say you should see?
   - What do you ACTUALLY see (from screenshot + DOM)?
   - What does the finding say correct behavior would be?
   - What would a reasonable user expect?

## Verdicts

| Verdict | Meaning |
|---|---|
| `CONFIRMED` | The page shows wrong/missing content exactly as the finding describes, AND a reasonable user would consider it a bug. |
| `CONFIRMED_MINOR` | Technically reproduces but impact is trivial (e.g. cosmetic, or only visible in obscure mode). Recommend severity downgrade. |
| `REPRO_BROKEN` | The .eval doesn't reach the code path / the bug_description points at the wrong thing / can't navigate to the location. The underlying finding may still be valid — say whether source code supports it. |
| `FALSE_POSITIVE` | The page shows CORRECT behavior AND re-reading the source confirms the finding misread the code. |
| `BY_DESIGN` | The behavior matches the finding's "observed" but it's clearly intentional (comments, git blame, or obvious design rationale). |
| `INCONCLUSIVE` | Cannot determine — explain exactly what blocked you. |

## Output

Write `findings/repros/verify/per-finding/<ID>.md`:

```markdown
# <ID> — <short title>

**Prior verdict:** <from VERIFICATION.md>
**New verdict:** <your verdict>
**Batch:** <batch> | **Port:** <port> | **Log:** `<.eval filename>`

## What the finding claims
<1-2 sentences, with file:line>

## What the repro's bug_description says to look for
<quote the observed/expected>

## What I actually observed

**Screenshot:** `artifacts/per-finding/<ID>-page.png`
<Your description of what the screenshot shows>

**DOM evidence:**
```
<inner_text or HTML snippet, ≤30 lines>
```

## Analysis
<Why your verdict. If it differs from prior verdict, explain what the previous check got wrong. If REPRO_BROKEN, say whether the source code still supports the finding. If FALSE_POSITIVE, quote the source showing correct behavior.>

## Recommended action
<One of: keep as-is / downgrade severity to X / fix repro by Y / remove finding>
```

## Gotchas

- Harness imports work via `sys.path` hacks — Pyright errors about `import harness` are cosmetic, ignore them.
- Run scripts via: `cd /home/ubuntu/GitHub/inspect_ai/findings/repros/verify && uv run --with playwright python -c "..."` or write a temp script there.
- `find_log("F20.1")` matches `F20.14` too — use `"F20.1-"` or `"F20.1_"`.
- Default event filter hides `state/store/sandbox/branch/sample_init` — switch to Debug.
- If your port is taken, add 100 and retry.
- Kill the session cleanly (use `with ViewerSession(...) as s:`).
