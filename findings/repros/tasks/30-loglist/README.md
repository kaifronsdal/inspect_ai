# 30-loglist repros

## Standard repros (run via `run.sh`)

`F30.1` `F30.2` `F30.4` `F31.1` `F31.2` `F31.3` are plain `@task` files —
regenerate any of them with:

```bash
cd "$(git rev-parse --show-toplevel)"
./findings/repros/run.sh findings/repros/tasks/30-loglist/<file>.py 30-loglist
```

## Post-processed repros (run as a script)

### F31.13 — missing `started_at` → "1970-01-01"

The recorder unconditionally sets `stats.started_at` on a completed eval, so a
normal task cannot produce a log with the field empty. The schema, however,
declares it as `string | ""`, and `TaskTab.tsx` reads it as
`new Date(evalStats?.started_at || 0)`. `F31.13_missing_started_at.py` is a
**standalone script** that:

1. runs a tiny mockllm eval to a temp dir,
2. rewrites `header.json` so `stats.started_at = ""` and
   `stats.completed_at = ""`,
3. writes `findings/repros/logs/30-loglist/F31.13-missing-started-at.eval`.

Regenerate (idempotent — overwrites any prior `*F31.13*` log):

```bash
cd "$(git rev-parse --show-toplevel)"
env -u UV_EXCLUDE_NEWER -u INSPECT_TELEMETRY -u INSPECT_API_KEY_OVERRIDE -u INSPECT_REQUIRED_HOOKS \
  uv run --frozen python findings/repros/tasks/30-loglist/F31.13_missing_started_at.py
```

Verify:

```bash
uv run --frozen --with playwright python findings/repros/verify/verify_one.py F31.13 --port 7871
```

In `inspect view`: open the log → **Task** tab → Task Info card shows
`START 1970-01-01 00:00:00` / `END 1970-01-01 00:00:00` / `DURATION 0.0 sec`.
Bonus: the navbar header **DURATION** column shows
`NaN days NaN hr NaN min NaN sec` (separate codepath, same root cause).
