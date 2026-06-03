#!/usr/bin/env python3
"""Benchmark EFundGPT vs DeepSeek OpenAI-compatible chat endpoints.

Usage:
  python scripts/benchmark_llm_endpoints.py

Env:
  DEEPSEEK_API_KEY        required for DeepSeek
  DEEPSEEK_BASE_URL       optional, default: https://api.deepseek.com/v1
  DEEPSEEK_MODEL          optional, default: deepseek-v4-flash

  EFundGPT key is read the same way as stockbench.llm.LLMClient:
  OPENAI_API_KEY, LLM_API_KEY, EFUNDGPT_API_KEY, EFUNDS_API_KEY, AIGC_API_KEY
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import openai
import yaml


DEFAULT_PROMPT = """请用三句话解释：动量交易和价值投资的核心区别是什么？最后给一个真实市场中的简单例子。"""
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"


@dataclass
class Endpoint:
    name: str
    base_url: str
    model: str
    api_key: str
    timeout_sec: float
    extra_headers: dict[str, str]


def first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return ""


def expand_env(text: Any) -> str:
    text = str(text)

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        default = match.group(2)
        return os.getenv(name, default if default is not None else "")

    return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}", replace, text)


def efunds_headers(base_url: str, configured: dict[str, Any] | None = None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if "aigc.efunds.com.cn" in base_url.lower():
        user_name = os.getenv("EFUNDS_USER_NAME") or os.getenv("EFUNDS_USERNAME")
        if not user_name:
            raw_user = os.getenv("USER") or os.getenv("USERNAME") or "unknown"
            user_name = raw_user if raw_user.startswith("SX-") else f"SX-{raw_user}"
        headers.update(
            {
                "Efunds-User-Name": user_name,
                "Efunds-Acc-Token": os.getenv("EFUNDS_ACC_TOKEN") or user_name,
                "Efunds-Source": os.getenv("EFUNDS_SOURCE") or "2025-SX",
            }
        )

    for key, value in (configured or {}).items():
        expanded = expand_env(value).strip()
        if expanded:
            headers[key] = expanded
    return headers


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_endpoints(config: dict[str, Any]) -> list[Endpoint]:
    # Use the same default EFundGPT profile as stockbench.apps.run_backtest (--llm-profile efund -> efundgpt).
    efund_profile = ((config.get("llm_profiles") or {}).get("efundgpt") or {}).copy()
    efund_base_url = os.getenv("EFUND_BASE_URL") or str(
        efund_profile.get("base_url") or "https://aigc.efunds.com.cn/v1"
    )
    efund_model = os.getenv("EFUND_MODEL") or str(efund_profile.get("model") or "EFundGPT-air")

    return [
        Endpoint(
            name="efundgpt",
            base_url=efund_base_url,
            model=efund_model,
            api_key=first_env("OPENAI_API_KEY", "LLM_API_KEY", "EFUNDGPT_API_KEY", "EFUNDS_API_KEY", "AIGC_API_KEY"),
            timeout_sec=float(os.getenv("EFUND_TIMEOUT_SEC") or efund_profile.get("timeout_sec") or 180),
            extra_headers=efunds_headers(efund_base_url, efund_profile.get("extra_headers")),
        ),
        Endpoint(
            name="deepseek",
            base_url=os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1",
            model=os.getenv("DEEPSEEK_MODEL") or "deepseek-v4-flash",
            api_key=first_env("DEEPSEEK_API_KEY"),
            timeout_sec=float(os.getenv("DEEPSEEK_TIMEOUT_SEC") or 180),
            extra_headers={},
        ),
    ]


def usage_value(usage: Any, key: str) -> int | None:
    if usage is None:
        return None
    if isinstance(usage, dict):
        value = usage.get(key)
    else:
        value = getattr(usage, key, None)
    return int(value) if value is not None else None


def estimated_tokens(text: str) -> int:
    # Fallback only when provider does not return usage in streaming chunks.
    ascii_chars = sum(1 for ch in text if ord(ch) < 128)
    non_ascii_chars = len(text) - ascii_chars
    return max(1, round(ascii_chars / 4 + non_ascii_chars / 2))


def run_once(endpoint: Endpoint, prompt: str, max_tokens: int) -> dict[str, Any]:
    if not endpoint.api_key:
        return {"name": endpoint.name, "model": endpoint.model, "status": "skipped", "reason": "missing_api_key"}

    client = openai.OpenAI(api_key=endpoint.api_key, base_url=endpoint.base_url, timeout=endpoint.timeout_sec)
    messages = [
        {"role": "system", "content": "你是一个简洁、准确的金融知识助手。"},
        {"role": "user", "content": prompt},
    ]

    started = time.perf_counter()
    first_token_at: float | None = None
    output_parts: list[str] = []
    usage: Any = None

    try:
        stream = client.chat.completions.create(
            model=endpoint.model,
            messages=messages,
            temperature=0.2,
            max_tokens=max_tokens,
            stream=True,
            stream_options={"include_usage": True},
            extra_headers=endpoint.extra_headers or None,
        )
        for chunk in stream:
            if getattr(chunk, "usage", None) is not None:
                usage = chunk.usage
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            content = getattr(choices[0].delta, "content", None)
            if content:
                if first_token_at is None:
                    first_token_at = time.perf_counter()
                output_parts.append(content)
    except Exception as exc:
        return {
            "name": endpoint.name,
            "model": endpoint.model,
            "base_url": endpoint.base_url,
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }

    ended = time.perf_counter()
    output = "".join(output_parts).strip()
    completion_tokens = usage_value(usage, "completion_tokens")
    prompt_tokens = usage_value(usage, "prompt_tokens")
    estimated = False
    if completion_tokens is None:
        completion_tokens = estimated_tokens(output)
        estimated = True

    total_sec = ended - started
    first_token_sec = None if first_token_at is None else first_token_at - started
    generation_sec = total_sec if first_token_at is None else max(ended - first_token_at, 1e-9)

    return {
        "name": endpoint.name,
        "model": endpoint.model,
        "base_url": endpoint.base_url,
        "status": "ok",
        "first_token_sec": first_token_sec,
        "total_sec": total_sec,
        "completion_tokens": completion_tokens,
        "prompt_tokens": prompt_tokens,
        "estimated_tokens": estimated,
        "tokens_per_sec": completion_tokens / generation_sec,
        "chars": len(output),
        "preview": output[:240],
    }


def fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark EFundGPT and DeepSeek chat endpoint speed.")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="same prompt sent to both models")
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--json", action="store_true", help="print raw JSON results")
    args = parser.parse_args()

    results = [run_once(endpoint, args.prompt, args.max_tokens) for endpoint in build_endpoints(load_config())]

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    print("name       model                 status   first_token_s  total_s  out_tokens  tokens/s")
    print("---------  --------------------  -------  -------------  -------  ----------  --------")
    for r in results:
        print(
            f"{r['name']:<9}  {r['model'][:20]:<20}  {r['status']:<7}  "
            f"{fmt(r.get('first_token_sec')):>13}  {fmt(r.get('total_sec')):>7}  "
            f"{fmt(r.get('completion_tokens'), 0):>10}  {fmt(r.get('tokens_per_sec')):>8}"
        )
        if r.get("status") != "ok":
            print(f"  reason: {r.get('reason') or r.get('error')}")
        else:
            mark = " approx" if r.get("estimated_tokens") else ""
            print(f"  preview{mark}: {r.get('preview')}")


if __name__ == "__main__":
    main()
