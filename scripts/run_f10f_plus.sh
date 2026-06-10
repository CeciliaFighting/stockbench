#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="${BASE_DIR:-/mnt/d/intern_life/efunds}"
PYTHON_BIN="${PYTHON_BIN:-$BASE_DIR/stockbench/.venv/bin/python}"
export STOCKBENCH_DATA_CACHE_DIR="${STOCKBENCH_DATA_CACHE_DIR:-$HOME/.cache/stockbench/data-cache}"

START_DATE="${START_DATE:-2025-03-03}"
END_DATE="${END_DATE:-2025-06-30}"
WORKDIR="$BASE_DIR/stockbench-f10f-plus"
RUN_ID="${RUN_ID:-F10F_PLUS_SMART_NT_BAND}"
LOG_FILE="$WORKDIR/storage/logs/${RUN_ID}.log"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[ERROR] PYTHON_BIN is not executable: $PYTHON_BIN" >&2
  exit 1
fi

if [[ ! -d "$WORKDIR" ]]; then
  echo "[ERROR] Missing worktree: $WORKDIR" >&2
  exit 1
fi

mkdir -p "$WORKDIR/storage/logs"
cd "$WORKDIR"

"$PYTHON_BIN" -m stockbench.apps.run_backtest \
  --cfg config.yaml \
  --start "$START_DATE" \
  --end "$END_DATE" \
  --strategy llm_decision \
  --run-id "$RUN_ID" \
  --llm-profile deepseek-v4-flash \
  --use-deepseek \
  --agent-mode dual \
  --data-mode offline_only \
  --no-reflection-agent \
  > "$LOG_FILE" 2>&1 &

echo "[SUCCESS] Started $RUN_ID"
echo "[INFO] PID: $!"
echo "[INFO] Log: $LOG_FILE"
