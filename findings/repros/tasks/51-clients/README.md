# Standalone Node/TS repros — pure-function frontend bugs

These five findings are unit-level bugs in pure functions inside the
`ts-mono` viewer codebase. They cannot be demonstrated via a `.eval` log file
(the bug is in code that never runs against log *content*), so each is
reproduced by a standalone script that exercises the function directly.

## Prerequisites

- **Node ≥ 22** (tested on v24.14.0). No `pnpm install` required.
- `npx tsx` is fetched on demand for the `.ts` repros — first run may take a
  few seconds.

## Run

```bash
cd findings/repros/tasks/51-clients
bash run-all.sh
```

or individually:

```bash
cd findings/repros/tasks/51-clients
npx --yes tsx F50.1_isLargeSample_always_true.ts
node          F51.1_pending_log_promise_race.mjs
npx --yes tsx F20.15_messagesFromEvents_empty_choices.ts
node          F40.6_renderer_mutates_entry.mjs
npx --yes tsx F80.1_parseLogFileName_invalid_date.ts
```

Each script prints **expected vs actual** and exits:

- `exit 0` / `PASS` → finding is a false positive, or the bug has been fixed.
- `exit 1` / `FAIL` → **bug confirmed**.

## How source is loaded

The `.ts` repros import the **real source file** under
`src/inspect_ai/_view/ts-mono/...` directly via `tsx`. The monorepo's
`@tsmono/*` package specifiers are redirected to lightweight stubs via
`tsconfig.json` `paths` (see `_stubs/`) — the stubs re-export only the
zero-dependency util functions actually needed (`estimateSize`, `filename`),
bypassing the full `@tsmono/util` barrel which would pull in `apache-arrow`,
`arquero`, `lz4js` etc.

The two `.mjs` repros (F51.1, F40.6) target source files whose transitive
runtime dependency graph is too heavy to load without `node_modules`
(`client-api.ts` → `remoteLogFile` → `fflate`/`fzstd`/`Worker`;
`RenderedContent.tsx` → `react`/`clsx`/`json5`). Those repros instead:

1. **Read the real source file** and assert the buggy line is still present
   (so the repro can't silently drift from the codebase).
2. Reproduce the buggy function body **verbatim** (sans JSX / heavy imports)
   and exercise it.

If step 1's pattern check fails, the script reports `PASS — source pattern not
found` so a fix is detected.

## Results (as of 2026-04-27)

| ID | File | Result | Actual vs Expected |
|---|---|---|---|
| F50.1 | `F50.1_isLargeSample_always_true.ts` | **CONFIRMED** | `isLargeSample({store:{}, messages:[tiny]})` → `true`; expected `false` |
| F51.1 | `F51.1_pending_log_promise_race.mjs` | **CONFIRMED** | concurrent `get_log("a")`/`get_log("b")` → both resolve to `a`'s contents; api only called once |
| F20.15 | `F20.15_messagesFromEvents_empty_choices.ts` | **CONFIRMED** | `ModelEvent` with `output.choices=[]` → `TypeError: Cannot read properties of undefined (reading 'message')` |
| F40.6 | `F40.6_renderer_mutates_entry.mjs` | **CONFIRMED** | after `Number.render(entry)`, `entry.value` mutated `1234.5678 → "1,234.5678"`; second render hits String path |
| F80.1 | `F80.1_parseLogFileName_invalid_date.ts` | **CONFIRMED** | `"2024-01-15T14-30-00+00-00_task_hash.eval"` → `.timestamp` is `Invalid Date` (`getTime()` is `NaN`) |

## Files

```
51-clients/
├── README.md                                   ← this file
├── run-all.sh                                  ← runs all five
├── tsconfig.json                               ← @tsmono/* → _stubs/ path map for tsx
├── _stubs/
│   ├── tsmono-util.ts                          ← re-exports real estimateSize, filename, formatNumber
│   ├── tsmono-inspect-common-types.ts          ← empty type-only module
│   └── empty.ts                                ← catch-all empty module
├── F50.1_isLargeSample_always_true.ts          ← imports real store_filter.ts
├── F51.1_pending_log_promise_race.mjs          ← verbatim extract + source-guard
├── F20.15_messagesFromEvents_empty_choices.ts  ← imports real messagesFromEvents.ts
├── F40.6_renderer_mutates_entry.mjs            ← verbatim extract + source-guard
└── F80.1_parseLogFileName_invalid_date.ts      ← imports real evallog.ts
```
