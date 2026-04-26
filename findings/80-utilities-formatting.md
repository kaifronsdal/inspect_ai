# Utilities & Formatting Code

**Reviewer scope:** `packages/util/src/`, `packages/inspect-common/src/`, `apps/inspect/src/utils/`, plus utility-adjacent files in `inspect-components`
**Date:** 2026-04-22

---

## Summary

The utility layer is fragmented across three locations (`@tsmono/util`, `apps/inspect/src/utils/`, `inspect-common/utils/`) with **substantial duplication** — `formatTime`, `formatDateTime`, `formatDuration`, `directoryRelativeUrl`, `join`, `encodePathParts`, `isUri`, `prettyDirUri`, `escapeSelector`, `decodeHtmlEntities`, `useWhyDidYouUpdate`, and the entire ~200-line `json-worker.ts` exist in two places with **divergent behavior**. Several formatters mishandle edge cases (scientific notation, `slice(-0)`, NaN dates). One confirmed correctness bug (`parseLogFileName`) silently produces `Invalid Date` for every log file. A handful of exports are dead. Overall health: functional but in need of consolidation; the duplication is a latent-bug factory.

---

## Findings

### F80.1 — `parseLogFileName` always produces `Invalid Date` for timestamp

- **Severity:** HIGH
- **Location:** `apps/inspect/src/utils/evallog.ts:27`
- **Category:** correctness

**Description:**
The regex captures timestamps like `2024-01-01T12-34-56+00-00` (dashes in time and TZ offset, per inspect's filesystem-safe naming). This string is passed directly to `Date.parse()`, which returns `NaN` because it is not valid ISO 8601. `new Date(NaN)` is an `Invalid Date`.

**Evidence:**
```ts
const kLogFilePattern =
  /^(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}[-+]\d{2}-\d{2})_(.+)_(...)\.(eval|json)$/;
...
return {
  timestamp: new Date(Date.parse(match[1])),  // Date.parse("2024-01-01T12-34-56+00-00") → NaN
```
Verified in Node: `Date.parse("2024-01-01T12-34-56+00-00")` → `NaN`.

**Why it matters / impact:**
The only caller (`app/log-list/grid/columns/hooks.tsx:125`) currently uses only `.name`, so the bug is latent. But any future use of `.timestamp` will silently get `Invalid Date`, and the type signature promises `Date | undefined` — not `Invalid Date`.

**Suggested fix:**
Convert dashes to colons in the time/offset portion before parsing: `match[1].replace(/T(\d{2})-(\d{2})-(\d{2})([+-])(\d{2})-(\d{2})/, 'T$1:$2:$3$4$5:$6')`.

---

### F80.2 — `centerTruncate` returns full string when `maxLength` is 4

- **Severity:** MEDIUM
- **Location:** `packages/util/src/format.ts:205-210`
- **Category:** correctness

**Description:**
When `availableLength` is odd (e.g. `maxLength=4` → `availableLength=1`), `endLength = Math.floor(1/2) = 0`, and `str.slice(-0)` is equivalent to `str.slice(0)` — the **entire string**.

**Evidence:**
```ts
const endLength = Math.floor(availableLength / 2);
const end = str.slice(-endLength);   // slice(-0) === entire string
```
Verified: `centerTruncate("abcdefghij", 4)` → `"a … abcdefghij"` (14 chars, not 4).

**Why it matters / impact:**
Caller is `apps/scout/src/app/components/DataframeView.tsx:84` with a configurable `options.maxStrLen`. If a column is configured with `maxStrLen ≤ 4`, the cell renders the full untruncated value.

**Suggested fix:**
`const end = endLength > 0 ? str.slice(-endLength) : "";`

---

### F80.3 — `filename()` returns full path for extensionless files in subdirectories

- **Severity:** MEDIUM
- **Location:** `packages/util/src/path.ts:22-27`
- **Category:** correctness

**Description:**
When `basename` has no extension and no match, the function falls through to `return path` — the **full path with directories** — instead of `return basename`.

**Evidence:**
```ts
const match = basename.match(/(.*)\.\S+$/);
if (match) {
  return match[1] ?? "";
} else {
  return path;   // ← should be `basename`
}
```
Verified: `filename("/a/b/README")` → `"/a/b/README"` (expected `"README"`).

**Why it matters / impact:**
Used in `evallog.ts:19` as fallback when log filename doesn't match the standard pattern. A non-conforming log path like `/logs/subdir/mylog` would display `/logs/subdir/mylog` instead of `mylog` in the log list.

---

### F80.4 — `formatTime` / `formatDateTime` / `formatDuration` duplicated with different behavior

- **Severity:** MEDIUM
- **Location:** `packages/util/src/format.ts:33-167` vs `apps/inspect/src/utils/format.ts:6-39`
- **Category:** consistency

**Description:**
Both packages export identically-named functions with different output:

| Function | `@tsmono/util` | `apps/inspect/src/utils/format` |
|---|---|---|
| `formatTime(45)` | `"45 sec"` (rounded int) | `"45.0 sec"` (1 decimal) |
| `formatTime(120)` | `"2 min"` (drops 0-sec) | `"2 min 0 sec"` (keeps 0-sec) |
| `formatDateTime` | `Intl.DateTimeFormat(undefined, {...})` (locale-dependent, 12-hour) | `toLocaleString("sv-SE")` (ISO-like, 24-hour) |
| `formatDuration` | delegates to util `formatTime` | delegates to local `formatTime` |

`apps/inspect` consistently imports the **local** copy (8 call sites), while `inspect-components` imports the **`@tsmono/util`** copy (e.g. `transcript/event/utils.ts:1`). So a duration shown in the sample header (`"2 min 0 sec"`) differs from the same duration in the transcript panel (`"2 min"`), and timestamps use different locales side-by-side in the same UI.

**Why it matters / impact:**
Visible inconsistency between app chrome and embedded transcript components. Maintenance burden: bug fixes to one copy don't reach the other.

**Suggested fix:**
Delete `apps/inspect/src/utils/format.ts`; standardize on `@tsmono/util`. If the sv-SE format is preferred, change it there.

---

### F80.5 — `formatDateTimeForInput` / `formatDateForInput` shift values to UTC

- **Severity:** MEDIUM
- **Location:** `packages/util/src/date.ts:25-27`, `:49-50`
- **Category:** correctness

**Description:**
Both functions call `date.toISOString()` and slice the result. `toISOString()` is always UTC, but HTML `<input type="datetime-local">` expects **local-time** strings (no TZ). A user in UTC-8 who picks `2024-01-01 10:00` local will see it round-tripped as `2024-01-01 18:00` (or the previous day for `type="date"`).

**Evidence:**
```ts
// Format as YYYY-MM-DDTHH:mm for datetime-local input
const isoStr = date.toISOString();
return isoStr.substring(0, 16); // YYYY-MM-DDTHH:mm  ← but in UTC, not local
```

**Why it matters / impact:**
Per `design/temporal-data-handling.md`, the project explicitly cares about TZ correctness. Any filter UI using these helpers (scout's column filters import from `date.ts`) will display shifted dates for non-UTC users.

**Suggested fix:**
Build the string from `getFullYear()/getMonth()/getDate()/getHours()/getMinutes()` (local accessors), or offset by `getTimezoneOffset()` before calling `toISOString()`.

---

### F80.6 — `resolveAttachments` drops `onFailedResolve` in recursive calls

- **Severity:** MEDIUM
- **Location:** `apps/inspect/src/utils/attachments.ts:18`, `:37`
- **Category:** correctness / fallback-hiding-errors

**Description:**
The top-level call receives `onFailedResolve`, but recursive descents into arrays and objects call `resolveAttachments(v, attachments)` **without** the callback. Since attachment refs always live inside event/message objects (never at the top level), the callback effectively never fires.

**Evidence:**
```ts
const resolvedArray = value.map((v) => {
  const resolved = resolveAttachments(v, attachments);  // ← onFailedResolve dropped
  ...
for (const [key, val] of Object.entries(value)) {
  const resolved = resolveAttachments(val, attachments); // ← dropped again
```

**Why it matters / impact:**
No current caller passes `onFailedResolve`, so this is latent. But the parameter exists precisely to surface unresolved attachments — and it can't.

---

### F80.7 — `isJson` logs `console.error` for every brace-wrapped non-JSON string

- **Severity:** MEDIUM
- **Location:** `packages/util/src/json.ts:7-9`
- **Category:** code-smell / fallback-hiding-errors

**Description:**
A predicate function has a side effect: any string that starts with `{` and ends with `}` but isn't valid JSON triggers `console.error`. This is called on chat-message text content (`MessageContent.tsx:153`), tool output (`ToolOutput.tsx:82`), and rendered content (`RenderedContent.tsx:130`). LLM output like `"{this is not json}"` or LaTeX `"{x \\over y}"` will spam the console.

**Evidence:**
```ts
try {
  JSON.parse(text);
  return true;
} catch (e) {
  console.error("Error parsing JSON:", e);   // ← side effect in predicate
  return false;
}
```

**Why it matters / impact:**
Noisy devtools console for users viewing transcripts with brace-heavy text; misleadingly labelled as an "error".

**Suggested fix:**
Drop the `console.error`. Match the silent style of `parsedJson`/`asJsonObjArray` in the same file.

---

### F80.8 — `directoryRelativeUrl` in `@tsmono/util` encodes `/` in fallback path; app copy does not

- **Severity:** MEDIUM
- **Location:** `packages/util/src/uri.ts:3`, `:31` vs `apps/inspect/src/utils/uri.ts:3`, `:30-37`
- **Category:** consistency / correctness

**Description:**
When `file` is not under `dir`, the `@tsmono/util` version returns `encodeURIComponent(file)` — turning every `/` into `%2F`. The `apps/inspect` copy returns `uriEncodePathSegments(file)` — encoding each segment but preserving `/`. Additionally, `@tsmono/util`'s `join()` lacks the "already absolute" guard and the `./` stripping that the app copy has.

**Evidence:**
```ts
// packages/util/src/uri.ts:31
return encodeURIComponent(file);          // "a/b" → "a%2Fb"
// apps/inspect/src/utils/uri.ts:30
return uriEncodePathSegments(normalizedFile);  // "a/b" → "a/b"
```

**Why it matters / impact:**
`apps/inspect` exclusively imports its local copy (verified via rg), so the `@tsmono/util` versions of `directoryRelativeUrl`/`encodePathParts`/`isUri`/`prettyDirUri` are effectively a stale fork used only by `apps/scout`. Any scout path that hits the fallback gets a single percent-encoded blob instead of a path.

---

### F80.9 — `json-worker.ts` duplicated (~200 LOC + ~160 KB base64 blob) with diverged API

- **Severity:** MEDIUM
- **Location:** `packages/util/src/json-worker.ts` vs `apps/inspect/src/utils/json-worker.ts`
- **Category:** dead-code / consistency

**Description:**
The two files are near-identical except:
- App copy adds `parseBytes()` / `asyncJsonParseBytes()` (used by `client/remote/remoteLogFile.ts`).
- App copy's `jsonParse` is sync with JSON5 fallback; util copy's `jsonParse` is `Promise.resolve(JSON.parse(text))` with no JSON5 fallback (and is unused).
- Both embed the same giant base64-encoded JSON5 library string (`kJson5ScriptBase64`), so the bundle ships **two copies** of JSON5.

**Why it matters / impact:**
~160 KB of duplicated base64 in the bundle; bug fixes won't propagate.

**Suggested fix:**
Upstream `parseBytes`/`asyncJsonParseBytes` into `@tsmono/util` and delete the app copy.

---

### F80.10 — `formatPrettyDecimal` / `formatDecimalNoTrailingZeroes` break on scientific notation

- **Severity:** MEDIUM
- **Location:** `packages/util/src/format.ts:64-98`
- **Category:** correctness

**Description:**
Both functions use `num.toString().split(".")` to count decimal places. For `|n| < 1e-6` or `|n| ≥ 1e21`, `Number.prototype.toString()` returns exponential notation (`"1.234e-7"`), so the "decimal part" becomes `"234e-7"` (length 6). Result: tiny scores render as `"0.000"`.

**Evidence:**
```
formatPrettyDecimal(0.0000001234) → "0.000"
formatDecimalNoTrailingZeroes(1.234e-7) → "0.000000"
formatPrettyDecimal(1e21) → "1e+21"   (treated as 0 decimals → toFixed(1) which JS renders as "1e+21")
```

**Why it matters / impact:**
`formatDecimalNoTrailingZeroes` is used by `NumericScoreDescriptor.tsx:31` to render numeric scores. A score of `1e-7` (e.g. a probability or loss) displays as `0.000000` — indistinguishable from zero. `formatPrettyDecimal` is used widely for metrics.

Secondary: `formatDecimalNoTrailingZeroes` is conceptually a no-op for normal numbers — `Number.prototype.toString()` never produces trailing zeroes, and the regex `/\.?0+$/` can never match a leading `.` since it's applied *after* the split. The function could be replaced with `String(num)`.

---

### F80.11 — `sampleLimitMessage` missing `working` and `custom` cases; also dead

- **Severity:** LOW
- **Location:** `packages/inspect-common/src/utils/sampleLimit.ts:6-21`
- **Category:** event-display / dead-code

**Description:**
`SampleLimitEvent["type"]` (generated.ts:2282) is `"message" | "time" | "working" | "token" | "cost" | "operator" | "custom"`. The switch handles 5 of 7; `working` and `custom` fall through to "An unknown limit terminated this sample." Compare with `inspect-components/src/transcript/event/utils.ts:6-14` which handles all 7 — so there are **two** limit-label tables that have drifted.

Also: `sampleLimitMessage` is exported from `inspect-common/utils/index.ts` but has **zero importers** anywhere in the monorepo.

---

### F80.12 — `formatDataset` produces leading/double spaces

- **Severity:** LOW
- **Location:** `packages/util/src/format.ts:20-28`
- **Category:** styling

**Description:**
`terms.join(" ")` joins empty-string placeholders, yielding e.g. `"foo —  10  samples"` (double space after em-dash, double before "samples") or `" 5 x 2  samples"` (leading space). HTML collapses these, but the string is also used in tooltips/titles where it's visible verbatim.

**Evidence:**
Verified: `formatDataset(10, 1, "foo")` → `"foo —  10  samples"`; `formatDataset(1, 1, null)` → `" 1  sample"`.

**Suggested fix:**
`terms.filter(Boolean).join(" ")` and drop trailing spaces inside individual terms.

---

### F80.13 — `debounce` accepts `trailing` option but ignores it

- **Severity:** LOW
- **Location:** `packages/util/src/sync.ts:70-120`
- **Category:** correctness

**Description:**
The signature is `options: { leading?: boolean; trailing?: boolean }`, but `trailing` is never read. A caller passing `{ trailing: false }` still gets trailing invocation. Also, `{ leading: true }` suppresses trailing invocation entirely (no `trailing: true` override possible) — this is the inverse of lodash semantics.

**Why it matters / impact:**
No current caller passes `trailing`, so latent. But `packages/react/src/hooks/useDebouncedCallback.ts` already imports `lodash-es` `debounce` instead — suggesting someone hit this and worked around it. Two debounce implementations in one codebase.

---

### F80.14 — `formatDateTime` has wrong JSDoc (copy-paste from `formatDecimalNoTrailingZeroes`)

- **Severity:** LOW
- **Location:** `packages/util/src/format.ts:141-144`
- **Category:** code-smell

**Evidence:**
```ts
/**
 * Formats a number to a string without trailing zeroes after the decimal point.
 */
export function formatDateTime(date: Date): string {
```

---

### F80.15 — `truncateMarkdown` treats `match.index === 0` as "no match"

- **Severity:** LOW
- **Location:** `apps/inspect/src/utils/markdown.ts:220`
- **Category:** correctness

**Description:**
`if (match && match.index)` is falsy when `index === 0`. If incomplete markdown syntax starts at position 0 (e.g. truncating `` `unterminated... ``), the guard fails and the broken substring is returned instead of `""`.

**Evidence:**
```ts
const match = substr.match(pattern);
if (match && match.index) {   // ← 0 is falsy
  return substr.slice(0, match.index);
}
```

---

### F80.16 — `isBase64` matches empty string and arbitrary 4-char words

- **Severity:** LOW
- **Location:** `packages/util/src/base64.ts:1-7`
- **Category:** correctness

**Description:**
`isBase64("")` → `true`; `isBase64("test")` → `true`; `isBase64("12345678")` → `true`. The companion `maybeBase64` mitigates with a length floor (default 256), but `isBase64` is exported standalone.

---

### F80.17 — `apps/inspect/src/utils/html.ts` is a dead, byte-identical copy of `packages/util/src/html.ts`

- **Severity:** LOW
- **Location:** `apps/inspect/src/utils/html.ts`
- **Category:** dead-code

**Description:**
File is identical to `packages/util/src/html.ts` and has zero importers (verified via rg). Additionally, `escapeSelector` is unused in **both** locations — only `decodeHtmlEntities` (from `@tsmono/util`) is called, by `MessageCitations.tsx`.

---

### F80.18 — Dead exports

- **Severity:** INFO
- **Location:** multiple
- **Category:** dead-code

**Description:**
The following exported symbols have zero importers anywhere in `ts-mono` (excluding their own definition file, barrel `index.ts`, and tests):

| Symbol | File |
|---|---|
| `firstUserMessage`, `lastAssistantMessage` | `packages/util/src/chatMessage.ts` (entire file dead) |
| `toAbsolutePath` | `packages/util/src/path.ts` |
| `isValidDate` | `packages/util/src/date.ts` |
| `escapeSelector` | `packages/util/src/html.ts` AND `apps/inspect/src/utils/html.ts` |
| `sampleLimitMessage` | `packages/inspect-common/src/utils/sampleLimit.ts` |
| `printCircularReferences`, `findDifferences` | `apps/inspect/src/utils/debugging.ts` (entire file dead) |
| `useWhyDidYouUpdate` (app copy) | `apps/inspect/src/utils/react.ts` (entire file dead; duplicates `packages/react/src/hooks/useWhyDidYouUpdate.ts`) |
| `simpleMarkdownTruncate` | `apps/inspect/src/utils/markdown.ts` (only called internally + by tests) |

`debugging.ts` and `react.ts` are debug helpers and may be intentionally kept for ad-hoc use.

---

### F80.19 — `toRelativePath` decodes `file://` URI for `absolutePath` but not for `basePath`

- **Severity:** LOW
- **Location:** `packages/util/src/path.ts:86-93`
- **Category:** consistency

**Description:**
`absolutePath` gets `decodeURIComponent` after stripping `file://`; `basePath` only strips `file://` without decoding. If `basePath` is `file:///Users/foo%20bar/` and `absolutePath` is `file:///Users/foo%20bar/x`, the decoded path won't `.startsWith()` the un-decoded base, and the function returns the full path instead of the relative one.

---

### F80.20 — `inputString` returns `[input]` for string but maps other content types to `""`

- **Severity:** LOW
- **Location:** `packages/inspect-common/src/utils/inputString.ts:18-25`
- **Category:** event-display

**Description:**
For `ChatMessage[]` input with `Content[]` content, only `type === "text"` is extracted; `reasoning`, `image`, `audio`, `video`, `document`, `data`, `tool_use` all become `""` and are then `join("\n")`'d — producing strings like `"\n\nhello\n\n"` with empty lines for each non-text block. Callers (`samplesDescriptor.tsx`, `columns.tsx`, `filters.ts`) join with `" "` so this is mostly invisible, but `SampleSummaryView.tsx` may render the raw newlines.

---

### F80.21 — `printArray` separator-budget off-by-one for first pair

- **Severity:** INFO
- **Location:** `packages/util/src/array.ts:6-10`
- **Category:** correctness

**Description:**
`remainingSize` pre-subtracts one `separator.length` before the loop, but the loop's `bothSize` already adds `separator.length` per pair. The first head/tail pair therefore double-counts a separator (2 chars too conservative). Cosmetic only — output is shorter than it could be, never longer.

---

### F80.22 — `formatDateTime` requires `@ts-expect-error` due to wrong option type

- **Severity:** INFO
- **Location:** `packages/util/src/format.ts:156-157`
- **Category:** code-smell

**Description:**
The `options` literal is widened to `{ year: string; ... }` instead of `Intl.DateTimeFormatOptions`. Adding `as const` or an explicit type annotation removes the need for `@ts-expect-error`.

---

### F80.23 — Two `resolveAttachments` implementations across apps

- **Severity:** INFO
- **Location:** `apps/inspect/src/utils/attachments.ts` vs `apps/scout/src/api/attachmentsHelpers.ts`
- **Category:** consistency

**Description:**
Scout has its own `resolveAttachments` with a simpler recursive walk (no identity-preservation, no `onFailedResolve`, no Date/RegExp guard). Scout's version has tests; inspect's does not. Candidate for `@tsmono/util`.

---

## Files reviewed

### `packages/util/src/`
- [x] `ansi.ts` — single regex predicate, looks correct
- [x] `api-error.ts` — trivial Error subclass, fine
- [x] `array.ts` — `printArray`; minor budget off-by-one (F80.21)
- [x] `arrow.ts` — Arrow/Arquero decoding; out of formatting scope, no issues spotted
- [x] `asyncData.ts` — `compose`/`data`/`loading`; fine
- [x] `base64.ts` — F80.16
- [x] `base64url.ts` — RFC 4648 §5, correct
- [x] `brand.ts` — nominal typing helper, fine
- [x] `browser.ts` — `clearDocumentSelection`, fine
- [x] `chatMessage.ts` — entire file dead (F80.18)
- [x] `date.ts` — F80.5; `isValidDate` dead
- [x] `format.ts` — F80.2, F80.4, F80.10, F80.12, F80.14, F80.22
- [x] `git.ts` — `ghCommitUrl`, fine
- [x] `html.ts` — `escapeSelector` dead (F80.17/18)
- [x] `http.ts` — `fetchRange`, no error-status check but acceptable
- [x] `index.ts` — barrel
- [x] `json-value.ts` — type-only, fine
- [x] `json-worker.ts` — F80.9 (duplicate); large base64 blob skimmed
- [x] `json.ts` — F80.7; `parsedJson`/`asJsonObjArray` only detect objects/arrays respectively (intentional?)
- [x] `logger.ts` — fine
- [x] `mime.ts` — trivial
- [x] `numeric.ts` — `compareWithNan`, fine
- [x] `object.ts` — `printObject`; same minor budget pattern as `printArray`
- [x] `path.ts` — F80.3, F80.19; `toAbsolutePath` dead
- [x] `python.ts` — `parsePackageName`, fine
- [x] `queue.ts` — `AsyncQueue`, fine
- [x] `retry.ts` — trivial
- [x] `sync.ts` — F80.13
- [x] `type.ts` — `isNumeric` uses double-`any` cast; works but smelly
- [x] `uri.ts` — F80.8 (diverged from app copy)
- [x] `vscode.ts` — fine

### `packages/inspect-common/src/`
- [x] `types/index.ts` — re-export plumbing, fine
- [x] `types/generated.ts` — generated, skimmed
- [x] `types/openapi-ts-behavior.test.ts` — fine
- [x] `utils/expandEvents.ts` — pure, well-tested, fine
- [x] `utils/inputString.ts` — F80.20
- [x] `utils/sampleLimit.ts` — F80.11

### `apps/inspect/src/utils/`
- [x] `attachments.ts` — F80.6, F80.23
- [x] `clear-events-preprocessor.ts` — byte-level scanner; `findEventsArrayStart` matches *any* `"events"` key (could match nested), but doc comment says 100MB while constant is 350MB
- [x] `debugging.ts` — dead (F80.18)
- [x] `dom.ts` — fine
- [x] `evallog.ts` — F80.1
- [x] `format.ts` — F80.4 (duplicate of util)
- [x] `html.ts` — dead duplicate (F80.17)
- [x] `json-worker.ts` — F80.9 (duplicate of util)
- [x] `markdown.ts` — F80.15; `simpleMarkdownTruncate` only used internally
- [x] `polling.ts` — `throw` inside async `setTimeout` callback (line 75) becomes unhandled rejection — never reaches caller
- [x] `react.ts` — dead duplicate (F80.18)
- [x] `uri.ts` — F80.8 (diverged from util)
- [x] `workQueue.ts` — `newItemsCount` computed but unused; otherwise fine

### `packages/inspect-components/src/` (top-level utils)
- [x] `transcript/event/utils.ts` — `formatTitle` skips tokens/time when value is `0` (`if (total_tokens)` truthy check)

## Open questions / needs verification

- `@tsmono/util` versions of `directoryRelativeUrl`/`join`/`encodePathParts`/`isUri`/`prettyDirUri` are used only by `apps/scout`. Is the intent for `apps/inspect/src/utils/uri.ts` to be the canonical version, or was it forked accidentally?
- `clear-events-preprocessor.ts` doc comment says "exceeds 100MB" but `MAX_EVENTS_SIZE_BYTES = 350 * 1024 * 1024`. Which is intended?
- Is `chatMessage.ts` in `@tsmono/util` kept for an external consumer (VS Code extension submodule)? The `ChatMessage` type alias there shadows the real one from `inspect-common`.
