#!/usr/bin/env python3
"""Reverse-oracle buy timing research for the default StockBench universe.

The script is offline-first: it reads the versioned daily price cache and the
local/shared news_by_day cache. It does not run a backtest and does not call an
LLM. The goal is to find hindsight-best buy dates/stocks and attach the news
context that would have been visible on or before those dates.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import Counter
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


DEFAULT_SYMBOLS = [
    "GS",
    "MSFT",
    "HD",
    "V",
    "SHW",
    "CAT",
    "MCD",
    "UNH",
    "AXP",
    "AMGN",
    "TRV",
    "CRM",
    "JPM",
    "IBM",
    "HON",
    "BA",
    "AMZN",
    "AAPL",
    "PG",
    "JNJ",
]

CATALYST_KEYWORDS = {
    "tariff": ["tariff", "trade war", "trade tensions", "duties", "import"],
    "earnings": ["earnings", "results", "quarter", "revenue", "profit", "eps"],
    "guidance": ["guidance", "forecast", "outlook", "raise", "lower"],
    "analyst": ["analyst", "upgrade", "downgrade", "price target", "rating"],
    "capital_return": ["buyback", "repurchase", "dividend"],
    "ai_cloud": [" ai ", "artificial intelligence", "cloud", "data center"],
    "defense_aerospace": ["defense", "aerospace", "aircraft", "plane", "737", "faa", "order"],
    "financial_conditions": ["fed", "rates", "yield", "loan", "credit", "bank"],
    "healthcare_policy": ["medicare", "medicaid", "cms", "doj", "probe", "investigation"],
    "management": ["ceo", "cfo", "management", "resign", "appointed"],
    "legal_regulatory": ["lawsuit", "regulatory", "regulator", "antitrust", "settlement"],
}


def pct(value: float | None) -> float | None:
    if value is None or math.isnan(value):
        return None
    return round(value * 100.0, 6)


def fmt_pct(value: float | None) -> str:
    if value is None or math.isnan(value):
        return "n/a"
    return f"{value * 100.0:+.2f}%"


def fmt_pct_number(value: Any) -> str:
    out = safe_float(value)
    if out is None:
        return "n/a"
    return f"{out:+.2f}%"


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        out = float(value)
        if math.isnan(out):
            return default
        return out
    except Exception:
        return default


def load_symbols(config_path: Path) -> list[str]:
    if yaml is None or not config_path.exists():
        return DEFAULT_SYMBOLS
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    symbols = cfg.get("symbols_universe") or DEFAULT_SYMBOLS
    return [str(symbol).upper() for symbol in symbols]


def load_price_frame(symbol: str, start: str, end: str, price_cache: Path) -> pd.DataFrame:
    day_dir = price_cache / symbol / "day"
    if not day_dir.exists():
        raise FileNotFoundError(f"missing price cache for {symbol}: {day_dir}")

    chunks: list[pd.DataFrame] = []
    for path in sorted(day_dir.glob("*.parquet")):
        day = path.stem
        if start <= day <= end:
            chunks.append(pd.read_parquet(path))
    if not chunks:
        raise FileNotFoundError(f"no bars for {symbol} in {start}..{end}")

    df = pd.concat(chunks, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df = df.sort_values("date").drop_duplicates("date", keep="last").set_index("date")
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["open", "close"])


def previous_return(df: pd.DataFrame, idx: int, days: int) -> float | None:
    """Return over the prior N completed trading sessions ending at T-1 close."""
    if idx <= days:
        return None
    prev = safe_float(df.iloc[idx - days - 1]["close"])
    last = safe_float(df.iloc[idx - 1]["close"])
    if prev is None or last is None or prev <= 0:
        return None
    return last / prev - 1.0


def drawdown_from_high(df: pd.DataFrame, idx: int, window: int) -> float | None:
    start_idx = max(0, idx - window)
    hist = df.iloc[start_idx:idx]
    if hist.empty:
        return None
    high = safe_float(hist["high"].max())
    current_open = safe_float(df.iloc[idx]["open"])
    if high is None or current_open is None or high <= 0:
        return None
    return current_open / high - 1.0


def compute_context_by_symbol(prices: dict[str, pd.DataFrame]) -> dict[tuple[str, pd.Timestamp], dict[str, Any]]:
    context: dict[tuple[str, pd.Timestamp], dict[str, Any]] = {}
    prior_5d: dict[pd.Timestamp, list[tuple[str, float]]] = {}
    below_ma20: dict[pd.Timestamp, list[bool]] = {}

    for symbol, df in prices.items():
        ma20 = df["close"].rolling(20, min_periods=5).mean()
        for idx, (date, row) in enumerate(df.iterrows()):
            ret_1d = previous_return(df, idx, 1)
            ret_3d = previous_return(df, idx, 3)
            ret_5d = previous_return(df, idx, 5)
            gap = None
            if idx > 0:
                prev_close = safe_float(df.iloc[idx - 1]["close"])
                if prev_close and prev_close > 0:
                    gap = safe_float(row["open"], 0.0) / prev_close - 1.0
            dd20 = drawdown_from_high(df, idx, 20)
            ma = safe_float(ma20.iloc[idx])
            below = bool(ma is not None and safe_float(row["open"], 0.0) < ma)
            if ret_5d is not None:
                prior_5d.setdefault(date, []).append((symbol, ret_5d))
            below_ma20.setdefault(date, []).append(below)
            context[(symbol, date)] = {
                "pre_1d_return": ret_1d,
                "pre_3d_return": ret_3d,
                "pre_5d_return": ret_5d,
                "open_gap_vs_prev_close": gap,
                "drawdown_from_20d_high": dd20,
                "below_20d_ma": below,
            }

    # Add cross-sectional context that is knowable at the entry open.
    for date, values in prior_5d.items():
        sorted_values = sorted(values, key=lambda item: item[1], reverse=True)
        ranks = {symbol: rank + 1 for rank, (symbol, _) in enumerate(sorted_values)}
        market_avg = sum(ret for _, ret in values) / len(values)
        panic_breadth = sum(1 for _, ret in values if ret <= -0.05) / len(values)
        for symbol, _ in values:
            row = context.get((symbol, date), {})
            row["prior_5d_rs_rank"] = ranks[symbol]
            row["prior_5d_rs_pctile"] = 1.0 - ((ranks[symbol] - 1) / max(1, len(values) - 1))
            row["universe_pre_5d_avg_return"] = market_avg
            row["universe_panic_breadth_5d"] = panic_breadth

    for date, flags in below_ma20.items():
        below_share = sum(1 for flag in flags if flag) / len(flags) if flags else None
        for symbol, _ in prior_5d.get(date, []):
            context.setdefault((symbol, date), {})["universe_below_20d_ma_share"] = below_share

    return context


def compute_oracle_rows(
    prices: dict[str, pd.DataFrame],
    horizons: list[int],
    context: dict[tuple[str, pd.Timestamp], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    trade_rows: list[dict[str, Any]] = []
    by_date_horizon: dict[tuple[pd.Timestamp, int], list[dict[str, Any]]] = {}

    for symbol, df in prices.items():
        for idx, (date, row) in enumerate(df.iterrows()):
            buy_open = safe_float(row["open"])
            if buy_open is None or buy_open <= 0:
                continue
            for horizon in horizons:
                future = df.iloc[idx + 1 : idx + 1 + horizon]
                if future.empty:
                    continue
                exit_date = future["close"].idxmax()
                exit_close = safe_float(future.loc[exit_date, "close"])
                if exit_close is None:
                    continue
                future_return = exit_close / buy_open - 1.0
                future_min_close = safe_float(future["close"].min())
                downside_before_exit = None
                if future_min_close is not None:
                    downside_before_exit = future_min_close / buy_open - 1.0
                row_ctx = context.get((symbol, date), {})
                out = {
                    "horizon_days": horizon,
                    "symbol": symbol,
                    "buy_date": str(date.date()),
                    "exit_date": str(exit_date.date()),
                    "hold_days_to_peak": int((df.index.get_loc(exit_date) - idx)),
                    "buy_open": round(buy_open, 6),
                    "exit_close": round(exit_close, 6),
                    "future_peak_return_pct": pct(future_return),
                    "future_downside_before_peak_pct": pct(downside_before_exit),
                    "pre_1d_return_pct": pct(row_ctx.get("pre_1d_return")),
                    "pre_3d_return_pct": pct(row_ctx.get("pre_3d_return")),
                    "pre_5d_return_pct": pct(row_ctx.get("pre_5d_return")),
                    "open_gap_vs_prev_close_pct": pct(row_ctx.get("open_gap_vs_prev_close")),
                    "drawdown_from_20d_high_pct": pct(row_ctx.get("drawdown_from_20d_high")),
                    "below_20d_ma": row_ctx.get("below_20d_ma"),
                    "prior_5d_rs_rank": row_ctx.get("prior_5d_rs_rank"),
                    "prior_5d_rs_pctile": row_ctx.get("prior_5d_rs_pctile"),
                    "universe_pre_5d_avg_return_pct": pct(row_ctx.get("universe_pre_5d_avg_return")),
                    "universe_panic_breadth_5d_pct": pct(row_ctx.get("universe_panic_breadth_5d")),
                    "universe_below_20d_ma_share_pct": pct(row_ctx.get("universe_below_20d_ma_share")),
                }
                trade_rows.append(out)
                by_date_horizon.setdefault((date, horizon), []).append(out)

    entry_rows: list[dict[str, Any]] = []
    for (date, horizon), rows in sorted(by_date_horizon.items(), key=lambda item: (item[0][1], item[0][0])):
        ranked = sorted(rows, key=lambda row: safe_float(row["future_peak_return_pct"], -999.0), reverse=True)
        top5 = ranked[:5]
        returns = [safe_float(row["future_peak_return_pct"], 0.0) for row in rows]
        top5_returns = [safe_float(row["future_peak_return_pct"], 0.0) for row in top5]
        entry_rows.append(
            {
                "horizon_days": horizon,
                "date": str(date.date()),
                "best_symbol": top5[0]["symbol"],
                "best_future_peak_return_pct": top5[0]["future_peak_return_pct"],
                "top5_symbols": ";".join(row["symbol"] for row in top5),
                "top5_future_peak_return_mean_pct": round(sum(top5_returns) / len(top5_returns), 6),
                "universe_future_peak_return_mean_pct": round(sum(returns) / len(returns), 6),
                "universe_pre_5d_avg_return_pct": top5[0].get("universe_pre_5d_avg_return_pct"),
                "universe_panic_breadth_5d_pct": top5[0].get("universe_panic_breadth_5d_pct"),
                "universe_below_20d_ma_share_pct": top5[0].get("universe_below_20d_ma_share_pct"),
            }
        )

    return trade_rows, entry_rows


def read_news_window(news_base: Path, symbol: str, buy_date: str, lookback_days: int) -> list[dict[str, Any]]:
    symbol_dir = news_base / symbol
    if not symbol_dir.exists():
        return []
    end = pd.to_datetime(buy_date).date()
    start = end - timedelta(days=lookback_days)
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for day in pd.date_range(start=start, end=end, freq="D"):
        path = symbol_dir / f"{day.date()}.json"
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        raw_items = data.get("items", []) if isinstance(data, dict) else data if isinstance(data, list) else []
        for item in raw_items:
            key = str(item.get("id") or item.get("article_url") or item.get("url") or item.get("title") or "")
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
    items.sort(key=lambda item: str(item.get("published_utc", "")), reverse=True)
    return items


def item_sentiment_for_symbol(item: dict[str, Any], symbol: str) -> str:
    for insight in item.get("insights", []) or []:
        if str(insight.get("ticker", "")).upper() == symbol:
            return str(insight.get("sentiment") or "unknown").lower()
    return "unknown"


def detect_keyword_tags(text: str) -> list[str]:
    lowered = f" {text.lower()} "
    tags: list[str] = []
    for tag, needles in CATALYST_KEYWORDS.items():
        if any(needle in lowered for needle in needles):
            tags.append(tag)
    return tags


def build_news_rows(news_base: Path, top_trade_rows: list[dict[str, Any]], lookback_days: int) -> list[dict[str, Any]]:
    news_rows: list[dict[str, Any]] = []
    for trade in top_trade_rows:
        symbol = str(trade["symbol"])
        buy_date = str(trade["buy_date"])
        items = read_news_window(news_base, symbol, buy_date, lookback_days)
        sentiment_counts: Counter[str] = Counter()
        tag_counts: Counter[str] = Counter()
        titles: list[str] = []
        for item in items:
            title = str(item.get("title") or "").strip()
            desc = str(item.get("description") or "").strip()
            if title and len(titles) < 5:
                titles.append(title.replace("\n", " "))
            sentiment_counts[item_sentiment_for_symbol(item, symbol)] += 1
            for tag in detect_keyword_tags(f"{title} {desc} {' '.join(item.get('keywords', []) or [])}"):
                tag_counts[tag] += 1
        news_rows.append(
            {
                "horizon_days": trade["horizon_days"],
                "symbol": symbol,
                "buy_date": buy_date,
                "future_peak_return_pct": trade["future_peak_return_pct"],
                "news_lookback_days": lookback_days,
                "news_count": len(items),
                "positive_news_count": sentiment_counts.get("positive", 0),
                "neutral_news_count": sentiment_counts.get("neutral", 0),
                "negative_news_count": sentiment_counts.get("negative", 0),
                "unknown_news_count": sentiment_counts.get("unknown", 0),
                "keyword_tags": ";".join(f"{tag}={count}" for tag, count in sorted(tag_counts.items())),
                "sample_titles": " | ".join(titles),
            }
        )
    return news_rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def top_n_by_group(rows: list[dict[str, Any]], key: str, n: int, metric: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    groups: dict[Any, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(row[key], []).append(row)
    for _, group_rows in sorted(groups.items()):
        out.extend(sorted(group_rows, key=lambda row: safe_float(row[metric], -999.0), reverse=True)[:n])
    return out


def write_summary(path: Path, trade_top_rows: list[dict[str, Any]], entry_top_rows: list[dict[str, Any]], news_rows: list[dict[str, Any]]) -> None:
    lines: list[str] = []
    lines.append("# Reverse-oracle buy timing research")
    lines.append("")
    lines.append("This is a hindsight/oracle diagnostic, not a tradable backtest. It asks: if we already know the March-June 2025 path of the default 20-stock universe, which dates and stocks were the best buys, and what pre-entry price/news clues existed?")
    lines.append("")
    lines.append("## Top hindsight trades by horizon")
    lines.append("")
    for horizon in sorted({int(row["horizon_days"]) for row in trade_top_rows}):
        lines.append(f"### {horizon} trading-day horizon")
        lines.append("")
        lines.append("| rank | symbol | buy | exit | peak return | pre-5d | drawdown from 20d high | universe pre-5d | panic breadth |")
        lines.append("|---:|---|---|---|---:|---:|---:|---:|---:|")
        group = [row for row in trade_top_rows if int(row["horizon_days"]) == horizon]
        for rank, row in enumerate(group[:10], 1):
            lines.append(
                f"| {rank} | {row['symbol']} | {row['buy_date']} | {row['exit_date']} | "
                f"{float(row['future_peak_return_pct']):+.2f}% | "
                f"{fmt_pct_number(row.get('pre_5d_return_pct'))} | "
                f"{fmt_pct_number(row.get('drawdown_from_20d_high_pct'))} | "
                f"{fmt_pct_number(row.get('universe_pre_5d_avg_return_pct'))} | "
                f"{fmt_pct_number(row.get('universe_panic_breadth_5d_pct'))} |"
            )
        lines.append("")

    lines.append("## Best entry-date clusters")
    lines.append("")
    lines.append("| horizon | date | best symbol | best return | top5 symbols | top5 mean | universe mean | panic breadth |")
    lines.append("|---:|---|---|---:|---|---:|---:|---:|")
    for row in entry_top_rows[:30]:
        lines.append(
            f"| {row['horizon_days']} | {row['date']} | {row['best_symbol']} | "
            f"{float(row['best_future_peak_return_pct']):+.2f}% | {row['top5_symbols']} | "
            f"{float(row['top5_future_peak_return_mean_pct']):+.2f}% | "
            f"{float(row['universe_future_peak_return_mean_pct']):+.2f}% | "
            f"{fmt_pct_number(row.get('universe_panic_breadth_5d_pct'))} |"
        )
    lines.append("")

    lines.append("## Cached news coverage for top trades")
    lines.append("")
    if news_rows:
        total = len(news_rows)
        covered = sum(1 for row in news_rows if int(row.get("news_count", 0)) > 0)
        lines.append(f"Local news_by_day coverage exists for {covered}/{total} top-trade rows. Empty rows usually mean the offline cache has no day-level news for that symbol/date window yet.")
        lines.append("")
        lines.append("| horizon | symbol | buy | return | news count | sentiment +/0/-/? | tags | sample titles |")
        lines.append("|---:|---|---|---:|---:|---|---|---|")
        for row in news_rows[:40]:
            lines.append(
                f"| {row['horizon_days']} | {row['symbol']} | {row['buy_date']} | "
                f"{float(row['future_peak_return_pct']):+.2f}% | {row['news_count']} | "
                f"{row['positive_news_count']}/{row['neutral_news_count']}/{row['negative_news_count']}/{row['unknown_news_count']} | "
                f"{row['keyword_tags']} | {row['sample_titles']} |"
            )
    lines.append("")

    lines.append("## Strategy implications to test")
    lines.append("")
    lines.append("1. Add an oracle-derived **panic rebound candidate tag**: only advisory; trigger when universe 5-day breadth is deeply negative, most symbols are below 20d MA, and the symbol is near a 20d drawdown low but has non-worst relative strength.")
    lines.append("2. Let F6 keep the core selection, but in this tagged regime bias buy/add sizing toward the strongest rebound industries/symbols instead of applying extra vetoes.")
    lines.append("3. Treat news as catalyst confirmation, not standalone alpha: tariff/policy relief, earnings/guidance beats, analyst upgrades, order/contract news, or management/regulatory overhang resolution should raise confidence only when price context agrees.")
    lines.append("4. The top cluster is broad market stress around early April 2025; avoid fitting only to one date by requiring cross-sectional breadth and testing on a wider Mar-Dec window before promoting the rule.")
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reverse-oracle buy timing research")
    parser.add_argument("--cfg", default="config.yaml", help="Config path with symbols_universe")
    parser.add_argument("--start", default="2025-03-01", help="Start date")
    parser.add_argument("--end", default="2025-06-30", help="End date")
    parser.add_argument("--price-cache", default="data/price_cache/parquet", help="Versioned price cache directory")
    parser.add_argument("--news-cache", default=None, help="Data cache directory containing news_by_day; defaults to STOCKBENCH_DATA_CACHE_DIR or storage/cache")
    parser.add_argument("--out-dir", default="storage/reports/reverse_oracle_buy_timing", help="Output directory")
    parser.add_argument("--horizons", default="5,10,21,42,63", help="Comma-separated forward horizons in trading days")
    parser.add_argument("--top-n", type=int, default=20, help="Top trades per horizon to attach news and include in summary")
    parser.add_argument("--news-lookback-days", type=int, default=5, help="Calendar-day news lookback ending on buy date")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg_path = Path(args.cfg)
    symbols = load_symbols(cfg_path)
    horizons = [int(part.strip()) for part in str(args.horizons).split(",") if part.strip()]
    price_cache = Path(args.price_cache)
    data_cache = Path(args.news_cache or os.environ.get("STOCKBENCH_DATA_CACHE_DIR", "storage/cache"))
    news_base = data_cache / "news_by_day"
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    prices: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        prices[symbol] = load_price_frame(symbol, args.start, args.end, price_cache)

    context = compute_context_by_symbol(prices)
    trade_rows, entry_rows = compute_oracle_rows(prices, horizons, context)
    sorted_trade_rows = sorted(trade_rows, key=lambda row: (int(row["horizon_days"]), -safe_float(row["future_peak_return_pct"], -999.0)))
    top_trade_rows = top_n_by_group(trade_rows, "horizon_days", args.top_n, "future_peak_return_pct")

    sorted_entry_rows = sorted(entry_rows, key=lambda row: (int(row["horizon_days"]), -safe_float(row["top5_future_peak_return_mean_pct"], -999.0)))
    top_entry_rows = top_n_by_group(entry_rows, "horizon_days", args.top_n, "top5_future_peak_return_mean_pct")
    top_entry_rows = sorted(top_entry_rows, key=lambda row: (int(row["horizon_days"]), -safe_float(row["top5_future_peak_return_mean_pct"], -999.0)))

    news_rows = build_news_rows(news_base, top_trade_rows, args.news_lookback_days)

    write_csv(out_dir / "oracle_all_trades.csv", sorted_trade_rows)
    write_csv(out_dir / "oracle_top_trades.csv", top_trade_rows)
    write_csv(out_dir / "oracle_entry_dates.csv", sorted_entry_rows)
    write_csv(out_dir / "oracle_top_entry_dates.csv", top_entry_rows)
    write_csv(out_dir / "oracle_news_context.csv", news_rows)
    write_summary(out_dir / "summary.md", top_trade_rows, top_entry_rows, news_rows)

    print("Generated reverse-oracle research outputs:")
    for name in [
        "oracle_all_trades.csv",
        "oracle_top_trades.csv",
        "oracle_entry_dates.csv",
        "oracle_top_entry_dates.csv",
        "oracle_news_context.csv",
        "summary.md",
    ]:
        print(f"- {out_dir / name}")


if __name__ == "__main__":
    main()
