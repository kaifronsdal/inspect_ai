# HOWTO: browser-verify a repro `.eval` file

You have a `.eval` file in `findings/repros/logs/<batch>/` that *claims* to
demonstrate a viewer bug. This harness opens it in a real `inspect view`
server, drives a headless Chromium at it, and lets you assert on what is
actually rendered.

> **Nothing here touches `src/` or `pyproject.toml`.** Playwright is pulled
> in transiently via `uv run --with playwright`.

---

## 1. One-time setup (already done on this VM)

```bash
cd /home/ubuntu/GitHub/inspect_ai
uv run --with playwright playwright install chromium
uv run --with playwright playwright install-deps chromium   # apt libs; sudo
```

Verify: `uv run --with playwright python -c "from playwright.sync_api import sync_playwright; print('ok')"`

---

## 2. Running an existing check

```bash
cd /home/ubuntu/GitHub/inspect_ai

# one finding
uv run --with playwright python findings/repros/verify/verify_one.py F04.2

# several (each gets its own server start/stop)
uv run --with playwright python findings/repros/verify/verify_one.py F01.2 F04.2 F40.1

# every check in a batch
uv run --with playwright python findings/repros/verify/verify_one.py --batch 01-events

# machine-readable
uv run --with playwright python findings/repros/verify/verify_one.py F04.2 --json
```

Exit code is `0` unless at least one check returned `INCONCLUSIVE` (so you
can `&&`-chain it in CI).

---

## 3. Writing a check

Create `findings/repros/verify/checks/F<NN>_<M>.py` (note: `_` not `.` in
the filename — `F01.2` → `F01_2.py`). Minimal contract:

```python
from harness import VerifyResult, ViewerSession

BATCH = "01-events"          # which logs/<batch>/ dir to serve

def check(session: ViewerSession) -> VerifyResult:
    session.goto_sample("F04.2", tab="transcript")
    subtabs = session.event_subtabs("Model Call")
    if "TOOLS" not in [t.upper() for t in subtabs]:
        return VerifyResult(
            verdict="CONFIRMED",
            evidence=f"sub-tabs: {subtabs}",
            notes="`tools.length > 1` off-by-one hides the tab.",
        )
    return VerifyResult("NOT_REPRODUCED", f"sub-tabs: {subtabs}")
```

The runner:

1. starts `inspect view --log-dir findings/repros/logs/<BATCH> --port <auto>`
2. launches headless chromium
3. calls your `check(session)`
4. tears everything down (even on exception)
5. prints / returns the `VerifyResult`

### `VerifyResult` verdicts

| Verdict | Meaning |
|---|---|
| `CONFIRMED` | The bug is visible exactly as the finding describes. |
| `NOT_REPRODUCED` | The viewer behaves **correctly** at the bug location — finding is stale or already fixed. |
| `INCONCLUSIVE` | Couldn't reach / parse the bug location. Often means the **repro `.eval`** is wrong (see F01.2). Fix the repro or the check, don't guess a verdict. |
| `FALSE_POSITIVE` | Reached the location and the finding's *description of current behaviour* is factually wrong (distinct from "fixed since"). |

`evidence` must be **text extracted from the page** (not your own prose) —
the load-bearing fragment that justifies the verdict. Keep it < 500 chars.

---

## 4. Navigation & selector reference

All discovered from `src/inspect_ai/_view/ts-mono/apps/inspect/src/` —
file refs in parentheses.

### URL patterns (hash router — `routing/url.ts`)

| Destination | Hash URL | Harness call |
|---|---|---|
| Log listing root | `#/logs` | `session.goto("/logs")` |
| Log, top-level tab | `#/logs/<file>/<tab>` where `<tab>` ∈ `samples \| info \| models \| task \| json \| error` | `session.goto_log("F01.2", tab="info")` |
| Sample, specific tab | `#/logs/<file>/samples/sample/<id>/<epoch>/<tab>` where `<tab>` ∈ `transcript \| messages \| scoring \| metadata \| error \| retries \| retry-errors \| json` | `session.goto_sample("F01.2", epoch=1, tab="transcript")` |
| Sample → transcript scrolled to event | `…/transcript?event=<uuid>` | `session.goto_sample("F01.2", tab="transcript", event=uuid)` |
| Sample → messages scrolled to msg | `…/messages?message=<id>` | `session.goto_sample("F01.2", tab="messages", message=mid)` |

`<file>` is the log filename **relative to the served `--log-dir`**
(URL-encoded). `goto_log` / `goto_sample` accept either the full filename or
any unique substring (e.g. the finding id) and resolve via glob.

> **Prefer deep-linking over click sequences.** The hash router handles
> everything; clicking is only needed when the bug is *about* a click.

### CSS selectors / locators

| Target | Selector | Notes |
|---|---|---|
| Sample-tab button (Transcript / Messages / …) | `button[role="tab"]#<tabId>` e.g. `#transcript`, `#metadata` | `TabSet.tsx` — button id == tab id. |
| Sample-tab content pane | `#<tabId>-contents` e.g. `#metadata-contents` | Only the active pane has children. |
| Transcript event panel | `[id^="event-panel-"]` | `EventPanel.tsx`. id is `event-panel-<nodeUuid>`. Use `session.event_panel("Model Call")` to filter by title. |
| Event sub-tab pill (Summary / All / Tools / API / …) | inside panel: `button[role="tab"]` (text = title, no id) | `EventNav.tsx`. Titles are CSS-uppercased so `inner_text` returns `"SUMMARY"`. Use `session.event_subtabs()` / `click_event_subtab()`. |
| Event panel active pane | inside panel: `.tab-pane.active` | Only the selected sub-tab is mounted. |
| Event collapse chevron | inside panel: `i.bi-chevron-right` (collapsed) / `i.bi-chevron-down` (expanded) | `session.expand_event()` / `collapse_event()`. |
| Outline row | `[class*="OutlineRow"]` with `[data-depth]` | `OutlineRow.tsx`. |
| RecordTree row | `.record-tree-key[data-index]` | `RecordTree.tsx` (`kRecordTreeKey`). |
| Log/sample grid cells | `.ag-cell` (filter by text) | ag-grid. |
| NavPills (e.g. Tasks/Folders/Samples segment) | `button[role="tab"][data-target="<title>"]` | `NavPills.tsx`. |

### Text-transform gotcha

The viewer applies `text-transform: uppercase` to most labels via CSS.
`inner_text()` returns the **transformed** text (`"MODEL CALL: MOCKLLM/MODEL"`,
`"SUMMARY"`), but Playwright's `has_text=` filter and `get_by_role(name=)`
match against the **source** text. The harness helpers try both; if you
write raw locators, remember:

```python
panel.filter(has_text="Model Call")   # works (source text)
"MODEL CALL" in panel.inner_text()     # works (rendered text)
```

### Known event titles (for `event_panel(...)`)

`Model Call:` · `Tool:` · `Score` · `Score Edit` · `Sample Init` · `Info` ·
`Error` · `Logger` · `State` · `Store` · `Approval` · `Sandbox` · `Subtask`
· `Span:` · `Solver:` (span wrapper).

---

## 5. `ViewerSession` cheat-sheet

```python
with ViewerSession("findings/repros/logs/01-events", port=7576) as v:

    # ---- navigation -------------------------------------------------------
    v.goto_log("F01.2", tab="info")
    v.goto_sample("F01.2", epoch=1, tab="metadata")
    v.goto("/logs")                              # raw hash path
    v.click_tab("Messages")                      # click the sample-tab button

    # ---- transcript events ------------------------------------------------
    v.event_panel("Model Call")                  # -> Locator
    v.event_panel_text("Model Call")             # -> str (inner_text)
    v.event_subtabs("Model Call")                # -> ["SUMMARY","ALL","API",…]
    v.click_event_subtab("All", in_event="Model Call")
    v.expand_event("Score")
    v.collapse_event("Score")

    # ---- extraction -------------------------------------------------------
    v.text_of("#metadata-contents")
    v.html_of('[id^="event-panel-"]')
    v.all_text()                                  # whole-page grep
    v.a11y_of("#transcript-contents")             # role/state tree
    v.screenshot("artifacts/F40.1.png", selector="#metadata-contents")
    v.dump_html("artifacts/F40.1.html")

    # ---- escape hatch -----------------------------------------------------
    v.page.get_by_role("button", name="Collapse").click()
    v.page.locator(".ag-cell").filter(has_text="task-alpha").click()
    v.wait_settled()
```

---

## 6. Port allocation for parallel agents

`inspect view` will **kill any existing server on the same port** before
binding (`view.py:view_acquire_port`). If two agents share a port, one will
silently terminate the other mid-check.

`harness.port_for_batch(batch)` gives each batch a fixed port:

| Batch | Port | Batch | Port |
|---|---|---|---|
| `01-events` | 7576 | `20-samples` | 7580 |
| `02-transform` | 7577 | `30-loglist` | 7581 |
| `10-chat` | 7578 | `40-content` | 7582 |
| `11-tools` | 7579 | `90-cross` | 7583 |

`verify_one.py` uses this automatically. Override with `--port N` if you
need to run two checks from the *same* batch concurrently.

---

## 7. Gotchas hit while building this

- **`tool_choice=ToolFunction(...)` filters `event.tools`** down to just the
  forced tool before it reaches the log. The F01.2 repro defined two tools
  but the ModelEvent only contains one → F04.2's `> 1` guard hides the Tools
  tab → F01.2 is unreachable. The harness correctly returns `INCONCLUSIVE`;
  the *repro* needs regenerating.
- **Only the active sub-tab is mounted.** `EventPanel` returns `null` for
  unselected children, so `html_of` on an inactive pane gives nothing —
  click the sub-tab first.
- **Virtualised lists** (`react-virtuoso`, ag-grid) only render visible rows.
  For "is row N present?" checks on long lists, scroll first
  (`v.page.locator(...).scroll_into_view_if_needed()`) or shrink the dataset
  in the repro.
- **`networkidle`** is needed after every hash navigation: the SPA fires API
  fetches (`/api/logs/<file>`, `/api/log-headers`). `wait_settled()` does
  this plus a 250 ms React-commit buffer.
- **Bug-description text bleeds into `inner_text`.** Every repro embeds a
  markdown table describing the bug as the first user message, which appears
  in the Transcript / Messages tab text. Anchor your assertions on
  **sentinel strings that only the buggy code path produces**, not on words
  that also appear in the description (see `F04_8.py` for a worked example).
- **Don't use `pytest`** for these — the sync Playwright API + subprocess
  server don't play well with the repo's anyio test hooks. Plain `python` is
  fine.

---

## 8. Worked examples (in `checks/`)

| File | Demonstrates | Result |
|---|---|---|
| `F04_2.py` | Presence/absence check on event sub-tabs | `CONFIRMED` |
| `F04_8.py` | `click_event_subtab` + parsing a 2-col grid | `CONFIRMED` |
| `F40_1.py` | Tab-content text grep + screenshot artifact | `CONFIRMED` |
| `F01_2.py` | `INCONCLUSIVE` path when the repro itself is broken | `INCONCLUSIVE` |

Copy whichever is closest to your finding's shape.
