#!/usr/bin/env bash
set -euo pipefail

BASE=${BASE:-/mnt/d/intern_life/efunds}
MAIN=${MAIN:-$BASE/stockbench}
BASE_CFG=${BASE_CFG:-$BASE/stockbench-f6-plus-mar-dec/config.yaml}

cd "$MAIN"

ITEMS=(
  "stockbench-f11f-v2-reliability-haircut|experiment/f11f-v2-reliability-haircut|F11F_v2_FUNDAMENTAL_RELIABILITY_HAIRCUT_ONLY|F11F_v2_FUNDAMENTAL_RELIABILITY_HAIRCUT_ONLY"
  "stockbench-f11f-v2-prompt-warning|experiment/f11f-v2-prompt-warning|F11F_v2_PROMPT_WARNING_ONLY|F11F_v2_PROMPT_WARNING_ONLY"
  "stockbench-f11k-v3-loser-cooldown|experiment/f11k-v3-loser-cooldown|F11K_v3_LOSER_COOLDOWN_HAIRCUT_ONLY|F11K_v3_LOSER_COOLDOWN_HAIRCUT_ONLY"
  "stockbench-f11k-v3-prompt-warning|experiment/f11k-v3-prompt-warning|F11K_v3_PROMPT_WARNING_ONLY|F11K_v3_PROMPT_WARNING_ONLY"
  "stockbench-f11g-v2-signal-conflict|experiment/f11g-v2-signal-conflict|F11G_v2_SIGNAL_CONFLICT_HAIRCUT_ONLY|F11G_v2_SIGNAL_CONFLICT_HAIRCUT_ONLY"
  "stockbench-f11j-v2-crowding-loser|experiment/f11j-v2-crowding-loser|F11J_v2_CROWDING_LOSER_ADD_ONLY|F11J_v2_CROWDING_LOSER_ADD_ONLY"
  "stockbench-f11l-v2-weekly-throttle|experiment/f11l-v2-weekly-throttle|F11L_v2_SOFT_WEEKLY_BUY_ADD_THROTTLE|F11L_v2_SOFT_WEEKLY_BUY_ADD_THROTTLE"
  "stockbench-f11e-v2-news-dryrun|experiment/f11e-v2-news-dryrun|F11E_v2_NEWS_PRICE_CONFLICT_DRYRUN|F11E_v2_NEWS_PRICE_CONFLICT_DRYRUN"
  "stockbench-f11c-v2-memory-dryrun|experiment/f11c-v2-memory-dryrun|F11C_v2_BAD_ENTRY_MEMORY_DRYRUN|F11C_v2_BAD_ENTRY_MEMORY_DRYRUN"
  "stockbench-f11-combo-v1|experiment/f11-combo-v1|F11_COMBO_v1_F11Fv2_F11Kv3_F11Gv2|COMBO"
)

for item in "${ITEMS[@]}"; do
  IFS="|" read -r wt branch run_id module <<< "$item"
  target="$BASE/$wt"
  if [[ ! -d "$target/.git" && ! -f "$target/.git" ]]; then
    if git show-ref --verify --quiet "refs/heads/$branch"; then
      git worktree add "$target" "$branch"
    else
      git worktree add -b "$branch" "$target" HEAD
    fi
  fi

  cp "$MAIN/stockbench/backtest/strategies/llm_decision.py" "$target/stockbench/backtest/strategies/llm_decision.py"
  cp "$MAIN/stockbench/agents/dual_agent_llm.py" "$target/stockbench/agents/dual_agent_llm.py"
  cp "$BASE_CFG" "$target/config.yaml"
  cat >> "$target/config.yaml" <<EOF

# F11 final reduced experiment overlay
stage4:
  base: F6_FUND1_COOLDOWN_5D
  run_id: $run_id

backtest:
  warmup_days: 35

f11_modules:
EOF

  case "$module" in
    COMBO)
      cat >> "$target/config.yaml" <<EOF
  F11F_v2_FUNDAMENTAL_RELIABILITY_HAIRCUT_ONLY:
    enabled: true
  F11K_v3_LOSER_COOLDOWN_HAIRCUT_ONLY:
    enabled: true
    lookback_days: 12
    forward_days: 5
  F11G_v2_SIGNAL_CONFLICT_HAIRCUT_ONLY:
    enabled: true
EOF
      ;;
    F11K_v3_LOSER_COOLDOWN_HAIRCUT_ONLY|F11K_v3_PROMPT_WARNING_ONLY)
      cat >> "$target/config.yaml" <<EOF
  $module:
    enabled: true
    lookback_days: 12
    forward_days: 5
EOF
      ;;
    F11L_v2_SOFT_WEEKLY_BUY_ADD_THROTTLE)
      cat >> "$target/config.yaml" <<EOF
  $module:
    enabled: true
    weekly_buy_add_budget: 10
EOF
      ;;
    *)
      cat >> "$target/config.yaml" <<EOF
  $module:
    enabled: true
EOF
      ;;
  esac

  mkdir -p "$target/storage/logs"
  echo "prepared $target ($run_id)"
done
