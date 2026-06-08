#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="${BASE_DIR:-/mnt/d/intern_life/efunds}"
PYTHON_BIN="${PYTHON_BIN:-$BASE_DIR/stockbench/.venv/bin/python}"

START_DATE="${START_DATE:-2025-03-03}"
END_DATE="${END_DATE:-2025-12-31}"
DATA_MODE="${DATA_MODE:-auto}"

if [[ -z "${STOCKBENCH_DATA_CACHE_DIR:-}" ]]; then
  CACHE_STAMP="$(date +%Y%m%d-%H%M%S)"
  export STOCKBENCH_DATA_CACHE_DIR="$HOME/.cache/stockbench/data-cache-f8-mar-dec-$CACHE_STAMP"
fi

declare -a EXPERIMENTS=(
  "stockbench-f8a-sell-discipline-mar-dec|F8A_SELL_DISCIPLINE_MAR_DEC_FULL"
  "stockbench-f8b-reduce-only-risk-review-mar-dec|F8B_REDUCE_ONLY_RISK_REVIEW_MAR_DEC_FULL"
  "stockbench-f8c-rebound-catchup-tag-mar-dec|F8C_REBOUND_CATCHUP_TAG_MAR_DEC_FULL"
  "stockbench-f8d-quality-trap-cap-mar-dec|F8D_QUALITY_TRAP_CAP_MAR_DEC_FULL"
)

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[ERROR] PYTHON_BIN is not executable: $PYTHON_BIN" >&2
  exit 1
fi

echo "[INFO] Date range: $START_DATE to $END_DATE"
echo "[INFO] Data mode: $DATA_MODE"
echo "[INFO] Fresh data cache: $STOCKBENCH_DATA_CACHE_DIR"

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
      --data-mode "$DATA_MODE" \
      --no-reflection-agent \
      > "$log_file" 2>&1
  ) &
  echo "[INFO] $run_id PID: $!"
  echo "[INFO] Log: $log_file"
done

echo "[SUCCESS] All four F8 Mar-Dec experiments have been started."
echo "[INFO] Check progress with:"
echo "ps -ef | grep -E 'F8A_|F8B_|F8C_|F8D_' | grep MAR_DEC | grep -v grep"
