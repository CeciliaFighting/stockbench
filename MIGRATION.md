# MIGRATION.md

One-time migration guide for moving StockBench **data cache** to a shared cache directory.

This file is intentionally separate from `AGENTS.md` because the migration should only be done once per machine/user setup. After the shared cache is migrated and `STOCKBENCH_DATA_CACHE_DIR` is persisted, this file can be deleted if it is no longer needed.

## What gets migrated

The migration script copies data cache from:

```text
storage/cache/
```

to a shared data-cache directory, while excluding:

```text
storage/cache/llm
```

Migrated/shared directories include:

```text
corporate_actions/
financials/
news/
news_by_day/
stock_indicators/
```

The following remain local to each worktree and are not shared:

```text
<worktree>/storage/cache/llm
<worktree>/storage/logs
<worktree>/storage/reports
<worktree>/storage/tmp
```

## Recommended Fedora / WSL target

Use a Linux-native path for Fedora and WSL:

```bash
$HOME/.cache/stockbench/data-cache
```

Avoid `/mnt/c/...` in WSL unless Windows-native Python must share the same physical cache, because many small cache files are slower on the Windows-mounted filesystem.

## Preview migration

Run from the repository root:

```bash
scripts/migrate_data_cache.py --dry-run
```

This shows what would be copied and which shell profile would be updated if `--persist-shell` is also used:

```bash
scripts/migrate_data_cache.py --dry-run --persist-shell
```

## Run migration and persist the environment variable

Default Linux/WSL-native setup:

```bash
scripts/migrate_data_cache.py --persist-shell
```

This copies data cache to:

```text
~/.cache/stockbench/data-cache
```

and writes an idempotent managed block to the inferred shell profile:

- zsh: `~/.zshrc`
- bash: `~/.bashrc`
- fallback: `~/.profile`

Managed block:

```bash
# >>> stockbench data cache >>>
export STOCKBENCH_DATA_CACHE_DIR=/home/terence/.cache/stockbench/data-cache
# <<< stockbench data cache <<<
```

Use explicit target/profile if needed:

```bash
scripts/migrate_data_cache.py \
  --target "$HOME/.cache/stockbench/data-cache" \
  --persist-shell \
  --shell-profile "$HOME/.zshrc"
```

If the target already contains files, existing files are skipped by default. Use `--overwrite` only when intentionally replacing shared cache files.

## WSL + Windows-native shared physical cache

Only use this if WSL and Windows-native Python must read/write the exact same data cache.

WSL can use either the `/mnt/c` path:

```bash
scripts/migrate_data_cache.py \
  --target "/mnt/c/Users/<you>/AppData/Local/stockbench/data-cache" \
  --persist-shell
```

or a Windows-style path, which the script converts under WSL/Linux:

```bash
scripts/migrate_data_cache.py \
  --target 'C:\Users\<you>\AppData\Local\stockbench\data-cache' \
  --persist-shell
```

Windows PowerShell equivalent for later Windows-native runs:

```powershell
$env:STOCKBENCH_DATA_CACHE_DIR="$env:LOCALAPPDATA\stockbench\data-cache"
```

To persist in Windows PowerShell, add that line to your PowerShell profile.

## Verify migration

Open a new shell session, then run:

```bash
echo "$STOCKBENCH_DATA_CACHE_DIR"
```

Expected Fedora/WSL-native value:

```text
/home/terence/.cache/stockbench/data-cache
```

Verify code routing:

```bash
"${PYTHON_BIN:-.venv/bin/python}" - <<'PY'
from stockbench.core import data_hub
from stockbench.llm.llm_client import LLMClient
print('data cache:', data_hub._CACHE_BASE)
print('llm cache:', LLMClient().cache_dir)
PY
```

Expected:

```text
data cache: <shared path from STOCKBENCH_DATA_CACHE_DIR>
llm cache: <current worktree>/storage/cache/llm
```

Confirm the shared cache does not contain LLM cache:

```bash
test -e "$STOCKBENCH_DATA_CACHE_DIR/llm" && echo "unexpected llm cache" || echo "ok: no llm cache"
```

## After migration

Use the shared data cache in every worktree by ensuring new sessions have:

```bash
STOCKBENCH_DATA_CACHE_DIR=<shared data cache path>
```

Then run parallel backtests with:

```bash
--data-mode offline_only
```

so workers mostly read the shared data cache instead of racing to populate it.
