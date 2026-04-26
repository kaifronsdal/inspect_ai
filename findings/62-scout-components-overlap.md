# scout-components — overlap & drift with inspect

**Reviewer scope:** `src/inspect_ai/_view/ts-mono/packages/scout-components/src/` (all files), cross-referenced against `packages/inspect-components/`, `packages/react/`, and `apps/inspect/`
**Date:** 2026-04-22

---

## Summary

`scout-components` is small (2 modules: `scanner-result-detail/` and `sentinels/`) and largely scout-specific — it is **not** a fork of `inspect-components`. However, despite the name, **the inspect app depends on it** (`apps/inspect/package.json:96` declares `@tsmono/scout-components` and 4 inspect source files import from it), so it is effectively a shared package. No bug-fix drift between forked components was found because there are no forked components. The findings below are dead code, duplicated tests, and minor display issues.

---

## Findings

### F62.1 — Dead `asciinema-player.d.ts` stub (also stale vs inspect-components copy)

- **Severity:** LOW
- **Location:** `packages/scout-components/src/types/asciinema-player.d.ts:1`
- **Category:** dead-code

**Description:**
`scout-components` ships a 1-line ambient module stub for `asciinema-player`, but nothing in the package imports `asciinema-player` and it is not a declared dependency. The only real consumer in the monorepo is `packages/react/src/components/AsciinemaPlayer.tsx`, which has its own (fully-typed) `.d.ts`. The `inspect-components` copy of this file is also unused but has been fleshed out to 42 lines of real types — so the two copies have drifted, while both are dead.

**Evidence:**
```ts
// scout-components/src/types/asciinema-player.d.ts
declare module "asciinema-player";
```
`rg "asciinema" packages/scout-components/` → only the `.d.ts` itself.
`rg "asciinema" packages/inspect-components/ -g '!*.d.ts'` → no matches.

**Suggested fix:**
Delete `packages/scout-components/src/types/asciinema-player.d.ts` and `packages/inspect-components/src/types/asciinema-player.d.ts`. Keep the canonical one in `packages/react/src/types/`.

---

### F62.2 — inspect app re-tests scout-components internals (duplicate test suites)

- **Severity:** LOW
- **Location:** `apps/inspect/src/tests/samples/scanReferences.test.ts:11-89` vs `packages/scout-components/src/sentinels/scannerReferences.test.ts`
- **Category:** consistency / dead-code

**Description:**
The inspect app's `scanReferences.test.ts` contains three `describe` blocks (`isScannerScore`, `metadataWithoutScannerKeys`, `readScannerReferences`) that import from `@tsmono/scout-components/sentinels` and assert exactly the same behaviour already covered by `scannerReferences.test.ts` inside the scout-components package. Only the fourth block (`buildScoreMarkdownRefs`, lines 91-117) tests inspect-app-local code.

**Why it matters:**
Two suites must be kept in sync; the inspect copy already lags (it doesn't assert `scanner_content` stripping, which the package test does). Maintenance burden with no extra coverage.

**Suggested fix:**
Drop the first three `describe` blocks from the inspect-app test; keep only `buildScoreMarkdownRefs`.

---

### F62.3 — `ValueList` silently truncates arrays without a "N more…" indicator

- **Severity:** LOW
- **Location:** `packages/scout-components/src/scanner-result-detail/Value.tsx:113-156`
- **Category:** event-display / consistency

**Description:**
`ValueTable` (object renderer) shows a "{n} more…" row when `maxTableSize` is exceeded (lines 212-226). The sibling `ValueList` (array renderer) slices to `maxListSize` (line 121) but renders no overflow indicator, so long arrays appear shorter than they are.

**Evidence:**
```tsx
const itemsToDisplay = value.slice(0, maxListSize);
// ... renders itemsToDisplay only; no `notShown` row
```

**Why it matters:**
Affects both scout (`ScannerResultsRow` uses `style="inline"` with default `maxTableSize=5`) and inspect (`SampleScansSidebar` → `ScannerResultDetailView` passes `maxTableSize=1000`, so unlikely to trigger there). User may believe an array result has fewer items than it does.

**Suggested fix:**
Mirror the `notShown > 0` block from `ValueTable` into `ValueList`.

---

### F62.4 — Unused `.resultContainer` rule in `ValidationResult.module.css`

- **Severity:** LOW
- **Location:** `packages/scout-components/src/scanner-result-detail/ValidationResult.module.css:21-26`
- **Category:** dead-code

**Description:**
The CSS module defines `.resultContainer` (a 2-column grid) but `ValidationResult.tsx` never references `styles.resultContainer`. Likely left over from a refactor that switched to `.validationTable` (flex column).

---

### F62.5 — Package named `scout-components` is a hard dependency of `apps/inspect`

- **Severity:** INFO
- **Location:** `apps/inspect/package.json:96`; consumers: `apps/inspect/src/app/samples/scans/SampleScansSidebar.tsx`, `apps/inspect/src/app/samples/scans/scanReferences.ts`, `apps/inspect/src/app/samples/transcript/TranscriptPanel.tsx`
- **Category:** code-smell

**Description:**
The review brief asked "Does inspect import from scout-components? (It shouldn't)". It does — `ScannerResultDetailView`, `inferValueType`, `ScanResultInput`, `metadataWithoutScannerKeys`, `isScannerScore`, `readScannerReferences` are all consumed by the inspect viewer's "Scans" sidebar. The dependency direction is fine (`scout-components` → `inspect-components` → `react`), but the *name* is misleading: this is a shared scan-result-rendering package, not scout-only. There is no reverse leak (scout does not import from `apps/inspect` internals).

**Suggested fix (optional):**
Either rename to something neutral (e.g. `@tsmono/scan-components`) or document in `ts-mono/CLAUDE.md` that `scout-components` is shared.

---

### F62.6 — Parallel metadata renderers: `Metadata` vs `MetaDataGrid`

- **Severity:** INFO
- **Location:** `packages/scout-components/src/scanner-result-detail/Metadata.tsx` vs `packages/inspect-components/src/content/MetaDataGrid.tsx`
- **Category:** consistency

**Description:**
Both render `Record<string, unknown>` as labelled key/value rows with markdown strings and recursive object handling. They are independent implementations (scout uses `LabeledValue`+`RecordTree`; inspect uses a CSS grid + `RenderedContent`) rather than a fork, so there is no drift to reconcile — but it does mean scan metadata in the inspect viewer's Scans sidebar renders with different visual treatment than metadata elsewhere in inspect (e.g. `ScoreEventView` uses `MetaDataGrid`). Noted for awareness only.

---

## Files reviewed

- [x] `packages/scout-components/src/index.ts` — barrel, fine
- [x] `packages/scout-components/src/scanner-result-detail/ScannerResultDetailView.tsx` — sole `VscodeCollapsible` user in monorepo; clean
- [x] `packages/scout-components/src/scanner-result-detail/Explanation.tsx` — thin wrapper, fine
- [x] `packages/scout-components/src/scanner-result-detail/Metadata.tsx` + `.test.tsx` — see F62.6
- [x] `packages/scout-components/src/scanner-result-detail/Value.tsx` + `.module.css` — see F62.3
- [x] `packages/scout-components/src/scanner-result-detail/ValidationResult.tsx` + `.module.css` — see F62.4; `text-size-smallestest` is a real class in `theme/src/base.css:146`, not a typo
- [x] `packages/scout-components/src/scanner-result-detail/types.ts` — type guards + `inferValueType`, fine
- [x] `packages/scout-components/src/scanner-result-detail/index.ts` — barrel, fine
- [x] `packages/scout-components/src/sentinels/scannerReferences.ts` + `.test.ts` — see F62.2
- [x] `packages/scout-components/src/sentinels/index.ts` — barrel, fine
- [x] `packages/scout-components/src/types/asciinema-player.d.ts` — see F62.1
- [x] `packages/scout-components/package.json` — depends on `inspect-components`, `react`, `util` (correct direction)

## Open questions / needs verification

- F62.5: confirm with maintainers whether the `apps/inspect` → `scout-components` dependency is intentional architecture or an expedient that should be inverted (move `sentinels/` + `ScannerResultDetailView` into `inspect-components`).
- `apps/inspect/src/app/samples/scans/scanReferences.ts:32-64` (`findEventForMessage`) is a hand-rolled simplified mirror of `inspect-components/transcript/resolveMessageToEvent.ts` operating on flat `Event[]` instead of `TimelineSpan`. Out of scope for this package review, but worth tracking as a potential drift point between the two message→event resolvers.
