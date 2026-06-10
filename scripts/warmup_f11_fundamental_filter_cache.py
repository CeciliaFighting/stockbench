from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, List

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from stockbench.agents.fundamental_filter_agent import filter_stocks_needing_fundamental
from stockbench.backtest.datasets import Datasets
from stockbench.backtest.engine import BacktestEngine
from stockbench.backtest.slippage import Slippage
from stockbench.backtest.strategies.llm_decision import Strategy as LlmDecisionStrategy
from stockbench.core.data_hub import set_data_mode
from stockbench.utils.logging_setup import setup_json_logging


class FundamentalFilterWarmupStrategy(LlmDecisionStrategy):
    """Build normal daily features, then warm only the shared fundamental-filter cache."""

    def __init__(self, cfg: Dict, run_id: str) -> None:
        super().__init__(cfg)
        self.run_id = run_id
        self.warmed_dates: List[str] = []

    def on_bar(self, ctx) -> List[Dict]:
        open_map = ctx.get("open_map", {}) or {}
        if not open_map:
            return []

        features_list = self._build_features_for_day(ctx)
        features_list = self._attach_f11_pre_decision_context(features_list, ctx)
        current_date = ctx["date"].strftime("%Y-%m-%d")
        self._cleanup_old_history(current_date)

        current_symbols = [fi.get("symbol", "") for fi in features_list if fi.get("symbol")]
        previous_decisions = self._build_previous_decisions_for_compatibility(current_date)
        decision_history = self._get_decision_history_for_prompt(current_symbols)

        result = filter_stocks_needing_fundamental(
            features_list=features_list,
            cfg=self.cfg,
            enable_llm=True,
            run_id=self.run_id,
            ctx=ctx,
            previous_decisions=previous_decisions,
            decision_history=decision_history,
        )
        selected = result.get("stocks_need_fundamental", []) if isinstance(result, dict) else []
        print(
            f"[F11_FILTER_WARMUP] date={current_date} universe={len(current_symbols)} "
            f"selected={len(selected)} symbols={','.join(selected)}",
            flush=True,
        )
        self.warmed_dates.append(current_date)
        return []


def _parse_symbols(symbols: str, config: Dict) -> List[str]:
    if symbols:
        return [s for s in re.split(r"[\s,]+", symbols.strip()) if s]
    return list(config.get("symbols_universe", []))


def _apply_data_mode(config: Dict, data_mode: str | None) -> None:
    effective = data_mode or ((config.get("data", {}) or {}).get("mode"))
    if effective:
        set_data_mode(str(effective))
        config.setdefault("data", {})["mode"] = str(effective)


def _apply_llm_profile(config: Dict, llm_profile: str, use_deepseek: bool) -> None:
    profiles = config.get("llm_profiles", {}) or {}
    requested = str(llm_profile or "efund").lower()
    profile_key = "deepseek-v4-flash" if use_deepseek else ("efundgpt" if requested == "efund" else requested)
    using_deepseek = profile_key == "deepseek-v4-flash"
    prof = profiles.get(profile_key)

    if using_deepseek and not os.getenv("DEEPSEEK_API_KEY"):
        raise RuntimeError("DEEPSEEK_API_KEY is required when using --use-deepseek")

    if using_deepseek and not isinstance(prof, dict):
        prof = {
            "provider": "openai",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-v4-flash",
            "backtest_report_model": "deepseek-v4-flash",
            "auth_required": True,
            "api_key_env": "DEEPSEEK_API_KEY",
            "timeout_sec": 180,
            "retry": {"max_retries": 3, "backoff_factor": 0.5},
        }

    if isinstance(prof, dict) and prof:
        base_llm = dict(config.get("llm", {}) or {})
        if "api_key_env" not in prof:
            base_llm.pop("api_key_env", None)
        config["llm"] = {**base_llm, **prof}

    selected = config.get("llm", {}) or {}
    print(
        f"[F11_FILTER_WARMUP] llm_profile={profile_key} "
        f"model={selected.get('model')} provider={selected.get('provider')}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Warm only the shared F11 fundamental_filter cache.")
    parser.add_argument("--cfg", required=True, type=Path)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--symbols", default="")
    parser.add_argument("--run-id", default="F11_FILTER_CACHE_WARMUP")
    parser.add_argument("--llm-profile", default="efund")
    parser.add_argument("--use-deepseek", action="store_true")
    parser.add_argument("--data-mode", default="offline_only")
    parser.add_argument("--shared-filter-cache-dir", default="")
    args = parser.parse_args()

    with args.cfg.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    setup_json_logging(config)
    _apply_data_mode(config, args.data_mode)
    _apply_llm_profile(config, args.llm_profile, args.use_deepseek)
    config.setdefault("backtest", {})["summary_llm"] = False
    config.setdefault("backtest", {})["timespan"] = "day"

    if args.shared_filter_cache_dir:
        os.environ["STOCKBENCH_FUNDAMENTAL_FILTER_CACHE_DIR"] = args.shared_filter_cache_dir
    if not os.getenv("STOCKBENCH_FUNDAMENTAL_FILTER_CACHE_DIR"):
        raise RuntimeError("Set STOCKBENCH_FUNDAMENTAL_FILTER_CACHE_DIR or pass --shared-filter-cache-dir")

    os.environ["TA_RUN_ID"] = args.run_id
    symbols = _parse_symbols(args.symbols, config)
    if not symbols:
        raise RuntimeError("No symbols found. Pass --symbols or set symbols_universe in config.")

    print(f"[F11_FILTER_WARMUP] cfg={args.cfg}", flush=True)
    print(f"[F11_FILTER_WARMUP] period={args.start}..{args.end} symbols={len(symbols)}", flush=True)
    print(f"[F11_FILTER_WARMUP] shared_filter_cache_dir={os.getenv('STOCKBENCH_FUNDAMENTAL_FILTER_CACHE_DIR')}", flush=True)
    print(f"[F11_FILTER_WARMUP] data_cache_dir={os.getenv('STOCKBENCH_DATA_CACHE_DIR', '<default>')}", flush=True)

    datasets = Datasets(config)
    slippage = Slippage.from_cfg(config)
    engine = BacktestEngine(config, datasets, slippage)
    strategy = FundamentalFilterWarmupStrategy(config, run_id=args.run_id)
    engine.run(strategy=strategy, start=args.start, end=args.end, symbols=symbols, timespan="day", run_id=args.run_id)
    print(f"[F11_FILTER_WARMUP] completed warmed_trading_days={len(strategy.warmed_dates)}", flush=True)


if __name__ == "__main__":
    main()
