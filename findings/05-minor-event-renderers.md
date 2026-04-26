# Minor Event Renderers (State/Store/SampleInit/SampleLimit/Score/Info/Logger/Error/Input/Approval/Sandbox/Branch/Compaction)

**Reviewer scope:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/{state/**, *EventView.tsx, ScoreValue.tsx, event/utils.ts, eventText.ts, icons.ts}` cross-referenced against `inspect-common/src/types/generated.ts` and `src/inspect_ai/event/_*.py` / `src/inspect_ai/_util/json.py`.
**Date:** 2026-04-22

---

## Summary

Focused deep-dive on the "minor" event renderers and the JSON-patch diff machinery they depend on. **F03.1 (`setPath` brace bug) and F01.3 (`ScoreEditEventView` UNCHANGED sentinel) are independently confirmed.** Beyond what 01/03 already found, this review surfaces: a second `setPath`-adjacent bug where `initializeArrays`' last-segment branch is a no-op with wrong arguments; missing JSON-Pointer unescaping (`~0`/`~1`); a `ScoreEditEventView` falsy-value bug that hides edited scores of `0`/`false`; a structural bug where `ScoreEditEventView`'s Metadata tab is nested inside Summary so it never appears as a tab; a signature-match counting bug in `generatePreview` that prevents the "tools added" preview from firing when >1 tool is added; and a type-alias mismatch in `SampleLimitEventView`. Several findings overlap with `01-transcript-event-renderers.md` and are cross-referenced rather than duplicated.

---

## Findings

### F05.1 — `setPath` only descends into newly-created keys (independent confirmation of F03.1)

- **Severity:** HIGH
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/state/StateEventView.tsx:292-308`
- **Category:** correctness

**Description:**
The `current = current[key]` advance is inside the `if (key && !(key in current))` block. When the intermediate key already exists (which it always does for `add`/`replace` ops because `initializeArrays()` runs first and creates it), the loop body is skipped entirely and `current` never advances.

**Evidence:**
```ts
for (let i = 0; i < keys.length - 1; i++) {
  const key = keys[i];
  if (key && !(key in current)) {
    const nextKey = keys[i + 1];
    if (nextKey) {
      current[key] = isArrayIndex(nextKey) ? [] : {};
    }
    current = current[key] as Record<string, unknown>;   // ← inside the if
  }
}
const lastKey = keys[keys.length - 1];
if (lastKey) { current[lastKey] = value; }
```

**Why it matters / impact:**
For path `/messages/0/content`: `initializeArrays` creates `target.messages = []`; then `setPath` sees `"messages" in target`, skips, leaves `current === target`; at `i=1` it creates `target["0"] = {}`; final write goes to `target["0"]["content"]` instead of `target["messages"][0]["content"]`. The Diff tab then shows phantom top-level keys and misses the real nested change. Affects every multi-segment path where the first segment is an array container — i.e. almost all real `StateEvent` changes (`/messages/N`, `/tools/N`, `/output/choices/N/...`).

**Suggested fix:**
Move `current = current[key]` outside the `if`.

---

### F05.2 — `initializeArrays` last-key branch passes wrong arguments and discards result

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/state/StateEventView.tsx:336-340`
- **Category:** correctness / dead-code

**Description:**
After the main loop, the function tries to pad the parent array up to the final index. But it reads `current[lastKey]` (the *element* at that index, not the parent array), passes it to `initializeArray` as the array to pad, and then discards the return value.

**Evidence:**
```ts
const lastKey = keys[keys.length - 1];
if (lastKey && isArrayIndex(lastKey)) {
  const lastValue = current[lastKey] as string[] | undefined;
  initializeArray(lastValue, lastKey);          // result not assigned anywhere
}
```

**Why it matters / impact:**
For a single-segment array path like `/5` (or after F05.1 is fixed, the final segment of `/choices/5`), the parent array is never padded with `""` placeholders, so the diff shows 5 spurious "added empty string" entries on one side. Currently masked by F05.1 corrupting things earlier in the pipeline.

**Suggested fix:**
Should be padding `current` (the parent) up to `lastKey`, not `current[lastKey]`. e.g. when `current` is an array: `initializeArray(current as unknown as string[], lastKey)` — and the result must be assigned back (or `current` mutated in place, which `initializeArray` already does when passed an array).

---

### F05.3 — `parsePath` does not decode JSON-Pointer escapes `~0`/`~1`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/state/StateEventView.tsx:346-348`
- **Category:** correctness

**Description:**
RFC 6901 (which `jsonpatch` emits and `JsonChange.path` uses) escapes `/` as `~1` and `~` as `~0` inside path segments. `parsePath` is just `path.split("/").filter(Boolean)` — no unescaping. It also drops empty-string keys via `filter(Boolean)`.

**Why it matters / impact:**
A `Store` key containing `/` (e.g. `store().set("foo/bar", x)`) is encoded as `/foo~1bar` by Python's `jsonpatch`; the viewer would set `after["foo~1bar"]` instead of `after["foo/bar"]`. The Diff tab would then show an unexpected `foo~1bar` key. Low likelihood but a correctness gap vs. the spec the backend follows.

**Suggested fix:**
After splitting: `seg.replace(/~1/g, "/").replace(/~0/g, "~")` (order matters).

---

### F05.4 — `generatePreview` exact-count match prevents preview when multiple ops match one signature

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/state/StateEventView.tsx:119-169` and `state/StateEventRenderers.tsx:64-74`
- **Category:** event-display

**Description:**
`requiredMatchCount` is the number of signature *patterns*; `matchingOps` is the number of *changes* that matched any pattern. The preview fires only on `matchingOps === requiredMatchCount`. The `add_tools` change-type has one pattern (`/tools/(\d+)`); a state event that adds two tools produces `matchingOps = 2`, `requiredMatchCount = 1`, so the equality fails and no rich preview is shown.

**Evidence:**
```ts
const requiredMatchCount =
  changeType.signature.remove.length +
  changeType.signature.replace.length +
  changeType.signature.add.length;
let matchingOps = 0;
for (const change of changes) { ... matchingOps++ ... }
if (matchingOps === requiredMatchCount) { ... }
```

**Why it matters / impact:**
`use_tools()` solver typically adds multiple tools in one state event. The friendly "Tools" preview never fires for that case; users get the raw JSON diff instead. The `messages` change-type avoids this by using `match:` instead of `signature:`.

**Suggested fix:**
Either `matchingOps >= requiredMatchCount`, or track per-pattern "did at least one change match" and require all patterns satisfied.

---

### F05.5 — `ScoreEditEventView` hides edited value when it is `0`, `false`, or `""`

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ScoreEditEventView.tsx:50-58`
- **Category:** correctness / fallback-hiding-errors

**Description:**
`{event.edit.value ? <Fragment>...<ScoreValue score={event.edit.value}/>...</Fragment> : ""}`. `Score.value` is `string | number | boolean | ...` — `0`, `false`, and `""` are all valid edited score values that the truthy check silently drops. (This is the *opposite* failure mode from F01.3: F01.3 is "UNCHANGED is shown when it shouldn't be"; this is "real falsy values are hidden when they should be shown".)

**Why it matters / impact:**
Editing a score from `1` → `0` (the most common manual correction) renders no "Value" row at all. The user cannot see what the score was changed to.

**Suggested fix:**
`event.edit.value !== kUnchangedSentinel ? ...` (covers both this and F01.3).

---

### F05.6 — `ScoreEditEventView` Metadata `data-name` is nested inside Summary → never becomes a tab

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ScoreEditEventView.tsx:39,118-127`
- **Category:** event-display / consistency

**Description:**
`EventPanel` discovers tabs by reading `data-name` on its **direct** children (`EventPanel.tsx:92-98,201-212`). In `ScoreEditEventView` the `<div data-name="Metadata">` is a child of `<div data-name="Summary">`, not of `EventPanel`. Compare `ScoreEventView.tsx:67-76` where Metadata is a sibling and correctly produces a second tab.

**Why it matters / impact:**
Edited metadata renders inline at the bottom of the Summary tab with a dead `data-name` attribute, instead of as its own "Metadata" tab. Inconsistent with `ScoreEventView`.

---

### F05.7 — `SampleLimitEventView` types its switch against `EvalSampleLimit["type"]` instead of `SampleLimitEvent["type"]`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/SampleLimitEventView.tsx:13,23-59`
- **Category:** code-smell / correctness

**Description:**
`EvalSampleLimitType = EvalSampleLimit["type"]` includes `"context"` (`generated.ts:1303`); `SampleLimitEvent["type"]` does not (`generated.ts:2282`). `resolve_title`/`resolve_icon` are typed against the wrong enum, have no `default` arm, and silently return `undefined` for `"context"`. TypeScript does not flag the non-exhaustive switch.

**Why it matters / impact:**
Today no runtime path produces `"context"` on a `SampleLimitEvent`, so this is latent. But if the backend enum is extended (as `EvalSampleLimit` already was), the panel would render with `title={undefined}` and the wrong icon. Also defeats exhaustiveness checking.

**Suggested fix:**
`type EvalSampleLimitType = SampleLimitEvent["type"]` and add a `default` returning the raw `type` string.

---

### F05.8 — `StateDiffView.unescapeNewlines` recursive object/array branches are dead; string replace can corrupt literal `\n`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/state/StateDiffView.tsx:23-53`
- **Category:** dead-code / correctness

**Description:**
`unescapeNewlines` is only ever called with `html_result` (a string), so its array/object recursion branches (L41-52) are unreachable. The active branch does `obj.replace(/\\n/g, "\n")` on the formatted HTML — intended to turn jsondiffpatch's escaped newlines into real line breaks, but it also rewrites any literal two-character sequence `\n` that appears in the diffed *data* (e.g. a regex pattern `"\\n+"` or a Windows path `C:\node` stored in state).

**Why it matters / impact:**
State values containing a literal backslash-n are displayed with a spurious line break in the Diff tab. Low likelihood.

---

### F05.9 — `SandboxEventView` `ExecView` early-return checks `=== null` but field is also optional

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/SandboxEventView.tsx:57-58`
- **Category:** code-smell

**Description:**
`if (event.cmd === null) { return undefined; }` — but `cmd?: string | null` so `undefined` is also possible (`generated.ts:2320`). With `cmd === undefined` the guard is bypassed and an empty `<pre>` is rendered under a "Command" heading. Similarly `ReadFileView`/`WriteFileView` use `if (!event.file)` (correct) — inconsistent null-checking style across the three sub-views.

---

### F05.10 — `SandboxEventView` Options section is rendered inside a 2-column grid meant for cmd/input

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/SandboxEventView.tsx:69-80`
- **Category:** styling

**Description:**
The `Options` `<EventSection>` is a third child of `<div className={styles.twoColumn}>`. With a two-column grid it lands in row 2 / column 1, visually under the `cmd` cell rather than spanning the panel. (No `grid-column: 1 / -1` rule exists in `SandboxEventView.module.css`.)

**Why it matters / impact:**
When `options` is present (e.g. `{"timeout": 30}`), it renders squeezed into the left half with the right half blank. Cosmetic.

---

### F05.11 — `SampleInitEventView` never shows `sample.sandbox` or `sample.id`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/SampleInitEventView.tsx:30-108` (vs `generated.ts:2187-2207`)
- **Category:** event-display

**Description:**
`Sample.sandbox` (the `SandboxEnvironmentSpec` — type + config) and `Sample.id` are not rendered anywhere in the panel. Files, Setup, Choices, Target, Metadata are all surfaced; sandbox spec is the only structural field omitted.

**Why it matters / impact:**
When debugging sandbox configuration per-sample, the user has to open raw JSON. Minor — sandbox is usually task-level, not sample-level.

---

### F05.12 — `BranchEventView` discards `event.metadata`

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/BranchEventView.tsx:23-29` (vs `generated.ts:489-491`)
- **Category:** event-display

**Description:**
The view builds a `data` record from `from_span`/`from_message` only. `BranchEvent.metadata` (the generic per-event metadata bag) is not merged in, unlike `CompactionEventView.tsx:30` which does `{ ...data, ...event.metadata }`.

---

### F05.13 — `StateEventRenderers.Tool` declares `toolDesc` prop but never reads it

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/state/StateEventRenderers.tsx:335-353`
- **Category:** dead-code

**Description:**
`ToolProps.toolDesc?: string` is declared, never destructured, never passed by the only caller (`Tools` at L327-328). The tool description is therefore unavailable in the preview even though `ToolDefinition.description` is in scope.

---

### F05.14 — `isArrayIndex` does not recognise the JSON-Pointer `"-"` append index

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/state/StateEventView.tsx:353-355` (vs `src/inspect_ai/_util/json.py:222-224`)
- **Category:** correctness

**Description:**
RFC 6901 / JSON-Patch uses `"-"` to mean "append to end of array". The Python side handles it (`_apply_fast_list_op` checks `rel_path == "-"`). `isArrayIndex` is `^\d+$` only, so a path like `/messages/-` would create `{"messages": {"-": value}}` (object, not array). In practice `jsonpatch.make_patch` emits numeric indices, so this is latent; flagged for spec completeness alongside F05.3.

---

### F05.15 — Cross-reference: findings independently verified from prior reviews

- **Severity:** INFO
- **Location:** (see below)
- **Category:** correctness

**Description:**
The following findings from `01-transcript-event-renderers.md` and `03-transcript-outline-timeline.md` were independently re-derived during this review and are **confirmed**, not re-reported:

| Prior ID | Confirmed | Notes |
|---|---|---|
| F03.1 | yes | See F05.1 above for expanded impact analysis |
| F01.3 | yes | `value` and `explanation` both leak `"UNCHANGED"`; F05.5 adds the inverse falsy-value case |
| F01.5 | yes | 12 minor renderers omit `eventCallbacks`; verified none of `SampleInit/SampleLimit/Score/ScoreEdit/Info/Branch/Compaction/Input/Error/Approval/Sandbox/Logger` thread it |
| F01.6 | yes | `score_name` absent from title and body |
| F01.7 | yes | `approver`/`modified`/`call`/`message` all dropped |
| F01.8 | yes | `tokens_after === 0` hidden; `type` field never shown |
| F01.9 | yes | `"Compaction" + source` missing `": "`; `branch`/`state`/`store` fall to `default: ""` |
| F01.14 | yes | `trace`/`sandbox` levels missing from `TranscriptIcons.logging`; `notset` is extraneous |
| F01.15 | yes | `limit` value and timestamp subtitle both omitted |
| F01.18 | yes | `` key={`$choice-{choice}`} `` — literal string, duplicate keys |
| F01.26 | yes | `isStore` prop dead |
| F01.29 | yes | `[undefined]` interpolation; `ProvenanceData.timestamp` is required so currently unreachable |

---

## Files reviewed

- [x] `transcript/state/StateEventView.tsx` — F05.1, F05.2, F05.3, F05.4, F05.14; F01.26 confirmed
- [x] `transcript/state/StateDiffView.tsx` — F05.8
- [x] `transcript/state/StateEventRenderers.tsx` — F05.4, F05.13
- [x] `transcript/SampleInitEventView.tsx` — F05.11; F01.18 confirmed
- [x] `transcript/SampleLimitEventView.tsx` — F05.7; F01.15 confirmed
- [x] `transcript/ScoreEventView.tsx` — clean (target/answer/explanation/score/metadata/intermediate all surfaced)
- [x] `transcript/ScoreEditEventView.tsx` — F05.5, F05.6; F01.3/F01.6/F01.29 confirmed
- [x] `transcript/ScoreValue.tsx` — clean
- [x] `transcript/InfoEventView.tsx` — clean (string→markdown, else→JSONPanel; source in title)
- [x] `transcript/LoggerEventView.tsx` — F01.14/F01.30 confirmed; `created`/`module` also unshown (minor)
- [x] `transcript/ErrorEventView.tsx` — clean (`traceback_ansi` via ANSIDisplay; `error.message` is embedded in traceback)
- [x] `transcript/InputEventView.tsx` — clean (`input_ansi` via ANSIDisplay)
- [x] `transcript/ApprovalEventView.tsx` — F01.7 confirmed
- [x] `transcript/SandboxEventView.tsx` — F05.9, F05.10; `completed` timestamp not shown (minor)
- [x] `transcript/BranchEventView.tsx` — F05.12
- [x] `transcript/CompactionEventView.tsx` — F01.8/F01.9 confirmed
- [x] `transcript/event/utils.ts` — F01.9/F01.13 confirmed
- [x] `transcript/eventText.ts` — reference (search-text extraction; consistent with renderers)
- [x] `transcript/icons.ts` — F01.14 confirmed
- [x] `transcript/TranscriptVirtualList.tsx` — F01.5 confirmed (dispatcher)
- [x] `inspect-common/src/types/generated.ts` — reference
- [x] `src/inspect_ai/_util/json.py` — reference (JsonChange emitter; confirms `~` escaping and `"-"` index are possible)
- [x] `src/inspect_ai/event/_{sample_init,sample_limit,score,score_edit,approval,sandbox,compaction,state}.py` — reference

## Open questions / needs verification

- F05.1/F05.2: a unit test with `changes = [{op:"add", path:"/messages/0/content", value:"x"}]` would make the misplacement concrete; worth adding before fixing to lock behaviour.
- F05.4: confirm whether `use_tools()` in practice emits one `StateEvent` per tool or one event for all tools — if the former, the `=== requiredMatchCount` check is accidentally fine.
- F05.10: needs visual confirmation in the running viewer; depends on `.twoColumn` CSS which was not read.
