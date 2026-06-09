# F10 Soft Execution Experiment Plan

## 1. 背景

当前 DeepSeek StockBench 主线里，F6 是阶段性最佳 baseline：

```text
F6 = F5_COOLDOWN_5D
   = cleaned fundamental signal
   + anti-overtrade memory
   + 5-day cooldown
```

F2 的结果说明，机械硬约束虽然能降低交易数，但也会误伤有效交易。F10 因此不继续加强 hard veto，而是在 F6 基础上测试更温和的 post-decision execution layer。

核心问题：

```text
在 F6 已经控制 overtrading 的前提下，soft execution 是否还能进一步提升交易质量？
```

## 2. 统一实验设置

所有 F10 实验统一使用以下设置，确保和 F6 可比：

```text
LLM model: deepseek-v4-flash
strategy: llm_decision
agent_mode: dual
reflection_agent: false
data_mode: offline_only
start: 2025-03-03
end: 2025-06-30
initial capital: 100,000 USD
stock pool: DJIA top 20
base risk control: cooldown_days = 5
base reference: F6 / F5_COOLDOWN_5D
```

标准运行命令模板：

```bash
python -m stockbench.apps.run_backtest \
  --cfg config.yaml \
  --start 2025-03-03 \
  --end 2025-06-30 \
  --strategy llm_decision \
  --run-id RUN_ID \
  --llm-profile deepseek-v4-flash \
  --use-deepseek \
  --agent-mode dual \
  --data-mode offline_only \
  --no-reflection-agent
```

## 3. 实验分组

### F10_EXEC_NT_BAND_ONLY

目的：验证 no-trade band 是否能过滤小额噪声交易。

机制：

```text
小额偏离：skip
中等偏离：partial rebalance
大额偏离：正常执行
```

预期作用：减少不必要的小额调仓，降低 turnover，同时尽量不影响高质量交易。

### F10_EXEC_REDUCE_ONLY

目的：验证 reduce-size 是否优于 hard reject。

机制：

```text
低信心 buy/add 不直接拒绝，而是降低执行规模
```

预期作用：保留 LLM 对方向的判断，同时降低低信心交易的仓位风险。

### F10_EXEC_PRIORITY_TURNOVER

目的：验证 turnover budget 是否应按交易优先级分配，而不是机械先到先得或简单 cap。

优先级：

```text
1. thesis-invalidated close / risk-reducing sell
2. other sell / decrease
3. high-conviction buy
4. add to existing position
5. normal buy
6. low-conviction rebalance
```

预期作用：当日交易预算有限时，保护更重要的交易，降低低优先级交易挤占预算的问题。

### F10_EXEC_SOFT_OPTIMIZER_FULL

目的：测试 soft execution 的组合效果。

组合机制：

```text
no-trade band
+ reduce-size
+ priority turnover allocation
```

预期作用：在不使用 hard veto 的情况下，综合降低噪声交易、控制 turnover，并保护高优先级机会。

## 4. Attribution 设计

四组实验避免一次性打包所有改动：

| Run ID | No-trade band | Reduce-size | Priority turnover | 用途 |
|---|---:|---:|---:|---|
| F10_EXEC_NT_BAND_ONLY | yes | no | no | 验证小额噪声过滤 |
| F10_EXEC_REDUCE_ONLY | no | yes | no | 验证 soft sizing |
| F10_EXEC_PRIORITY_TURNOVER | no | no | yes | 验证预算优先级分配 |
| F10_EXEC_SOFT_OPTIMIZER_FULL | yes | yes | yes | 验证组合效果 |

如果组合版提升，需要回看单项实验确认主要贡献来源。  
如果组合版下降，也需要判断是哪个子机制拖累。

## 5. 评估指标

### 5.1 策略表现

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

成功标准不是交易数下降，而是风险调整收益和交易质量改善。

### 5.2 干预质量

需要统计被干预交易的未来表现：

```text
skipped_trade_future_return_5d / 10d
reduced_trade_future_return_5d / 10d
approved_trade_future_return_5d / 10d
executed_trade_future_return_5d / 10d
```

核心判断：

```text
被 skip/reduce 的交易，未来表现是否显著差于 approved/executed 交易？
```

如果是，说明 execution layer 有信息含量。  
如果不是，说明模块可能只是随机砍交易。

### 5.3 反弹保护

重点检查：

```text
April drawdown behavior
May-June rebound participation
monthly returns
winner exposure preservation
```

尤其要避免 soft execution 挡掉 5-6 月的反弹参与。

### 5.4 现金比例与暴露

需要确认收益/回撤变化不是单纯由现金比例变化造成：

```text
Average Cash Ratio
Gross Exposure
Net Exposure
Trades Notional
```

如果 MDD 改善只是因为现金显著升高，同时收益被压低，则不算结构性改进。

### 5.5 干预次数

每组至少记录：

```text
no_trade_band_skip_count
no_trade_band_partial_count
reduce_size_count
turnover_budget_partial_count
turnover_budget_skip_count
approved_count
hard_reject_count
```

如果模块触发很少，结果不能强归因于该模块。

## 6. 实验运行与主结果

四组 F10 soft execution 实验已经完成。主报告只保留唯一有继续研究价值的版本：

```text
F10_EXEC_NT_BAND_ONLY
```

其余三组（`F10_EXEC_REDUCE_ONLY`、`F10_EXEC_PRIORITY_TURNOVER`、`F10_EXEC_SOFT_OPTIMIZER_FULL`）未纳入主结果表。原因是它们相对 F6 收益、回撤或交易行为明显变差，尤其 full 组合版出现过度干预。

### 6.1 保留版本

| Run ID | Branch | Worktree | Status | Report Dir |
|---|---|---|---|---|
| F10_EXEC_NT_BAND_ONLY | f10-exec-nt-band-only | `/home/terence/code/stockbench-f10-exec-nt-band-only` | completed | `/home/terence/code/stockbench-f10-exec-nt-band-only/storage/reports/backtest/F10_EXEC_NT_BAND_ONLY_20260609_040435_877553` |

日志路径：

```text
/home/terence/code/stockbench-f10-exec-nt-band-only/storage/logs/F10_EXEC_NT_BAND_ONLY.log
```

## 7. 实验结果

### 7.1 总体结果

| Run ID | Total Return | Sharpe | Sortino | Max Drawdown | Trades | Trades Notional | Avg Cash Ratio | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| F6 / F5_COOLDOWN_5D | +3.9913% | 0.556719 | 0.043074 | -9.1603% | 261 | 418155.76 | n/a | baseline |
| F10_EXEC_NT_BAND_ONLY | +2.9943% | 0.477596 | 0.041265 | -10.2283% | 436 | 1008753.60 | n/a | 四组 F10 中最好，但仍弱于 F6 |

### 7.2 干预统计

| Run ID | Reviewed Orders | Output Orders | NT skip | NT partial | Reduced | Turnover partial | Turnover skip | Approved | Hard reject |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| F10_EXEC_NT_BAND_ONLY | 595 | 437 | 158 | 216 | 0 | 0 | 0 | 437 | 0 |

补充说明：

- `NT skip` 对应交易价值低于 no-trade band 的订单，直接转为 hold。
- `NT partial` 对应小到中等偏离订单，执行 50% partial rebalance。
- 最终实际成交 trades 为 436，略低于 soft execution 输出订单数 437，说明有 1 笔订单在后续执行层未形成成交。

### 7.3 月度表现

| Run ID | Mar 2025 | Apr 2025 | May 2025 | Jun 2025 |
|---|---:|---:|---:|---:|
| F10_EXEC_NT_BAND_ONLY | -3.70% | -3.68% | +4.68% | +3.31% |

F10_EXEC_NT_BAND_ONLY 在 5-6 月仍参与了反弹，但 3-4 月的下行和整体回撤没有优于 F6。

### 7.4 结论

```text
Best F10 variant: F10_EXEC_NT_BAND_ONLY
Whether F10 beats F6: No
Primary useful mechanism: no-trade band / partial rebalance
Main failure mode: 降低小额噪声交易有一定效果，但没有改善 F6 的整体收益和回撤；交易金额反而高于 F6
Recommendation for next experiment: 不升级 F10 为主线；F6 仍保留为当前 baseline。如继续研究，只保留 no-trade band 作为轻量执行层候选，避免叠加 reduce-only 和 priority-turnover full 组合。
```

整体判断：F10_EXEC_NT_BAND_ONLY 是四组 soft execution 里唯一值得记录的版本，因为它保持正收益、Sortino 接近 F6，且机制归因相对清晰；但它没有超过 F6，所以不能替代 F6 主线。
