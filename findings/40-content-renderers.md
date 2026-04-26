# Low-Level Content Renderers

**Reviewer scope:** `packages/inspect-components/src/content/**`, `packages/react/src/components/{MarkdownDiv,MarkdownDivWithReferences,markdownRendering,AnsiDisplay,JsonPanel,ExpandablePanel,CopyButton,LightboxCarousel,Preformatted,SourceCodePanel,AsciinemaPlayer,HumanBaselineView}.tsx`, `packages/react/src/hooks/{useCollapsedState,useCollapsibleIds,usePrismHighlight}.ts`, `apps/inspect/src/components/**`
**Date:** 2026-04-22

---

## Summary

The content layer is a heuristic dispatch pipeline (`RenderedContent` → typed renderers → `MarkdownDiv` / `JSONPanel` / `ANSIDisplay` / `MetaDataGrid`). Markdown XSS handling is sound (manual escape + `markdown-it` with html:true + tested). However there are several **state-management correctness bugs** (RecordTree default-collapse never fires, render-queue cancels the wrong task, lightbox listener leak), a number of **prop-mutation / un-memoized recompute** smells, and **three near-identical code-highlighting components plus three dead-code app-level components**. ANSI and JSON rendering have no virtualization and re-parse on every render.

---

## Findings

### F40.1 — RecordTree default-collapse logic never executes

- **Severity:** HIGH
- **Location:** `packages/inspect-components/src/content/RecordTree.tsx:87-108,243` (and `packages/react/src/hooks/useCollapsibleIds.ts:30`)
- **Category:** correctness | collapse-expand

**Description:**
`useCollapsibleIds` returns `(entries || {}) as Record<string, boolean>` — never `undefined`. But `RecordTree` guards the default-collapse effect with `if (collapsedIds) return;` and the flash-prevention with `if (!collapsedIds) return null;`. Both checks treat `{}` as truthy, so the effect body that computes `defaultCollapsedIds` (collapse nodes with `depth >= defaultExpandLevel` or `childCount > 5`) **never runs**, and the flash guard is dead code.

**Evidence:**
```ts
// useCollapsibleIds.ts
return [(entries || {}) as Record<string, boolean>, collapseId, clearIds];
// RecordTree.tsx
useEffect(() => {
  if (collapsedIds) { return; }   // {} is truthy → always early-returns
  const defaultCollapsedIds = items.reduce(...);
  setCollapsedIds(defaultCollapsedIds);
}, [collapsedIds, items]);
...
if (!collapsedIds) { return null; }   // never true
```

**Why it matters / impact:**
Every `RecordTree` (sample metadata, store events, score metadata, ContentDataView) mounts **fully expanded** regardless of `defaultExpandLevel`. Large stores/metadata produce huge initial DOM and an unusable wall of nested rows. The "avoid flash" comment is misleading.

**Suggested fix:**
Either have `useCollapsibleIds` return `entries` (undefined-able) directly, or check `Object.keys(collapsedIds).length === 0 && !initialized.current` with a ref guard.

---

### F40.2 — RecordTree Enter-key toggle reads wrong id

- **Severity:** MEDIUM
- **Location:** `packages/inspect-components/src/content/RecordTree.tsx:118`
- **Category:** correctness | a11y

**Description:**
Keyboard handler for `Enter` toggles using `!collapsedIds?.[id]` — `id` is the **tree's** root id, not the focused row's `itemId`. Arrow-left/right correctly use `itemId`.

**Evidence:**
```ts
case "Enter":
  setCollapsed(itemId, !collapsedIds?.[id]);  // should be collapsedIds?.[itemId]
```

**Why it matters / impact:**
Pressing Enter on a row sets that row's collapsed state based on an unrelated value — effectively always collapses or always expands depending on whether a key equal to the tree id happens to be set. Keyboard users get inconsistent behaviour vs. click.

---

### F40.3 — MarkdownRenderQueue.cancel() marks the wrong queued task

- **Severity:** MEDIUM
- **Location:** `packages/react/src/components/MarkdownDiv.tsx:228-235`
- **Category:** correctness

**Description:**
`cancel()` sets the closure flag (correct) but then finds *the first non-cancelled task in the entire queue* and marks it cancelled — not the task created by this `enqueue` call.

**Evidence:**
```ts
const cancel = () => {
  cancelled = true;
  const index = this.queue.findIndex((t) => !t.cancelled);
  if (index !== -1 && this.queue[index]) {
    this.queue[index].cancelled = true;   // wrong task
  }
};
```

**Why it matters / impact:**
When component A unmounts while B's render is queued ahead of it, A's cleanup silently cancels B's render. B then never gets its markdown rendered (stays as escaped plaintext). The closure `cancelled` flag mostly masks this, but the queue-skip optimisation in `processQueue` will skip the wrong job.

**Suggested fix:**
Capture `queueTask` reference and set `queueTask.cancelled = true` directly.

---

### F40.4 — LightboxCarousel keyup listener leaks (capture-flag mismatch)

- **Severity:** MEDIUM
- **Location:** `packages/react/src/components/LightboxCarousel.tsx:84-85`
- **Category:** correctness | perf

**Description:**
Listener is added with `useCapture=true` but removed without it. `removeEventListener` requires the same capture flag, so the handler is never removed.

**Evidence:**
```ts
window.addEventListener("keyup", handleKeyUp, true);
return () => window.removeEventListener("keyup", handleKeyUp);  // missing `true`
```

**Why it matters / impact:**
Each open/close of the lightbox (or each `showNext`/`showPrev`, since the effect deps include them) leaks a global capture-phase keyup handler. After a few interactions, every keyup triggers stale closures. Combined with F40.19 (handler calls `preventDefault`/`stopPropagation` unconditionally on every keyup), this can interfere with other keyboard handling app-wide.

---

### F40.5 — `web_search` renderer output never displays (array fails `isValidElement`)

- **Severity:** MEDIUM
- **Location:** `packages/inspect-components/src/content/RenderedContent.tsx:73,260-281`
- **Category:** event-display | correctness

**Description:**
The `web_search` renderer returns `{ rendered: results }` where `results` is a `ReactNode[]`. The dispatcher then checks `isValidElement(rendered)` — which is `false` for arrays — and falls through to the JSON-stringify fallback.

**Evidence:**
```tsx
if (rendered !== undefined && isValidElement(rendered)) {
  return rendered;
}
// ...fallthrough
return <span>{JSON.stringify(entry.value)}</span>;
```

**Why it matters / impact:**
Web-search tool results render as a raw JSON blob instead of the intended formatted query + links. The custom renderer is effectively dead.

**Suggested fix:**
Wrap the array in a `<Fragment>` or relax the guard to `rendered !== undefined`.

---

### F40.6 — `Boolean` / `Number` renderers mutate the incoming `entry` prop

- **Severity:** MEDIUM
- **Location:** `packages/inspect-components/src/content/RenderedContent.tsx:163,177`
- **Category:** correctness | code-smell

**Description:**
`entry.value = entry.value.toString()` and `entry.value = formatNumber(entry.value)` mutate the object passed in by the caller (e.g. `MetaDataGrid`'s `entries`).

**Why it matters / impact:**
On a second render of the same entry object (re-render without new props, or two `RenderedContent` instances sharing the same record), a number `42` has become the string `"42"` — `typeof === "number"` is now false, so it falls to the String renderer and `formatNumber` is skipped. In strict-mode double-render this is observable. Also breaks referential equality for parent memoization.

**Suggested fix:**
Pass a cloned `{ ...entry, value: ... }` to the delegated `String.render`.

---

### F40.7 — ANSIDisplay re-parses output on every render

- **Severity:** MEDIUM
- **Location:** `packages/react/src/components/AnsiDisplay.tsx:22-23,77`
- **Category:** perf

**Description:**
`new ANSIOutput()` + `processOutput(output)` + `getUniformBackgroundColor()` (full line scan) run unconditionally in the render body, not memoized. Toggling the "show raw" button re-parses the entire output. There is also no virtualization, so a 10k-line tool output produces 10k `<div>` + N `<span>` per line on every render.

**Why it matters / impact:**
Sandbox/tool events with large terminal output (common in agent evals) make the transcript sluggish; toggling raw-mode freezes the tab.

**Suggested fix:**
`useMemo` over `[output]` for both the parsed lines and the dominant background colour.

---

### F40.8 — LightboxCarousel `showNext` does not wrap; `showPrev` does

- **Severity:** LOW
- **Location:** `packages/react/src/components/LightboxCarousel.tsx:62-68`
- **Category:** consistency | correctness

**Evidence:**
```ts
const showNext = useCallback(() => {
  setCurrentIndex(currentIndex + 1);          // no modulo
}, ...);
const showPrev = useCallback(() => {
  setCurrentIndex((currentIndex - 1 + slides.length) % slides.length);
}, ...);
```

**Why it matters / impact:**
ArrowRight past the last slide goes to a blank panel (`slides[n]?.render()` → undefined). ArrowLeft wraps. Asymmetric UX; in HumanBaselineView with multiple terminal sessions, users can "fall off the end".

---

### F40.9 — ExpandablePanel overflow threshold unit mismatch (rem vs element fontSize)

- **Severity:** LOW
- **Location:** `packages/react/src/components/ExpandablePanel.tsx:46-54,63`
- **Category:** consistency | styling

**Description:**
The collapsed `maxHeight` is `${lines}rem` (root font size), but the `showToggle` decision compares `scrollHeight` against `parseFloat(getComputedStyle(element).fontSize) * lines` (the **element's** font size). Most call-sites wrap content in `text-size-small`/`text-size-smaller`, so the threshold is computed with a smaller font than the actual clamp height.

**Why it matters / impact:**
The "more…" toggle appears for content that actually fits, or fails to appear for content that overflows by a small margin. Visible as spurious "more…" links on short tool outputs.

---

### F40.10 — MetaDataGrid separator CSS var missing closing paren

- **Severity:** LOW
- **Location:** `packages/inspect-components/src/content/MetaDataGrid.tsx:55`
- **Category:** styling

**Evidence:**
```tsx
borderBottom: `${!options?.plain ? "solid 1px var(--bs-light-border-subtle" : ""}`
```

**Why it matters / impact:**
Invalid CSS → browser drops the rule → no row separator is ever drawn in non-plain mode.

---

### F40.11 — `JSONPanel.resolveBase64` recurses without circular-ref guard

- **Severity:** LOW
- **Location:** `packages/react/src/components/JsonPanel.tsx:52-85`
- **Category:** correctness | fallback-hiding-errors

**Description:**
Walks every object/array recursively to redact base64 strings before `JSON.stringify`. No `WeakSet` of visited nodes.

**Why it matters / impact:**
A circular structure passed to `<JSONPanel data={...}>` (e.g. a hydrated sample object with back-references) throws `RangeError: Maximum call stack size exceeded` and blanks the panel. `JSON.stringify` itself would have thrown a clearer "circular structure" error, but `resolveBase64` crashes first.

---

### F40.12 — `resolveStoreKeys` silently drops orphan store keys

- **Severity:** LOW
- **Location:** `packages/inspect-components/src/content/record_processors/store.ts:40-55`
- **Category:** fallback-hiding-errors | event-display

**Description:**
A key matching `name:<22-char-id>:field` whose instance container was not previously created (instance key missing or out of order) hits `if (storeInstances[instanceKey]) { ... continue; }` → false → falls past the `else` → **never added to `result`**. The test at `store.test.ts:62-74` documents this drop as expected.

**Why it matters / impact:**
If a Python-side store ever serialises keys before the `:instance` marker (dict ordering is insertion-order, so any refactor could do this), those values vanish from the metadata view with no indication.

**Suggested fix:**
Fall through to `result[key] = value` for unmatched store keys instead of dropping.

---

### F40.13 — `isJson` logs `console.error` on every non-JSON string wrapped in `{...}`

- **Severity:** LOW
- **Location:** `packages/util/src/json.ts:7-9` (used by `RenderedContent.JsonString` and `MessageContent.text`)
- **Category:** fallback-hiding-errors | code-smell

**Description:**
Any model output that happens to start with `{` and end with `}` (e.g. `"{not json}"`, `"{x | x > 0}"`) triggers a console error during the heuristic probe — even though "not JSON" is the expected, non-error outcome.

**Why it matters / impact:**
Console spam in normal operation; makes real errors harder to spot. Also: `isJson` only matches objects, never `[...]`, so JSON arrays in text content are rendered as markdown, not via `JSONPanel` — inconsistent with `RenderedContent`'s intent.

---

### F40.14 — RecordTree clears collapse state on unmount, defeating persistence in virtualized parents

- **Severity:** LOW
- **Location:** `packages/inspect-components/src/content/RecordTree.tsx:70-74`
- **Category:** collapse-expand | consistency

**Description:**
The unmount cleanup calls `clearIds()`, wiping the persisted collapse map. When a `RecordTree` lives inside a parent `Virtuoso` row (e.g. transcript event), scrolling it out of view unmounts it → state cleared → scrolling back shows it fully expanded again (and given F40.1, default-collapse doesn't reapply).

**Why it matters / impact:**
User collapses a noisy metadata branch, scrolls down, scrolls back — branch is open again. Contradicts the whole point of storing collapse state in the global property bag.

---

### F40.15 — Three near-duplicate code-highlighting panels

- **Severity:** LOW
- **Location:** `packages/react/src/components/SourceCodePanel.tsx`, `apps/inspect/src/components/CodePanel.tsx`, `packages/inspect-components/src/chat/MessageContent.tsx:435-448`
- **Category:** dead-code | consistency

**Description:**
All three are `<div ref><pre><code class="language-X">` + `usePrismHighlight`. The `apps/inspect` one is **unused** (no imports). The inline one in `MessageContent` duplicates `SourceCodePanel` minus the `simple` prop.

**Suggested fix:**
Delete `apps/inspect/src/components/CodePanel.{tsx,module.css}`; replace the inline `CodePanel` with `SourceCodePanel`.

---

### F40.16 — Dead components in `apps/inspect/src/components/`

- **Severity:** LOW
- **Location:** `apps/inspect/src/components/AsciinemaPlayer.tsx`, `apps/inspect/src/components/MorePopOver.tsx` (+ `MorePopover.css`), `apps/inspect/src/components/CodePanel.tsx`
- **Category:** dead-code

**Description:**
None of these are imported anywhere. `AsciinemaPlayer` is a byte-for-byte copy of `packages/react/src/components/AsciinemaPlayer.tsx` (which **is** used via `HumanBaselineView`). `MorePopOver` depends on bootstrap's `Popover` and clones DOM nodes — fragile pattern that's been superseded by `packages/react/PopOver.tsx`.

---

### F40.17 — Markdown links open in same tab; no `rel="noopener"`

- **Severity:** LOW
- **Location:** `packages/react/src/components/markdownRendering.ts:37` (no `link_open` rule override)
- **Category:** consistency | a11y

**Why it matters / impact:**
Clicking a link in model output navigates the viewer away (loses scroll/state). Standard practice for log viewers is `target="_blank" rel="noopener noreferrer"`. Same applies to `<a href={result.url}>` in the `web_search` renderer (`RenderedContent.tsx:270`).

---

### F40.18 — Images rendered without `alt` text

- **Severity:** LOW
- **Location:** `packages/inspect-components/src/content/RenderedContent.tsx:320`; also `chat/MessageContent.tsx` image renderer
- **Category:** a11y

**Evidence:**
```tsx
return { rendered: <img src={entry.value} /> };
```

**Why it matters / impact:**
Screen readers announce "image" with no context. Also no `className` → unbounded size, no max-width constraint.

---

### F40.19 — LightboxCarousel global keyup handler swallows all keyups while open

- **Severity:** LOW
- **Location:** `packages/react/src/components/LightboxCarousel.tsx:73-83`
- **Category:** a11y | correctness

**Description:**
The capture-phase handler calls `e.preventDefault(); e.stopPropagation();` for **every** key, not just Escape/Arrow. While the lightbox is open, no other keyup handler on the page fires.

---

### F40.20 — `MetaDataGrid` references non-existent CSS class `styles.nested`

- **Severity:** INFO
- **Location:** `packages/inspect-components/src/content/MetaDataGrid.tsx:84` vs `MetadataGrid.module.css`
- **Category:** styling | dead-code

**Description:**
`className={clsx(styles.nested)}` resolves to `undefined` — `MetadataGrid.module.css` has no `.nested` rule. Intended nested-indent styling is missing.

---

### F40.21 — `RenderedContent` rebuilds renderer table on every render

- **Severity:** INFO
- **Location:** `packages/inspect-components/src/content/RenderedContent.tsx:52-69`
- **Category:** perf

**Description:**
`contentRenderers(icons, renderObject, externalRenderers)` is called in the render body, allocating ~12 closures, then `Object.keys → map → sort → find` on every render of every cell. In a `MetaDataGrid` with 50 entries inside a virtualized list this is hundreds of allocations per scroll frame. Should be `useMemo` keyed on `[icons, renderObject, externalRenderers]`.

---

### F40.22 — `web_search` renderer: missing React keys + assumes `.results` exists

- **Severity:** INFO
- **Location:** `packages/inspect-components/src/content/RenderedContent.tsx:260-279`
- **Category:** code-smell

**Description:**
Pushes `<div>` elements into an array without `key` props (React warning). Also dereferences `entry.value.results.forEach` without a guard — a `web_search` entry without `results` throws. (Moot until F40.5 is fixed since the output never renders anyway.)

---

### F40.23 — `RecordTree` hides `null` / `undefined` leaf values entirely

- **Severity:** INFO
- **Location:** `packages/inspect-components/src/content/RecordTree.tsx:219,346`
- **Category:** event-display | consistency

**Description:**
`undefined` is coerced to `null` (line 346), then `item.value !== null && ...` (line 219) suppresses the value cell. A metadata key whose value is `null` renders as `key:` with blank right-hand side — indistinguishable from "empty string" and inconsistent with `RenderedContent` which renders `[null]` explicitly.

---

### F40.24 — `CopyButton` setTimeout not cleared on unmount

- **Severity:** INFO
- **Location:** `packages/react/src/components/CopyButton.tsx:36-38`
- **Category:** code-smell

**Description:**
If the button unmounts within 1250 ms of a click, `setIsCopied(false)` fires on an unmounted component. Harmless in React 18 but noisy in dev.

---

### F40.25 — `LinkButton` has copy-pasted JSDoc from `LightboxCarousel`

- **Severity:** INFO
- **Location:** `apps/inspect/src/components/LinkButton.tsx:14-16`
- **Category:** code-smell

**Evidence:**
```ts
/**
 * LightboxCarousel component provides a carousel with lightbox functionality.
 */
export const LinkButton: FC<LinkButtonProps> = ...
```

---

### F40.26 — `Html` content renderer is misleadingly named

- **Severity:** INFO
- **Location:** `packages/inspect-components/src/content/RenderedContent.tsx:299-308` (consumer: `apps/inspect/src/app/log-view/tabs/TaskTab.tsx:73`)
- **Category:** code-smell

**Description:**
`canRender` checks `entry.value._html` and returns it as `rendered`. The only producer (`TaskTab.tsx`) sets `_html` to a **JSX element**, not an HTML string. So this is really a "pass-through ReactNode" renderer; the name `Html` and key `_html` invite someone to pass a raw HTML string, which would render as text (or worse, tempt a future `dangerouslySetInnerHTML`). Rename to `_node` / `ReactNode`.

---

### F40.27 — `usePrismHighlight` skips re-highlight when content changes but length is identical

- **Severity:** INFO
- **Location:** `packages/react/src/hooks/usePrismHighlight.ts:22-36`
- **Category:** correctness

**Description:**
The effect dep is `[contentLength, containerRef]` and blocks are marked `data-highlighted` after first pass. If `code` changes to a different string of the same length, the effect doesn't re-run (same `contentLength`) and the `data-highlighted` attribute on the old `<code>` (which React reuses) prevents the MutationObserver path from re-highlighting.

**Why it matters / impact:**
Edge case: switching between two JSON tabs of identical byte length shows stale highlighting. Low likelihood.

---

## Files reviewed

- [x] `packages/inspect-components/src/content/RenderedContent.tsx` — dispatcher; mutation, web_search, perf issues
- [x] `packages/inspect-components/src/content/RenderedText.tsx` — thin wrapper over MarkdownDivWithReferences/Preformatted; clean
- [x] `packages/inspect-components/src/content/RecordTree.tsx` — default-collapse broken, key bug, null hiding
- [x] `packages/inspect-components/src/content/MetaDataGrid.tsx` — CSS typo, missing `.nested`, local-only expand state
- [x] `packages/inspect-components/src/content/{ContentRenderersContext,DisplayModeContext,IconsContext,types,index}.ts(x)` — clean
- [x] `packages/inspect-components/src/content/record_processors/store.ts` — silent drop of orphan keys
- [x] `packages/inspect-components/src/content/record_processors/{types.ts,store.test.ts}` — clean
- [x] `packages/react/src/components/MarkdownDiv.tsx` — cancel bug, `renderedHtml` in deps causes extra effect run
- [x] `packages/react/src/components/MarkdownDivWithReferences.tsx` — `javascript:void(0)` href; otherwise clean
- [x] `packages/react/src/components/markdownRendering.ts` — XSS escaping verified sound; no new-tab links
- [x] `packages/react/src/components/__tests__/markdownSecurity.test.ts` — covers script/onerror in math; good
- [x] `packages/react/src/components/AnsiDisplay.tsx` — un-memoized parse, no virtualization
- [x] `packages/react/src/components/JsonPanel.tsx` — no circular-ref guard, falsy `data` ignored
- [x] `packages/react/src/components/ExpandablePanel.tsx` — rem vs fontSize mismatch
- [x] `packages/react/src/components/CopyButton.tsx` — uncleaned timeout; a11y OK
- [x] `packages/react/src/components/LightboxCarousel.tsx` — listener leak, no next-wrap, swallows keyups
- [x] `packages/react/src/components/{Preformatted,SourceCodePanel}.tsx` — clean
- [x] `packages/react/src/components/{AsciinemaPlayer,HumanBaselineView}.tsx` — clean
- [x] `packages/react/src/hooks/{useCollapsedState,useCollapsibleIds,usePrismHighlight}.ts` — see F40.1, F40.27
- [x] `apps/inspect/src/components/ActivityBar.tsx` — proper ARIA progressbar; clean
- [x] `apps/inspect/src/components/{AsciinemaPlayer,CodePanel,MorePopOver}.tsx` — **dead code**
- [x] `apps/inspect/src/components/{DownloadButton,DownloadLogButton,DownloadPanel}.tsx` — clean
- [x] `apps/inspect/src/components/{FindBand,FindBandUI}.tsx` — complex but out of scope for content rendering
- [x] `apps/inspect/src/components/{LargeModal,Modal,LinkButton,MessageBand}.tsx` — wrong JSDoc on LinkButton; `Modal` duplicates `packages/react/Modal`

## Open questions / needs verification

- F40.1: confirm in-browser that RecordTree mounts fully expanded (should be obvious on any sample with large `store`).
- F40.5: confirm whether any current eval log actually emits `name === "web_search"` entries through `RenderedContent` (vs. the chat-message tool path) — if not, the renderer is doubly dead.
- `apps/inspect/src/components/Modal.tsx` vs `packages/react/src/components/Modal.tsx` — both exist; only the app-level one is used in `ResultsPanel.tsx`. Candidate for consolidation in Wave 4.
