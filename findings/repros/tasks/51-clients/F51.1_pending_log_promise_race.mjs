/**
 * Repro for F51.1 — `pending_log_promise` returns wrong log under concurrent
 * requests.
 *
 * Source: src/inspect_ai/_view/ts-mono/apps/inspect/src/client/api/client-api.ts:98-127
 *
 * `get_log()` deduplicates in-flight fetches via a single closure-scoped
 * `pending_log_promise`, but the dedup check does not compare `log_file`.
 * If caller A requests "a.json" and (before it resolves) caller B requests
 * "b.json", B is handed A's promise and receives A's contents.
 *
 * `client-api.ts` cannot be imported directly without `node_modules`
 * (transitively pulls fflate / fzstd / Worker via remoteLogFile). So this
 * repro:
 *   1. Asserts the buggy pattern is still present in the source file (so the
 *      copy below can't drift silently).
 *   2. Reproduces the `get_log` closure verbatim against a mocked `api`.
 *
 * Run:
 *   cd findings/repros/tasks/51-clients
 *   node F51.1_pending_log_promise_race.mjs
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC = join(
  HERE,
  "../../../../src/inspect_ai/_view/ts-mono/apps/inspect/src/client/api/client-api.ts"
);

// ─── 1. Source-pattern guard ────────────────────────────────────────────────
// If somebody fixes the source (e.g. by tracking the in-flight log_file) this
// repro should not silently keep "confirming" a bug that no longer exists.
const src = readFileSync(SRC, "utf8");
const guardA = "if (pending_log_promise) {";
const guardB = "return pending_log_promise;";
if (!src.includes(guardA) || !src.includes(guardB)) {
  console.log("─".repeat(60));
  console.log("F51.1 — pending_log_promise race");
  console.log("─".repeat(60));
  console.log(
    "NOTE: source no longer contains the unguarded `if (pending_log_promise)`\n" +
      "      pattern. This repro's verbatim copy is stale; re-check by hand."
  );
  console.log();
  console.log("PASS — finding may be FIXED (source pattern not found).");
  process.exit(0);
}

// ─── 2. Verbatim extract of get_log (client-api.ts:98-127) ──────────────────
// Only change: `api` is a parameter instead of an outer-scope capture.
function makeGetLog(api) {
  let current_log = undefined;
  let current_path = undefined;
  let pending_log_promise = null;

  const get_log = async (log_file, cached = false) => {
    // If the requested log is different or no cached log exists, start fetching
    if (!cached || log_file !== current_path || !current_log) {
      // If there's already a pending fetch, return the same promise
      if (pending_log_promise) {
        return pending_log_promise;
      }

      // Otherwise, create a new promise for fetching the log
      pending_log_promise = api
        .get_log_contents(log_file, 100)
        .then((log) => {
          current_log = log;
          current_path = log_file;
          pending_log_promise = null;
          return log;
        })
        .catch((err) => {
          pending_log_promise = null;
          throw err;
        });

      return pending_log_promise;
    }
    return current_log;
  };
  return get_log;
}

// ─── 3. Mock api + concurrent calls ─────────────────────────────────────────
const calls = [];
const api = {
  get_log_contents: (log_file /*, headerOnly */) => {
    calls.push(log_file);
    // Resolve on a later microtask so both get_log() calls land while the
    // first fetch is still pending.
    return new Promise((resolve) =>
      setTimeout(() => resolve({ parsed: { path: log_file } }), 10)
    );
  },
};

const get_log = makeGetLog(api);

const pA = get_log("a.json");
const pB = get_log("b.json"); // fired before pA resolves

const [resA, resB] = await Promise.all([pA, pB]);

console.log("─".repeat(60));
console.log("F51.1 — pending_log_promise returns wrong log on concurrent calls");
console.log("─".repeat(60));
console.log("Concurrent calls:  get_log('a.json'), get_log('b.json')");
console.log("api.get_log_contents called with:", JSON.stringify(calls));
console.log();
console.log("Expected: A → {path:'a.json'},  B → {path:'b.json'}");
console.log(
  "Actual:   A →",
  JSON.stringify(resA?.parsed),
  ",  B →",
  JSON.stringify(resB?.parsed)
);
console.log();

const aOK = resA?.parsed?.path === "a.json";
const bOK = resB?.parsed?.path === "b.json";

if (aOK && bOK) {
  console.log("PASS — finding is a FALSE POSITIVE (or has been fixed).");
  process.exit(0);
} else {
  console.log(
    "FAIL — BUG CONFIRMED: caller B received caller A's log contents."
  );
  console.log(
    "       (api was only invoked for",
    JSON.stringify(calls),
    "— B's request was swallowed.)"
  );
  process.exit(1);
}
