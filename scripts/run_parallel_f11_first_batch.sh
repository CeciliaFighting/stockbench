#!/usr/bin/env bash
set -euo pipefail

BASE=${BASE:-/mnt/d/intern_life/efunds}
PYTHON_BIN=${PYTHON_BIN:-$BASE/stockbench/.venv/bin/python}
export STOCKBENCH_DATA_CACHE_DIR="${STOCKBENCH_DATA_CACHE_DIR:-$HOME/.cache/stockbench/data-cache}"

START_DATE=${START_DATE:-2025-03-03}
END_DATE=${END_DATE:-2025-06-30}
LLM_PROFILE=${LLM_PROFILE:-deepseek-v4-flash}

run_one() {
  local worktree="$1"
  local run_id="$2"
  local wt="$BASE/$worktree"
  local log="$wt/storage/logs/$run_id.log"

  mkdir -p "$wt/storage/logs"
  cd "$wt"
  echo "Starting $run_id in $wt"
  "$PYTHON_BIN" -m stockbench.apps.run_backtest \
    --cfg config.yaml \
    --start "$START_DATE" \
    --end "$END_DATE" \
    --strategy llm_decision \
    --run-id "$run_id" \
    --llm-profile "$LLM_PROFILE" \
    --use-deepseek \
    --agent-mode dual \
    --data-mode offline_only \
    --no-reflection-agent \
    > "$log" 2>&1 &
  echo "  pid=$! log=$log"
}

run_one stockbench-f11h-rel-strength F11H_I5_UNIVERSE_RELATIVE_STRENGTH_CONTEXT
run_one stockbench-f11f-fundamental-reliability F11F_I3_FUNDAMENTAL_RELIABILITY_TAG
run_one stockbench-f11m-drawdown-context F11M_R6_DRAWDOWN_CONTEXT_PROMPT
run_one stockbench-f11i-confidence-sizing F11I_R2_CONFIDENCE_WEIGHTED_SIZING
run_one stockbench-f11k-state-cooldown F11K_R4_STATE_DEPENDENT_COOLDOWN
run_one stockbench-f11n-winner-friction F11N_R7_SOFT_WINNER_HOLDING_FRICTION

echo "All F11 first-batch jobs launched."
