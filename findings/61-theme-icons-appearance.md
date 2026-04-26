# Theming, Icons, and Appearance

**Reviewer scope:** `packages/theme/src/**`, `apps/inspect/src/app/appearance/**`, `apps/inspect/src/app/App.css`, app-level global CSS (`apps/inspect/src/components/*.css`), all icon registries (`ApplicationIcons`, `TranscriptIcons`, `IconsContext`, `TimelineIconsContext`, `ComponentIconContext`)
**Date:** 2026-04-22

---

## Summary

The theming layer carries significant legacy debt: ~40% of `ApplicationIcons` keys and a large block of `base.css` selectors are dead, and the appearance helpers (`colors.ts`, `fonts.ts`, `styles.ts`) are almost entirely unused. There are **four parallel icon registries** that have already drifted (e.g. three different "fork" icons). Several CSS-variable references are typo'd or reference variables Bootstrap never defines (`--bs-body-background`, `--bs-error-bg-subtle`, `--inspect-fond-size-larger`, `--inspect-text-size-small`, `--body-color`), so the affected rules silently no-op. Dark-mode handling is patchy: only two `[data-bs-theme="dark"]` overrides exist, while several components hardcode light-mode hex colors. z-indexes are ad-hoc magic numbers ranging from `-1` to `10000` with no token scale.

---

## Findings

### F61.1 — Undefined Bootstrap variable `--bs-body-background` (3×)

- **Severity:** MEDIUM
- **Location:** `packages/theme/src/base.css:534`, `:544`, `:639`
- **Category:** correctness / styling

**Description:**
Three rules reference `var(--bs-body-background)`. Bootstrap 5 defines `--bs-body-bg`, not `--bs-body-background`. The variable resolves to nothing.

**Evidence:**
```css
.log :not(pre) > code[class*="language-"],
.log pre[class*="language-"] {
  background-color: var(--bs-body-background);   /* undefined */
}
.accordion-item:not(.no-highlight) .accordion-button:not(.collapsed) {
  ...
  background-color: var(--bs-body-background);   /* undefined */
}
```

**Why it matters / impact:**
The accordion-button "expanded" state intended to switch to body-bg is silently ignored; the workspace/log Prism backgrounds also no-op. Because the parent `.log` / `.workspace` selectors are themselves likely dead (see F61.18), the visible impact today is limited to the accordion rule.

**Suggested fix:**
Replace with `var(--bs-body-bg)`.

---

### F61.2 — Undefined `--bs-error-bg-subtle` / `--bs-error-text-emphasis` in MessageBand

- **Severity:** MEDIUM
- **Location:** `apps/inspect/src/components/MessageBand.css:25-26,38`
- **Category:** correctness / styling

**Description:**
Bootstrap 5 names the red palette `danger`, not `error`. `--bs-error-bg-subtle` and `--bs-error-text-emphasis` do not exist.

**Evidence:**
```css
.message-band.error {
  background-color: var(--bs-error-bg-subtle);
  color: var(--bs-error-text-emphasis);
}
.message-band-btn.error {
  color: var(--bs-error-text-emphasis);
}
```

**Why it matters / impact:**
Any `<MessageBand type="error">` renders with no background colour and default text colour — visually indistinguishable from `info`, so users may miss error banners.

**Suggested fix:**
Use `--bs-danger-bg-subtle` / `--bs-danger-text-emphasis`.

---

### F61.3 — Typo `--inspect-fond-size-larger` (font → fond)

- **Severity:** LOW
- **Location:** `apps/inspect/src/components/FindBand.css:50` (also duplicated in `apps/scout/src/app/components/FindBand.css:41`)
- **Category:** correctness / styling

**Evidence:**
```css
.findBand .btn.next,
.findBand .btn.prev {
  font-size: var(--inspect-fond-size-larger);
}
```

**Why it matters / impact:**
Prev/Next chevron buttons in the Find bar fall back to inherited 0.9rem instead of 1.1rem, making them smaller than designed.

---

### F61.4 — Typo `--inspect-text-size-small` (should be `--inspect-font-size-small`)

- **Severity:** LOW
- **Location:** `packages/inspect-components/src/chat/tools/ToolInput.module.css:17,22`
- **Category:** correctness / styling

**Evidence:**
```css
.toolInput pre code {
  font-size: var(--inspect-text-size-small) !important;
}
```

**Why it matters / impact:**
Tool-input code blocks ignore the small-size override (the `!important` is wasted on an undefined value).

---

### F61.5 — Typo `text-sixe-small` className (2×)

- **Severity:** LOW
- **Location:** `packages/inspect-components/src/usage/TokenTable.tsx:51,61`
- **Category:** correctness / styling

**Evidence:**
```tsx
className={clsx("text-sixe-small", ...)}
```

**Why it matters / impact:**
Token-table header cells render at base font size instead of small; alignment with body cells is off.

---

### F61.6 — Unclosed `var(` in inline style string

- **Severity:** MEDIUM
- **Location:** `packages/inspect-components/src/content/MetaDataGrid.tsx:55`
- **Category:** correctness / styling

**Evidence:**
```tsx
borderBottom: `${!options?.plain ? "solid 1px var(--bs-light-border-subtle" : ""}`,
```

**Why it matters / impact:**
Browsers tolerate the missing `)` (CSS error recovery closes it), so this currently renders, but it's invalid CSS and could break under stricter CSSOM parsers or future bundler minification.

---

### F61.7 — Typo `var(--body-color)` (missing `bs-` prefix)

- **Severity:** LOW
- **Location:** `apps/inspect/src/components/Card.css:42`
- **Category:** correctness / styling

**Evidence:**
```css
.card-collapsing-header-contents {
  color: var(--body-color);
```

**Why it matters / impact:**
Resolves to nothing. However the entire file is dead (see F61.19), so no runtime impact.

---

### F61.8 — Missing `bi` base class on Bootstrap icon

- **Severity:** LOW
- **Location:** `packages/inspect-components/src/transcript/timeline/components/TimelineSelector.tsx:56`
- **Category:** correctness / styling

**Evidence:**
```tsx
<i className={clsx("bi-chevron-down", styles.chevron)} />
```

**Why it matters / impact:**
`bi-chevron-down` sets `content` via `::before`, but the `bi` base class supplies `font-family: "bootstrap-icons"`, `display`, `line-height`, antialiasing. Without it the glyph renders only because the user-agent picks up the codepoint via the global `@font-face`, but it loses the canonical metrics (e.g. `-webkit-font-smoothing`, `-.125em` vertical-align). Every other icon in the codebase uses the two-class form.

**Suggested fix:**
`clsx("bi", "bi-chevron-down", styles.chevron)` — or use `useTimelineIcons().chevron.down` which already exists in this file.

---

### F61.9 — `fork` icon inconsistent across the four icon registries

- **Severity:** MEDIUM
- **Location:** `apps/inspect/src/app/appearance/icons.ts:80` vs `packages/inspect-components/src/transcript/icons.ts:23` vs `packages/inspect-components/src/transcript/timeline/components/TimelineIconsContext.tsx:22`
- **Category:** consistency

**Description:**
| Registry | Value |
|---|---|
| `ApplicationIcons.fork` | `bi bi-signpost-split` |
| `TranscriptIcons.fork` | `bi bi-sign-intersection-y-fill` |
| `TimelineIcons.fork` (default) | `bi bi-sign-intersection-y-fill` |

**Why it matters / impact:**
The inspect app never overrides `TimelineIconsContext` or `IconsContext` (no provider found in `apps/inspect/src/**`), so the package defaults win and the app-level `ApplicationIcons.fork` is silently ignored. If the app ever does wire its icons through, the fork glyph will change shape between the outline/timeline and any app-level UI.

---

### F61.10 — `BranchEvent` uses the *info* icon in transcript but *fork* icon in outline

- **Severity:** MEDIUM
- **Location:** `packages/inspect-components/src/transcript/BranchEventView.tsx:37` vs `packages/inspect-components/src/transcript/outline/OutlineRow.tsx:124`
- **Category:** consistency / event-display

**Evidence:**
```tsx
// BranchEventView.tsx
icon={TranscriptIcons.info}            // bi-info-circle
// OutlineRow.tsx (same event type)
return TranscriptIcons.fork;           // bi-sign-intersection-y-fill
```

**Why it matters / impact:**
The same `BranchEvent` shows a generic ⓘ in the transcript body but a fork glyph in the left-hand outline, breaking the "same concept → same icon" contract and making it harder to correlate outline rows with transcript panels.

**Suggested fix:**
`BranchEventView` should use `TranscriptIcons.fork`.

---

### F61.11 — Task-level "Cancelled" / "Error" status icons differ from sample/log-list status icons

- **Severity:** MEDIUM
- **Location:** `apps/inspect/src/app/log-view/title-view/StatusPanel.tsx:12-29` vs `apps/inspect/src/app/log-list/grid/columns/hooks.tsx:218-227` vs `apps/inspect/src/app/samples/status/sampleStatus.tsx:66-71`
- **Category:** consistency

**Description:**
| Status | StatusPanel (title bar) | Log-list grid | Sample grid |
|---|---|---|---|
| Cancelled | `ApplicationIcons.logging["info"]` → `bi-info-square` | `ApplicationIcons.cancelled` → `bi-x-circle` | `ApplicationIcons.cancelled` → `bi-x-circle` |
| Error | `ApplicationIcons.logging["error"]` → `bi-x-circle` | `ApplicationIcons.error` → `bi-exclamation-circle-fill` | `ApplicationIcons.error` → `bi-exclamation-circle-fill` |

**Why it matters / impact:**
The title bar shows ⓘ for a cancelled run while the row beneath it in the log list shows ⊗ for the same run. Worse, title-bar "Error" reuses the same `bi-x-circle` glyph that the grids use for "Cancelled", so the two states are visually swapped between views.

**Suggested fix:**
`StatusPanel` should use `ApplicationIcons.cancelled` / `ApplicationIcons.error` directly.

---

### F61.12 — Four duplicate icon registries with copy-pasted defaults

- **Severity:** MEDIUM
- **Location:** `apps/inspect/src/app/appearance/icons.ts`, `packages/inspect-components/src/transcript/icons.ts`, `packages/inspect-components/src/content/IconsContext.tsx:24-43`, `packages/inspect-components/src/transcript/timeline/components/TimelineIconsContext.tsx:19-29`
- **Category:** code-smell / consistency

**Description:**
`ApplicationIcons`, `TranscriptIcons`, `IconsContext` defaults, and `TimelineIconsContext` defaults all hardcode overlapping Bootstrap icon strings (`agent`, `model`, `error`, `approvals`, `limits`, `logging`, `tree`, `checkbox`, `fork`, `compaction`, `solvers`, `iconForMimeType`). The inspect app never wraps its tree in `IconsContext.Provider` or `TimelineIconsContext.Provider`, so the package defaults are what actually render — meaning `ApplicationIcons` is **not** the single source of truth despite its name.

**Why it matters / impact:**
Already drifting (F61.9). Any future icon change must be made in up to four places; missing one produces silent visual inconsistency.

**Suggested fix:**
Either (a) have `TranscriptIcons` import from a shared constants module that `ApplicationIcons` also re-exports, or (b) make the inspect app actually provide `IconsContext`/`TimelineIconsContext` from `ApplicationIcons` and drop the package-side defaults.

---

### F61.13 — `iconForMimeType` exported from app but never used

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/appearance/icons.ts:11-19`
- **Category:** dead-code

**Description:**
`iconForMimeType` is duplicated verbatim in `IconsContext.tsx:38-42` (which is what `ContentDocumentView` actually consumes) and again in `apps/scout/src/icons.ts`. The `apps/inspect` copy has zero importers.

---

### F61.14 — `ApplicationColors` is dead code

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/appearance/colors.ts:1-9`
- **Category:** dead-code

**Description:**
`ApplicationColors` (logging-level → CSS-var colour map) is exported but has no importers anywhere in the monorepo. `LoggerEventView` does not colour-code by level at all.

---

### F61.15 — `ApplicationStyles` / `FontSize` / `TextStyle` almost entirely unused; `FontSize` scale out of sync with CSS

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/appearance/styles.ts`, `apps/inspect/src/app/appearance/fonts.ts`
- **Category:** dead-code / consistency

**Description:**
- `ApplicationStyles.lineClamp` is the only member referenced (once, `SampleErrorView.tsx:35`). `moreButton`, `threeLineClamp`, `wrapText`, `scoreFills` have zero callers.
- `FontSize` / `TextStyle` are referenced **only** by the dead `ApplicationStyles.moreButton`.
- `FontSize` defines `small` and `smaller` to the *same* value (`-0.1` → 0.8rem) and omits `largest` / `smallest` / `smallestest`, so it is out of sync with the CSS scale in `base.css:27-36` (which itself sets `small` and `smaller` to the same 0.8rem — see F61.24).

**Suggested fix:**
Delete `colors.ts` and `fonts.ts`; reduce `styles.ts` to `lineClamp` (or inline it).

---

### F61.16 — ~36 unused keys in `ApplicationIcons`

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/appearance/icons.ts`
- **Category:** dead-code

**Description:**
The following top-level keys have no `ApplicationIcons.<key>` reference anywhere in `apps/inspect/src/**`:
`agent`, `approve`, `approvals`, `caret`, `changes`, `config`, `epoch`, `edit`, `eval`, `"eval-set"`, `fork`, `home`, `input`, `inspect`, `json`, `limits`, `link`, `menu`, `messages`, `metadata`, `model`, `more`, `"multiple-choice"`, `options`, `retry`, `role`, `samples`, `sandbox`, `search`, `solvers`, `step`, `subtask`, `transcript`, `tree`, `turns`, `usage`.

**Why it matters / impact:**
~50% of the registry is noise. Several of these were the *intended* injection points for `IconsContext` / `TimelineIconsContext` (e.g. `tree`, `role`, `model`, `search`, `agent`) but the providers were never wired up (F61.12).

---

### F61.17 — Redundant duplicate icon keys inside `ApplicationIcons`

- **Severity:** INFO
- **Location:** `apps/inspect/src/app/appearance/icons.ts`
- **Category:** consistency

**Description:**
Several distinct semantic keys map to the same glyph, suggesting either intentional aliasing or accidental duplication:
- `loading` and `refresh` → `bi bi-arrow-clockwise`
- `config` and `options` → `bi bi-gear`
- `menu`, `sidebar`, `limits.tokens` → `bi bi-list`
- `limits.time` and `pendingTask` → `bi bi-clock`
- `limits.execution` and `usage` → `bi bi-stopwatch`
- `next`, `"toggle-right"`, `chevron.right` → `bi bi-chevron-right`
- `expand.down`, `chevron.down` → `bi bi-chevron-down`
- `edit`, `approvals.modify` → `bi bi-pencil-square`

Most are harmless aliasing, but combined with F61.16 it makes the registry hard to audit.

---

### F61.18 — Large block of dead selectors in `base.css`

- **Severity:** LOW
- **Location:** `packages/theme/src/base.css`
- **Category:** dead-code

**Description:**
The following global selectors have **zero** matching `className` literals in any `.ts/.tsx/.html` under `ts-mono/`:
`.tbd` (547), `.font-title` (578), `.font-subtitle` (583), `.tight-paragraphs` (588), `.tight-last-paragraph` (592), `.hide-when-collapsed` (610), `.hide-when-expanded` (614), `.no-bottom-padding-when-expanded` (618), `.zerowidth-when-expanded` (622), `.zeroheight-when-expanded` (631), `.giant-text-when-expanded` (651), `.full-flex-basis-when-expanded` (659), `.highlight-when-expanded` (688-695), `.toggle-rotated` (701-732), `.fadeout-when-not-collapsed` (734), `.do-not-collapse-self` (772), `.left-to-right-animate` + `@keyframes moveLeftToRight` (839-851), `.hideSelection` (1194), `.multi-score-label` (254), `.sidebar .list-group*` (489-514, 372-383), `.log pre*` (522-535), `#sidebarToggle` (456), all `.accordion-*` rules (278-283, 321-323, 635-714).

**Why it matters / impact:**
~180 lines of CSS shipped to every viewer instance and VSCode webview that can never match. Several reference further undefined vars (F61.1). The `.sidebar`/accordion rules are clearly leftovers from a pre-ag-grid layout.

---

### F61.19 — `apps/inspect/src/components/Card.css` is dead (never imported)

- **Severity:** LOW
- **Location:** `apps/inspect/src/components/Card.css`
- **Category:** dead-code

**Description:**
No `import "./Card.css"` exists. None of its class names (`card-header-container`, `card-header-icon`, `card-collaping-header` [sic — typo], `card-collapsing-header-*`) appear in any TSX. The shared `packages/react/src/components/Card.module.css` is what's actually used. File also contains the `var(--body-color)` typo (F61.7) and the `card-collaping-header` spelling error.

---

### F61.20 — `MorePopOver.css` is empty

- **Severity:** INFO
- **Location:** `apps/inspect/src/components/MorePopOver.css`
- **Category:** dead-code

**Description:** 0-byte (1 blank line) file. Safe to delete along with its import (if any).

---

### F61.21 — `loggingIcons` missing `trace` and `sandbox` levels

- **Severity:** LOW
- **Location:** `apps/inspect/src/app/appearance/icons.ts:1-9`, `packages/inspect-components/src/transcript/icons.ts:35-43`
- **Category:** consistency / event-display

**Description:**
The generated `LoggingMessage.level` union is `"debug" | "trace" | "http" | "sandbox" | "info" | "warning" | "error" | "critical"`. Both `loggingIcons` maps cover `notset/debug/http/info/warning/error/critical` but omit `trace` and `sandbox`. `LoggerEventView` falls back to `TranscriptIcons.info`, so these levels render with a generic ⓘ rather than a level-specific glyph.

---

### F61.22 — Hardcoded light-mode colours that ignore `data-bs-theme="dark"`

- **Severity:** MEDIUM
- **Location:** `apps/inspect/src/app/log-list/ViewerOptionsPopover.module.css:44,65-71`; `apps/inspect/src/components/ActivityBar.module.css:25,33`; `packages/react/src/components/LoadingBar.module.css:25`; `packages/react/src/components/PopOver.tsx:440-482`; `packages/inspect-components/src/chat/server-tools/ServerToolCall.module.css:36`
- **Category:** styling / a11y

**Evidence:**
```css
/* ViewerOptionsPopover.module.css */
.notSet      { color: #666; }
.messageSuccess { background-color: #d4edda; color: #155724; }
.messageError   { background-color: #f8d7da; color: #721c24; }

/* ActivityBar.module.css / LoadingBar.module.css */
background-color: #3b82f6;

/* PopOver.tsx */
borderColor: "#eee transparent transparent transparent",

/* ServerToolCall.module.css */
color: red;
```

**Why it matters / impact:**
`index.html` sets `data-bs-theme` from a query param, but only **two** rules in `base.css` (lines 442, 510) react to it. Everything above renders identical pastel/light values on a dark background (e.g. `#d4edda` green pill on dark grey → poor contrast). The `.vscode-dark` selector handles the VSCode case but not the standalone-browser dark case.

**Suggested fix:**
Use `var(--bs-success-bg-subtle)` / `var(--bs-danger-bg-subtle)` / `var(--bs-secondary)` / `var(--bs-primary)` etc.

---

### F61.23 — `--bs-tertiary-bg` defined twice in the same vscode block

- **Severity:** INFO
- **Location:** `packages/theme/src/base.css:169` and `:191`
- **Category:** code-smell

**Evidence:**
```css
body[class^="vscode-"] {
  ...
  --bs-tertiary-bg: var(--vscode-list-hoverBackground);   /* 169 */
  ...
  --bs-tertiary-bg: var(--vscode-list-hoverBackground);   /* 191 */
```

Both lines assign the same value, so behaviour is correct; it just signals copy-paste drift in the override block.

---

### F61.24 — Font-size scale: `small` == `smaller`; redundant token

- **Severity:** INFO
- **Location:** `packages/theme/src/base.css:33-34`
- **Category:** consistency

**Evidence:**
```css
--inspect-font-size-small: 0.8rem;
--inspect-font-size-smaller: 0.8rem;
```

**Why it matters / impact:**
`.text-size-small` and `.text-size-smaller` are visually identical. Either give `smaller` 0.75rem or collapse the two tokens; today there's no way to get a step between 0.8 and 0.7.

---

### F61.25 — z-index values are ad-hoc magic numbers with no scale

- **Severity:** LOW
- **Location:** repo-wide (38 occurrences)
- **Category:** styling / code-smell

**Description:**
Values in use: `-1, 1, 2, 3, 10, 998, 999, 1000, 1001, 1040, 1049, 1050, 1060, 1200, 9998, 9999, 10000`. Notable potential conflicts:
- `LightboxCarousel` overlay (`9998-10000`) vs `AutocompleteInput` dropdown (`10000`) vs `ValidationSetSelector` (`10000`) — autocomplete inside a lightbox would tie.
- `ActivityBar` / `LoadingBar` at `1200` sit above `FindBand` at `1060` and `Modal` at `1050` — a loading shimmer would paint over an open modal.
- `data-tooltip` pseudo-element at `1000` (base.css:794) sits *under* `SampleDisplay` header at `1001`.

**Suggested fix:**
Define a small set of `--inspect-z-*` tokens (sticky, dropdown, modal, toast, lightbox) in `base.css` and reference those.

---

### F61.26 — `kArrowRightIcon` local constant duplicates `TranscriptIcons.arrows.right`

- **Severity:** INFO
- **Location:** `packages/inspect-components/src/transcript/SubtaskEventView.tsx:12,86`
- **Category:** consistency / code-smell

**Evidence:**
```tsx
const kArrowRightIcon = "bi bi-arrow-right";
...
<i className={kArrowRightIcon} />
```

`TranscriptIcons.arrows.right` already exists with the same value and is imported elsewhere in this directory.

---

### F61.27 — `SubtaskEventView` renders no panel icon

- **Severity:** LOW
- **Location:** `packages/inspect-components/src/transcript/SubtaskEventView.tsx:49-63`
- **Category:** consistency / event-display

**Description:**
`SubtaskEventView` calls `<EventPanel ... />` without an `icon` prop, even for `event.type === "fork"`. Every other concrete event view passes one. The outline (`OutlineRow.tsx:124`) shows `TranscriptIcons.fork` for the same node, so the outline row has an icon while the corresponding transcript panel header has none.

---

### F61.28 — `.copy-button i.bi` rule applies vscode foreground even outside VS Code

- **Severity:** LOW
- **Location:** `packages/theme/src/base.css:284-288`
- **Category:** styling

**Evidence:**
```css
.copy-button i.bi,
.download-scan-button i.bi,
body[class^="vscode-"] .navbar-text i.bi {
  color: var(--vscode-editor-foreground);
}
```

**Why it matters / impact:**
The first two selectors are **not** scoped to `body[class^="vscode-"]`, so in the standalone browser viewer they set `color` to `var(--vscode-editor-foreground)`. This only resolves because `vscode.css` happens to define `--vscode-editor-foreground: #3b3b3b` at `:root` as a fallback — but it forces copy buttons to dark-grey even when `data-bs-theme="dark"` is active (no dark override for that var outside VS Code).

---

### F61.29 — `tool-output` / Prism background hardcoded; no `[data-bs-theme="dark"]` variant

- **Severity:** LOW
- **Location:** `packages/theme/src/base.css:857-870`
- **Category:** styling

**Evidence:**
```css
pre[class*="language-"], .tool-output { background-color: #f8f8f8; }
.vscode-dark pre[class*="language-"], .vscode-dark .tool-output { background-color: #333333; }
```

**Why it matters / impact:**
Browser dark mode (`data-bs-theme="dark"` without `.vscode-dark`) leaves tool-output blocks at `#f8f8f8` light grey on a dark page. Only VS Code dark gets the override.

---

### F61.30 — `StatusPanel` leaves an empty inline `style={{}}`

- **Severity:** INFO
- **Location:** `apps/inspect/src/app/log-view/title-view/StatusPanel.tsx:55`
- **Category:** code-smell

**Evidence:**
```tsx
<i className={clsx(icon, styles.statusIcon)} style={{}} />
```

Vestigial; harmless but should be removed.

---

## Files reviewed

- [x] `packages/theme/src/base.css` — 1200-line global sheet; many dead selectors, 3 undefined-var refs, 1 dup declaration
- [x] `packages/theme/src/vscode.css` — vscode fallback palette; clean
- [x] `packages/theme/src/base.d.ts` / `vscode.d.ts` — side-effect stubs; clean
- [x] `apps/inspect/src/app/appearance/icons.ts` — ~50% unused keys; `iconForMimeType` dead
- [x] `apps/inspect/src/app/appearance/colors.ts` — entirely dead
- [x] `apps/inspect/src/app/appearance/fonts.ts` — only consumed by dead `styles.ts` members; scale out of sync with CSS
- [x] `apps/inspect/src/app/appearance/styles.ts` — only `lineClamp` used
- [x] `apps/inspect/src/app/App.css` — clean (SVG mask icons + print rules)
- [x] `apps/inspect/src/app/App.tsx` (icon wiring) — provides `ComponentIconProvider` but not `IconsContext`/`TimelineIconsContext`
- [x] `apps/inspect/src/components/Card.css` — dead file
- [x] `apps/inspect/src/components/MessageBand.css` — undefined `--bs-error-*` vars
- [x] `apps/inspect/src/components/FindBand.css` — `fond-size` typo
- [x] `apps/inspect/src/components/MorePopOver.css` — empty
- [x] `apps/inspect/src/components/DownloadButton.css` / `DownloadPanel.css` — clean
- [x] `apps/inspect/src/app/log-list/ViewerOptionsPopover.module.css` — hardcoded light colours
- [x] `packages/inspect-components/src/transcript/icons.ts` — duplicates ApplicationIcons subset; `fork` differs
- [x] `packages/inspect-components/src/content/IconsContext.tsx` — default-only; never overridden by inspect app
- [x] `packages/inspect-components/src/transcript/timeline/components/TimelineIconsContext.tsx` — default-only; never overridden
- [x] `packages/inspect-components/src/transcript/timeline/components/TimelineSelector.tsx` — missing `bi` base class
- [x] `packages/react/src/components/ComponentIconContext.tsx` — clean (throws if no provider; good)
- [x] `apps/inspect/src/app/samples/status/sampleStatus.tsx` + `.module.css` — clean; used as consistency baseline
- [x] `apps/inspect/src/app/log-view/title-view/StatusPanel.tsx` — inconsistent cancelled/error icons
- [x] `apps/inspect/index.html` — theme-switch entry point

## Open questions / needs verification

- F61.18 dead-selector list was derived by grepping `*.ts/*.tsx/*.html` for literal class names; if any class is added via runtime string concatenation (none found) it could be a false positive.
- F61.16 counts only `apps/inspect`; some "unused" `ApplicationIcons` keys might be intentionally kept for parity with `apps/scout`'s `icons.ts` — worth checking before deletion.
- Is there any consumer that sets `data-bs-theme="dark"` without also adding a `vscode-dark` body class? If not, F61.22/F61.28/F61.29 are theoretical until standalone dark mode ships.
