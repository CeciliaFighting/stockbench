#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE:-/mnt/d/intern_life/efunds}"
MAIN="${MAIN:-$BASE/stockbench}"
CFG="${CFG:-$BASE/stockbench-f11g-v2-signal-conflict/config.yaml}"
PYTHON_BIN="${PYTHON_BIN:-$MAIN/.venv/bin/python}"

export STOCKBENCH_DATA_CACHE_DIR="${STOCKBENCH_DATA_CACHE_DIR:-$HOME/.cache/stockbench/data-cache}"
export STOCKBENCH_FUNDAMENTAL_FILTER_CACHE_DIR="${STOCKBENCH_FUNDAMENTAL_FILTER_CACHE_DIR:-$MAIN/storage/cache/llm/fundamental_filter_shared}"

mkdir -p "$MAIN/storage/logs" "$STOCKBENCH_FUNDAMENTAL_FILTER_CACHE_DIR"

"$PYTHON_BIN" "$MAIN/scripts/warmup_f11_fundamental_filter_cache.py" \
  --cfg "$CFG" \
  --start "${START_DATE:-2025-03-03}" \
  --end "${END_DATE:-2025-06-30}" \
  --run-id "${RUN_ID:-F11_FILTER_CACHE_WARMUP}" \
  --llm-profile "${LLM_PROFILE:-deepseek-v4-flash}" \
  --use-deepseek \
  --data-mode "${DATA_MODE:-offline_only}" \
  --shared-filter-cache-dir "$STOCKBENCH_FUNDAMENTAL_FILTER_CACHE_DIR" \
  > "$MAIN/storage/logs/${RUN_ID:-F11_FILTER_CACHE_WARMUP}.log" 2>&1
