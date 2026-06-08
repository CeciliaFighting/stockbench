#!/usr/bin/env python3
"""Build experiment attribution tables from existing StockBench reports.

This script is intentionally offline-only: it reads completed backtest reports,
logs, detailed trades, snapshots, and local price cache. It does not run a
backtest and does not call LLMs.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

from stockbench.core import data_hub


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

RUN_SUFFIX_RE = re.compile(r"_(20\d{6}_\d{6}_\d+)$")
DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")


@dataclass
class RunPaths:
    run_id: str
    full_run_id: str
    worktree: Path
    metrics_dir: Path
    detail_dir: Path | None
    log_path: Path | None


def clean_run_id(name: str) -> str:
    return RUN_SUFFIX_RE.sub("", name)


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


def fmt_list(values: list[str]) -> str:
    return ";".join(values)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def load_symbols(config_path: Path) -> list[str]:
    if yaml is None or not config_path.exists():
        return DEFAULT_SYMBOLS
    try:
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        symbols = cfg.get("symbols_universe") or cfg.get("symbols") or []
        return [str(s).upper() for s in symbols] or DEFAULT_SYMBOLS
    except Exception:
        return DEFAULT_SYMBOLS


def discover_report_roots(base_dir: Path, explicit_roots: list[str]) -> list[Path]:
    if explicit_roots:
        return [Path(p).expanduser().resolve() for p in explicit_roots]

    candidates = [base_dir.resolve()]
    parent = base_dir.resolve().parent
    candidates.extend(sorted(parent.glob("stockbench*")))
    roots: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        report_root = candidate / "storage" / "reports" / "backtest"
        if report_root.exists() and report_root not in seen:
            roots.append(report_root)
            seen.add(report_root)
    return roots


def discover_runs(report_roots: list[Path], include_all_runs: bool = False) -> list[RunPaths]:
    latest: dict[tuple[Path, str], RunPaths] = {}
    all_runs: list[RunPaths] = []
    for report_root in report_roots:
        worktree = report_root.parent.parent.parent
        for metrics_path in report_root.glob("*/metrics.json"):
            metrics_dir = metrics_path.parent
            full_run_id = metrics_dir.name
            run_id = clean_run_id(full_run_id)
            detail_dir = report_root / run_id
            if not detail_dir.exists():
                detail_dir = None
            log_candidates = [
                worktree / "storage" / "logs" / f"{run_id}.log",
                worktree / "storage" / "logs" / f"{full_run_id}.log",
            ]
            log_path = next((p for p in log_candidates if p.exists()), None)
            run = RunPaths(
                run_id=run_id,
                full_run_id=full_run_id,
                worktree=worktree,
                metrics_dir=metrics_dir,
                detail_dir=detail_dir,
                log_path=log_path,
            )
            all_runs.append(run)
            key = (worktree, run_id)
            if key not in latest or metrics_dir.stat().st_mtime > latest[key].metrics_dir.stat().st_mtime:
                latest[key] = run
    return sorted(all_runs if include_all_runs else latest.values(), key=lambda r: (r.run_id, str(r.worktree)))


def load_price_map(symbols: list[str], start: str, end: str, future_days: int) -> dict[str, pd.DataFrame]:
    end_ext = (pd.to_datetime(end) + pd.Timedelta(days=max(future_days * 3, 15))).strftime("%Y-%m-%d")
    out: dict[str, pd.DataFrame] = {}
    cfg = {"data": {"mode": "offline_only"}}
    for symbol in symbols:
        df = data_hub.get_bars(symbol, start, end_ext, 1, "day", True, cfg=cfg)
        if df is None or df.empty:
            continue
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        df = df.sort_values("date").drop_duplicates("date")
        out[symbol] = df.reset_index(drop=True)
    return out


def price_on_or_after(df: pd.DataFrame, date: pd.Timestamp, column: str) -> float | None:
    rows = df[df["date"] >= date]
    if rows.empty:
        return None
    return safe_float(rows.iloc[0].get(column))


def future_price(df: pd.DataFrame, date: pd.Timestamp, horizon: int, column: str = "close") -> float | None:
    rows = df[df["date"] > date].reset_index(drop=True)
    if len(rows) < horizon:
        return None
    return safe_float(rows.iloc[horizon - 1].get(column))


def future_return(
    price_map: dict[str, pd.DataFrame],
    symbol: str,
    date_value: Any,
    horizon: int,
    side: str | None = None,
    ref_price: float | None = None,
) -> float | None:
    df = price_map.get(symbol)
    if df is None or df.empty:
        return None
    date = pd.to_datetime(date_value).normalize()
    base = ref_price if ref_price and ref_price > 0 else price_on_or_after(df, date, "open")
    fut = future_price(df, date, horizon, "close")
    if base is None or fut is None or base <= 0:
        return None
    raw = fut / base - 1.0
    if side and side.lower() == "sell":
        return -raw
    return raw


def market_top5(price_map: dict[str, pd.DataFrame], symbols: list[str], start: str, end: str) -> tuple[list[dict[str, Any]], list[str]]:
    start_dt = pd.to_datetime(start).normalize()
    end_dt = pd.to_datetime(end).normalize()
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        df = price_map.get(symbol)
        if df is None or df.empty:
            continue
        start_px = price_on_or_after(df, start_dt, "open")
        end_rows = df[df["date"] <= end_dt]
        if end_rows.empty:
            continue
        end_px = safe_float(end_rows.iloc[-1].get("close"))
        if start_px and end_px:
            rows.append({"symbol": symbol, "market_return": end_px / start_px - 1.0})
    rows.sort(key=lambda r: r["market_return"], reverse=True)
    return rows[:5], [r["symbol"] for r in rows[:5]]


def avg_cash_ratio(snapshots: list[dict[str, Any]]) -> float | None:
    vals = []
    for row in snapshots:
        cash = safe_float(row.get("cash"))
        equity = safe_float(row.get("total_equity"))
        if cash is not None and equity and equity > 0:
            vals.append(cash / equity)
    return mean(vals) if vals else None


def avg_exposure_by_symbol(snapshots: list[dict[str, Any]]) -> dict[str, float]:
    exposure: dict[str, list[float]] = defaultdict(list)
    all_symbols: set[str] = set()
    for row in snapshots:
        positions = row.get("positions") or {}
        if isinstance(positions, dict):
            all_symbols.update(str(s) for s in positions.keys())
    for row in snapshots:
        positions = row.get("positions") or {}
        for symbol in all_symbols:
            pos = positions.get(symbol) if isinstance(positions, dict) else None
            exposure[symbol].append(safe_float((pos or {}).get("position_pct"), 0.0) or 0.0)
    return {symbol: mean(vals) for symbol, vals in exposure.items() if vals}


def trade_stats(trades: list[dict[str, Any]], price_map: dict[str, pd.DataFrame]) -> dict[str, Any]:
    buy_notional: dict[str, float] = defaultdict(float)
    sell_notional: dict[str, float] = defaultdict(float)
    signed_5d: list[float] = []
    signed_10d: list[float] = []
    buy_5d: list[float] = []
    buy_10d: list[float] = []
    sell_5d: list[float] = []
    sell_10d: list[float] = []

    for trade in trades:
        symbol = str(trade.get("symbol", "")).upper()
        side = str(trade.get("side", "")).lower()
        notional = abs(safe_float(trade.get("trade_value"), 0.0) or 0.0)
        if side == "buy":
            buy_notional[symbol] += notional
        elif side == "sell":
            sell_notional[symbol] += notional
        ref_price = safe_float(trade.get("exec_ref_price")) or safe_float(trade.get("exec_price"))
        r5 = future_return(price_map, symbol, trade.get("timestamp"), 5, side=side, ref_price=ref_price)
        r10 = future_return(price_map, symbol, trade.get("timestamp"), 10, side=side, ref_price=ref_price)
        if r5 is not None:
            signed_5d.append(r5)
            (buy_5d if side == "buy" else sell_5d).append(r5)
        if r10 is not None:
            signed_10d.append(r10)
            (buy_10d if side == "buy" else sell_10d).append(r10)

    top_buy = sorted(buy_notional.items(), key=lambda kv: kv[1], reverse=True)[:5]
    return {
        "buy_trades_count": sum(1 for t in trades if str(t.get("side", "")).lower() == "buy"),
        "sell_trades_count": sum(1 for t in trades if str(t.get("side", "")).lower() == "sell"),
        "top5_by_buy_notional": [s for s, _ in top_buy],
        "top5_by_buy_notional_values": [v for _, v in top_buy],
        "executed_trade_future_return_5d_avg": mean(signed_5d) if signed_5d else None,
        "executed_trade_future_return_10d_avg": mean(signed_10d) if signed_10d else None,
        "executed_buy_future_return_5d_avg": mean(buy_5d) if buy_5d else None,
        "executed_buy_future_return_10d_avg": mean(buy_10d) if buy_10d else None,
        "executed_sell_future_return_5d_avg": mean(sell_5d) if sell_5d else None,
        "executed_sell_future_return_10d_avg": mean(sell_10d) if sell_10d else None,
        "executed_future_return_observations_5d": len(signed_5d),
        "executed_future_return_observations_10d": len(signed_10d),
    }


def trade_future_rows(
    run: RunPaths,
    trades: list[dict[str, Any]],
    price_map: dict[str, pd.DataFrame],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_side: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    by_side_symbol: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    for trade in trades:
        symbol = str(trade.get("symbol", "")).upper()
        side = str(trade.get("side", "")).lower()
        if side not in {"buy", "sell"} or not symbol:
            continue
        ref_price = safe_float(trade.get("exec_ref_price")) or safe_float(trade.get("exec_price"))
        for horizon in [5, 10]:
            ret = future_return(price_map, symbol, trade.get("timestamp"), horizon, side=side, ref_price=ref_price)
            if ret is None:
                continue
            by_side[side][f"{horizon}d"].append(ret)
            by_side_symbol[(side, symbol)][f"{horizon}d"].append(ret)

    for side, vals in by_side.items():
        rows.append(
            {
                "run_id": run.run_id,
                "worktree": str(run.worktree),
                "side": side,
                "symbol": "ALL",
                "trade_count_5d_obs": len(vals.get("5d", [])),
                "future_return_5d_avg_pct": pct(mean(vals["5d"])) if vals.get("5d") else None,
                "trade_count_10d_obs": len(vals.get("10d", [])),
                "future_return_10d_avg_pct": pct(mean(vals["10d"])) if vals.get("10d") else None,
            }
        )
    for (side, symbol), vals in sorted(by_side_symbol.items()):
        rows.append(
            {
                "run_id": run.run_id,
                "worktree": str(run.worktree),
                "side": side,
                "symbol": symbol,
                "trade_count_5d_obs": len(vals.get("5d", [])),
                "future_return_5d_avg_pct": pct(mean(vals["5d"])) if vals.get("5d") else None,
                "trade_count_10d_obs": len(vals.get("10d", [])),
                "future_return_10d_avg_pct": pct(mean(vals["10d"])) if vals.get("10d") else None,
            }
        )
    return rows


def symbol_trade_summary(trades: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "buy_notional": 0.0,
        "sell_notional": 0.0,
        "buy_count": 0,
        "sell_count": 0,
        "realized_pnl": 0.0,
        "first_buy_date": "",
        "last_sell_date": "",
    })
    for trade in trades:
        symbol = str(trade.get("symbol", "")).upper()
        side = str(trade.get("side", "")).lower()
        if not symbol:
            continue
        row = out[symbol]
        date = str(trade.get("timestamp", ""))[:10]
        notional = abs(safe_float(trade.get("trade_value"), 0.0) or 0.0)
        row["realized_pnl"] += safe_float(trade.get("realized_pnl"), 0.0) or 0.0
        if side == "buy":
            row["buy_notional"] += notional
            row["buy_count"] += 1
            if not row["first_buy_date"] or date < row["first_buy_date"]:
                row["first_buy_date"] = date
        elif side == "sell":
            row["sell_notional"] += notional
            row["sell_count"] += 1
            if not row["last_sell_date"] or date > row["last_sell_date"]:
                row["last_sell_date"] = date
    return dict(out)


def exposure_proxy_contribution(
    snapshots: list[dict[str, Any]],
    price_map: dict[str, pd.DataFrame],
    symbol: str,
) -> float | None:
    """Approximate contribution as previous-day position weight times next close return."""
    if not snapshots or symbol not in price_map:
        return None
    prices = price_map[symbol][["date", "close"]].copy()
    prices["ret_next"] = prices["close"].shift(-1) / prices["close"] - 1.0
    ret_by_date = {pd.to_datetime(r.date).normalize(): safe_float(r.ret_next) for r in prices.itertuples()}
    contrib = 0.0
    obs = 0
    for snap in snapshots:
        date = pd.to_datetime(snap.get("date")).normalize()
        positions = snap.get("positions") or {}
        pos = positions.get(symbol) if isinstance(positions, dict) else None
        weight = safe_float((pos or {}).get("position_pct"), 0.0) or 0.0
        ret = ret_by_date.get(date)
        if ret is None:
            continue
        contrib += weight * ret
        obs += 1
    return contrib if obs else None


def symbol_exposure_rows(
    run: RunPaths,
    trades: list[dict[str, Any]],
    snapshots: list[dict[str, Any]],
    price_map: dict[str, pd.DataFrame],
    symbols: list[str],
    focus_symbols: list[str],
    start: str,
    end: str,
) -> list[dict[str, Any]]:
    exposures = avg_exposure_by_symbol(snapshots)
    exposure_rank = {
        symbol: rank
        for rank, (symbol, _) in enumerate(sorted(exposures.items(), key=lambda kv: kv[1], reverse=True), start=1)
    }
    trades_by_symbol = symbol_trade_summary(trades)
    start_dt = pd.to_datetime(start).normalize()
    end_dt = pd.to_datetime(end).normalize()
    rows: list[dict[str, Any]] = []
    for symbol in focus_symbols:
        df = price_map.get(symbol)
        market_ret = None
        if df is not None and not df.empty:
            start_px = price_on_or_after(df, start_dt, "open")
            end_rows = df[df["date"] <= end_dt]
            end_px = safe_float(end_rows.iloc[-1].get("close")) if not end_rows.empty else None
            if start_px and end_px:
                market_ret = end_px / start_px - 1.0
        trade_row = trades_by_symbol.get(symbol, {})
        rows.append(
            {
                "run_id": run.run_id,
                "worktree": str(run.worktree),
                "symbol": symbol,
                "market_return_pct": pct(market_ret),
                "avg_exposure_pct": pct(exposures.get(symbol, 0.0)),
                "exposure_rank": exposure_rank.get(symbol, ""),
                "buy_notional": trade_row.get("buy_notional", 0.0),
                "sell_notional": trade_row.get("sell_notional", 0.0),
                "buy_count": trade_row.get("buy_count", 0),
                "sell_count": trade_row.get("sell_count", 0),
                "first_buy_date": trade_row.get("first_buy_date", ""),
                "last_sell_date": trade_row.get("last_sell_date", ""),
                "realized_pnl": trade_row.get("realized_pnl", 0.0),
                "exposure_proxy_contribution_pct": pct(exposure_proxy_contribution(snapshots, price_map, symbol)),
                "missed_winner_flag": symbol in symbols and (exposures.get(symbol, 0.0) < 0.03),
            }
        )
    return rows


def parse_log_interventions(log_path: Path | None, price_map: dict[str, pd.DataFrame]) -> dict[str, Any]:
    counts: dict[str, int] = defaultdict(int)
    reason_counts: dict[str, int] = defaultdict(int)
    dated_interventions: list[dict[str, Any]] = []
    current_date: str | None = None

    if log_path is None or not log_path.exists():
        return {
            "intervention_counts": counts,
            "reason_counts": reason_counts,
            "dated_interventions": dated_interventions,
        }

    for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "stockbench.backtest.engine:run" in line:
            dates = DATE_RE.findall(line)
            if dates:
                # Log lines start with wall-clock time; the last date is the backtest date.
                current_date = dates[-1]

        for key in [
            "cooldown_block_count",
            "reversal_block_count",
            "allowed_same_direction_add_count",
            "allowed_risk_reducing_sell_count",
            "thesis_invalidated_exception_count",
            "regime_intervention_count",
            "add_to_winners_allowed_count",
        ]:
            m = re.search(rf"{key}=(\d+)", line)
            if m:
                counts[key] += int(m.group(1))

        m_review = re.search(
            r"\[RISK_REVIEW\] reviewed=(\d+), approved=(\d+), reduced=(\d+), delayed=(\d+), rejected=(\d+)",
            line,
        )
        if m_review:
            for key, value in zip(["reviewed", "approved", "reduced", "delayed", "rejected"], m_review.groups()):
                counts[f"risk_review_{key}_count"] += int(value)

        m_reduce = re.search(r"\[RISK_REVIEW\] reduce_size ([A-Z]+): ([^,]+), qty ([\-0-9.]+) -> ([\-0-9.]+)", line)
        if m_reduce:
            symbol, reason, qty_before, qty_after = m_reduce.groups()
            reason_counts[f"risk_review_reduce:{reason}"] += 1
            counts["risk_review_reduce_detail_count"] += 1
            if current_date:
                dated_interventions.append(
                    {
                        "type": "risk_review_reduce",
                        "symbol": symbol,
                        "date": current_date,
                        "side": "buy" if float(qty_before) > 0 else "sell",
                    }
                )

        m_delay = re.search(r"\[RISK_REVIEW\] delay ([A-Z]+): ([^,]+)", line)
        if m_delay:
            symbol, reason = m_delay.groups()
            reason_counts[f"risk_review_delay:{reason}"] += 1
            counts["risk_review_delay_detail_count"] += 1
            if current_date:
                dated_interventions.append({"type": "risk_review_delay", "symbol": symbol, "date": current_date, "side": None})

        m_reject = re.search(r"\[RISK_REVIEW\] reject ([A-Z]+): ([^,]+)", line)
        if m_reject:
            symbol, reason = m_reject.groups()
            reason_counts[f"risk_review_reject:{reason}"] += 1
            counts["risk_review_reject_detail_count"] += 1
            if current_date:
                dated_interventions.append({"type": "risk_review_reject", "symbol": symbol, "date": current_date, "side": None})

        m_block_sell = re.search(r"\[COOLDOWN\] Block sell after recent buy ([A-Z]+)", line)
        if m_block_sell and current_date:
            dated_interventions.append({"type": "cooldown_block_sell_after_buy", "symbol": m_block_sell.group(1), "date": current_date, "side": "sell"})

        m_block_buy = re.search(r"\[COOLDOWN\] Block rebuy after recent sell ([A-Z]+)", line)
        if m_block_buy and current_date:
            dated_interventions.append({"type": "cooldown_block_rebuy_after_sell", "symbol": m_block_buy.group(1), "date": current_date, "side": "buy"})

    by_type_5d: dict[str, list[float]] = defaultdict(list)
    by_type_10d: dict[str, list[float]] = defaultdict(list)
    for item in dated_interventions:
        r5 = future_return(price_map, item["symbol"], item["date"], 5, side=item.get("side"))
        r10 = future_return(price_map, item["symbol"], item["date"], 10, side=item.get("side"))
        if r5 is not None:
            by_type_5d[item["type"]].append(r5)
        if r10 is not None:
            by_type_10d[item["type"]].append(r10)

    counts["dated_intervention_count"] = len(dated_interventions)
    for intervention_type, vals in by_type_5d.items():
        counts[f"{intervention_type}_future_return_5d_avg"] = mean(vals)
        counts[f"{intervention_type}_future_return_5d_n"] = len(vals)
    for intervention_type, vals in by_type_10d.items():
        counts[f"{intervention_type}_future_return_10d_avg"] = mean(vals)
        counts[f"{intervention_type}_future_return_10d_n"] = len(vals)

    return {
        "intervention_counts": counts,
        "reason_counts": reason_counts,
        "dated_interventions": dated_interventions,
    }


def pct(value: float | None) -> float | None:
    return None if value is None else value * 100.0


def round_value(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 6)
    return value


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                keys.append(key)
                seen.add(key)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: round_value(row.get(key)) for key in keys})


def build_tables(args: argparse.Namespace) -> dict[str, Path]:
    base_dir = Path.cwd()
    symbols = load_symbols(base_dir / "config.yaml")
    price_map = load_price_map(symbols, args.start, args.end, max(args.future_horizons))
    top5_rows, market_top5_symbols = market_top5(price_map, symbols, args.start, args.end)

    report_roots = discover_report_roots(base_dir, args.report_root)
    runs = discover_runs(report_roots, include_all_runs=args.all_runs)
    if args.run_filter:
        pattern = re.compile(args.run_filter)
        runs = [run for run in runs if pattern.search(run.run_id) or pattern.search(str(run.worktree))]

    attribution_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    intervention_detail_rows: list[dict[str, Any]] = []
    trade_future_by_side_rows: list[dict[str, Any]] = []
    intervention_summary_rows: list[dict[str, Any]] = []
    winner_rows: list[dict[str, Any]] = []
    nonwinner_rows: list[dict[str, Any]] = []

    winner_symbols = [row["symbol"] for row in top5_rows]
    nonwinner_focus_symbols = ["V", "TRV", "JPM"]

    for run in runs:
        metrics = load_json(run.metrics_dir / "metrics.json")
        detail_summary = load_json((run.detail_dir or Path()) / "detailed_trading_summary.json") if run.detail_dir else {}
        trades = read_jsonl((run.detail_dir / "detailed_trades.jsonl") if run.detail_dir else None)
        snapshots = read_jsonl((run.detail_dir / "detailed_portfolio_snapshots.jsonl") if run.detail_dir else None)
        tstats = trade_stats(trades, price_map)
        trade_future_by_side_rows.extend(trade_future_rows(run, trades, price_map))
        exposures = avg_exposure_by_symbol(snapshots)
        top_exposure = sorted(exposures.items(), key=lambda kv: kv[1], reverse=True)[:5]
        log_data = parse_log_interventions(run.log_path, price_map)
        intervention_counts = dict(log_data["intervention_counts"])
        reason_counts = dict(log_data["reason_counts"])

        selected_by_buy = tstats["top5_by_buy_notional"]
        selected_by_exp = [s for s, _ in top_exposure]
        buy_overlap = sorted(set(selected_by_buy) & set(market_top5_symbols))
        exp_overlap = sorted(set(selected_by_exp) & set(market_top5_symbols))
        avg_cash = avg_cash_ratio(snapshots)
        total_trades = detail_summary.get("total_trades") or metrics.get("trades_count") or len(trades)

        attribution_row: dict[str, Any] = {
            "run_id": run.run_id,
            "worktree": str(run.worktree),
            "total_return_pct": pct(safe_float(metrics.get("cum_return"))),
            "sortino": safe_float(metrics.get("sortino")),
            "sharpe": safe_float(metrics.get("sharpe")),
            "max_drawdown_pct": pct(safe_float(metrics.get("max_drawdown"))),
            "trades_count": total_trades,
            "trades_notional": safe_float(metrics.get("trades_notional")),
            "avg_cash_ratio_pct": pct(avg_cash),
            "buy_trades_count": tstats["buy_trades_count"],
            "sell_trades_count": tstats["sell_trades_count"],
            "executed_trade_future_return_5d_avg_pct": pct(tstats["executed_trade_future_return_5d_avg"]),
            "executed_trade_future_return_10d_avg_pct": pct(tstats["executed_trade_future_return_10d_avg"]),
            "executed_buy_future_return_5d_avg_pct": pct(tstats["executed_buy_future_return_5d_avg"]),
            "executed_buy_future_return_10d_avg_pct": pct(tstats["executed_buy_future_return_10d_avg"]),
            "executed_sell_future_return_5d_avg_pct": pct(tstats["executed_sell_future_return_5d_avg"]),
            "executed_sell_future_return_10d_avg_pct": pct(tstats["executed_sell_future_return_10d_avg"]),
            "future_return_obs_5d": tstats["executed_future_return_observations_5d"],
            "future_return_obs_10d": tstats["executed_future_return_observations_10d"],
            "top5_by_buy_notional": fmt_list(selected_by_buy),
            "top5_by_avg_exposure": fmt_list(selected_by_exp),
            "market_top5": fmt_list(market_top5_symbols),
            "buy_top5_overlap_with_market_top5": fmt_list(buy_overlap),
            "buy_top5_overlap_count": len(buy_overlap),
            "exposure_top5_overlap_with_market_top5": fmt_list(exp_overlap),
            "exposure_top5_overlap_count": len(exp_overlap),
            "log_path": str(run.log_path) if run.log_path else "",
            "metrics_dir": str(run.metrics_dir),
            "detail_dir": str(run.detail_dir) if run.detail_dir else "",
        }
        for key, value in intervention_counts.items():
            if isinstance(value, float):
                attribution_row[key.replace("future_return", "future_return_pct")] = pct(value)
            else:
                attribution_row[key] = value
        attribution_row["intervention_reason_counts"] = ";".join(f"{k}={v}" for k, v in sorted(reason_counts.items()))
        attribution_rows.append(attribution_row)

        selection_rows.append(
            {
                "run_id": run.run_id,
                "worktree": str(run.worktree),
                "total_return_pct": pct(safe_float(metrics.get("cum_return"))),
                "sortino": safe_float(metrics.get("sortino")),
                "top5_by_buy_notional": fmt_list(selected_by_buy),
                "top5_by_avg_exposure": fmt_list(selected_by_exp),
                "market_top5": fmt_list(market_top5_symbols),
                "buy_top5_overlap_count": len(buy_overlap),
                "buy_top5_overlap_symbols": fmt_list(buy_overlap),
                "exposure_top5_overlap_count": len(exp_overlap),
                "exposure_top5_overlap_symbols": fmt_list(exp_overlap),
            }
        )

        for item in log_data["dated_interventions"]:
            row = {
                "run_id": run.run_id,
                "worktree": str(run.worktree),
                "date": item.get("date"),
                "symbol": item.get("symbol"),
                "intervention_type": item.get("type"),
                "side": item.get("side") or "",
                "future_return_5d_pct": pct(future_return(price_map, item["symbol"], item["date"], 5, side=item.get("side"))),
                "future_return_10d_pct": pct(future_return(price_map, item["symbol"], item["date"], 10, side=item.get("side"))),
            }
            intervention_detail_rows.append(row)

        intervention_groups: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        for item in log_data["dated_interventions"]:
            for horizon in [5, 10]:
                ret = future_return(price_map, item["symbol"], item["date"], horizon, side=item.get("side"))
                if ret is not None:
                    intervention_groups[item["type"]][f"{horizon}d"].append(ret)
        for intervention_type, vals in intervention_groups.items():
            intervention_summary_rows.append(
                {
                    "run_id": run.run_id,
                    "worktree": str(run.worktree),
                    "intervention_type": intervention_type,
                    "event_count_with_date": sum(1 for item in log_data["dated_interventions"] if item["type"] == intervention_type),
                    "future_return_5d_avg_pct": pct(mean(vals["5d"])) if vals.get("5d") else None,
                    "future_return_5d_n": len(vals.get("5d", [])),
                    "future_return_10d_avg_pct": pct(mean(vals["10d"])) if vals.get("10d") else None,
                    "future_return_10d_n": len(vals.get("10d", [])),
                }
            )

        winner_rows.extend(symbol_exposure_rows(run, trades, snapshots, price_map, symbols, winner_symbols, args.start, args.end))
        nonwinner_rows.extend(symbol_exposure_rows(run, trades, snapshots, price_map, symbols, nonwinner_focus_symbols, args.start, args.end))

    market_rows = [
        {
            "rank": i + 1,
            "symbol": row["symbol"],
            "market_return_pct": pct(row["market_return"]),
            "start": args.start,
            "end": args.end,
        }
        for i, row in enumerate(top5_rows)
    ]

    out_dir = Path(args.output_dir)
    paths = {
        "module_intervention_attribution": out_dir / "module_intervention_attribution.csv",
        "strategy_vs_market_top5": out_dir / "strategy_vs_market_top5.csv",
        "market_top5": out_dir / "market_top5.csv",
        "intervention_details": out_dir / "intervention_details.csv",
        "trade_future_by_side": out_dir / "trade_future_by_side.csv",
        "intervention_future_by_type": out_dir / "intervention_future_by_type.csv",
        "missed_winner_analysis": out_dir / "missed_winner_analysis.csv",
        "focus_exposure_attribution": out_dir / "focus_exposure_attribution.csv",
    }
    write_csv(paths["module_intervention_attribution"], attribution_rows)
    write_csv(paths["strategy_vs_market_top5"], selection_rows)
    write_csv(paths["market_top5"], market_rows)
    write_csv(paths["intervention_details"], intervention_detail_rows)
    write_csv(paths["trade_future_by_side"], trade_future_by_side_rows)
    write_csv(paths["intervention_future_by_type"], intervention_summary_rows)
    write_csv(paths["missed_winner_analysis"], winner_rows)
    write_csv(paths["focus_exposure_attribution"], nonwinner_rows)

    summary_path = out_dir / "README.md"
    summary_path.write_text(
        "\n".join(
            [
                "# Experiment Attribution Outputs",
                "",
                f"Period: {args.start} to {args.end}",
                f"Runs analyzed: {len(runs)}",
                f"Universe: {', '.join(symbols)}",
                f"Market Top5: {', '.join(market_top5_symbols)}",
                "",
                "Files:",
                "- `module_intervention_attribution.csv`: run-level metrics, module intervention counts, executed trade future returns, and top5 overlap.",
                "- `strategy_vs_market_top5.csv`: each run's selected top5 stocks versus the 20-stock market top5.",
                "- `market_top5.csv`: actual best 5 stocks in the 20-stock universe for the period.",
                "- `intervention_details.csv`: dated intervention events parsed from logs; future-return fields are blank when price data is unavailable.",
                "- `trade_future_by_side.csv`: buy/sell future returns, both aggregate and per symbol.",
                "- `intervention_future_by_type.csv`: future returns for dated reduce/delay/block interventions grouped by intervention type.",
                "- `missed_winner_analysis.csv`: exposure and trade activity for actual market Top5 winners.",
                "- `focus_exposure_attribution.csv`: exposure proxy attribution for V, TRV, and JPM.",
                "",
                "Notes:",
                "- `top5_by_buy_notional` is the strategy's most actively bought stocks.",
                "- `top5_by_avg_exposure` is the strategy's highest average portfolio exposure stocks.",
                "- Executed trade future returns are signed by trade side: buy benefits from price up, sell benefits from price down.",
                "- Some historical logs only contain aggregate intervention counts; those events contribute to counts but not dated future-return attribution.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths["readme"] = summary_path
    return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2025-03-03", help="Analysis start date.")
    parser.add_argument("--end", default="2025-06-30", help="Analysis end date.")
    parser.add_argument(
        "--output-dir",
        default="storage/reports/experiment_attribution",
        help="Directory for generated CSV tables.",
    )
    parser.add_argument(
        "--report-root",
        action="append",
        default=[],
        help="Backtest report root to scan. Can be repeated. Defaults to current repo and sibling stockbench* worktrees.",
    )
    parser.add_argument(
        "--run-filter",
        default="",
        help="Optional regex filter applied to run_id or worktree path, e.g. 'F6|F7'.",
    )
    parser.add_argument("--all-runs", action="store_true", help="Include all timestamped runs instead of latest per run_id/worktree.")
    parser.add_argument("--future-horizons", nargs="+", type=int, default=[5, 10], help="Future-return horizons; max is used for price loading.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = build_tables(args)
    print("Generated attribution tables:")
    for name, path in paths.items():
        print(f"- {name}: {path}")


if __name__ == "__main__":
    main()
