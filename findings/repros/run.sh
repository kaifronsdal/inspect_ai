#!/usr/bin/env bash
# Thin wrapper around `inspect eval` that clears AISI-platform env vars which
# break the local editable install (aisitools is not in this venv) and the
# global UV_EXCLUDE_NEWER which breaks dependency resolution.
#
# Usage:
#   ./findings/repros/run.sh <task.py> <log-subdir> [extra inspect-eval args...]
#
# Example:
#   ./findings/repros/run.sh \
#       findings/repros/tasks/example/F01.3_score_edit_unchanged_sentinel.py \
#       example
#
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

TASK="${1:?usage: run.sh <task.py> <log-subdir> [extra args...]}"
SUBDIR="${2:?usage: run.sh <task.py> <log-subdir> [extra args...]}"
shift 2

exec env \
  -u UV_EXCLUDE_NEWER \
  -u INSPECT_TELEMETRY \
  -u INSPECT_API_KEY_OVERRIDE \
  -u INSPECT_REQUIRED_HOOKS \
  uv run --frozen inspect eval "$TASK" \
    --model mockllm/model \
    --log-dir "findings/repros/logs/$SUBDIR" \
    --log-format eval \
    --display plain \
    "$@"
