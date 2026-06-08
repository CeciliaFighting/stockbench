# Inspirations

## F2 的定位

F2 属于 **post-decision execution layer**：LLM 先给出交易建议，F2 再决定订单是否执行、执行多少。

它主要是执行层，少量触及持仓管理层：

- 执行层：`max_trades_per_day`、`max_daily_turnover_pct_nav`、`min_trade_notional_pct_nav`
- 持仓管理层：`winner_holding_rule`、`weak_stock_no_add_rule`

## 最重要的建议

不要把 F2 继续做成更强的硬过滤器，而应改成 **soft execution optimizer**：

```text
少 reject
多 reduce_size
用 no-trade band
用 signal-to-cost threshold
按交易优先级分配 turnover budget
保护 high-conviction trade
```

核心原因：交易少不等于策略更好。F2/C1/A2 的共同问题是过滤了坏交易，也误伤了好交易。

## 可借鉴的量化做法

### 1. No-trade band

不要因为目标仓位轻微变化就交易。只有仓位偏离超过阈值时才调整。

启示：

```text
小偏离不交易
中等偏离 partial rebalance
大偏离才完整执行
```

### 2. Signal-to-cost threshold

交易不应只看数量上限，而应比较：

```text
expected edge > transaction cost + safety margin
```

高质量的第 9 笔交易可能应该执行；低质量的前 3 笔也可以跳过。

### 3. Soft constraints over hard reject

优先使用：

```text
reduce_size
partial execution
trade to boundary
```

尽量少用 hard reject。

### 4. Turnover budget allocation

如果当天有 turnover budget，应优先给更重要的交易：

1. risk-reducing sell
2. thesis-invalidated sell
3. high-conviction buy
4. winner add
5. normal rebalance
6. low-conviction trade

## F2_v2 草案

```yaml
soft_execution:
  enabled: true
  no_trade_band_pct_nav: 0.01
  daily_turnover_budget_pct_nav: 0.30

  low_priority_action: reduce_size

  hard_reject_only:
    - hard_cooldown_violation
    - position_limit_breach
    - data_quality_issue

  allow_budget_override_for:
    - thesis_invalidated_sell
    - risk_reducing_sell
    - high_conviction_buy
```

## 建议实验基线

建议所有 soft execution 实验都从 **F6** 继承，而不是从 F2 或 FUND1 继承。

原因：F6 是当前综合最优主线，已经包含有效模块：

```text
F6 = cleaned fundamental signal
   + anti-overtrade memory
   + 5-day cooldown
```

新的执行层实验应回答：

```text
在 F6 已经控制 overtrading 的基础上，soft execution 是否还能进一步改善交易质量？
```

## 两种实验方案：二选一

### 方案 A：最小版本

适合时间有限、只想快速验证方向。

```text
F10_EXEC_NT_BAND_ONLY
F10_EXEC_SOFT_OPTIMIZER_FULL
```

含义：

1. `F10_EXEC_NT_BAND_ONLY`：只验证 no-trade band 是否能过滤小额噪声交易。
2. `F10_EXEC_SOFT_OPTIMIZER_FULL`：直接集成 soft execution optimizer。

优点：实验少，推进快。  
缺点：组合版归因不够干净。

### 方案 B：完整做法

适合时间允许、希望明确归因。

```text
F10_EXEC_NT_BAND_ONLY
F10_EXEC_REDUCE_ONLY
F10_EXEC_PRIORITY_TURNOVER
F10_EXEC_SOFT_OPTIMIZER_FULL
```

含义：

1. `NT_BAND_ONLY`：小仓位偏离不交易，中等偏离 partial rebalance。
2. `REDUCE_ONLY`：低优先级交易不 reject，只 reduce_size。
3. `PRIORITY_TURNOVER`：有限 turnover budget 按交易优先级分配。
4. `SOFT_OPTIMIZER_FULL`：组合前三类机制。

优点：能看清楚哪个机制有效。  
缺点：实验数量更多。

### 推荐选择

如果时间紧，选 **方案 A**。  
如果要写更有说服力的实验报告，选 **方案 B**。

不要只跑组合版一次。否则结果好坏都难以解释。

## 关键判断标准

每组实验至少回答以下问题。

### 1. 是否真的改善策略表现？

对比 F6 和 Buy & Hold：

```text
Total Return
Sortino
Sharpe
Max Drawdown
Trades
Trades Notional
Average Cash Ratio
Return per Trade
```

不能只看交易数下降。交易少但收益下降，不算成功。

### 2. 被干预的交易未来表现是否更差？

必须分析：

```text
skipped_trade_future_return_5d/10d
reduced_trade_future_return_5d/10d
executed_trade_future_return_5d/10d
approved_trade_future_return_5d/10d
```

核心问题：

```text
被 skip/reduce 的交易，未来是否真的比 executed/approved 交易差？
```

如果是，说明 execution layer 有信息含量。  
如果不是，说明只是随机砍交易。

### 3. 是否误伤反弹参与？

重点看：

```text
April drawdown behavior
May-June rebound participation
monthly returns
winner exposure preservation
```

尤其要确认 soft execution 没有挡掉 5-6 月的强势反弹股。

### 4. 是否只是提高现金比例制造风控？

必须看：

```text
Average Cash Ratio
Gross Exposure
Trades Notional
```

如果 MDD 变好只是因为现金大幅增加，而收益被压低，不算结构性改进。

### 5. 干预次数是否足够解释结果？

必须记录：

```text
no_trade_band_skip_count
reduced_count
turnover_budget_limited_count
hard_reject_count
hard_reject_reason
```

如果模块几乎没有触发，结果不能归因于该模块。

## References

- AQR, *Portfolio Rebalancing: Common Misconceptions*  
  https://www.aqr.com/Insights/Research/White-Papers/Portfolio-Rebalancing-Common-Misconceptions

- AQR, *Transactions Costs: Practical Application*  
  https://www.aqr.com/Insights/Research/White-Papers/Transactions-Costs-Practical-Application

- NBIM, *No-Trade Band Rebalancing Rules: Expected Returns and Transaction Costs*  
  https://www.nbim.no/contentassets/8cb41f89dce345f5a6a295238f7872fb/no-trade-band-rebalancing-rules-expected-returns-and-transaction-costs.pdf

- MOSEK Portfolio Optimization Cookbook, *Transaction costs*  
  https://docs.mosek.com/portfolio-cookbook/transaction.html

- Gurobi Finance, *Limiting Turnover*  
  https://gurobi-finance.readthedocs.io/en/latest/modeling_notebooks/turnover.html
