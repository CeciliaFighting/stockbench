#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="${BASE_DIR:-/mnt/d/intern_life/efunds}"
PYTHON_BIN="${PYTHON_BIN:-$BASE_DIR/stockbench/.venv/bin/python}"

TAG_ROWS="${TAG_ROWS:-$BASE_DIR/stockbench-f10a-rebound-diagnostic/storage/reports/f10a_rebound_diagnostic/rebound_diagnostic_rows.csv}"
OUT_DIR="${OUT_DIR:-$BASE_DIR/stockbench-f10c-target-exposure-audit/storage/reports/f10c_target_exposure_audit}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[ERROR] PYTHON_BIN is not executable: $PYTHON_BIN" >&2
  exit 1
fi

if [[ ! -f "$TAG_ROWS" ]]; then
  echo "[ERROR] Missing F10A tag rows: $TAG_ROWS" >&2
  exit 1
fi

cd "$BASE_DIR/stockbench-f10c-target-exposure-audit"

"$PYTHON_BIN" scripts/f10c_target_exposure_audit.py \
  --tag-rows "$TAG_ROWS" \
  --out-dir "$OUT_DIR" \
  --run "F6=$BASE_DIR/stockbench-f5-cooldown5d/storage/reports/backtest/F5_COOLDOWN_5D" \
  --run "F10B=$BASE_DIR/stockbench-f10b-rebound-context/storage/reports/backtest/F10B_REBOUND_CONTEXT_MAIN" \
  --run "F10E=$BASE_DIR/stockbench-f10e-defensive-lagging-no-add/storage/reports/backtest/F10E_DEFENSIVE_LAGGING_NO_ADD" \
  --run "F10F=$BASE_DIR/stockbench-f10f-nt-band-lite/storage/reports/backtest/F10F_NT_BAND_LITE_ON_F6" \
  --run "F10G=$BASE_DIR/stockbench-f10g-extreme-risk-budget/storage/reports/backtest/F10G_EXTREME_RISK_BUDGET"

echo "[SUCCESS] F10C target exposure audit written to $OUT_DIR"
