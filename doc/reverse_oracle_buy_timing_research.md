# 反推式买点调研：DeepSeek Flash 版策略启发

分支：`research/reverse-oracle-buy-timing`

## 0. 固定前提

后续这个方向统一锁定使用：

```text
model: deepseek-v4-flash
api key: DEEPSEEK_API_KEY
run option: --use-deepseek 或 --llm-profile deepseek-v4-flash
```

本调研不是直接跑完整回测，而是先做 hindsight/oracle 归因：看默认股票池在默认区间 `2025-03-01 ~ 2025-06-30` 的真实走势，反推出最应该买入的日期和股票，然后把这些可解释线索转成 DeepSeek Flash 能理解的 prompt/实现规则。

新增离线工具：

```bash
.venv/bin/python scripts/reverse_oracle_buy_timing.py \
  --cfg config.yaml \
  --start 2025-03-01 \
  --end 2025-06-30 \
  --out-dir storage/reports/reverse_oracle_buy_timing
```

新增 DeepSeek mock 工具：

```bash
.venv/bin/python scripts/mock_deepseek_reverse_oracle_prompts.py
```

mock 输出：

```text
storage/reports/reverse_oracle_buy_timing/deepseek_flash_mock_results.md
storage/reports/reverse_oracle_buy_timing/deepseek_flash_mock_results.json
```

## 1. 反推里最值得学的具体点

### 点一：宏观冲击后的 panic rebound，不要只防守

**学到的东西**

默认区间最强买点高度集中在 `2025-04-07 ~ 2025-04-09`。当时不是单票逻辑，而是全股票池级别的 panic：

- 4/7 全股票池过去 5 日平均收益约 `-8.11%`；
- 70% 股票过去 5 日跌幅超过 5%；
- 约 95% 股票低于 20 日均线；
- BA、GS、AMZN、AXP、JPM 等都出现 20 日高点回撤 19%-28% 左右；
- 新闻主因是 tariff / trade-war / macro policy shock，而不是这些公司永久性基本面损坏。

4/9 后，政策暂停/谈判/缓和新闻触发市场级反弹。这个模式说明：F6 在这种环境里不应该只降低风险，也应该识别 panic rebound 买点。

**DeepSeek Flash mock 结果**

- Case: `P1_macro_panic_rebound`
- 结果：通过
- DeepSeek 选择：`2025-04-09`, `BA`, `GS`, `buy`, confidence `0.90`
- 优先级：提高到 `P0`

DeepSeek 能抓住：极端 breadth + 20d MA below + policy relief = 应该买，而不是继续防守。

**建议加入的提示词**

```text
If the whole universe sells off together over 3-5 sessions, most names fall
below the 20-day moving average, and the news driver is macro/policy/tariff
uncertainty rather than permanent company impairment, do not only defend.
Look for a panic-rebound buy/add zone in the strongest cyclicals or quality names.
Policy relief, negotiation, pause, exemption, or de-escalation headlines should
raise buy/add priority.
```

**实现思路**

增加一个低权限 `rebound_evidence_card`，放进 DeepSeek prompt，不直接改订单：

```json
{
  "universe_5d_avg_return": -0.0811,
  "panic_breadth_5d": 0.70,
  "below_20d_ma_share": 0.95,
  "macro_shock_tags": ["tariff", "policy_uncertainty"],
  "policy_relief_tags": ["pause", "negotiation", "de-escalation"]
}
```

触发条件建议：

```text
panic_breadth_5d >= 0.50
below_20d_ma_share >= 0.70
universe_5d_avg_return <= -0.05
macro_shock_tags 非空
```

权限边界：只作为 prompt evidence；第一轮不要自动新增股票或覆盖 F6 决策。

---

### 点二：金融股不能一概当风险，GS/JPM 可能是波动率受益者

**学到的东西**

4 月 panic 中，GS/JPM/AXP 的价格都被打下来，但大行/投行的商业模式和普通消费/制造不同。高波动、交易量上升、客户对冲需求增加，可能转化为 trading revenue。后续 Q1 财报也验证了大型银行 trading revenue 强。

所以 DeepSeek 需要学会把“市场波动”拆开：

- 对普通风险资产：宏观风险；
- 对 GS/JPM 这类大型交易型金融机构：可能同时是收入催化；
- 对 AXP 这类消费信贷暴露：反弹可以有，但优先级低于 GS。

**DeepSeek Flash mock 结果**

- Case: `P2_financial_volatility_beneficiary`
- 结果：通过
- DeepSeek 选择：`2025-04-07`, `GS`, `buy`, confidence `0.85`
- 优先级：提高到 `P0`

**建议加入的提示词**

```text
During macro panic, separate business models. For large trading/investment banks,
market volatility can be a revenue catalyst through trading revenue and client
activity. If the stock is panic-sold with the market but no idiosyncratic credit
impairment is visible, rank GS/JPM-like names above generic cyclicals.
Consumer-credit-sensitive finance names can be secondary, not first.
```

**实现思路**

给 symbol 增加简单行业/商业模式标签：

```json
{
  "GS": ["large_investment_bank", "volatility_beneficiary"],
  "JPM": ["large_bank", "trading_revenue_beneficiary"],
  "AXP": ["payments", "consumer_credit_sensitive"]
}
```

当 `macro_panic = true` 时，在 prompt 里附加：

```text
Do not treat all financial stocks as identical. GS/JPM may benefit from volatility;
AXP has more consumer-credit sensitivity.
```

权限边界：只改变 DeepSeek 的 reasoning/context，不做硬排序器；如果未来要做 Buy/Add Nudge，可只在 F6 已经 buy/add GS/JPM 时轻微增加 target。

---

### 点三：BA 是“非致命宏观错杀 + 交付/订单复苏线索”，不能只用跌幅解释

**学到的东西**

BA 是默认区间最大 hindsight winner：

- `2025-04-07` buy open 到 `2025-06-09` peak close，63d oracle return 约 `+64.72%`；
- 4 月初大跌主因是 macro/tariff panic，不是新一轮 safety grounding；
- 后续 BA Q1 亏损缩窄、交付改善、订单/交付韧性进一步确认复苏逻辑。

这里真正要学的是：

```text
panic drawdown + 非致命外部冲击 + backlog/delivery/order recovery clues
```

不是简单地“跌很多就买”。

**DeepSeek Flash mock 结果**

- Case: `P3_ba_nonfatal_panic_plus_recovery`
- 结果：通过
- DeepSeek 选择：`2025-04-07`, `BA`, `buy`, confidence `0.85`
- 优先级：提高到 `P1`

DeepSeek 能做到：不等到 4/23 财报确认后才追，而是在 panic zone 识别 BA 的非致命错杀。

**建议加入的提示词**

```text
For BA-like aerospace recovery names, a large drawdown is buyable only when the
shock is nonfatal and externally driven, while backlog, deliveries, order pipeline,
or operational recovery clues remain intact. Do not wait for the whole recovery
to be confirmed if the panic is broad and the company-specific thesis is not broken.
Prefer small-to-medium buy/add in the panic zone, then hold/add if later delivery
or earnings evidence confirms.
```

**实现思路**

增加 `company_recovery_clues` 字段，不需要复杂 agent：

```json
{
  "symbol": "BA",
  "shock_type": "macro_tariff",
  "company_impairment": false,
  "recovery_clues": ["backlog_intact", "delivery_cadence_stable", "order_pipeline"]
}
```

触发逻辑：

```text
macro_panic = true
symbol_drawdown_20d <= -0.20
company_impairment_news = false
recovery_clues 非空
```

权限边界：P1，不作为第一优先级硬模块；先作为 evidence card。若 DeepSeek/F6 原本已选 BA，可支持更高 confidence 或更耐心持有。

---

### 点四：MSFT/质量股的买点是“回撤稳定后、财报确认前”

**学到的东西**

MSFT 的 oracle 买点不是最恐慌的 4/7，而是 `2025-04-21 ~ 2025-04-24`。这时市场已经从 panic 里开始稳定，但 MSFT 还没有 4/30 财报后的确认跳涨。可见线索是：

- 前期随市场回撤；
- 20d drawdown 约 8%-12%，但不是公司 thesis broken；
- cloud/AI demand 线索仍在；
- 即将发布财报；
- 买在财报后就变成追涨。

**DeepSeek Flash mock 结果**

- Case: `P4_quality_earnings_setup_msft`
- 结果：通过
- DeepSeek 选择：`2025-04-21`, `MSFT`, `buy`, confidence `0.85`
- 优先级：提高到 `P1`

**建议加入的提示词**

```text
For high-quality cloud/AI compounders, the best buy may come after the market
panic has started to stabilize but before earnings confirmation. Look for:
market-driven pullback, moderate 20d drawdown, no company-specific thesis break,
upcoming earnings, and visible demand clues around cloud/AI. Avoid buying only
after the post-earnings gap because much of the edge is gone.
```

**实现思路**

增加 `quality_earnings_setup` evidence：

```json
{
  "symbol": "MSFT",
  "quality_tags": ["cloud", "ai", "mega_cap_quality"],
  "drawdown_20d": -0.085,
  "market_panic_stabilizing": true,
  "upcoming_earnings_days": 7,
  "company_thesis_broken": false
}
```

触发条件建议：

```text
quality_tags 包含 cloud/ai/mega_cap_quality
-0.15 <= drawdown_20d <= -0.05
upcoming_earnings_days in [3, 10]
company_thesis_broken = false
```

权限边界：只对 F6 原候选做 confidence boost；不要自动新增仓位，避免财报赌博。

---

### 点五：UNH 式 idiosyncratic capitulation 要作为风险保护，不要误学成买点

**学到的东西**

UNH 在 `2025-05-15/16` 有短期 hindsight rebound，但背景是 DOJ/Medicare Advantage 调查、监管和治理风险。这和 4 月 tariff panic 完全不同：

- universe 不是 panic；
- 单票 20d drawdown 极端；
- 新闻是公司特异性监管/法律风险；
- 后续有反弹不代表当时应该高优先级买入。

这个点非常重要：反推学习不能只看 future return，否则会把坏样本学成买入规则。

**DeepSeek Flash mock 结果**

- Case: `P5_unh_idiosyncratic_capitulation_guard`
- 结果：通过
- DeepSeek 选择：`no_buy`, `UNH`, confidence `0.90`
- 优先级：提高到 `P0 risk guard`

**建议加入的提示词**

```text
Separate macro panic from idiosyncratic impairment. A single-stock collapse on
DOJ, regulatory, fraud, Medicare investigation, accounting, safety, or governance
news is not the same as broad market panic. Even if a rebound is possible, downgrade
from buy to small_watch/no_buy until there is clarification, analyst risk reset,
company rebuttal, or position size can be kept tiny.
```

**实现思路**

增加硬风险标签，但仍建议先作为 prompt 约束：

```json
{
  "idiosyncratic_impairment_tags": ["DOJ", "regulatory_investigation", "fraud_allegation"],
  "universe_panic": false,
  "allowed_decision_bias": "no_buy_or_small_watch"
}
```

触发条件：

```text
idiosyncratic_impairment_tags 非空
universe_panic = false
```

权限边界：这是唯一建议优先做成强约束的点；至少 prompt 中必须明确禁止 DeepSeek 把 UNH 式暴雷当成 high-conviction rebound buy。

## 2. DeepSeek Flash mock 汇总

| 点 | case | DeepSeek 是否通过 | DeepSeek 选择 | 调整后优先级 |
|---|---|---:|---|---|
| 宏观 panic rebound | P1 | yes | 2025-04-09, BA/GS, buy | P0 |
| 金融波动率受益 | P2 | yes | 2025-04-07, GS, buy | P0 |
| BA 非致命错杀 + 复苏 | P3 | yes | 2025-04-07, BA, buy | P1 |
| MSFT quality earnings setup | P4 | yes | 2025-04-21, MSFT, buy | P1 |
| UNH idiosyncratic guard | P5 | yes | no_buy | P0 risk guard |

结论：DeepSeek Flash 对这些 prompt 规则的理解能力是够的。下一步不应该先做复杂 agent，而应该把这些规则包装成简洁、可解释的 evidence card，并保持低权限。

## 3. 推荐继承顺序

### 第一优先级：Reverse Oracle Evidence Card

组合点一、点二、点五。它最容易实现、风险最低、且 DeepSeek mock 表现最好。

输入给 DeepSeek：

```json
{
  "reverse_oracle_evidence": {
    "universe_5d_avg_return": -0.0811,
    "panic_breadth_5d": 0.70,
    "below_20d_ma_share": 0.95,
    "macro_shock_tags": ["tariff", "policy_uncertainty"],
    "policy_relief_tags": ["pause", "negotiation"],
    "financial_volatility_beneficiary_symbols": ["GS", "JPM"],
    "idiosyncratic_impairment_symbols": []
  }
}
```

只改 prompt，不改 order generation。

### 第二优先级：Buy/Add Nudge Buy/Add Nudge

仅当 F6/DeepSeek 原始决策已经是 buy/add 时启用：

```text
if macro_panic and not idiosyncratic_impairment and symbol in F6_buy_or_add:
    allow confidence/target_cash small boost
```

建议 boost 上限：`+10% ~ +20% target_cash_amount`，并且只限 BA/GS/JPM/AMZN/AAPL/MSFT 这类非致命 panic/recovery 标的。

### 第三优先级：Quality Earnings Setup Quality Earnings Setup Card

先只服务 MSFT/IBM/AMZN 这类质量科技股，且只在财报前 3-10 天提示，不做硬买入。

## 4. 本地新闻缓存问题

当前 `news_by_day` 对 4 月/5 月关键窗口覆盖不足，DeepSeek mock 使用的是整理后的公开事件线索，不是完整本地新闻缓存。因此如果要进入真实回测，需要 targeted pre-cache：

```text
symbols: BA, GS, JPM, AXP, AMZN, AAPL, MSFT, UNH
range: 2025-04-01 ~ 2025-05-20
```

建议命令方向：

```bash
STOCKBENCH_DATA_CACHE_DIR="$HOME/.cache/stockbench/data-cache" \
.venv/bin/python -m stockbench.apps.pre_cache \
  --cfg config.yaml \
  --start 2025-04-01 \
  --end 2025-05-20 \
  --symbols BA,GS,JPM,AXP,AMZN,AAPL,MSFT,UNH \
  --include-prices false \
  --include-news true \
  --include-financials false \
  --include-indicators false \
  --include-corp-actions false
```

## 5. 外部事件来源

- CNBC, 2025-04-09, Trump 90-day tariff pause: https://www.cnbc.com/2025/04/09/trump-announces-90-day-tariff-pause-for-at-least-some-countries.html
- CBS News, 2025-04-09, stocks soar after tariff pause: https://www.cbsnews.com/news/stock-market-today-dow-jones-china-tariffs-trump-04-09-25/
- BBC, 2025-04-09, US stocks make historic gains after tariff pause: https://www.bbc.com/news/articles/cgrggqydxv5o
- Euronews, 2025-04-23, Boeing losses narrow/deliveries increase: https://www.euronews.com/business/2025/04/23/boeing-sees-losses-narrow-shares-soar-as-jet-deliveries-increase
- Seattle Times, 2025-05, Boeing April deliveries: https://www.seattletimes.com/business/boeing-aerospace/boeing-delivered-45-planes-in-april-including-two-to-china/
- Goldman Sachs Q1 2025 earnings release: https://www.sec.gov/Archives/edgar/data/886982/000119312525079625/d750054dex991.htm
- CNBC, 2025-04-30, Microsoft Q3 earnings/Azure: https://www.cnbc.com/2025/04/30/microsoft-msft-q3-earnings-report-2025.html
- Microsoft FY25 Q3 release: https://news.microsoft.com/source/2025/04/30/microsoft-cloud-and-ai-strength-drives-third-quarter-results-2/
- CNBC, 2025-05-15, UnitedHealth DOJ investigation report: https://www.cnbc.com/2025/05/15/unitedhealth-group-stock-doj-investigation-report.html

## 6. 下一步执行计划

### 6.1 不建议一次全开只跑一次

下一阶段应基于 DeepSeek Flash + F6 做分模块实验。代码可以统一实现成 feature flags，但实验必须拆开跑，否则无法判断是哪个规则有效、哪个规则互相抵消。

### 6.2 必须先建立 DeepSeek 版 F6 baseline

第一组先跑：

```text
F6_DEEPSEEK_BASELINE_FULL
```

原因：此前 F6 最优结论不应直接迁移到 DeepSeek Flash。所有 reverse-oracle 实验都应和 DeepSeek 版 F6 baseline 比较。

建议命令形态：

```bash
bash scripts/run_benchmark.sh \
  --use-deepseek \
  --start-date 2025-03-01 \
  --end-date 2025-06-30 \
  --strategy llm_decision \
  --data-mode offline_only
```

后续实现 run-id 覆盖时使用：

```text
F6_DEEPSEEK_BASELINE_FULL
```

### 6.3 建议实验拆分

| 顺序 | 实验 | 开关 | 权限 | 目的 |
|---:|---|---|---|---|
| 0 | F6_DEEPSEEK_BASELINE_FULL | 全关 | baseline | 建立 DeepSeek 参照组 |
| 1 | REVERSE_ORACLE_EVIDENCE_CARD | evidence_card=true | 只提示 | 验证 macro panic rebound 证据是否改善 DeepSeek 判断 |

注：其他变体（idiosyncratic guard、buy/add nudge、quality earnings setup）在首次实验中未通过，已从主实现中移除，相关实验记录见第 8 节。

### 6.4 当前 config flags

```yaml
reverse_oracle:
  enabled: false
  evidence_card: false
  panic_breadth_threshold: 0.50
  below_20d_ma_share_threshold: 0.70
  universe_5d_avg_return_threshold: -0.05
```

### 6.5 Worktree 建议

开发可在当前分支统一完成；实验时建议每组一个 worktree，方便隔离 logs/reports/LLM cache：

```text
stockbench-f6-deepseek-baseline
stockbench-f10a-evidence-card
```

所有 worktree 共享数据缓存：

```bash
export STOCKBENCH_DATA_CACHE_DIR="$HOME/.cache/stockbench/data-cache"
export PYTHON_BIN=/home/terence/code/stockbench/.venv/bin/python
```

LLM cache、logs、reports 保持 worktree-local，避免互相污染。

### 6.6 下一步产生优先级

1. 实现 `reverse_oracle_evidence_card` 计算和 prompt 注入。
2. 做短区间 smoke test，确认 DeepSeek Flash 调用和 prompt 格式正常。
3. 跑 `F6_DEEPSEEK_BASELINE_FULL`。
4. 跑 `REVERSE_ORACLE_EVIDENCE_CARD`。
5. 若相对 baseline 有正向迹象，再考虑后续优化。

## 7. 集成状态与开跑命令

已集成的代码入口：

```text
stockbench/core/reverse_oracle.py
stockbench/agents/dual_agent_llm.py
stockbench/apps/run_backtest.py
scripts/run_benchmark.sh
config.yaml
```

默认 `config.yaml` 中全部关闭，因此仍保持 F6 baseline 行为：

```yaml
reverse_oracle:
  enabled: false
  evidence_card: false
```

### F6 DeepSeek baseline

```bash
RUN_ID_OVERRIDE=F6_DEEPSEEK_BASELINE_FULL \
bash scripts/run_benchmark.sh \
  --use-deepseek \
  --start-date 2025-03-01 \
  --end-date 2025-06-30 \
  --data-mode offline_only
```

### Reverse Oracle Evidence Card

```bash
RUN_ID_OVERRIDE=REVERSE_ORACLE_EVIDENCE_CARD \
bash scripts/run_benchmark.sh \
  --use-deepseek \
  --start-date 2025-03-01 \
  --end-date 2025-06-30 \
  --data-mode offline_only \
  --reverse-oracle-evidence-card
```

## 8. DeepSeek full-run 实验结果

本轮最终继承的方法名为：**Reverse Oracle Evidence Card**。不再使用编号命名。

实验范围：默认 20 股票池，`2025-03-01 ~ 2025-06-30`，DeepSeek Flash，dual agent，offline_only。

| 方法 | 累计收益 | 最大回撤 | Sharpe | Sortino | 交易数 | 结论 |
|---|---:|---:|---:|---:|---:|---|
| F6 DeepSeek baseline | +1.57% | -11.61% | 0.307 | 0.0247 | 517 | 对照组 |
| **Reverse Oracle Evidence Card** | **+3.08%** | -13.38% | **0.437** | **0.0371** | 458 | **继承** |
| Reverse Oracle Evidence Card + idiosyncratic guard | +2.08% | -12.22% | 0.349 | 0.0287 | 477 | 暂不继承，新闻覆盖不足时约束噪声偏大 |
| Reverse Oracle Buy/Add Nudge | +1.22% | -14.02% | 0.268 | 0.0229 | 552 | 不继承，放大回撤和交易数 |
| Reverse Oracle Quality Earnings Setup | +0.85% | -13.55% | 0.234 | 0.0195 | 438 | 不继承，单独加入无增益 |

对应输出位于 Reverse Oracle Evidence Card 实验 worktree 的最新 `storage/reports/backtest/` 目录。

### 8.1 继承实现

保留并提交：

```yaml
reverse_oracle:
  enabled: false
  evidence_card: false
```

正式启用方式：

```bash
RUN_ID_OVERRIDE=REVERSE_ORACLE_EVIDENCE_CARD \
bash scripts/run_benchmark.sh \
  --use-deepseek \
  --start-date 2025-03-01 \
  --end-date 2025-06-30 \
  --data-mode offline_only \
  --reverse-oracle-evidence-card
```

实现边界：

- 只向 DeepSeek decision prompt 注入 `reverse_oracle_evidence`；
- 不直接改订单；
- 不直接改仓位；
- 不自动新增股票；
- 让模型在 panic rebound 窗口更好识别 BA/GS/JPM/AMZN/AAPL/MSFT 等候选。

实验结论：该方法显著提高 DeepSeek 版 F6 的收益、Sharpe 和 Sortino，但最大回撤略有扩大。后续优化方向不是启用 nudge，而是在 Evidence Card 内增加更温和的风险提示。
