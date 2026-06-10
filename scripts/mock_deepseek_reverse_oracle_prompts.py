#!/usr/bin/env python3
"""Mock-test reverse-oracle prompt lessons with DeepSeek V4 Flash.

This is a small research harness, not a backtest. It asks DeepSeek Flash to
choose among hindsight-inspired candidate setups using only pre-entry price/news
clues, then records whether the answer matches the oracle lesson.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI


MODEL = "deepseek-v4-flash"
BASE_URL = "https://api.deepseek.com/v1"


@dataclass
class MockCase:
    case_id: str
    title: str
    lesson_prompt: str
    user_case: str
    expected: str
    pass_regex: str
    priority_if_pass: str
    priority_if_fail: str


BASE_SYSTEM = """You are a portfolio decision assistant for StockBench.
Use DeepSeek Flash only. This is a mock prompt test, not investment advice.
You must choose the best buy point from the provided candidates using only the
price/news clues supplied in the case. Do not use hidden future returns.
Return JSON only with keys:
{
  "best_buy_date": "YYYY-MM-DD or no_buy",
  "best_symbols": ["SYMBOL"],
  "confidence": 0.0-1.0,
  "decision": "buy|small_watch|no_buy",
  "reasoning": ["short bullet", "short bullet"],
  "prompt_rule_to_implement": "one concise rule"
}
"""


CASES = [
    MockCase(
        case_id="P1_macro_panic_rebound",
        title="宏观冲击后的 panic rebound 买点",
        lesson_prompt="""Lesson rule:
When the whole universe sells off together over 3-5 sessions, most names fall
below the 20-day moving average, and the news driver is macro/policy/tariff
uncertainty rather than permanent company impairment, do not only defend. Look
for a panic-rebound buy zone in the strongest cyclicals/quality names. Policy
relief, negotiation, pause, exemption, or de-escalation headlines should raise
buy/add priority. Prefer the earliest extreme panic zone, but avoid company-
specific fraud/regulatory impairment.
""",
        user_case="""Candidate setups from the default 20-stock universe:
A) 2025-03-20 BA: normal market; universe 5d avg +1.1%; panic breadth 0%; BA 20d drawdown -3%; ordinary company news.
B) 2025-04-04 AMZN: tariff shock starting; universe 5d avg -4.3%; panic breadth 40%; 80% below 20d MA; AMZN 20d drawdown -18.9%; policy risk unresolved.
C) 2025-04-07 BA/AMZN/AXP/GS: broad tariff panic; universe 5d avg -8.1%; panic breadth 70%; 95% below 20d MA. BA 5d -21.2%, 20d drawdown -28.4%; GS 20d drawdown -24.6%; AMZN 20d drawdown -21.4%. News is macro tariff shock, not permanent company impairment.
D) 2025-04-09 AAPL/BA/GS/JPM: panic breadth 85%; market still extremely oversold. In the day/newsflow, policy pause/negotiation headlines start to appear.
E) 2025-05-15 UNH: single-stock collapse on DOJ/Medicare Advantage investigation report; universe not in panic.
Pick the best buy point and symbols.
""",
        expected="Expected: choose the 2025-04-07 to 2025-04-09 macro panic zone; symbols like BA, GS, AMZN, AXP, AAPL/JPM are acceptable. Do not choose UNH.",
        pass_regex=r"2025-04-0[79]|BA|GS|AMZN|AXP|AAPL|JPM",
        priority_if_pass="P0",
        priority_if_fail="P2",
    ),
    MockCase(
        case_id="P2_financial_volatility_beneficiary",
        title="金融股：把市场波动从风险拆成收入催化",
        lesson_prompt="""Lesson rule:
During macro panic, separate business models. For large trading/investment banks,
market volatility can be a revenue catalyst through trading revenue and client
activity. If the stock is panic-sold with the market but no idiosyncratic credit
impairment is visible, rank GS/JPM-like names above generic cyclicals. Consumer
credit-sensitive finance names can be secondary, not first.
""",
        user_case="""All candidates are available around 2025-04-07 after a tariff-driven market selloff:
A) GS: 5d -13.3%, 20d drawdown -24.6%, panic-sold with market. News context: high market volatility, trading volume spike, no company-specific credit event.
B) JPM: 5d -13.4%, 20d drawdown -19.2%, large bank, some credit-cycle risk but also trading activity benefit.
C) AXP: 5d -12.0%, 20d drawdown -20.1%, payment/consumer-credit exposure, more recession-sensitive.
D) HD: 5d -9.2%, 20d drawdown -15.0%, tariff/consumer demand risk.
E) PG: 5d -2.8%, defensive, small drawdown, limited rebound convexity.
Pick the best buy point and symbol.
""",
        expected="Expected: choose GS on/around 2025-04-07; JPM acceptable as secondary. Avoid treating all finance as pure risk.",
        pass_regex=r"GS|Goldman",
        priority_if_pass="P0",
        priority_if_fail="P2",
    ),
    MockCase(
        case_id="P3_ba_nonfatal_panic_plus_recovery",
        title="BA：非致命宏观错杀 + 交付/订单复苏线索",
        lesson_prompt="""Lesson rule:
For BA-like aerospace recovery names, a large drawdown is buyable only when the
shock is nonfatal and externally driven, while backlog/deliveries/order pipeline
or operational recovery clues remain intact. Do not wait for the whole recovery
to be confirmed if the panic is broad and the company-specific thesis is not
broken. Prefer small-to-medium buy/add in the panic zone, then hold/add if later
delivery or earnings evidence confirms.
""",
        user_case="""Candidate setups:
A) BA 2025-04-07: 5d -21.2%, 20d drawdown -28.4%, broad tariff panic. Existing clues: aerospace backlog and delivery cadence have not collapsed; the selloff is macro/tariff driven, not a new safety grounding.
B) AAPL 2025-04-09: 5d -22.8%, 20d drawdown -23.8%; tariff/China supply-chain risk remains direct and large.
C) AMZN 2025-04-07: 5d -11.3%, 20d drawdown -21.4%; tariff risk to retail margins, but cloud still strong.
D) BA 2025-04-23: Q1 loss narrows and deliveries improve; stock has already rebounded from the panic low.
E) UNH 2025-05-15: huge drawdown on DOJ investigation, company-specific regulatory impairment risk.
Pick the best buy point and symbol.
""",
        expected="Expected: choose BA in the 2025-04-07 panic zone, not wait until 2025-04-23 after confirmation; avoid UNH.",
        pass_regex=r"BA|Boeing",
        priority_if_pass="P1",
        priority_if_fail="P3",
    ),
    MockCase(
        case_id="P4_quality_earnings_setup_msft",
        title="质量股：回撤后、财报前的 Cloud/AI setup",
        lesson_prompt="""Lesson rule:
For high-quality cloud/AI compounders, the best buy may come after the market
panic has started to stabilize but before earnings confirmation. Look for:
market-driven pullback, moderate 20d drawdown, no company-specific thesis break,
upcoming earnings, and visible demand clues around cloud/AI. Avoid buying only
after the post-earnings gap because much of the edge is gone.
""",
        user_case="""Candidate setups:
A) MSFT 2025-04-07: broad panic, but tariff/news uncertainty still very high; 20d drawdown around -12%.
B) MSFT 2025-04-21: pullback has stabilized; 20d drawdown around -8.5%; upcoming 2025-04-30 earnings; visible cloud/AI demand clues; no company-specific break.
C) MSFT 2025-04-30 after earnings: Azure/cloud/AI results confirmed, but stock gaps up sharply after the announcement.
D) IBM 2025-04-21: quality tech, but less direct mega-cap cloud/AI earnings surprise setup than MSFT.
E) AMZN 2025-05-01 after earnings: mixed retail tariff/margin concern and AWS capex concern.
Pick the best buy point and symbol.
""",
        expected="Expected: choose MSFT around 2025-04-21/2025-04-24, before earnings confirmation; do not wait for 2025-04-30 post-earnings gap.",
        pass_regex=r"MSFT|Microsoft|2025-04-2[124]",
        priority_if_pass="P1",
        priority_if_fail="P3",
    ),
    MockCase(
        case_id="P5_unh_idiosyncratic_capitulation_guard",
        title="UNH：不要把公司特异性监管暴雷误学成高优先级买入",
        lesson_prompt="""Lesson rule:
Separate macro panic from idiosyncratic impairment. A single-stock collapse on
DOJ/regulatory/fraud/Medicare investigation is not the same as a broad tariff
panic. Even if a rebound is possible, the prompt should downgrade from buy to
small_watch/no_buy until there is clarification, analyst risk reset, company
rebuttal, or position size can be kept tiny. This rule protects F6 from learning
bad hindsight rebounds.
""",
        user_case="""Candidate setup:
UNH 2025-05-15: stock opens after a severe decline; 5d -21.2%, 20d drawdown -53.8%. Universe 5d avg is +2.1%, panic breadth only 10%, so this is not a market-wide panic. News: WSJ/CNBC report DOJ criminal investigation into Medicare Advantage practices; CEO/leadership uncertainty; analysts may later debate whether risks are overdone. The hindsight chart later shows a short rebound.
Should the strategy mark this as a high-priority buy point, a small watchlist candidate, or no-buy?
""",
        expected="Expected: small_watch or no_buy, not high-conviction buy; explicitly cite idiosyncratic regulatory impairment.",
        pass_regex=r"small_watch|no_buy|regulatory|DOJ|investigation|not.*buy|avoid",
        priority_if_pass="P0 risk guard",
        priority_if_fail="P1 manual guard required",
    ),
]


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        return {"raw": text}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"raw": text}


def run_case(client: OpenAI, case: MockCase) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": BASE_SYSTEM + "\n" + case.lesson_prompt},
        {"role": "user", "content": case.user_case},
    ]
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.1,
        max_tokens=1200,
    )
    content = response.choices[0].message.content or ""
    parsed = extract_json(content)
    searchable = json.dumps(parsed, ensure_ascii=False) + "\n" + content
    passed = re.search(case.pass_regex, searchable, flags=re.I | re.S) is not None
    return {
        "case_id": case.case_id,
        "title": case.title,
        "model": MODEL,
        "expected": case.expected,
        "passed": passed,
        "priority": case.priority_if_pass if passed else case.priority_if_fail,
        "response": parsed,
        "raw_response": content,
    }


def write_markdown(path: Path, results: list[dict[str, Any]]) -> None:
    lines = [
        "# DeepSeek Flash reverse-oracle prompt mock results",
        "",
        f"Model locked: `{MODEL}`",
        "",
        "| case | pass | priority | selected date | symbols | decision | confidence |",
        "|---|---:|---|---|---|---|---:|",
    ]
    for result in results:
        response = result.get("response") if isinstance(result.get("response"), dict) else {}
        symbols = response.get("best_symbols", [])
        if isinstance(symbols, list):
            symbols_text = ", ".join(str(s) for s in symbols)
        else:
            symbols_text = str(symbols)
        lines.append(
            f"| {result['case_id']} | {'yes' if result['passed'] else 'no'} | {result['priority']} | "
            f"{response.get('best_buy_date', '')} | {symbols_text} | {response.get('decision', '')} | {response.get('confidence', '')} |"
        )
    lines.extend(["", "## Detailed responses", ""])
    for result in results:
        lines.extend([
            f"### {result['case_id']}: {result['title']}",
            "",
            f"Expected: {result['expected']}",
            "",
            f"Pass: `{result['passed']}`; priority: `{result['priority']}`",
            "",
            "```json",
            json.dumps(result.get("response"), ensure_ascii=False, indent=2),
            "```",
            "",
        ])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mock DeepSeek Flash on reverse-oracle prompt lessons")
    parser.add_argument("--out", default="storage/reports/reverse_oracle_buy_timing/deepseek_flash_mock_results.json", help="JSON output path")
    parser.add_argument("--markdown", default="storage/reports/reverse_oracle_buy_timing/deepseek_flash_mock_results.md", help="Markdown output path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY is required; this harness is locked to DeepSeek Flash.")
    client = OpenAI(api_key=api_key, base_url=BASE_URL, timeout=180)
    results = [run_case(client, case) for case in CASES]

    out_path = Path(args.out)
    md_path = Path(args.markdown)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(md_path, results)
    print(f"Wrote {out_path}")
    print(f"Wrote {md_path}")
    for result in results:
        print(f"{result['case_id']}: pass={result['passed']} priority={result['priority']}")


if __name__ == "__main__":
    main()
