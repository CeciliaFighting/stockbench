from __future__ import annotations

import logging
import math
import re
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

MACRO_KEYWORDS = {
    "tariff": ["tariff", "tariffs"],
    "trade_war": ["trade war", "trade-war"],
    "policy_uncertainty": ["policy uncertainty", "policy shock"],
}
RELIEF_KEYWORDS = {
    "pause": ["pause", "paused", "90-day"],
    "negotiation": ["negotiation", "talks", "deal", "truce"],
    "de_escalation": ["de-escalation", "deescalation", "relief", "exemption"],
}
IMPAIRMENT_KEYWORDS = {
    "DOJ": ["doj", "department of justice"],
    "regulatory_investigation": ["investigation", "probe", "criminal", "regulatory"],
    "fraud_allegation": ["fraud", "allegation"],
    "accounting": ["accounting", "restatement"],
    "safety": ["grounding", "safety", "crash"],
    "governance": ["ceo exit", "governance", "resignation"],
    "medicare": ["medicare", "medicare advantage"],
}
RECOVERY_KEYWORDS = {
    "backlog_intact": ["backlog"],
    "delivery_cadence": ["delivery", "deliveries", "delivered"],
    "order_pipeline": ["order", "orders"],
    "loss_narrowing": ["loss narrows", "losses narrow", "narrowed loss"],
}

SYMBOL_PROFILES: Dict[str, Dict[str, List[str]]] = {
    "GS": {"business_model_tags": ["large_investment_bank", "volatility_beneficiary"]},
    "JPM": {"business_model_tags": ["large_bank", "trading_revenue_beneficiary"]},
    "AXP": {"business_model_tags": ["payments", "consumer_credit_sensitive"]},
    "BA": {"business_model_tags": ["aerospace_recovery", "order_delivery_recovery"]},
    "MSFT": {"quality_tags": ["cloud", "ai", "mega_cap_quality"]},
    "AMZN": {"quality_tags": ["cloud", "ai", "mega_cap_quality"], "business_model_tags": ["tariff_exposed_retail", "cloud"]},
    "AAPL": {"quality_tags": ["mega_cap_quality"], "business_model_tags": ["tariff_exposed_supply_chain"]},
    "IBM": {"quality_tags": ["cloud", "ai", "quality_tech"]},
}


def reverse_oracle_enabled(cfg: Dict[str, Any] | None) -> bool:
    ro_cfg = ((cfg or {}).get("reverse_oracle", {}) or {})
    return bool(ro_cfg.get("enabled", False)) and bool(ro_cfg.get("evidence_card", False))


def _cfg(cfg: Dict[str, Any] | None) -> Dict[str, Any]:
    return ((cfg or {}).get("reverse_oracle", {}) or {})


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        if math.isfinite(result):
            return result
    except (TypeError, ValueError):
        pass
    return default


def _bars_before_date(bars: Any, current_date: Optional[pd.Timestamp]) -> pd.DataFrame:
    if bars is None or not isinstance(bars, pd.DataFrame) or bars.empty:
        return pd.DataFrame()
    df = bars.copy()
    if "date" in df.columns:
        df["_date"] = pd.to_datetime(df["date"], errors="coerce")
    else:
        df["_date"] = pd.to_datetime(df.index, errors="coerce")
    df = df.dropna(subset=["_date"])
    if current_date is not None:
        cur = pd.Timestamp(current_date).normalize()
        df = df[df["_date"].dt.normalize() < cur]
    if "close" not in df.columns:
        return pd.DataFrame()
    return df.sort_values("_date").drop_duplicates(subset=["_date"], keep="last")


def _price_stats(bars: Any, current_date: Optional[pd.Timestamp]) -> Dict[str, Any]:
    df = _bars_before_date(bars, current_date)
    closes = [_safe_float(v) for v in (df["close"].tolist() if not df.empty else [])]
    closes = [v for v in closes if v > 0]
    if len(closes) < 2:
        return {
            "return_5d": 0.0,
            "drawdown_20d": 0.0,
            "below_20d_ma": False,
            "ma20_gap": 0.0,
            "price_history_days": len(closes),
        }
    last = closes[-1]
    ret_5d = (last / closes[-6] - 1.0) if len(closes) >= 6 and closes[-6] > 0 else 0.0
    window20 = closes[-20:]
    peak20 = max(window20) if window20 else last
    ma20 = sum(window20) / len(window20) if window20 else last
    return {
        "return_5d": ret_5d,
        "drawdown_20d": (last / peak20 - 1.0) if peak20 > 0 else 0.0,
        "below_20d_ma": bool(last < ma20) if ma20 > 0 else False,
        "ma20_gap": (last / ma20 - 1.0) if ma20 > 0 else 0.0,
        "price_history_days": len(closes),
    }


def _iter_news_text(features: Dict[str, Any], bar_info: Dict[str, Any] | None) -> List[str]:
    texts: List[str] = []
    events = ((features.get("news_events", {}) or {}).get("top_k_events", []) if isinstance(features, dict) else [])
    if isinstance(events, list):
        for item in events:
            if isinstance(item, str):
                texts.append(item)
            elif isinstance(item, dict):
                texts.append(" ".join(str(item.get(k, "")) for k in ("title", "description")))
    if isinstance(bar_info, dict):
        news_items = bar_info.get("news_items", []) or []
        if isinstance(news_items, list):
            for item in news_items:
                if isinstance(item, str):
                    texts.append(item)
                elif isinstance(item, dict):
                    texts.append(" ".join(str(item.get(k, "")) for k in ("title", "description")))
    return [t for t in texts if t and "No news" not in t]


def _tag_text(texts: List[str], keyword_map: Dict[str, List[str]]) -> List[str]:
    haystack = " \n".join(texts).lower()
    tags: List[str] = []
    for tag, keywords in keyword_map.items():
        for keyword in keywords:
            if re.search(re.escape(keyword.lower()), haystack):
                tags.append(tag)
                break
    return tags


def build_reverse_oracle_context(
    features_list: List[Dict[str, Any]],
    bars_data: Dict[str, Dict[str, Any]] | None,
    cfg: Dict[str, Any] | None,
    ctx: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build the Reverse Oracle Evidence Card.

    The card is low-permission prompt context only: it does not place orders,
    change target sizes, or automatically add symbols.
    """
    ro_cfg = _cfg(cfg)
    if not reverse_oracle_enabled(cfg):
        return {}

    current_date = pd.Timestamp(ctx["date"]) if ctx and ctx.get("date") is not None else None
    symbol_stats: Dict[str, Dict[str, Any]] = {}
    return_5d_values: List[float] = []
    below20_count = 0
    valid_count = 0
    all_macro_tags: set[str] = set()
    all_relief_tags: set[str] = set()

    feature_by_symbol = {item.get("symbol", "UNKNOWN"): item for item in features_list}
    for symbol, item in feature_by_symbol.items():
        features = item.get("features", {}) or {}
        bar_info = (bars_data or {}).get(symbol, {}) or {}
        stats = _price_stats(bar_info.get("bars_day"), current_date)
        if stats["price_history_days"] >= 6:
            valid_count += 1
            return_5d_values.append(float(stats["return_5d"]))
            if stats["below_20d_ma"]:
                below20_count += 1

        texts = _iter_news_text(features, bar_info)
        macro_tags = _tag_text(texts, MACRO_KEYWORDS)
        relief_tags = _tag_text(texts, RELIEF_KEYWORDS)
        impairment_tags = _tag_text(texts, IMPAIRMENT_KEYWORDS)
        recovery_tags = _tag_text(texts, RECOVERY_KEYWORDS)
        all_macro_tags.update(macro_tags)
        all_relief_tags.update(relief_tags)

        profile = SYMBOL_PROFILES.get(symbol, {})
        symbol_stats[symbol] = {
            "return_5d": stats["return_5d"],
            "drawdown_20d": stats["drawdown_20d"],
            "below_20d_ma": stats["below_20d_ma"],
            "ma20_gap": stats["ma20_gap"],
            "business_model_tags": profile.get("business_model_tags", []),
            "quality_tags": profile.get("quality_tags", []),
            "macro_shock_tags": macro_tags,
            "policy_relief_tags": relief_tags,
            "idiosyncratic_impairment_tags": impairment_tags,
            "recovery_clues": recovery_tags,
        }

    universe_5d_avg = sum(return_5d_values) / len(return_5d_values) if return_5d_values else 0.0
    panic_breadth = sum(1 for r in return_5d_values if r <= -0.05) / len(return_5d_values) if return_5d_values else 0.0
    below20_share = below20_count / valid_count if valid_count else 0.0
    macro_panic = (
        panic_breadth >= float(ro_cfg.get("panic_breadth_threshold", 0.50))
        and below20_share >= float(ro_cfg.get("below_20d_ma_share_threshold", 0.70))
        and universe_5d_avg <= float(ro_cfg.get("universe_5d_avg_return_threshold", -0.05))
    )
    if macro_panic and not all_macro_tags:
        all_macro_tags.add("price_implied_broad_panic")

    financial_beneficiaries = [
        s for s, st in symbol_stats.items()
        if any(t in st.get("business_model_tags", []) for t in ("volatility_beneficiary", "trading_revenue_beneficiary"))
    ]
    impairment_symbols = [s for s, st in symbol_stats.items() if st.get("idiosyncratic_impairment_tags")]

    for symbol, st in symbol_stats.items():
        suggested_bias = "neutral"
        if macro_panic and not st.get("idiosyncratic_impairment_tags"):
            if symbol in financial_beneficiaries:
                suggested_bias = "panic_rebound_buy_add_priority"
            elif st.get("drawdown_20d", 0.0) <= -0.15:
                suggested_bias = "panic_rebound_candidate"
        elif st.get("idiosyncratic_impairment_tags"):
            suggested_bias = "idiosyncratic_impairment_risk"
        st["suggested_bias"] = suggested_bias

    context = {
        "method": "Reverse Oracle Evidence Card",
        "permissions": "prompt_context_only_no_order_or_size_override",
        "trade_date": current_date.strftime("%Y-%m-%d") if current_date is not None else None,
        "global_market": {
            "universe_5d_avg_return": universe_5d_avg,
            "panic_breadth_5d": panic_breadth,
            "below_20d_ma_share": below20_share,
            "macro_panic": bool(macro_panic),
            "macro_shock_tags": sorted(all_macro_tags),
            "policy_relief_tags": sorted(all_relief_tags),
            "financial_volatility_beneficiary_symbols": financial_beneficiaries,
            "idiosyncratic_impairment_symbols": impairment_symbols,
        },
        "symbols": symbol_stats,
        "decision_guidance": [
            "Macro panic rebound rule: when broad 3-5 day selloff, most names below 20d MA, and no permanent company impairment, do not only defend; consider buy/add for strongest cyclicals or quality names.",
            "Financial model split: GS/JPM-like large trading banks may benefit from volatility through trading revenue; do not treat them as generic consumer-credit risk.",
            "Do not treat a single-stock DOJ/regulatory/fraud/accounting/safety/governance collapse as the same as broad macro panic.",
        ],
    }
    logger.info(
        "[REVERSE_ORACLE] Built Evidence Card: macro_panic=%s avg5d=%.4f breadth=%.2f below20=%.2f",
        macro_panic, universe_5d_avg, panic_breadth, below20_share,
    )
    return context


def build_reverse_oracle_system_addendum(cfg: Dict[str, Any] | None) -> str:
    if not reverse_oracle_enabled(cfg):
        return ""
    return (
        "\n\n[ReverseOracle] Reverse Oracle Evidence Card may appear in user input as low-permission context. "
        "Use it to improve reasoning around broad macro panic rebounds and financial volatility beneficiaries, "
        "but do not let it override direct price/news/fundamental evidence. It must not force orders, target sizes, "
        "or new positions by itself."
    )
