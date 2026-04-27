/**
 * Repro for F40.6 — `RenderedContent` Number/Boolean renderers mutate
 * `entry.value` in place.
 *
 * Source: src/inspect_ai/_view/ts-mono/packages/inspect-components/src/content/RenderedContent.tsx:163,177
 *
 *   Boolean.render = (id, entry, options) => {
 *     entry.value = entry.value.toString();      // ← mutates caller's object
 *     return contentRenderers.String?.render(id, entry, options) || {...};
 *   }
 *   Number.render = (id, entry, options) => {
 *     entry.value = formatNumber(entry.value);   // ← mutates caller's object
 *     return contentRenderers.String?.render(id, entry, options) || {...};
 *   }
 *
 * On a second render of the same entry object (StrictMode double-render, or
 * two RenderedContent instances sharing one record), `42` has become `"42"`,
 * so `typeof === "number"` is false → falls to the String renderer and
 * `formatNumber` is skipped. Also breaks parent memoization.
 *
 * `RenderedContent.tsx` is JSX with hard deps on react/clsx/json5/@tsmono/react,
 * none of which are installed, so this repro:
 *   1. Asserts the mutating assignments are still present in the source.
 *   2. Reproduces the renderer bodies verbatim (sans JSX) and demonstrates
 *      the mutation + the second-render type drift.
 *
 * Run:
 *   cd findings/repros/tasks/51-clients
 *   node F40.6_renderer_mutates_entry.mjs
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC = join(
  HERE,
  "../../../../src/inspect_ai/_view/ts-mono/packages/inspect-components/src/content/RenderedContent.tsx"
);

// ─── 1. Source-pattern guard ────────────────────────────────────────────────
const src = readFileSync(SRC, "utf8");
const mutBool = "entry.value = entry.value.toString();";
const mutNum = "entry.value = formatNumber(entry.value);";
const boolPresent = src.includes(mutBool);
const numPresent = src.includes(mutNum);

console.log("─".repeat(60));
console.log("F40.6 — Number/Boolean renderers mutate entry.value in place");
console.log("─".repeat(60));
console.log("Source check (RenderedContent.tsx):");
console.log("  '" + mutBool + "' →", boolPresent ? "PRESENT" : "absent");
console.log("  '" + mutNum + "'  →", numPresent ? "PRESENT" : "absent");
console.log();

if (!boolPresent && !numPresent) {
  console.log("PASS — finding may be FIXED (mutation pattern not found in source).");
  process.exit(0);
}

// ─── 2. Verbatim renderer bodies (JSX → plain return) ───────────────────────
// formatNumber from @tsmono/util uses `navigator.language`; we use a fixed
// locale here since the bug is the *mutation*, not the format.
const formatNumber = (n) =>
  n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 5 });

const contentRenderers = {
  String: {
    canRender: (entry) => typeof entry.value === "string",
    render: (_id, entry /*, options*/) => ({ rendered: entry.value.trim() }),
  },
  Boolean: {
    canRender: (entry) => typeof entry.value === "boolean",
    render: (id, entry, options) => {
      entry.value = entry.value.toString(); // ← line 163 verbatim
      return contentRenderers.String.render(id, entry, options);
    },
  },
  Number: {
    canRender: (entry) => typeof entry.value === "number",
    render: (id, entry, options) => {
      entry.value = formatNumber(entry.value); // ← line 177 verbatim
      return contentRenderers.String.render(id, entry, options);
    },
  },
};

// Dispatcher matching RenderedContent.tsx:59-73 — find first canRender match.
const dispatch = (id, entry) => {
  const r = Object.values(contentRenderers).find((r) => r.canRender(entry));
  return { renderer: r, out: r?.render(id, entry, {}) };
};

// ─── 3. Test: shared entry object, two renders ──────────────────────────────
const numEntry = { name: "score", value: 1234.5678 };
const numBefore = { value: numEntry.value, type: typeof numEntry.value };

const r1 = dispatch("id", numEntry);
const numAfter1 = { value: numEntry.value, type: typeof numEntry.value };
const r2 = dispatch("id", numEntry); // second render of SAME object
const numAfter2 = { value: numEntry.value, type: typeof numEntry.value };

const boolEntry = { name: "passed", value: true };
const boolBefore = { value: boolEntry.value, type: typeof boolEntry.value };
dispatch("id", boolEntry);
const boolAfter = { value: boolEntry.value, type: typeof boolEntry.value };

console.log("Number entry (shared object, rendered twice):");
console.log("  before render 1:", JSON.stringify(numBefore));
console.log("  after  render 1:", JSON.stringify(numAfter1), "← MUTATED");
console.log(
  "  render 1 hit:   ",
  r1.renderer === contentRenderers.Number ? "Number renderer" : "String renderer",
  "→",
  JSON.stringify(r1.out?.rendered)
);
console.log(
  "  render 2 hit:   ",
  r2.renderer === contentRenderers.Number
    ? "Number renderer"
    : "String renderer (formatNumber SKIPPED)",
  "→",
  JSON.stringify(r2.out?.rendered)
);
console.log();
console.log("Boolean entry:");
console.log("  before:", JSON.stringify(boolBefore));
console.log("  after: ", JSON.stringify(boolAfter), "← MUTATED");
console.log();

const numMutated = numAfter1.type !== "number";
const boolMutated = boolAfter.type !== "boolean";
const secondRenderDrifted = r2.renderer !== contentRenderers.Number;

console.log("Expected: entry.value unchanged after render (no input mutation)");
console.log(
  "Actual:   Number entry.value is now",
  JSON.stringify(numAfter1.value),
  `(${numAfter1.type});`,
  "Boolean entry.value is now",
  JSON.stringify(boolAfter.value),
  `(${boolAfter.type})`
);
console.log();

if (!numMutated && !boolMutated) {
  console.log("PASS — finding is a FALSE POSITIVE (or has been fixed).");
  process.exit(0);
} else {
  console.log("FAIL — BUG CONFIRMED: render() mutated its input.");
  if (secondRenderDrifted) {
    console.log(
      "       Second render of the same object hit the String renderer, not Number."
    );
  }
  process.exit(1);
}
