from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from stockbench.llm.llm_client import LLMClient, LLMConfig
from stockbench.utils.formatting import round_numbers_in_obj

logger = logging.getLogger(__name__)


def _prompt_dir() -> str:
    return os.path.join(os.path.dirname(__file__), "prompts")


def _load_prompt(name: str) -> str:
    path = os.path.join(_prompt_dir(), name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return (
            "System: You are a portfolio reflection agent. Analyze the market, "
            "portfolio, and symbols, then output valid JSON without trading orders."
        )


def _prompt_version(name: str) -> str:
    base = os.path.splitext(name)[0]
    return base.replace("_", "/")


def _extract_trade_date(features_list: List[Dict], ctx: Optional[Dict] = None) -> str:
    try:
        for item in features_list or []:
            features = item.get("features", {})
            market_data = features.get("market_data", {})
            if "date" in market_data:
                return str(market_data["date"])
            timestamp = market_data.get("timestamp")
            if isinstance(timestamp, str):
                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    return dt.strftime("%Y-%m-%d")
                except Exception:
                    pass

        if ctx and "date" in ctx:
            ctx_date = ctx["date"]
            if hasattr(ctx_date, "strftime"):
                return ctx_date.strftime("%Y-%m-%d")
            if isinstance(ctx_date, str):
                return ctx_date
    except Exception as e:
        logger.warning("[REFLECTION_AGENT] Error extracting trade date: %s", e)

    trade_date = datetime.now().strftime("%Y-%m-%d")
    logger.warning("[REFLECTION_AGENT] No trade date found, using current date: %s", trade_date)
    return trade_date


def _build_history_from_previous_decisions(
    previous_decisions: Optional[Dict] = None,
    current_features: Optional[Dict] = None,
) -> Dict[str, List[Dict]]:
    history: Dict[str, List[Dict]] = {}
    if not previous_decisions:
        return history

    try:
        decisions = {k: v for k, v in previous_decisions.items() if k != "__meta__"}
        history_date = None
        meta = previous_decisions.get("__meta__")
        if isinstance(meta, dict):
            history_date = meta.get("date")

        for symbol, decision in decisions.items():
            if not isinstance(decision, dict):
                continue

            action = decision.get("action", "hold")
            cash_change = decision.get("cash_change", 0.0)
            target_cash_amount = decision.get("target_cash_amount", 0.0)
            if action == "hold" and target_cash_amount == 0.0 and cash_change == 0.0:
                if current_features and symbol in current_features:
                    current_pos = current_features[symbol].get("position_state", {}).get("current_position_value", 0.0)
                    if current_pos > 0:
                        target_cash_amount = current_pos

            history[symbol] = [
                {
                    "date": history_date,
                    "action": action,
                    "cash_change": cash_change,
                    "target_cash_amount": target_cash_amount,
                    "reasons": decision.get("reasons", []),
                    "confidence": decision.get("confidence", 0.5),
                }
            ]
    except Exception as e:
        logger.warning("[REFLECTION_AGENT] Failed to build history from previous decisions: %s", e)

    return history


def _fallback_reflection(features_list: List[Dict], reason: str) -> Dict:
    symbols = [item.get("symbol", "UNKNOWN") for item in features_list]
    return {
        "market_regime": "uncertain",
        "market_summary": f"Reflection fallback: {reason}",
        "portfolio_diagnosis": {
            "cash_exposure": "normal",
            "risk_level": "medium",
            "key_issue": "Reflection unavailable; decision agent should rely on original features.",
            "target_equity_exposure_band": "40%-70%",
            "deployment_urgency": "normal",
        },
        "symbol_assessments": {
            symbol: {
                "relative_strength": "neutral",
                "trend_quality": "stable",
                "risk": "medium",
                "preferred_bias": "hold",
                "rationale": "Fallback neutral assessment.",
            }
            for symbol in symbols
        },
        "decision_guidance": {
            "overall_bias": "maintain_exposure",
            "candidate_actions": [],
            "watch_items": ["Reflection agent fallback was used."],
        },
    }


def _validate_reflection(data: Dict, input_symbols: set) -> Dict:
    if not isinstance(data, dict):
        return _fallback_reflection([{"symbol": s} for s in sorted(input_symbols)], "invalid reflection payload")

    symbol_assessments = data.get("symbol_assessments")
    if not isinstance(symbol_assessments, dict):
        symbol_assessments = {}

    cleaned_assessments = {}
    for symbol in input_symbols:
        item = symbol_assessments.get(symbol)
        if not isinstance(item, dict):
            item = {}
        cleaned_assessments[symbol] = {
            "relative_strength": str(item.get("relative_strength", "neutral")),
            "trend_quality": str(item.get("trend_quality", "stable")),
            "risk": str(item.get("risk", "medium")),
            "preferred_bias": str(item.get("preferred_bias", "hold")),
            "rationale": str(item.get("rationale", "No specific reflection rationale provided.")),
        }

    portfolio_diagnosis = data.get("portfolio_diagnosis")
    if not isinstance(portfolio_diagnosis, dict):
        portfolio_diagnosis = {}

    decision_guidance = data.get("decision_guidance")
    if not isinstance(decision_guidance, dict):
        decision_guidance = {}

    candidate_actions = decision_guidance.get("candidate_actions", [])
    if not isinstance(candidate_actions, list):
        candidate_actions = []

    cleaned_candidate_actions = []
    for item in candidate_actions:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol", "")).strip()
        if symbol not in input_symbols:
            continue
        cleaned_candidate_actions.append(
            {
                "symbol": symbol,
                "suggested_action": str(item.get("suggested_action", "hold")),
                "priority": str(item.get("priority", "medium")),
                "rationale": str(item.get("rationale", "No candidate action rationale provided.")),
            }
        )

    watch_items = decision_guidance.get("watch_items", [])
    if not isinstance(watch_items, list):
        watch_items = [str(watch_items)]

    return {
        "market_regime": str(data.get("market_regime", "uncertain")),
        "market_summary": str(data.get("market_summary", "")),
        "portfolio_diagnosis": {
            "cash_exposure": str(portfolio_diagnosis.get("cash_exposure", "normal")),
            "risk_level": str(portfolio_diagnosis.get("risk_level", "medium")),
            "key_issue": str(portfolio_diagnosis.get("key_issue", "")),
            "target_equity_exposure_band": str(portfolio_diagnosis.get("target_equity_exposure_band", "")),
            "deployment_urgency": str(portfolio_diagnosis.get("deployment_urgency", "normal")),
        },
        "symbol_assessments": cleaned_assessments,
        "decision_guidance": {
            "overall_bias": str(decision_guidance.get("overall_bias", "maintain_exposure")),
            "candidate_actions": cleaned_candidate_actions,
            "watch_items": [str(item) for item in watch_items],
        },
    }


def generate_portfolio_reflection(
    features_list: List[Dict],
    cfg: Dict | None = None,
    enable_llm: bool = True,
    run_id: Optional[str] = None,
    previous_decisions: Optional[Dict] = None,
    decision_history: Optional[Dict[str, List[Dict]]] = None,
    ctx: Optional[Dict] = None,
) -> Dict:
    """Generate a structured advisory reflection for the decision agent."""

    input_symbols = {item.get("symbol", "UNKNOWN") for item in features_list}
    if not enable_llm:
        return _fallback_reflection(features_list, "LLM not enabled")

    llm_cfg_raw = (cfg or {}).get("llm", {})
    if not llm_cfg_raw:
        logger.warning("[REFLECTION_AGENT] No LLM configuration found; using fallback reflection")
        return _fallback_reflection(features_list, "missing LLM configuration")

    dual_agent_cfg = (cfg or {}).get("agents", {}).get("dual_agent", {})
    reflection_cfg = dual_agent_cfg.get("reflection_agent", {})
    prompt_name = reflection_cfg.get("prompt", "reflection_agent_v1.txt")
    system_prompt = _load_prompt(prompt_name)

    cache_mode = str((cfg or {}).get("cache", {}).get("mode", "full")).lower()
    llm_cfg = LLMConfig(
        provider=str(llm_cfg_raw.get("provider", "openai-compatible")),
        base_url=str(llm_cfg_raw.get("base_url", "https://api.openai.com/v1")),
        model=str(reflection_cfg.get("model") or llm_cfg_raw.get("reflection_agent_model") or llm_cfg_raw.get("model") or "gpt-4o-mini"),
        temperature=float(reflection_cfg.get("temperature", 0.3)),
        max_tokens=int(reflection_cfg.get("max_tokens", 8000)),
        seed=llm_cfg_raw.get("seed"),
        timeout_sec=float(llm_cfg_raw.get("timeout_sec", 60)),
        max_retries=int(llm_cfg_raw.get("retry", {}).get("max_retries", 3)),
        backoff_factor=float(llm_cfg_raw.get("retry", {}).get("backoff_factor", 0.5)),
        cache_enabled=bool(llm_cfg_raw.get("cache", {}).get("enabled", True)),
        cache_ttl_hours=int(llm_cfg_raw.get("cache", {}).get("ttl_hours", 24)),
        budget_prompt_tokens=int(llm_cfg_raw.get("budget", {}).get("max_prompt_tokens", 200_000)),
        budget_completion_tokens=int(llm_cfg_raw.get("budget", {}).get("max_completion_tokens", 200_000)),
        auth_required=llm_cfg_raw.get("auth_required"),
        extra_headers=llm_cfg_raw.get("extra_headers"),
    )

    if cache_mode == "off":
        llm_cfg.cache_read_enabled = False
        llm_cfg.cache_write_enabled = False
    elif cache_mode == "llm_write_only":
        llm_cfg.cache_read_enabled = False
        llm_cfg.cache_write_enabled = True
    elif cache_mode == "full":
        llm_cfg.cache_read_enabled = True
        llm_cfg.cache_write_enabled = True
    else:
        llm_cfg.cache_read_enabled = None
        llm_cfg.cache_write_enabled = None

    symbols = {}
    total_current_position = 0.0
    current_features = {}
    for item in features_list:
        symbol = item.get("symbol", "UNKNOWN")
        features = item.get("features", {})
        symbols[symbol] = {"features": features}
        current_features[symbol] = features
        total_current_position += float(features.get("position_state", {}).get("current_position_value", 0.0) or 0.0)

    portfolio_cfg = cfg.get("portfolio", {}) if cfg else {}
    if ctx and "portfolio" in ctx:
        current_cash = float(ctx["portfolio"].cash)
        total_assets = current_cash + total_current_position
        available_cash = current_cash
    else:
        total_assets = float(portfolio_cfg.get("total_cash", 100000))
        available_cash = total_assets - total_current_position

    history = decision_history or _build_history_from_previous_decisions(previous_decisions, current_features)
    reflection_input = {
        "portfolio_info": {
            "total_assets": total_assets,
            "available_cash": available_cash,
            "position_value": total_current_position,
            "cash_ratio": available_cash / total_assets if total_assets > 0 else 0.0,
        },
        "symbols": symbols,
        "history": history,
    }

    trade_date = _extract_trade_date(features_list, ctx)
    user_prompt = json.dumps(round_numbers_in_obj(reflection_input, 2), ensure_ascii=False)

    try:
        data, meta = LLMClient().generate_json(
            "reflection_agent",
            llm_cfg,
            system_prompt,
            user_prompt,
            trade_date=trade_date,
            run_id=run_id,
            retry_attempt=0,
        )
        logger.info(
            "[REFLECTION_AGENT] LLM call completed: cached=%s, latency=%sms",
            meta.get("cached", False),
            meta.get("latency_ms", 0),
        )
        reflection = _validate_reflection(data or {}, input_symbols)
        reflection["__meta__"] = {
            "enabled": True,
            "prompt_version": _prompt_version(prompt_name),
            "cached": bool(meta.get("cached", False)),
            "latency_ms": int(meta.get("latency_ms", 0)),
            "usage": meta.get("usage", {}),
        }
        return reflection
    except Exception as e:
        logger.error("[REFLECTION_AGENT] Reflection generation failed: %s", e)
        reflection = _fallback_reflection(features_list, str(e)[:80])
        reflection["__meta__"] = {
            "enabled": True,
            "prompt_version": _prompt_version(prompt_name),
            "fallback": True,
            "error": str(e)[:200],
        }
        return reflection
