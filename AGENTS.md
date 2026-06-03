# AGENTS.md

Guidance for coding agents working in this repository.

## Project rules

- Make small, targeted changes. Prefer minimal diffs over broad rewrites.
- Follow the existing Python style and module layout.
- Do not commit runtime artifacts:
  - `storage/`
  - `logs/`
  - generated reports, PID files, benchmark logs
- `data/price_cache/parquet/` is versioned fixed price data and may be tracked by Git. Do not confuse it with runtime cache under `storage/cache/`.
- Prefer the existing virtual environment when present:

```bash
.venv/bin/python -m py_compile <changed-python-files>
bash -n scripts/run_benchmark.sh
```

- New worktrees do not automatically contain `.venv` because it is ignored by Git. Either create a local venv in that worktree, or set `PYTHON_BIN` to an existing venv interpreter before using `scripts/run_benchmark.sh`:

```bash
export PYTHON_BIN=/home/terence/code/stockbench/.venv/bin/python
```

- Do not run a long full backtest unless the user explicitly asks. For smoke tests, use a short date range.
- DeepSeek is opt-in only. Do not switch to DeepSeek just because `DEEPSEEK_API_KEY` exists. Use DeepSeek only with:

```bash
bash scripts/run_benchmark.sh --use-deepseek
# or
USE_DEEPSEEK=true bash scripts/run_benchmark.sh
```

## Cache policy

Only **data cache** is intended to be shared across worktrees. The following must remain worktree-local:

```text
<worktree>/storage/cache/llm
<worktree>/storage/logs
<worktree>/storage/reports
<worktree>/storage/tmp
```

The shared data cache is controlled by:

```bash
STOCKBENCH_DATA_CACHE_DIR
```

When set, `stockbench/core/data_hub.py` uses that directory for data cache such as:

```text
news/
news_by_day/
financials/
stock_indicators/
corporate_actions/
```

When not set, behavior is unchanged and data cache stays under:

```text
<worktree>/storage/cache
```

LLM cache is intentionally unaffected by `STOCKBENCH_DATA_CACHE_DIR` and remains isolated per worktree.

## Fedora and WSL path guidance

Preferred Fedora/Linux path:

```bash
export STOCKBENCH_DATA_CACHE_DIR="$HOME/.cache/stockbench/data-cache"
```

Preferred WSL path:

```bash
export STOCKBENCH_DATA_CACHE_DIR="$HOME/.cache/stockbench/data-cache"
```

For WSL, keep worktrees, virtualenvs, and cache on the Linux filesystem when possible. Avoid `/mnt/c/...` for high-volume cache reads/writes because many small JSON/parquet files are much slower on the Windows-mounted filesystem.

If WSL and Windows-native Python must share the exact same physical data cache, use a Windows-backed location. In WSL either form is accepted:

```bash
export STOCKBENCH_DATA_CACHE_DIR="/mnt/c/Users/<you>/AppData/Local/stockbench/data-cache"
# or Windows-style path; the code converts it under WSL/Linux
export STOCKBENCH_DATA_CACHE_DIR='C:\Users\<you>\AppData\Local\stockbench\data-cache'
```

Windows PowerShell equivalent:

```powershell
$env:STOCKBENCH_DATA_CACHE_DIR="$env:LOCALAPPDATA\stockbench\data-cache"
```

## Creating a feature branch with a worktree

Use a separate worktree for each feature or strategy experiment. Choose the base branch deliberately (`main`, or the current feature branch if continuing that work).

Example from the main repository:

```bash
BASE=/home/terence/code/stockbench
WT=/home/terence/code/stockbench-my-feature
BRANCH=feature/my-feature
BASE_REF=main

git -C "$BASE" fetch --all --prune
git -C "$BASE" worktree add -b "$BRANCH" "$WT" "$BASE_REF"
cd "$WT"
```

If the branch already exists:

```bash
git -C "$BASE" worktree add "$WT" "$BRANCH"
cd "$WT"
```

Prepare Python dependencies in the new worktree using one of these patterns:

```bash
# Option A: create an isolated venv in the new worktree
python -m venv .venv
.venv/bin/pip install -r requirements.txt

# Option B: reuse an existing venv interpreter for dependencies
export PYTHON_BIN=/home/terence/code/stockbench/.venv/bin/python
```

Check active worktrees:

```bash
git -C "$BASE" worktree list
```

Remove a worktree after it is no longer needed:

```bash
git -C "$BASE" worktree remove "$WT"
git -C "$BASE" worktree prune
```

## Running multiple strategies in parallel

Recommended pattern:

1. Create one worktree per strategy or experiment.
2. Point all worktrees at the same data cache:

```bash
export STOCKBENCH_DATA_CACHE_DIR="$HOME/.cache/stockbench/data-cache"
```

3. Pre-cache data once, preferably from a single worktree/process:

```bash
PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
STOCKBENCH_DATA_CACHE_DIR="$HOME/.cache/stockbench/data-cache" \
"$PYTHON_BIN" -m stockbench.apps.pre_cache \
  --cfg config.yaml \
  --start 2025-03-01 \
  --end 2025-06-30
```

4. Run parallel backtests in `offline_only` mode so workers mostly read shared data cache instead of racing to write it:

```bash
# worktree A
cd /home/terence/code/stockbench-strategy-a
mkdir -p storage/logs
export STOCKBENCH_DATA_CACHE_DIR="$HOME/.cache/stockbench/data-cache"
export PYTHON_BIN="${PYTHON_BIN:-/home/terence/code/stockbench/.venv/bin/python}"
nohup bash scripts/run_benchmark.sh \
  --start-date 2025-03-01 \
  --end-date 2025-06-30 \
  --strategy llm_decision \
  --llm-profile efund \
  --data-mode offline_only \
  > storage/logs/strategy-a.out 2>&1 &

# worktree B
cd /home/terence/code/stockbench-strategy-b
mkdir -p storage/logs
export STOCKBENCH_DATA_CACHE_DIR="$HOME/.cache/stockbench/data-cache"
export PYTHON_BIN="${PYTHON_BIN:-/home/terence/code/stockbench/.venv/bin/python}"
nohup bash scripts/run_benchmark.sh \
  --start-date 2025-03-01 \
  --end-date 2025-06-30 \
  --strategy llm_decision \
  --llm-profile efund \
  --data-mode offline_only \
  > storage/logs/strategy-b.out 2>&1 &
```

For direct Python runs, use a unique `--run-id` per strategy to keep result naming clear:

```bash
"${PYTHON_BIN:-.venv/bin/python}" -m stockbench.apps.run_backtest \
  --cfg config.yaml \
  --start 2025-03-01 \
  --end 2025-06-30 \
  --strategy llm_decision \
  --run-id EFUND_strategy_a \
  --llm-profile efund \
  --agent-mode dual \
  --data-mode offline_only
```

Notes:

- Shared data cache is safe to read from multiple worktrees.
- Avoid multiple workers in `auto` mode writing the same shared news/day-cache files at the same time. There is no strict cross-platform file lock around all data-cache writes.
- LLM cache, logs, reports, and tmp stay local to each worktree, so strategy-specific LLM outputs and reports do not pollute each other.
- If comparing strategies, prefer distinct branches/worktrees and distinct run IDs.

## Useful checks

```bash
git status --short --branch
ps -ef | rg 'run_benchmark|run_backtest'
tail -n 80 storage/logs/<run-log>.log
```

Validate cache routing:

```bash
STOCKBENCH_DATA_CACHE_DIR="$HOME/.cache/stockbench/data-cache" \
"${PYTHON_BIN:-.venv/bin/python}" - <<'PY'
from stockbench.core import data_hub
from stockbench.llm.llm_client import LLMClient
print('data cache:', data_hub._CACHE_BASE)
print('llm cache:', LLMClient().cache_dir)
PY
```

Expected result:

```text
data cache: <shared path from STOCKBENCH_DATA_CACHE_DIR>
llm cache: <current worktree>/storage/cache/llm
```
