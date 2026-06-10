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

run_one stockbench-f11f-v2-reliability-haircut F11F_v2_FUNDAMENTAL_RELIABILITY_HAIRCUT_ONLY
run_one stockbench-f11f-v2-prompt-warning F11F_v2_PROMPT_WARNING_ONLY
run_one stockbench-f11k-v3-loser-cooldown F11K_v3_LOSER_COOLDOWN_HAIRCUT_ONLY
run_one stockbench-f11k-v3-prompt-warning F11K_v3_PROMPT_WARNING_ONLY
run_one stockbench-f11g-v2-signal-conflict F11G_v2_SIGNAL_CONFLICT_HAIRCUT_ONLY
run_one stockbench-f11j-v2-crowding-loser F11J_v2_CROWDING_LOSER_ADD_ONLY
run_one stockbench-f11l-v2-weekly-throttle F11L_v2_SOFT_WEEKLY_BUY_ADD_THROTTLE
run_one stockbench-f11e-v2-news-dryrun F11E_v2_NEWS_PRICE_CONFLICT_DRYRUN
run_one stockbench-f11c-v2-memory-dryrun F11C_v2_BAD_ENTRY_MEMORY_DRYRUN
run_one stockbench-f11-combo-v1 F11_COMBO_v1_F11Fv2_F11Kv3_F11Gv2

echo "All F11 final-batch jobs launched."
