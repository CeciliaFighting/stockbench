# 第 5–15 页图示内容规划文档

> 目标：为第 5–15 页准备每一页所需图示的**内容框架**。
> 本文档只说明：
>
> - 每个图应该表达什么
> - 图的目的是什么
> - 图中应包含哪些内容
> - 哪些内容需要从代码库或实验输出中补充
> - 如何在代码库中寻找这些内容
>
> 不包含图形形式、排版、配色或视觉风格建议。

---

## 第 5 页图：整体实验问题与研究目标

### 图的目的

说明本实验为什么要做：
原始 LLM 交易 Agent 存在输入噪声、状态缺失、交易反转频繁、难以归因等问题，因此需要将其改造为模块化、可记忆、可约束、可复盘的交易系统。

### 图的主题

**从单步 LLM 决策到模块化交易 Agent 的问题转化**

### 图中应包含的内容

1. **原始问题**
   - LLM 每天根据当日输入直接生成交易动作。
   - 缺少对历史交易行为的持续记忆。
   - 缺少订单后处理约束。
   - 难以解释收益变化来自哪个模块。

2. **核心改造方向**
   - 提升输入质量。
   - 构建候选股票池。
   - 引入股票级交易记忆。
   - 加入买卖动作约束。
   - 记录模块干预日志。
   - 通过消融实验验证模块贡献。

3. **最终目标**
   - 提升决策稳定性。
   - 降低无意义交易。
   - 增强实验可解释性。
   - 找到真正有效的模块组合。

### 是否需要从代码库中寻找内容

**需要，但不需要很深入。**

主要用于补充：

- baseline 的原始决策流程；
- 最终版本中包含了哪些模块；
- 实验文档中对问题的描述。

### 在代码库中寻找的方法

可以搜索以下关键词：

```bash
grep -R "baseline" .
grep -R "LLM" .
grep -R "memory" .
grep -R "cooldown" .
grep -R "ablation" .
grep -R "experiment" .
```

如果代码库是 Python 项目，可以优先查看：

```text
README.md
docs/
experiments/
scripts/
agent/
trading/
```

重点找：

- baseline agent 的入口文件；
- 最终 agent 的主流程；
- 实验配置文件；
- 消融实验说明文档。

---

## 第 6 页图：8 层模块化技术架构总览

### 图的目的

展示整个交易 Agent 被拆解为 8 个功能层，说明每一层在系统中承担的职责，以及这些层如何共同形成完整决策链路。

### 图的主题

**模块化 LLM 交易 Agent 的 8 层架构**

### 图中应包含的内容

8 个层级：

1. **数据特征层**
   - 原始行情数据。
   - 基本面数据。
   - 技术指标。
   - 组合状态数据。
   - 数据清洗与特征归类。

2. **选股层**
   - 可交易股票池。
   - 数据完整性过滤。
   - 流动性或有效性过滤。
   - 初步候选集。

3. **买入候选排序层**
   - 候选股票打分。
   - Top-K 候选选择。
   - 排序依据，如基本面、趋势、组合需求等。

4. **交易记忆层**
   - 股票级记忆。
   - 上次动作。
   - 上次交易原因。
   - 持仓状态。
   - 距离上次交易天数。

5. **Prompt 决策层**
   - 将特征、候选、记忆、组合状态输入 LLM。
   - 输出初始动作。
   - 输出理由。
   - 输出置信度或风险说明。

6. **订单约束层**
   - 交易冷却。
   - 反向交易限制。
   - 仓位约束。
   - 订单动作修正。

7. **风险控制层**
   - 风险提示。
   - 波动或回撤信息。
   - 组合集中度。
   - 是否触发风险干预。

8. **归因分析层**
   - 记录 LLM 原始动作。
   - 记录最终执行动作。
   - 记录触发模块。
   - 记录动作变化原因。
   - 支撑实验复盘。

### 是否需要从代码库中寻找内容

**需要。**

这个图需要尽量贴合代码中的真实模块名称、函数名称和数据流，否则会显得空泛。

### 在代码库中寻找的方法

搜索模块名或功能关键词：

```bash
grep -R "feature" .
grep -R "universe" .
grep -R "candidate" .
grep -R "rank" .
grep -R "memory" .
grep -R "prompt" .
grep -R "cooldown" .
grep -R "risk" .
grep -R "attribution" .
grep -R "log" .
```

如果是 Windows CMD，可以使用：

```cmd
findstr /S /I "feature universe candidate rank memory prompt cooldown risk attribution log" *.py *.md *.json *.yaml
```

重点查看：

- agent 主入口文件；
- config 配置文件；
- prompt 构造文件；
- memory 管理文件；
- order 或 execution 相关文件；
- experiment runner；
- log 输出文件。

需要从代码中补充：

- 每层真实函数名；
- 每层输入输出变量；
- 模块是否真实实现；
- 哪些模块只是实验尝试，哪些进入最终版本。

---

## 第 7 页图：数据特征层的数据来源与清洗逻辑

### 图的目的

解释 LLM 决策前的数据并不是直接原样输入，而是经过清洗、筛选、归类和压缩，从而减少噪声，提高输入质量。

### 图的主题

**从原始市场数据到结构化特征输入**

### 图中应包含的内容

1. **数据来源**
   - 股票价格数据。
   - 成交量或流动性数据。
   - 基本面数据。
   - 技术指标。
   - 持仓与现金状态。
   - 历史交易记录。

2. **数据处理步骤**
   - 缺失值处理。
   - 异常值处理。
   - 字段筛选。
   - 特征归类。
   - 数值转文本摘要。
   - Prompt 输入压缩。

3. **输出内容**
   - 每只股票的结构化特征摘要。
   - 市场环境摘要。
   - 当前组合状态摘要。
   - 可供 LLM 直接读取的输入块。

4. **实验结论相关内容**
   - 数据清洗提升输入稳定性。
   - 不是字段越多越好。
   - 高噪声字段可能损害 LLM 判断。

### 是否需要从代码库中寻找内容

**需要。**

尤其需要确认：

- 使用了哪些真实数据字段；
- 是否有基本面指标；
- 是否有技术指标；
- 是否有字段归一化或文本化处理。

### 在代码库中寻找的方法

搜索：

```bash
grep -R "fundamental" .
grep -R "indicator" .
grep -R "technical" .
grep -R "price" .
grep -R "volume" .
grep -R "feature" .
grep -R "normalize" .
grep -R "summary" .
grep -R "missing" .
grep -R "nan" .
```

Windows CMD：

```cmd
findstr /S /I "fundamental indicator technical price volume feature normalize summary missing nan" *.py *.md *.json *.yaml
```

重点查看：

- 数据加载脚本；
- feature engineering 文件；
- prompt 输入构造函数；
- 数据预处理函数；
- 实验配置中的 feature list。

需要从代码中补充：

- 真实字段名称；
- 是否删除字段；
- 是否生成摘要文本；
- 数据输入到 Prompt 的具体格式。

---

## 第 8 页图：选股层与候选股票池构建

### 图的目的

说明 Agent 并不是在全市场上无差别决策，而是先通过规则或数据完整性筛选出一个可控的股票池，再交给后续模块处理。

### 图的主题

**从全量股票到可交易候选池**

### 图中应包含的内容

1. **输入范围**
   - 全部可用股票。
   - 当日有行情数据的股票。
   - 数据完整的股票。

2. **过滤条件**
   - 数据缺失过滤。
   - 流动性过滤。
   - 价格异常过滤。
   - 基本面可用性过滤。
   - 已停牌或不可交易过滤。
   - 其他实验中定义的股票池限制。

3. **输出结果**
   - 可交易股票池。
   - 初步候选集。
   - 每日可供排序的股票列表。

4. **实验结论相关内容**
   - 股票池过大时，Prompt 噪声增加。
   - 股票池过小时，可能错过交易机会。
   - 合理候选池可以提升 LLM 横向比较质量。

### 是否需要从代码库中寻找内容

**需要。**

选股层往往在代码中有明确过滤规则，图中最好使用真实规则而不是泛泛而谈。

### 在代码库中寻找的方法

搜索：

```bash
grep -R "universe" .
grep -R "screen" .
grep -R "filter" .
grep -R "tradable" .
grep -R "candidate" .
grep -R "stock_pool" .
grep -R "valid_symbols" .
grep -R "available_stocks" .
```

Windows CMD：

```cmd
findstr /S /I "universe screen filter tradable candidate stock_pool valid_symbols available_stocks" *.py *.md *.json *.yaml
```

重点查看：

- 股票池构造函数；
- 每日回测循环中如何选择股票；
- 配置文件中的股票列表；
- 数据加载后的过滤逻辑。

需要从代码中补充：

- 初始股票数量；
- 过滤后股票数量；
- 具体过滤条件；
- 是否每天动态更新股票池。

---

## 第 9 页图：买入候选排序层的评分与排序逻辑

### 图的目的

解释在进入 LLM 决策前，系统如何对候选股票进行优先级排序，帮助 LLM 聚焦更值得考虑的股票。

### 图的主题

**候选股票排序与 Top-K 输入机制**

### 图中应包含的内容

1. **输入**
   - 选股层输出的候选股票池。
   - 每只股票的特征摘要。
   - 当前持仓状态。
   - 市场环境或风险信息。

2. **排序依据**
   - 基本面质量。
   - 近期表现。
   - 技术指标。
   - 趋势或动量。
   - 当前是否已持仓。
   - 是否有近期交易记忆。
   - 是否符合组合需求。

3. **排序输出**
   - 候选股票得分。
   - 排名列表。
   - Top-K 候选。
   - 输入 Prompt 的候选摘要。

4. **实验结论相关内容**
   - 排序可以减少 LLM 比较负担。
   - 过度依赖短期排序信号会放大噪声。
   - 排序层应作为辅助，而不是直接决定买入。

### 是否需要从代码库中寻找内容

**需要。**

尤其需要确认是否真的有显式评分函数，还是只是按照某些字段排序。

### 在代码库中寻找的方法

搜索：

```bash
grep -R "rank" .
grep -R "score" .
grep -R "top_k" .
grep -R "topk" .
grep -R "candidate" .
grep -R "sort" .
grep -R "priority" .
```

Windows CMD：

```cmd
findstr /S /I "rank score top_k topk candidate sort priority" *.py *.md *.json *.yaml
```

重点查看：

- candidate ranking 函数；
- prompt 构造前的股票排序；
- 是否存在 score 字段；
- 是否保存候选排序结果。

需要从代码中补充：

- 排序指标；
- 评分公式或规则；
- Top-K 数量；
- 排序输出样例。

---

## 第 10 页图：交易记忆层的股票级状态结构

### 图的目的

说明系统如何让 LLM 记住过去的交易行为，使 Agent 的决策具有连续性，而不是每天从零开始。

### 图的主题

**股票级交易记忆如何进入 LLM 决策**

### 图中应包含的内容

1. **记忆对象**
   - 每只股票独立维护一份记忆。
   - 不只是全局账户状态。

2. **记忆字段**
   - 股票代码。
   - 当前是否持仓。
   - 当前持仓数量或权重。
   - 上次交易动作。
   - 上次交易日期。
   - 距离上次交易天数。
   - 上次交易理由。
   - 最近一次 LLM 判断。
   - 是否处于冷却期。

3. **记忆更新过程**
   - 决策前读取记忆。
   - Prompt 中加入记忆摘要。
   - LLM 输出动作。
   - 订单执行后更新记忆。
   - 记忆进入下一轮决策。

4. **实验结论相关内容**
   - 记忆减少了重复决策和短期反转。
   - 股票级记忆比全局摘要更适合交易场景。
   - 记忆与冷却机制组合效果更明显。

### 是否需要从代码库中寻找内容

**强烈需要。**

这个图需要尽量展示真实 memory 数据结构，否则容易显得虚。

### 在代码库中寻找的方法

搜索：

```bash
grep -R "memory" .
grep -R "last_action" .
grep -R "last_trade" .
grep -R "days_since" .
grep -R "position" .
grep -R "holding" .
grep -R "trade_history" .
grep -R "reason" .
```

Windows CMD：

```cmd
findstr /S /I "memory last_action last_trade days_since position holding trade_history reason" *.py *.md *.json *.yaml
```

重点查看：

- memory manager；
- trading state；
- portfolio state；
- trade history；
- prompt 中 memory block 的构造。

需要从代码中补充：

- memory 的真实字段；
- memory 存储格式；
- memory 更新函数；
- Prompt 中如何展示 memory。

---

## 第 11 页图：Prompt 决策层的输入输出结构

### 图的目的

说明 LLM 实际接收到哪些信息，以及它需要输出什么结构化内容。重点展示 LLM 决策不是一句自然语言问答，而是由多个输入块共同构成的结构化决策任务。

### 图的主题

**LLM Prompt 的结构化决策输入与输出**

### 图中应包含的内容

1. **Prompt 输入块**
   - 系统角色说明。
   - 当前市场状态。
   - 当前组合状态。
   - 候选股票列表。
   - 股票特征摘要。
   - 股票级记忆。
   - 风险提示。
   - 交易规则或约束说明。

2. **LLM 需要输出**
   - 股票代码。
   - 动作：Buy / Sell / Hold。
   - 交易数量或目标仓位。
   - 决策理由。
   - 风险说明。
   - 置信度或优先级。
   - 输出格式要求。

3. **后续处理**
   - 解析 LLM 输出。
   - 检查格式合法性。
   - 保存原始动作。
   - 传入订单约束层。

4. **实验结论相关内容**
   - 结构化 Prompt 比长文本堆叠更稳定。
   - 保留原始 LLM 输出对归因分析很重要。
   - LLM 应输出建议动作，而不是直接执行订单。

### 是否需要从代码库中寻找内容

**强烈需要。**

Prompt 是实验技术性最核心的内容之一，最好从真实代码中抽取输入块名称和输出格式。

### 在代码库中寻找的方法

搜索：

```bash
grep -R "prompt" .
grep -R "system_message" .
grep -R "user_message" .
grep -R "template" .
grep -R "json" .
grep -R "Buy" .
grep -R "Sell" .
grep -R "Hold" .
grep -R "reason" .
```

Windows CMD：

```cmd
findstr /S /I "prompt system_message user_message template json Buy Sell Hold reason" *.py *.md *.json *.yaml *.txt
```

重点查看：

- prompt template 文件；
- LLM 调用函数；
- response parser；
- 决策输出 schema；
- 示例 Prompt 或日志。

需要从代码中补充：

- Prompt 的真实输入段落；
- 输出 JSON 或文本格式；
- 解析函数；
- 是否有格式错误处理。

---

## 第 12 页图：订单约束层与 5 日冷却机制

### 图的目的

解释系统如何在 LLM 输出动作后进行低权限后处理，尤其是如何通过 5 日冷却机制抑制短期反向交易。

### 图的主题

**LLM 原始动作到最终交易动作的约束修正**

### 图中应包含的内容

1. **输入**
   - LLM 原始动作。
   - 当前持仓状态。
   - 上次交易日期。
   - 距离上次交易天数。
   - 当前是否出现反向交易。

2. **冷却判断**
   - 如果距离上次交易不足 5 天。
   - 且当前动作与上次动作方向相反。
   - 则触发冷却机制。

3. **动作修正**
   - Buy 可能被改为 Hold。
   - Sell 可能被改为 Hold。
   - 非反向动作可以保留。
   - Hold 通常不需要修正。

4. **输出**
   - 最终动作。
   - 是否触发冷却。
   - 触发原因。
   - 归因日志记录。

5. **实验结论相关内容**
   - 冷却机制减少了短期反转。
   - 它不替代 LLM 决策，只做稳定性约束。
   - 5 日窗口有效，但未来可以探索自适应冷却。

### 是否需要从代码库中寻找内容

**强烈需要。**

尤其要确认：

- 冷却窗口是否确实为 5；
- 触发条件如何写；
- 动作修正规则是什么；
- 是否记录干预日志。

### 在代码库中寻找的方法

搜索：

```bash
grep -R "cooldown" .
grep -R "5" .
grep -R "days_since" .
grep -R "last_trade" .
grep -R "reverse" .
grep -R "override" .
grep -R "final_action" .
grep -R "raw_action" .
```

Windows CMD：

```cmd
findstr /S /I "cooldown days_since last_trade reverse override final_action raw_action" *.py *.md *.json *.yaml
```

重点查看：

- order constraint 文件；
- action post-processing 函数；
- memory 与 order 交互部分；
- 实验配置中的 cooldown_days；
- 日志中 raw_action 和 final_action 的差异。

需要从代码中补充：

- 冷却窗口参数；
- 判断条件；
- 原始动作与最终动作示例；
- 干预日志字段。

---

## 第 13 页图：风险控制层的实验尝试与保留策略

### 图的目的

说明风险控制层为什么没有作为强覆盖模块进入最终版本，而是更适合作为提示信息或软约束。这一页应体现实验不是所有模块都被保留，而是通过实验判断模块边界。

### 图的主题

**风险模块从强覆盖到软提示的实验结论**

### 图中应包含的内容

1. **风险层尝试内容**
   - 波动风险。
   - 回撤风险。
   - 仓位集中风险。
   - 单股暴露风险。
   - 市场环境风险。

2. **强覆盖逻辑**
   - 风险过高时强制改为 Hold。
   - 风险过高时阻止 Buy。
   - 风险过高时降低仓位。

3. **观察到的问题**
   - 可能过度保守。
   - 可能错过有效交易机会。
   - 风险层权限过高时，会覆盖 LLM 的有效判断。
   - 收益弹性可能下降。

4. **最终处理策略**
   - 风险信息仍然保留。
   - 作为 Prompt 输入或提示。
   - 不作为常规强制覆盖层。
   - 只在极端情况下考虑硬约束。

5. **实验结论相关内容**
   - 模块不是越多越好。
   - 模块权限需要控制。
   - 风险控制适合作为软信息，而不是无条件执行器。

### 是否需要从代码库中寻找内容

**需要。**

需要确认风险层在实验中实际实现到什么程度，以及是否有对应配置或 ablation 版本。

### 在代码库中寻找的方法

搜索：

```bash
grep -R "risk" .
grep -R "volatility" .
grep -R "drawdown" .
grep -R "exposure" .
grep -R "concentration" .
grep -R "risk_control" .
grep -R "risk_score" .
grep -R "risk_note" .
```

Windows CMD：

```cmd
findstr /S /I "risk volatility drawdown exposure concentration risk_control risk_score risk_note" *.py *.md *.json *.yaml
```

重点查看：

- risk module 文件；
- prompt 中 risk 信息；
- ablation 配置；
- 风险层是否修改最终动作；
- 实验结果中 Risk 版本表现。

需要从代码中补充：

- 风险指标；
- 风险触发条件；
- 风险是否覆盖动作；
- Risk 版本的表现结论。

---

## 第 14 页图：消融实验版本对比

### 图的目的

展示实验如何一步步验证模块贡献，说明最终版本 F6 不是随意组合，而是经过 baseline、基本面、记忆、冷却、量化信号、风险模块等对比后筛选出来的。

### 图的主题

**从 Baseline 到 F6 的模块贡献验证**

### 图中应包含的内容

1. **实验版本**
   - B0 Baseline。
   - FUND1 或基本面增强版本。
   - 记忆模块版本。
   - 记忆 + 冷却版本。
   - Q1 量化信号版本。
   - Risk 风险覆盖版本。
   - F6 最终版本。

2. **每个版本包含哪些模块**
   - 数据清洗。
   - 选股。
   - 候选排序。
   - 交易记忆。
   - 5 日冷却。
   - 量化信号。
   - 风险覆盖。
   - 归因日志。

3. **对比维度**
   - 收益表现。
   - 稳定性。
   - 交易频率。
   - 短期反转次数。
   - 可解释性。
   - 模块干预次数。
   - 是否进入最终版本。

4. **实验结论相关内容**
   - 基本面清洗有效。
   - 记忆 + 冷却明显改善行为稳定性。
   - Q1 可能引入短期噪声。
   - Risk 强覆盖可能过度保守。
   - F6 是较均衡的最终版本。

### 是否需要从代码库中寻找内容

**强烈需要。**

这一页需要实验结果支持，最好直接使用真实 ablation 表格、日志或输出指标。

### 在代码库中寻找的方法

搜索：

```bash
grep -R "ablation" .
grep -R "B0" .
grep -R "FUND" .
grep -R "F5" .
grep -R "F6" .
grep -R "Q1" .
grep -R "Risk" .
grep -R "result" .
grep -R "metrics" .
grep -R "return" .
grep -R "sharpe" .
grep -R "drawdown" .
```

Windows CMD：

```cmd
findstr /S /I "ablation B0 FUND F5 F6 Q1 Risk result metrics return sharpe drawdown" *.py *.md *.json *.yaml *.csv *.txt
```

重点查看：

- 实验结果 CSV；
- backtest output；
- ablation 配置；
- summary report；
- 日志目录；
- README 中的实验结论。

需要从代码中补充：

- 各版本真实名称；
- 各版本启用模块；
- 实验指标；
- 最终选择 F6 的依据；
- 哪些版本被排除及原因。

---

## 第 15 页图：最终系统结论与证据链

### 图的目的

总结整个实验最终得到的技术结论，并把这些结论与前面模块、日志和消融实验连接起来，形成完整闭环。

### 图的主题

**最终版本 F6 的系统性结论**

### 图中应包含的内容

1. **最终保留模块**
   - 数据特征清洗。
   - 选股层。
   - 候选排序。
   - 股票级记忆。
   - Prompt 决策。
   - 5 日冷却。
   - 风险软提示。
   - 归因日志。

2. **没有强保留的模块或策略**
   - 过强短期量化信号。
   - 高权限风险覆盖。
   - 过多未经筛选的输入字段。
   - 直接让 LLM 独立控制最终订单。

3. **核心实验结论**
   - 输入质量比输入数量更重要。
   - 股票级记忆提升连续性。
   - 低权限约束提升稳定性。
   - 模块权限过高可能产生负贡献。
   - 归因日志让实验结论可验证。
   - 最终 Agent 是 LLM 与工程规则共同组成的系统。

4. **证据来源**
   - 消融实验结果。
   - 交易日志。
   - raw_action 与 final_action 对比。
   - 冷却机制触发记录。
   - Risk / Q1 版本表现。
   - 最终 F6 表现。

### 是否需要从代码库中寻找内容

**需要。**

这一页是总结页，最好把前面找到的真实证据压缩成结论链。

### 在代码库中寻找的方法

搜索：

```bash
grep -R "final" .
grep -R "F6" .
grep -R "summary" .
grep -R "conclusion" .
grep -R "best" .
grep -R "selected" .
grep -R "cooldown" .
grep -R "raw_action" .
grep -R "final_action" .
grep -R "intervention" .
```

Windows CMD：

```cmd
findstr /S /I "final F6 summary conclusion best selected cooldown raw_action final_action intervention" *.py *.md *.json *.yaml *.csv *.txt
```

重点查看：

- final config；
- final experiment result；
- summary 文档；
- intervention log；
- 消融实验最终对比；
- 最终模型或策略命名。

需要从代码中补充：

- F6 的真实模块组成；
- 最终实验指标；
- 模块触发统计；
- 最终结论原文；
- 可以支撑结论的具体例子。

---

# 汇总表

| 页码     | 图标题                         | 主要目的                   | 是否需要代码库补充 |
| -------- | ------------------------------ | -------------------------- | ------------------ |
| 第 5 页  | 整体实验问题与研究目标         | 说明为什么需要模块化 Agent | 需要，轻量         |
| 第 6 页  | 8 层模块化技术架构总览         | 展示完整系统结构           | 需要               |
| 第 7 页  | 数据特征层的数据来源与清洗逻辑 | 解释输入如何被加工         | 需要               |
| 第 8 页  | 选股层与候选股票池构建         | 说明股票池如何缩小         | 需要               |
| 第 9 页  | 买入候选排序层的评分与排序逻辑 | 说明候选如何排序           | 需要               |
| 第 10 页 | 交易记忆层的股票级状态结构     | 展示 Agent 如何记忆        | 强烈需要           |
| 第 11 页 | Prompt 决策层的输入输出结构    | 展示 LLM 决策接口          | 强烈需要           |
| 第 12 页 | 订单约束层与 5 日冷却机制      | 展示动作如何被修正         | 强烈需要           |
| 第 13 页 | 风险控制层的实验尝试与保留策略 | 解释 Risk 为什么弱化       | 需要               |
| 第 14 页 | 消融实验版本对比               | 验证模块贡献               | 强烈需要           |
| 第 15 页 | 最终系统结论与证据链           | 总结 F6 为什么成立         | 需要               |

---

# 建议优先从代码库补充的材料

如果时间有限，建议优先找以下 6 类内容：

1. **最终版本配置**
   - F6 启用了哪些模块。
   - 哪些模块关闭或弱化。

2. **Prompt 模板**
   - LLM 输入块。
   - LLM 输出格式。

3. **交易记忆结构**
   - memory 字段。
   - 更新逻辑。

4. **冷却机制代码**
   - 是否为 5 日。
   - 触发条件。
   - 动作如何改写。

5. **消融实验结果**
   - B0、FUND、F5、F6、Q1、Risk 的对比。

6. **干预日志**
   - raw action。
   - final action。
   - trigger module。
   - reason。
