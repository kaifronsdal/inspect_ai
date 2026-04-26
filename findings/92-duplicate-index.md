# Duplicate Findings Index

This index maps every finding that was independently reported by two or more review agents to a single canonical ID. **Do not edit the original findings files** — they remain the per-agent record. Use this table when triaging to avoid double-counting.

A "strict duplicate" means the same line(s) of code and the same defect. An "overlap/extends" means substantially the same issue reported at different granularity or scope; these are listed separately and **not** subtracted from unique counts.

---

## Strict duplicates

| Canonical ID | Duplicate IDs | Title | Severity (canonical) |
|---|---|---|---|
| F01.1 | F04.1 | `ModelEventView` `slice(-1)` drops preceding user/system messages | HIGH |
| F01.2 | F04.3 | `ToolChoiceView` renders literal `` `$ `` around function name | HIGH |
| F01.4 | F04.2 | Tools tab hidden when `tools.length === 1` | MEDIUM¹ |
| F01.7 | F11.11 | `ApprovalEventView` drops `approver`/`modified`/`message`/`call` | MEDIUM |
| F01.10 | F11.6 | `ToolEventView` `useMemo` depends on `event.events` not `childNodes` | MEDIUM |
| F01.13 | F04.17, F04.14 | `formatTitle` 3rd param semantics / dead `role` param | LOW |
| F01.14 | F61.21 | `loggingIcons` map missing `trace` / `sandbox` levels | LOW |
| F01.19 | F04.12, F04.19 | `EventTimingPanel` dead `bordered` field + wrong docstring | LOW |
| F03.1 | F05.1, F50.2 | `setPath()` only descends when key is missing → wrong state diffs | HIGH |
| F03.7 | F02.10 | `noScorerChildren` visitor never resets state | LOW |
| F03.8 | F61.8 | `TimelineSelector` chevron missing `bi` base class | LOW |
| F03.15 | F02.6 | `flatTree` writes `parentNode.children = visitorResult` per-child | LOW |
| F03.16 | F04.16 | Timeline token aggregation vs `usage.total_tokens` | INFO |
| F04.10 | F61.5 | `text-sixe-small` className typo in `TokenTable` | LOW |
| F20.7 | F21.3 | `ScorerDescriptor.scores()/explanation()/metadata()` dead code | LOW |
| F20.8 | F21.1 | `ScoreDescriptor.compare()` never called | MEDIUM² |
| F20.13 | F21.12 | `ListScoreDescriptor` unreachable guard + "non-lisß" typo | LOW |
| F20.16 | F52.14, F50.21 | `kSampleMetdataTabId` / `kLogsRoutUrlPattern` typos | INFO |
| F20.21 | F80.20 | `inputString` drops non-text content silently | INFO |
| F20.22 | F21.23, F52.16 | `BooleanScoreDescriptor` uses literal `"boolean"` | INFO |
| F21.16 | F50.4 | `useFilteredSamples` dispatches store actions inside `useMemo` | MEDIUM |
| F30.2 | F61.11 | Status icons differ between log-list grid and detail header | MEDIUM |
| F30.5 | F31.19 | `createFolderFirstComparator` ignores sort direction | MEDIUM |
| F30.7 | F80.1 | `parseLogFileName` always produces `Invalid Date` | HIGH³ |
| F30.15 | F51.18 | Duplicate `toLogPreview` implementations with drift | LOW |
| F30.17 | F31.28 | `intoTabConfig` typo (LogView) | LOW |
| F30.18 | F80.4 | Duplicate `formatTime`/`formatDateTime`/`formatDuration` with drift | MEDIUM |
| F40.3 | F60.5 | `MarkdownRenderQueue.cancel()` cancels the wrong queued task | MEDIUM |
| F40.4 | F60.2 | `LightboxCarousel` keyup listener leak (capture-flag mismatch) | MEDIUM |
| F40.7 | F60.43 | `ANSIDisplay` re-parses output on every render (no memo) | MEDIUM |
| F40.8 | F60.4 | `LightboxCarousel.showNext` does not wrap; `showPrev` does | LOW |
| F40.9 | F60.32 | `ExpandablePanel` rem vs element-fontSize threshold mismatch | LOW |
| F40.10 | F61.6 | `MetaDataGrid` `var(` missing closing paren in inline style | MEDIUM |
| F40.13 | F80.7 | `isJson` logs `console.error` for brace-wrapped non-JSON | MEDIUM |
| F40.24 | F60.35 | `CopyButton` `setTimeout` not cleared on unmount | INFO |
| F40.27 | F60.42 | `usePrismHighlight` re-highlights on `contentLength` only | LOW |
| F50.8 | F51.5 | ReplicationService detail-queue index misalignment | MEDIUM |
| F51.2 | F52.8 | Hand-coded `Event` union missing `SpanBegin`/`SpanEnd`/`ScoreEdit` | MEDIUM |
| F51.11 | F52.5 | `.replace(" ", "+")` only replaces first space | LOW |
| F52.9 | F80.8 | `apps/inspect/utils/uri.ts` duplicates `@tsmono/util/uri.ts` with drift | MEDIUM |
| F80.11 | F81.8 | `sampleLimitMessage` dead + missing `working`/`custom` cases | LOW |

**Notes:**
¹ F04.2 rated this HIGH; verification (91) recommends MEDIUM. F01.4 already rated MEDIUM.
² F20.8 rated LOW (just "dead"); F21.1 rated MEDIUM (adds "wrong sort behaviour" impact). Canonical takes MEDIUM.
³ F30.7 rated LOW (latent — only `.name` used today); F80.1 rated HIGH. Canonical rated HIGH per the more detailed analysis, but note the bug is currently latent.

---

## Overlaps / extensions (not strict duplicates)

These share subject matter but add distinct analysis, scope, or impact. Kept as separate findings.

| Primary | Related | Relationship |
|---|---|---|
| F01.24 | F04.5, F04.6, F04.7, F04.15, F04.18 | F01.24 lists all unrendered `ModelEvent` fields; F04.x splits each into a separate MEDIUM/INFO finding with impact analysis |
| F01.25 | F11.7, F11.24 | F01.25 lists all unrendered `ToolEvent` fields; F11.7/F11.24 expand `truncated` and `failed` individually |
| F02.7 | F03.15 | Both about `flatTree` `.children` divergence; F02.7 covers visitor vs no-visitor path, F03.15 covers per-sibling overwrite |
| F10.2 | F11.8 | Both about `ChatMessage` filtering tool content to text/image; F10.2 adds `error` omission, F11.8 adds path-divergence analysis |
| F10.18 | F40.18 | Both `<img>` without `alt`; different files (chat vs RenderedContent) |
| F20.4 | F21.10, F90.3, F90.14 | Score-rendering divergence: F20.4 covers Scoring tab, F21.10 covers two grids, F90.3 adds transcript `ScoreValue`, F90.14 adds headline metric |
| F30.6 | F52.1 | Same double-`ref` bug pattern in two different components (`ViewerOptionsButton` vs `FlowButton`) |
| F30.18 / F80.4 | F90.1, F90.2 | F90.x extends with on-screen co-occurrence analysis (same screen, two formats) |
| F31.14 | F81.31 | F81.31 adds `evalStats`/`samples` to F31.14's dead-prop list |
| F40.16 | F81.1 | F81 inventory adds `LargeModal` to F40.16's dead-component list |
| F40.19 | F60.2 | F60.2 includes the "swallows all keyups" detail; F40.19 reports it standalone |
| F50.11 | F52.13 | Both list `app.logsSampleView` as dead; F52.13 adds 5 more dead types |
| F80.17, F80.18 | F81 §1 | F81 inventory consolidates and extends F80's dead-export list |

---

## De-duplication summary

| | Raw count | Strict-duplicate IDs removed | Unique count |
|---|---|---|---|
| **HIGH** | 20 | 4 (F04.1, F04.2⁴, F05.1, F50.2) | 16 → **14** after 91's downgrades⁵ |
| **MEDIUM** | 122 | 11 | ~113 |
| **LOW** | 268 | 22 | ~246 |
| **INFO** | 129 | 9 | ~120 |
| **Total** | 539 | 46 | **~493** |

⁴ F04.2 absorbed by F01.4 (MEDIUM).
⁵ Verification (91) downgrades F04.2 and F31.1 from HIGH to MEDIUM; F04.2 was already a duplicate. Net standing HIGH: 14 (15 if F80.1/F30.7 is kept at HIGH despite being latent).
