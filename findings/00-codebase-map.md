# Inspect AI Viewer Architecture Map

## Overview

The Inspect AI viewer is a **browser-based evaluation log explorer** with a Python FastAPI backend and TypeScript React frontend (distributed as a git submodule). It displays evaluation transcripts with collapsible events, chat histories, model calls, and interactive scoring interfaces.

**Key locations:**
- **Backend:** `src/inspect_ai/_view/*.py` (FastAPI server, schema generation)
- **Frontend:** `src/inspect_ai/_view/ts-mono/` (monorepo with apps + packages)

---

## Part 1: Python Backend Architecture

### `src/inspect_ai/_view/` Directory

| File | Purpose |
|------|---------|
| `server.py` | View server entry point; orchestrates start/stop |
| `fastapi_server.py` | FastAPI app factory with routes for logs, events, samples, attachments, scoring |
| `schema.py` | OpenAPI schema generator; creates `inspect-openapi.json` → runs `openapi-typescript` |
| `common.py` | Shared utilities: log dir/file access, log filtering, streaming |
| `notify.py` | Optional file change notification (used during log polling) |
| `view.py` | View mode entry; sets up browser launch and server config |
| `_dist.py` | Resolves dist directory for pre-built frontend bundle |
| `_openapi.py` | Custom OpenAPI schema builder with stable type names |

### Event Type Pipeline (Python → TypeScript)

Python defines 20 event types in `src/inspect_ai/event/_*.py`:
1. **SampleInitEvent** - marks log start
2. **SampleLimitEvent** - marks sample limit breach
3. **SandboxEvent** - sandbox state change
4. **StateEvent** - mutable state snapshot (LLM context, etc.)
5. **StoreEvent** - persistent store updates
6. **ModelEvent** - LLM API calls and responses
7. **ToolEvent** - tool invocation and results
8. **SpanBeginEvent / SpanEndEvent** - timing/nesting spans
9. **StepEvent** - deprecated; replaced by spans
10. **ToolEvent** - tool calls with input/output
11. **ApprovalEvent** - human approval/rejection
12. **BranchEvent** - branching logic markers
13. **CompactionEvent** - transcript compression markers
14. **InputEvent** - sample input data
15. **ScoreEvent** - evaluation scores
16. **ScoreEditEvent** - manual score edits
17. **ErrorEvent** - runtime errors
18. **LoggerEvent** - logging messages
19. **InfoEvent** - arbitrary JSON metadata
20. **SubtaskEvent** - nested subtask tracking

**Flow:** `Event` classes → Pydantic serialization → OpenAPI schema → `inspect-openapi.json` → `openapi-typescript` → `packages/inspect-common/src/types/generated.ts`

---

## Part 2: TypeScript Frontend Architecture

### Monorepo Structure (`ts-mono/`)

**Key constraint (from AGENTS.md):**
- Consumed via git submodule in parent repos (inspect_ai, inspect_scout, VS Code extension)
- Turbo orchestrates workspace scripts (single-concern leaf commands)
- pnpm workspace; `"workspace:*"` protocol for interdeps
- **`@tsmono/util`** is barrel export (import from package, not individual files)

### Apps

#### `apps/inspect/src/`

**Main viewer application.** Renders log list, sample transcript, scoring UI.

| Folder | Purpose |
|--------|---------|
| `client/` | API abstraction layer |
| `client/api/` | Client implementations: `view-server`, `vscode`, `static-http` (for different deployment modes) |
| `client/api/types.ts` | Type definitions: `SampleData`, `LogDetails`, event unions |
| `client/database/` | IndexedDB abstraction (message/call pool deduplication, schema v1) |
| `client/storage/` | VSCode state persistence + localStorage fallback |
| `client/remote/` | ZIP file parsing, zstd decompression, remote file streaming |
| `state/` | Redux store slices + hooks (appSlice, sampleSlice, logsSlice, scoring, polling) |
| `app/` | Main components: `App.tsx`, routing, layout, tabs |
| `app/log-view/` | Sample transcript display + event rendering |
| `app/log-list/` | Log list filtering, pagination, sorting |
| `app/samples/` | Sample list, metadata, scoring interface |
| `app/samples-panel/` | Sample detail sidebar |
| `app/appearance/` | Theme, display mode (raw/rendered) |
| `components/` | App-specific wrappers (LogViewer, TranscriptPanel, etc.) |
| `scoring/` | Score input form, retry logic, API calls |
| `utils/` | Formatters, filters, URL/path manipulation |

### Packages

#### `packages/inspect-common/src/`

**Generated types and utilities.** NO manual edits — `schema.py` regenerates.

| File | Purpose |
|------|---------|
| `types/generated.ts` | Auto-generated from Python via openapi-typescript |
| `types/index.ts` | Re-exports + stable union types |
| `utils/expandEvents.ts` | Flattens nested transcript structure |
| `utils/sampleLimit.ts` | Detects sample limit events |
| `utils/inputString.ts` | Serializes sample input to string |

#### `packages/inspect-components/src/`

**Reusable components for transcripts, chat, content rendering.**

| Folder | Purpose |
|--------|---------|
| `transcript/` | Event rendering pipeline |
| `transcript/types.ts` | Core types: `EventNode`, `StateManager`, collapse scopes |
| `transcript/transform/` | Event tree transformations (see below) |
| `transcript/event/` | Event panel + section renderers |
| `transcript/state/` | StateEvent rendering (JSON diffs, previews) |
| `transcript/outline/` | Transcript outline navigation |
| `transcript/timeline/` | Timeline breadcrumb navigation |
| `transcript/hooks/` | Transcript-specific hooks |
| `chat/` | ChatMessage rendering |
| `chat/messages.ts` | ChatMessage type definitions & parsing |
| `chat/MessageContent.tsx` | Content renderer dispatch (see below) |
| `chat/tools/` | ToolCall, ToolResult rendering |
| `chat/server-tools/` | Server-side tool rendering (tool_use content) |
| `chat/documents/` | Document content rendering |
| `chat/content-data/` | Arbitrary JSON data viewing |
| `content/` | Shared content: text, images, records, metadata grid |
| `content/record_processors/` | Custom record formatters (e.g. pandas DataFrame) |
| `usage/` | Token usage display |

#### `packages/react/src/`

**Foundational, reusable React components & hooks.**

| Folder | Purpose |
|--------|---------|
| `components/` | 38+ UI components: ExpandablePanel, TabSet, SegmentedControl, MarkdownDiv, Preformatted, JsonPanel, LabeledValue, Modal, PopOver, etc. |
| `hooks/` | useProperty (state persistence), useStatefulScrollPosition, useVirtuosoState, usePrismHighlight |
| `state/` | ComponentStateContext (per-component property bag management) |

#### `packages/theme/src/`

**CSS design tokens, color palettes, typography scales.**

#### `packages/util/src/`

**Utility functions.** Barrel export; import from package root only. 38 files covering:
- JSON processing (json-worker.ts: 1.2k lines)
- Format/display (date, time, numbers)
- Path/URI manipulation
- ANSI terminal sequences
- Base64 encoding
- Type guards and helpers

#### `packages/scout-components/src/`

**Scout-specific components** (used by inspect_scout, not viewer). Separate relaxed linting rules.

---

## Part 3: Event Rendering Pipeline

### Raw Event → Rendered Panel Flow

```
1. Python EventLog → FastAPI /events endpoint
2. Browser fetch → apps/inspect/src/state/useLoadLog.ts
3. Normalize & expand via inspect-common/utils/expandEvents.ts
4. Transform via packages/inspect-components/src/transcript/transform/:
   - flatten.ts: collapses single-child spans
   - treeify.ts: rebuilds tree structure from flat list
   - transform.ts: applies state machine (unwrap_main, split_spans, etc.)
   - fixups.ts: post-processing fixups
5. EventNode[] → inspect-components/src/transcript/ renderers
6. render() → EventPanel (collapsible) → EventSection + EventRow
```

### Event Type Renderers

Each event type has specialized rendering logic, keyed by `event.type`:

| Event Type | Renderer Component | Key Details |
|------------|-------------------|------------|
| **span_begin** | EventPanel (recursive children) | Collapsible tree; shows duration if span_end present |
| **model** | ModelEvent renderer | Shows request/response, model name, token counts |
| **tool** | ToolEvent renderer | Shows tool name, input, output, nested calls |
| **state** | StateEventView.tsx | JSON diff viewer; expandable preview mode |
| **store** | StoreEvent renderer | Key-value map display |
| **score** | ScoreEvent renderer | Score name, value, metadata |
| **step** (deprecated) | SpanBeginEvent-like | Timing info, context |
| **subtask** | SubtaskEvent renderer | Nested task tracking |
| **input** | InputEvent renderer | Sample input display |
| **logger** | LoggerEvent renderer | Log level, message text, optional context |
| **info** | InfoEvent renderer | Generic JSON display |
| **error** | ErrorEvent renderer | Error type, message, traceback |
| **approval** | ApprovalEvent renderer | Approval status, actor, comment |
| **branch** | BranchEvent renderer | Branch condition, outcome |
| **compaction** | CompactionEvent renderer | Marker; shows compaction summary |
| **sandbox** | SandboxEvent renderer | Sandbox state changes |
| **sample_init** / **sample_limit** | Special handling | Timeline markers |

**All event renderers receive:**
- `EventPanelCallbacks`: `{ onCollapse, getCollapsed, getEventUrl, linkingEnabled }`
- `eventNodeId`: string (unique per panel for collapse tracking)
- `children`: React elements from child events

---

## Part 4: Chat Message Rendering Pipeline

### ChatMessage Type & Rendering

**Type definition:** `inspect-common/types/generated.ts` → `ChatMessage` (union of role-based types)

**Roles:** user, assistant, system, tool

**Content types** (rendered via `messageRenderers` dispatcher in `MessageContent.tsx`):

| Type | Renderer | Supports |
|------|----------|----------|
| **text** | TextRenderer | Plain text, markdown, JSON parsing, citations |
| **reasoning** | ReasoningRenderer | Reasoning text, redacted mode, summaries, OpenRouter JSON format |
| **image** | ImageRenderer | Data URI or URL |
| **audio** | AudioRenderer | Base64 data, MIME type detection (mp3/wav) |
| **video** | VideoRenderer | Base64 data, MIME type detection (mp4/mov/mpeg) |
| **document** | DocumentRenderer | PDF, markdown, structured content |
| **data** | DataRenderer | Arbitrary JSON, with custom processors |
| **tool** | ToolRenderer | Tool output (text/structured) |
| **tool_use** | ServerToolRenderer | Server-side tool invocation (Claude API format) |

**Message rendering flow:**
```
ChatMessage → ChatMessage.tsx (role header, timestamp, linking)
  → MessageContents.tsx (combines multiple content blocks)
    → MessageContent.tsx (per-content-type renderer dispatch)
      → Content-specific component (MarkdownDiv, AudioPlayer, JsonPanel, etc.)
```

**Special features:**
- Citations attached to text blocks (superscript numbers)
- Refusal text (redacted if present)
- Internal reasoning XML tags stripped (`<internal>`, `<think>`)
- Tool calls vs tool results distinguished by role
- Message visibility toggle (system/user collapsed by default)

---

## Part 5: Collapse/Expand & Visibility System

### Collapse State Storage

**Stored in Redux:** `appSlice.ts` → `collapsed: Record<string, boolean>`

**Keys:** `{eventNodeId}` → boolean (true = collapsed)

**Retrieval in EventPanel:**
```tsx
const collapsed = getCollapsed?.(eventNodeId) ?? false;
const toggleCollapse = () => onCollapse?.(eventNodeId, !collapsed);
```

### Visibility Toggle (separate from collapse)

**Stored in:** `appSlice.ts` → `messages: Record<string, boolean>`

**Used for:** Role visibility (hide system/assistant messages)

**Implementation:** `setMessageVisible(id, bool)` / `getMessageVisible(id)`

### Default-Collapsed Behavior

**Event types with children default to collapsed:**
- `span_begin`, `step`, `tool` (via `kCollapsibleEventTypes`)

**Per-panel override:** `data-default` attribute on child elements

**Manual override:** User click toggles `collapsed` state in Redux

### Property Persistence

**Cross-component state via `useProperty` hook** (packages/react/src/hooks/useProperty.ts):
```tsx
const [selectedNav, setSelectedNav] = useProperty(eventNodeId, "selectedNav", {
  defaultValue: defaultPillId
});
```

**Under the hood:** ComponentStateContext → Redux propertyBags

---

## Part 6: Key Shared Abstractions

### Core Reusable Components (`packages/react/src/components/`)

**UI Building Blocks:**
- `ExpandablePanel` - toggle content visibility
- `TabSet` / `NavPills` - tab navigation
- `Card` - styled container
- `Modal` / `PopOver` - dialogs and popovers
- `SegmentedControl` - button group selector
- `TextInput` / `AutocompleteInput` - form inputs
- `MarkdownDiv` / `MarkdownDivWithReferences` - Markdown rendering with links
- `Preformatted` - code/monospace display with copy button
- `SourceCodePanel` - syntax-highlighted code with language detection
- `JsonPanel` - collapsible JSON tree viewer
- `LabeledValue` - label + value layout
- `ProgressBar` - visual progress indicator
- `LightboxCarousel` - image gallery viewer
- `LiveVirtualList` - virtualized scrolling (Virtuoso integration)
- `AsciinemaPlayer` - terminal recording playback
- `AnsiDisplay` - ANSI escape sequence rendering
- `CopyButton` - icon button with copy-to-clipboard feedback
- `ErrorPanel` / `EmptyPanel` / `NonIdealState` - state messages
- `LoadingBar` / `PulsingDots` - loading indicators
- `HumanBaselineView` - comparison display

### Reusable Hooks

- `useProperty<T>` - component-scoped state persistence
- `useStatefulScrollPosition` - scroll position restoration
- `useVirtuosoState` - virtualized list state
- `usePrismHighlight` - syntax highlighting
- `useStickyObserver` - sticky element detection

### Context Providers

- `ComponentStateContext` - property bag storage
- `ComponentIconContext` - icon overrides
- `StickyScrollContext` - sticky behavior coordination
- `ContentRenderersContext` - custom content type renderers

---

## Part 7: Data Loading Architecture

### API Client Layer

**Three client implementations** (apps/inspect/src/client/api/):
1. **view-server** - FastAPI backend (default)
2. **vscode** - VS Code extension (JSON-RPC)
3. **static-http** - Static file serving

**All implement common interface:**
```ts
getLog(logFile: string): Promise<LogDetails>
getSample(logFile: string, sampleId: string): Promise<SampleData>
getAttachment(logFile: string, attachmentId: string): Promise<Blob>
scoreLog(logFile: string, sampleId: string, scores: ...): Promise<void>
```

### Storage Layer

**apps/inspect/src/client/database/** - IndexedDB wrapper
- Schema v1: single-key store
- Deduplicates message/call pools (for efficiency)
- Provides sync/async interfaces

**apps/inspect/src/client/storage/** - Persistence
- VSCode: `vscodeApi.getState()` / `vscodeApi.setState()`
- Web: localStorage (via resolveStorage())
- Stores: PersistedState (version + app state)

### Polling & Sync

**apps/inspect/src/state/:**
- `useLoadLog.ts` - initial fetch + caching
- `useLoadSample.ts` - sample fetch
- `logPolling.ts` - long-poll for new samples (backend)
- `samplePolling.ts` - long-poll for sample completion
- `clientEventsService.ts` - optional streaming events (future)
- `usePollSample.ts` - React hook wrapper

### State Management

**Redux store** (apps/inspect/src/state/store.ts):
- `appSlice` - UI state (tabs, dialogs, collapse, scroll positions)
- `logsSlice` - log list + filtering
- `sampleSlice` - current sample + events
- `scoring` - pending score edits

**Key actions:**
- `setCollapsed(id, bool)` - event collapse state
- `setMessageVisible(id, bool)` - message visibility
- `setPropertyValue(bag, key, value)` - generic property persistence
- `setScrollPosition(name, px)` / `getScrollPosition(name)` - virtualized list position

---

## Part 8: Design Docs & Conventions

### AGENTS.md (Monorepo Constraints)

**Critical rules for all ts-mono work:**
- Git submodule consumption — see `docs/submodule-guide.md`
- Turbo orchestrates workspace scripts (single-concern design)
- pnpm only; workspace deps use `"workspace:*"`
- **`@tsmono/util` is barrel export** — always import from root, never individual files
- Legacy code (apps/scout, packages/util) has relaxed linting; new packages are strict

### Design Docs

Located in `ts-mono/design/` (check for migration docs):
- `type-generation-pipeline.md` - Schema → OpenAPI → TS types flow
- Other design decisions TBD by code review

---

## Part 9: Component Dependency Graph (Key Abstractions)

### Transcript Components

```
Transcript (facade)
├── TranscriptView (main layout)
├── TranscriptList (virtualized event list)
│   └── EventRow (event row container)
│       └── EventPanel (collapsible with title)
│           ├── EventSection (titled subsection)
│           ├── EventNavs (tab navigation)
│           └── [Event-specific renderers]
├── TranscriptOutline (nav sidebar)
└── TranscriptTimeline (breadcrumb)
```

### Chat Components

```
ChatView (container)
├── ChatViewVirtualList (virtualized message list)
│   └── ChatMessageRow (message container)
│       └── ChatMessage (role header, content)
│           ├── MessageContents (multi-block container)
│           │   └── MessageContent (type dispatcher)
│           │       ├── RenderedText (Markdown)
│           │       ├── ImageRenderer (img tag)
│           │       ├── AudioRenderer (audio tag)
│           │       ├── VideoRenderer (video tag)
│           │       ├── ToolRenderer (ToolOutput)
│           │       ├── ServerToolRenderer (tool_use)
│           │       ├── ContentDataView (JSON)
│           │       └── ContentDocumentView (PDF/etc.)
│           └── MessageCitations (footnotes)
```

### Content Rendering

```
RenderedContent (dispatch by type)
├── RenderedText (Markdown + links + citations)
├── RecordTree (structured data tree)
│   └── MetaDataGrid (key-value pairs)
├── record_processors/ (custom formatters)
│   ├── pandas DataFrame processor
│   └── other structured types
└── ContentRenderersContext (custom renderers)
```

---

## Part 10: Quick Reference: File Counts & LOC

| Package | Files | Type | Role |
|---------|-------|------|------|
| inspect-common | 8 | Generated + utils | Type defs, event utilities |
| inspect-components | 133+ | TSX/TS | Transcript, chat, content rendering |
| react | 38 | TSX/TS | Reusable UI components & hooks |
| util | 38 | TS | Shared helpers (barrel export) |
| scout-components | N/A | TSX/TS | Scout-specific (separate rules) |
| apps/inspect | 100+ | TSX/TS | Main viewer app |

**Python backend:** ~1500 LOC (server, schema gen, common utils)

---

## Summary: Critical Paths for Code Review

1. **Adding event type?** → Python `event/_*.py` → `schema.py` regen → `generated.ts` auto-updates → add renderer in `transcript/event/` or custom transform in `transform/`

2. **Adding message content type?** → Update Python ChatMessage model → `schema.py` regen → add renderer in `messageRenderers` dict in `MessageContent.tsx`

3. **UI component reuse?** → Add to `packages/react/src/components/`, export from `index.ts`, import via `@tsmono/react/components`

4. **Collapse state needed?** → Use `appSlice.ts` (`getCollapsed` / `setCollapsed`) or `useProperty()` for per-component state

5. **Data loading?** → Implement in `client/api/` (all three backends), store in `state/` slices, optionally cache in `client/database/`

6. **Performance bottleneck?** → Check `transcript/transform/` (tree ops), virtualization (Virtuoso), or message/call pool dedup in IndexedDB

---

*Map generated for multi-agent code review. ~600 lines. For questions on specific components, check corresponding source files.*
