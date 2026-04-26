# Chat Message Rendering

**Reviewer scope:** `packages/inspect-components/src/chat/` (top-level files), `chat/content-data/`, `chat/documents/`; cross-referenced against `packages/inspect-common/src/types/generated.ts`, `src/inspect_ai/model/_chat_message.py`, `src/inspect_ai/_util/content.py`
**Date:** 2026-04-22

---

## Summary

The chat rendering pipeline covers all eight Python `Content` variants (text, reasoning, image, audio, video, data, tool_use, document) and all four roles. However, there are several correctness bugs around the tool-message path (orphans dropped, errors hidden, content types filtered out), citation numbering does not coordinate between inline superscripts and the rendered list, and the `indented` display option is a no-op. There is also a fair amount of dead code: an unused `MessagesContext` plumbed through every renderer, and ~8 CSS-module class references that don't resolve to any rule (or vice-versa).

---

## Findings

### F10.1 — Orphan tool messages are silently dropped

- **Severity:** HIGH
- **Location:** `packages/inspect-components/src/chat/messages.ts:46-54`, `packages/inspect-components/src/chat/ChatMessageRow.tsx:96-101`
- **Category:** fallback-hiding-errors

**Description:**
`resolveMessages` attaches every `role === "tool"` message to the *preceding* resolved entry's `toolMessages` array, regardless of that entry's role. `ChatMessageRow` only iterates `toolMessages` when `resolvedMessage.message.role === "assistant"`. Therefore a tool message that follows a user/system message (or appears first in the conversation) is collected but never rendered.

**Evidence:**
```ts
if (resolved.role === "tool") {
  if (resolvedMessages.length > 0) {
    const msg = resolvedMessages[resolvedMessages.length - 1];
    msg.toolMessages.push(resolved);   // attaches to ANY preceding role
  }
  // else: first message is tool → dropped entirely
}
```

**Why it matters / impact:**
Malformed or provider-reordered conversations (e.g. a tool result with no preceding assistant turn, or a tool result after a user clarification) disappear from the transcript with no placeholder or warning. The viewer is the primary debugging surface for these cases.

**Suggested fix:**
If the preceding entry is not `assistant`, push the tool message as its own `ResolvedMessage` instead of swallowing it.

---

### F10.2 — Standalone tool messages never show `error` and drop most content types

- **Severity:** HIGH
- **Location:** `packages/inspect-components/src/chat/ChatMessage.tsx:116-129`
- **Category:** event-display

**Description:**
When `collapseToolMessages: false` (or when a tool message has `function === "Task"` falling through to `MessageContents`… actually no, only the non-Task branch), tool messages render via `ChatMessage`. The `isNonTaskTool` branch passes content to `ToolOutput` after filtering to `text | image` only — `audio`, `video`, `document`, `data`, `reasoning` content are discarded. Crucially, `message.error` is never read on this path, so a failed tool call rendered standalone shows only its (often empty) `content` and hides the error.

**Evidence:**
```tsx
{isNonTaskTool ? (
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
) : ( ... )}
```

**Why it matters / impact:**
Contrast with the collapsed path (`resolveToolMessage` in `ChatMessageRow.tsx:228-231`), which *does* substitute `error.message` for content. The two render modes show different information for the same message. A user toggling `collapseToolMessages` off to debug a tool failure will see *less* than before.

**Suggested fix:**
Mirror `resolveToolMessage`: if `message.error`, render the error message; pass the full content list (ToolOutput already handles `document`/`data`/`reasoning`).

---

### F10.3 — `display.indented` option has no visual effect

- **Severity:** MEDIUM
- **Location:** `packages/inspect-components/src/chat/ChatMessage.module.css:33-40`
- **Category:** styling

**Description:**
The `.messageContents.indented` rule sets `margin-left: 0rem`, identical to the base `.messageContents { margin-left: 0 }`. The `indented` prop is threaded through `ChatViewDisplayOptions`, documented in `types.ts`, and set by four call sites (`apps/inspect/.../SampleDisplay.tsx:549`, `SamplePrintView.tsx:177`, `apps/scout/.../ResultBody.tsx` ×3) — none of which get any indentation.

**Evidence:**
```css
.messageContents { margin-left: 0; }
.messageContents.indented { margin-left: 0rem; }
```

**Why it matters / impact:**
Either a regression from a refactor (intended value lost) or the option should be removed. Currently it's a misleading no-op API.

---

### F10.4 — Citation superscript numbers don't match the citation list

- **Severity:** MEDIUM
- **Location:** `packages/inspect-components/src/chat/MessageContent.tsx:320-371`, `packages/inspect-components/src/chat/MessageCitations.tsx:23-28`
- **Category:** correctness

**Description:**
Inline `<sup>` markers are numbered by *position within each text block* (positional cites get `positionalCites.length - i`; end-cites get `++citeCount`). The footnote list in `MessageCitations` numbers by `index + 1` over `flatMap((c) => c.citations)`. These two schemes only coincide when there is a single text block whose citations are all non-positional and in arrival order.

Additionally, positional-cite numbering resets to 1 for each text block in the run because the superscript uses `positionalCites.length - i` rather than `citeCount + (positionalCites.length - i)`.

**Evidence:**
```ts
for (let i = 0; i < positionalCites.length; i++) {
  textWithCites = ... + `<sup>${positionalCites.length - i}</sup>` + ...;
}
citeCount = citeCount + positionalCites.length;
const citeText = endCites?.map(() => `${++citeCount}`);
```
vs.
```tsx
{citations.map((citation, index) => (<><span>{index + 1}</span> ...</>))}
```

**Why it matters / impact:**
Users clicking through to citation N in the list may land on an unrelated source. With mixed positional/end citations or multiple coalesced text blocks, the numbering is essentially arbitrary.

**Suggested fix:**
Build a single ordered citation array while inserting superscripts, then pass that exact array (in the same order) to `MessageCitations`.

---

### F10.5 — `isLast` computed against the wrong array length

- **Severity:** LOW
- **Location:** `packages/inspect-components/src/chat/MessageContent.tsx:73-96`
- **Category:** styling

**Description:**
After `normalizeContent` collapses runs of text, the map iterates `normalized` but compares `index === contents.length - 1` (the original, longer array). When collapsing occurs, `isLast` is never true for the final item, so `no-last-para-padding` is not applied.

**Evidence:**
```ts
const normalized = normalizeContent(contents);
return normalized.map((content, index) => {
  ...
  index === contents.length - 1,  // should be normalized.length - 1
```

---

### F10.6 — `<think>` / `<internal>` blocks stripped silently from rendered text

- **Severity:** MEDIUM
- **Location:** `packages/inspect-components/src/chat/MessageContent.tsx:142-151`
- **Category:** fallback-hiding-errors

**Description:**
`purgeInternalContainers` deletes any `<internal>`, `<content-internal>`, or `<think>` element from text content before rendering. There is no visual indicator that content was removed. A model that emits `<think>...</think>` inside a *text* block (rather than a `ContentReasoning` block) — common with open-weights models via raw completion — has that output hidden entirely.

**Why it matters / impact:**
The viewer is meant to faithfully show what the model produced. Silent deletion makes debugging "why did the model say X" impossible when X was inside `<think>`. At minimum a "[hidden internal content]" placeholder or collapse toggle should appear.

---

### F10.7 — System-message collapsing loses ids, metadata, timestamps

- **Severity:** MEDIUM
- **Location:** `packages/inspect-components/src/chat/messages.ts:62-105`
- **Category:** event-display

**Description:**
All system messages are merged into one synthetic message with hard-coded `id: "sys-message-6815A84B062A"`, `metadata: null`, no timestamp. Consequences:
- `labels.messageLabels[originalSystemId]` never matches → system messages can't be labelled.
- `linking.getMessageUrl(originalSystemId)` never matches → copy-link button produces a URL for the synthetic id.
- Per-system-message `metadata` is dropped (assistant/user/tool metadata *is* shown via `ChatMessage.tsx:132-142`).
- A mid-conversation system injection is hoisted to the top, misrepresenting conversation order.

**Why it matters / impact:**
Inconsistent with how every other role preserves identity/metadata. Mid-stream system prompts (e.g. injected reminders) are common in agent loops and reordering them is misleading.

---

### F10.8 — Tool header renders `"tool: null"` when `function` is absent

- **Severity:** LOW
- **Location:** `packages/inspect-components/src/chat/ChatMessage.tsx:87`
- **Category:** event-display

**Description:**
`ChatMessageTool.function` is `string | null | undefined` (generated.ts:609). The header unconditionally appends it.

**Evidence:**
```tsx
{message.role === "tool" ? `: ${message.function}` : ""}
```

**Suggested fix:**
`message.function ? \`: ${message.function}\` : ""`.

---

### F10.9 — Keyboard navigation `itemCount` uses pre-collapse length

- **Severity:** LOW
- **Location:** `packages/inspect-components/src/chat/ChatViewVirtualList.tsx:74-78`
- **Category:** correctness

**Description:**
`useListKeyboardNavigation` is called with `itemCount: messages.length`, but the virtual list renders `collapsedMessages` (tool messages folded in, system messages merged). The hook is also invoked unconditionally before the `useVirtuoso` branch, so when falling back to non-virtual `ChatView` it attaches handlers to a `listHandle` that is never bound.

**Why it matters / impact:**
Keyboard end-of-list / page-down bounds will overshoot by the number of collapsed tool + extra system messages.

---

### F10.10 — `onDownloadFile` never reaches `ContentDocumentView` from chat path

- **Severity:** LOW
- **Location:** `packages/inspect-components/src/chat/MessageContent.tsx:272-276`
- **Category:** dead-code

**Description:**
`ContentDocumentView` accepts `onDownloadFile` and renders a download link when present. The `document` renderer in `messageRenderers` instantiates it without that prop, and there is no plumbing on `ChatViewDisplayOptions` / `MessagesContext` to supply one. The migration doc (`design/migration/chat-migration.md:59`) says it should be "threaded through" — it isn't.

**Why it matters / impact:**
Documents in chat content are never downloadable; the download-link branch in `ContentDocumentView` is dead from this entry point (it *is* reachable from `ToolOutput`, but `ToolOutput` is also never given `onDownloadFile` by `ChatMessage` or `ChatMessageRow`).

---

### F10.11 — `MessagesContext` is created and threaded but never read

- **Severity:** LOW
- **Location:** `packages/inspect-components/src/chat/MessageContents.tsx:21-39`, `packages/inspect-components/src/chat/MessageContent.tsx:121-127`
- **Category:** dead-code

**Description:**
`defaultContext()` allocates `{ citations: [] }`, passed as `context` to every `MessageRenderer.render`. No renderer reads it (the `text` renderer's leading comment says "we'll use it to keep track of citations" but then ignores it). `defaultContext` and `MessagesContext` are also re-exported from `index.ts`.

**Suggested fix:**
Either wire citations through it (which would help F10.4) or delete the parameter, the type, and the exports.

---

### F10.12 — `ContentText.refusal` and `ChatMessageAssistant.model` never surfaced

- **Severity:** INFO
- **Location:** `packages/inspect-components/src/chat/MessageContent.tsx:131-172`, `packages/inspect-components/src/chat/ChatMessage.tsx`
- **Category:** event-display

**Description:**
`refusal: bool | null` on `ContentText` is set everywhere to `null` and never read for display — a refused completion looks identical to a normal one. `ChatMessageAssistant.model` (which model generated the turn) is also never shown. Both may be intentional, but in multi-model evals the per-turn model is useful debugging info.

---

### F10.13 — JSON-detected text drops React `key` and citations

- **Severity:** LOW
- **Location:** `packages/inspect-components/src/chat/MessageContent.tsx:153-155`
- **Category:** correctness

**Description:**
When `isJson(c.text)` is true the renderer returns `<JsonMessageContent id={...} json={obj} />` with no `key` prop (every other branch sets `key={key}`), causing React list-key warnings when multiple content parts exist. It also bypasses the `<MessageCitations>` block, so a JSON-shaped text part with citations loses them.

---

### F10.14 — `normalizeContent` mis-orders output if a raw string appears mid-array

- **Severity:** LOW
- **Location:** `packages/inspect-components/src/chat/MessageContent.tsx:373-385`
- **Category:** correctness

**Description:**
The "shouldn't happen" string branch pushes directly to `result` without first calling `collect()`. Any `ContentText` items already buffered in `collection` are flushed *after* the string, reversing their order relative to it.

**Evidence:**
```ts
if (typeof content === "string") {
  result.push({ type: "text", text: content, ... });  // no collect() first
  continue;
}
```

---

### F10.15 — Dead / mismatched CSS-module classes

- **Severity:** LOW
- **Location:** multiple
- **Category:** dead-code

**Description:**
Referenced in TSX but **not defined** in the corresponding `.module.css` (resolve to `undefined`, silently dropped by `clsx`):
- `styles.userRole` — `ChatMessage.tsx:71` (no `.userRole` in `ChatMessage.module.css`)
- `styles.item` — `ChatViewVirtualList.tsx:188` (only `.list` exists in `ChatViewVirtualList.module.css`)
- `styles.data` — `ContentDataView.tsx:39,112` (no `.data` in `ContentDataView.module.css`)
- `styles.label`, `styles.results` — `WebSearchResults.tsx:19,28` (not in `WebSearchResults.module.css`)

Defined in CSS but **never referenced**:
- `.list` — `ChatViewVirtualList.module.css:1`
- `.data` — `MessageContent.module.css:15`
- `.webSearch`, `.query` — `WebSearchResults.module.css:1-10` (copy-pasted from `WebSearch.module.css`)
- `.jsonMessage {}` — `JsonMessageContent.module.css:1` (empty rule; whole file is a no-op)
- `.codeCompact {}`, `.simple {}` — `ChatMessageRow.module.css:53-59` (empty placeholder rules)

**Why it matters / impact:**
None of these break rendering, but `userRole` strongly suggests a lost style (cf. `systemRole` which dims opacity), and `styles.item` was presumably meant to apply the `.list` margin.

---

### F10.16 — Tool-message `metadata` not shown on the collapsed path

- **Severity:** LOW
- **Location:** `packages/inspect-components/src/chat/ChatMessageRow.tsx:104-156`
- **Category:** consistency

**Description:**
When tool messages are folded into the preceding assistant row, only `content`/`error` are extracted via `resolveToolMessage`. `toolMessage.metadata` is discarded. Standalone `ChatMessage` does render `metadata` (lines 132-145), so the two paths are inconsistent.

---

### F10.17 — Duplicate `tool_call_id` resolves to the same response twice

- **Severity:** LOW
- **Location:** `packages/inspect-components/src/chat/ChatMessageRow.tsx:110-116`
- **Category:** correctness

**Description:**
`toolMessages.find(msg => msg.tool_call_id === tool_call.id)` returns the first match. If a provider emits two tool calls with the same `id` (observed with some OpenAI parallel-call edge cases), both render the first response and the second response is orphaned. The fallback-by-index path (`toolMessages[idx]`) only triggers when `tool_call.id` is falsy.

**Suggested fix:**
Track consumed tool-message indices, or fall back to index when `find` returns an already-consumed match.

---

### F10.18 — Images rendered without `alt`; download link is non-keyboard-accessible

- **Severity:** LOW
- **Location:** `packages/inspect-components/src/chat/MessageContent.tsx:225`, `packages/inspect-components/src/chat/documents/ContentDocumentView.tsx:67-75`
- **Category:** a11y

**Description:**
- `<img src={c.image} className={styles.contentImage} />` has no `alt`.
- The document download uses `<a onClick={...}>` with no `href`, `role="button"`, `tabIndex`, or key handler — unreachable via keyboard and announced as a generic element by screen readers.

---

### F10.19 — `DocumentCitation` rendered with no distinguishing info

- **Severity:** INFO
- **Location:** `packages/inspect-components/src/chat/MessageCitations.tsx:37-50`
- **Category:** event-display

**Description:**
`MessageCitation` special-cases `type === "url"` (renders a link) and falls through to `OtherCitation` for `content` and `document`. `DocumentCitation` carries a `range: { type: "page" | "block" | "char", start_index, end_index }` which is never shown — the user sees only the title/cited_text with no indication of which document or page. If `title` and `cited_text` are both null (valid per schema), the citation row is blank.

---

### F10.20 — Minor dead expressions

- **Severity:** INFO
- **Location:** `packages/inspect-components/src/chat/ChatMessageRow.tsx:76`, `packages/inspect-components/src/chat/MessageContent.tsx:406-409`
- **Category:** dead-code

**Description:**
- `String(number) || undefined` — `String(n)` is never falsy for `n ≥ 1`; the `|| undefined` is unreachable.
- `export type DistributiveOmit` is exported but only used by the private `isCitationWithRange` in the same file; not re-exported from `index.ts`.
- `const cites = c.citations ?? [];` (MessageContent.tsx:136) — `cites` is computed then re-derived as `c.citations && c.citations.length` six lines later instead of reusing it.

---

### F10.21 — `mimeTypeForFormat` doc comment is wrong

- **Severity:** INFO
- **Location:** `packages/inspect-components/src/chat/MessageContent.tsx:279-300`
- **Category:** code-smell

**Description:**
The JSDoc reads "Renders message content based on its type. Supports rendering strings, images, and tools using specific renderers." — copy-pasted from `MessageContent`. The function maps audio/video format enums to MIME types. Also: the `default` branch returns `"video/mp4"` even for unknown *audio* formats, which would set the wrong `<source type>` on an `<audio>` element.

---

## Files reviewed

- [x] `chat/ChatMessage.tsx` — role header, collapse, metadata; F10.2, F10.3, F10.8, F10.15
- [x] `chat/ChatMessage.module.css` — F10.3, F10.15
- [x] `chat/ChatMessageRow.tsx` — tool-call pairing, label hoisting; F10.2, F10.16, F10.17, F10.20
- [x] `chat/ChatMessageRow.module.css` — F10.15
- [x] `chat/ChatView.tsx` — non-virtual list wrapper; OK
- [x] `chat/ChatViewVirtualList.tsx` — virtual list + keyboard nav; F10.9, F10.15
- [x] `chat/ChatViewVirtualList.module.css` — F10.15
- [x] `chat/JsonMessageContent.tsx` / `.module.css` — empty CSS rule; F10.15
- [x] `chat/MessageCitations.tsx` / `.module.css` — F10.4, F10.19
- [x] `chat/MessageContent.tsx` / `.module.css` — content-type dispatch; F10.4–F10.6, F10.10, F10.11, F10.13, F10.14, F10.18, F10.20, F10.21
- [x] `chat/MessageContents.tsx` — dead context; F10.11
- [x] `chat/index.ts` — exports; OK
- [x] `chat/labelLength.ts` — OK
- [x] `chat/messageSearchText.ts` — search extraction omits `data`/`document`/`image` but that's reasonable for text search
- [x] `chat/messages.ts` — resolve/collapse; F10.1, F10.7
- [x] `chat/messages.test.ts` — covers happy path only; no test for orphan tool / mid-stream system
- [x] `chat/messagesToStr.ts` — string export; OK (handles all content types)
- [x] `chat/types.ts` — option interfaces; OK
- [x] `chat/content-data/ContentDataView.tsx` / `.module.css` — renderer registry; F10.15; silently strips `encrypted_content` (intentional?)
- [x] `chat/content-data/CompactionData.tsx` / `.module.css` — unguarded cast `data[kCompactionMetadata] as Record<...>` will throw on `.type` access if the key is missing, but `canRender` guards it
- [x] `chat/content-data/WebSearch.tsx` / `.module.css` — OK
- [x] `chat/content-data/WebSearchResults.tsx` / `.module.css` — F10.15
- [x] `chat/documents/ContentDocumentView.tsx` / `.module.css` — F10.10, F10.18

## Open questions / needs verification

- Is `purgeInternalContainers` (F10.6) a deliberate product decision? If so it should at least show a redaction marker.
- Is system-message hoisting (F10.7) required by a downstream consumer, or a legacy convenience that should now be opt-in?
- `ContentDataView` strips `encrypted_content` from the fallback `RecordTree` — confirm this is intentional (it hides potentially huge base64 blobs, which seems right, but there's no "[encrypted content hidden]" hint).
