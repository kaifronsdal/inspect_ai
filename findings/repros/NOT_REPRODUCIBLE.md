# Findings not reproducible via a `.eval` file

A `.eval` file is a static snapshot of an eval run. It cannot exercise the
HTTP layer, browser storage, keyboard handling, or cross-navigation state. For
findings in those categories, record them here instead of forcing a contrived
repro. See [`HOWTO.md` §9](HOWTO.md#9-when-a-finding-is-not-reproducible-via-eval)
for the full criteria.

If a finding is **partially** reproducible, build the partial `.eval` repro and
note the gap in its `bug_sample(extra=...)` — do **not** list it here.

> **2026-04-27 update:** all five findings previously listed here
> (F02.12, F20.15, F31.13, F40.6, F80.1) now have **non-`.eval` repros** —
> post-processed `.eval` scripts, standalone `tsx`/`node` scripts, or pytest
> tests. See [`INVENTORY.md` § Non-.eval repros](INVENTORY.md#non-eval-repros)
> and [`README.md` § Non-.eval repros](README.md#non-eval-repros) for run
> commands.
>
> Performance and race-condition findings that require a profiler or
> fake-timer harness (and so have **no executable repro**) are documented in
> [`DOCUMENTED_ONLY.md`](DOCUMENTED_ONLY.md) instead.

| Finding ID | Reason | Alternative verification |
|------------|--------|--------------------------|
| — | *(none — table retained for future entries)* | — |
