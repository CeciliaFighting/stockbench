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

## 6. 当前运行安排

四组实验已按 worktree 并行运行，结果待补充。

| Run ID | Branch | Worktree | Status |
|---|---|---|---|
| F10_EXEC_NT_BAND_ONLY | f10-exec-nt-band-only | `/home/terence/code/stockbench-f10-exec-nt-band-only` | running |
| F10_EXEC_REDUCE_ONLY | f10-exec-reduce-only | `/home/terence/code/stockbench-f10-exec-reduce-only` | running |
| F10_EXEC_PRIORITY_TURNOVER | f10-exec-priority-turnover | `/home/terence/code/stockbench-f10-exec-priority-turnover` | running |
| F10_EXEC_SOFT_OPTIMIZER_FULL | f10-exec-soft-optimizer-full | `/home/terence/code/stockbench-f10-exec-soft-optimizer-full` | running |

日志路径：

```text
/home/terence/code/stockbench-f10-exec-nt-band-only/storage/logs/F10_EXEC_NT_BAND_ONLY.log
/home/terence/code/stockbench-f10-exec-reduce-only/storage/logs/F10_EXEC_REDUCE_ONLY.log
/home/terence/code/stockbench-f10-exec-priority-turnover/storage/logs/F10_EXEC_PRIORITY_TURNOVER.log
/home/terence/code/stockbench-f10-exec-soft-optimizer-full/storage/logs/F10_EXEC_SOFT_OPTIMIZER_FULL.log
```

## 7. 结果待补充

实验完成后补充以下表格。

### 7.1 总体结果

| Run ID | Total Return | Sharpe | Sortino | Max Drawdown | Trades | Trades Notional | Avg Cash Ratio | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| F6 / F5_COOLDOWN_5D | TBD | TBD | TBD | TBD | TBD | TBD | TBD | baseline |
| F10_EXEC_NT_BAND_ONLY | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| F10_EXEC_REDUCE_ONLY | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| F10_EXEC_PRIORITY_TURNOVER | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| F10_EXEC_SOFT_OPTIMIZER_FULL | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

### 7.2 干预统计

| Run ID | NT skip | NT partial | Reduced | Turnover partial | Turnover skip | Approved | Hard reject |
|---|---:|---:|---:|---:|---:|---:|---:|
| F10_EXEC_NT_BAND_ONLY | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| F10_EXEC_REDUCE_ONLY | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| F10_EXEC_PRIORITY_TURNOVER | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| F10_EXEC_SOFT_OPTIMIZER_FULL | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

### 7.3 结论

待实验完成后补充：

```text
Best F10 variant: TBD
Whether F10 beats F6: TBD
Primary useful mechanism: TBD
Main failure mode if any: TBD
Recommendation for next experiment: TBD
```
