#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="${BASE_DIR:-/mnt/d/intern_life/efunds}"
PYTHON_BIN="${PYTHON_BIN:-$BASE_DIR/stockbench/.venv/bin/python}"
export STOCKBENCH_DATA_CACHE_DIR="${STOCKBENCH_DATA_CACHE_DIR:-$HOME/.cache/stockbench/data-cache}"

START_DATE="${START_DATE:-2025-03-03}"
END_DATE="${END_DATE:-2025-06-30}"

declare -a EXPERIMENTS=(
  "stockbench-f10b-rebound-context|F10B_REBOUND_CONTEXT_MAIN"
  "stockbench-f10d-confirmed-winner-hold|F10D_CONFIRMED_WINNER_HOLD_SOFT"
)

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[ERROR] PYTHON_BIN is not executable: $PYTHON_BIN" >&2
  exit 1
fi

for item in "${EXPERIMENTS[@]}"; do
  IFS="|" read -r worktree run_id <<< "$item"
  workdir="$BASE_DIR/$worktree"
  log_file="$workdir/storage/logs/${run_id}.log"

  if [[ ! -d "$workdir" ]]; then
    echo "[ERROR] Missing worktree: $workdir" >&2
    exit 1
  fi

  mkdir -p "$workdir/storage/logs"
  echo "[INFO] Starting $run_id in $workdir"
  (
    cd "$workdir"
    "$PYTHON_BIN" -m stockbench.apps.run_backtest \
      --cfg config.yaml \
      --start "$START_DATE" \
      --end "$END_DATE" \
      --strategy llm_decision \
      --run-id "$run_id" \
      --llm-profile deepseek-v4-flash \
      --use-deepseek \
      --agent-mode dual \
      --data-mode offline_only \
      --no-reflection-agent \
      > "$log_file" 2>&1
  ) &
  echo "[INFO] $run_id PID: $!"
  echo "[INFO] Log: $log_file"
done

echo "[SUCCESS] F10 rebound follow-up experiments launched."
echo "[INFO] Check progress with:"
echo "ps -ef | grep -E 'F10B_|F10D_' | grep -v grep"
