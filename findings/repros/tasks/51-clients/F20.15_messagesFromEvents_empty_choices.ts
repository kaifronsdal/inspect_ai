/**
 * Repro for F20.15 — `messagesFromEvents` crashes on `output.choices = []`.
 *
 * Source: src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/messagesFromEvents.ts:30
 *
 * The function dereferences `e.output.choices[0].message` without checking
 * that `choices` is non-empty. A `ModelEvent` with `output.choices = []`
 * (e.g. an aborted/empty completion that didn't set `error`) throws
 * `TypeError: Cannot read properties of undefined (reading 'message')`.
 *
 * (Secondary: line 37 uses `messages.values().toArray()` — an ES2025 iterator
 * helper. Node 24 supports it, so that part won't fail here.)
 *
 * Run:
 *   cd findings/repros/tasks/51-clients
 *   npx --yes tsx F20.15_messagesFromEvents_empty_choices.ts
 */

import { messagesFromEvents } from "../../../../src/inspect_ai/_view/ts-mono/apps/inspect/src/app/samples/messagesFromEvents.ts";

// A minimal ModelEvent shape with empty choices and no error.
// (`error` is falsy so it survives the `.filter((e) => !e.error)` step.)
const events = [
  {
    event: "model" as const,
    error: null,
    input: [{ id: "msg-1", role: "user", content: "hello" }],
    output: {
      choices: [], // ← the trigger
    },
  },
];

console.log("─".repeat(60));
console.log("F20.15 — messagesFromEvents crashes on empty choices[]");
console.log("─".repeat(60));
console.log("Input: 1 ModelEvent with output.choices = [] and error = null");
console.log("Expected: returns the input messages without throwing");
console.log();

let threw: unknown = undefined;
let result: unknown = undefined;
try {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  result = messagesFromEvents(events as any);
} catch (e) {
  threw = e;
}

if (threw === undefined) {
  console.log("Actual:   returned", JSON.stringify(result));
  console.log();
  console.log("PASS — finding is a FALSE POSITIVE (or has been fixed).");
  process.exit(0);
} else {
  const msg = threw instanceof Error ? threw.message : String(threw);
  console.log("Actual:   THREW →", (threw as Error)?.constructor?.name, ":", msg);
  console.log();
  console.log("FAIL — BUG CONFIRMED: empty choices[] crashes the message extractor.");
  process.exit(1);
}
