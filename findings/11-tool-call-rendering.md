# Tool Call & Tool Result Rendering

**Reviewer scope:** `inspect-components/src/chat/tools/**`, `inspect-components/src/chat/server-tools/**`, `inspect-components/src/transcript/ToolEventView.tsx`, `inspect-components/src/transcript/ApprovalEventView.tsx`, callers in `ChatMessage.tsx` / `ChatMessageRow.tsx` / `MessageContent.tsx`; cross-referenced against `inspect-common/types/generated.ts` and `src/inspect_ai/tool/_tool_call.py`.
**Date:** 2026-04-22

---

## Summary

Tool rendering is split across three loosely-coupled paths: `ToolCallView` (assistant tool_calls + paired tool messages), `ToolOutput` (orphan tool messages / `ContentTool` wrapper), and `ServerToolCall` (`ContentToolUse`). The paths have drifted: error results are visually indistinguishable from success, several `ToolCallError` / `ToolEvent` fields (`type`, `truncated`, `parse_error`, `failed`, `modified`) are never surfaced, the Python-side `ToolCallContent.format` flag is ignored, and a number of CSS-module class references resolve to `undefined`. Several `.map()` callbacks emit keyless fragments. Most issues are display-fidelity rather than crashes, but the error-masking ones are user-facing.

---

## Findings

### F11.1 — Tool errors rendered identically to successful output

- **Severity:** HIGH
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ToolEventView.tsx:110`; `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/chat/ChatMessageRow.tsx:228-231`
- **Category:** event-display

**Description:**
Both render paths flatten a `ToolCallError` into its `.message` string and pass it through the same `output` prop used for successful results. There is no error styling, icon, or label applied downstream.

**Evidence:**
```tsx
// ToolEventView.tsx
output={event.error?.message || event.result || ""}

// ChatMessageRow.tsx → resolveToolMessage()
const content =
  toolMessage.error !== null && toolMessage.error
    ? toolMessage.error.message
    : toolMessage.content;
```

**Why it matters / impact:**
A `timeout` or `permission` error renders as a plain grey `<pre>` block, exactly like a tool that succeeded and printed text. Users scanning a long transcript cannot tell which tool calls failed without reading every output. Contrast with `ServerToolCall.tsx:126-129`, which renders `content.error` in red bold — the two paths are inconsistent.

**Suggested fix:**
Thread an `error?: ToolCallError` prop into `ToolCallView` and render it with distinct styling (e.g. red left-border + "Error (timeout):" prefix), separate from `output`.

---

### F11.2 — `ToolCallError.type` is never displayed

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ToolEventView.tsx:110`; `chat/ChatMessageRow.tsx:230`
- **Category:** event-display

**Description:**
`ToolCallError` carries a typed enum (`"parsing" | "timeout" | "permission" | "file_not_found" | "limit" | ...`) but only `.message` is ever read. The error type is dropped on the floor in every render path.

**Why it matters / impact:**
The type is the most diagnostically useful field — a generic message like `"command failed"` is far less actionable than knowing it was a `timeout` vs `permission` vs `approval` rejection.

**Suggested fix:**
Prefix the rendered error with the type, e.g. `` `${error.type}: ${error.message}` ``.

---

### F11.3 — Single content-object outputs are JSON-stringified instead of rendered

- **Severity:** HIGH
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/chat/tools/ToolCallView.tsx:273-293`
- **Category:** correctness

**Description:**
`normalizeContent` only checks `Array.isArray(output)`. Per `ToolEvent.result` (generated.ts:2869), the result can be a *single* `ContentText | ContentImage | ContentAudio | ContentVideo | ContentDocument` object (not wrapped in an array). That hits the `else` branch and is `JSON.stringify`'d into a text blob.

**Evidence:**
```tsx
if (Array.isArray(output)) {
  return output;
} else {
  return [{
    type: "tool",
    content: [{
      type: "text",
      text: typeof output === "object"
        ? JSON.stringify(output)
        : String(output),
      ...
```

**Why it matters / impact:**
A tool returning a single `ContentImage` renders as `{"type":"image","image":"data:image/png;base64,iVBOR..."}` instead of an `<img>`. Same for single `ContentDocument`.

**Suggested fix:**
Add `else if (typeof output === "object" && "type" in output) { return [output]; }` before the stringify fallback.

---

### F11.4 — `ToolCallContent.format` is ignored

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/chat/tools/ToolInput.tsx:36-43`
- **Category:** correctness

**Description:**
Python `ToolCallContent` has `format: Literal["text", "markdown"]` (`_tool_call.py:18`). The renderer always passes `toolCallView.content` to `RenderedText` (markdown), regardless of `format`.

**Evidence:**
```tsx
if (useToolView) {
  return (
    <RenderedText
      markdown={toolCallView.content || ""}
      ...
```

**Why it matters / impact:**
A tool author who sets `format="text"` to display literal content containing `*`, `_`, `#`, `<`, or `[...]()` will see it mangled by the markdown parser. The Python contract is silently violated.

**Suggested fix:**
Branch on `toolCallView.format === "text"` → render in `<pre>` (or `Preformatted`); else markdown.

---

### F11.5 — `ServerToolCall` displays the constant `"tool_use"` instead of `tool_type`

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/chat/server-tools/ServerToolCall.tsx:55`
- **Category:** event-display

**Description:**
The header right-slot renders `{content.type}`. Per `ContentToolUse` (generated.ts:838-863), `type` is the literal discriminant `"tool_use"` — every server tool call shows the same useless label. The meaningful field is `tool_type` (`"web_search" | "mcp_call" | "code_execution"`).

**Evidence:**
```tsx
<div className={styles.type}>{content.type}</div>
```

**Why it matters / impact:**
Users see `tool_use` on every server-tool header instead of `web_search` / `mcp_call` / `code_execution`.

**Suggested fix:**
`{content.tool_type}`.

---

### F11.6 — `ToolEventView` useMemo depends on `event.events` instead of `childNodes`

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ToolEventView.tsx:64-78`
- **Category:** correctness

**Description:**
The memo closure reads `childNodes` but the dependency array is `[event.events]` (a deprecated, typically-empty field). The eslint rule is suppressed.

**Evidence:**
```tsx
const { approvalNode, lastModelNode } = useMemo(() => {
  const approval = childNodes.find((e) => e.event.event === "approval");
  const lastModel = childNodes.findLast((e) => e.event.event === "model");
  return { approvalNode: ..., lastModelNode: ... };
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [event.events]);
```

**Why it matters / impact:**
In live/streaming view, when a child approval or model event arrives (mutating `childNodes`) but `event.events` is referentially stable, the approval/model panel will not appear until something else forces a remount.

**Suggested fix:**
Change dep to `[childNodes]` and drop the eslint-disable.

---

### F11.7 — `ToolEvent.truncated` is never surfaced

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ToolEventView.tsx` (omission)
- **Category:** event-display

**Description:**
`ToolEvent.truncated?: [number, number]` (generated.ts:2875) records that tool output was clipped (original vs displayed bytes). `ToolEventView` never reads it.

**Why it matters / impact:**
Users see a result that ends mid-stream with no indication it was truncated by Inspect rather than by the tool itself. Debugging "why is my output cut off" becomes guesswork.

**Suggested fix:**
When `event.truncated`, append a muted footer: `Output truncated (showing N of M bytes)`.

---

### F11.8 — `ChatMessage` filters orphan tool-message content to text+image only

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/chat/ChatMessage.tsx:117-125`
- **Category:** event-display / consistency

**Description:**
When a tool message is rendered standalone (not paired under an assistant call), its content is pre-filtered to `text | image` before being handed to `ToolOutput` — even though `ToolOutput` itself handles `document`, `reasoning`, and `data`.

**Evidence:**
```tsx
<ToolOutput
  output={
    typeof message.content === "string"
      ? message.content
      : message.content.filter(
          (c): c is ContentText | ContentImage =>
            c.type === "text" || c.type === "image"
        )
  }
/>
```

**Why it matters / impact:**
A tool message containing a `ContentDocument` or `ContentData` block renders as empty when shown via this path, but renders correctly via the paired-with-assistant path (`ChatMessageRow → ToolCallView → MessageContent`). Silent content drop, inconsistent between views.

**Suggested fix:**
Filter only `tool_use` out (to match `ToolOutputProps`), not everything except text/image.

---

### F11.9 — `ToolOutput` silently drops `audio` and `video` content

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/chat/tools/ToolOutput.tsx:34-65`
- **Category:** event-display

**Description:**
The `forEach` switch handles `text`, `document`, `image`, `reasoning`, `data` — but `ContentAudio` and `ContentVideo` (both valid per the prop type `Exclude<Content, {type:"tool_use"}>[]`) fall through with no output and no warning.

**Why it matters / impact:**
Audio/video tool results vanish in `ToolOutput` but render fine in `MessageContent` (which has `audio`/`video` renderers). Another path divergence.

---

### F11.10 — `ToolOutput` hides falsy-but-valid results

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/chat/tools/ToolOutput.tsx:28-30`
- **Category:** fallback-hiding-errors

**Description:**
```tsx
if (!output) {
  return null;
}
```
`output` is typed `string | number | boolean | ...[]`. Values `0`, `false`, and `""` are valid tool results that get suppressed.

**Why it matters / impact:**
A tool that returns `false` or `0` shows nothing, which is indistinguishable from "no result yet."

**Suggested fix:**
`if (output === undefined || output === null || (Array.isArray(output) && output.length === 0))`.

---

### F11.11 — `ApprovalEventView` drops `modified`, `approver`, and `message`

- **Severity:** MEDIUM
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ApprovalEventView.tsx:22-31`
- **Category:** event-display

**Description:**
`ApprovalEvent` carries `approver: string`, `message: string`, and `modified?: ToolCall` (generated.ts:372-395). The view renders only `decision` + `explanation`. When `decision === "modify"`, the modified tool call (the thing the user most needs to see) is not shown.

**Why it matters / impact:**
A reviewer cannot see *what* the approver changed the call to, or *who* approved it. "Modified" with no diff is uninformative.

---

### F11.12 — Five CSS-module class references resolve to `undefined`

- **Severity:** LOW
- **Location:**
  - `chat/tools/ToolOutput.tsx:91` → `styles.ansiOutput` (not in `ToolOutput.module.css`)
  - `chat/tools/ToolInput.tsx:82` → `styles.bottomMargin` (not in `ToolInput.module.css`)
  - `chat/tools/tool-input/TodoWriteInput.tsx:56` → `styles.todoItem` (not in `TodoWriteInput.module.css`)
  - `chat/server-tools/ServerToolCall.tsx:55` → `styles.type` (not in `ServerToolCall.module.css`)
  - `chat/server-tools/ServerToolCall.tsx:89` → `styles.result` (not in `ServerToolCall.module.css`)
- **Category:** dead-code / styling

**Description:**
Each reference compiles to `undefined`, which `clsx` drops silently. Intended styling (e.g. ANSI output sizing, todo-item spacing) is simply absent.

**Why it matters / impact:**
No crash, but whatever margin/spacing/colour was intended is missing. Also defeats `typescript-plugin-css-modules` if it were enabled.

---

### F11.13 — Missing React `key` on mapped fragments

- **Severity:** LOW
- **Location:** `chat/tools/tool-input/TodoWriteInput.tsx:43-64`; `chat/server-tools/ServerToolCall.tsx:72-81` and `:103-122`
- **Category:** code-smell

**Description:**
`.map()` callbacks return `<>...</>` with no `key`. React emits "Each child in a list should have a unique key" warnings and may mis-reconcile on re-render.

**Evidence:**
```tsx
{todoItems.map((todo) => {
  return (
    <>
      <i className={...} />
      <span ...>{todo.content}</span>
    </>
  );
})}
```

**Suggested fix:**
Use `<Fragment key={...}>`.

---

### F11.14 — `ServerToolCall` reuses the same `ExpandablePanel` id across siblings

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/chat/server-tools/ServerToolCall.tsx:107,132`
- **Category:** collapse-expand

**Description:**
Inside the `mcp_list_tools` branch, every per-tool `ExpandablePanel` gets `id={\`${id}-output\`}` (no `index`), and the generic-result panel below uses the same id. `ExpandablePanel` persists collapse state by id.

**Why it matters / impact:**
Expanding one tool in the list expands/collapses all of them (shared state key). The fallback result panel also collides.

**Suggested fix:**
`` id={`${id}-tool-${index}`} `` for the loop; keep `${id}-output` for the fallback only.

---

### F11.15 — `TodoWriteInput` silently renders nothing on shape mismatch

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/chat/tools/tool-input/TodoWriteInput.tsx:25-33`
- **Category:** fallback-hiding-errors

**Description:**
`toToolTodos` returns `[]` if any item in the array fails the `isRawTodo` guard (e.g. one todo missing `status`). The component then renders an empty `<div>` — the entire todo list disappears with no fallback.

**Why it matters / impact:**
A minor schema drift (e.g. Claude Code renaming a field) makes the todo input invisible instead of falling back to the raw JSON view.

**Suggested fix:**
On guard failure, fall through to the generic `<pre>{JSON.stringify(contents, null, 2)}</pre>` path.

---

### F11.16 — `ToolCall.parse_error` is never displayed

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/chat/ChatMessageRow.tsx:104-156` (omission)
- **Category:** event-display

**Description:**
`ToolCall.parse_error?: string | null` (generated.ts:2780) records when the model emitted malformed tool-call JSON. Neither `ChatMessageRow` nor `ToolEventView` reads it.

**Why it matters / impact:**
When a model hallucinates bad arguments, the viewer shows the (possibly empty/partial) `arguments` dict with no hint that parsing failed.

---

### F11.17 — `web_search` input is highlighted as JSON

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/chat/tools/tool.ts:68-72`
- **Category:** consistency

**Description:**
`extractInputMetadata("web_search")` returns `contentType: "json"`, but the extracted `input` is the raw `query` string (e.g. `"latest claude model"`). It is rendered in a `<code class="language-json">` block.

**Why it matters / impact:**
Plain-English queries get JSON syntax highlighting (colons/braces highlighted if present), inconsistent with `bash`/`python` which use the correct language. Cosmetic.

**Suggested fix:**
Use `contentType: "text"` (or omit) for `web_search`.

---

### F11.18 — `contentType` (an input descriptor) gates *output* rendering

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/chat/tools/ToolCallView.tsx:171-180`
- **Category:** code-smell / consistency

**Description:**
`contentType` is derived from `extractInputMetadata` and describes how to syntax-highlight the *input*. But `ToolCallView` also uses `contentType === "markdown"` to decide whether to render *output* via `MarkdownToolOutput`. The only tool that sets `"markdown"` is `Task`, so this is effectively a hard-coded special case smuggled through an unrelated field.

**Why it matters / impact:**
Adding a new tool with markdown-formatted *input* would unexpectedly switch its *output* to markdown rendering. Confusing coupling.

---

### F11.19 — `collapsible={false}` is ignored for markdown output

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/chat/tools/ToolCallView.tsx:171-193`
- **Category:** collapse-expand

**Description:**
The ternary checks `collapsible` only on the second branch. When `contentType === "markdown"`, output is always wrapped in `ExpandablePanel` regardless of `collapsible`.

**Evidence:**
```tsx
{contentType === "markdown" && hasContent ? (
  <ExpandablePanel ...>...</ExpandablePanel>   // ignores collapsible
) : hasContent && collapsible ? (
  <ExpandablePanel ...>...</ExpandablePanel>
) : (
  <MessageContent ... />
)}
```

---

### F11.20 — Custom-view callback receives a stripped props object

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/chat/tools/ToolCallView.tsx:128-142`
- **Category:** consistency

**Description:**
A fresh `props: ToolCallViewProps` is built that omits `view`, `mode`, and `collapsible` before being passed to `getCustomToolView` / `getDefaultCustomToolView`. A custom renderer cannot honour the Python-supplied `view` or the caller's `mode`.

**Suggested fix:**
Pass the component's full props (or destructured originals) instead of rebuilding a partial object.

---

### F11.21 — `ToolTextOutput` uses a non-unique hardcoded id

- **Severity:** LOW
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/chat/tools/ToolOutput.tsx:84`
- **Category:** code-smell

**Description:**
```tsx
return <JsonMessageContent id={`1-json`} json={obj} />;
```
Every JSON tool output on the page gets `id="1-json"`. If `JsonMessageContent` keys collapse state on id (as other components do), all JSON outputs share state.

---

### F11.22 — Stale / copy-pasted docstrings

- **Severity:** INFO
- **Location:** `chat/tools/ToolTitle.tsx:11-13` ("Renders the ToolCallView component"); `chat/tools/ToolCallView.tsx:198-200` (same comment on a `type`); `chat/server-tools/ServerToolCall.tsx:20-22` ("Renders the ToolOutput component")
- **Category:** code-smell

**Description:**
JSDoc headers were copy-pasted and never updated to match the component they sit on.

---

### F11.23 — Object args stringified without indentation in `ToolInput`

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/chat/tools/ToolInput.tsx:73-74`
- **Category:** consistency

**Description:**
`JSON.stringify(contents)` (no indent) produces a single unwrapped line, whereas `formatArg` in `tool.ts:147` uses `JSON.stringify(value, undefined, 2)`. Nested-object tool inputs render as one long line in the `<pre>` block.

---

### F11.24 — `ToolEvent.failed` not reflected in `ToolEventView` header

- **Severity:** INFO
- **Location:** `src/inspect_ai/_view/ts-mono/packages/inspect-components/src/transcript/ToolEventView.tsx`
- **Category:** event-display

**Description:**
`event.failed` is consumed by the timeline (`useEventNodes.ts:43`) but the transcript event card itself shows no failure indicator on its header/icon. Related to F11.1 but at the panel-chrome level rather than the body.

---

### F11.25 — `ToolCallView.context` (Python `ToolCallView.context`) has no consumer

- **Severity:** INFO
- **Location:** `inspect-common/types/generated.ts:2824-2827` vs all renderers
- **Category:** event-display

**Description:**
Python's `ToolCallView` has both `call` and `context` (`_tool_call.py:32-36`). The log schema serialises only the `call` portion onto `ToolCall.view` / `ToolEvent.view` (a single `ToolCallContent`), so `context` never reaches the renderer. The full `ToolCallView` schema (with `context`) appears in `generated.ts` only on `ApprovalEvent.view` (line 404) — and `ApprovalEventView` ignores it. Net: tool authors who populate `ToolCallView.context` see nothing in the UI.

---

## Files reviewed

- [x] `chat/tools/ToolCallView.tsx` — main renderer; F11.3, F11.18, F11.19, F11.20
- [x] `chat/tools/ToolCallView.module.css` — minimal, ok
- [x] `chat/tools/ToolInput.tsx` — F11.4, F11.12, F11.23
- [x] `chat/tools/ToolInput.module.css` — missing `.bottomMargin`
- [x] `chat/tools/ToolOutput.tsx` — F11.9, F11.10, F11.12, F11.21
- [x] `chat/tools/ToolOutput.module.css` — missing `.ansiOutput`
- [x] `chat/tools/ToolTitle.tsx` — F11.22
- [x] `chat/tools/ToolTitle.module.css` — ok
- [x] `chat/tools/customToolRendering.tsx` — `answer` tool only; ok
- [x] `chat/tools/tool.ts` — `resolveToolInput`; F11.17
- [x] `chat/tools/tool-input/TodoWriteInput.tsx` — F11.12, F11.13, F11.15
- [x] `chat/tools/tool-input/TodoWriteInput.module.css` — missing `.todoItem`
- [x] `chat/server-tools/ServerToolCall.tsx` — F11.5, F11.12, F11.13, F11.14
- [x] `chat/server-tools/ServerToolCall.module.css` — missing `.type`, `.result`
- [x] `transcript/ToolEventView.tsx` — F11.1, F11.2, F11.6, F11.7, F11.24
- [x] `transcript/ApprovalEventView.tsx` — F11.11
- [x] `chat/ChatMessageRow.tsx` — caller; F11.1, F11.16
- [x] `chat/ChatMessage.tsx` — caller; F11.8
- [x] `chat/MessageContent.tsx` — `tool` / `tool_use` dispatch; ok for this scope
- [x] `inspect-common/src/types/generated.ts` — type cross-reference
- [x] `src/inspect_ai/tool/_tool_call.py` — Python source of truth
- [x] `src/inspect_ai/model/_chat_message.py` — `ChatMessageTool` shape

## Open questions / needs verification

- F11.3: confirm whether any production path actually emits a *bare* `ContentImage` (not array-wrapped) as `ToolEvent.result`. The Python `ToolResult` type allows it; need a real log to confirm it hits the stringify branch.
- F11.14: depends on whether `ExpandablePanel` keys collapse state on `id` (other components in this package do). If it's purely local state, severity drops to INFO.
- F11.25: verify whether any built-in tool actually sets `ToolCallView.context` — if none do, this is purely theoretical.
