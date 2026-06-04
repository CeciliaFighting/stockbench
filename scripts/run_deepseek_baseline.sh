#!/usr/bin/env bash
set -euo pipefail

# DeepSeek baseline experiment:
# - DeepSeek V4 Flash
# - no reflection agent
# - no raw fundamental features
# - no F1.0 quant factor features
#
# Usage:
#   bash scripts/run_deepseek_baseline.sh --start-date 2025-03-03 --end-date 2025-06-30

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
    echo "[ERROR] DEEPSEEK_API_KEY is required for DeepSeek baseline runs" >&2
    exit 1
fi

mkdir -p storage/tmp storage/logs

PYTHON_BIN="${PYTHON_BIN:-python}"
if [[ "${PYTHON_BIN}" == "python" && -x ".venv/bin/python" ]]; then
    PYTHON_BIN=".venv/bin/python"
fi

BASE_CONFIG="${BASE_CONFIG:-config.yaml}"
BASELINE_CONFIG="storage/tmp/config_deepseek_baseline.yaml"

if [[ ! -f "${BASE_CONFIG}" ]]; then
    echo "[ERROR] Config file not found: ${BASE_CONFIG}" >&2
    exit 1
fi

export BASE_CONFIG BASELINE_CONFIG

"${PYTHON_BIN}" - <<'PY'
import os
from pathlib import Path
import re

src = Path(os.environ.get("BASE_CONFIG", "config.yaml"))
dst = Path(os.environ.get("BASELINE_CONFIG", "storage/tmp/config_deepseek_baseline.yaml"))
text = src.read_text(encoding="utf-8")

text = re.sub(
    r"(?m)^(\s*quant_factors:\s*\n\s*enabled:\s*)true(\s*.*)$",
    r"\1false\2",
    text,
    count=1,
)
text = re.sub(
    r"(?m)^(\s*fundamental:\s*\n\s*enabled:\s*)true(\s*.*)$",
    r"\1false\2",
    text,
    count=1,
)
text = re.sub(
    r"(?m)^(\s*reflection_agent:\s*\n\s*enabled:\s*)true(\s*.*)$",
    r"\1false\2",
    text,
    count=1,
)

dst.write_text(text, encoding="utf-8")
PY

START_DATE="${START_DATE:-2025-03-03}"
END_DATE="${END_DATE:-2025-06-30}"
RUN_ID="${RUN_ID:-DEEPSEEK_BASELINE_FULL}"
DATA_MODE="${DATA_MODE:-offline_only}"
AGENT_MODE="${AGENT_MODE:-dual}"
STRATEGY="${STRATEGY:-llm_decision}"
LOG_FILE="${LOG_FILE:-storage/logs/DEEPSEEK_BASELINE_FULL.log}"

ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --start-date)
            START_DATE="$2"
            shift 2
            ;;
        --end-date)
            END_DATE="$2"
            shift 2
            ;;
        --run-id)
            RUN_ID="$2"
            shift 2
            ;;
        --data-mode)
            DATA_MODE="$2"
            shift 2
            ;;
        --agent-mode)
            AGENT_MODE="$2"
            shift 2
            ;;
        --strategy)
            STRATEGY="$2"
            shift 2
            ;;
        --log-file)
            LOG_FILE="$2"
            shift 2
            ;;
        *)
            ARGS+=("$1")
            shift
            ;;
    esac
done

echo "[INFO] Running DeepSeek baseline"
echo "[INFO] Config: ${BASELINE_CONFIG}"
echo "[INFO] Date range: ${START_DATE} to ${END_DATE}"
echo "[INFO] Run id: ${RUN_ID}"
echo "[INFO] Log file: ${LOG_FILE}"

"${PYTHON_BIN}" -m stockbench.apps.run_backtest \
    --cfg "${BASELINE_CONFIG}" \
    --start "${START_DATE}" \
    --end "${END_DATE}" \
    --strategy "${STRATEGY}" \
    --run-id "${RUN_ID}" \
    --llm-profile deepseek-v4-flash \
    --use-deepseek \
    --agent-mode "${AGENT_MODE}" \
    --data-mode "${DATA_MODE}" \
    --no-reflection-agent \
    --no-fundamental-features \
    "${ARGS[@]}" \
    > "${LOG_FILE}" 2>&1

echo "[SUCCESS] DeepSeek baseline completed"
echo "[INFO] Log file: ${LOG_FILE}"
