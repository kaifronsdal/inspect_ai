# Re-audit of structural/positional verdicts

**Date:** 2026-04-24
**Trigger:** User's manual screenshot of F02.4 appeared to show correct rendering (GRANDCHILD one level under CHILD), contradicting the CONFIRMED verdict. This re-audit (a) root-causes that disagreement and (b) adversarially re-verifies every other verdict that relies on depth / indentation / tree-order / element-position evidence.

**Method:** For each finding, (1) re-read the cited source line(s) on `main`; (2) take a fresh screenshot via the harness on port 7585; (3) measure pixel `boundingBox().x` offsets and/or `data-depth` attributes; (4) compare against the finding's claim. A verdict survives only if **both** the source matches the claim **and** the pixels show the wrong rendering.

**Artifacts:** `findings/repros/verify/artifacts/reaudit/`
**Scripts:** `reaudit_F02_4.py`, `reaudit_structural.py`, `reaudit_part2.py`, `reaudit_shots.py`

---

## Part 1 — F02.4 root cause

### What the check measured

`checks/F02_4.py` reads the outline's `data-depth` attribute (set directly from `node.depth` at `OutlineRow.tsx:76`) and compares CHILD vs GRANDCHILD. It found `CHILD@d1, GRANDCHILD@d3` → gap of 2 → CONFIRMED.

### What the source says

`transform.ts:203-208`:
```ts
const unwrapNode = (node: EventNode): EventNode[] => {
  return node.children.map((child) => {
    child.depth = node.depth;     // direct children only — no recursion
    return child;
  });
};
```
The bug is real: `unwrapNode` re-depths only immediate children. Contrast `discardNode` (line 223) which uses recursive `reduceDepth`.

### Does the repro trigger `unwrap_main`?

Yes. The `.eval` (dumped via `read_eval_log`) contains `span_begin name='WRAPPER_type_main_gets_unwrapped' type='main'`, which matches `transformers()[0]` (`node.event.type === "main"`). The repro explicitly creates this — Python never emits `type="main"` organically (F02.18).

### Pixel measurements (port 7585, viewport 1400×1000)

| Surface | Element | x (px) | Δ from previous | depth |
|---|---|---:|---:|---:|
| Outline | `nested_under_main` | 21.7 | — | 0 |
| Outline | `CHILD_after_unwrap` | 31.3 | **+9.6** | 1 |
| Outline | `GRANDCHILD` | 50.5 | **+19.2** ← 2× | 3 |
| Outline | `1 turn` | 60.1 | +9.6 | 4 |
| Transcript | `SOLVER: NESTED_UNDER_MAIN` | 464.0 | — | 0 |
| Transcript | `CHILD_AFTER_UNWRAP` | 475.2 | +11.2 (0.7em) | 1 |
| Transcript | `INFO` (CHILD's child) | 507.2 | **+32.0** ← 2× | 3 |
| Transcript | `GRANDCHILD` | 507.2 | +0 | 3 |
| Transcript | `INFO` (GRANDCHILD's child) | 523.2 | **+16.0** | 4 |
| Transcript | `MODEL CALL` | 523.2 | +0 | 4 |

One outline indent unit = 9.6 px (`0.75em` @ 12.8 px/em, `OutlineRow.tsx:57`). One transcript indent unit (depth>1) = 16 px (`1em`, `TranscriptVirtualListComponent.tsx:178`). The CHILD→GRANDCHILD step is **two units** in both surfaces; every other parent→child step is one unit. See `artifacts/reaudit/F02.4-outline-zoom.png` — the double-width gap between CHILD and GRANDCHILD is visible by eye.

### Why the user's screenshot looked "correct"

The repro's `where_to_look` / `observed` / `expected` text is **wrong about the observable**. It says:

> Observed: GRANDCHILD … is indented **one extra level relative to its sibling Info event**.
> Expected: GRANDCHILD should sit at depth 2, **flush with the sibling Info event** directly above it.

But GRANDCHILD and its sibling INFO are at the **same** depth (both `d3`, both `x=507.2`). They're flush — exactly what the "expected" text describes — so a user following those instructions concludes "rendering is correct".

The actual observable is different: `unwrapNode` shifts CHILD from d2→d1 but leaves **all of CHILD's descendants** untouched, so the sibling INFO **and** GRANDCHILD **and** everything below are *all* one level too deep relative to CHILD. The bug shows up as a **double-width indent step between CHILD and its children**, not as a difference between GRANDCHILD and its sibling.

### Verdict

**F02.4 stays CONFIRMED.** None of (a) FALSE_POSITIVE, (b) repro doesn't trigger path, (c) check measured wrong thing apply. The check measured the right thing (`data-depth` 1 vs 3), the source has the bug, and pixels confirm a 2× indent step. The disagreement was caused by **incorrect verification instructions in the repro task** (`tasks/02-transform/F02.4_unwrap_main_grandchild_depth.py:62-70`), which describe a comparison (GRANDCHILD vs sibling INFO) that does **not** distinguish bug from no-bug.

### Repro fix needed

`tasks/02-transform/F02.4_unwrap_main_grandchild_depth.py` — rewrite `observed` / `expected` / `where_to_look`:

> **Where to look:** Outline (left panel) — measure indent of CHILD vs GRANDCHILD. Or transcript: compare the indent step `CHILD → its first child` against the step `GRANDCHILD → its first child`.
> **Observed:** CHILD is at depth 1; *every* descendant of CHILD (sibling INFO, GRANDCHILD, …) is at depth ≥3. The indent step from CHILD to its children is **two** units; every other parent→child step is one unit.
> **Expected:** CHILD's children at depth 2 (one unit in from CHILD).

---

## Part 2 — Re-audit of structural verdicts

| ID | Old | New | Source matches finding? | Pixels/screenshot show wrong rendering? | Reasoning |
|---|---|---|---|---|---|
| **F02.1** | CONFIRMED | **CONFIRMED** | ✅ `fixups.ts:128` `parent_id:null`, `:132` events pushed unmodified, `treeify.ts:164-166` parents by original `span_id` | ✅ 3× `SANDBOX:` panels at `x=121` (same as siblings), no `Sandbox Events` group panel; `kSandboxSignalName` special-casing in `OutlineRow.tsx:166`/`SpanEventView` proves grouping is intended | Not by-design: `groupSandboxEvents` *creates* synthetic span markers in span mode (lines 127-134) — clearly intends to group but the wiring is broken. `artifacts/reaudit/F02.1-debug-filter.png` |
| **F02.2 / F02.3** | CONFIRMED | **CONFIRMED** | ✅ `treeify.ts:192` `id: kBeginScorerId`; `:58` `spanNodes.set(event.id, …)`; `:210` reparents to `kScorersSpanId`; `:159` `spanNodes.get(parentId)` → miss. `:247` `!hasCollectedScorers` blocks 2nd scorer. | ✅ Outline: `scorer_ONE@d0/x=21.7`, `scorer_TWO@d0/x=21.7`, no `scorers` row. Transcript: both `SCORER:` panels at `x=415` (depth 0). | Repro verified to fire `injectScorersSpan`: scorer spans have `parent_id=None` (so `‖ kScorersSpanId` kicks in) and there is no `type='scorers'` span in the log (so the line-241 bail-out doesn't fire). `artifacts/reaudit/F02.2-F02.3-transcript.png` |
| **F02.4** | CONFIRMED | **CONFIRMED** | ✅ `transform.ts:203-208` no recursion | ✅ CHILD→GRANDCHILD = 19.2 px (outline) / 32 px (transcript) = **2×** the unit step | See Part 1. **Repro `observed`/`expected` text needs rewrite.** |
| **F02.5** | CONFIRMED | **CONFIRMED** | ✅ `transform.ts:219` `reduceDepth(newNode.children, 2)`; `:233` recursion hard-codes `1` | ✅ `TOOL: TRANSFER_TO_SUBAGENT` @ `x=472.0`, `AGENT: …` @ `x=472.0` — child flush with parent. AGENT's children @ `x=483.2` (one unit, not two — secondary "+2 jump" claim still not observed; `discard_solvers_span` applies a uniform −1 that masks it) | Primary observable (tool & agent same indent) is unambiguous. `artifacts/reaudit/F02.5-transcript.png` |
| **F05.1** | CONFIRMED | **CONFIRMED** | ✅ `StateEventView.tsx:294-301` — `current = current[key]` is inside `if (key && !(key in current))` | ✅ Diff renders `{ LOOK_HERE: { nested_key: "BEFORE"→"AFTER" } }` at the **root** — `metadata` key is absent entirely. `toplevel_keys=['LOOK_HERE']`, `ancestors=[]`. | The patch op is `{op:'replace', path:'/metadata/LOOK_HERE/nested_key'}`. `initializeArrays` creates `before.metadata.LOOK_HERE={}` first, so `'metadata' in before` is true → `setPath` skips the advance → writes `before.LOOK_HERE.nested_key`. `before.metadata` and `after.metadata` are then identical (`{LOOK_HERE:{}}`) so `metadata` doesn't appear in the diff at all. **`ancestors=[]` is exactly the bug signature**, not a measurement artefact. `artifacts/reaudit/F05.1-state-diff.png` |
| **F10.7** | CONFIRMED | **CONFIRMED** *(behaviour is by-design; side-effects are the finding)* | ✅ `messages.ts:62-105` — collects all system messages, builds one synthetic `id:"sys-message-6815A84B062A"` with `metadata:null`, `unshift`s it. Comment "Collapse system messages" + present since initial commit (`3f5bf2b3a`) ⇒ **merging is intentional design**. | ✅ 1 SYSTEM header, 5 rows (expected 7). `SYSTEM MSG #2` (pos 176) and `#3` (pos 296) both render **before** `Assistant turn A` (pos 1192). | The finding's category is `event-display`, not `correctness`; it documents *consequences* of the design (lost ids/metadata, mid-stream injections hoisted to row 1). Those consequences are real and observed. CONFIRMED is correct for "the described behaviour occurs"; recommend the finding text add *"intentional collapse with the following side-effects:"* so it isn't read as an accidental bug. `artifacts/reaudit/F10.7-messages.png` |
| **F30.2** | CONFIRMED | **CONFIRMED** | ✅ `hooks.tsx:222` list error→`ApplicationIcons.error`; `:226` cancelled→`ApplicationIcons.cancelled`; `StatusPanel.tsx:25` header error→`ApplicationIcons.logging.error`. `icons.ts:70` `error="bi-exclamation-circle-fill"`; `:36` `cancelled="bi-x-circle"`; `:7` `logging.error="bi-x-circle"`. | ✅ List screenshot: F30.2 row shows red filled `!` circle. Header screenshot: same log shows `⊗` (x-circle) "TASK FAILED". | **Not** "different but semantically fine": `bi-x-circle` means *cancelled* in the list and *error* in the header — the same glyph carries opposite meanings in adjacent surfaces. `artifacts/reaudit/F30.2-list-row.png`, `F30.2-detail-navbar.png` |
| **F90.2** | CONFIRMED | **CONFIRMED** *(with clarification)* | ✅ `apps/inspect/src/utils/format.ts:8` → `` `${formatPrettyDecimal(s,1)} sec` `` (1 decimal). `packages/util/src/format.ts:35` → `` `${Math.round(s)} sec` `` (integer). Two distinct `formatTime` impls. | ✅ Metadata "Working" = `"2.8 sec"` (= 2.818 s); EventTimingPanel "Working Time → Start" = `"3 sec"` (= 2.812 s); log-list Duration = `"3.0 sec"` (≈ 3.0 s wall-clock). | The user's concern *"2.8 vs 3.0 are different VALUES, not formats"* applies to **(A) vs (C)** — those are genuinely different durations (sample working-time vs eval wall-clock). But **(A) vs (B)** are the same quantity (2.818 s vs 2.812 s, Δ=6 ms) rendered through two formatters with different precision. (A) vs (B) alone proves the inconsistency; (C) is the same formatter as (A) on a different value and adds nothing. `artifacts/reaudit/F90.2-*.png` |

**Net verdict changes: 0.** All eight structural verdicts survive adversarial re-verification. The F02.4 disagreement was a **repro-documentation error**, not a check error.

---

## Part 3 — Spot-check of text-presence verdicts

Re-ran on port 7585 to confirm the harness is not systematically broken:

| ID | Re-run verdict | Evidence |
|---|---|---|
| F01.2 | CONFIRMED | Tool Choice cell: `` '`$my_forced_tool()`' `` |
| F01.3 | CONFIRMED | `VALUE → 'UNCHANGED'`, `EXPLANATION → 'UNCHANGED'` |
| F04.8 | CONFIRMED | `INPUT='' \| CACHE_READ='100' \| OUTPUT='50'` |
| F11.4 | CONFIRMED | `<h1>This line should be PLAIN TEXT…</h1>` rendered |
| F21.2 | CONFIRMED | autocomplete contains `'undefined'`, none of `good/bad/ugly` |

5/5 stable — harness is sound.

---

## Lessons

1. **Repro `observed`/`expected` text must describe a comparison that actually distinguishes bug from no-bug.** F02.4's repro told the reviewer to compare two elements that are *equally wrong* — they're flush with each other whether or not the bug exists. The check script (correctly) compared CHILD vs GRANDCHILD; the human instructions (incorrectly) compared GRANDCHILD vs sibling-INFO. **When the bug shifts a whole subtree by a constant, comparing two members of that subtree shows nothing.** Compare across the boundary (parent vs child), or compare an indent *step* against a known-correct indent step.

2. **Depth gaps are easy to miss by eye in the transcript.** 16 px on a 1400 px-wide panel is subtle; with no element rendered at the "missing" depth there is no visual anchor. The outline (`0.75em` step on a narrow column) makes the 2× gap much more obvious. **Prefer the outline `data-depth` attribute for depth checks** — it's the ground-truth `node.depth` value.

3. **"ancestors=[]" looked suspicious but is exactly right.** The F05.1 evidence string didn't say *what* the expected ancestors were, so a reader might assume `[]` meant "couldn't find the element". Adding the **expected** value to the evidence string (`ancestors=[] (expected ['metadata'])`) and the **top-level diff keys** (`toplevel=['LOOK_HERE']`) would have made it self-evidently wrong.

4. **Multi-value evidence needs the underlying numbers.** F90.2's `"2.8 sec / 3 sec / 3.0 sec"` invites the objection "those are different values". Including the source values (`2.818 / 2.812 / ~3.0`) makes it clear which pair is a format difference and which is a value difference.

5. **"By design" ≠ "not a finding".** F10.7's merge is intentional (per code comments + git history). The finding correctly targets the *side-effects* (lost ids/metadata, reordering). Verification confirmed the side-effects occur; the finding text should be tightened to lead with "intentional collapse with the following losses" so it isn't dismissed as "they meant to do that".

6. **`ViewerSession._current_log` carries across `goto_sample()` calls.** When running multiple checks in one session, the second `goto_sample("F02.5")` reused F02.2's log and rendered nothing. The per-finding `verify_one.py` runner avoids this by using a fresh session per check; ad-hoc multi-finding scripts must reset `_current_log = None` (or pass `log=` explicitly) between findings.
