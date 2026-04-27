// Stub for `@tsmono/inspect-common/types` — types are erased at runtime by
// tsx/esbuild, but the module specifier still has to resolve. This file
// provides an empty module so the import succeeds.
export {};
// Re-declare just enough that `import { X } from "..."` (non-`import type`)
// doesn't trip esbuild's "no matching export" check.
export type EvalSample = unknown;
export type ChatMessage = unknown;
export type ChatMessageAssistant = unknown;
export type ChatMessageSystem = unknown;
export type ChatMessageTool = unknown;
export type ChatMessageUser = unknown;
export type Event = unknown;
export type LogFilesResponse = unknown;
