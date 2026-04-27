/**
 * Repro for F80.1 — `parseLogFileName` always produces `Invalid Date`.
 *
 * Source: src/inspect_ai/_view/ts-mono/apps/inspect/src/utils/evallog.ts:26
 *
 * Inspect log filenames use a filesystem-safe timestamp format with dashes
 * in place of colons (e.g. `2024-01-15T14-30-00+00-00`). The regex captures
 * this verbatim and feeds it to `Date.parse()`, which returns `NaN` because
 * `T14-30-00+00-00` is not valid ISO 8601. `new Date(NaN)` is an Invalid Date.
 *
 * Run:
 *   cd findings/repros/tasks/51-clients
 *   npx --yes tsx F80.1_parseLogFileName_invalid_date.ts
 */

import { parseLogFileName } from "../../../../src/inspect_ai/_view/ts-mono/apps/inspect/src/utils/evallog.ts";

// A real, conforming inspect log filename (matches kLogFilePattern).
const filename = "2024-01-15T14-30-00+00-00_my-task_a1B2c3D4e5.eval";

const parsed = parseLogFileName(filename);

const ts = parsed.timestamp;
const isDate = ts instanceof Date;
const isValid = isDate && !Number.isNaN(ts.getTime());

console.log("─".repeat(60));
console.log("F80.1 — parseLogFileName produces Invalid Date");
console.log("─".repeat(60));
console.log("Input:           ", filename);
console.log("Parsed .name:    ", parsed.name);
console.log("Parsed .taskId:  ", parsed.taskId);
console.log("Parsed .timestamp:", ts);
console.log("  instanceof Date:", isDate);
console.log("  getTime():      ", isDate ? ts.getTime() : "(n/a)");
console.log();
console.log(
  "Expected: a valid Date (≈ 2024-01-15T14:30:00Z → getTime()=1705329000000)"
);
console.log(
  "Actual:  ",
  isValid ? `valid Date (${ts.toISOString()})` : "Invalid Date (getTime() is NaN)"
);
console.log();

if (isValid) {
  console.log("PASS — finding is a FALSE POSITIVE (or has been fixed).");
  process.exit(0);
} else {
  console.log("FAIL — BUG CONFIRMED: timestamp is Invalid Date.");
  console.log(
    "       Type signature promises `Date | undefined`, never an invalid Date."
  );
  process.exit(1);
}
