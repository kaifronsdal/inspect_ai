// Stub for `@tsmono/util` — re-exports only the pure-JS bits needed by the
// repro targets, bypassing the package barrel (which pulls in apache-arrow,
// arquero, lz4js etc. that aren't installed).
//
// Each export below points at the *real* source file, so the function under
// test is the actual implementation, not a copy.

export { estimateSize } from "../../../../../src/inspect_ai/_view/ts-mono/packages/util/src/json.ts";
export { filename } from "../../../../../src/inspect_ai/_view/ts-mono/packages/util/src/path.ts";
export { formatNumber } from "../../../../../src/inspect_ai/_view/ts-mono/packages/util/src/format.ts";
