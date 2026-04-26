# Inspect Viewer Code Review Findings

This folder contains findings from a thorough multi-agent code review of the Inspect viewer.

**→ Start here: [`SUMMARY.md`](SUMMARY.md)** — executive summary, top issues, thematic patterns, and recommended next steps.

## Scope

- `src/inspect_ai/_view/` — Python backend (server, API, schema)
- `src/inspect_ai/_view/ts-mono/apps/inspect/` — Main viewer React app
- `src/inspect_ai/_view/ts-mono/packages/inspect-components/` — Transcript, chat, content rendering
- `src/inspect_ai/_view/ts-mono/packages/react/` — Base UI components
- `src/inspect_ai/_view/ts-mono/packages/inspect-common/` — Shared types/utils
- `src/inspect_ai/_view/ts-mono/packages/theme/`, `packages/util/`

## Contents

| File | Description |
|---|---|
| [`SUMMARY.md`](SUMMARY.md) | Executive summary: counts, top ~15 issues, themes, per-area index, next steps |
| [`TEMPLATE.md`](TEMPLATE.md) | Format template for individual findings files |
| [`00-codebase-map.md`](00-codebase-map.md) | Architecture map: backend, monorepo, event/chat pipelines, key abstractions |
| [`01-transcript-event-renderers.md`](01-transcript-event-renderers.md) | Per-event-type renderers (`*EventView.tsx`) and `EventPanel`/`EventNav` primitives |
| [`02-transcript-transform-pipeline.md`](02-transcript-transform-pipeline.md) | `treeify` / `transform` / `flatten` / `fixups` — raw events → render tree |
| [`03-transcript-outline-timeline.md`](03-transcript-outline-timeline.md) | Outline sidebar, timeline swimlanes, state-diff viewer |
| [`04-model-event-and-usage.md`](04-model-event-and-usage.md) | `ModelEventView` and token-usage panels (`ModelUsagePanel`, `TokenTable`) |
| [`05-minor-event-renderers.md`](05-minor-event-renderers.md) | State/Store/SampleInit/Score/Approval/Sandbox/Branch/Compaction renderers |
| [`10-chat-message-rendering.md`](10-chat-message-rendering.md) | `ChatMessage`, `MessageContent`, citations, system-message collapsing |
| [`11-tool-call-rendering.md`](11-tool-call-rendering.md) | `ToolCallView`, `ToolOutput`, `ServerToolCall`, tool input renderers |
| [`20-sample-display-scores.md`](20-sample-display-scores.md) | `SampleDisplay`, `SampleSummaryView`, scoring tab, error/status, print view |
| [`21-sample-list-descriptors.md`](21-sample-list-descriptors.md) | Sample list/grid, score-type descriptors, filter expression engine |
| [`30-log-list-and-view.md`](30-log-list-and-view.md) | Log-list AG-Grid, folder grouping, title-view header (`PrimaryBar`/`StatusPanel`) |
| [`31-log-tabs-plan-navbar.md`](31-log-tabs-plan-navbar.md) | Task/Info/Models/JSON tabs, plan/solver display, navbar breadcrumbs |
| [`40-content-renderers.md`](40-content-renderers.md) | `RenderedContent`, `RecordTree`, `MarkdownDiv`, `ANSIDisplay`, `LightboxCarousel` |
| [`50-state-and-routing.md`](50-state-and-routing.md) | Zustand store slices, persist/rehydrate, hash routing, URL parsing |
| [`51-data-loading-clients.md`](51-data-loading-clients.md) | view-server/vscode/static-http clients, IndexedDB cache, remote zip, replication |
| [`52-app-shell-flow.md`](52-app-shell-flow.md) | `main.tsx`, `App.tsx`, error boundary, flow panel, transcript wrapper |
| [`60-base-react-components.md`](60-base-react-components.md) | `@tsmono/react` shared components (Modal, TabSet, PopOver, etc.) and hooks |
| [`61-theme-icons-appearance.md`](61-theme-icons-appearance.md) | `base.css`, icon registries, dark-mode handling, CSS-variable typos |
| [`62-scout-components-overlap.md`](62-scout-components-overlap.md) | `scout-components` package: overlap with inspect, shared dependency direction |
| [`70-python-view-backend.md`](70-python-view-backend.md) | `server.py` / `fastapi_server.py` / `common.py` — security, async, divergence |
| [`80-utilities-formatting.md`](80-utilities-formatting.md) | `@tsmono/util` vs `apps/inspect/utils/` — duplication, formatter edge cases |
| [`81-dead-code-inventory.md`](81-dead-code-inventory.md) | Mechanical sweep: dead exports, undefined `styles.X`, dead CSS, unused props |
| [`90-cross-cutting-consistency.md`](90-cross-cutting-consistency.md) | Same concept rendered differently across subsystems (timestamps, scores, status) |
| [`91-high-severity-verification.md`](91-high-severity-verification.md) | Independent re-verification of every HIGH finding (17 confirmed, 2 partial, 0 refuted) |
| [`92-duplicate-index.md`](92-duplicate-index.md) | Canonical-ID table for findings reported by multiple agents |
| [`repros/README.md`](repros/README.md) | Minimal `.eval` log files reproducing 53 viewer bugs — open in `inspect view` to see each bug live |

## Organization

Each findings file is numbered and scoped to a specific subsystem. Use `TEMPLATE.md` as the format.

| Range | Area |
|---|---|
| `01-*` through `09-*` | Transcript & event rendering |
| `10-*` through `19-*` | Chat / message / tool-call rendering |
| `20-*` through `29-*` | Sample display, scores, metadata, navigation |
| `30-*` through `39-*` | Log list, filtering, sorting, navbar |
| `40-*` through `49-*` | Content rendering (markdown, JSON, media, ANSI) |
| `50-*` through `59-*` | State management, routing, data loading |
| `60-*` through `69-*` | Base UI components (`packages/react`), theme |
| `70-*` through `79-*` | Python backend, API |
| `80-*` through `89-*` | Utilities, formatting, dead code |
| `90-*` through `99-*` | Cross-cutting / consistency / verification / indices |

## Severity levels

- **HIGH** — Correctness bug, wrong data shown, crash, security issue
- **MEDIUM** — UX inconsistency, misleading display, silent fallback hiding errors, significant code smell
- **LOW** — Minor stylistic inconsistency, dead code, naming, minor smell
- **INFO** — Observation worth noting, not necessarily a problem
