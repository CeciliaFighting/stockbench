#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="${BASE_DIR:-/mnt/d/intern_life/efunds}"
PYTHON_BIN="${PYTHON_BIN:-$BASE_DIR/stockbench/.venv/bin/python}"
export STOCKBENCH_DATA_CACHE_DIR="${STOCKBENCH_DATA_CACHE_DIR:-$HOME/.cache/stockbench/data-cache}"

START_DATE="${START_DATE:-2025-03-03}"
END_DATE="${END_DATE:-2025-06-30}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[ERROR] PYTHON_BIN is not executable: $PYTHON_BIN" >&2
  exit 1
fi

diag_dir="$BASE_DIR/stockbench-f10a-rebound-diagnostic"
if [[ ! -d "$diag_dir" ]]; then
  echo "[ERROR] Missing F10A diagnostic worktree: $diag_dir" >&2
  exit 1
fi

echo "[INFO] Running F10A rebound diagnostic in $diag_dir"
(
  cd "$diag_dir"
  "$PYTHON_BIN" scripts/f10a_rebound_diagnostic.py \
    --cfg config.yaml \
    --start "$START_DATE" \
    --end "$END_DATE" \
    --targets BA,HON,IBM,MSFT,GS
)

declare -a EXPERIMENTS=(
  "stockbench-f10e-defensive-lagging-no-add|F10E_DEFENSIVE_LAGGING_NO_ADD"
  "stockbench-f10f-nt-band-lite|F10F_NT_BAND_LITE_ON_F6"
  "stockbench-f10g-extreme-risk-budget|F10G_EXTREME_RISK_BUDGET"
)

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

echo "[SUCCESS] F10 first batch launched."
echo "[INFO] Check progress with:"
echo "ps -ef | grep -E 'F10E_|F10F_|F10G_' | grep -v grep"
