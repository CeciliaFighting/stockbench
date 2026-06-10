# DeepSeek StockBench Agent 实验计划与阶段总结

## 1. 实验目标

本实验用于系统评估如何改进基于 DeepSeek 的 StockBench 金融交易 Agent。实验遵循课题文档中的统一设置：

- 股票池：StockBench 使用的 DJIA 前 20 只股票
- 回测区间：2025-03-03 至 2025-06-30
- 初始资金：100,000 USD
- 主指标：Sortino Ratio
- 辅助指标：Total Return、Max Drawdown、Sharpe、相对 SPY 的 Excess Return、交易次数、交易金额、现金比例、分月表现

本课题重点不是单纯刷高最终收益，而是理解现有 LLM Agent 的失败模式，并通过信号处理、执行约束、市场状态识别和记忆机制等通用方法验证哪些结构性改动真正提升决策质量。

## 2. 第一阶段实验结果

第一阶段完成了 B0、Q1、FUND1、C1、M1 五组完整回测。B0 是 DeepSeek baseline，其余四组分别测试结构化价格量化信号、清洗后的基本面信号、规则执行约束和选择性记忆。

| 版本 | 核心设计 | Total Return | Max Drawdown | Sharpe | Sortino | Excess vs SPY | Trades | Trades Notional |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| B0 DeepSeek baseline | 纯 DeepSeek LLM，无 reflection、无 fundamental、无 structured quant | +2.56% | -10.47% | 0.404 | 0.034 | -4.10% | 564 | 718.7k |
| Q1 Structured price quant | 结构化 momentum / trend / risk / action bias | -7.54% | -13.99% | -0.881 | -0.063 | -15.54% | 257 | 519.2k |
| FUND1 Cleaned fundamental | 清洗、bucket 化后的 fundamental_signal | +3.35% | -11.61% | 0.471 | 0.038 | -4.55% | 351 | 647.4k |
| C1 Rule-constrained execution | 执行层硬约束，限制交易数和换手 | +1.58% | -10.98% | 0.302 | 0.023 | -6.16% | 75 | 350.9k |
| M1 Selective memory | 选择性历史错误记忆 / reflection context | -0.02% | -11.20% | 0.126 | 0.009 | -7.79% | 227 | 399.3k |

## 3. 第一阶段核心结论

### 3.1 FUND1 是唯一明确优于 B0 的版本

FUND1 将收益从 B0 的 +2.56% 提升到 +3.35%，Sharpe 从 0.404 提升到 0.471，Sortino 从 0.034 提升到 0.038，同时交易数从 564 降到 351。虽然最大回撤从 -10.47% 扩大到 -11.61%，但整体收益和风险调整收益均有改善。

这说明 cleaned fundamental signal 对 DeepSeek 决策有边际贡献。后续实验应以 FUND1 为 base，而不是继续以 B0 为唯一主线。

### 3.2 Q1 失败，但给出了重要负面结果

Q1 把 raw quant factor 整理成结构化信号后，交易数从 B0 的 564 降到 257，说明结构化信号确实让模型更克制。但收益变成 -7.54%，最大回撤扩大到 -13.99%，说明它克制错了方向。

主要问题判断：

- Q1 把 alpha 和 risk 混在同一个 overall score 中，导致高波动反弹股被过早降权。
- 低波动、低回撤被模型误读为更优 alpha，策略偏向 JNJ、PG、HON 等防守或低弹性股票。
- 2025 年 4 月后市场进入反弹阶段，真正强势的是 GS、BA、CAT、MSFT、JPM、IBM、AMZN 等风险偏好修复受益股，Q1 未能充分参与。
- Prompt 变长后并没有提升决策质量，反而可能增加模型解释负担。

因此，量化因子不应该被放弃，但第二阶段必须把 alpha signal 和 risk signal 分离。Risk 只用于仓位调整，不应直接惩罚 alpha。

### 3.3 C1 证明执行约束有效，但单独使用过强

C1 将交易数从 564 降到 75，交易金额也显著下降，说明执行约束非常有效。但收益只有 +1.58%，低于 B0 和 FUND1。这说明过强规则会压制策略参与反弹的能力。

后续不应继续运行 standalone C1，而应将更轻量的执行约束叠加到 FUND1 上，目标是把交易数降到 150-250，而不是压到极低。

### 3.4 M1 的 generic reflection 不够有效

M1 收益接近 0，Sortino 也明显低于 B0 和 FUND1。它虽然降低了交易数，但没有改善收益或回撤。

问题可能在于 generic reflection 让模型更保守，却没有精确约束低质量交易。第二阶段应避免泛化的“反思 agent”，改成 anti-overtrade memory：只记录最近 5 天同一股票的重复低质量交易，并用 cooldown 机制抑制无效买卖。

## 4. 第二阶段实验设计

第二阶段以 FUND1 为 base，不再单独重复 Q1/C1/M1。主比较对象为 B0 和 FUND1。

### 4.1 F2：FUND1 + Light Execution Constraints

目标：在保留 FUND1 选股能力的基础上，加入比 C1 更温和的执行约束，减少无效交易和换手，但不明显牺牲收益。

配置：

```yaml
execution_constraints:
  enabled: true
  max_trades_per_day: 8
  max_daily_turnover_pct_nav: 0.35
  min_trade_notional_pct_nav: 0.01
  winner_holding_rule: true
  weak_stock_no_add_rule: true
```

实验假设：

- Trades 从 FUND1 的 351 降到 150-250。
- Total Return 尽量不低于 FUND1。
- Max Drawdown 和 Sortino 有机会改善。
- 如果收益明显下降，说明约束仍然过强，或 winner/weak 规则误伤了反弹股。

重点分析：

- 被过滤的订单数量、原因和股票分布。
- 4 月回撤阶段是否减少错误交易。
- 5-6 月反弹阶段是否仍能加仓强势股。

### 4.2 F3：FUND1 + Alpha-only Quant Signal

目标：修复 Q1 的核心问题，将 alpha 和 risk 分开。Alpha 用于判断收益机会，risk 只用于仓位大小，不直接降低 alpha 排名。

Alpha signal：

```yaml
quant_alpha_signal:
  relative_strength_20d_rank
  relative_strength_60d_rank
  trend_recovery_score
  rebound_participation_score
  sector_relative_strength_rank
  alpha_score
```

Risk signal：

```yaml
quant_risk_signal:
  volatility_20d_rank
  drawdown_20d_rank
  risk_level
```

原则：

- 不把 volatility / drawdown 放入 overall alpha ranking。
- 不因为高波动就单独降级 alpha。
- 高风险股票可以降低仓位，但如果 alpha 强，不应直接禁止买入。
- 重点观察是否能更好参与 4 月后的反弹。

### 4.3 F4：FUND1 + Regime-aware Risk Overlay

目标：让 FUND1 继续负责选股，市场状态只控制风险暴露、加仓权限和换手上限。

市场状态分类：

```text
risk_on_low_vol
risk_on_high_vol
risk_off_low_vol
risk_off_high_vol
```

规则输入：

- SPY 20d / 60d return
- SPY MA20 / MA60
- VIX percentile
- realized volatility percentile

控制逻辑：

- risk_on：允许加仓强势股，提高 gross exposure 上限。
- risk_off：降低 gross exposure，限制加仓，优先保留强势持仓。
- high_vol：降低单日换手上限，避免波动期过度交易。
- low_vol：允许更稳定地建仓。

注意：F4 不做选股替代，只做 risk overlay。

### 4.4 F5：FUND1 + Anti-overtrade Memory

目标：不再使用 generic reflection，只记录最近 5 天同一股票的低质量重复交易。

记忆对象：

- repeated buy/sell without profit
- repeated small loss trades
- 同一股票短期内频繁买卖但没有改善组合收益

Cooldown 规则：

- 对重复低质量交易的股票设置短期冷却。
- 冷却期间禁止同方向重复交易。
- 允许例外：高置信信号、重大趋势反转、风险降低型卖出。

实验假设：

- 降低无效换手。
- 不像 M1 那样让模型整体过度保守。
- 对 FUND1 的收益影响应小于 C1，但能改善交易质量。

## 5. 第二阶段运行计划

建议只跑一轮完整回测，先判断方向是否有价值：

```text
F2  DEEPSEEK_F2_FUND_LIGHT_CONSTRAINT_FULL
F3  DEEPSEEK_F3_FUND_ALPHA_QUANT_FULL
F4  DEEPSEEK_F4_FUND_REGIME_RISK_FULL
F5  DEEPSEEK_F5_FUND_ANTI_OVERTRADE_FULL
```

统一设置：

```text
start = 2025-03-03
end   = 2025-06-30
model = deepseek-v4-flash
data_mode = offline_only
reflection_agent = false
fundamental = cleaned_signal
```

对照组：

```text
B0    DEEPSEEK_BASELINE_FULL
FUND1 DEEPSEEK_FUND1_CLEAN_FUND_FULL
```

## 6. 报告指标

每组至少报告：

- Total Return
- Sortino
- Sharpe
- Max Drawdown
- Excess Return vs SPY
- Trades
- Turnover / Trades Notional
- Average cash ratio
- Monthly returns
- April drawdown behavior

重点回答：

1. 是否优于 FUND1，而不仅是优于 B0？
2. 是否降低了 4 月回撤？
3. 是否参与了 5-6 月反弹？
4. 是否减少了重复低质量交易？
5. 收益变化来自选股改善、仓位改善，还是交易约束？
6. Sortino 提升来自收益提升、下行风险下降，还是两者都有？

## 7. 当前推荐优先级

优先级排序：

1. F2：最小改动，验证轻量执行约束能否保留 FUND1 收益并降低换手。
2. F3：最有研究价值，修正 Q1 的 alpha/risk 混合问题。
3. F5：针对 M1 的失败模式，做更精确的 anti-overtrade memory。
4. F4：框架价值高，但需要先确认 VIX 和市场 regime 数据是否稳定。

第二阶段的核心研究问题：

> FUND1 已经改善选股质量后，进一步加入轻量交易约束或纯 alpha 量化信号，能否在不牺牲收益的情况下降低回撤和换手？

## 8. 第三阶段实验：以 F5 为 base 的快速提升实验

### 8.1 实验背景

第二阶段结果显示，F5（FUND1 + anti-overtrade memory）是当前最好的结构性改进版本：

| 版本 | Total Return | Max Drawdown | Sharpe | Sortino | Excess vs SPY | Trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| F5 baseline | +3.83% | -12.41% | 0.525 | 0.045 | -4.48% | 363 |

因此第三阶段不再以 B0 或 FUND1 为 base，而是统一以 F5 为 base，优先测试更可能快速提升指标的单模块实验。

第三阶段实验全部已经完成。统一设置如下：

```text
start = 2025-03-03
end   = 2025-06-30
model = deepseek-v4-flash
data_mode = offline_only
reflection_agent = false
fundamental = cleaned_signal
base = F5
shared_data_cache = $HOME/.cache/stockbench/data-cache
```

### 8.2 实验组设计

| 实验 | 设计目的 | 核心设置 |
| --- | --- | --- |
| F5_LH_WEEKLY_10D | 测试低频调仓是否能减少短期噪声交易 | weekly rebalance + 10d horizon + min_hold 5d |
| F5_LH_BIWEEKLY_20D | 测试更长持有周期是否改善风险收益 | biweekly rebalance + 20d horizon + min_hold 10d |
| F5_LH_MONTHLY_20D | 测试月度调仓是否能显著降低回撤和换手 | monthly rebalance + 20d horizon + min_hold 20d |
| F5_COOLDOWN_5D | 测试轻量 cooldown 是否减少反复买卖 | buy/sell 反向交易 cooldown 5d |
| F5_COOLDOWN_10D | 测试更强 cooldown 是否进一步降低换手 | buy/sell 反向交易 cooldown 10d |
| F5_QUANT_GUARDRAIL | 测试量化因子作为确认/否决/仓位调整信号 | quant confirmation / veto / position sizing |
| F5_REGIME_FACTOR_WEIGHTS | 测试不同 market regime 下使用不同因子权重 | risk_off / rebound / trend_following / range_bound factor weights |

### 8.3 实验结果总表

| 实验 | Total Return | Max Drawdown | Sharpe | Sortino | Excess vs SPY | Information Ratio | Trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| F5 baseline | +3.83% | -12.41% | 0.525 | 0.045 | -4.48% | - | 363 |
| F5_LH_WEEKLY_10D | +0.12% | -8.22% | 0.125 | 0.009 | -7.86% | -0.642 | 133 |
| F5_LH_BIWEEKLY_20D | -0.26% | -12.52% | 0.083 | 0.007 | -8.57% | -0.677 | 50 |
| F5_LH_MONTHLY_20D | -2.61% | -8.83% | -0.363 | -0.026 | -10.98% | -0.941 | 48 |
| F5_COOLDOWN_5D | **+3.99%** | **-9.16%** | **0.557** | 0.043 | **-4.07%** | **-0.332** | **261** |
| F5_COOLDOWN_10D | +0.57% | -11.81% | 0.188 | 0.016 | -7.07% | -0.604 | 240 |
| F5_QUANT_GUARDRAIL | -2.60% | -13.79% | -0.163 | -0.012 | -9.04% | -0.680 | 289 |
| F5_REGIME_FACTOR_WEIGHTS | -5.89% | -13.34% | -0.856 | -0.067 | -11.80% | -0.985 | 301 |

### 8.4 主要结论

#### 8.4.1 F5_COOLDOWN_5D 是本阶段唯一明确优于 F5 的版本

F5_COOLDOWN_5D 在收益、回撤、Sharpe、相对 SPY 超额收益和交易次数上都优于 F5：

```text
Total Return: +3.83% -> +3.99%
Max Drawdown: -12.41% -> -9.16%
Sharpe: 0.525 -> 0.557
Excess vs SPY: -4.48% -> -4.07%
Trades: 363 -> 261
```

这说明 F5 的主要问题不是缺少复杂模型，而是仍然存在短周期反复交易。5 天 cooldown 能有效减少低质量反向交易，同时仍保留足够灵活性参与 5-6 月反弹。

该结果具有较强研究价值：它不是单纯调参提高最终收益，而是验证了一个通用机制，即“限制短期反向交易可以降低 overtrading，并在不牺牲收益的情况下降低回撤”。

#### 8.4.2 Cooldown 不能过强，10D 明显压制收益

F5_COOLDOWN_10D 虽然将交易数从 363 降到 240，但收益下降到 +0.57%，Sharpe 也降到 0.188。

这说明 cooldown 的有效性存在强度边界。10 天限制过强，会导致策略在市场快速变化时无法及时纠错或重新买回强势标的。对本任务的 2025-03 至 2025-06 短样本来说，5 天是更合适的初始约束。

#### 8.4.3 Longer Horizon 系列整体失败

三个 Longer Horizon 实验共同说明：单纯降低调仓频率并不能提高 F5。

| 实验 | 现象 |
| --- | --- |
| Weekly | 回撤下降到 -8.22%，但收益只有 +0.12% |
| Biweekly | 交易数只有 50，收益为 -0.26% |
| Monthly | 交易数只有 48，收益为 -2.61% |

Weekly 版本证明低频约束确实能降低回撤，但收益几乎被完全牺牲。Biweekly 和 Monthly 则说明，在本实验区间里，过低频调仓会错过 4 月后市场修复和强势股轮动。

因此 Longer Horizon 不适合作为下一阶段主线。若继续探索，应改为“只限制反向交易，不限制正常加仓/风险减仓”，而不是全面降低调仓频率。

#### 8.4.4 Quant Guardrail 当前设计失败

F5_QUANT_GUARDRAIL 的收益为 -2.60%，最大回撤扩大到 -13.79%，Sharpe 为 -0.163。它没有达到“只做 confirmation / veto / position sizing”的预期效果。

主要原因判断：

- veto 规则过硬，可能挡掉了 LLM 原本能识别的反弹机会。
- 量化因子虽然标准化了，但仍然缺少针对本股票池和短样本区间的校准。
- momentum、volatility、drawdown、quality、value 等信号在 2025 年 3-6 月的短样本中容易相互冲突。
- LLM 在 prompt 中看到量化 guardrail 后，可能过度依赖风险提示，导致错过高 beta / 高波动反弹股。

因此，量化因子不能以当前形式作为硬 veto。后续如果继续使用量化因子，应弱化为：

```text
soft warning
position size adjustment only
no hard veto unless liquidity/data quality 极端异常
```

#### 8.4.5 Regime Factor Weights 是本阶段最差版本

F5_REGIME_FACTOR_WEIGHTS 的收益为 -5.89%，最大回撤 -13.34%，Sharpe -0.856，是本阶段最差结果。

失败原因判断：

- 当前 regime 是用 20 股票池内部价格序列近似得到的，不是真正基于 SPY/VIX/市场宽度的稳定 regime。
- regime 分类误差会直接传导到因子权重，导致错误放大。
- regime-specific weights 让模型更像在执行一套固定风格轮动规则，但本任务股票池较小、样本较短，权重很容易过拟合或错配。
- 当市场从 4 月回撤转向 5-6 月反弹时，错误 regime 可能压制了高 beta / 相对强势标的。

因此该版本不建议继续作为主线。若未来探索 regime，应先做“regime context only”，只把市场状态作为上下文，不直接改变因子权重或交易规则。

### 8.5 第三阶段最终排序

按综合表现排序：

1. F5_COOLDOWN_5D：唯一明确优于 F5，建议作为下一阶段 base。
2. F5_LH_WEEKLY_10D：有降回撤价值，但收益过低，不适合作为主线。
3. F5_COOLDOWN_10D：证明 cooldown 过强会压制收益。
4. F5_LH_BIWEEKLY_20D：交易过少，错过机会。
5. F5_LH_MONTHLY_20D：交易过少，收益为负。
6. F5_QUANT_GUARDRAIL：当前量化 guardrail 设计失败。
7. F5_REGIME_FACTOR_WEIGHTS：当前 regime + factor weights 设计失败。

### 8.6 下一步建议

建议定义新主线：

```text
F6 = F5 + cooldown_days=5
```

下一轮不建议再跑复杂组合实验，而是围绕 F6 做小粒度改进：

```text
F6_COOLDOWN_3D
F6_COOLDOWN_4D
F6_COOLDOWN_6D
F6_COOLDOWN_5D_ONLY_REVERSAL
```

其中最值得优先实现的是：

```text
F6_COOLDOWN_5D_ONLY_REVERSAL
```

含义是只限制短期反向交易：

```text
buy 后 5 天内默认不能 sell
sell 后 5 天内默认不能 rebuy
```

但不限制：

```text
正常加仓
风险减仓
高置信度 thesis invalidated 的卖出
重大趋势反转
```

该方向比 Longer Horizon 更细粒度，也比 Quant Guardrail 更稳健。它保留了 F5 的语义理解和 fundamental signal 优势，同时针对当前最明确的失败模式：短期反复交易。

### 8.7 当前阶段结论

第三阶段最重要的研究结论是：

> 在当前 StockBench 短周期实验中，提升交易表现的关键不是加入更复杂的量化因子或市场 regime 权重，而是用轻量、可解释的交易记忆约束减少 overtrading。5 天 cooldown 是目前最有效的结构性改进。

该结论也解释了为什么前期 Q1、F3、Quant Guardrail 和 Regime Factor Weights 反复失败：量化信号如果直接参与选股、veto 或风格权重切换，容易在短样本和小股票池中引入噪声；而轻量交易行为约束更直接对应 LLM Agent 的实际失败模式。

### 8.8 按课题文档口径：相对 20 股 Buy & Hold 的评价

课题文档 3.2 节规定，主指标为 Sortino Ratio，辅助指标包括 Total Return 和 Max Drawdown。其中 Total Return 的说明是“相对 Buy & Hold 的超额收益”，3.3 节也明确要求必须包含 Buy & Hold 作为 baseline 对照。

因此，本项目的主对照不应是 SPY，而应是同一股票池的 Buy & Hold。这里采用 StockBench 报告中的 `per_symbol_benchmark_nav.parquet`，即对 DJIA 前 20 只股票分别等金额买入并持有，再取 20 股等权组合平均 NAV。

该 Buy & Hold baseline 在 2025-03-03 至 2025-06-30 区间的表现为：

```text
20-stock equal-weight Buy & Hold return: +0.7348%
20-stock equal-weight Buy & Hold Sortino: 0.018
20-stock equal-weight Buy & Hold Max Drawdown: -14.95%
```

按该口径重新比较第三阶段结果：

| 实验 | Strategy Return | B&H Return | Excess vs B&H | Strategy Sortino | B&H Sortino | Sortino Δ | Strategy MDD | B&H MDD | MDD 改善 | Trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| F5 baseline | +3.83% | +0.7348% | +3.10% | 0.045 | 0.018 | +0.027 | -12.41% | -14.95% | +2.54% | 363 |
| F5_LH_WEEKLY_10D | +0.12% | +0.7348% | -0.61% | 0.009 | 0.018 | -0.009 | -8.22% | -14.95% | +6.73% | 133 |
| F5_LH_BIWEEKLY_20D | -0.26% | +0.7348% | -0.99% | 0.007 | 0.018 | -0.011 | -12.52% | -14.95% | +2.43% | 50 |
| F5_LH_MONTHLY_20D | -2.61% | +0.7348% | -3.34% | -0.026 | 0.018 | -0.044 | -8.83% | -14.95% | +6.13% | 48 |
| F5_COOLDOWN_5D | **+3.99%** | +0.7348% | **+3.26%** | **0.043** | 0.018 | **+0.025** | **-9.16%** | -14.95% | **+5.79%** | 261 |
| F5_COOLDOWN_10D | +0.57% | +0.7348% | -0.16% | 0.016 | 0.018 | -0.002 | -11.81% | -14.95% | +3.14% | 240 |
| F5_QUANT_GUARDRAIL | -2.60% | +0.7348% | -3.33% | -0.012 | 0.018 | -0.030 | -13.79% | -14.95% | +1.16% | 289 |
| F5_REGIME_FACTOR_WEIGHTS | -5.89% | +0.7348% | -6.62% | -0.067 | 0.018 | -0.085 | -13.34% | -14.95% | +1.62% | 301 |

按课题文档口径，结论比 SPY 口径更清楚：

1. F5 baseline 已经显著优于 20 股 Buy & Hold：收益超额 +3.10%，Sortino 提高 +0.027，最大回撤改善 2.54 个百分点。
2. F5_COOLDOWN_5D 是当前最优版本：收益超额 +3.26%，Sortino 仍显著高于 Buy & Hold，最大回撤改善 5.79 个百分点，同时交易数从 F5 的 363 降到 261。
3. Longer Horizon 虽然改善最大回撤，但收益和 Sortino 多数低于 Buy & Hold，不满足主指标改善要求。
4. Quant Guardrail 和 Regime Factor Weights 均低于 Buy & Hold，说明当前量化因子使用方式不仅没有贡献增量，反而损害了主指标。

因此，最终评价时应把表述从“是否跑赢 SPY”改为“是否优于 20 股 Buy & Hold”。SPY 只保留为市场环境参照，而不是课题主 benchmark。

## 9. 全部实验按 20 股 Buy & Hold 口径重新汇总

### 9.1 统一 benchmark

按照课题文档要求，所有实验统一和同一股票池的 Buy & Hold baseline 比较。这里使用 20 支股票等金额买入持有组合：

```text
20-stock equal-weight Buy & Hold return: +0.7348%
20-stock equal-weight Buy & Hold Sortino: 0.018
20-stock equal-weight Buy & Hold Max Drawdown: -14.95%
```

评价时重点看：

```text
Sortino 是否高于 Buy & Hold
Total Return 是否高于 Buy & Hold
Max Drawdown 是否低于 Buy & Hold
```

### 9.2 全实验总表

| 实验 | Strategy Return | Excess vs B&H | Strategy Sortino | Sortino Δ | Strategy MDD | MDD 改善 | Trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| B0 DeepSeek baseline | +2.56% | +1.86% | 0.034 | +0.016 | -10.47% | +4.48% | 564 |
| FUND1 Cleaned fundamental | +3.35% | +2.65% | 0.038 | +0.020 | -11.61% | +3.34% | 351 |
| Q1 Structured price quant | -7.54% | -8.24% | -0.063 | -0.081 | -13.99% | +0.96% | 257 |
| C1 Rule constraints | +1.58% | +0.88% | 0.023 | +0.005 | -10.98% | +3.97% | 75 |
| M1 Selective memory | -0.02% | -0.73% | 0.009 | -0.009 | -11.20% | +3.75% | 227 |
| F2 Light constraints | +2.33% | +1.62% | 0.028 | +0.010 | -9.52% | +5.43% | 106 |
| F3 Alpha quant | -2.46% | -3.16% | -0.010 | -0.028 | -14.11% | +0.84% | 287 |
| F4 Regime risk overlay | -0.02% | -0.72% | 0.005 | -0.013 | -5.86% | +9.09% | 229 |
| F5 Anti-overtrade memory | +3.83% | +3.13% | 0.045 | +0.027 | -12.41% | +2.54% | 363 |
| F5_LH_WEEKLY_10D | +0.12% | -0.59% | 0.009 | -0.009 | -8.22% | +6.73% | 133 |
| F5_LH_BIWEEKLY_20D | -0.26% | -0.96% | 0.007 | -0.011 | -12.52% | +2.43% | 50 |
| F5_LH_MONTHLY_20D | -2.61% | -3.32% | -0.026 | -0.044 | -8.83% | +6.13% | 48 |
| F5_COOLDOWN_5D | **+3.99%** | **+3.29%** | **0.043** | **+0.025** | **-9.16%** | **+5.79%** | 261 |
| F5_COOLDOWN_10D | +0.57% | -0.13% | 0.016 | -0.002 | -11.81% | +3.14% | 240 |
| F5_QUANT_GUARDRAIL | -2.60% | -3.30% | -0.012 | -0.030 | -13.79% | +1.16% | 289 |
| F5_REGIME_FACTOR_WEIGHTS | -5.89% | -6.60% | -0.067 | -0.085 | -13.34% | +1.62% | 301 |

说明：

- `Excess vs B&H = Strategy Return - 20-stock Buy & Hold Return`。
- `Sortino Δ = Strategy Sortino - Buy & Hold Sortino`。
- `MDD 改善 = Strategy MDD - Buy & Hold MDD`。由于 MDD 是负数，正值表示回撤更小。

### 9.3 按课题主指标的排序

按 Sortino 及其相对 Buy & Hold 的提升排序，最好的版本是：

1. F5 Anti-overtrade memory：Sortino 0.045，Sortino Δ +0.027。
2. F5_COOLDOWN_5D：Sortino 0.043，Sortino Δ +0.025。
3. FUND1 Cleaned fundamental：Sortino 0.038，Sortino Δ +0.020。
4. B0 DeepSeek baseline：Sortino 0.034，Sortino Δ +0.016。
5. F2 Light constraints：Sortino 0.028，Sortino Δ +0.010。
6. C1 Rule constraints：Sortino 0.023，Sortino Δ +0.005。

如果只看主指标 Sortino，F5 baseline 略高于 F5_COOLDOWN_5D。但如果同时考虑收益、回撤和交易数，F5_COOLDOWN_5D 更均衡：

```text
F5:              Return +3.83%, MDD -12.41%, Trades 363
F5_COOLDOWN_5D:  Return +3.99%, MDD -9.16%,  Trades 261
```

因此报告中可以把 F5_COOLDOWN_5D 表述为“综合最优”，而不是“单一 Sortino 最高”。

### 9.4 重新评价各阶段实验

#### 第一阶段

B0 和 FUND1 都显著优于 Buy & Hold。FUND1 相比 B0 的收益和 Sortino 更高，交易数更少，因此 cleaned fundamental signal 的方向成立。

Q1 低于 Buy & Hold，说明直接把价格量化因子塞进 prompt 会损害模型判断。C1 虽然收益和 Sortino 略高于 Buy & Hold，但交易数被压到 75，收益增量不足。M1 低于 Buy & Hold，说明 generic memory/reflection 没有带来稳定增量。

#### 第二阶段

F2 优于 Buy & Hold，并且回撤改善明显，但收益和 Sortino 低于 FUND1/F5，说明 light constraints 有风控价值，但单独使用会压制 alpha。

F3、F4 均低于 Buy & Hold。F4 的回撤非常低，但收益和 Sortino 不合格，说明 regime risk overlay 过度保守；F3 则继续证明当前 quant signal 设计没有提供有效增量。

F5 明确优于 Buy & Hold，是第二阶段最好的结构性改进。

#### 第三阶段

第三阶段中，只有 F5_COOLDOWN_5D 同时满足：

```text
收益高于 Buy & Hold
Sortino 高于 Buy & Hold
最大回撤低于 Buy & Hold
交易数少于 F5
```

Longer Horizon、Quant Guardrail 和 Regime Factor Weights 大多低于 Buy & Hold，不应作为下一阶段主线。

### 9.5 最终结论

按课题文档的 20 股 Buy & Hold 口径，目前可保留的有效方向是：

```text
FUND1: cleaned fundamental signal
F5: anti-overtrade memory
F5_COOLDOWN_5D: lightweight cooldown
```

最推荐进入下一轮的版本是：

```text
F6 = F5 + cooldown_days=5
```

更准确地说，F6 的研究假设应写成：

> 在 cleaned fundamental signal 和 anti-overtrade memory 已经改善决策质量后，进一步加入轻量 cooldown，可以减少短期反向交易，在保持 Sortino 显著高于 Buy & Hold 的同时，提高收益、降低回撤并减少交易次数。

## 10. 第四阶段实验设计：以 F6 为 base 的低权限模块验证

### 10.1 第四阶段目标

第三阶段后，当前综合最优版本为：

```text
F6 = F5_COOLDOWN_5D
   = cleaned fundamental signal
   + anti-overtrade memory
   + cooldown_days = 5
```

第四阶段不继续堆复杂组合，而是围绕课题文档中的三个方向形成逻辑闭环：

```text
A. 决策机制改进
B. 信号消融与重组
C. 记忆与上下文管理
```

已有结论如下：

1. FUND1 cleaned fundamental signal 有效。
2. F5 anti-overtrade memory 有效。
3. F5_COOLDOWN_5D 综合最优。
4. Q1、F3、Quant Guardrail、Regime Factor Weights 失败，说明 high-authority quant/regime 会破坏 LLM 原本有效判断。
5. generic reflection 不稳定，不再做泛化 reflection。

因此第四阶段的核心原则是：

> 所有新增模块都必须是低权限模块，只能做审查、排序、仓位微调、风险预算或记忆更新，不能覆盖 F6 的核心选股逻辑。

统一设置：

```text
start = 2025-03-03
end   = 2025-06-30
model = deepseek-v4-flash
data_mode = offline_only
reflection_agent = false
fundamental = cleaned_signal
benchmark = 20-stock equal-weight Buy & Hold
base = F6
```

F6 baseline 当前指标：

| 版本 | Total Return | Excess vs B&H | Sortino | Sortino Δ | Max Drawdown | MDD 改善 | Trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| F6 / F5_COOLDOWN_5D | +3.99% | +3.29% | 0.043 | +0.025 | -9.16% | +5.79% | 261 |

### 10.2 实验 A2：F6 + Risk Review Agent

#### 目的

验证低权限风险审查 agent 是否能降低最大回撤、提高交易质量，同时不明显牺牲收益。

该实验对应课题方向 A：决策机制改进。

#### 机制

F6 先生成 proposed trades。Risk Review Agent 对每笔 proposed trade 做二次检查。

Risk Review Agent 只能输出：

```text
approve
reduce_size
delay
reject_low_quality_trade
```

Risk Review Agent 不能：

```text
新增买入
强制卖出
改变股票排序
覆盖 F6 cooldown
重新做 alpha selection
```

审查维度：

```text
cooldown_violation
repeated_loss_trade
low_conviction
excessive_position_size
small_notional_trade
cost_not_justified
high_portfolio_drawdown_state
```

#### 实验假设

Risk Review Agent 如果有效，应当表现为：

- Max Drawdown 低于 F6。
- Trades 低于或接近 F6。
- Return 不显著低于 F6。
- 被 reject/delay 的交易在未来 5d/10d 的收益显著低于被 approve 的交易。

#### 必须记录

```text
reviewed_trade_count
approved_count
reduced_count
delayed_count
rejected_count
rejection_reason
rejected_trade_future_return_5d
rejected_trade_future_return_10d
executed_trade_future_return_5d
executed_trade_future_return_10d
```

#### 建议 run id

```text
F6_A2_RISK_REVIEW_FULL
```

### 10.3 实验 B2：F6 + Signal Priority Layer

#### 目的

验证给不同信号设置明确权限后，能否避免 quant/regime 信号误伤 LLM 决策。

该实验对应课题方向 B：信号消融与重组。

#### 信号权限设计

```yaml
fundamental_signal:
  role: primary_alpha
  can_trigger_buy: true
  can_trigger_hold: true
  can_trigger_sell_if_deteriorated: true

price_alpha_signal:
  role: candidate_rerank_only
  can_trigger_buy: false
  can_trigger_sell: false
  can_veto: false

risk_signal:
  role: position_sizing_only
  can_trigger_buy: false
  can_trigger_sell: false
  can_reduce_size: true
  max_size_adjustment: 0.10

regime_signal:
  role: risk_budget_context_only
  can_trigger_stock_selection: false
  can_change_factor_weights: false
  can_veto_stock: false

memory_signal:
  role: execution_constraint
  can_block_repeated_trade: true
  can_override_only_if_thesis_invalidated: true
```

#### 规则

- F6 决策仍以 cleaned fundamental + LLM thesis 为主。
- price alpha 只在 F6 候选股内部排序。
- risk 只微调仓位。
- regime 只调整 gross exposure / new buy threshold。
- memory/cooldown 保持 F6 逻辑。

#### 实验假设

B2 如果有效，应当说明“量化信号失败不是因为信号完全无用，而是因为权限过高”。预期表现为：

- Sortino 不低于 F6 太多，最好略高。
- Return 接近或高于 F6。
- Trades 不明显上升。
- 与 Q1/F3/Quant Guardrail 相比，避免负收益和大幅 underperform。

#### 建议 run id

```text
F6_B2_SIGNAL_PRIORITY_FULL
```

### 10.4 实验 C1：F6 + Thesis Memory

#### 目的

验证持仓 thesis 记忆是否能减少短期噪声卖出，并改善 hold/sell 质量。

该实验对应课题方向 C：记忆与上下文管理。

#### 每个持仓维护的 thesis 结构

```yaml
ticker:
entry_date:
entry_price:
original_thesis:
thesis_type:
  - fundamental
  - recovery
  - momentum
  - defensive
key_catalyst:
invalidation_condition:
current_status:
  - intact
  - weakened
  - invalidated
days_held:
last_action:
recent_trade_quality:
```

#### 规则

- new buy 必须生成 thesis 和 invalidation_condition。
- thesis intact: prefer hold，不因短期噪声卖出。
- thesis weakened: hold 或 reduce。
- thesis invalidated: allow sell，即使在 cooldown 内。
- cooldown 仍默认生效，但 thesis invalidated 可以作为例外。
- 每次交易后更新 thesis_status。

#### 实验假设

C1 如果有效，应当改善 F6 的持仓连续性：

- 减少买入后短期卖出。
- 提高 hold_after_signal_return。
- thesis intact 的持仓未来收益为正或至少优于被错误卖出的持仓。
- thesis invalidated 后的卖出能避免后续下跌。

#### 必须记录

```text
thesis_created_count
thesis_intact_hold_count
thesis_weakened_reduce_count
thesis_invalidated_sell_count
thesis_intact_hold_return_5d
thesis_intact_hold_return_10d
thesis_invalidated_sell_avoided_loss_5d
thesis_invalidated_sell_avoided_loss_10d
```

#### 建议 run id

```text
F6_C1_THESIS_MEMORY_FULL
```

### 10.5 实验 G1：F6 + Alpha Rerank Only

#### 目的

低权限验证 price alpha 是否仍有边际贡献。

该实验是对 Q1/F3/Quant Guardrail 失败后的修正：alpha 只能在 F6 已经生成的候选买入中排序，不能新增股票、不能否决、不能触发卖出。

#### 规则

- F6 先生成 buy/add candidates。
- alpha 只在 candidates 内部 rerank。
- alpha 不能新增股票。
- alpha 不能 veto 高置信 F6 buy。
- alpha 不能触发 sell。
- alpha 不能改变 hold/sell。

Alpha features：

```text
relative_strength_20d
relative_strength_60d
trend_recovery_score
rebound_participation_score
```

#### 实验假设

G1 如果有效，应当说明 price alpha 可以作为弱排序信号存在：

- Return per buy trade 高于 F6。
- buy_after_signal_return 高于 F6。
- 不出现 Q1/F3 那样的收益大幅转负。
- Trades 不显著增加。

#### 必须记录

```text
original_candidate_rank
alpha_reranked_rank
selected_final_buy
buy_after_signal_return
return_per_buy_trade
```

#### 建议 run id

```text
F6_G1_ALPHA_RERANK_ONLY_FULL
```

### 10.6 实验 G3：F6 + Regime Risk Budget Only

#### 目的

低权限验证 regime 是否适合风险预算，而不是因子权重或选股风格切换。

该实验是对 F4 和 F5_REGIME_FACTOR_WEIGHTS 失败后的修正：regime 不再控制个股选择或因子权重，只控制组合层风险预算。

#### Regime classes

```text
risk_off
recovery
normal
```

#### Regime features

```text
SPY return 20d
SPY return 60d
SPY above MA20
SPY above MA60
realized volatility 20d percentile
market drawdown from 60d high
VIX percentile if available
```

#### 规则

- regime 不改变个股排序。
- regime 不改变 factor weights。
- regime 不 veto 个股。
- regime 只控制 gross exposure、max single_position、new_buy_threshold。

Risk budget：

```yaml
risk_off:
  max_gross_exposure: 0.70
  max_single_position: 0.08
  new_buy_threshold: high
  allow_add_to_winners: false
  allow_risk_reducing_sell: true

recovery:
  max_gross_exposure: 0.90
  max_single_position: 0.10
  new_buy_threshold: normal
  allow_add_to_winners: true
  cooldown_days: 5

normal:
  max_gross_exposure: 0.95
  max_single_position: 0.10
  new_buy_threshold: normal
  allow_add_to_winners: true
```

#### 实验假设

G3 如果有效，应当表现为：

- April drawdown 期间回撤低于 F6。
- May-June rebound 期间仍能恢复较好收益。
- Return 不明显低于 F6。
- Regime 只改变 exposure，不破坏 F6 的 stock selection。

#### 建议 run id

```text
F6_G3_REGIME_RISK_BUDGET_FULL
```

### 10.7 第四阶段统一评估指标

所有实验必须同时对比：

```text
F6 baseline
20-stock equal-weight Buy & Hold
```

核心指标：

```text
Total Return
Excess vs Buy & Hold
Sortino
Sortino Δ vs Buy & Hold
Sharpe
Max Drawdown
MDD improvement vs Buy & Hold
Trades
Trades Notional
Average cash ratio
Return per trade
Transaction-cost-adjusted return
```

行为归因：

```text
buy_after_signal_return
sell_after_signal_return
hold_after_signal_return
rejected_trade_future_return
executed_trade_future_return
skipped_trade_reason
thesis_intact_hold_return
thesis_invalidated_sell_return
```

阶段表现：

```text
April drawdown behavior
May-June rebound participation
monthly returns
```

### 10.8 第四阶段优先级

建议优先顺序：

1. A2 Risk Review Agent：最贴近“决策机制改进”，且权限低，风险相对可控。
2. C1 Thesis Memory：最贴近 F5/F6 已经成功的 memory 方向，有望解释和减少错误卖出。
3. G1 Alpha Rerank Only：用于验证 price alpha 在低权限场景下是否有边际贡献。
4. G3 Regime Risk Budget Only：用于验证 regime 是否只适合组合层风控。
5. B2 Signal Priority Layer：作为整合型实验，建议在 G1/G3 有结果后再跑，避免一开始组合后 attribution 不清。

如果时间只允许先跑三组，推荐：

```text
F6_A2_RISK_REVIEW_FULL
F6_C1_THESIS_MEMORY_FULL
F6_G1_ALPHA_RERANK_ONLY_FULL
```

### 10.9 第四阶段预期研究贡献

第四阶段的目标不是证明“更多模块一定更好”，而是回答：

1. 风险审查是否可以作为低权限二次决策层，而不重蹈 generic reflection 的失败？
2. 价格 alpha 在不能主导选股时，是否仍能提高买入候选质量？
3. Regime 在不能改变风格权重时，是否仍能通过风险预算改善回撤？
4. Thesis memory 是否能比简单 cooldown 更准确地区分“该持有”和“该卖出”？

如果第四阶段成功，最终报告可以形成一个清晰闭环：

```text
cleaned fundamental signal 提高输入质量
anti-overtrade memory 减少重复低质量交易
cooldown 限制短期反向交易
低权限 review/rerank/risk-budget/thesis-memory 模块进一步改善交易质量
```

## 11. 第四阶段实验结果：F6 低权限模块验证

### 11.1 对照组

第四阶段统一以当前综合最优版本 F6 作为 base：

```text
F6 = F5_COOLDOWN_5D
```

同时按照课题文档中的要求，将策略结果与 20-stock equal-weight Buy & Hold 进行比较，而不是只和 SPY 比较。

| 对照组 | Total Return | Sortino | Sharpe | Max Drawdown | Trades | Trades Notional |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 20-stock equal-weight Buy & Hold | +0.7348% | 0.017979 | - | -14.9520% | - | - |
| F6 baseline | +3.9913% | 0.043074 | 0.556719 | -9.1603% | 261 | 418155.76 |

F6 相比 20 股等权买入持有：

```text
Excess Return: +3.2867%
Sortino Delta: +0.025096
MDD Improvement: +5.7916%
```

因此第四阶段的核心问题是：新模块能否在不破坏 F6 收益和回撤优势的前提下，进一步提高交易质量。

### 11.2 第四阶段完整结果

| 实验 | Total Return | Excess vs Buy & Hold | Sortino | Sortino Delta | Sharpe | Max Drawdown | MDD Improvement | Trades | Trades Notional |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| F6 baseline | +3.9913% | +3.2867% | 0.043074 | +0.025096 | 0.556719 | -9.1603% | +5.7916% | 261 | 418155.76 |
| F6_A2_RISK_REVIEW_FULL | +0.3347% | -0.3699% | 0.011802 | -0.006177 | 0.168332 | -9.8599% | +5.0921% | 87 | 197932.95 |
| F6_C1_THESIS_MEMORY_FULL | -3.3181% | -4.0227% | -0.018144 | -0.036122 | -0.227336 | -12.0198% | +2.9321% | 108 | 232941.50 |
| F6_G1_ALPHA_RERANK_ONLY_FULL | -0.2890% | -0.9936% | 0.006729 | -0.011249 | 0.089823 | -11.2849% | +3.6670% | 142 | 267470.91 |
| F6_G3_REGIME_RISK_BUDGET_FULL | +2.7461% | +2.0415% | 0.035571 | +0.017592 | 0.431495 | -10.7435% | +4.2085% | 239 | 400310.71 |
| F6_B2_SIGNAL_PRIORITY_FULL | +1.6101% | +0.9055% | 0.024798 | +0.006819 | 0.307936 | -12.1019% | +2.8501% | 264 | 321177.75 |

### 11.3 单实验分析

#### A2 Risk Review Agent

A2 明显降低了交易次数：

```text
Trades: 261 -> 87
Trades Notional: 418155.76 -> 197932.95
```

但收益从 +3.9913% 降到 +0.3347%，Sortino 也从 0.043074 降到 0.011802。日志中 Risk Review 对很多交易给出了 `reject_low_quality_trade`，其中常见原因是 `small_notional_trade`。

结论：

- 风险审查层确实能压低交易频率。
- 但当前规则过于保守，过滤掉了太多有效交易机会。
- A2 不适合作为当前主线版本。
- 如果后续继续优化，应放宽 reject 权限，让 Risk Review 更多使用 `reduce_size` 或 `delay`，减少直接拒绝。

#### C1 Thesis Memory

C1 表现最差：

```text
Total Return: -3.3181%
Sharpe: -0.227336
Sortino: -0.018144
```

这说明当前 thesis memory 没有稳定改善持仓质量，反而可能让策略在错误 thesis 下继续持有，或者让卖出决策变得迟缓。

结论：

- thesis memory 的方向在研究叙事上合理，但当前实现还不够可靠。
- 主要问题不是“记忆不该做”，而是 thesis 状态更新和 invalidation condition 还没有形成足够可执行的判断。
- 该模块暂时不进入最优策略。
- 如果重做，应先增强日志和归因，例如明确输出 `thesis_intact_hold_return`、`thesis_invalidated_sell_return`，再决定是否继续。

#### G1 Alpha Rerank Only

G1 的设计是让 price alpha 只在 F6 候选股内部重排，不新增股票、不 veto、不触发卖出。但结果仍然弱于 F6：

```text
Total Return: -0.2890%
Excess vs Buy & Hold: -0.9936%
MDD: -11.2849%
```

结论：

- 低权限 alpha rerank 仍然没有提供正向边际贡献。
- 这进一步支持前面 Q1/F3 的结论：当前 price quant 因子虽然有解释价值，但直接参与排序容易误伤 LLM 原本有效的判断。
- 在当前数据区间内，price alpha 更适合做事后分析或轻量风控参考，而不是参与最终候选排序。

#### G3 Regime Risk Budget Only

G3 是第四阶段中表现最好的新增模块：

```text
Total Return: +2.7461%
Excess vs Buy & Hold: +2.0415%
Sortino: 0.035571
Sharpe: 0.431495
```

但它仍然弱于 F6：

```text
F6 Total Return: +3.9913%
G3 Total Return: +2.7461%
```

结论：

- Regime 只做风险预算，比 Regime-specific Factor Weights 更稳。
- 这说明 regime 不适合直接改变选股风格或因子权重，但可以作为组合层风险控制信号。
- 当前 G3 仍然偏保守，在 May-June rebound 阶段可能限制了反弹参与。
- 如果要继续优化，建议做轻量版 G3，而不是加更多 regime 逻辑：

```text
F6_G3_LIGHT_REGIME_BUDGET
risk_off max_gross_exposure: 0.80
normal max_gross_exposure: 1.00
只在极端 risk_off 下提高 new buy threshold
不限制 add-to-winners
```

#### B2 Signal Priority Layer

B2 将 fundamental、price alpha、risk、regime、memory 统一放入权限分层框架。结果为正收益，但仍明显弱于 F6：

```text
Total Return: +1.6101%
Excess vs Buy & Hold: +0.9055%
Sharpe: 0.307936
MDD: -12.1019%
```

结论：

- 权限分层的研究逻辑是合理的，但一次性叠加多个低权限模块仍然会产生过度约束。
- B2 的问题不是某一个模块单独失效，而是多个模块共同削弱了 F6 的进攻性。
- 当前不建议作为主线版本。

### 11.4 第四阶段总体结论

第四阶段没有任何新增模块超过 F6 baseline。

当前综合排序为：

| Rank | Version | 判断 |
| ---: | --- | --- |
| 1 | F6 = F5_COOLDOWN_5D | 当前最优，保留为主线 |
| 2 | F6_G3_REGIME_RISK_BUDGET_FULL | 有研究价值，但收益低于 F6 |
| 3 | F6_B2_SIGNAL_PRIORITY_FULL | 正收益，但过度约束 |
| 4 | F6_A2_RISK_REVIEW_FULL | 降低交易数有效，但牺牲收益过大 |
| 5 | F6_G1_ALPHA_RERANK_ONLY_FULL | price alpha rerank 未提供增量 |
| 6 | F6_C1_THESIS_MEMORY_FULL | 当前实现失败 |

可以形成的研究结论是：

1. `cleaned fundamental signal` 是最有效的输入改进。
2. `anti-overtrade memory` 和 `cooldown_days=5` 是最有效的交易行为约束。
3. 高权限 quant/regime 会破坏 LLM 原有判断。
4. 低权限 quant/regime 虽然更稳，但目前仍未超过 F6。
5. 风险审查和 thesis memory 需要更精细的日志归因和规则校准，否则容易过度保守或错误持有。

因此当前推荐的最终主线版本仍然是：

```text
F6 = FUND1 cleaned fundamental signal
   + F5 anti-overtrade memory
   + cooldown_days = 5
   + no generic reflection
   + no high-authority quant/regime
```

如果需要继续做一轮小实验，最有价值的方向不是重跑 A2/C1/G1/B2，而是基于 G3 做更轻量的风险预算版本：

```text
F6_G3_LIGHT_REGIME_BUDGET
```

目标是只在极端风险环境下降低仓位，避免在正常和反弹阶段压制收益。

## 12. 第五阶段实验结果：F7 低权限行为保持实验

### 12.1 实验背景

第四阶段结果显示，A2 risk review、C1 thesis memory、G1 alpha rerank、G3 full regime risk budget、B2 signal priority 均未超过 F6。第五阶段因此不再增加复杂 agent，也不引入高权限量化选股或 regime 选股，而是继续以 F6 为唯一 base，测试更低权限、更行为保持的四个 F7 变体。

统一设置如下：

```text
start = 2025-03-03
end = 2025-06-30
model = deepseek-v4-flash
data_mode = offline_only
reflection_agent = false
fundamental = cleaned_signal
base = F6
benchmark = 20-stock equal-weight Buy & Hold
```

F6 定义保持不变：

```text
F6 = cleaned fundamental signal
   + anti-overtrade memory
   + 5-day cooldown
   + no generic reflection
   + no high-authority quant/regime modules
```

### 12.2 F7 实验设计

| 实验 | 核心设计 | 权限边界 |
| --- | --- | --- |
| F7A_COOLDOWN_ONLY_REVERSAL_FULL | cooldown 只阻止 5 日内反向交易：买入后短期默认卖出、卖出后短期默认回买 | 不阻止同向加仓、赢家加仓、风险降低型卖出、再平衡或 thesis invalidated 高置信卖出 |
| F7B_LIGHT_REGIME_BUDGET_FULL | 极轻量 regime risk budget | regime 不选股、不重排、不 veto、不改因子权重，只在 extreme risk-off 下限制组合层 gross exposure |
| F7C_SOFT_RISK_REVIEW_FULL | F6 出单后增加 soft risk review | 默认 approve，只允许 approve、reduce_size、delay；hard reject 仅限硬 cooldown、重复亏损同向交易、数据质量问题、仓位限制 |
| F7D_COOLDOWN_ONLY_REVERSAL_PLUS_LIGHT_REGIME_FULL | 组合 F7A 与 F7B | 不加入 soft risk review，用于测试个股层 churn 控制与组合层风险预算是否互补 |

### 12.3 F7 完整结果

下表按课题文档口径，主比较对象为 F6，辅助比较对象为 20 股等权 Buy & Hold。Buy & Hold 口径沿用前文统一 benchmark：Total Return +0.7348%，Sortino 0.017978，Max Drawdown -14.9519%。

| 实验 | Total Return | vs F6 Return | Excess vs B&H | Sortino | vs F6 Sortino | Sortino Delta vs B&H | Sharpe | Max Drawdown | MDD Improvement vs B&H | Trades | Trades Notional | Avg Cash Ratio |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| F6 baseline | +3.9913% | 0.0000% | +3.2867% | 0.043074 | 0.000000 | +0.025096 | 0.556719 | -9.1603% | +5.7916% | 261 | 418155.76 | n/a |
| F7A_COOLDOWN_ONLY_REVERSAL_FULL | +2.4401% | -1.5512% | +1.7355% | 0.031284 | -0.011790 | +0.013306 | 0.398754 | -11.7178% | +3.2341% | 70 | 178832.39 | 2.12% |
| F7B_LIGHT_REGIME_BUDGET_FULL | +2.3280% | -1.6633% | +1.6234% | 0.030287 | -0.012788 | +0.012309 | 0.373755 | -12.3172% | +2.6347% | 283 | 251866.65 | 7.69% |
| F7C_SOFT_RISK_REVIEW_FULL | +3.1997% | -0.7916% | +2.4951% | 0.040001 | -0.003073 | +0.022023 | 0.473993 | -11.2418% | +3.7101% | 138 | 296683.84 | 8.57% |
| F7D_COOLDOWN_ONLY_REVERSAL_PLUS_LIGHT_REGIME_FULL | +0.6573% | -3.3340% | -0.0473% | 0.013972 | -0.029102 | -0.004006 | 0.197753 | -8.9461% | +6.0058% | 36 | 209101.09 | 4.16% |

### 12.4 月度收益与反弹参与

| 实验 | 2025-03 | 2025-04 | 2025-05 | 2025-06 | April drawdown behavior | May-June rebound participation |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| F7A | -2.9672% | -0.1110% | +3.3619% | +2.2615% | 4 月几乎持平，但 3 月损失较大 | 5-6 月有反弹参与，但强度不足以追上 F6 |
| F7B | -4.7622% | -2.6676% | +5.4555% | +4.6886% | 3-4 月连续回撤，light regime 未能有效保护 | 5-6 月反弹参与较好，但前期损失过大 |
| F7C | -3.8891% | -2.3802% | +6.2402% | +3.5382% | 4 月仍有明显下行，soft review 没有精准降低最大回撤 | 5 月参与最好，是四组里最接近 F6 的版本 |
| F7D | +0.4360% | -2.7378% | +3.7252% | -0.6592% | 3 月防守较强，MDD 最好 | 6 月反弹参与不足，收益被明显压制 |

### 12.5 诊断日志汇总

| 实验 | cooldown_block_count | reversal_block_count | allowed_same_direction_add_count | allowed_risk_reducing_sell_count | regime_intervention_count | add_to_winners_allowed_count | Risk Review |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| F7A | 1 | 1 | 11 | 20 | 0 | 0 | n/a |
| F7B | 41 | 41 | 72 | 90 | 3 | 71 | n/a |
| F7C | 10 | 10 | 44 | 31 | 0 | 0 | reviewed=156, approved=124, reduced=14, delayed=18, rejected=0 |
| F7D | 0 | 0 | 2 | 9 | 4 | 7 | n/a |

诊断信息说明：

1. F7A 的 reversal cooldown 实际只拦截 1 次，说明“只阻止短期反向交易”没有足够触发频率，难以解释交易数从 261 降到 70 的全部变化。
2. F7B 的 regime intervention 只有 3 次，但交易数反而升至 283，说明 light regime 没有形成有效的组合保护。
3. F7C 符合 soft risk review 的设计：没有 hard reject，大多数交易被 approve，少量交易被 reduce 或 delay。它是本轮最接近 F6 的版本。
4. F7D 的 MDD 最好，但几乎没有 reversal block，收益下降主要来自组合行为更保守和反弹参与不足。

### 12.6 单实验分析

#### F7A Cooldown Only Reversal

F7A 的主要优点是显著降低交易数：

```text
Trades: 261 -> 70
Trades Notional: 418155.76 -> 178832.39
```

但收益从 +3.9913% 降到 +2.4401%，Sortino 从 0.043074 降到 0.031284，最大回撤也从 -9.1603% 变差到 -11.7178%。由于诊断日志显示 reversal block 只有 1 次，说明该模块没有精准命中足够多的短期反向 churn。它降低了交易频率，但没有提高单位交易质量。

结论：F7A 不适合作为 F6 的替代版本。cooldown-only-reversal 的研究逻辑合理，但当前样本中触发太少，边际贡献不足。

#### F7B Light Regime Budget

F7B 原本目标是避免 G3_FULL 过度保守，只在 extreme risk-off 下限制组合总敞口。结果如下：

```text
Total Return: +2.3280%
Sortino: 0.030287
Max Drawdown: -12.3172%
Trades: 283
```

该结果弱于 F6，也弱于上一轮 G3_FULL 的 +2.7461%。诊断日志中 regime_intervention_count 只有 3，说明 light regime 并未真正承担有效风控；同时 trades 增加到 283，意味着它没有减少行为噪声。

结论：F7B 不保留为主线。Regime 作为组合风险预算仍有研究价值，但当前 light 版本太弱，既没有保护 3-4 月，也没有提升 Sortino。

#### F7C Soft Risk Review

F7C 是本轮最接近 F6 的版本：

```text
Total Return: +3.1997%
Sortino: 0.040001
Trades: 138
Risk Review: reviewed=156, approved=124, reduced=14, delayed=18, rejected=0
```

相比第四阶段 A2 hard risk review，F7C 明显更合理。A2 因 hard reject 过多导致收益只剩 +0.3347%，而 F7C 保留了大部分交易，只对少量交易 reduce 或 delay，因此收益没有崩掉，交易数也从 F6 的 261 降到 138。

问题是 F7C 的 Max Drawdown 为 -11.2418%，比 F6 的 -9.1603% 更差。说明 soft review 虽然减少了交易，但没有精准减少真正导致下行风险的交易；部分 delay 可能还降低了反弹参与效率。

结论：F7C 可以作为后续候选方向继续优化，但不能替代 F6。下一步应减少 delay，更多使用轻量 reduce_size，并针对 4 月回撤和 5-6 月反弹做事后归因。

#### F7D Cooldown Reversal + Light Regime

F7D 组合了 F7A 与 F7B，但结果显示两者不互补：

```text
Total Return: +0.6573%
Sortino: 0.013972
Max Drawdown: -8.9461%
Trades: 36
```

它的最大回撤略优于 F6，是四组里防守最好的一组；但收益大幅下降，且低于 20 股 Buy & Hold。月度收益显示 F7D 在 6 月为 -0.6592%，说明它明显错过了后段反弹。

结论：F7D 不值得保留。它证明“更少交易 + 更低回撤”并不自动等于更好的 Sortino；如果牺牲了上涨参与，组合层风险预算会变成收益压制器。

### 12.7 第五阶段总体结论

第五阶段没有任何 F7 变体超过 F6。

综合排序如下：

| Rank | Version | 判断 |
| ---: | --- | --- |
| 1 | F6 baseline | 仍是当前主线版本，收益、Sortino、Sharpe 综合最优 |
| 2 | F7C_SOFT_RISK_REVIEW_FULL | 最接近 F6，交易数明显下降，但 MDD 变差，需继续调优 |
| 3 | F7A_COOLDOWN_ONLY_REVERSAL_FULL | 交易数最低之一，但收益和回撤弱于 F6，reversal block 触发太少 |
| 4 | F7B_LIGHT_REGIME_BUDGET_FULL | 未形成有效风控，收益、Sortino、MDD 均弱于 F6 |
| 5 | F7D_COOLDOWN_ONLY_REVERSAL_PLUS_LIGHT_REGIME_FULL | MDD 最好，但收益被严重压制，错过反弹 |

本阶段可以形成的研究结论是：

1. F6 的 5-day cooldown 仍是目前最稳的行为约束；将 cooldown 改成 only-reversal 后没有带来增量。
2. Light regime budget 如果触发太少，就无法提供有效保护；如果进一步加强，又可能重蹈 G3_FULL 错过反弹的问题。
3. Soft risk review 的方向比 hard risk review 更合理，因为它不会大规模 reject 有效交易。
4. 当前最值得继续优化的是 F7C，但优化目标不是增加权限，而是改进 reduce/delay 的触发条件，使其减少 4 月回撤而不牺牲 5-6 月反弹。
5. 主线版本仍应保留为 F6，不建议把 F7A、F7B、F7C 或 F7D 直接升级为最终策略。

因此，当前推荐主线仍然是：

```text
F6 = cleaned fundamental signal
   + anti-overtrade memory
   + 5-day cooldown
   + no generic reflection
   + no high-authority quant/regime modules
```

后续若继续做小实验，建议只围绕 F7C 做低权限微调：

```text
F7C_v2_SOFT_RISK_REVIEW_REDUCE_ONLY
- hard reject 仍只用于硬约束
- 减少 delay，避免错过反弹
- 对低置信和小 notional 不 reject，只做轻量 reduce_size
- 记录 reduced/delayed trade 的 5d/10d future return，用于判断 review 是否真的有信息含量
```

## 13. 第六阶段实验计划：F8 交易行为修正实验

### 13.1 实验背景

前五个阶段的实验已经说明，当前能够提升表现的方向主要有两类：

```text
1. 改善输入质量：cleaned fundamental signal
2. 改善交易行为：anti-overtrade memory + cooldown
```

进一步的 attribution analysis 显示，当前最大短板不是买入，而是卖出：

```text
Buy future return 整体仍有一定正向信息；
Sell future return 普遍较差，很多 sell 后 5d/10d 股票继续上涨。
```

同时，F7C 的 soft risk review 结果显示：

```text
risk_review_delay: 未来 5d/10d 平均为正收益，可能误伤 alpha
risk_review_reduce: 未来 10d 明显为负收益，说明 reduce_size 有信息含量
```

此外，symbol attribution 显示两个具体失败模式：

1. `BA` 是明确 missed winner。它是 20 股区间收益 Top5，但表现较好的实验几乎没有持仓，说明模型对高波动反弹股捕捉不足。
2. `V` 是明显 false comfort holding。模型过度偏好“高质量稳健叙事”，但没有足够用 relative strength 验证它是否真的有 alpha。

因此，第六阶段不再增加复杂 agent，也不使用高权限 quant/regime selection，而是专门围绕交易行为做四个低权限、可归因实验。

### 13.2 统一实验设置

F8 继续以 F6 为唯一 base：

```text
F6 = cleaned fundamental signal
   + anti-overtrade memory
   + 5-day cooldown
   + no generic reflection
   + no high-authority quant/regime modules
```

统一设置如下：

```text
start = 2025-03-03
end = 2025-06-30
model = deepseek-v4-flash
data_mode = offline_only
reflection_agent = false
fundamental = cleaned_signal
benchmark = 20-stock equal-weight Buy & Hold
shared_data_cache = $HOME/.cache/stockbench/data-cache
```

F8 的核心原则：

```text
只修正具体交易行为；
不新增复杂 agent；
不让 quant/regime 直接选股、rerank、veto；
不覆盖 F6 原始 alpha selection；
所有模块必须能通过 attribution table 解释干预是否有效。
```

### 13.3 F8A：Sell Discipline Layer

```text
F8A_SELL_DISCIPLINE_FULL
```

#### 目标

解决当前最明确的失败模式：卖出质量差、过早卖出赢家。

当前 attribution 显示，多组实验的 sell future return 为负，说明策略经常在卖出后错过后续上涨。F8A 的目标不是禁止卖出，而是在卖出前增加一个低权限的 sell discipline layer，保护仍然具备相对强度的赢家。

#### 设计

在 F6 生成交易后，如果某只股票的 proposed action 是：

```text
sell
decrease
close
```

则进入 sell discipline 检查。

如果股票仍满足 winner / relative strength 条件，则默认把卖出改为：

```text
hold
或 reduce_size
```

而不是直接执行 full sell。

建议使用的保护条件：

```text
return_20d_rank_pct >= 0.60
或 return_60d_rank_pct >= 0.60
或 current_position_pnl > 0 且 recent momentum 未破坏
或 price_above_20d_ma = true
或 stock 是 portfolio top performer
```

允许卖出的例外条件：

```text
thesis_invalidated
data_quality_issue
hard position limit breach
20d relative strength 明显转弱
5d/20d momentum 同时为负
price below 20d_ma 且 below 50d_ma
风险降低型 partial sell
```

#### 权限边界

F8A 只能处理 sell/decrease/close：

```text
不能新建买入；
不能改变买入股票排序；
不能提高仓位；
不能覆盖 hard risk constraints；
不能取消 thesis_invalidated 的高置信卖出。
```

#### 主要诊断指标

```text
sell_reviewed_count
sell_blocked_to_hold_count
sell_reduced_count
sell_allowed_count
sell_allowed_reason
sell_block_reason
protected_winner_sell_count
protected_winner_future_return_5d/10d
allowed_sell_future_return_5d/10d
sell_future_return_5d/10d before/after
winner_premature_sell_count
```

#### 成功标准

F8A 只有在同时满足以下条件时才有价值：

```text
sell future return 改善；
Total Return 不低于 F6 太多；
Sortino 高于 F6 或接近 F6；
Max Drawdown 不明显变差；
May-June rebound participation 不下降。
```

### 13.4 F8B：Reduce-Only Risk Review

```text
F8B_REDUCE_ONLY_RISK_REVIEW_FULL
```

#### 目标

继承 F7C soft risk review 的优点，但去掉最可疑的 delay。

F7C 结果显示：

```text
risk_review_delay: 5d +0.43%, 10d +1.55%
risk_review_reduce: 5d -0.13%, 10d -4.32%
```

这说明 delay 可能错过上涨机会，而 reduce_size 更可能降低坏交易仓位。因此 F8B 改为 reduce-only risk review。

#### 设计

在 F6 proposed trades 后加入 soft risk review：

```text
default = approve
allowed actions = approve, reduce_size
hard reject only for hard constraints
delay disabled
```

建议规则：

```text
small_notional_trade -> approve，不 delay
low_conviction -> reduce_size，不 delay
generic_market_risk -> reduce_size，不 reject
excessive_position_size -> reduce_size
repeated_same_direction_loss_trade -> reduce_size 或 hard reject
position_limit_breach -> cap/reject
data_quality_issue -> reject
hard cooldown violation -> reject
```

#### 权限边界

F8B 不能：

```text
创建新买入；
强制卖出；
改变股票排序；
覆盖 F6 alpha selection；
覆盖 cooldown；
使用 hard reject 处理 low_conviction、small_notional_trade 或 generic market risk。
```

#### 主要诊断指标

```text
risk_reviewed_count
approved_count
reduced_count
rejected_count
delay_count_should_be_zero
reduced_reason
rejected_reason
reduced_trade_future_return_5d/10d
approved_trade_future_return_5d/10d
executed_trade_future_return_5d/10d
return_per_trade
```

#### 成功标准

F8B 需要证明：

```text
比 F7C 少误伤 alpha；
比 F6 降低无效交易或提高 return per trade；
不明显牺牲 Total Return；
Sortino 或 Max Drawdown 至少一项改善。
```

### 13.5 F8C：Rebound Catch-Up Tag

```text
F8C_REBOUND_CATCHUP_TAG_FULL
```

#### 目标

解决 BA missed winner 问题。

BA 在 2025-03-03 到 2025-06-30 区间是 20 股真实 Top5 winner，但表现较好的实验几乎没有有效持仓。这说明模型对高波动反弹股捕捉不足，容易偏向稳健叙事股，而忽视从深度回撤中恢复的 rebound winner。

F8C 不直接强制买入 BA，也不做 rerank，而是给 LLM 增加一个低权限标签：

```text
rebound_candidate = true/false
```

#### 设计

对每只股票计算轻量 rebound signal。建议条件：

```text
previous_drawdown_20d 或 previous_drawdown_60d 较深
recent_return_10d_rank_pct >= 0.70
recent_return_20d_rank_pct >= 0.70
price recovered above 20d_ma
relative_strength_improvement >= threshold
```

输出到 prompt 的形式应是解释性标签，而不是直接分数排序：

```text
rebound_candidate:
  enabled: true
  reason: "Recovered from deep drawdown; recent 20d relative strength top 20%; price back above 20d MA"
```

#### 权限边界

F8C 只能提供 context：

```text
不能直接买入；
不能 rerank；
不能 veto；
不能修改仓位上限；
不能改变 factor weights；
不能强迫模型选择 rebound stock。
```

#### 主要诊断指标

```text
rebound_candidate_count
rebound_candidate_symbols_by_day
rebound_candidate_bought_count
rebound_candidate_avg_exposure
missed_rebound_candidate_count
BA_rebound_signal_days
BA_buy_count
BA_avg_exposure
BA_exposure_proxy_contribution
rebound_candidate_future_return_5d/10d
non_rebound_candidate_future_return_5d/10d
```

#### 成功标准

F8C 不是看是否一定买 BA，而是看：

```text
BA/HON/IBM 等 rebound winner 的 exposure 是否提高；
missed winner count 是否下降；
Total Return 和 Sortino 是否不低于 F6；
不会因为追涨噪声导致 MDD 明显恶化。
```

### 13.6 F8D：Quality Trap Cap

```text
F8D_QUALITY_TRAP_CAP_FULL
```

#### 目标

解决 V false comfort holding 问题。

V 在区间内实际收益为负，但多个表现较好的实验都长期重仓 V。这说明模型容易把“高质量稳健公司叙事”误当成当前 alpha。F8D 的目标是限制这类 quality trap 股票继续扩大仓位。

#### 设计

对每只股票计算轻量 quality trap warning。触发条件示例：

```text
fundamental/company quality 看起来稳定
但 return_20d_rank_pct < 0.50
且 return_60d_rank_pct < 0.50
且 rebound_participation 弱
且 price below 20d_ma 或 50d_ma
```

触发 warning 后：

```text
不允许 add-to-position
不阻止 sell
不强制 sell
target_position_cap 降到 5%-6%
如果已有仓位高于 cap，只允许自然减仓或风险审查下 partial reduce
```

#### 权限边界

F8D 只能限制加仓和仓位上限：

```text
不能强制卖出；
不能 veto 初始小仓位；
不能替代 LLM 选股；
不能惩罚所有高质量股；
只有 quality narrative 与 relative strength 背离时才触发。
```

#### 主要诊断指标

```text
quality_trap_warning_count
quality_trap_symbols_by_day
quality_trap_add_block_count
quality_trap_position_cap_count
V_quality_trap_days
V_avg_exposure
V_buy_notional
V_exposure_proxy_contribution
quality_trap_future_return_5d/10d
blocked_quality_trap_add_future_return_5d/10d
```

#### 成功标准

F8D 需要证明：

```text
V 等 false comfort holdings 的负贡献下降；
JPM/MSFT/GS 等有效暴露不被误伤；
Total Return 或 Sortino 改善；
MDD 不明显恶化；
不是简单变成更高现金比例。
```

### 13.7 F8 实验汇总表

| 实验 | 解决的问题 | 主要干预 | 权限级别 | 预期收益来源 | 主要风险 |
| --- | --- | --- | --- | --- | --- |
| F8A_SELL_DISCIPLINE_FULL | 卖出质量差，过早卖赢家 | 将部分 sell 改成 hold/reduce | 低权限，只处理 sell | 改善 sell future return，保留 winner | 该卖不卖，增加回撤 |
| F8B_REDUCE_ONLY_RISK_REVIEW_FULL | delay 误伤 alpha | 去掉 delay，只保留 reduce_size | 低权限，post-trade review | 降低坏交易仓位，不错过机会 | reduce 过多导致收益被压 |
| F8C_REBOUND_CATCHUP_TAG_FULL | BA missed winner | 增加 rebound_candidate 标签 | 只提供 context | 提高 rebound winner exposure | 追涨噪声 |
| F8D_QUALITY_TRAP_CAP_FULL | V false comfort holding | 限制弱相对强度质量股加仓 | 限制加仓/仓位 cap | 减少无 alpha 质量股拖累 | 误伤短暂整理后的强股 |

### 13.8 F8 评估指标

所有 F8 实验都必须继续报告标准指标：

```text
Total Return
Excess vs Buy & Hold
Sortino
Sortino Delta vs Buy & Hold
Sharpe
Max Drawdown
MDD Improvement vs Buy & Hold
Trades
Trades Notional
Average Cash Ratio
Return per Trade
transaction-cost-adjusted return if available
monthly returns
April drawdown behavior
May-June rebound participation
```

同时必须生成 attribution tables：

```text
module_intervention_attribution.csv
trade_future_by_side.csv
intervention_future_by_type.csv
missed_winner_analysis.csv
focus_exposure_attribution.csv
strategy_vs_market_top5.csv
```

F8 额外关注以下诊断：

```text
buy_future_return_5d/10d
sell_future_return_5d/10d
blocked_sell_future_return_5d/10d
reduced_trade_future_return_5d/10d
BA_avg_exposure
BA_buy_count
BA_exposure_proxy_contribution
V_avg_exposure
V_buy_notional
V_exposure_proxy_contribution
JPM/MSFT/GS/HON/IBM exposure preservation
```

### 13.9 F8 判断规则

F8 变体只有在满足以下条件时才认为有效：

```text
1. 不明显牺牲 F6 Total Return；
2. 至少改善 Sortino、MDD、sell future return、false comfort holding、missed winner exposure 中的一项；
3. 干预次数足够解释结果，不是偶然触发；
4. 不通过提高现金比例来制造表面风控；
5. 不引入高权限复杂模块，保持行为归因清晰。
```

优先级建议：

```text
1. F8A_SELL_DISCIPLINE_FULL
2. F8B_REDUCE_ONLY_RISK_REVIEW_FULL
3. F8D_QUALITY_TRAP_CAP_FULL
4. F8C_REBOUND_CATCHUP_TAG_FULL
```

其中 F8A 和 F8B 是最直接对应 attribution 结果的实验，应优先跑；F8C 和 F8D 更接近 alpha behavior correction，需要更谨慎地检查是否引入追涨或误伤。

## 14. 第六阶段实验结果：F8 交易行为修正实验

### 14.1 结果总表

F8 四组实验已经完成。所有 F8 变体仍以 F6 为唯一 base，主比较对象为 F6，辅助比较对象为 20 股等权 Buy & Hold。

参考基准：

```text
F6 = cleaned fundamental signal + anti-overtrade memory + 5-day cooldown
F6 Total Return = +3.9913%
F6 Sortino = 0.043074
F6 Sharpe = 0.556719
F6 Max Drawdown = -9.1603%
F6 Trades = 261

20-stock equal-weight Buy & Hold Return = +0.7348%
```

| 实验 | 主要改动 | Total Return | vs F6 | vs B&H | Sortino | Sharpe | Max Drawdown | Trades | Trades Notional | 结论 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| F8A_SELL_DISCIPLINE_FULL | 对 sell 加赢家保护 | +2.5229% | -1.4684pp | -0.0409pp | 0.033148 | 0.388135 | -13.1485% | 198 | 384100.72 | 保护卖出方向成立，但 hard hold 过粗，回撤恶化 |
| F8B_REDUCE_ONLY_RISK_REVIEW_FULL | 去掉 delay，只允许 approve/reduce | +3.5926% | -0.3987pp | +1.0288pp | 0.040338 | 0.487114 | -13.2106% | 160 | 254420.10 | 最接近 F6，交易数显著下降，但未改善回撤 |
| F8C_REBOUND_CATCHUP_TAG_FULL | 低权限 rebound candidate tag | +3.8273% | -0.1640pp | +1.2635pp | 0.040601 | 0.509349 | -10.4193% | 292 | 396932.50 | 收益最接近 F6，但 rebound tag 实际未触发，归因不成立 |
| F8D_QUALITY_TRAP_CAP_FULL | 限制 quality trap 加仓 | +1.9665% | -2.0248pp | -0.5973pp | 0.028991 | 0.377769 | -9.0893% | 206 | 371666.18 | MDD 略好于 F6，但收益被明显压制 |

### 14.2 月度收益与反弹参与

| 实验 | 2025-03 | 2025-04 | 2025-05 | 2025-06 | 5-6 月反弹参与 |
| --- | ---: | ---: | ---: | ---: | ---: |
| F8A | -4.7008% | -4.8576% | +4.4695% | +5.9554% | +10.3889% |
| F8B | -5.7962% | -3.9333% | +5.9506% | +4.6470% | +10.5978% |
| F8C | -3.6106% | -4.0210% | +4.5882% | +4.3482% | +8.8775% |
| F8D | -1.7876% | -4.4293% | +3.6140% | +3.0705% | +6.6437% |

月度表现说明：

1. F8A 和 F8B 的 5-6 月反弹参与较好，但 3-4 月亏损较大，尤其 MDD 明显差于 F6。
2. F8C 的收益最接近 F6，且 MDD 低于 F8A/F8B，但交易数上升到 292，说明它不是更克制的改进。
3. F8D 的 3 月和 MDD 最稳，但 5-6 月反弹参与最弱，说明 quality trap cap 过度压制上涨暴露。

### 14.3 模块干预诊断

| 实验 | 核心诊断 | 事件数 / 触发情况 | 解释 |
| --- | --- | ---: | --- |
| F8A | sell reviewed | 116 | 对卖出做了实质干预 |
| F8A | sell blocked to hold | 28 | 确实保护了 BA、HON、AMZN 等盈利强势股 |
| F8A | sell allowed | 88 | 大多数卖出仍允许执行 |
| F8B | reviewed | 163 | risk review 有稳定触发 |
| F8B | approved | 153 | 默认 approve，符合低权限设计 |
| F8B | reduced | 10 | 只对少量交易降 size |
| F8B | delayed / rejected | 0 / 0 | 成功去掉 delay，避免 F7C 的 alpha 误伤问题 |
| F8C | rebound_candidate_count | 0 | rebound tag 完全没有触发，不能证明捕捉 BA 类反弹股有效 |
| F8D | quality_trap warning in orders | 100 | 触发频率很高 |
| F8D | add block | 86 | 大量拦截加仓 |
| F8D | resize | 4 | 少量新仓/加仓被缩小 |
| F8D | context warnings | 每日约 10 个 | 规则过宽，容易误伤非 V 股票 |

### 14.4 单实验复盘

#### F8A：Sell Discipline

F8A 针对 F6 的卖出短板，在 proposed sell 后加入低权限 sell discipline。如果持仓盈利、20d/60d 相对强度仍然较好，模块会将卖出改为 hold。

它确实解决了一部分“卖飞赢家”问题。例如日志中多次保护 BA、HON、AMZN：

```text
sell_reviewed_count = 116
sell_blocked_to_hold_count = 28
protected_winner_sell_count = 28
```

失败原因：

1. F8A 把问题从“卖得太早”推向了“卖得太慢”。只要股票是盈利且相对强度较强，就容易被保护，但这并不等于后续继续有 alpha。
2. 它只处理卖出，没有处理“继续持有错误股票”或“错误加仓”的问题。
3. MDD 从 F6 的 -9.1603% 恶化到 -13.1485%，说明 hard hold 增加了下行暴露。

结论：卖出纪律方向成立，但不能再做 hard block。下一轮应改成 sell second-confirmation：证据不足的 full sell 降成 partial sell，而不是直接 hold。

#### F8B：Reduce-Only Risk Review

F8B 继承 F7C soft risk review 的低权限框架，但去掉 delay。历史 attribution 显示 delay 的交易未来 5d/10d 仍上涨，说明 delay 可能误伤 alpha；reduce 的交易未来表现较弱，说明 reduce 更有信息量。

F8B 结果符合设计：

```text
reviewed = 163
approved = 153
reduced = 10
delayed = 0
rejected = 0
```

失败原因：

1. F8B 主要是仓位缩小器，不改变买入 alpha，也没有修正卖出质量。
2. 它将 Trades 从 F6 的 261 降到 160，Return 仍有 +3.5926%，说明 reduce-only 是有效方向；但 MDD 恶化到 -13.2106%，说明它没有精准减少导致回撤的交易。
3. 减少交易和降低 notional 并不自动提高 Sortino。如果减少的是有效暴露，收益也会被压低。

结论：F8B 是 F8 中最值得保留的组件，但下一轮应进一步收窄权限，只 review buy/add，不 review sell。

#### F8C：Rebound Catch-Up Tag

F8C 原本用于解决 BA missed winner 问题。设计思路是给高波动反弹股提供低权限 rebound candidate context，避免模型只偏好稳健叙事而错过 BA 这类反弹赢家。

结果表面上较好：

```text
Total Return = +3.8273%
Sortino = 0.040601
Sharpe = 0.509349
Max Drawdown = -10.4193%
```

但关键诊断显示：

```text
rebound_candidate_count = 0
```

失败原因：

1. rebound 信号定义过严或计算方式不合适，导致 BA、HON、IBM、MSFT 等真实 winner 没有被识别出来。
2. F8C 的接近 F6 表现不能归因于 rebound tag，可能来自 60 日价格上下文变化或 LLM 决策随机性。
3. Trades 上升到 292，说明这组不是通过减少无效交易改善表现。

结论：高反弹股捕捉方向仍然重要，但 F8C 作为主实验没有验证成功。下一步应先做离线 rebound diagnostic，确认 BA 能被规则识别，再接入 LLM。

#### F8D：Quality Trap Cap

F8D 针对 V false comfort holding 问题。它尝试限制“基本面叙事稳定但价格相对强度弱”的股票继续加仓。

它确实降低了回撤：

```text
F8D MDD = -9.0893%
F6 MDD = -9.1603%
```

但收益明显下降：

```text
F8D Total Return = +1.9665%
F6 Total Return = +3.9913%
```

失败原因：

1. quality trap warning 过宽，每天大约触发 10 个股票，实际订单中 warning 100 次、block add 86 次。
2. 规则不只限制 V，也误伤了 MSFT、GS、CAT、UNH、AMGN 等可能只是短期整理的股票。
3. F8D 把“稳健但无 alpha”的问题处理成了广泛降风险，导致 5-6 月反弹参与只有 +6.6437%，明显低于 F8A/F8B。

结论：quality trap 方向正确，但必须更窄、更连续触发、更只限制 add，而不能泛化成全市场弱相对强度惩罚。

### 14.5 F8 阶段结论

F8 没有任何一组明确超过 F6，但它验证了后续 F9 的设计方向：

1. 卖出控制有必要，但不能 hard block，应改成 sell evidence 二次确认。
2. delay 应该删除。F8B 已证明 reduce-only 比 delay 更干净。
3. rebound 捕捉不能直接接入主实验，应先离线验证信号能否识别 BA。
4. quality trap 应保留为研究方向，但触发条件必须窄化，只处理 V-style false comfort holding。
5. F6 仍是主线 base，F8 不作为替代版本。

## 15. 第七阶段实验计划：F9 精准交易行为修正

### 15.1 实验背景

F8 的价值不在于直接提升 F6，而在于明确了四类行为修正的有效边界：

```text
卖出质量差是真问题；
delay 会误伤 alpha，应删除；
BA 类高反弹股捕捉需要先修信号；
V 类 false comfort holding 需要更窄、更连续的 add check。
```

因此 F9 不再做四个大模块，也不做组合版。F9 只做三组更窄、更低权限、更容易归因的实验：

```text
F9A = F6 + buy/add-only reduce review
F9B = F6 + sell second-confirmation
F9C = F6 + narrow quality-trap add check
```

不做 F9D 组合版。只有单组实验明确有效后，再考虑组合。

### 15.2 统一实验设置

所有 F9 实验继续以 F6 为唯一 base：

```text
base = F6
start = 2025-03-03
end = 2025-06-30
model = deepseek-v4-flash
data_mode = offline_only
reflection_agent = false
fundamental = cleaned_signal
anti_overtrade_memory = true
trade_cooldown = 5 trading days
high-authority quant/regime/rerank = false
benchmark = 20-stock equal-weight Buy & Hold
shared_data_cache = $HOME/.cache/stockbench/data-cache
```

F9 统一权限边界：

```text
不创建新买入；
不强制卖出；
不改变股票 ranking；
不覆盖 F6 alpha selection；
不覆盖 cooldown；
不新增复杂 agent；
所有模块只做交易后低权限行为修正。
```

### 15.3 F9A：Buy/Add-only Reduce Review

```text
F9A_BUY_ADD_ONLY_REDUCE_REVIEW_FULL
```

#### 目标

保留 F8B 的优点，进一步收窄权限。F8B 证明 reduce-only 比 delay 更合理，但它仍然 review 所有交易。F9A 只审查 buy/add，不审查 sell。

F9A 解决的问题是：

```text
F6 买入质量总体可接受，但仓位表达可能过冲；
F8B 降低交易数有效，但不应干预卖出；
需要将 risk review 定位为 buy/add sizing brake，而不是交易裁判。
```

#### 规则

F6 先生成 proposed trades。F9A 只处理：

```text
qty > 0
new buy
add-to-position
```

不处理：

```text
sell
partial sell
close
risk-reducing trade
hold
```

允许动作：

```text
approve
reduce_size
```

hard reject 仅允许用于：

```text
hard cooldown violation
position limit breach
data quality issue
```

建议触发规则：

```text
low_confidence buy/add -> reduce_size 50%
high volatility and not rebound candidate -> reduce_size 50%
position already near cap -> reduce to cap
same-symbol repeated add within short window -> reduce_size
small_notional_trade -> approve
generic market risk -> reduce_size, not delay
```

#### 必须记录

```text
buy_add_reviewed_count
buy_add_approved_count
buy_add_reduced_count
buy_add_rejected_count
sell_reviewed_count_should_be_zero
delay_count_should_be_zero
reduced_reason
approved_buy_add_future_return_5d/10d
reduced_buy_add_future_return_5d/10d
return_per_trade
trades_notional
```

#### 成功标准

```text
Total Return 不低于 F6 超过 0.5pp；
Trades 和 Trades Notional 明显低于 F6；
MDD 优于 F6 或 Sortino 不低于 F6；
不能通过大幅提高现金比例制造表面风控；
sell future return 不应因模块干预恶化。
```

### 15.4 F9B：Sell Second-confirmation

```text
F9B_SELL_SECOND_CONFIRMATION_FULL
```

#### 目标

修复 F8A 的 hard hold 问题。F8A 证明保护赢家有价值，但硬阻止 sell 会让组合卖得太慢。F9B 不再简单保护赢家，而是要求 sell 有足够证据。

核心思想：

```text
full sell 需要二次确认；
证据不足的 full sell 降成 partial sell；
证据不足的 partial sell 改成 hold。
```

#### Sell Evidence

F9B 为每个 proposed sell 计算 sell evidence。建议证据项：

```text
relative_strength_20d_rank_pct < 0.40
relative_strength_60d_rank_pct < 0.40
price below 20d moving average
position PnL <= 0 and trend still weakening
profit giveback from recent peak >= 5%-8%
clear thesis_invalidated reason in LLM decision
negative news / fundamental deterioration
consecutive underperformance vs 20-stock universe
```

#### 执行规则

```text
如果是 full sell:
  sell_evidence_count >= 2 -> allow full sell
  sell_evidence_count = 1 -> reduce to partial sell
  sell_evidence_count = 0 -> hold

如果是 partial sell:
  sell_evidence_count >= 1 -> allow partial sell
  sell_evidence_count = 0 -> hold
```

例外情况：

```text
thesis_invalidated_high_confidence -> allow full sell
position limit breach -> allow risk-reducing sell
hard risk limit / data quality issue -> allow sell
severe drawdown with trend breakdown -> allow sell
```

#### 必须记录

```text
sell_reviewed_count
full_sell_allowed_count
full_sell_to_partial_count
sell_to_hold_count
partial_sell_allowed_count
partial_sell_to_hold_count
sell_evidence_count_by_trade
sell_evidence_reason
thesis_invalidated_exception_count
risk_reducing_sell_exception_count
allowed_sell_future_return_5d/10d
blocked_or_reduced_sell_future_return_5d/10d
BA/HON/IBM/MSFT avg exposure
May-June rebound participation
April drawdown behavior
```

#### 成功标准

```text
sell future return 5d/10d 的错误卖出明显减少；
Total Return >= F6 或不明显低于 F6；
MDD 不比 F6 明显恶化；
May-June rebound participation 提升；
BA/HON/IBM/MSFT 的 missed winner exposure 改善；
交易数不能因 partial sell 过多而大幅上升。
```

### 15.5 F9C：Narrow Quality-trap Add Check

```text
F9C_NARROW_QUALITY_TRAP_ADD_CHECK_FULL
```

#### 目标

修复 F8D 的过宽触发问题。F8D 方向正确，确实降低了 MDD，但它把太多股票都当成 quality trap，导致收益被压制。F9C 只处理 V-style false comfort holding。

F9C 关注的不是“质量股不能买”，而是：

```text
高质量稳健叙事 + 低相对强度 + 持有后无 alpha + 模型反复想加仓。
```

#### 触发条件

quality_trap_candidate 必须同时满足：

```text
fundamental_signal positive 或明显 high-quality narrative
20d relative strength rank < 0.40
60d relative strength rank < 0.40
current holding_days >= 10
position PnL <= 0 或 relative performance underperform
recent 5d/10d 没有明显恢复
no strong catalyst
```

相比 F8D，F9C 必须显著降低触发频率。不能每天对半个股票池发 warning。

#### 执行规则

F9C 只处理 buy/add：

```text
首次触发:
  reduce add size by 50%

连续第二次触发:
  block add

连续第三次触发，且持仓仍 underperform:
  allow partial trim suggestion only if F6 already proposes sell
```

禁止行为：

```text
不限制首次小仓买入；
不强制 full sell；
不因单日弱势 hard block；
不惩罚所有低 relative strength 股票；
不误伤有强 catalyst 或 rebound evidence 的股票。
```

#### 必须记录

```text
quality_trap_candidate_count_by_day
quality_trap_symbols_by_day
consecutive_quality_trap_count
quality_trap_add_reduced_count
quality_trap_add_blocked_count
quality_trap_trim_allowed_count
V_quality_trap_days
V_avg_exposure
V_buy_notional
V_exposure_proxy_contribution
non_V_quality_trap_symbol_count
blocked_quality_trap_add_future_return_5d/10d
MSFT/GS/HON/BA false_positive_block_count
```

#### 成功标准

```text
V exposure 或 V add notional 明显下降；
non-V false positive 显著少于 F8D；
Total Return 不像 F8D 那样被压低；
MDD 优于或接近 F6；
MSFT/GS/HON/BA 不被大量误伤；
quality_trap warning 数量远低于 F8D。
```

### 15.6 F9 实验汇总表

| 实验 | 继承自 | 解决的问题 | 核心修正 | 权限 | 主要风险 |
| --- | --- | --- | --- | --- | --- |
| F9A_BUY_ADD_ONLY_REDUCE_REVIEW_FULL | F8B | delay 误伤 alpha、仓位表达过冲 | 只对 buy/add reduce，不审 sell，不 delay | buy/add sizing only | reduce 有效 alpha，收益轻微下降 |
| F9B_SELL_SECOND_CONFIRMATION_FULL | F8A | 卖出质量差、过早卖赢家 | full sell 需要 sell evidence，证据不足降为 partial/hold | sell moderation only | 该卖不卖，回撤扩大 |
| F9C_NARROW_QUALITY_TRAP_ADD_CHECK_FULL | F8D | V-style false comfort holding | 连续触发才 reduce/block add，只针对窄质量陷阱 | add check only | 触发过窄无效果，触发过宽重复 F8D |

### 15.7 F9 优先级和预期

建议运行顺序：

```text
1. F9B_SELL_SECOND_CONFIRMATION_FULL
2. F9A_BUY_ADD_ONLY_REDUCE_REVIEW_FULL
3. F9C_NARROW_QUALITY_TRAP_ADD_CHECK_FULL
```

预期排序：

```text
最有希望提升 alpha leakage：F9B
最稳健降低换手和 notional：F9A
最需要谨慎调参：F9C
```

F9 的核心评价规则：

```text
F9 不是看模块是否“看起来更聪明”，而是看它是否在不改变 F6 选股主逻辑的情况下，修正一类明确失败行为。
```
## 16. F9 实验结果与阶段结论

F9 三组实验已完成，统一设置如下：

```text
start = 2025-03-03
end   = 2025-06-30
model = deepseek-v4-flash
data_mode = offline_only
reflection_agent = false
```

### 16.1 F9 结果总表

| 实验 | 核心设计 | Total Return | Max Drawdown | Sharpe | Sortino | Trades |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| F9A_BUY_ADD_ONLY_REDUCE_REVIEW_FULL | buy/add 只允许 approve 或 reduce size，不 delay sell | +3.36% | -9.73% | 0.500 | 0.039 | 245 |
| F9B_SELL_SECOND_CONFIRMATION_FULL | full sell 需要二次确认，证据不足降为 partial/hold | +0.50% | -12.54% | 0.187 | 0.014 | 186 |
| F9C_NARROW_QUALITY_TRAP_ADD_CHECK_FULL | 窄版 quality-trap add check，连续触发才 reduce/block add | +3.03% | -12.20% | 0.475 | 0.035 | 50 |

对照此前关键版本：

| 对照版本 | Total Return | Max Drawdown | Sharpe | Sortino | Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| FUND1_CLEAN_FUND_FULL | +3.35% | -11.61% | 0.471 | 0.038 | 351 |
| F5_COOLDOWN_5D | +3.99% | -9.16% | 0.557 | 0.043 | 261 |
| F8C_REBOUND_CATCHUP_TAG_FULL | +3.83% | -10.42% | 0.509 | 0.041 | - |

### 16.2 主要结论

#### 16.2.1 F9A 是 F9 中唯一接近可用的版本

F9A 的收益为 +3.36%，基本回到 FUND1 水平，同时最大回撤从 FUND1 的 -11.61% 改善到 -9.73%，交易数也从 FUND1 的 351 降到 245。

这说明 buy/add review 如果只做低权限的 size reduction，而不是 delay 或 hard reject，可以在不明显牺牲收益的情况下改善回撤和交易质量。F9A 没有超过 F5_COOLDOWN_5D，但它验证了一个有价值的方向：买入/加仓审查应以缩小仓位为主，而不是阻断决策。

后续如果继续使用 F9A 思路，建议只把它作为 F10 组合里的轻量 sizing layer，而不是替代 F5_COOLDOWN_5D 主线。

#### 16.2.2 F9B 明确失败

F9B 的收益只有 +0.50%，Sortino 只有 0.014，最大回撤扩大到 -12.54%。虽然交易数降到 186，但收益被明显压制。

这说明 sell second confirmation 当前设计过强。它本来想减少卖飞 winner，但实际更可能导致该卖不卖，或者把卖出动作拖成低效率 partial sell / hold，导致风险释放不及时。

结论是：不能把“保护 winner”泛化成对 sell 的普遍二次确认。后续如果做 winner_hold，必须只针对明确强势持仓触发，例如同时满足 relative strength strong、rebound participation strong、fundamental 未恶化、无明确负面 news。对普通 sell 不应增加额外阻力。

#### 16.2.3 F9C 交易数极低，但收益不够强

F9C 的收益为 +3.03%，低于 FUND1、F5_COOLDOWN_5D 和 F8C；最大回撤为 -12.20%，也没有体现出明显风控优势。但它把交易数压到 50，说明 narrow quality-trap add check 对交易行为影响很强。

这个结果说明 F9C 的触发虽然比 F8D 窄，但仍然可能过度压制加仓和组合调整。它适合作为分析 quality-trap 行为的诊断实验，不适合作为当前主线策略。

后续不建议继续扩大 quality-trap cap 的权限。若保留该方向，应只输出 soft warning 或 very small add-size haircut，不应 block add。

### 16.3 F9 对后续 F10 的启发

F9 的整体结论是：

```text
低权限 buy/add sizing 有一定价值；
sell confirmation 不能泛化；
quality-trap add check 容易压制收益；
下一阶段应继续围绕 F5_COOLDOWN_5D 做低权限模块验证，而不是以 F9B/F9C 为主线。
```

对最终版 F10 的启发是：

```text
1. rebound 方向不能直接沿用 F8C，需要先离线诊断 tag 是否真的能识别 BA/HON/IBM/MSFT/GS 等 winner。
2. F9A 的 buy/add reduce-only 思路可以复用，但权限必须更窄，只做轻微 sizing haircut。
3. winner_hold 只能做 soft positive tag，不能复用 F9B 式 generic sell second confirmation。
4. quality-trap / defensive lagging 方向只能降低新增或加仓优先级，不能 hard block。
5. risk budget 只能在极端风险时压仓，不能重新引入 regime factor weights。
```

暂不建议：

```text
generic sell second confirmation
hard quality-trap add block
strong thesis-memory sell gating
any module that broadly reduces all sell/add actions
```

F9 的研究价值主要在于排除了两个看似合理但实证不佳的方向：generic sell confirmation 和 quality-trap hard add check。真正可复用的是 F9A 的低权限 buy/add sizing 思路。

## 17. 最终版 F10 七组实验计划

F10 不再继续扩展 generic reflection、hard quant veto、复杂 thesis memory 或 full soft optimizer，而是围绕当前最强基线做去重后的七组低权限实验。

原本 F10 三组和新七组存在明显重叠，不能简单相加成十组。最终版 F10 统一整理为七组。F10A 诊断完成后，rebound 方向的定位需要降权：修正后的 tag 能识别真实 winner，但暂未证明它是稳定正 alpha，因此后续 rebound 模块只能先作为 context / exposure diagnostic，不能直接升级为 sizing boost 或强持有约束。

当前代码结构说明：

```text
run_backtest.py 目前直接支持 cooldown_days、reflection_agent、fundamental_features、data_mode 等运行时开关；
reflection_agent 是已有 pre-decision advisory layer，但 F10 不建议继续走 generic reflection；
rebound_candidate、winner_hold、defensive_lagging、nt_band_lite、extreme_risk_budget 目前不是稳定的一等配置项；
这些模块应通过独立实验分支中的特征构造、prompt context、order overlay 或风险参数实现，并在 attribution 脚本中补充计数。
```

核心原则：

```text
统一命名为 F10，不再新增 F11；
所有完整 LLM backtest 一律从 F10_BASE = F6 / F5_COOLDOWN_5D 口径出发；
F10_BASE = FUND1 cleaned fundamental + anti-overtrade memory + 5d cooldown；
F10A 是门控诊断，用来区分“tag 能否识别 winner”和“tag 是否有未来收益预测力”；
F10C 是结果归因 audit，用来解释 F6/F10B/F10E/F10F/F10G 的 winner exposure 路径；
rebound tag 只能先作为 context，不直接做正向 sizing boost；
只借用 F9A 的低权限 buy/add sizing 思路，但不再把它绑定到 rebound tag；
soft execution 四组只保留 very-lite no-trade band 候选，不重复 reduce-only、priority-turnover 或 full optimizer；
所有新增模块必须可归因、可计数、可单独 ablation。
```

重叠关系整理：

| 原本 F10 三组 | 和最终七组的关系 | 处理 |
| --- | --- | --- |
| F10A = cooldown + rebound_catchup_tag | 与最终 F10A/F10B 重叠 | 保留方向，但拆成“先诊断 rebound 是否识别 winner”，再跑主实验 |
| F10B = F10A + buy/add sizing | 与旧 F10C 重叠 | 暂不保留 rebound sizing；改成 F10C exposure audit，避免把未证实 alpha 接入执行层 |
| F10C = F10A + winner_hold soft tag | 与最终 F10D 重叠 | 保留 winner_hold 方向，但改成 confirmed winner hold，rebound 只做辅助证据 |

### 17.1 F10 的 base 选择

F10 的统一底座为：

```text
F10_BASE = F6 = F5_COOLDOWN_5D
         = FUND1 cleaned fundamental
         + anti-overtrade memory
         + 5d cooldown
```

执行规则：

```text
F10B/F10D/F10E/F10F/F10G 都必须是 F6 + 单一低权限模块；
F10A 不跑 LLM backtest，但诊断使用同一股票池、同一区间和同一价格数据口径；
F10C 不跑 LLM backtest，只审计 F6 与 F10 各单模块结果；
不得以 F8C、F9A、F10 soft execution full 作为新的 base；
任何 F10 组合版必须等单模块结果完成后另行命名，不纳入当前七组。
```

选择该底座的原因：

| 版本 | Total Return | Max Drawdown | Sharpe | Sortino | 结论 |
| --- | ---: | ---: | ---: | ---: | --- |
| FUND1 | +3.35% | -11.61% | 0.471 | 0.038 | cleaned fundamental 有明确正贡献 |
| F5_COOLDOWN_5D | +3.99% | -9.16% | 0.557 | 0.043 | 当前最强低权限执行层版本 |
| F8C_REBOUND_CATCHUP_TAG_FULL | +3.83% | -10.42% | 0.509 | 0.041 | rebound tag 有继续组合价值 |
| F9A_BUY_ADD_ONLY_REDUCE_REVIEW_FULL | +3.36% | -9.73% | 0.500 | 0.039 | buy/add sizing 可作为轻量辅助 |

因此，F10 的问题不是“重新寻找 base”，而是验证：

```text
在 F5_COOLDOWN_5D 已经降低低质量反向交易后，
rebound/relative strength context、confirmed winner-hold soft tag、defensive lagging、very-lite no-trade band、
extreme risk budget 是否还能继续提升 winner exposure、降低无效交易或改善回撤。
```

### 17.2 F10 实验矩阵

最终版 F10 保留七组，按单模块或诊断逐一验证，不做 full low-permission 大组合。

| 编号 | 实验名 | Base / 对照 | 改哪一层 | 做什么 | 权限边界 | 目的 |
| --- | --- | --- | --- | --- | --- | --- |
| F10A | REBOUND_DIAGNOSTIC_TAG | F6 数据口径；不跑 LLM | 特征层 / 选股层 | 修正 rebound 定义，离线检查 BA、HON、IBM、MSFT、GS 这类真实 winner 是否能被标出来，并比较 tagged / untagged future return | 只诊断，不改 prompt，不改订单 | 解决 F8C tag 没触发、归因不成立的问题，同时判断 tag 是否只是解释性 context |
| F10B | REBOUND_CONTEXT_MAIN | F6 + context-only tag | 特征层 / 买入候选排序层 | 把修正后的 rebound / relative strength tag 放进 LLM prompt，只给信息，不加执行约束 | 不做 sizing boost，不 hard veto，不要求买入 rebound 股票 | 验证 rebound context 是否帮助 LLM 少错过 BA/MSFT/IBM/GS/HON；不能把收益改善强归因于 rebound alpha |
| F10C | REBOUND_TARGET_EXPOSURE_AUDIT | 审计 F6/F10B/F10E/F10F/F10G | 归因/诊断层 | 对 BA、HON、IBM、MSFT、GS 每日 exposure、tagged-but-missed 日期、sell 后 5d/10d 表现做审计 | 不跑 LLM，不改策略，不生成新收益曲线 | 区分“没看到 winner”“看到但没买”“买了但太早卖”，暂不做 sizing 实验 |
| F10D | CONFIRMED_WINNER_HOLD_SOFT | F6 + confirmed winner hold | 持仓管理层 | 只对已持仓且实际表现强、基本面未恶化、无明确负面 news 的 confirmed winner 给 soft hold tag；rebound 只做辅助证据 | 只影响低置信 sell；允许 thesis invalidated / risk-reducing sell | 测试能否减少卖飞 BA/MSFT/IBM 这类 winner，避免 F9B 式泛化 sell confirmation |
| F10E | DEFENSIVE_LAGGING_NO_ADD | F6 + defensive lagging tag | 选股层 / 仓位管理层 | 对反弹期明显落后的防御股加 soft negative tag，只降低新增/加仓优先级 | 只处理 buy/add；不强制卖出；高置信例外允许通过 | 减少资金卡在低弹性标的里 |
| F10F | NT_BAND_LITE_ON_F6 | F6 + very-lite no-trade band | 执行层 | 只保留很轻的 no-trade band，过滤极小额噪声交易，不做 full optimizer | 只 skip/partial 极小交易；不启用 reduce-only、priority-turnover、full optimizer | 复用 F10 soft execution 里唯一相对有价值的部分 |
| F10G | EXTREME_RISK_BUDGET | F6 + extreme-only risk budget | 风险预算层 | 只在极端组合风险、连续亏损或高集中度时轻微压仓，不做 regime factor 权重 | normal/recovery 基本放行；risk 只控仓位，不改 alpha ranking | 看能否改善 MDD，同时不伤 5-6 月反弹 |

F10A 是门控诊断，不应和 F10B-G 同等解释为收益实验。F10A 当前结果显示：修正后的 rebound tag 能识别 BA、HON、IBM、MSFT、GS，但 tagged 样本未来 5d/10d 平均收益暂时低于 untagged 样本。因此，rebound 方向可以继续作为 context / exposure audit，但不应直接作为买入加权、sizing boost 或强 hold 依据。

### 17.2.1 F10 单组实验内容

#### F10A_REBOUND_DIAGNOSTIC_TAG

```text
类型：离线诊断，不跑 LLM
对照：F8C old rebound tag vs revised rebound tag
输入：F6 同股票池、同价格数据、2025-03-03 至 2025-06-30
输出：
  old/revised tag count
  BA/HON/IBM/MSFT/GS tag days
  tagged vs untagged future_return_5d/10d
  missed winner days
结论用途：
  决定 rebound 是否能进入 F10B prompt
  决定 rebound 是否能作为 execution/sizing 依据
```

#### F10B_REBOUND_CONTEXT_MAIN

```text
类型：完整 LLM backtest
base：F6
唯一新增：
  revised_rebound_tag
  relative_strength_tag
  prompt 中的 context-only explanation
禁止：
  不改变 order size
  不新增 post-decision reviewer
  不对 tagged 股票强制买入、加仓或持有
必须统计：
  target winner avg exposure
  tagged target bought count
  tagged target missed count
  BA/HON/IBM/MSFT/GS monthly exposure
  return/MDD/Sortino/trades vs F6
成功条件：
  target winner exposure 明显高于 F6，且收益或回撤不明显恶化。
```

#### F10C_REBOUND_TARGET_EXPOSURE_AUDIT

```text
类型：归因诊断，不跑 LLM
审计对象：
  F6
  F10B
  F10E
  F10F
  F10G
核心问题：
  tagged winner 当天是否进入候选/持仓
  LLM 是否看到了 tag 但没有买
  买入后是否太早卖出
  sell 后 5d/10d 是否继续上涨
  cash 是否闲置但 target winner 被 tagged
输出：
  target exposure by day
  tagged-but-missed table
  sell-too-early table
  target contribution attribution
结论用途：
  若主要问题是没买，后续才讨论低质量 buy/add haircut；
  若主要问题是太早卖，才运行 F10D。
```

#### F10D_CONFIRMED_WINNER_HOLD_SOFT

```text
类型：完整 LLM backtest，但必须等 F10C 后运行
base：F6
唯一新增：
  confirmed_winner_hold_soft_tag
触发条件：
  existing position
  positive unrealized PnL 或 20d/60d relative strength strong
  fundamental_signal not negative
  no clear negative news
  position not over risk cap
  rebound tag 只能作为辅助证据
允许：
  low-confidence full sell -> partial sell / hold caution
  low-confidence partial sell -> smaller trim / hold caution
  thesis invalidated -> allow sell
  risk-reducing sell -> allow sell
禁止：
  不做 generic sell second confirmation
  不保护亏损弱势股
  不永久禁止卖出
必须统计：
  protected sell count
  protected sell future_return_5d/10d
  false-protected loser count
  target winner holding days vs F6
```

#### F10E_DEFENSIVE_LAGGING_NO_ADD

```text
类型：完整 LLM backtest
base：F6
唯一新增：
  defensive_lagging_signal
  buy/add soft negative priority
触发倾向：
  market 20d proxy positive
  symbol 20d return rank low
  symbol 20d return <= 0 或明显弱于 universe
权限：
  new buy can be skipped when confidence is not high
  existing add can be reduced
  sell is untouched
  high-confidence exception allowed
必须统计：
  defensive_lagging_count
  skipped_new_buy_count
  reduced_add_count
  affected order future_return_5d/10d
  defensive exposure vs F6
```

#### F10F_NT_BAND_LITE_ON_F6

```text
类型：完整 LLM backtest
base：F6
唯一新增：
  very-lite no-trade band
权限：
  skip extremely small notional trades
  partial very small-to-medium rebalances
禁止：
  no reduce-only optimizer
  no priority-turnover optimizer
  no full soft execution optimizer
必须统计：
  nt_skip_count
  nt_partial_count
  output_orders
  final trades
  trades_notional
  return/MDD/Sortino vs F6
成功条件：
  降低噪声交易或 notional，同时不弱于 F6 太多。
```

#### F10G_EXTREME_RISK_BUDGET

```text
类型：完整 LLM backtest
base：F6
唯一新增：
  extreme-only risk budget
触发条件：
  portfolio drawdown / consecutive loss / concentration risk 达到 extreme threshold
权限：
  extreme risk-off mild gross exposure cap
  extreme risk-off mild single-name cap
  normal/recovery 不改变 alpha ranking
禁止：
  不做 regime factor weights
  不用 volatility 惩罚 alpha
  不阻止 confirmed winner / rebound candidate 的合理资金部署
必须统计：
  risk_budget_intervention_count
  days_in_extreme_state
  exposure cap vs actual exposure
  MDD improvement
  May-June rebound participation
```

### 17.2.2 F10A 离线诊断结果

F10A 已完成离线诊断，时间区间为 `2025-03-03` 至 `2025-06-30`，股票池为 20-stock universe，target winner 为 `BA/HON/IBM/MSFT/GS`。

总体结果：

| 指标 | 结果 |
| --- | ---: |
| Diagnostic rows | 1440 |
| Universe symbols | 20 |
| Old F8C tag count | 79 |
| Revised tag count | 304 |

目标 winner 命中：

| Symbol | Old tag days | Revised tag days | Period return |
| --- | ---: | ---: | ---: |
| BA | 1 | 15 | +29.68% |
| HON | 0 | 11 | +11.03% |
| IBM | 0 | 9 | +19.37% |
| MSFT | 5 | 10 | +29.70% |
| GS | 15 | 28 | +28.27% |

Tagged / untagged future return 对比：

| Tag version | Tagged 5d mean | Untagged 5d mean | Tagged 10d mean | Untagged 10d mean |
| --- | ---: | ---: | ---: | ---: |
| old_f8c_rebound_tag | +0.70% | +0.47% | +1.07% | +0.85% |
| revised_rebound_tag | +0.37% | +0.51% | +0.58% | +0.93% |

阶段性解释：

```text
1. revised_rebound_tag 解决了 F8C 的“tag 可能不触发 / 识别不到真实 winner”问题。
2. revised_rebound_tag 尚未证明是稳定正 alpha；全样本 tagged future return 低于 untagged。
3. rebound tag 可以继续进入 F10B prompt 作为 context，但不能作为 F10C 式执行层正向加权依据。
4. winner_hold 不能只依赖 rebound tag，必须改成 confirmed winner hold。
```

### 17.3 分层优化设计

#### 17.3.1 数据/特征层

目标：保留 FUND1 的 cleaned fundamental 价值，同时加入少量低噪音 soft tags。

建议新增或强化：

```text
rebound_participation_tag
relative_strength_tag
winner_hold_tag
defensive_lagging_tag
```

定义：

| Tag | 含义 | 用途 | 权限 |
| --- | --- | --- | --- |
| rebound_participation_tag | 股票是否参与市场反弹，是否跑赢 SPY / 20-stock universe | 帮助识别反弹 winner | soft positive tag |
| relative_strength_tag | 20d/60d 相对强弱排名 | 买入排序和持仓保护 | soft ranking hint |
| winner_hold_tag | 已持仓且趋势/基本面未破坏的强势股 | 防止低置信卖飞 | sell caution only |
| defensive_lagging_tag | 低波动但明显跑输反弹行情的防御股 | 降低新增买入优先级 | soft negative tag |

F10A 的 rebound diagnostic 已离线输出：

```text
rebound_candidate_count
rebound_candidate_symbols_by_day
BA/HON/IBM/MSFT/GS tag days
tagged vs untagged future_return_5d/10d
missed_winner_days
```

禁止事项：

```text
不生成 overall quant score；
不把 volatility/drawdown 混入 alpha priority；
不做 hard veto；
不把 tag 写成长篇自然语言解释。
```

#### 17.3.2 选股层

目标：不硬排除股票，而是给 decision agent 更清晰的候选分层。

建议输出：

```text
candidate_tier:
  core_candidate
  watch_candidate
  hold_only
  reduce_only
```

规则倾向：

```text
core_candidate:
  fundamental positive
  relative_strength strong
  rebound_participation strong

watch_candidate:
  signal mixed
  only small initial buy allowed

hold_only:
  existing position acceptable
  no strong add evidence

reduce_only:
  clear deterioration
  risk budget breach
```

该层只影响提示和排序，不直接下单。

#### 17.3.3 买入候选排序层

目标：解决 FUND1/F5 仍可能把新增资金分配给低弹性防御股的问题。

建议构造低权限 `buy_priority_hint`：

```text
positive:
  cleaned fundamental strength
  rebound participation
  relative strength
  high-quality positive event

negative:
  defensive_lagging
  repeated low-conviction add
  position already near cap
```

执行方式：

```text
只影响 LLM prompt 中的候选排序；
或只影响 post-decision add size；
不允许直接把 buy 改成 reject；
不允许替代 decision_agent 的原始判断。
```

Sizing 暂缓与后续恢复条件：

```text
原 F10C_REBOUND_BUY_ADD_SIZING 暂缓；
不基于 revised_rebound_tag 做正向加权或 sizing boost；
如后续恢复 sizing，只能改成 LOW_QUALITY_BUY_ADD_HAIRCUT：
  只处理 buy/add；
  只允许 reduce_size，不允许 reject；
  默认 haircut 20%-30%，极端低质量最多 50%；
  不审 sell；
  不对所有高波动股票降 size，rebound evidence 只能作为不惩罚的辅助理由。
```

当前 F10C 改为 `REBOUND_TARGET_EXPOSURE_AUDIT`，不发起 LLM backtest，不改订单。

#### 17.3.4 决策架构层

目标：不回到 generic reflection，而是把审查放到具体订单之后。

推荐架构：

```text
features
-> decision_agent generates initial decisions
-> low-permission order overlays
-> execution
-> attribution
```

不推荐：

```text
features -> generic reflection_agent -> decision_agent
```

原因：

```text
generic reflection 权限过大；
输出难归因；
容易让模型整体保守；
和 decision_agent 职责重叠；
M1/reflection 结果已经显示收益没有改善。
```

F10 中如果需要 reviewer，应只审具体动作：

```text
buy/add reviewer: reduce size only
sell reviewer: only caution for confirmed winner_hold
risk reviewer: cap size only
```

#### 17.3.5 执行层

目标：保留 F5_COOLDOWN_5D 的成功机制。

必须保留：

```text
5d reversal cooldown
anti-overtrade memory
allow risk-reducing sell exception
allow high-confidence thesis invalidation exception
```

不建议：

```text
10d cooldown
weekly/monthly long-horizon rebalance
generic delay
hard reject except position/data/cooldown violation
```

F10 的执行层重点不是继续降交易数，而是减少低质量反向交易，同时保留反弹行情里的快速纠错能力。

F10F 只允许 very-lite no-trade band：

```text
过滤极小额噪声交易；
允许小到中等偏离做 partial rebalance；
不启用 reduce-only sizing；
不启用 priority-turnover；
不启用 full soft optimizer。
```

依据 `F10_soft_execution_experiment_plan.md` 的已完成结果，`F10_EXEC_NT_BAND_ONLY` 是 soft execution 四组里唯一相对有记录价值的版本，但仍弱于 F6；因此 F10F 只能作为轻量候选，不应升级为主线执行框架。

#### 17.3.6 持仓管理层

目标：减少卖飞 winner，但不重复 F9B 的失败。

建议只做 `confirmed_winner_hold_soft_tag`：

触发条件必须较窄：

```text
current position exists
positive unrealized PnL or relative_strength_tag = strong
fundamental_signal not deteriorated
no clear negative news
position not over risk cap
rebound_participation_tag can support but cannot trigger alone
```

允许动作：

```text
low-confidence full sell -> reduce to partial sell
low-confidence partial sell -> hold or smaller trim
high-confidence thesis invalidation -> allow sell
risk-reducing sell -> allow sell
```

禁止动作：

```text
不对所有 sell 做二次确认；
不因为 winner_hold_tag 永久禁止卖出；
不阻止明确风险释放。
```

#### 17.3.7 风险预算层

目标：风险只控制仓位，不接管选股。

建议：

```text
normal regime:
  max single position 10%-12%

confirmed winner:
  max single position 12%-14%

extreme risk-off:
  max single position 6%-8%
  restrict new high-risk adds
```

不建议：

```text
regime factor weights
market regime changes alpha ranking
volatility directly penalizes alpha
```

F4/F5_REGIME_FACTOR_WEIGHTS 的失败说明，regime 作为因子权重层容易错过反弹。F10 中 regime 只能做 risk budget。

F10G 的 extreme risk budget 触发必须很窄：

```text
portfolio drawdown or consecutive loss exceeds threshold;
single-name concentration exceeds cap;
cash deployment remains allowed for confirmed rebound/winner candidates;
only mild size cap or add restriction, not broad risk-off de-risking.
```

#### 17.3.8 归因/评估层

F10 必须在报告中回答模块是否真的有贡献，不能只看最终收益。

必须汇总：

```text
module_intervention_count
rebound_tag exposure contribution
winner_hold sell reductions
buy/add sizing reductions
blocked/reduced order future return 5d/10d
allowed order future return 5d/10d
market top5 exposure
missed winner analysis
MSFT/BA/IBM/HON/GS avg exposure
trade_count
trades_notional
cash ratio
monthly return
April drawdown
May-June rebound participation
```

成功标准不应只看 Total Return：

```text
Total Return >= F5_COOLDOWN_5D 或接近 F5 且 MDD 更优；
Sortino >= F5_COOLDOWN_5D 或明显优于 FUND1；
Top5 winner exposure 高于 F5；
reduced buy/add future return 低于 allowed buy/add；
winner_hold 保护的 sell 后续确实上涨；
交易数不因模块叠加被压到极低。
```

### 17.4 推荐运行顺序

建议按以下顺序运行：

```text
1. F10A_REBOUND_DIAGNOSTIC_TAG
2. F10E_DEFENSIVE_LAGGING_NO_ADD
3. F10F_NT_BAND_LITE_ON_F6
4. F10G_EXTREME_RISK_BUDGET
5. F10B_REBOUND_CONTEXT_MAIN
6. F10C_REBOUND_TARGET_EXPOSURE_AUDIT
7. F10D_CONFIRMED_WINNER_HOLD_SOFT
```

运行策略：

```text
F10A 已完成离线诊断，不需要完整 LLM backtest；
第一批完整 backtest 先跑 F10E/F10F/F10G，因为它们与 rebound alpha 弱相关；
F10B 可以后续运行，但只做 context，不加执行约束；
F10C 是 exposure audit，依赖 F6/F10B/F10E/F10F/F10G 的结果，不单独跑 LLM；
F10D 必须等 F10C 确认“卖飞 winner”确实存在后再跑；
暂不设计 F10H/F11 full combo，避免把多个弱正贡献模块叠加成过度约束。
```

如果 API 成本允许，最终候选应补充稳健性区间：

```text
main:
  2025-03-03 to 2025-06-30

extended:
  2025-03-03 to 2025-12-31

subperiod:
  2025-03-03 to 2025-04-30
  2025-05-01 to 2025-06-30
```

### 17.5 F10 预期结论模板

F10 最终报告应明确回答：

```text
F10A 是否证明 rebound tag 能识别真实 winner，以及是否具备 future-return alpha；
F10B 是否在不加执行约束的情况下提高 target winner exposure；
F10C 是否证明问题来自没看到 winner、看到但没买、买了但太早卖；
F10D 的 confirmed_winner_hold_soft_tag 是否减少卖飞，而不是重复 F9B 的该卖不卖；
F10E 是否减少低弹性 defensive lagging exposure，且不误伤反弹参与；
F10F 的 very-lite no-trade band 是否能过滤噪声交易，且不重复 full optimizer 的过度干预；
F10G 是否改善 MDD，同时不伤 5-6 月 rebound participation；
最终 F10 是否优于 F5_COOLDOWN_5D / F6 口径，而不只是优于 FUND1 或 B0。
```

阶段性判断标准：

```text
若 F10A 能识别 BA/HON/IBM/MSFT/GS 但 tagged future return 不优：
  rebound 只能作为 context / audit，不能作为 sizing boost。

若 F10B 提高 target winner exposure：
  rebound context 可继续保留，但仍需通过 F10C 确认是否改善交易路径。

若 F10C 发现主要问题是 tagged winner 未买入：
  后续再考虑 LOW_QUALITY_BUY_ADD_HAIRCUT，而不是 rebound buy/add boost。

若 F10C 发现主要问题是买入后太早卖：
  再运行 F10D_CONFIRMED_WINNER_HOLD_SOFT。

若 F10D 明显弱于 F10B 或 F6：
  winner_hold 仍需更窄触发，不能做 sell gate。

若 F10E/F10F/F10G 弱于 F6：
  只保留为诊断，不进入最终主线。
```
### 17.6 F10 已完成实验结果与分析

本节记录最终版 F10 的已完成结果。所有收益型 backtest 统一使用以下口径：

```text
period = 2025-03-03 to 2025-06-30
benchmark = 20-stock equal-weight Buy & Hold
BH20 return = +0.7348%
BH20 max drawdown = -14.9520%
base = F6 = F5_COOLDOWN_5D
     = FUND1 cleaned fundamental
     + anti-overtrade memory
     + 5D cooldown
```

#### 17.6.1 F10 汇总结果

| Run | Strategy Return | BH20 Return | Excess vs BH20 | Strategy MDD | BH20 MDD | Sharpe | IR vs SPY | Trades | 判断 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| F6 baseline | +3.99% | +0.73% | +3.26% | -9.16% | -14.95% | 0.557 | -0.332 | 261 | 当前最强基线 |
| F10B_REBOUND_CONTEXT_MAIN_V2 | +2.07% | +0.73% | +1.33% | -12.98% | -14.95% | 0.361 | -0.423 | 122 | 信息有效但不够强 |
| F10D_CONFIRMED_WINNER_HOLD_SOFT_V2 | +1.00% | +0.73% | +0.27% | -13.32% | -14.95% | 0.245 | -0.414 | 162 | 不建议保留为主线 |
| F10E_DEFENSIVE_LAGGING_NO_ADD_V2 | +3.68% | +0.73% | +2.94% | -11.11% | -14.95% | 0.496 | -0.371 | 268 | 最接近 F6，但仍弱于 F6 |
| F10F_NT_BAND_LITE_ON_F6 old | +4.17% | +0.73% | +3.41% | -11.19% | -14.95% | 0.578 | -0.315 | 251 | 收益略高但回撤恶化 |
| F10F_PLUS_SMART_NT_BAND | +0.59% | +0.73% | -0.15% | -13.60% | -14.95% | 0.211 | -0.477 | 62 | 失败，过度过滤交易 |
| F10G_EXTREME_RISK_BUDGET old | +0.96% | +0.73% | +0.22% | -10.84% | -14.95% | 0.236 | -0.526 | 164 | 风险预算压制收益 |

结论：

```text
F10 没有产生稳定超过 F6 的新主线。
F6 仍然是最终主基线。
F10E 是最接近 F6 的候选，但还没有超过 F6。
F10F old 收益略高于 F6，但最大回撤明显更差，不能视为全面胜出。
F10Fplus、F10D、F10G 不建议进入最终策略。
F10B 只能保留为 context / attribution 方向，不能升级为执行层约束。
```

#### 17.6.2 F10A 诊断结论

F10A 是离线诊断，不是收益实验。它的核心任务是确认 revised rebound tag 是否真的能识别真实 winner，以及这个 tag 是否具备 future-return alpha。

| 指标 | 结果 |
| --- | ---: |
| Diagnostic rows | 1440 |
| Universe symbols | 20 |
| Old F8C tag count | 79 |
| Revised tag count | 304 |

目标 winner 命中：

| Symbol | Old tag days | Revised tag days | Period return |
| --- | ---: | ---: | ---: |
| BA | 1 | 15 | +29.68% |
| HON | 0 | 11 | +11.03% |
| IBM | 0 | 9 | +19.37% |
| MSFT | 5 | 10 | +29.70% |
| GS | 15 | 28 | +28.27% |

Tagged / untagged future return：

| Tag version | Tagged 5d mean | Untagged 5d mean | Tagged 10d mean | Untagged 10d mean |
| --- | ---: | ---: | ---: | ---: |
| old_f8c_rebound_tag | +0.70% | +0.47% | +1.07% | +0.85% |
| revised_rebound_tag | +0.37% | +0.51% | +0.58% | +0.93% |

解释：

```text
revised tag 解决了旧 F8C tag 识别不到 BA/HON/IBM/MSFT/GS 的问题；
但 revised tagged 样本的未来 5d/10d 平均收益低于 untagged；
因此 rebound tag 有解释价值，但不是稳定 alpha；
后续只能作为 prompt context 或 exposure audit，不能作为 sizing boost 或强持有约束。
```

#### 17.6.3 F10B_v2：rebound context

F10B_v2 将 revised rebound / relative strength tag 放进 LLM prompt，只给信息，不加执行约束。

机制触发：

```text
REBOUND_TAG lines = 85
nonzero days = 79
sum rebound_candidate_count = 320
max daily rebound_candidate_count = 11
```

结果：

```text
return = +2.07%
excess vs BH20 = +1.33%
MDD = -12.98%
Sharpe = 0.361
trades = 122
```

分析：

```text
F10B_v2 这次代码接入是有效的，tag 确实进入了运行链路；
但收益、MDD、Sharpe 都弱于 F6；
核心原因是 F10A 已经证明 rebound tag 不是稳定 future-return alpha；
LLM 看到更多 rebound context 后变得更谨慎，交易数下降，但没有换来更好的风险收益。
```

结论：F10B 可保留为 context / audit 方向，但不能进入最终主线。

#### 17.6.4 F10C：target exposure audit

F10C 是归因审计，不跑独立 LLM 收益曲线。它用于解释 F6/F10B/F10E/F10F/F10G 对 BA/HON/IBM/MSFT/GS 的 exposure。

既有 audit 结果：

| Run | Avg target exposure | Target days | Missed target days | Target sells |
| --- | ---: | ---: | ---: | ---: |
| F10B old | 5.27% | 349 | 15 | 26 |
| F10E old | 4.78% | 351 | 12 | 22 |
| F10F old | 4.66% | 319 | 17 | 12 |
| F10G old | 2.11% | 172 | 55 | 2 |
| F6 | 3.85% | 223 | 34 | 12 |

分析：

```text
F6 已经不是完全看不到 winner；
F10B/F10E/F10F old 在 target exposure 上有局部改善；
F10G 明显压低 target exposure，解释了收益被风险预算压制；
后续若继续做 F10C，应基于 V2 结果重新跑一次 exposure audit。
```

#### 17.6.5 F10D_v2：confirmed winner hold

F10D_v2 对强势持仓加 confirmed winner hold soft tag，目标是减少卖飞 winner，但不做 F9B 式 generic sell confirmation。

机制触发：

```text
hold_tag_lines = 83
nonzero days = 82
sum confirmed_winner_hold_count = 771
max daily confirmed_winner_hold_count = 14
protected_sell_events_sum = 1
```

结果：

```text
return = +1.00%
excess vs BH20 = +0.27%
MDD = -13.32%
Sharpe = 0.245
trades = 162
```

分析：

```text
tag 很活跃，但真正保护 sell 只有 1 次；
说明该模块在订单层影响很小；
如果提高保护强度，又会接近 F9B 的失败模式，即该卖不卖；
因此 winner_hold 方向在当前触发条件下没有形成有效收益贡献。
```

结论：F10D_v2 不建议保留为主线。

#### 17.6.6 F10E_v2：defensive lagging no-add

F10E_v2 对反弹期明显落后的防御股加 soft negative tag，只降低新增和加仓优先级。

机制触发：

```text
defensive_tag_lines = 83
nonzero days = 30
sum defensive_lagging_count = 136
max daily defensive_lagging_count = 7
skipped_new_buy_sum = 0
reduced_add_sum = 0
```

结果：

```text
return = +3.68%
excess vs BH20 = +2.94%
MDD = -11.11%
Sharpe = 0.496
trades = 268
```

分析：

```text
F10E_v2 是本轮最接近 F6 的实验；
tag 已经触发，说明前一版“完全不触发”的接入问题已经修正；
但 skipped_new_buy 和 reduced_add 都为 0，说明执行层没有真正改变订单；
因此 F10E_v2 的结果不能证明 no-add overlay 已经有效，只能说明 defensive lagging 识别方向有一定研究价值。
```

结论：F10E 是唯一值得继续修正的候选。下一版应从 soft tag 改为更明确的 low-elasticity add haircut，但仍只处理 buy/add，不碰 sell。

#### 17.6.7 F10F old 与 F10Fplus：no-trade band

F10F old 是 very-lite no-trade band，F10Fplus 是更智能但更强的 smart no-trade band。

F10F old：

```text
return = +4.17%
excess vs BH20 = +3.41%
MDD = -11.19%
Sharpe = 0.578
trades = 251
```

F10Fplus 机制触发：

```text
NT_BAND_PLUS lines = 13
reviewed = 65
output = 63
skip = 2
partial = 9
approved = 54
override = 24
```

F10Fplus 结果：

```text
return = +0.59%
excess vs BH20 = -0.15%
MDD = -13.60%
Sharpe = 0.211
trades = 62
```

分析：

```text
F10F old 的收益略高于 F6，但 MDD 从 -9.16% 恶化到 -11.19%；
因此 F10F old 不是全面优于 F6，只是收益小幅提高、风险同步变差；
F10Fplus 将 trades 压到 62，但收益也被压没；
说明 smart no-trade band 过度过滤了有效纠错和反弹参与。
```

结论：F10F old 可作为轻量候选记录，但不能替代 F6；F10Fplus 判定失败。

#### 17.6.8 F10G old：extreme risk budget

F10G old 只在极端组合风险、连续亏损或高集中度时轻微压仓，目标是改善 MDD，同时不伤 5-6 月反弹。

结果：

```text
return = +0.96%
excess vs BH20 = +0.22%
MDD = -10.84%
Sharpe = 0.236
trades = 164
```

分析：

```text
F10G 有一定风险控制效果，MDD 好于多数 F10 变体；
但收益大幅低于 F6；
原因是 2025-05 至 2025-06 存在明显反弹，风险预算过早压仓会错过 rebound participation；
这与 F4/F5 regime factor weights 的失败逻辑一致：风险层一旦接管 alpha，容易压制反弹收益。
```

结论：F10G 不进入最终主线，只作为风险预算失败样本记录。

#### 17.6.9 F10 总结论

F10 的核心发现不是某个新模块战胜 F6，而是证明了 F6 已经是一个很强的低权限组合：

```text
F6 = cleaned fundamental signal
   + anti-overtrade memory
   + 5D cooldown
```

在 F6 上继续叠加模块，主要出现三类问题：

```text
1. 信息有解释价值，但预测力不足：
   F10A/F10B 的 rebound tag 可以识别 winner，但不是稳定 future-return alpha。

2. soft tag 太软，影响不了订单：
   F10E_v2 tag 已触发，但 skip/add reduce 都为 0。

3. 执行或风险约束太硬，会错过反弹：
   F10Fplus 和 F10G 都降低了交易或风险暴露，但收益被明显压制。
```

最终保留判断：

| 模块 | 是否进入最终主线 | 处理 |
| --- | --- | --- |
| F6 baseline | 是 | 继续作为主基线 |
| F10A diagnostic | 是，作为诊断 | 证明 rebound 可解释但不能直接加权 |
| F10B rebound context | 否 | 仅保留为 prompt context / attribution 备选 |
| F10C exposure audit | 是，作为分析工具 | 后续用 V2 结果补跑 audit |
| F10D winner hold | 否 | 不保留 |
| F10E defensive lagging | 候选 | 下一轮改为更明确的 buy/add haircut |
| F10F old NT band | 候选但不替代 F6 | 记录收益略高、回撤更差 |
| F10Fplus smart band | 否 | 过度保守，失败 |
| F10G risk budget | 否 | 风控压制收益 |

最终结论：

```text
F10 没有产生超过 F6 的新主线。
F6 继续作为最终主基线。
下一轮若继续优化，应只围绕 F10E 的 low-elasticity buy/add haircut 做更窄权限实验；
不要继续叠加 rebound sizing、generic winner hold、smart no-trade optimizer 或 regime/risk budget。
```
