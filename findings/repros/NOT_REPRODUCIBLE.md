# Findings not reproducible via a `.eval` file

A `.eval` file is a static snapshot of an eval run. It cannot exercise the
HTTP layer, browser storage, keyboard handling, or cross-navigation state. For
findings in those categories, record them here instead of forcing a contrived
repro. See [`HOWTO.md` §9](HOWTO.md#9-when-a-finding-is-not-reproducible-via-eval)
for the full criteria.

If a finding is **partially** reproducible, build the partial `.eval` repro and
note the gap in its `bug_sample(extra=...)` — do **not** list it here.

| Finding ID | Reason | Alternative verification |
|------------|--------|--------------------------|
| F02.12 | `Event` is a closed pydantic discriminated union — a Task cannot emit an event whose `event` field is outside that union, so a `.eval` produced by `inspect eval` can never contain an "unknown" event type. Triggering the `default: return null` branch requires hand-editing the `.eval` zip or a future schema addition. | Add a `satisfies never` exhaustiveness check in `TranscriptVirtualList.tsx:248`; or hex-edit a sample's events JSON inside a `.eval` to insert `{"event":"bogus",...}`. |
| F80.1 | **Latent** — `parseLogFileName().timestamp` is computed but never displayed: the only caller (`log-list/grid/columns/hooks.tsx:125`) reads only `.name`. The log-list "Created" column is fed from the log header's `eval.created` field, not the filename parse, so no `Invalid Date` surfaces in the UI regardless of `.eval` content. | Node REPL: `Date.parse("2024-01-01T12-34-56+00-00")` → `NaN`. Unit-test `parseLogFileName` directly. |
| F31.13 | Requires `evalStats.started_at` to be empty/missing → only happens for `status="started"` (in-progress / interrupted) logs. A completed mockllm run always populates `started_at` unconditionally (`_eval/task/run.py:226`); a scripted run cannot cleanly produce a `started` log without killing the process mid-write. | Open a `.eval` from a still-running eval (or strip `stats` from a log header via `read_eval_log`/`write_eval_log`), then check Task tab → Start row shows "Jan 1, 1970". |
| F40.6 | Prop-mutation bug (`entry.value = entry.value.toString()`) is a React render-time side effect; only observable via strict-mode double-render or two `RenderedContent` instances sharing one JS object reference. A `.eval` file cannot encode "render this entry twice with the same object identity" — the log just contains data. | Unit test: `const e = {name:'n', value: 42}; render(<RenderedContent entry={e}/>); expect(e.value).toBe(42)` — currently fails (`e.value === "42"`). |
| F20.15 | `messagesFromEvents()` is only invoked from `SampleDisplay.tsx:147` when `sample?.messages` is absent **and** `runningSampleData` is set — i.e. the live-streaming path while an eval is *running*. A completed `.eval` always has `sample.messages` populated, so the `e.output.choices[0].message` crash on empty `choices` is unreachable from a static log. | Unit test in `messagesFromEvents.test.ts` feeding a `ModelEvent` with `output.choices: []`; or open the viewer against a *currently-running* eval whose model returns `choices=[]` (stop reason `max_tokens` w/ no content). |
|            |        |                          |
