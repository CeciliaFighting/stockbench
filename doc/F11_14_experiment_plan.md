# F11 十四组低权限实验计划

## 1. 背景与总原则

F10 之后，当前项目进入瓶颈期：F6 仍是最强主基线，继续叠加 rebound、winner hold、risk budget、smart no-trade band 等模块时，普遍出现信息有效但预测力不足、soft tag 不改变订单、或执行约束过强错过反弹的问题。

因此 F11 不再做高权限模块，而是一次性拆成 14 个低权限单模块实验。所有 F11 实验都必须从同一个 base 出发：

```text
F11_BASE = F6 = F5_COOLDOWN_5D
         = FUND1 cleaned fundamental
         + anti-overtrade memory
         + 5D cooldown

period = 2025-03-03 to 2025-06-30
benchmark = 20-stock equal-weight Buy & Hold
BH20 return = +0.7348%
BH20 max drawdown = -14.9520%
model = deepseek-v4-flash
agent_mode = dual
reflection_agent = false
data_mode = offline_only
```

F11 的统一权限边界：

```text
允许：
  prompt context
  memory retrieval
  low-permission sizing multiplier
  buy/add budget
  soft cooldown
  logging and attribution

禁止：
  hard sell blocking
  forced buy blocking
  forced sell
  regime hard-switch
  quant signal replacement
  full optimizer
  simulator/evaluator 大改
```

核心判断标准：

```text
第一目标：是否优于 F6
第二目标：是否优于 BH20
第三目标：是否改善 MDD / Sharpe / Sortino / trades quality
第四目标：模块触发是否真实改变 prompt、memory retrieval、size 或 budget
```

## 2. F11 实验矩阵

| 编号 | 实验名 | 类型 | 改动层 | 权限 | 主要目的 |
| --- | --- | --- | --- | --- | --- |
| F11A | M2_EVENT_LEVEL_MISTAKE_MEMORY | memory | 记忆层 / prompt context | 只提示，不改订单 | 用具体事件级错误替代 generic reflection |
| F11B | M3_EXPIRING_MEMORY | memory | 记忆检索层 | 只过滤过期记忆 | 防止旧记忆污染当前决策 |
| F11C | M4_COUNTERFACTUAL_TRADE_MEMORY | memory | 交易后归因 / prompt context | 只提示，不改订单 | 记录如果不交易会怎样，减少低质量买卖 |
| F11D | M5_STATE_CONDITIONED_MEMORY | memory | 记忆检索层 | 只过滤相似状态记忆 | 避免不相关记忆误导 LLM |
| F11E | I2_NEWS_PRICE_CONFIRMATION | information | 新闻/价格确认 context | 只提示，不改订单 | 防止追逐未被价格确认的新闻 |
| F11F | I3_FUNDAMENTAL_RELIABILITY_TAG | information | 基本面可靠性 context | 只提示，不改数值 | 避免过度依赖陈旧/缺失基本面 |
| F11G | I4_SIGNAL_CONSENSUS_SCORE | information + sizing | 信号一致性 / buy-add sizing | 低一致性只轻微降 buy/add size | 让 LLM 识别多源信号冲突 |
| F11H | I5_UNIVERSE_RELATIVE_STRENGTH_CONTEXT | information | 股票池相对强弱 context | 只提示，不改订单 | 用横截面强弱替代单纯绝对 momentum |
| F11I | R2_CONFIDENCE_WEIGHTED_SIZING | risk/execution | 置信度映射 size | 只改 size，不改方向 | 让低置信交易更小，高置信 buy 适度更大 |
| F11J | R3_SOFT_POSITION_CROWDING_PENALTY | risk/execution | 持仓拥挤度 size penalty | 只降低加仓 size | 避免大仓位继续过度集中 |
| F11K | R4_STATE_DEPENDENT_COOLDOWN | risk/execution | 状态依赖 cooldown | buy/add 降 size，sell 仅 soft | 改进 F6 固定 cooldown |
| F11L | R5_WEEKLY_TRADE_BUDGET | risk/execution | 组合级周度 buy/add budget | 限制新增风险，不限 sell | 控制过度交易但保留风控卖出 |
| F11M | R6_DRAWDOWN_CONTEXT_PROMPT | risk context | 组合回撤 prompt | 只提示，不改订单 | 让 LLM 感知组合回撤但不 hard risk-off |
| F11N | R7_SOFT_WINNER_HOLDING_FRICTION | risk/execution | 短持有 winner sell friction | 低置信 sell 降 size | 减少短期卖飞盈利持仓 |

## 3. 单组实验设计

### F11A / M2_EVENT_LEVEL_MISTAKE_MEMORY

目标：用具体事件级错误记忆替代 generic reflection。

触发与生成记忆：

```text
outcome_horizon_days = 5
expiry_days = 15
max_memories_per_symbol = 3
underperformance_threshold = 0.02

mistake types:
  premature_averaging_down
  premature_profit_taking
  chasing_weak_rebound
```

决策时用法：

```text
[Event-Level Mistake Memory]
只展示同 symbol / 相似 action-state 的 active memories
不 override action
不 hard block buy/sell
```

预期：若有效，应减少 add loser 和低置信 profit taking；交易数可能下降，但不应像 F10Fplus 那样压得过低。

主要归因指标：

```text
memory_created_count
memory_retrieved_count
mistake_type_distribution
affected_symbol_count
future_return_after_retrieved_memory
return/MDD/Sharpe/trades vs F6
```

### F11B / M3_EXPIRING_MEMORY

目标：防止旧记忆污染当前决策。

设计：

```text
default_expiry_days = 15
expiry_by_mistake_type:
  premature_averaging_down = 15
  premature_profit_taking = 10
  chasing_weak_rebound = 15
  overtrade = 10
expire_on_regime_change = true
```

注意：M3 单独跑可能是 no-op。如果当前运行没有新 memory 产生，则单组结果主要验证 expiry 机制与日志，不应强行解释收益。

主要归因指标：

```text
active_memory_count
expired_memory_count
archived_memory_count
retrieved_memory_count
```

### F11C / M4_COUNTERFACTUAL_TRADE_MEMORY

目标：记录“如果当时不交易会怎样”，避免重复低质量买入或过早卖出。

生成规则：

```text
SELL/REDUCE 后 5d counterfactual return > +2%:
  生成 premature sell lesson

BUY/ADD 后 5d return < -2%
或跑输 universe median 超过 2%:
  生成 low-quality entry lesson
```

决策时用法：

```text
[Counterfactual Trade Memory]
只提示，不改订单方向和 size
```

风险：和 M2 有重叠。单跑 F11C 用于验证 counterfactual lesson 是否比普通 mistake memory 更精确。

### F11D / M5_STATE_CONDITIONED_MEMORY

目标：记忆只有在当前状态相似时才检索，避免错误泛化。

相似度特征：

```text
same symbol
same proposed action type
same position_pnl_sign
same 5d momentum sign
same 20d momentum sign
same position_weight_bucket
same regime_tag, if available

similarity_threshold = 3
max_retrieved_memories = 3
```

注意：F11D 单独跑可能是 no-op；更有价值的是和 M2/M4 组合跑。

### F11E / I2_NEWS_PRICE_CONFIRMATION

目标：防止新闻过度反应。

提示逻辑：

```text
positive news + 1d/5d price not positive:
  warning: positive news is not confirmed by price

negative news + price stable:
  note: avoid panic selling unless risk evidence is strong

negative news + price weakness:
  note: cautious with new buy/add
```

缺失数据 fallback：

```text
no news: log missing_news, add no context
no volume: skip volume confirmation
```

风险：当前 offline cache 新闻可能稀疏，F11E 可能触发不足。若触发低，不应简单判定方向失败。

### F11F / I3_FUNDAMENTAL_RELIABILITY_TAG

目标：让 LLM 知道基本面数据是否陈旧或缺失。

可靠性：

```text
high:
  data_age_days <= 90 and missing_ratio < 20%
medium:
  data_age_days <= 180 and missing_ratio < 40%
low:
  data_age_days > 180 or missing_ratio >= 40%
unknown:
  timestamp unavailable and cannot infer age
```

用法：

```text
[Fundamental Reliability Context]
Do not overweight stale or incomplete fundamentals.
```

预期：减少对不可靠 fundamentals 的过度解释。由于 F6 的 cleaned fundamental 已有效，F11F 不能高权限削弱 fundamental，只能提示 reliability。

### F11G / I4_SIGNAL_CONSENSUS_SCORE

目标：总结 fundamental、momentum、news、position PnL 的方向一致性。

计算：

```text
fundamental_direction = bullish/bearish/neutral/unknown
momentum_direction = bullish if 5d > 0 and 20d > 0
news_direction = bullish/bearish/neutral/unknown
position_pnl_direction = winning/losing/flat/no_position

agreement_score = abs(sum(nonzero signals)) / number_of_nonzero_signals
if fewer than 2 nonzero signals:
  agreement_score = 0.5
  direction = mixed/uncertain
```

低权限 sizing：

```text
if agreement_score < 0.4:
  BUY/ADD size_multiplier = 0.8
SELL size unchanged
```

风险：如果 signal consensus 太粗糙，可能重复 F5/F10 的“信息有用但预测不够准”问题。因此只允许轻微 size haircut。

### F11H / I5_UNIVERSE_RELATIVE_STRENGTH_CONTEXT

目标：提供股票池内相对强弱，而不是只看绝对涨跌。

计算：

```text
lookbacks = [1, 5, 20]
relative_5d = symbol_5d_return - universe_median_5d_return
relative_20d = symbol_20d_return - universe_median_20d_return
rank_bucket = top_quartile / above_median / below_median / bottom_quartile
```

用法：

```text
[Universe Relative Strength Context]
只提示，不改变 action 或 size
```

预期：这是 F10A/B rebound 方向的更稳健替代版。它不直接说“买 rebound”，只告诉 LLM 横截面强弱。

### F11I / R2_CONFIDENCE_WEIGHTED_SIZING

目标：把 LLM confidence 映射为交易 size，但不改变 action direction。

规则：

```text
default_confidence = 0.5

BUY:
  confidence < 0.4: multiplier = 0.5
  0.4 <= confidence < 0.7: multiplier = 1.0
  confidence >= 0.7: multiplier = 1.2

ADD:
  confidence < 0.4: multiplier = 0.3
  0.4 <= confidence < 0.7: multiplier = 0.8
  confidence >= 0.7: multiplier = 1.0

SELL/REDUCE:
  confidence < 0.4: multiplier = 0.5
  confidence >= 0.4: multiplier = 1.0
```

风险：如果 LLM confidence 不稳定，可能放大噪声。因此必须记录 parsed confidence，并允许 missing confidence fallback 到 0.5。

### F11J / R3_SOFT_POSITION_CROWDING_PENALTY

目标：避免已有大仓位继续被过度加仓。

规则：

```text
position_weight > 8%: multiplier = 0.7
position_weight > 10%: multiplier = 0.5
position_weight > 12%: multiplier = 0.3 unless confidence >= 0.7
```

边界：

```text
只作用于 BUY/ADD that increase exposure
不强制卖出
不阻止 risk-reducing trades
```

预期：可能改善 MDD，但有压制 winner 的风险。需要特别看 BA/MSFT/IBM/GS/HON 的 exposure 是否被误伤。

### F11K / R4_STATE_DEPENDENT_COOLDOWN

目标：把 F6 的固定 5D cooldown 改成更细的状态依赖 cooldown。

规则：

```text
add_to_loser cooldown = 7 trading days
add_to_winner cooldown = 3 trading days
new_buy_after_sell cooldown = 5 trading days
sell_after_buy cooldown = 5 trading days, soft only

buy_add_cooldown_multiplier = 0.5
sell_cooldown_multiplier = 0.7
protective sell is not restricted
```

关键假设：F6 的 5D cooldown 有效，但可能过于一刀切。F11K 测试“少加 loser，多允许 winner”的细化是否更好。

### F11L / R5_WEEKLY_TRADE_BUDGET

目标：组合级控制 buy/add 频率，保留 sell 灵活性。

规则：

```text
weekly_buy_add_budget = 8
SELL/REDUCE unlimited

if budget exceeded:
  confidence >= 0.7: multiplier = 0.7
  confidence < 0.7: multiplier = 0.2
```

风险：如果 budget 太紧，可能重复 F10Fplus 的问题，把有效纠错压掉。因此 F11L 要重点看 5-6 月反弹参与。

### F11M / R6_DRAWDOWN_CONTEXT_PROMPT

目标：让 LLM 感知组合回撤，但不做 hard risk-off。

规则：

```text
drawdown > -5%:
  no note

-8% < drawdown <= -5%:
  moderate drawdown note

drawdown <= -8%:
  severe drawdown note

if drawdown improving for 3 consecutive trading days:
  soften warning
```

预期：比 F10G 更低权限。F10G 失败说明风险预算直接压仓会伤收益，F11M 只做 prompt context。

### F11N / R7_SOFT_WINNER_HOLDING_FRICTION

目标：减少短持有盈利仓位的过早卖出。

规则：

```text
for SELL/REDUCE:
  position PnL > 0
  holding period < 5 trading days
  no explicit negative catalyst / risk-control reason

then:
  sell_size_multiplier = 0.5
  unless confidence >= 0.8
  or reason contains risk keyword
```

和 F10D 的区别：

```text
F10D 试图识别 confirmed winner，tag 很多但真正保护 sell 很少；
F11N 只处理“盈利 + 短持有 + 无风险理由”的小场景；
它不是 winner gate，只是 short-term profit-taking friction。
```

## 4. 推荐运行顺序

优先级按“实现风险低、解释价值高、最可能接近 F6”排序：

```text
第一批：信息 context，低风险
1. F11H_I5_UNIVERSE_RELATIVE_STRENGTH_CONTEXT
2. F11F_I3_FUNDAMENTAL_RELIABILITY_TAG
3. F11M_R6_DRAWDOWN_CONTEXT_PROMPT
4. F11E_I2_NEWS_PRICE_CONFIRMATION

第二批：低权限 sizing / budget
5. F11I_R2_CONFIDENCE_WEIGHTED_SIZING
6. F11J_R3_SOFT_POSITION_CROWDING_PENALTY
7. F11K_R4_STATE_DEPENDENT_COOLDOWN
8. F11L_R5_WEEKLY_TRADE_BUDGET
9. F11N_R7_SOFT_WINNER_HOLDING_FRICTION
10. F11G_I4_SIGNAL_CONSENSUS_SCORE

第三批：memory 系列，成本高且需要 outcome lag
11. F11A_M2_EVENT_LEVEL_MISTAKE_MEMORY
12. F11C_M4_COUNTERFACTUAL_TRADE_MEMORY
13. F11B_M3_EXPIRING_MEMORY
14. F11D_M5_STATE_CONDITIONED_MEMORY
```

说明：

```text
M3/M5 单跑可能 no-op；
它们更适合作为 memory combo 的机制验证；
若 API 成本有限，应先跑 F11H/F11F/F11M/F11I/F11K/F11N。
```

## 5. 组合实验预案

14 组单模块跑完后，再考虑组合，不建议一开始跑 full combo。

建议组合：

```text
COMBO_MEMORY_M2_M3_M5:
  M2_EVENT_LEVEL_MISTAKE_MEMORY
  M3_EXPIRING_MEMORY
  M5_STATE_CONDITIONED_MEMORY

COMBO_COUNTERFACTUAL_M3_M4_M5:
  M3_EXPIRING_MEMORY
  M4_COUNTERFACTUAL_TRADE_MEMORY
  M5_STATE_CONDITIONED_MEMORY

COMBO_RISK_R2_R4_R7:
  R2_CONFIDENCE_WEIGHTED_SIZING
  R4_STATE_DEPENDENT_COOLDOWN
  R7_SOFT_WINNER_HOLDING_FRICTION

COMBO_ALL_LOW_PERMISSION:
  M2_EVENT_LEVEL_MISTAKE_MEMORY
  M3_EXPIRING_MEMORY
  M5_STATE_CONDITIONED_MEMORY
  I3_FUNDAMENTAL_RELIABILITY_TAG
  I4_SIGNAL_CONSENSUS_SCORE
  I5_UNIVERSE_RELATIVE_STRENGTH_CONTEXT
  R2_CONFIDENCE_WEIGHTED_SIZING
  R4_STATE_DEPENDENT_COOLDOWN
  R6_DRAWDOWN_CONTEXT_PROMPT
  R7_SOFT_WINNER_HOLDING_FRICTION
```

不建议放入 all combo：

```text
I2_NEWS_PRICE_CONFIRMATION, unless news coverage is verified
R3_SOFT_POSITION_CROWDING_PENALTY, because it may cap winners
R5_WEEKLY_TRADE_BUDGET, because it may repeat F10Fplus over-filtering
```

## 6. 配置与日志要求

建议每个实验对应一个 config preset：

```text
configs/experiments/F11A_M2_EVENT_LEVEL_MISTAKE_MEMORY.yaml
configs/experiments/F11B_M3_EXPIRING_MEMORY.yaml
configs/experiments/F11C_M4_COUNTERFACTUAL_TRADE_MEMORY.yaml
configs/experiments/F11D_M5_STATE_CONDITIONED_MEMORY.yaml
configs/experiments/F11E_I2_NEWS_PRICE_CONFIRMATION.yaml
configs/experiments/F11F_I3_FUNDAMENTAL_RELIABILITY_TAG.yaml
configs/experiments/F11G_I4_SIGNAL_CONSENSUS_SCORE.yaml
configs/experiments/F11H_I5_UNIVERSE_RELATIVE_STRENGTH_CONTEXT.yaml
configs/experiments/F11I_R2_CONFIDENCE_WEIGHTED_SIZING.yaml
configs/experiments/F11J_R3_SOFT_POSITION_CROWDING_PENALTY.yaml
configs/experiments/F11K_R4_STATE_DEPENDENT_COOLDOWN.yaml
configs/experiments/F11L_R5_WEEKLY_TRADE_BUDGET.yaml
configs/experiments/F11M_R6_DRAWDOWN_CONTEXT_PROMPT.yaml
configs/experiments/F11N_R7_SOFT_WINNER_HOLDING_FRICTION.yaml
```

统一日志字段：

```text
date
symbol
module_name
triggered
prompt_context_added
original_action
final_action
original_size
size_multiplier
final_size
confidence
reason
metadata
```

每组必须额外记录：

```text
module_intervention_count
prompt_context_count
size_modified_count
budget_modified_count
memory_created_count
memory_retrieved_count
no_op_count
missing_data_count
```

## 7. 评估与报告格式

每组输出统一表：

| Experiment | Return | Excess vs BH20 | MDD | Sharpe | Sortino | Trades | Trades Notional | Intervention Count | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |

单组判断模板：

```text
若 return > F6 且 MDD 不差于 F6：
  进入主候选

若 return 接近 F6 且 MDD 明显改善：
  进入风险候选

若 return 低于 F6 但明显优于 BH20 且机制解释清楚：
  保留为诊断模块

若 return 低于 BH20 或 trades 被压到极低：
  判定失败

若模块 no-op：
  不做收益结论，只做接入结论
```

重点归因问题：

```text
1. 模块是否真的触发？
2. 是否改变 prompt / size / budget / memory retrieval？
3. 改变的订单后续 5d/10d 表现是否更差或更好？
4. 是否误伤 BA/HON/IBM/MSFT/GS 这类 winner exposure？
5. 是否错过 2025-05 至 2025-06 反弹？
6. 是否只是降低交易数而压制 alpha？
```

## 8. 当前建议

F11 的第一批最值得先跑：

```text
F11H_I5_UNIVERSE_RELATIVE_STRENGTH_CONTEXT
F11F_I3_FUNDAMENTAL_RELIABILITY_TAG
F11M_R6_DRAWDOWN_CONTEXT_PROMPT
F11I_R2_CONFIDENCE_WEIGHTED_SIZING
F11K_R4_STATE_DEPENDENT_COOLDOWN
F11N_R7_SOFT_WINNER_HOLDING_FRICTION
```

原因：

```text
这些模块权限最低，和 F10 的失败模式距离最远；
不依赖 future outcome memory；
不强行阻断 buy/sell；
最有希望在 F6 基础上做小幅改善，而不是重新发明高权限策略。
```

不建议第一批就跑：

```text
M2/M3/M4/M5 memory 系列：
  需要 outcome lag 和 memory store，接入成本高，且容易 no-op；

R5 weekly trade budget：
  可能重复 F10Fplus 的过度过滤问题；

R3 crowding penalty：
  可能误伤 winner exposure；

I2 news-price confirmation：
  取决于 offline news cache 覆盖率，若 news 稀疏则解释力弱。
```

## 9. 第一批 F11 实验结果

第一批已完成 6 组实验：

```text
F11H_I5_UNIVERSE_RELATIVE_STRENGTH_CONTEXT
F11F_I3_FUNDAMENTAL_RELIABILITY_TAG
F11M_R6_DRAWDOWN_CONTEXT_PROMPT
F11I_R2_CONFIDENCE_WEIGHTED_SIZING
F11K_R4_STATE_DEPENDENT_COOLDOWN
F11N_R7_SOFT_WINNER_HOLDING_FRICTION
```

统一评估口径：

```text
period = 2025-03-03 to 2025-06-30
benchmark = 20-stock equal-weight Buy & Hold
BH20 return = +0.7348%
BH20 max drawdown = -14.9520%
base = F6 = F5_COOLDOWN_5D
```

### 9.1 结果总表

| Run | Strategy Return | BH20 Return | Excess vs BH20 | Strategy MDD | BH20 MDD | Sharpe | Trades | 判断 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| F6 baseline | +3.99% | +0.73% | +3.26% | -9.16% | -14.95% | 0.557 | 261 | 当前基线 |
| F11H_I5_UNIVERSE_RELATIVE_STRENGTH_CONTEXT | +2.87% | +0.73% | +2.14% | -11.50% | -14.95% | 0.435 | 433 | 不如 F6 |
| F11F_I3_FUNDAMENTAL_RELIABILITY_TAG | +3.78% | +0.73% | +3.05% | -11.15% | -14.95% | 0.540 | 427 | 接近 F6，但回撤/交易更差 |
| F11M_R6_DRAWDOWN_CONTEXT_PROMPT | +0.05% | +0.73% | -0.69% | -13.66% | -14.95% | 0.146 | 341 | 失败 |
| F11I_R2_CONFIDENCE_WEIGHTED_SIZING | +2.76% | +0.73% | +2.03% | -9.84% | -14.95% | 0.450 | 326 | 不如 F6 |
| F11K_R4_STATE_DEPENDENT_COOLDOWN | +3.95% | +0.73% | +3.22% | -10.35% | -14.95% | 0.567 | 418 | 最接近，有研究价值 |
| F11N_R7_SOFT_WINNER_HOLDING_FRICTION | +1.55% | +0.73% | +0.82% | -10.59% | -14.95% | 0.304 | 409 | 基本无效 |

结论：

```text
第一批 F11 没有跑赢 F6。
F11K 是唯一值得继续优化的方向。
F11F 接近 F6，但机制上 reliability 全是 unknown，不能视为强有效模块。
F11M 和 F11N 基本没有形成有效干预。
```

### 9.2 机制触发统计

| Run | 触发统计 | 解释 |
| --- | --- | --- |
| F11H | context_lines = 83, sum_context = 1660 | 每天 20 只都加入了 relative strength context，确认不是 no-op |
| F11F | reliability_lines = 83, last counts = {'high': 0, 'medium': 0, 'low': 0, 'unknown': 20} | 全部为 unknown，说明基本面 timestamp / freshness 信息不足 |
| F11M | drawdown_lines = 83, context_true = 0, levels = ['normal'] | 没有触发 moderate/severe drawdown note，基本 no-op |
| F11I | size_adjust_count = 171, avg_multiplier = 1.039, up = 102, down = 69 | 真实改变 size，但整体偏放大风险 |
| F11K | cooldown_rows = 1366, active = 313, reduced = 313 | 真实触发状态依赖 cooldown，且实际降 size |
| F11N | friction_rows = 597, applied = 0, reduced = 0 | 条件过窄，没有实际干预 |

### 9.3 单组分析

#### F11H_I5_UNIVERSE_RELATIVE_STRENGTH_CONTEXT

F11H 的 context 确实进入 prompt，每个交易日对 20 只股票都生成相对强弱信息。

结果：

```text
return = +2.87%
excess vs BH20 = +2.14%
MDD = -11.50%
Sharpe = 0.435
trades = 433
```

解释：

```text
relative strength context 有信息价值，但它让 LLM 更活跃；
trades 从 F6 的 261 增加到 433；
更多横截面信息没有带来更高 alpha，反而增加噪声交易和回撤。
```

结论：不进入主线。

#### F11F_I3_FUNDAMENTAL_RELIABILITY_TAG

F11F 的结果最接近 F6，但机制解释不够强。

结果：

```text
return = +3.78%
excess vs BH20 = +3.05%
MDD = -11.15%
Sharpe = 0.540
trades = 427
```

机制：

```text
83 天都有 reliability context；
但所有股票 reliability 都是 unknown；
说明当前 fundamental 数据缺少足够的 timestamp / age 信息。
```

解释：

```text
F11F 接近 F6，但不是因为 high/medium/low reliability 分类真的发挥了作用；
更可能是 prompt 中多了一条“不要过度依赖不完整基本面”的保守提醒；
交易数和回撤都高于 F6，因此不能替代 F6。
```

结论：保留为观察方向，但不作为主线。

#### F11M_R6_DRAWDOWN_CONTEXT_PROMPT

F11M 目标是让 LLM 感知组合回撤，但本轮基本没有触发。

结果：

```text
return = +0.05%
excess vs BH20 = -0.69%
MDD = -13.66%
Sharpe = 0.146
trades = 341
```

机制：

```text
drawdown_lines = 83
context_true = 0
levels = ['normal']
```

解释：

```text
整个回测中 drawdown context 都是 normal；
没有 moderate/severe warning 进入 prompt；
因此这组不能证明 drawdown prompt 有效，反而说明当前阈值或 drawdown 字段接入不适合作为 F11 主线。
```

结论：失败，不继续。

#### F11I_R2_CONFIDENCE_WEIGHTED_SIZING

F11I 根据 LLM confidence 调整交易大小。

结果：

```text
return = +2.76%
excess vs BH20 = +2.03%
MDD = -9.84%
Sharpe = 0.450
trades = 326
```

机制：

```text
size_adjust_count = 171
avg_multiplier = 1.039
up = 102
down = 69
```

解释：

```text
模块真实改变了订单 size；
但平均 multiplier 大于 1，说明整体偏向放大高置信 buy；
LLM confidence 未必是稳定 alpha，因此放大高置信交易没有提升收益，反而弱于 F6。
```

结论：不进入主线。若后续重做，应取消 buy high-confidence 1.2x 放大，只保留 low-confidence haircut。

#### F11K_R4_STATE_DEPENDENT_COOLDOWN

F11K 是第一批最有价值的结果。

结果：

```text
return = +3.95%
excess vs BH20 = +3.22%
MDD = -10.35%
Sharpe = 0.567
trades = 418
```

机制：

```text
cooldown_rows = 1366
active = 313
reduced = 313
```

解释：

```text
状态依赖 cooldown 确实触发并改变 size；
收益几乎贴近 F6，Sharpe 略高于 F6；
但 MDD 比 F6 差，trades 从 261 增加到 418；
说明“状态依赖 cooldown”方向有潜力，但当前规则太活跃，未能保持 F6 的低交易与低回撤优势。
```

结论：保留为下一轮优化候选。

下一版建议：

```text
F11K_v2:
  只加强 add_to_loser cooldown；
  不缩短 add_to_winner cooldown 到 3d，避免交易变多；
  sell_after_buy 只提示，不降 size；
  目标是保持 F6 trades 接近 261，而不是升到 418。
```

#### F11N_R7_SOFT_WINNER_HOLDING_FRICTION

F11N 目标是减少盈利短持仓过早卖出，但本轮触发条件太窄。

结果：

```text
return = +1.55%
excess vs BH20 = +0.82%
MDD = -10.59%
Sharpe = 0.304
trades = 409
```

机制：

```text
friction_rows = 597
applied = 0
reduced = 0
```

解释：

```text
模块检查了很多 sell/reduce 场景；
但没有一次满足“盈利 + 持有少于 5 天 + 无风险理由 + 低置信”的组合条件；
因此这组不是证明 winner friction 思路失败，而是证明当前触发条件过窄。
```

结论：当前版本无效。若继续，应放宽为“盈利持仓 + 低置信 reduce/close + 后续趋势未破坏”，而不是限制 holding_days < 5。

### 9.4 第一批 F11 总结

第一批 F11 的经验：

```text
1. 单纯增加 prompt context 容易让 LLM 更活跃，交易数上升，但收益不一定提高。
2. LLM confidence 不能直接当作 alpha 放大器。
3. drawdown prompt 如果没有真实触发，就是 no-op。
4. winner friction 的触发条件不能过窄，否则没有实验意义。
5. 状态依赖 cooldown 是目前最值得继续的 F11 方向，但需要降低交易数和回撤。
```

当前保留判断：

| 模块 | 是否继续 | 处理 |
| --- | --- | --- |
| F11H relative strength context | 否 | 交易过多，弱于 F6 |
| F11F fundamental reliability | 观察 | 接近 F6，但 reliability 全 unknown |
| F11M drawdown context | 否 | no-op，结果失败 |
| F11I confidence sizing | 否 | confidence 放大没有贡献 |
| F11K state cooldown | 是 | 下一轮做 v2 |
| F11N winner friction | 需改触发 | 当前 applied = 0，不解释收益 |

下一步建议优先做：

```text
F11K_v2_STATE_COOLDOWN_NARROW
```

不要立刻做 full combo，因为第一批单模块还没有明确超过 F6 的稳定贡献。

## 10. F11 更新版：暂停原 14 组，改跑最终 10 个收敛变体

第一批 F11 完成后，原始 14 组计划需要收敛。后续不再继续原版 F11A-F11N 的剩余实验，而是暂停它们，改跑约 10 个更窄、更保守的 final F11 variants。

核心原因：

```text
1. prompt-only context 并不天然低风险。
   F11H/F11F 都把 trades 从 F6 的 261 提高到 420+，且收益弱于 F6。

2. LLM confidence 不能当 alpha。
   F11I v1 放大高置信交易，结果弱于 F6。

3. 后续 F11 不能再做 positive reinforcement。
   不允许把 size 放大到超过 F6 原始决策。

4. 所有新模块 size_multiplier 必须 <= 1.0。

5. 大多数模块只允许降低低质量 BUY/ADD。

6. SELL/REDUCE 默认不修改，除非实验明确说明。

7. 避免 full-universe daily context injection。

8. trades 应尽量接近 F6：
   ideal = 240-320
   warning = 320-360
   likely failure = >360 unless return materially improves

9. 当前值得重试的方向只有 F11F 和 F11K：
   F11F：原版 reliability 可能因为 timestamp / reliability 识别问题和 context 注入过宽而失真；
   F11K：state cooldown 有潜力，但必须限制在 weak/loss states。
```

后续统一 base：

```text
period = 2025-03-03 to 2025-06-30
benchmark = BH20
BH20 return = +0.7348%
model = deepseek-v4-flash
agent_mode = dual
reflection_agent = false
data_mode = offline_only
base = F6 / F11 base config
```

### 10.1 全局硬规则

所有 final F11 variants 必须满足：

```text
1. No module may use size_multiplier > 1.0.
2. No module may encourage BUY/ADD.
3. No module may add long daily context to every symbol.
4. Context, if used, must be short, conditional, and warning-only.
5. SELL/REDUCE must not be modified unless explicitly stated.
6. Dry-run mode must not modify prompt or orders.
7. Hard fail if any multiplier > 1.0.
8. Hard fail if dry-run modifies order or prompt.
9. Hard fail if a module modifies SELL/REDUCE when not allowed.
```

统一日志字段：

```text
module_name
date
symbol
action
original_size
multiplier
final_size
triggered
no_op_reason
```

统一实验 summary 必须包含：

```text
total_return
max_drawdown
sharpe
total_trades
BUY_count
ADD_count
SELL_count
REDUCE_count
intervention_count
intervention_rate
average_multiplier_when_triggered
comparison versus F6 trades = 261
```

### 10.2 最终 10 个 F11 变体矩阵

| 编号 | 实验名 | 类型 | 权限 | 是否改订单 | 目的 |
| --- | --- | --- | --- | --- | --- |
| 1 | F11F_v2_FUNDAMENTAL_RELIABILITY_HAIRCUT_ONLY | reliability sizing | BUY/ADD haircut only | 是，仅 BUY/ADD | 低可靠/陈旧/矛盾基本面只降 size |
| 2 | F11F_v2_PROMPT_WARNING_ONLY | reliability prompt | 短 warning only | 否 | 分离 reliability warning 和 sizing 的价值 |
| 3 | F11K_v3_LOSER_COOLDOWN_HAIRCUT_ONLY | cooldown sizing | weak/loss BUY/ADD haircut only | 是，仅 BUY/ADD | 只惩罚失败后继续加弱势仓 |
| 4 | F11K_v3_PROMPT_WARNING_ONLY | cooldown prompt | 短 warning only | 否 | 分离 cooldown warning 和 sizing 的价值 |
| 5 | F11G_v2_SIGNAL_CONFLICT_HAIRCUT_ONLY | signal conflict sizing | BUY/ADD haircut only | 是，仅 BUY/ADD | 多源信号冲突时降低新增风险 |
| 6 | F11J_v2_CROWDING_LOSER_ADD_ONLY | crowding sizing | crowded loser add haircut | 是，仅 BUY/ADD | 只限制拥挤弱仓继续加仓 |
| 7 | F11L_v2_SOFT_WEEKLY_BUY_ADD_THROTTLE | trade budget sizing | weekly buy/add throttle | 是，仅 BUY/ADD | 控制过度新增风险，避免 F10Fplus 式硬过滤 |
| 8 | F11E_v2_NEWS_PRICE_CONFLICT_DRYRUN | dry-run diagnostic | no prompt / no order | 否 | 先测 news-price conflict 覆盖率 |
| 9 | F11C_v2_BAD_ENTRY_MEMORY_DRYRUN | dry-run diagnostic | no prompt / no order | 否 | 先测 bad-entry memory 是否有足够检索 |
| 10 | F11_COMBO_v1_F11Fv2_F11Kv3_F11Gv2 | conservative combo | min multiplier | 是，仅 BUY/ADD | 只组合最有希望的负向控制模块 |

### 10.3 F11F_v2_FUNDAMENTAL_RELIABILITY_HAIRCUT_ONLY

目的：把 F11F 从 prompt context 改成风险控制模块。原版 F11F reliability 全部为 unknown，且 context 注入过宽；v2 不再给 LLM 加完整 context，只在 BUY/ADD 基本面可靠性低时 haircut。

可靠性评分：

```text
start reliability_score = 1.0

if latest_fundamental_timestamp missing:
  reliability_score = min(reliability_score, 0.2)

elif data_age_days <= 45:
  no penalty
elif data_age_days <= 90:
  reliability_score -= 0.2
elif data_age_days <= 180:
  reliability_score -= 0.4
else:
  reliability_score -= 0.6

missing field penalty:
  reliability_score -= 0.1 * missing_required_field_count
  cap penalty at 0.4

contradiction_flag:
  reliability_score -= 0.3

clamp reliability_score to [0, 1]
```

Required fields if available：

```text
revenue_growth
earnings_growth
margin_trend
debt_or_leverage
cashflow_quality
valuation_metric
analyst_revision_or_guidance
```

订单规则：

```text
Only BUY/ADD can be modified.
SELL/REDUCE unchanged.

if reliability_score < 0.3:
  BUY multiplier = 0.7
  ADD multiplier = 0.5
elif reliability_score < 0.5:
  BUY multiplier = 0.85
  ADD multiplier = 0.7
else:
  multiplier = 1.0
```

配置：

```text
configs/experiments/F11F_v2_FUNDAMENTAL_RELIABILITY_HAIRCUT_ONLY.yaml
```

### 10.4 F11F_v2_PROMPT_WARNING_ONLY

目的：分离 fundamental reliability warning 本身的价值，不改订单。

触发：

```text
proposed action in BUY/ADD
reliability_score < 0.5
```

prompt 只允许一行短 warning：

```text
Fundamental data reliability is low or stale; avoid relying on fundamentals for this BUY/ADD unless other evidence is strong.
```

禁止：

```text
full fundamental values
long explanations
bullish encouragement
reliable-data positive messages
order size modification
```

配置：

```text
configs/experiments/F11F_v2_PROMPT_WARNING_ONLY.yaml
```

### 10.5 F11K_v3_LOSER_COOLDOWN_HAIRCUT_ONLY

目的：重试 F11K，但只对 repeated BUY/ADD in weak or losing states 做 haircut，避免干扰正常反弹参与。

定义：

```text
failed_recent_buy_add:
  previous BUY/ADD on same symbol within last 10 trading days
  followed by:
    5d_forward_return < -2%
    OR 5d_forward_return - universe_median_5d < -2%

weak_current_state:
  any of:
    current unrealized_pnl < 0
    return_5d < 0
    return_20d < 0
    current price below 20d moving average if available

improved_state:
  all of:
    return_5d > 0
    current unrealized_pnl >= 0 if position exists
    price above 20d moving average if available
```

触发：

```text
proposed action in BUY/ADD
same symbol has failed_recent_buy_add
weak_current_state is true
improved_state is false
```

规则：

```text
if trigger false:
  multiplier = 1.0

if trigger true and action == ADD:
  multiplier = 0.5

if trigger true and action == BUY:
  multiplier = 0.7

strong rebound exception:
  if return_5d > 3% and return_20d > 0:
    multiplier = max(multiplier, 0.85)
```

禁止：

```text
block trade entirely
modify SELL/REDUCE
apply cooldown to winners
use LLM confidence as override
```

配置：

```text
configs/experiments/F11K_v3_LOSER_COOLDOWN_HAIRCUT_ONLY.yaml
```

### 10.6 F11K_v3_PROMPT_WARNING_ONLY

目的：只测试短 cooldown warning 是否有价值，不改订单。

使用与 F11K_v3 haircut 相同的 `failed_recent_buy_add / weak_current_state / improved_state` 定义。

触发后只加一行 prompt：

```text
Recent similar BUY/ADD in this symbol had poor short-term outcome and current state remains weak; avoid repeating the same entry unless evidence has improved.
```

订单：

```text
multiplier = 1.0 always
SELL/REDUCE unchanged
```

配置：

```text
configs/experiments/F11K_v3_PROMPT_WARNING_ONLY.yaml
```

### 10.7 F11G_v2_SIGNAL_CONFLICT_HAIRCUT_ONLY

目的：多源信号冲突时降低 BUY/ADD size，不做任何正向放大。

信号：

```text
fundamental_direction:
  bullish = +1
  bearish = -1
  neutral/unknown = 0

momentum_direction:
  bullish if return_5d > 0 and return_20d > 0
  bearish if return_5d < 0 and return_20d < 0
  otherwise 0

news_direction:
  bullish = +1
  bearish = -1
  neutral/unknown/no_news = 0

position_pnl_direction:
  winning = +1
  losing = -1
  flat/no_position = 0
```

agreement score：

```text
use nonzero signals only
if nonzero_signal_count < 2:
  agreement_score = None
  multiplier = 1.0
else:
  agreement_score = max(count(+1), count(-1)) / nonzero_signal_count
```

订单规则：

```text
Only BUY/ADD can be modified.
SELL/REDUCE unchanged.

if agreement_score is None:
  multiplier = 1.0
elif agreement_score < 0.4:
  BUY multiplier = 0.7
  ADD multiplier = 0.5
elif agreement_score < 0.6:
  BUY multiplier = 0.9
  ADD multiplier = 0.8
else:
  multiplier = 1.0
```

可选 prompt：

```text
Only when multiplier < 1.0:
  "Signal conflict detected; reduce BUY/ADD size."
```

配置：

```text
configs/experiments/F11G_v2_SIGNAL_CONFLICT_HAIRCUT_ONLY.yaml
```

### 10.8 F11J_v2_CROWDING_LOSER_ADD_ONLY

目的：避免对已经拥挤的弱势仓位继续加仓，同时避免过度压制 winner。

触发：

```text
proposed action in BUY/ADD
action increases exposure
existing position_weight > 8%
```

weak_state：

```text
any of:
  unrealized_pnl < 0
  return_5d < 0
  return_20d < 0
```

规则：

```text
if trigger false:
  multiplier = 1.0

if trigger true and weak_state false:
  multiplier = 1.0

if trigger true and weak_state true:
  if position_weight > 12%:
    multiplier = 0.3
  elif position_weight > 10%:
    multiplier = 0.5
  elif position_weight > 8%:
    multiplier = 0.7

strong winner exception:
  if position_weight > 12%
  and unrealized_pnl > 0
  and return_20d > 0:
    multiplier = max(multiplier, 0.7)
```

禁止：

```text
use LLM confidence as override
modify SELL/REDUCE
force sells
penalize healthy winners unnecessarily
```

配置：

```text
configs/experiments/F11J_v2_CROWDING_LOSER_ADD_ONLY.yaml
```

### 10.9 F11L_v2_SOFT_WEEKLY_BUY_ADD_THROTTLE

目的：降低过度 BUY/ADD 活跃度，但避免重复 F10Fplus 的过度过滤。

规则：

```text
weekly_buy_add_budget = 10
count only BUY/ADD trades above minimum notional threshold if available
SELL/REDUCE unlimited
```

订单规则：

```text
Only BUY/ADD can be modified.

if weekly_buy_add_count_before_trade <= 10:
  multiplier = 1.0

if weekly_buy_add_count_before_trade > 10:
  if confidence < 0.5:
    multiplier = 0.4
  else:
    multiplier = 0.8

never block trade entirely
never use multiplier below 0.4
never modify SELL/REDUCE
never use multiplier above 1.0
```

配置：

```text
configs/experiments/F11L_v2_SOFT_WEEKLY_BUY_ADD_THROTTLE.yaml
```

### 10.10 F11E_v2_NEWS_PRICE_CONFLICT_DRYRUN

目的：先 dry-run 测试 news-price conflict 是否有足够覆盖率，不直接实现完整 news module。

dry-run 规则：

```text
Do not add prompt context.
Do not modify orders.
Only log hypothetical conflicts.
```

只在 news exists 时触发诊断：

```text
Case 1:
  positive news
  proposed action in BUY/ADD
  return_1d <= 0
  return_5d <= 0

Case 2:
  negative news
  proposed action in BUY/ADD
  return_1d < 0 or return_5d < 0

Case 3:
  negative news
  proposed action in SELL/REDUCE
  return_1d >= 0
  return_5d >= 0
```

是否进入完整实现的门槛：

```text
Only implement full F11E_v2 if total_conflict_count >= 20.
```

配置：

```text
configs/experiments/F11E_v2_NEWS_PRICE_CONFLICT_DRYRUN.yaml
```

### 10.11 F11C_v2_BAD_ENTRY_MEMORY_DRYRUN

目的：先 dry-run 测试 bad-entry memory 是否有足够检索价值，不改 prompt / orders。

生成 hypothetical memory：

```text
after BUY/ADD:
  if 5d_forward_return < -2%
  or 5d_forward_return - universe_median_5d < -2%:
    create hypothetical low_quality_entry memory
```

检索条件：

```text
same symbol
proposed action in BUY/ADD
same position_pnl_sign
same 5d momentum sign
max 1 memory per symbol
```

dry-run：

```text
Do not modify prompt.
Do not modify orders.
Only log hypothetical memory creation and retrieval.
```

进入完整实现门槛：

```text
Only implement full F11C_v2 if memory_retrieved_count >= 20.
```

配置：

```text
configs/experiments/F11C_v2_BAD_ENTRY_MEMORY_DRYRUN.yaml
```

### 10.12 F11_COMBO_v1_F11Fv2_F11Kv3_F11Gv2

目的：只组合最有希望的 conservative negative-control modules：

```text
F11F_v2 reliability haircut
F11K_v3 loser cooldown haircut
F11G_v2 signal conflict haircut
```

运行前提：

```text
Only run after Experiments 1, 3, and 5 complete.
If any single module causes trades > 360
or materially worsens return/drawdown,
exclude that module from combo.
```

组合规则：

```text
Compute all applicable multipliers independently.
final_multiplier = min(F11F_multiplier, F11K_multiplier, F11G_multiplier)
Use min rather than product to avoid excessive over-filtering.
```

边界：

```text
Only BUY/ADD can be modified.
SELL/REDUCE unchanged.
No long prompt context.
No positive reinforcement.
No multiplier above 1.0.
```

配置：

```text
configs/experiments/F11_COMBO_v1_F11Fv2_F11Kv3_F11Gv2.yaml
```

### 10.13 暂停的原始实验

不再运行以下原始版本：

```text
F11A M2_EVENT_LEVEL_MISTAKE_MEMORY
F11B M3_EXPIRING_MEMORY
F11C M4_COUNTERFACTUAL_TRADE_MEMORY original
F11D M5_STATE_CONDITIONED_MEMORY
F11E I2_NEWS_PRICE_CONFIRMATION original
F11F I3_FUNDAMENTAL_RELIABILITY original
F11G I4_SIGNAL_CONSENSUS_SCORE original
F11H R1_RELATIVE_STRENGTH_CONTEXT
F11I R2_CONFIDENCE_POSITION_SIZING original
F11J R3_SOFT_POSITION_CROWDING_PENALTY original
F11K R4_STATE_COOLDOWN original
F11L R5_WEEKLY_TRADE_BUDGET original
F11M R6_DRAWDOWN_CONTEXT
F11N R7_WINNER_SELL_FRICTION original
```

同时暂停：

```text
any positive reinforcement module
any high-confidence enlargement module
any full-universe daily context injection module
any module that modifies SELL/REDUCE unless explicitly requested
```

### 10.14 更新后的报告格式

最终 comparison table：

| Column | 说明 |
| --- | --- |
| experiment | 实验名 |
| total_return | 策略收益 |
| excess_return_vs_F6 | 相对 F6 收益差 |
| max_drawdown | 最大回撤 |
| max_drawdown_vs_F6 | 相对 F6 回撤差 |
| sharpe | Sharpe |
| total_trades | 总交易数 |
| trade_delta_vs_F6_261 | 相对 F6 交易数差 |
| BUY_count / ADD_count / SELL_count / REDUCE_count | 动作拆分 |
| intervention_count | 干预次数 |
| intervention_rate | 干预比例 |
| avg_multiplier_when_triggered | 触发时平均 multiplier |
| notes | 解释 |

模块专项诊断：

```text
F11F:
  reliability_score distribution
  missing timestamp count
  stale data count
  contradiction count
  BUY/ADD haircut count
  average forward 5d return of haircutted trades

F11K:
  failed_recent_buy_add count
  weak_current_state count
  improved_state exception count
  rebound_exception count
  average forward 5d return of cooled trades

F11G:
  agreement_score distribution
  conflict trade count
  forward 5d return of conflict BUY/ADD

F11J:
  crowded weak add count
  strong winner exception count
  weight distribution of affected trades

F11L:
  weeks exceeding budget
  trades affected per week
  whether total trades remained near F6

F11E dry-run:
  total_conflict_count
  whether full implementation is justified

F11C dry-run:
  memory_retrieved_count
  whether full implementation is justified
```

成功标准：

```text
Primary:
  total_return > F6 total_return
  max_drawdown <= F6 max_drawdown
  trades <= 340 preferred

Secondary:
  if return is similar to F6, prefer lower drawdown and fewer trades
  reject modules with trades > 360 unless return improvement is material
  reject modules with intervention_count too low to evaluate unless dry-run
```
