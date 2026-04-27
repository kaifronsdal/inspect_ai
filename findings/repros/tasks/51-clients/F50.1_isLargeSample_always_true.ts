/**
 * Repro for F50.1 — `isLargeSample()` always returns `true`.
 *
 * Source: src/inspect_ai/_view/ts-mono/apps/inspect/src/state/store_filter.ts:19-31
 *
 * The function checks store-key count (> 5000) and estimated message size
 * (> 250000) and returns `true` if either threshold is exceeded — but then
 * unconditionally returns `true` at the end. The final line should be
 * `return false`.
 *
 * Run:
 *   cd findings/repros/tasks/51-clients
 *   npx --yes tsx F50.1_isLargeSample_always_true.ts
 */

// `store_filter.ts` imports:
//   - { EvalSample }      from "@tsmono/inspect-common/types"  (type-only → stub)
//   - { estimateSize }    from "@tsmono/util"                  (→ stub re-exports real fn)
//   - { PersistedState }  from "./store"                       (type-only → erased by tsx)
//
// tsx (esbuild) erases imports that are only used in type position, so the
// `./store` import disappears at runtime. The `@tsmono/*` specifiers are
// satisfied via tsconfig.json `paths` → `_stubs/`.

import { isLargeSample } from "../../../../src/inspect_ai/_view/ts-mono/apps/inspect/src/state/store_filter.ts";

// A trivially tiny sample: empty store, one short message.
// countKeys({}) === 0; estimateSize([{...12 chars...}]) ≈ 30.
// Both thresholds (5000 keys, 250000 bytes) are wildly under-shot.
const tinySample = {
  store: {},
  messages: [{ role: "user", content: "hi" }],
} as Parameters<typeof isLargeSample>[0];

const result = isLargeSample(tinySample);

console.log("─".repeat(60));
console.log("F50.1 — isLargeSample() always returns true");
console.log("─".repeat(60));
console.log("Input:    tiny sample (store={}, 1 message of 2 chars)");
console.log("Expected: false   (sample is well under both thresholds)");
console.log("Actual:  ", result);
console.log();

if (result === false) {
  console.log("PASS — finding is a FALSE POSITIVE (or has been fixed).");
  process.exit(0);
} else {
  console.log("FAIL — BUG CONFIRMED: tiny sample reported as large.");
  console.log("       Every sample is sent to the non-reactive ref store.");
  process.exit(1);
}
