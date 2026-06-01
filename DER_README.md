# DER README

## Git proxy configuration

### 小猫

```bash
git config --global http.proxy  "socks5://127.0.0.1:7890"
git config --global https.proxy "socks5://127.0.0.1:7890"
```

### 软路由

```bash
git config --global --unset http.proxy
git config --global --unset https.proxy
```

## Run baseline

Use the fixed price cache under `data/price_cache/parquet/` and the default EFund LLM profile:

```bash
bash scripts/run_benchmark.sh --start-date 2025-03-03 --end-date 2025-06-30
```

Logs:

```text
storage/logs/efund_2025-03-03_2025-06-30.log
```

Results:

```text
storage/reports/backtest/
```

Check progress:

```bash
tail -f storage/logs/efund_2025-03-03_2025-06-30.log
```
