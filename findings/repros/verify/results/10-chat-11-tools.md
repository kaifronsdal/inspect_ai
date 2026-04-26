# Browser-verification results — batches `10-chat` + `11-tools`

**Date:** 2026-04-24
**Method:** `findings/repros/verify/verify_one.py` (Playwright + live `inspect view`, port 7578)
**Checks:** `findings/repros/verify/checks/F10_*.py`, `F11_*.py`

---

## Summary

| Verdict | Count | IDs |
|---|---|---|
| **CONFIRMED** | **10** | F10.1 · F10.4† · F10.6 · F10.7 · F11.1 · F11.2 · F11.3 · F11.4 · F11.7 · F11.11 |
| **NOT_REPRODUCED** | **2** | F10.2 · F11.8 |
| **FALSE_POSITIVE** | **0** | — |
| **INCONCLUSIVE** | **0** | — |

† F10.4 was NOT_REPRODUCED with the original `.eval`; **repro fixed** (regenerated with positional `cited_text=(start,end)` spans) → now CONFIRMED.

**No FALSE_POSITIVEs.** Both NOT_REPRODUCED verdicts are *repro-doesn't-reach-the-code-path* cases — the cited source code is buggy as described, but the inspect viewer never invokes it (the only caller setting `collapseToolMessages: false` is `apps/scout`).

---

## Results table

| ID | Verdict | Evidence (extracted from page) |
|---|---|---|
| F10.1 | CONFIRMED | Between user turns 2→3: `'Second user turn. … ↓\n\n3\nUSER\n\nThird user turn. ↑'` — orphan tool msg absent |
| F10.2 | NOT_REPRODUCED | `row2='…rich_tool(q: "x")\nF10.2_ERROR_FIELD_timeout — exceeded 30s (this is \`error.message\`)'` — error IS shown (collapsed path) |
| F10.4 | CONFIRMED (after repro fix) | `inline <sup>: [1,2,1,2]` vs `footnotes: [1=CITE-A 2=CITE-B 3=CITE-C 4=CITE-D]` |
| F10.6 | CONFIRMED | assistant row: `'2\n\nVisible answer: …'` — `<think>` body gone, no marker |
| F10.7 | CONFIRMED | `SYSTEM role headers=1, total rows=5, SYSTEM#3@296 before AssistantA@1192` |
| F11.1 | CONFIRMED | both `<pre class='_textOutput_h7uyp_10 tool-output'>`; bad-only classes=NONE; error-icon=False |
| F11.2 | CONFIRMED | between fn header and error.message: `'\n'` — no `permission:` prefix |
| F11.3 | CONFIRMED | bare panel: `'type:\nimage\nimage:\ndetail:\nauto'` (RecordTree); control: `<img class="_contentImage_…">` |
| F11.4 | CONFIRMED | `<h1>This line should be PLAIN TEXT not an &lt;h1&gt; heading</h1>`; `<strong>`; `<a href>` |
| F11.7 | CONFIRMED | no viewer `N of M bytes` footer; Python preamble in result text instead |
| F11.8 | NOT_REPRODUCED | `row2='…data_tool\ntext part survives ✓\nsentinel:\nF11.8_CONTENTDATA_SENTINEL…\nn:\n42'` — ContentData IS rendered |
| F11.11 | CONFIRMED | approval-row chrome (excl. explanation): `'MODIFIED'` — approver/modified/message=False |

Artifacts: `findings/repros/verify/artifacts/F11.1-transcript.png`

---

## Per-finding detail

### F10.1 — CONFIRMED

The orphan `ChatMessageTool` (following a user turn, no assistant) is absent
from the Messages tab. Only rows `1/USER`, `2/USER`, `3/USER` render;
`function=orphaned_tool` and the sentinel tail
`IF THIS LINE IS MISSING FROM THE MESSAGES TAB…` appear nowhere outside the
description table. `resolveMessages` attached it to the preceding user row's
`toolMessages[]`; `ChatMessageRow` only iterates that array for `role==='assistant'`.

### F10.2 — NOT_REPRODUCED (repro can't reach code path in inspect viewer)

The Messages tab shows `rich_tool(q: "x")` followed by the full
`error.message` — i.e. the error **is** displayed. This is the **collapsed**
path (`ChatMessageRow.resolveToolMessage`, lines 228-231), which the finding
itself says works.

The buggy path is `ChatMessage.tsx:116-129`, reached only when a tool message
renders **standalone** (`collapseToolMessages: false`). Grep for callers:

```text
ChatView.tsx:38           tools?.collapseToolMessages ?? true
ChatViewVirtualList.tsx:131  tools?.collapseToolMessages ?? true
apps/scout/.../refs.tsx:132,146,208   collapseToolMessages: false
```

The inspect app never sets it `false`. The repro therefore cannot demonstrate
F10.2 in the live inspect viewer; the bug is only observable in `apps/scout`
or via `ModelEventView` when `context.hasToolEvents === false` (which the
repro also doesn't construct). **Finding is correct at source level; repro
.eval does not exercise it.**

### F10.4 — CONFIRMED (after regenerating repro)

**Original repro was wrong.** It used `UrlCitation(cited_text="cited text for X")`
— a string → `isCitationWithRange()` returns `false` → all four cites are
*end-cites*, which share `++citeCount` across the coalesced text run and
number correctly (`<sup>` = 1,2,3,4; footnotes = 1,2,3,4). Verdict on original
`.eval`: NOT_REPRODUCED.

**Repro fix applied** (`tasks/10-chat/F10.4_citation_numbering_mismatch.py`):
changed `cited_text` to `(start, end)` tuples → positional cites. Regenerated
log: `logs/10-chat/2026-04-24T03-26-12-…_F10.4-….eval`. Result:

> inline `<sup>`: **`1,2,1,2`** | footnotes: **`1=CITE-A 2=CITE-B 3=CITE-C 4=CITE-D`**

Block 2's positional superscripts restart at 1 (`positionalCites.length - i`
ignores the running `citeCount`), while `MessageCitations` numbers the
flattened list 1..4. Footnote #3 (CITE-C) maps to inline `¹`. **CONFIRMED.**

### F10.6 — CONFIRMED

Assistant row renders only `"Visible answer: the capital of France is Paris.
↑ There is supposed to be a `` block ABOVE this line…"`. The `<think>…</think>`
body (sentinel `F10.6_HIDDEN_REASONING — IF YOU CAN READ THIS…`) is gone, and
no `[hidden]` / `[internal]` / redaction marker appears. (Note the `` `` empty
code span in the prose — `purgeInternalContainers` also stripped the literal
`<think>…</think>` mentioned in the self-describing text, leaving empty backticks.)

### F10.7 — CONFIRMED

Messages tab renders **5 rows** (expected 7). Row 1 = `SYSTEM` containing
**all three** system-message bodies concatenated:
`"🟦 SYSTEM MSG #1 …🟦 SYSTEM MSG #2 …🟦 SYSTEM MSG #3 …"`. Mid-stream `#2`
(original position 4) and trailing `#3` (position 7) are hoisted above
"Assistant turn A". Only one `SYSTEM` role header in the entire tab.

### F11.1 — CONFIRMED

`good_tool` (success) and `bad_tool` (`ToolError`) panels render their output
in identical `<pre class="_textOutput_h7uyp_10 tool-output">` blocks. The
`bad_tool` panel has **zero CSS classes** the `good_tool` panel lacks, and no
error icon (`bi-exclamation*`, `bi-x-circle`, `text-danger`). Screenshot:
`artifacts/F11.1-transcript.png`. Visually indistinguishable.

### F11.2 — CONFIRMED

Rendered tool result: `"restricted_op\n<error.message>"`. The gap between the
function-name header and the first word of `error.message` is a single `\n` —
no `permission:` prefix, no badge, no label. `error.type` is dropped.

### F11.3 — CONFIRMED (with caveat on observed-behaviour description)

`screenshot_list` (control, `result=[ContentImage(…)]`) → clean
`<img class="_contentImage_…">`.
`screenshot_bare` (`result=ContentImage(…)`, no list) → record-tree:
`type: image / image: <img> / detail: auto` inside `<div id="1-json" class="_jsonMessage_…">`.

The `normalizeContent` `JSON.stringify` branch fires exactly as the finding
describes. **However**, the *visible* output is **not** the raw
`{"type":"image","image":"data:…"}` text the finding's Observed section claims —
`ToolTextOutput` detects valid JSON and re-renders it via `JsonMessageContent`
(a RecordTree). Net effect is unchanged: bare ContentImage renders as a
key/value tree, not a content image. The finding's description of *what the
user sees* should be updated.

### F11.4 — CONFIRMED

`ToolCallContent(format='text', content='# This line should be PLAIN TEXT…')`
renders as `<h1>This line should be PLAIN TEXT not an &lt;h1&gt; heading</h1>`;
`**…**` → `<strong>`; `[not a link](…)` → `<a href="http://example.invalid">`.
`ToolInput.tsx` ignores `.format` and always passes content to
`<RenderedText markdown=…>`.

### F11.7 — CONFIRMED (impact overstated)

Tool panel: `"big_output\nThe output of your call to big_output was too long
to be displayed.\nHere is a truncated version:\n<START_TOOL_OUTPUT>\n…
F11.7_FULL_OUTPUT_END\n<END_TOOL_OUTPUT>"`.

No viewer-side `showing N of M bytes` footer reading `event.truncated`.
**Narrow claim confirmed.** However:

1. The finding's impact ("no indication it was truncated") is **overstated** —
   inspect-core's `truncate_tool_output()` rewrites `event.result` to include
   the `"too long to be displayed. Here is a truncated version:"` preamble,
   which the viewer faithfully prints. Users *do* see a truncation hint; it
   just doesn't come from the viewer reading `event.truncated`.
2. The repro's claim "you will NOT see `F11.7_FULL_OUTPUT_END`" is wrong —
   head+tail truncation keeps both markers.

Suggested re-severity: MEDIUM → LOW.

### F11.8 — NOT_REPRODUCED (repro can't reach code path in inspect viewer)

`data_tool` result row shows `text part survives ✓ / sentinel:
F11.8_CONTENTDATA_SENTINEL_if_missing_bug_confirmed / n: 42` — the
`ContentData` block **is** rendered.

Same root cause as F10.2: the repro pairs the tool message with an assistant
`tool_call`, so it goes through the **collapsed** path
(`ChatMessageRow → ToolCallView → MessageContent`) which handles `ContentData`.
The buggy filter is in `ChatMessage.tsx:117-125`, only reachable when
`collapseToolMessages: false` — never set by the inspect app. Source snippet:

```tsx
// ChatMessage.tsx:117-125 — unreachable from apps/inspect Messages tab
: message.content.filter(
    (c): c is ContentText | ContentImage =>
      c.type === "text" || c.type === "image"
  )
```

**Finding is correct at source level; repro .eval does not exercise it in
the inspect viewer.** An orphan tool message can't be used as an alternative
trigger because F10.1 swallows it before render.

### F11.11 — CONFIRMED

The approval renders as a bare `EventRow`: title `MODIFIED` + the explanation
text. Stripping the explanation body, the viewer-added chrome is exactly
`'MODIFIED'` — no approver name, no modified-args diff, no `event.message`.
Source confirms (`ApprovalEventView.tsx:22-31`):

```tsx
<EventRow title={decisionLabel(event.decision)} icon={…}>
  {event.explanation || ""}
</EventRow>
```

`event.approver`, `event.modified`, `event.message` are never read.

---

## Repro fixes applied

| ID | File | Change | New `.eval` |
|---|---|---|---|
| F10.4 | `tasks/10-chat/F10.4_citation_numbering_mismatch.py` | `cited_text="…"` → `cited_text=(start, end)` (positional cites) | `logs/10-chat/2026-04-24T03-26-12-00-00_F10.4-citation-numbering-mismatch_nNrxCMoT78wRMJgUEM54VK.eval` |

## Reproduce

```bash
cd /home/ubuntu/GitHub/inspect_ai
uv run --with playwright python findings/repros/verify/verify_one.py \
    F10.1 F10.2 F10.4 F10.6 F10.7 F11.1 F11.2 F11.3 F11.4 F11.7 F11.8 F11.11 \
    --port 7578
```
