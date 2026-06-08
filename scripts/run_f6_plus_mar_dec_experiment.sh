#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="${BASE_DIR:-/mnt/d/intern_life/efunds}"
WORKTREE="${WORKTREE:-$BASE_DIR/stockbench-f6-plus-mar-dec}"
PYTHON_BIN="${PYTHON_BIN:-$BASE_DIR/stockbench/.venv/bin/python}"

RUN_ID="${RUN_ID:-F6_PLUS_MAR_DEC_FULL}"
START_DATE="${START_DATE:-2025-03-03}"
END_DATE="${END_DATE:-2025-12-31}"
DATA_MODE="${DATA_MODE:-auto}"

CACHE_STAMP="$(date +%Y%m%d-%H%M%S)"
export STOCKBENCH_DATA_CACHE_DIR="${F6_PLUS_DATA_CACHE_DIR:-$HOME/.cache/stockbench/data-cache-f6-plus-mar-dec-$CACHE_STAMP}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[ERROR] PYTHON_BIN is not executable: $PYTHON_BIN" >&2
  exit 1
fi

if [[ ! -d "$WORKTREE" ]]; then
  echo "[ERROR] Missing worktree: $WORKTREE" >&2
  exit 1
fi

mkdir -p "$WORKTREE/storage/logs"
LOG_FILE="$WORKTREE/storage/logs/${RUN_ID}.log"

echo "[INFO] Starting $RUN_ID"
echo "[INFO] Worktree: $WORKTREE"
echo "[INFO] Date range: $START_DATE to $END_DATE"
echo "[INFO] Data mode: $DATA_MODE"
echo "[INFO] Fresh data cache: $STOCKBENCH_DATA_CACHE_DIR"
echo "[INFO] Log: $LOG_FILE"

(
  cd "$WORKTREE"
  "$PYTHON_BIN" -m stockbench.apps.run_backtest \
    --cfg config.yaml \
    --start "$START_DATE" \
    --end "$END_DATE" \
    --strategy llm_decision \
    --run-id "$RUN_ID" \
    --llm-profile deepseek-v4-flash \
    --use-deepseek \
    --agent-mode dual \
    --data-mode "$DATA_MODE" \
    --no-reflection-agent \
    > "$LOG_FILE" 2>&1
) &

echo "[SUCCESS] $RUN_ID started with PID: $!"
echo "[INFO] Check progress with:"
echo "ps -ef | grep F6_PLUS_MAR_DEC_FULL | grep -v grep"
echo "tail -f $LOG_FILE"
