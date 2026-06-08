#!/usr/bin/env bash
set -euo pipefail

# Start the first-pass DeepSeek experiment batch from a shell that already has
# DEEPSEEK_API_KEY exported.

BASE="/mnt/d/intern_life/efunds"
PYTHON_BIN="${PYTHON_BIN:-${BASE}/stockbench/.venv/bin/python}"
export STOCKBENCH_DATA_CACHE_DIR="${STOCKBENCH_DATA_CACHE_DIR:-$HOME/.cache/stockbench/data-cache}"

if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
    echo "[ERROR] DEEPSEEK_API_KEY is not set in this shell." >&2
    echo "Run this script from the same WSL terminal where your API check prints DEEPSEEK True." >&2
    exit 1
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "[ERROR] Python interpreter not found or not executable: ${PYTHON_BIN}" >&2
    exit 1
fi

start_run() {
    local wt="$1"
    local run_id="$2"
    local log_name="$3"
    local fundamental_flag="$4"

    cd "${wt}"
    mkdir -p storage/logs
    echo "[INFO] Starting ${run_id} in ${wt}"
    nohup "${PYTHON_BIN}" -m stockbench.apps.run_backtest \
        --cfg config.yaml \
        --start 2025-03-03 \
        --end 2025-06-30 \
        --strategy llm_decision \
        --run-id "${run_id}" \
        --llm-profile deepseek-v4-flash \
        --use-deepseek \
        --agent-mode dual \
        --data-mode offline_only \
        --no-reflection-agent \
        "${fundamental_flag}" \
        > "storage/logs/${log_name}" 2>&1 &
    echo "[INFO] ${run_id} PID: $!"
    echo "[INFO] Log: ${wt}/storage/logs/${log_name}"
}

start_run "${BASE}/stockbench-q1" \
    "DEEPSEEK_Q1_STRUCTURED_QUANT_FULL" \
    "DEEPSEEK_Q1_STRUCTURED_QUANT_FULL.log" \
    "--no-fundamental-features"

start_run "${BASE}/stockbench-fund1" \
    "DEEPSEEK_FUND1_CLEAN_FUND_FULL" \
    "DEEPSEEK_FUND1_CLEAN_FUND_FULL.log" \
    "--fundamental-features"

start_run "${BASE}/stockbench-c1" \
    "DEEPSEEK_C1_RULE_CONSTRAINT_FULL" \
    "DEEPSEEK_C1_RULE_CONSTRAINT_FULL.log" \
    "--no-fundamental-features"

start_run "${BASE}/stockbench-m1" \
    "DEEPSEEK_M1_MEMORY_FULL" \
    "DEEPSEEK_M1_MEMORY_FULL.log" \
    "--no-fundamental-features"

echo "[SUCCESS] All four first-pass experiments have been started."
echo "[INFO] Check progress with:"
echo "ps -ef | grep -E 'DEEPSEEK_Q1|DEEPSEEK_FUND1|DEEPSEEK_C1|DEEPSEEK_M1' | grep -v grep"
