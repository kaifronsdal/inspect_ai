#!/usr/bin/env bash
# Run every standalone TS/Node repro in this directory.
# Exit 0 if all PASS (false positives / fixed); exit 1 if any FAIL (bug confirmed).
set -uo pipefail
cd "$(dirname "$0")"

TSX="npx --yes tsx"
fail=0

run() {
  echo
  echo "━━━ $1 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  if [[ "$1" == *.mjs ]]; then
    node "$1" || fail=1
  else
    $TSX "$1" || fail=1
  fi
}

run F50.1_isLargeSample_always_true.ts
run F51.1_pending_log_promise_race.mjs
run F20.15_messagesFromEvents_empty_choices.ts
run F40.6_renderer_mutates_entry.mjs
run F80.1_parseLogFileName_invalid_date.ts

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [[ $fail -eq 0 ]]; then
  echo "ALL PASS — no bugs reproduced (all false-positive or fixed)."
else
  echo "SOME FAIL — one or more bugs confirmed (see output above)."
fi
exit $fail
