# Reflection-Augmented StockBench Agent 实验设计

## 1. 研究动机

当前 StockBench baseline 使用 dual-agent 流程：

```text
Fundamental Filter Agent -> Enhanced Feature Construction -> Decision Agent
```

该流程已经能够根据股票特征做买入、卖出或持有决策，但缺少一个显式的中间分析层。Decision Agent 需要同时完成市场状态判断、组合风险诊断、个股相对强弱分析和最终交易决策，容易出现分析与交易耦合过紧、历史错误难以被显式吸收的问题。

本实验拟研究：在交易决策前加入结构化 reflection 阶段，是否能提升金融 LLM Agent 的风险调整收益。

## 2. 研究假设

相比原版直接决策流程，显式 reflection 能让 LLM 在下单前先形成可审计的市场判断、组合诊断和个股偏好，从而改善最终交易决策。

核心假设：

```text
Reflection Agent 可以提升 Sortino Ratio，并在不显著降低 Total Return 的情况下控制 Max Drawdown。
```

辅助假设：

```text
1. Reflection 能减少趋势切换阶段的过度保守或过早卖出。
2. Reflection 能提升强势股持有质量，减少弱势股暴露。
3. Reflection 输出的结构化分析可以帮助解释策略收益、回撤和换手的变化。
```

## 3. 实验组设计

### Baseline

原版 dual-agent 流程：

```text
fundamental_filter -> decision_agent
```

对应当前配置：

```yaml
agents:
  mode: "dual"
```

### Variant 1: Reflection Only

第一阶段优先实现：

```text
fundamental_filter -> reflection_agent -> decision_agent
```

Reflection Agent 只做分析，不直接下单。Decision Agent 在原有 features 基础上额外读取 reflection_context。

该实验用于回答：

```text
显式市场反思是否能改善最终交易质量？
```

### Variant 2: Reflection + Risk Review

第二阶段可选：

```text
fundamental_filter -> reflection_agent -> decision_agent -> risk_review_agent
```

Risk Review Agent 对交易结果做二次审查，重点检查回撤风险、集中度风险、现金暴露和决策一致性。

该实验用于回答：

```text
风险审查是否能降低 Max Drawdown，同时尽量维持收益？
```

### Variant 3: Reflection + Memory

第三阶段可选：

```text
fundamental_filter -> reflection_agent(with memory) -> decision_agent
```

Reflection Agent 额外读取最近 N 天的历史决策和执行后表现，用于显式识别历史错误。

该实验用于回答：

```text
历史错误记忆是否能提升策略稳定性？
```

## 4. Reflection Agent 输出 Schema

Reflection Agent 输出结构化 JSON，不输出订单。

建议 schema：

```json
{
  "market_regime": "risk_off | rebound | trend_up | range_bound | uncertain",
  "market_summary": "Brief assessment of broad market and symbol universe conditions.",
  "portfolio_diagnosis": {
    "cash_exposure": "too_high | normal | too_low",
    "risk_level": "low | medium | high",
    "key_issue": "Main portfolio issue before making today's decisions."
  },
  "symbol_assessments": {
    "SYMBOL": {
      "relative_strength": "strong | neutral | weak",
      "trend_quality": "improving | stable | deteriorating",
      "risk": "low | medium | high",
      "preferred_bias": "increase | hold | reduce",
      "rationale": "Short, evidence-based reason."
    }
  },
  "decision_guidance": {
    "overall_bias": "increase_exposure | maintain_exposure | reduce_exposure",
    "watch_items": [
      "Key risks or contradictions the decision agent should consider."
    ]
  }
}
```

要求：

```text
1. 每个 symbol 必须有 symbol_assessments 条目。
2. Reflection 不得给出具体股数或目标金额。
3. preferred_bias 只表达倾向，最终交易仍由 Decision Agent 决定。
4. rationale 必须基于输入特征，不得引用未来信息。
```

## 5. 配置开关设计

为保证 baseline 可复现，reflection 默认关闭。

建议新增配置：

```yaml
agents:
  dual_agent:
    reflection_agent:
      enabled: false
      prompt: "reflection_agent_v1.txt"
      temperature: 0.3
      max_tokens: 8000
```

实验时只修改：

```yaml
enabled: true
```

## 6. 代码插入点

当前主要入口：

```text
stockbench/agents/dual_agent_llm.py
```

当前流程位于：

```text
decide_batch_dual_agent()
```

建议插入位置：

```text
Step 1: Fundamental Filter Agent
Step 2: Enhanced Feature Construction
Step 3: Reflection Agent
Step 4: Decision Agent with reflection_context
```

第一阶段需要新增或修改：

```text
stockbench/agents/prompts/reflection_agent_v1.txt
stockbench/agents/reflection_agent.py
stockbench/agents/dual_agent_llm.py
config.yaml
```

实现原则：

```text
1. reflection_agent.enabled=false 时行为与 baseline 保持一致。
2. reflection 失败时 fallback 为无 reflection_context，不中断回测。
3. reflection JSON 写入 LLM meta 或日志，方便实验分析。
4. prompt_version 记录 reflection prompt 名称，保证实验可追踪。
```

## 7. 评估指标

遵循课题文档的统一评估规范。

主指标：

```text
Sortino Ratio
```

辅助指标：

```text
Total Return
Max Drawdown
```

解释性指标：

```text
1. 平均现金比例
2. 股票仓位变化
3. trades_count 与 turnover
4. 强势股持有比例
5. 弱势股暴露比例
6. Reflection 与最终决策的一致性
```

解释性指标用于分析机制，不替代官方主指标。

## 8. 第一阶段实施计划

第一阶段只实现 Variant 1: Reflection Only。

步骤：

```text
1. 新增 reflection_agent_v1.txt，定义角色、输入、输出 JSON schema。
2. 新增 reflection_agent.py，封装 LLM 调用与 JSON 解析。
3. 在 dual_agent_llm.py 中加入 reflection_agent.enabled 配置分支。
4. 将 reflection_context 注入 Decision Agent 输入。
5. 跑短区间 smoke test，确认输出格式稳定。
6. 跑完整 baseline 与 Variant 1，比较 Sortino、Total Return、Max Drawdown。
```

## 9. 预期分析方式

如果 Variant 1 改进有效，重点分析：

```text
1. 是否提升 Sortino Ratio。
2. 是否降低或维持 Max Drawdown。
3. 是否在中后期趋势恢复阶段改善股票仓位。
4. 是否减少过早卖出强势股或持续持有弱势股。
```

如果 Variant 1 未改进，也仍有研究价值：

```text
1. Reflection 是否输出了正确分析但 Decision Agent 未执行。
2. Reflection 是否过度保守，导致收益下降。
3. Reflection 是否增加了 prompt 噪声。
4. 是否需要 Risk Review 或 Memory 才能转化为交易改进。
```

## 10. 当前建议结论

本课题第一阶段不做针对单次回测结果的硬规则优化，而是引入通用的显式 reflection 机制。该方向符合课题文档中的“决策机制改进”和“记忆与上下文管理”方向，也便于通过 ablation 实验验证多阶段 LLM Agent 架构是否真正改善交易质量。
