# Fixed price cache

This directory contains versioned daily OHLCV price data used by baseline backtests.

- Path: `data/price_cache/parquet/{SYMBOL}/day/{YYYY-MM-DD}.parquet`
- Source: yfinance
- Adjustment: unadjusted OHLC (`--no-yfinance-auto-adjust`) so corporate actions are handled by the backtest layer.
- Coverage for the pinned baseline cache: 20-stock universe plus `SPY`, 2025-02-01 through 2025-06-30, excluding US market holidays.

`storage/` is runtime-only and ignored by git. Runtime API backfills may be written under `storage/parquet`, but reads prefer this fixed cache first.
