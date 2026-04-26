# Base React Component Library (`@tsmono/react`)

**Reviewer scope:** `src/inspect_ai/_view/ts-mono/packages/react/src/` — all components, hooks, state, and CSS modules; cross-referenced against usages in `apps/inspect/`, `apps/scout/`, and `packages/inspect-components/`.
**Date:** 2026-04-22

---

## Summary

The shared component library is broadly functional but shows clear signs of code drift: at least **8 CSS-module class references resolve to `undefined`** (silently dropped by `clsx`), one prop is declared but never wired (`AsciinemaPlayer.className`), one component is dead (`NavPills`), and several components have correctness bugs that affect users today (`CardBody padded={false}` defeated by `!important`, `LightboxCarousel` keyup listener leak + broken transitions, `MarkdownRenderQueue.cancel()` cancels the wrong task). a11y is uneven — `Modal`, `MenuActionButton`, `LightboxCarousel`, and `ToolDropdownButton` lack roles, focus traps, and keyboard support. Styling primitives are inconsistent (Bootstrap globals vs CSS modules vs `--vscode-*` vars vs 200+ lines of inline styles in `PopOver`).

---

## Findings

### F60.1 — `CardBody padded={false}` is defeated by `!important`

- **Severity:** MEDIUM
- **Location:** `packages/react/src/components/Card.module.css:24` (and `Card.tsx:62-70`)
- **Category:** correctness | styling

**Description:**
`.body` declares `padding: 0.5rem !important;`. The override `.body.noPadding { padding: 0; }` has higher specificity but no `!important`, so it never wins. Every `<CardBody padded={false}>` still renders with 0.5rem padding.

**Evidence:**
```css
.body {
  padding: 0.5rem !important;
}
.body.noPadding {
  padding: 0;          /* loses to !important above */
}
```

**Why it matters / impact:**
Used 4× in `apps/inspect/src/app/samples/SampleDisplay.tsx:712,747,766,782` and once in `ResultsPanel.tsx:152`. Those panels render with unwanted padding the author explicitly tried to remove.

**Suggested fix:**
Drop `!important` from `.body`, or add `!important` to `.noPadding`.

---

### F60.2 — `LightboxCarousel` keyup listener never removed (capture-phase mismatch)

- **Severity:** MEDIUM
- **Location:** `packages/react/src/components/LightboxCarousel.tsx:84-85`
- **Category:** correctness

**Description:**
The listener is added with `useCapture=true` but removed without it. `removeEventListener` requires matching capture flags, so cleanup is a no-op and listeners accumulate every time the lightbox opens.

**Evidence:**
```tsx
window.addEventListener("keyup", handleKeyUp, true);
return () => window.removeEventListener("keyup", handleKeyUp);  // missing `true`
```

**Why it matters / impact:**
After opening the lightbox N times, N stale handlers remain attached. Each calls `e.preventDefault()`/`e.stopPropagation()` **unconditionally on every keyup** (line 81-82 fire even for non-arrow keys), which can break typing in unrelated inputs after the lightbox is closed.

**Suggested fix:**
Pass `true` to `removeEventListener`; move `preventDefault/stopPropagation` inside the matched-key branches.

---

### F60.3 — `LightboxCarousel` open/closed/prev/next CSS never matches (CSS-module scoping)

- **Severity:** MEDIUM
- **Location:** `packages/react/src/components/LightboxCarousel.tsx:116,128,138,148` and `LightboxCarousel.module.css:33-43,76-82`
- **Category:** correctness | styling

**Description:**
JSX applies plain string classes `"open"`, `"closed"`, `"prev"`, `"next"`. The CSS module defines `.lightboxOverlay.open`, `.lightboxPreviewButton.prev`, etc. — but in CSS modules `.open`/`.prev`/`.next` are *also* locally scoped (hashed). The DOM class `open` therefore never matches the compiled selector.

**Evidence:**
```tsx
className={clsx(styles.lightboxOverlay, isOpen ? "open" : "closed")}
```
```css
.lightboxOverlay.open { opacity: 1; }     /* compiles to ._abc._def */
.lightboxPreviewButton.next { left: 10px } /* never matches */
```

**Why it matters / impact:**
The fade-in/out transition silently does nothing (overlay just pops). The prev/next buttons get no `left`/`right` positioning, so they overlap at the default position. Additionally, `.next { left: 10px }` and `.prev { right: 10px }` are **swapped** — even if the selector matched, the buttons would be on the wrong sides.

**Suggested fix:**
Use `styles.open` / `styles.closed` / `styles.prev` / `styles.next` in JSX; swap the left/right rules.

---

### F60.4 — `LightboxCarousel.showNext` does not wrap; `showPrev` does

- **Severity:** LOW
- **Location:** `packages/react/src/components/LightboxCarousel.tsx:62-68`
- **Category:** consistency | correctness

**Description:**
`showPrev` uses modulo wraparound; `showNext` does not. After the last slide, `currentIndex` becomes `slides.length` and `slides[currentIndex]?.render()` returns `undefined` → blank lightbox.

**Evidence:**
```tsx
const showNext = useCallback(() => {
  setCurrentIndex(currentIndex + 1);            // no % slides.length
}, ...);
const showPrev = useCallback(() => {
  setCurrentIndex((currentIndex - 1 + slides.length) % slides.length);
}, ...);
```

---

### F60.5 — `MarkdownRenderQueue.cancel()` cancels the wrong queued task

- **Severity:** MEDIUM
- **Location:** `packages/react/src/components/MarkdownDiv.tsx:228-235`
- **Category:** correctness

**Description:**
`cancel()` sets the closure flag correctly, but then finds *the first non-cancelled task in the queue* and marks **that** one cancelled — not the task it just enqueued.

**Evidence:**
```ts
const cancel = () => {
  cancelled = true;
  const index = this.queue.findIndex((t) => !t.cancelled);  // wrong target
  if (index !== -1 && this.queue[index]) {
    this.queue[index].cancelled = true;
  }
};
```

**Why it matters / impact:**
When component A unmounts while B's task is at the head of the queue, B's render is silently dropped (its `wrappedTask` early-returns and the promise never resolves). Combined with F60.6, every `MarkdownDiv` mount triggers an immediate cancel cycle, so cross-component cancellation collisions are realistic in virtual lists.

**Suggested fix:**
Capture `queueTask` in the closure and set `queueTask.cancelled = true` directly.

---

### F60.6 — `MarkdownDiv` effect depends on its own output (`renderedHtml`)

- **Severity:** LOW
- **Location:** `packages/react/src/components/MarkdownDiv.tsx:148-156`
- **Category:** code-smell | perf

**Description:**
The effect deps include `renderedHtml`, which the effect itself sets via `setRenderedHtml`. On a fresh (uncached) render this produces: enqueue → set sanitized → effect re-runs → cleanup cancels prior task → re-enqueue → resolve → set final → effect re-runs again (now hits cache, no-op). One wasted enqueue/cancel per mount, and the cancel hits F60.5.

**Suggested fix:**
Remove `renderedHtml` from deps; the cached-path equality check can use a ref.

---

### F60.7 — `AsciinemaPlayer` accepts `className` but never applies it

- **Severity:** LOW
- **Location:** `packages/react/src/components/AsciinemaPlayer.tsx:21,81-86`
- **Category:** dead-code | consistency

**Description:**
`className` is in `AsciinemaPlayerProps` and is passed by `HumanBaselineView.tsx:69` (`className={"asciinema-player"}`), but the destructure at line 24-38 omits it and the rendered `<div>` doesn't apply it.

---

### F60.8 — Multiple `styles.*` references resolve to `undefined` (missing CSS rules)

- **Severity:** LOW–MEDIUM
- **Location:** see table
- **Category:** styling | dead-code

**Description:**
`clsx` silently drops `undefined`, so these compile fine but apply no class.

| TSX reference | CSS module | Exists? |
|---|---|---|
| `styles.padBottom` (`ExpandablePanel.tsx:77`) | `ExpandablePanel.module.css` | **No** |
| `moduleStyles.pill` (`TabSet.tsx:114`) | `TabSet.module.css` | **No** — only `.pillSmall` exists; `type="pills"` used in 4 callers |
| `styles.labeledValueValue` (`LabeledValue.tsx:43`) | `LabeledValue.module.css` | **No** |
| `styles.ansiDisplayLine` (`AnsiDisplay.tsx:107`) | `AnsiDisplay.module.css` | **No** |

**Why it matters / impact:**
`TabSet type="pills"` (used in `LogView.tsx:129`, `ScanPanelBody.tsx:230`, etc.) gets no module styling — the buttons rely solely on bootstrap `nav-pills`. If a `.pill` rule was intended (parallel to `.pillSmall`), it's missing.

---

### F60.9 — Dead CSS rules in `ExpandablePanel.module.css`

- **Severity:** INFO
- **Location:** `packages/react/src/components/ExpandablePanel.module.css:10-16`
- **Category:** dead-code

`.expandableTogglable` and `.expandableContents` are defined but never referenced from `ExpandablePanel.tsx`.

---

### F60.10 — Invalid CSS: quoted custom-property value in `TabSet.module.css`

- **Severity:** LOW
- **Location:** `packages/react/src/components/TabSet.module.css:18`
- **Category:** styling | correctness

**Evidence:**
```css
.tab {
  color: "var(--bs-body-color)";   /* string literal, ignored by browser */
}
```

The quotes make this an invalid `color` value; the declaration is dropped.

---

### F60.11 — Invalid CSS: `white-space: prewrap` in `ErrorPanel.module.css`

- **Severity:** LOW
- **Location:** `packages/react/src/components/ErrorPanel.module.css:25`
- **Category:** styling | correctness

`prewrap` is not a valid keyword (should be `pre-wrap`). Stack traces in `ErrorPanel` therefore don't wrap.

---

### F60.12 — `EmptyPanel.css` is never imported

- **Severity:** LOW
- **Location:** `packages/react/src/components/EmptyPanel.tsx:1-15` / `EmptyPanel.css`
- **Category:** styling | dead-code

**Description:**
`EmptyPanel.tsx` renders `<div className="empty-panel"><div className="container">…` but imports no CSS. `EmptyPanel.css` exists with the matching rules but `rg` finds no `import` of it anywhere in the monorepo. Additionally, `container` collides with Bootstrap's global `.container` (max-width + horizontal padding), so the panel inherits unintended Bootstrap layout.

**Why it matters / impact:**
Used in `LogView.tsx` and `SampleScoresGrid.tsx`. The intended flex-centering never applies; the Bootstrap `.container` accidentally provides *some* centering via `margin: auto`, masking the bug.

---

### F60.13 — `NavPills` is dead (exported, never used)

- **Severity:** INFO
- **Location:** `packages/react/src/components/NavPills.tsx`
- **Category:** dead-code

**Description:**
No `<NavPills>` JSX anywhere in `apps/` or `packages/`. `TabSet` with `type="pills"` is used instead. The internal `NavPill` also accepts `children` that it renders inside the `<li>` but the parent never passes any.

---

### F60.14 — `useDocumentTitle` hardcodes `"Inspect Scout"` in a shared package

- **Severity:** LOW
- **Location:** `packages/react/src/hooks/useDocumentTitle.ts:3`
- **Category:** consistency | code-smell

**Description:**
`const APP_NAME = "Inspect Scout"` is baked into a hook exported from the *shared* `@tsmono/react` package. The `inspect` app avoids this by defining its own `useDocumentTitle` (`apps/inspect/src/state/hooks.ts:519`) — so two implementations exist with the same name, and the shared one is scout-specific despite living in shared code.

**Suggested fix:**
Accept app name via context/parameter, or move to `apps/scout`.

---

### F60.15 — `Modal` lacks dialog semantics, focus trap, and scroll lock

- **Severity:** MEDIUM
- **Location:** `packages/react/src/components/Modal.tsx:57-76`
- **Category:** a11y

**Description:**
- No `role="dialog"` / `aria-modal="true"` / `aria-labelledby`.
- No focus trap — `Tab` cycles into the page behind the backdrop.
- No body scroll lock.
- Global `keydown` handler intercepts **Enter** anywhere on the page and fires `onSubmit`. If the modal contains a `<textarea>` or a multi-field form, pressing Enter in any field submits instead of inserting a newline / moving to next field.
- Close button (`<button>`) has no `aria-label`.

**Why it matters / impact:**
Used by `ConfirmationDialog` and ~9 scout call sites. Keyboard users can tab out of the modal; screen readers don't announce it as a dialog.

---

### F60.16 — `MenuActionButton` / `ToolDropdownButton` lack keyboard and ARIA support

- **Severity:** LOW
- **Location:** `packages/react/src/components/MenuActionButton.tsx:34-63`, `ToolDropdownButton.tsx:104-154`
- **Category:** a11y

**Description:**
Neither sets `aria-haspopup="menu"` / `aria-expanded`. Neither closes on `Escape`. Neither supports arrow-key navigation of items. `MenuActionButton`'s backdrop is a `<div onClick>` with no keyboard equivalent. Menu items are plain `<button>`s without `role="menuitem"`.

---

### F60.17 — `LightboxCarousel` thumbnails are non-keyboard-accessible

- **Severity:** LOW
- **Location:** `packages/react/src/components/LightboxCarousel.tsx:100-111`
- **Category:** a11y

`<div onClick>` thumbnails have no `role="button"`, `tabIndex`, or `onKeyDown`. The close/prev/next `<button>` elements have no `aria-label` (icon-only).

---

### F60.18 — `TextInput` clear button is an `<i onClick>` and fakes a `ChangeEvent`

- **Severity:** LOW
- **Location:** `packages/react/src/components/TextInput.tsx:38-52`
- **Category:** a11y | code-smell

**Description:**
The clear affordance is `<i role="button" onClick={…}>` — not focusable, no keyboard handler, no `aria-label`. It calls `onChange({ target: { value: "" } } as ChangeEvent<HTMLInputElement>)` with a fake event object; any consumer that reads `e.target.name`, `e.currentTarget`, or calls `e.preventDefault()` will crash.

---

### F60.19 — `Segment.selectedId` field is unused

- **Severity:** INFO
- **Location:** `packages/react/src/components/SegmentedControl.tsx:10`
- **Category:** dead-code

`Segment` declares `selectedId?: string` but `SegmentedControl` reads selection from the top-level `selectedId` prop, never from per-segment data.

---

### F60.20 — `SegmentedControl` `selectedId ?? segments[0]?.id` fallback is unreachable

- **Severity:** INFO
- **Location:** `packages/react/src/components/SegmentedControl.tsx:33`
- **Category:** code-smell

`selectedId` is typed as required `string`, so the `??` fallback never fires. Either the type should be `string | undefined` or the fallback should be removed.

---

### F60.21 — `LoadingBar` has hard-coded `aria-valuenow={25}`

- **Severity:** LOW
- **Location:** `packages/react/src/components/LoadingBar.tsx:17`
- **Category:** a11y

An indeterminate progress bar should omit `aria-valuenow` entirely. Hard-coding `25` is misleading to AT.

---

### F60.22 — `ProgressBar` has no ARIA attributes

- **Severity:** LOW
- **Location:** `packages/react/src/components/ProgressBar.tsx:21-33`
- **Category:** a11y

No `role="progressbar"` / `aria-valuemin/max/now`. Ironically `LoadingBar` (indeterminate) has them but `ProgressBar` (determinate, with real values) doesn't.

---

### F60.23 — `ToolButton` has redundant `classes` prop alongside `className`

- **Severity:** INFO
- **Location:** `packages/react/src/components/ToolButton.tsx:8,15`
- **Category:** consistency

Two props do the same thing (`classes` and `className`); both are concatenated. No callers in the repo pass `classes`.

---

### F60.24 — `PopOver` arrow uses hard-coded `white` / `#eee` (breaks dark mode)

- **Severity:** LOW
- **Location:** `packages/react/src/components/PopOver.tsx:440-528`
- **Category:** styling | consistency

**Description:**
The popover body uses `var(--bs-body-bg)` / `var(--bs-border-color)`, but the arrow triangles hard-code `white` (fill) and `#eee` (border). In dark mode the arrow renders as a white triangle against a dark popover body. ~200 lines of inline-style arrow geometry would be better as a CSS module.

---

### F60.25 — `PopOver` portal container reuses `id` as DOM id

- **Severity:** LOW
- **Location:** `packages/react/src/components/PopOver.tsx:190-204`
- **Category:** code-smell

**Description:**
The portal container does `document.getElementById(id)` and creates one if missing. If two popovers share an `id` (e.g. `MarkdownDivWithReferences` uses `"markdown-ref-popover-${ref.id}"` — citation IDs can collide across messages), the second mount reuses the first's container, then the first unmount removes it from under the second. Also, callers pass `id`s like `"select-scorer-popover"` which become global DOM ids without namespacing.

---

### F60.26 — `ComponentIcons.toggleRight` is required but never consumed

- **Severity:** INFO
- **Location:** `packages/react/src/components/ComponentIconContext.tsx:25`
- **Category:** dead-code

Both apps must supply `toggleRight` (App.tsx:51 in each), but no shared component reads `icons.toggleRight`. Dead interface member that forces every host to provide an unused mapping.

---

### F60.27 — `useExtendedFind` error message references wrong provider

- **Severity:** INFO
- **Location:** `packages/react/src/components/ExtendedFindContext.tsx:134`
- **Category:** code-smell

Throws `"useSearch must be used within a SearchProvider"` — should say `useExtendedFind` / `ExtendedFindProvider`.

---

### F60.28 — `ExtendedFindProvider` context value is a fresh object each render

- **Severity:** LOW
- **Location:** `packages/react/src/components/ExtendedFindContext.tsx:117-123`
- **Category:** perf

`contextValue` is built inline (no `useMemo`), so every render of the provider re-renders every consumer (`LiveVirtualList`, find bar). The four callbacks are stable `useCallback`s, so wrapping the object in `useMemo([...])` is trivial.

---

### F60.29 — `TabSet` renders `TabPanel` children twice (props read + clone)

- **Severity:** LOW
- **Location:** `packages/react/src/components/TabSet.tsx:140-145,177`
- **Category:** code-smell | consistency

**Description:**
Callers write `<TabPanel ...>{body}</TabPanel>` as children of `<TabSet>`. `TabSet` ignores the original elements, reads their `props`, and re-renders `<TabPanel {...tab.props} index={i} />`. This means the user-supplied `key` is discarded, and `TabPanel` is effectively rendered with `index` injected. It works, but: (a) `index` is in `TabPanelProps` yet meaningless if the caller sets it; (b) `TabPanel` only renders `children` when `selected` (line 177), so unselected tabs unmount — fine for perf, but `useStatefulScrollPosition` is still called for *every* tab on *every* render via `TabPanels`.

---

### F60.30 — `TabSet` has no keyboard arrow navigation

- **Severity:** LOW
- **Location:** `packages/react/src/components/TabSet.tsx:103-131`
- **Category:** a11y

`role="tablist"` / `role="tab"` / `aria-selected` are present, but WAI-ARIA tabs pattern expects Left/Right arrow to move focus between tabs and a single tab-stop (`tabIndex={0}` only on the active tab). Currently every tab is a separate tab-stop and arrows do nothing.

---

### F60.31 — `ExpandablePanel` applies `className` twice (outer + inner)

- **Severity:** LOW
- **Location:** `packages/react/src/components/ExpandablePanel.tsx:68,78`
- **Category:** consistency

**Evidence:**
```tsx
<div className={clsx(className)}>
  <div ... className={clsx(styles.expandablePanel, ..., className)}>
```

If a caller passes a class with margin/padding/border it's applied to two nested divs. `ChatMessage.tsx:111` and others pass `className` here.

---

### F60.32 — `ExpandablePanel` height check compares `scrollHeight` (px) to `lines * fontSize` but collapses with `${lines}rem`

- **Severity:** LOW
- **Location:** `packages/react/src/components/ExpandablePanel.tsx:46-64`
- **Category:** correctness

**Description:**
`checkOverflow` computes `maxCollapsedHeight = fontSize * lines` (px, using the element's *computed* font-size). The collapsed `maxHeight` is `${lines}rem` (root font-size × lines). If the panel's font-size differs from root (very common — content uses `text-size-smaller`), the toggle may show when content fits, or hide when it overflows. Also `fontSize` ≠ `lineHeight`.

---

### F60.33 — `AutocompleteInput` dropdown doesn't reposition on scroll/resize

- **Severity:** LOW
- **Location:** `packages/react/src/components/AutocompleteInput.tsx:99-110`
- **Category:** correctness

**Description:**
Position is computed once when `showDropdown` flips true. The portal'd `<ul>` uses `position: fixed` with that snapshot. If the page scrolls or the container moves (e.g. inside a `PopOver` that repositions), the listbox detaches from the input. `ToolDropdownButton` handles this (lines 88-97) — `AutocompleteInput` doesn't.

---

### F60.34 — `AutocompleteInput` Enter commits stale value when a suggestion is highlighted

- **Severity:** LOW
- **Location:** `packages/react/src/components/AutocompleteInput.tsx:223-234`
- **Category:** correctness

**Description:**
On Enter with a highlighted suggestion: `selectSuggestion()` calls `onChange(suggestion)` (async state update in parent), then *synchronously* calls `onCommit?.()`. The parent's `onCommit` typically reads its current `value` state — which is still the *typed* text, not the just-selected suggestion. Whether this is a bug depends on the caller, but it's a footgun.

---

### F60.35 — `CopyButton` `setTimeout` fires after unmount

- **Severity:** INFO
- **Location:** `packages/react/src/components/CopyButton.tsx:36-38`
- **Category:** code-smell

`setTimeout(() => setIsCopied(false), 1250)` is never cleared. If the button unmounts within 1.25s of click (e.g. in a virtual list), React logs a "set state on unmounted component" warning (React ≤17) or it's a harmless no-op (React 18+). Minor.

---

### F60.36 — `LiveVirtualList` `Footer` component recreated every render

- **Severity:** LOW
- **Location:** `packages/react/src/components/LiveVirtualList.tsx:372-378,462`
- **Category:** perf

`Footer` is a function declared inside the render body and passed to Virtuoso's `components={{ Footer, ...components }}`. New identity every render → Virtuoso remounts the footer on every parent render. Also `components` spread creates a new object each render even when caller's `components` is stable.

---

### F60.37 — `LiveVirtualList` `MutationObserver` on `document.body` with `subtree: true`

- **Severity:** LOW
- **Location:** `packages/react/src/components/LiveVirtualList.tsx:218-223` (and `useScrollDirection.ts:121-123`)
- **Category:** perf | code-smell

**Description:**
To detect when `scrollRef.current` becomes non-null, both attach a `MutationObserver` to the *entire* document body with `subtree: true`. With 4 `LiveVirtualList` instances and a few `useScrollDirection` consumers, every DOM mutation anywhere on the page (including inside Virtuoso item churn) fires all of these `sync()` callbacks.

**Suggested fix:**
Use a callback ref on the scroll container instead of polling the whole DOM.

---

### F60.38 — `useVirtuosoState` clears persisted list position on every dep change, not just unmount

- **Severity:** LOW
- **Location:** `packages/react/src/hooks/useVirtuosoState.ts:44-57`
- **Category:** correctness

**Description:**
The cleanup `return () => { clearListPosition(); }` runs whenever `delay`, `elementKey`, `handleStateChange`, or `clearListPosition` change identity — not only on unmount. `handleStateChange` depends on `setListPosition` which depends on `useSetValue()` from the host adapter; if that isn't perfectly stable, scroll restoration state is wiped mid-session.

---

### F60.39 — `MarkdownDivWithReferences` attaches DOM listeners that race async markdown render

- **Severity:** MEDIUM
- **Location:** `packages/react/src/components/MarkdownDivWithReferences.tsx:107-178`
- **Category:** correctness

**Description:**
The effect runs when `markdown` changes and queries `container.querySelectorAll(".${styles.cite}")`. But citation `<a>` elements only exist *after* `MarkdownDiv` finishes its **async** render (queue → `startTransition` → `setRenderedHtml`). On first mount the query finds zero links, the effect doesn't re-run (deps don't include `renderedHtml`), and hover-preview never wires up. It only works when the markdown is already in `renderCache`.

**Why it matters / impact:**
Citation hover previews (the entire point of `MarkdownDivWithReferences`) silently fail on first view of any uncached message.

**Suggested fix:**
Either listen via event delegation on the container (`mouseenter` doesn't bubble — use `mouseover` + `closest()`), or add a `MutationObserver`, or have `MarkdownDiv` expose an `onRendered` callback.

---

### F60.40 — `MarkdownDivWithReferences` uses shared `useProperty("popover","visibleKey")` across all instances

- **Severity:** LOW
- **Location:** `packages/react/src/components/MarkdownDivWithReferences.tsx:52-55`
- **Category:** consistency

All instances share the same property-bag key (`id="popover"`, `prop="visibleKey"`). Hovering a citation in message A while a popover is open in message B closes B. May be intentional (one popover at a time), but it's implicit global state in a "div" component.

---

### F60.41 — Styling-primitive drift across the library

- **Severity:** INFO
- **Location:** package-wide
- **Category:** styling | consistency

**Description:**
Four distinct styling vocabularies coexist:
1. **Bootstrap globals**: `"btn"`, `"nav"`, `"nav-pills"`, `"nav-link"`, `"active"`, `"tab-pane"` (TabSet, NavPills, ToolButton, ExpandablePanel)
2. **`--bs-*` CSS vars**: Card, PopOver, ToolButton, AutocompleteInput, SegmentedControl
3. **`--vscode-*` CSS vars**: Modal, MenuActionButton, ConfirmationDialog (via `VscodeButton`)
4. **Inline `style={{...}}`**: PopOver (~200 lines), AnsiDisplay run styles, LiveVirtualList

`Modal` and `ConfirmationDialog` are scout-flavored (vscode vars + `@vscode-elements/react-elements` import) but live in the shared package; `apps/inspect` has its *own* `components/Modal` (see `ResultsPanel.tsx:9`) — a sign the shared one didn't fit.

---

### F60.42 — `usePrismHighlight` re-highlights on `contentLength` only

- **Severity:** LOW
- **Location:** `packages/react/src/hooks/usePrismHighlight.ts:26-71`
- **Category:** correctness

**Description:**
Effect deps are `[contentLength, containerRef]`. If `code` changes but its length stays the same (e.g. user toggles between two same-length JSON blobs in `JSONPanel`), the effect doesn't re-run; the `data-highlighted` attribute on the old `<code>` node is gone (React re-rendered text content), but the MutationObserver only fires on `childList`, not `characterData`. The `requestAnimationFrame` initial call also won't re-fire. Edge case, but `SourceCodePanel` and `JSONPanel` both pass `.length`.

---

### F60.43 — `AnsiDisplay` does heavy parse on every render with no memoization

- **Severity:** LOW
- **Location:** `packages/react/src/components/AnsiDisplay.tsx:22-77`
- **Category:** perf

`new ANSIOutput()` + `processOutput(output)` + `getUniformBackgroundColor()` (two passes over all lines) run on every render — including the re-render triggered by `setShowRaw`. Should be wrapped in `useMemo([output])`.

---

### F60.44 — `useRevokableUrls` leaks URLs on re-render in `HumanBaselineView`

- **Severity:** LOW
- **Location:** `packages/react/src/components/HumanBaselineView.tsx:42-77` + `hooks/useRevokableUrls.ts`
- **Category:** correctness | perf

**Description:**
`HumanBaselineView` calls `createRevokableUrl(sessionLog.input)` etc. **during render**, inside a `for` loop, with no memoization. Every re-render creates 3×N new Blob URLs and pushes them onto `urlsRef`. They're only revoked on unmount. With long-lived views this accumulates. The hook is correct; the call site isn't.

---

### F60.45 — `ToolButton` renders bare `0` when `label={0}`

- **Severity:** INFO
- **Location:** `packages/react/src/components/ToolButton.tsx:33-36`
- **Category:** code-smell

`label ? styles.marginRight : undefined` — if `label` is the number `0` or empty string `""`, the icon gets no right margin even though `{label}` renders. `label` is typed `string | ReactNode` so `0` is valid. Minor.

---

## Files reviewed

- [x] `components/AnsiDisplay.tsx` — perf (no memo), missing `.ansiDisplayLine` CSS
- [x] `components/AsciinemaPlayer.tsx` — `className` prop ignored
- [x] `components/AutocompleteInput.tsx` — solid a11y; no scroll-reposition; Enter race
- [x] `components/Card.tsx` + `.module.css` — `padded={false}` broken by `!important`
- [x] `components/ComponentIconContext.tsx` — `toggleRight` unused
- [x] `components/ComponentNavigationContext.tsx` — clean
- [x] `components/ConfirmationDialog.tsx` — vscode-coupled in shared pkg
- [x] `components/CopyButton.tsx` — uncleaned timeout
- [x] `components/EmptyPanel.tsx` — CSS file never imported; bootstrap `.container` collision
- [x] `components/ErrorPanel.tsx` + `.module.css` — `white-space: prewrap` typo
- [x] `components/ExpandablePanel.tsx` + `.module.css` — `padBottom` missing; className duped; rem vs px mismatch
- [x] `components/ExtendedFindContext.tsx` — wrong error msg; unmemoized context value
- [x] `components/HumanBaselineView.tsx` — blob URL leak per render
- [x] `components/JsonPanel.tsx` — clean (global CSS, not module)
- [x] `components/LabeledValue.tsx` + `.module.css` — `labeledValueValue` missing
- [x] `components/LightboxCarousel.tsx` + `.module.css` — listener leak, scoping bug, swapped prev/next, no-wrap next
- [x] `components/LiveVirtualList.tsx` — Footer remount, body-wide MutationObserver
- [x] `components/LoadingBar.tsx` — hardcoded `aria-valuenow=25`
- [x] `components/MarkdownDiv.tsx` — queue cancel() bug; self-dep effect
- [x] `components/MarkdownDivWithReferences.tsx` — listener-attach race vs async render
- [x] `components/MenuActionButton.tsx` — no a11y/keyboard
- [x] `components/Modal.tsx` — no role/focus-trap; global Enter intercept
- [x] `components/NavPills.tsx` — dead component
- [x] `components/NoContentsPanel.tsx` — clean
- [x] `components/NonIdealState.tsx` — clean
- [x] `components/PopOver.tsx` — hardcoded white arrow; portal id collision; large inline styles
- [x] `components/Preformatted.tsx` — clean
- [x] `components/ProgressBar.tsx` — no ARIA
- [x] `components/PulsingDots.tsx` — clean
- [x] `components/SegmentedControl.tsx` — dead `Segment.selectedId`; unreachable `??`
- [x] `components/SourceCodePanel.tsx` — length-only highlight dep
- [x] `components/StickyScroll.tsx` — clean
- [x] `components/StickyScrollContext.tsx` — clean (consumer lives in inspect-components)
- [x] `components/TabSet.tsx` + `.module.css` — `pill` missing; quoted CSS var; no kbd nav; double-render pattern
- [x] `components/TextInput.tsx` — fake ChangeEvent; `<i>` as button
- [x] `components/ToolButton.tsx` — redundant `classes` prop
- [x] `components/ToolDropdownButton.tsx` — no a11y/keyboard
- [x] `components/markdownRendering.ts` — reviewed (security covered by existing tests)
- [x] `hooks/*` — all reviewed; notable: useDocumentTitle (scout-specific), useVirtuosoState (over-eager clear), usePrismHighlight (length dep), useScrollDirection (body MutationObserver)
- [x] `state/ComponentStateContext.tsx` — clean

## Open questions / needs verification

- **F60.3 / F60.4** — `LightboxCarousel` is only reachable via `HumanBaselineView` (terminal session playback). Worth confirming whether anyone has actually opened a multi-session human-baseline view in production; the prev/next button positioning bug suggests not.
- **F60.39** — Need to confirm in-browser whether citation hover works on first load of an uncached message. The `renderCache` may mask this in dev (hot reload keeps cache warm).
- **F60.1** — Verify visually in `SampleDisplay.tsx` that the `padded={false}` cards do show unwanted 0.5rem padding.
- **F60.41** — Is there an intent to unify on `--vscode-*` vs `--bs-*`? `Modal.module.css` uses vscode vars exclusively, which won't resolve in the inspect app unless its theme defines them.
