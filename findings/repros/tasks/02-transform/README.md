# 02-transform repros

## Standard repros (run via `run.sh`)

`F02.1` `F02.2/F02.3` `F02.4` `F02.5` `F03.4` `F03.5` are plain `@task` files —
regenerate any of them with:

```bash
cd "$(git rev-parse --show-toplevel)"
./findings/repros/run.sh findings/repros/tasks/02-transform/<file>.py 02-transform
```

## Post-processed repros (run as a script)

### F02.12 — unknown event type renders nothing

The Python `Event` union is closed, so a normal task cannot emit an event with
an unknown `event` discriminator. `F02.12_unknown_event_type.py` is therefore a
**standalone script** (not a `@task`) that:

1. runs a tiny mockllm eval to a temp dir,
2. cracks the resulting `.eval` zip open,
3. injects `{"event": "F02_12_unknown_type", ...}` (plus an `info` banner and a
   `logger` marker) into `samples/F02.12_epoch_1.json`,
4. writes `findings/repros/logs/02-transform/F02.12-unknown-event-type.eval`.

Regenerate (idempotent — overwrites any prior `*F02.12*` log):

```bash
cd "$(git rev-parse --show-toplevel)"
env -u UV_EXCLUDE_NEWER -u INSPECT_TELEMETRY -u INSPECT_API_KEY_OVERRIDE -u INSPECT_REQUIRED_HOOKS \
  uv run --frozen python findings/repros/tasks/02-transform/F02.12_unknown_event_type.py
```

Verify:

```bash
uv run --frozen --with playwright python findings/repros/verify/verify_one.py F02.12 --port 7870
```

In `inspect view`: open sample F02.12 → Transcript → switch **Events** filter
to **Debug** → the WARNING marker is immediately followed by STATE UPDATED with
nothing in between. The left-hand outline *does* list `F02_12_unknown_type`,
proving the EventNode exists; `RenderedEventNode → default: return null` just
renders nothing for it.
