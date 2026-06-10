#!/usr/bin/env bash
set -euo pipefail

BASE=${BASE:-/mnt/d/intern_life/efunds}
MAIN=${MAIN:-$BASE/stockbench}
PYTHON_BIN=${PYTHON_BIN:-$MAIN/.venv/bin/python}

WORKTREES=(
  stockbench-f11g-v2-signal-conflict
  stockbench-f11k-v3-loser-cooldown
  stockbench-f11f-v2-reliability-haircut
)

for wt in "${WORKTREES[@]}"; do
  target="$BASE/$wt"
  cp "$MAIN/stockbench/agents/fundamental_filter_agent.py" "$target/stockbench/agents/fundamental_filter_agent.py"
  cd "$target"
  "$PYTHON_BIN" -m py_compile stockbench/agents/fundamental_filter_agent.py
  "$PYTHON_BIN" - <<'PY'
from pathlib import Path

import yaml

p = Path("config.yaml")
cfg = yaml.safe_load(p.read_text())
profile = cfg.setdefault("llm_profiles", {}).setdefault("deepseek-v4-flash", {})
profile["timeout_sec"] = 60
profile.setdefault("retry", {})["max_retries"] = 1
profile.setdefault("retry", {})["backoff_factor"] = 0.5

if isinstance(cfg.get("llm"), dict):
    cfg["llm"]["timeout_sec"] = 60
    cfg["llm"].setdefault("retry", {})["max_retries"] = 1
    cfg["llm"].setdefault("retry", {})["backoff_factor"] = 0.5

p.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
PY
  echo "prepared $target"
done
