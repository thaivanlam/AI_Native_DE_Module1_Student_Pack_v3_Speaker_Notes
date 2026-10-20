#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p "$ROOT/logs"
# Append so reruns on the same day retain the earlier execution logs.
exec >> "$ROOT/logs/pipeline_$(date +%Y%m%d).log" 2>&1
printf '\n[%s] Starting daily pipeline | root=%s\n' "$(date -Iseconds)" "$ROOT"

if [[ -f "$ROOT/.venv/bin/activate" ]]; then
    source "$ROOT/.venv/bin/activate"
elif [[ -f "$ROOT/.venv/Scripts/activate" ]]; then
    # Windows virtual environment, when launched from Git Bash.
    source "$ROOT/.venv/Scripts/activate"
else
    printf 'ERROR: Python virtual environment .venv is missing.\n' >&2
    exit 1
fi

# Replace the shell with Python to preserve its exact exit code.
exec python -m src.pipeline --source both --input-dir data/incremental/day_2026-07-01 --refresh-mart
