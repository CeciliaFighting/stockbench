from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd
import yaml


DEFAULT_TARGETS = ["BA", "HON", "IBM", "MSFT", "GS"]


def _load_symbols(cfg_path: Path) -> List[str]:
    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return list(cfg.get("symbols_universe") or [])


def _read_symbol_prices(root: Path, symbol: str) -> pd.DataFrame:
    day_dir = root / "data" / "price_cache" / "parquet" / symbol / "day"
    frames = []
    for path in sorted(day_dir.glob("*.parquet")):
        df = pd.read_parquet(path)
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["date", "close"])
    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"]).dt.date
    out = out.sort_values("date").drop_duplicates("date", keep="last")
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    return out[["date", "close"]].dropna()


def _rank_pct(values: Dict[str, float]) -> Dict[str, float]:
    clean = {k: v for k, v in values.items() if pd.notna(v)}
    if not clean:
        return {}
    ordered = sorted(clean.items(), key=lambda item: item[1])
    denom = max(1, len(ordered) - 1)
    return {symbol: idx / denom for idx, (symbol, _value) in enumerate(ordered)}


def _future_return(closes: List[float], idx: int, days: int) -> float | None:
    future_idx = idx + days
    if idx < 0 or future_idx >= len(closes) or closes[idx] <= 0:
        return None
    return closes[future_idx] / closes[idx] - 1.0


def build_diagnostic(root: Path, cfg_path: Path, start: str, end: str, targets: Iterable[str]) -> tuple[pd.DataFrame, Dict]:
    symbols = _load_symbols(cfg_path)
    target_set = set(targets)
    start_date = pd.to_datetime(start).date()
    end_date = pd.to_datetime(end).date()

    by_symbol = {symbol: _read_symbol_prices(root, symbol) for symbol in symbols}
    rows = []
    for symbol, prices in by_symbol.items():
        if prices.empty:
            continue
        closes = prices["close"].astype(float).tolist()
        dates = prices["date"].tolist()
        for idx, date in enumerate(dates):
            if date < start_date or date > end_date or idx < 60:
                continue
            window60 = closes[idx - 60 : idx + 1]
            window20 = closes[idx - 20 : idx + 1]
            if min(window60) <= 0:
                continue
            close = closes[idx]
            ret5 = close / closes[idx - 5] - 1.0 if idx >= 5 and closes[idx - 5] > 0 else None
            ret20 = close / closes[idx - 20] - 1.0 if idx >= 20 and closes[idx - 20] > 0 else None
            ret60 = close / closes[idx - 60] - 1.0 if closes[idx - 60] > 0 else None
            peak60 = max(window60)
            dd60 = close / peak60 - 1.0 if peak60 > 0 else None
            ma20 = sum(window20) / len(window20)
            rows.append(
                {
                    "date": date.isoformat(),
                    "symbol": symbol,
                    "close": close,
                    "return_5d": ret5,
                    "return_20d": ret20,
                    "return_60d": ret60,
                    "drawdown_60d": dd60,
                    "price_above_20d_ma": close >= ma20,
                    "future_return_5d": _future_return(closes, idx, 5),
                    "future_return_10d": _future_return(closes, idx, 10),
                    "target_winner": symbol in target_set,
                }
            )

    df = pd.DataFrame(rows)
    if df.empty:
        return df, {"error": "no rows"}

    ranked = []
    for date, group in df.groupby("date"):
        rank5 = _rank_pct(dict(zip(group["symbol"], group["return_5d"])))
        rank20 = _rank_pct(dict(zip(group["symbol"], group["return_20d"])))
        rank60 = _rank_pct(dict(zip(group["symbol"], group["return_60d"])))
        g = group.copy()
        g["return_5d_rank_pct"] = g["symbol"].map(rank5)
        g["return_20d_rank_pct"] = g["symbol"].map(rank20)
        g["return_60d_rank_pct"] = g["symbol"].map(rank60)
        ranked.append(g)
    df = pd.concat(ranked, ignore_index=True)

    df["old_f8c_rebound_tag"] = (
        (df["drawdown_60d"] <= -0.12)
        & ((df["return_20d_rank_pct"] >= 0.70) | (df["return_5d_rank_pct"] >= 0.70))
        & df["price_above_20d_ma"]
    )
    df["revised_rebound_tag"] = (
        (df["drawdown_60d"] <= -0.06)
        & ((df["return_20d_rank_pct"] >= 0.60) | (df["return_5d_rank_pct"] >= 0.60))
        & ((df["return_5d"] > 0) | (df["return_20d"] > 0))
    )

    summary = {
        "rows": int(len(df)),
        "symbols": len(symbols),
        "targets": list(targets),
        "old_tag_count": int(df["old_f8c_rebound_tag"].sum()),
        "revised_tag_count": int(df["revised_rebound_tag"].sum()),
        "target_summary": {},
        "tagged_future_returns": {},
    }
    for symbol in targets:
        s = df[df["symbol"] == symbol]
        summary["target_summary"][symbol] = {
            "old_tag_days": int(s["old_f8c_rebound_tag"].sum()),
            "revised_tag_days": int(s["revised_rebound_tag"].sum()),
            "first_revised_tag_dates": s.loc[s["revised_rebound_tag"], "date"].head(12).tolist(),
            "period_return": float(s["close"].iloc[-1] / s["close"].iloc[0] - 1.0) if len(s) > 1 else None,
        }
    for tag in ["old_f8c_rebound_tag", "revised_rebound_tag"]:
        tagged = df[df[tag]]
        untagged = df[~df[tag]]
        summary["tagged_future_returns"][tag] = {
            "tagged_future_return_5d_mean": float(tagged["future_return_5d"].mean()) if not tagged.empty else None,
            "untagged_future_return_5d_mean": float(untagged["future_return_5d"].mean()) if not untagged.empty else None,
            "tagged_future_return_10d_mean": float(tagged["future_return_10d"].mean()) if not tagged.empty else None,
            "untagged_future_return_10d_mean": float(untagged["future_return_10d"].mean()) if not untagged.empty else None,
        }
    return df, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="F10A rebound tag diagnostic")
    parser.add_argument("--cfg", default="config.yaml")
    parser.add_argument("--start", default="2025-03-03")
    parser.add_argument("--end", default="2025-06-30")
    parser.add_argument("--targets", default=",".join(DEFAULT_TARGETS))
    parser.add_argument("--out-dir", default="storage/reports/f10a_rebound_diagnostic")
    args = parser.parse_args()

    root = Path.cwd()
    targets = [item.strip().upper() for item in args.targets.split(",") if item.strip()]
    df, summary = build_diagnostic(root, root / args.cfg, args.start, args.end, targets)
    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "rebound_diagnostic_rows.csv", index=False)
    with (out_dir / "rebound_diagnostic_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))
    print(f"Wrote {out_dir / 'rebound_diagnostic_rows.csv'}")
    print(f"Wrote {out_dir / 'rebound_diagnostic_summary.json'}")


if __name__ == "__main__":
    main()
