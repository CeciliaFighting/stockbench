# 第 5–15 页图示生成实施计划

> 本文档记录图示生成的技术方案、视觉方向、产物规格与执行步骤。  
> `SPEC.md` 保持为内容规划文档；本文件补充视觉与实现计划，避免混淆内容需求和设计实现。

---

## 1. 目标

为成果展示 PPT 第 5–15 页生成每页一张静态图片，用于直接插入对应页面。

图示需要满足：

- 每页一张图片；
- 尺寸统一，适配 16:9 PPT；
- 使用网页技术生成，但最终消费形态是静态图；
- 不出现按钮、hover、输入框、链接态等网页交互痕迹；
- **图片本身只保留核心图表，不放页码、不放页面标题、不放右上角实验角标**；
- PPT 中已有标题和说明，图片不重复这些信息；
- 风格美观、专业、贴近当前 StockBench / DeepSeek / EFund 实验；
- 信息密度克制，优先通俗易懂、可一眼读懂；
- 文字、指标和模块名称尽量来自代码库、实验文档、日志或提交记录，但不把所有证据塞进图里。

---

## 2. 技术栈

采用 **HTML/CSS/SVG + Playwright 截图导出** 的方案。

建议目录：

```text
presentation/figures/
  package.json
  tsconfig.json
  src/
    data.ts
    pages/
      Page05.tsx
      Page06.tsx
      ...
      Page15.tsx
    styles.css
    render.ts
  output/
    page-05.png
    page-06.png
    ...
    page-15.png
```

### 2.1 主要工具

- **Vite + React + TypeScript**
  - 用组件化方式维护 11 张图；
  - 统一设计 token、布局组件、图例、标签、数据卡片。

- **CSS + SVG**
  - CSS 负责整体排版、字体、颜色、阴影、网格；
  - SVG 用于流程线、架构层、矩阵关系、冷却闸门、证据链等图形元素。

- **Playwright / Chromium**
  - 批量渲染并截图；
  - 保证输出尺寸、字体渲染和留白一致。

### 2.2 输出规格

默认输出：

```text
PNG
3840 × 2160
16:9
```

设计画布仍按 1920 × 1080 CSS 逻辑排版，但 Playwright 使用 2× device scale factor 输出高清 PNG，插入 PPT 后小字和细线更清晰。

可选补充输出：

```text
SVG 或 PDF
```

用于高清备份或后续二次编辑。

---

## 3. 视觉方向

### 3.1 总体风格：Experiment Ledger / 交易审计台

本项目面向易方达暑期实习成果展示，图示不应像泛互联网 dashboard，也不应像炫技型 AI 黑绿屏。更适合的方向是：

> 机构研究员把 LLM 交易 Agent 拆解成一个可审计、可约束、可归因、可复盘的交易系统。

关键词：

- 机构研究；
- 交易日志；
- 模块归因；
- 回测凭证；
- 证据链；
- 可复盘。

### 3.2 色彩 token

```text
Ledger Mist      #EEF3F6  背景底色，冷灰蓝研究纸面
Ink Navy         #16253A  主文字与结构线
Efund Blue       #285C9D  主品牌/主流程强调
Trade Cyan       #4BA3B7  数据流、输入、候选池
Signal Amber     #D49A34  信号、排序、实验发现
Risk Carmine     #B64A50  风险、拦截、负面结果
Muted Graphite   #6B7583  辅助文字、注释、证据来源
Panel White      #F8FAFC  卡片底色
Line Bluegray    #C8D3DC  分割线与弱边框
```

控制原则：

- 大面积使用冷灰蓝和白色，保持研究报告感；
- 蓝色表示主链路与保留模块；
- 青色表示输入与数据流；
- 琥珀色表示实验信号、排序、发现；
- 胭脂红只用于风险、拦截、失败实验，不滥用。

### 3.3 字体

优先使用开源字体：

```text
中文 / 正文：Noto Sans SC 或 Source Han Sans
英文 / 标题：IBM Plex Sans
数字 / 代码 / 字段：IBM Plex Mono
```

字体使用原则：

- 标题短而明确，不做营销化表达；
- 数字和字段用等宽字体，强化实验凭证感；
- 页面中保留少量英文 run id / schema / module name，贴近代码与实验日志。

### 3.4 记忆点

每张图都像一张 **模块审计凭证**，但要控制为“图表语言”，不是文档页：

- 不在图片上重复 PPT 已经提供的页码、标题、实验时间、模型名、股票池等信息；
- 少用长句，多用短标签、模块名、箭头和关键数字；
- **大面积说明和重点内容使用中文；仅保留必要的专业短词或 run id，如 Prompt、JSON、F6、Q1**；
- 关键节点可以像交易清算单字段，但只保留理解图表必须的信息；
- 第 12 页冷却机制可使用“raw order → cooldown gate → final order”的闸门/盖章式表达；
- 第 14 页消融实验使用“版本账本矩阵”，避免普通柱状图模板感，同时保证负收益柱状图不压住文字。

这项视觉风险的理由：项目核心并非“LLM 会交易”，而是“LLM 交易动作被工程化为可约束、可归因、可复盘的系统”。

---

## 4. 版式规格

### 4.1 画布

```text
CSS canvas: 1920 × 1080
PNG output: 3840 × 2160
Safe margin: 72–96 px
Content area: approximately 1728 × 888 px
```

### 4.2 图片内部结构

图片内部只放核心图表：

```text
┌──────────────────────────────────────────────┐
│                                              │
│ Main diagram / chart only                    │
│                                              │
│ Optional small legend if necessary            │
│                                              │
└──────────────────────────────────────────────┘
```

注意：

- 不放页码；
- 不放页面大标题；
- 不放右上角 metadata；
- 不放 source strip，证据来源留在文档或演讲稿中；
- 每页只承担一个主论点；
- 不使用无意义编号装饰；
- 只在真实流程、真实层级或版本序列中使用编号；
- 图例必须服务理解，能删则删。

---

## 5. 需要从代码库补充的材料

优先抽取以下内容：

### 5.1 实验设定

来源：

```text
config.yaml
README.md
doc/deepseek_agent_experiment_plan.md
doc/F10_soft_execution_experiment_plan.md
```

已发现线索：

```text
stock pool: DJIA top 20
start: 2025-03-03
end: 2025-06-30
initial capital: 100,000 USD
model: deepseek-v4-flash
strategy: llm_decision
agent_mode: dual
data_mode: offline_only
reflection_agent: false
```

### 5.2 F6 / F5_COOLDOWN_5D 关键结论

来源：

```text
doc/deepseek_agent_experiment_plan.md
doc/F10_soft_execution_experiment_plan.md
```

已发现线索：

```text
F6 = F5_COOLDOWN_5D
   = cleaned fundamental signal
   + anti-overtrade memory
   + 5-day cooldown
```

核心指标：

```text
Total Return: +3.9913%
Sharpe: 0.556719
Sortino: 0.043074
Max Drawdown: -9.1603%
Trades: 261
Trades Notional: 418155.76
```

### 5.3 消融实验结果

来源：

```text
doc/deepseek_agent_experiment_plan.md
doc/F10_soft_execution_experiment_plan.md
```

已发现结果：

```text
B0 DeepSeek baseline: +2.56%, MDD -10.47%, Sharpe 0.404, Trades 564
Q1 Structured price quant: -7.54%, MDD -13.99%, Sharpe -0.881, Trades 257
FUND1 Cleaned fundamental: +3.35%, MDD -11.61%, Sharpe 0.471, Trades 351
C1 Rule-constrained execution: +1.58%, MDD -10.98%, Sharpe 0.302, Trades 75
M1 Selective memory: -0.02%, MDD -11.20%, Sharpe 0.126, Trades 227
F5 baseline: +3.83%, MDD -12.41%, Sharpe 0.525, Trades 363
F5_COOLDOWN_5D / F6: +3.99%, MDD -9.16%, Sharpe 0.557, Trades 261
F5_COOLDOWN_10D: +0.57%, MDD -11.81%, Sharpe 0.188, Trades 240
F5_QUANT_GUARDRAIL: -2.60%, MDD -13.79%, Sharpe -0.163, Trades 289
F5_REGIME_FACTOR_WEIGHTS: -5.89%, MDD -13.34%, Sharpe -0.856, Trades 301
F10_EXEC_NT_BAND_ONLY: +2.9943%, MDD -10.2283%, Sharpe 0.477596, Trades 436
```

### 5.4 Prompt 与 Agent 结构

继续查看：

```text
stockbench/agents/dual_agent_llm.py
stockbench/agents/fundamental_filter_agent.py
stockbench/agents/reflection_agent.py
stockbench/agents/prompts/decision_agent_v1.txt
stockbench/agents/prompts/fundamental_filter_v1.txt
stockbench/agents/prompts/reflection_agent_v1_1.txt
stockbench/llm/llm_client.py
```

需要确认：

- Prompt 输入块；
- LLM 输出 schema；
- JSON 解析与失败重试；
- fundamental filter 与 decision agent 的真实分工。

### 5.5 数据特征与股票池

继续查看：

```text
stockbench/core/features.py
stockbench/core/data_hub.py
stockbench/backtest/engine.py
config.yaml
```

需要确认：

- 价格序列字段；
- technical / quant factor 字段；
- fundamental signal 的清洗方式；
- 股票池过滤与候选选择逻辑。

### 5.6 冷却、风险与归因日志

继续查看：

```text
stockbench/backtest/engine.py
scripts/analyze_experiment_attribution.py
storage/logs/
storage/reports/
```

需要确认：

- cooldown_days = 5 的触发逻辑；
- 是否只拦截短期反向交易；
- raw action / final action 是否有日志；
- risk review / intervention 统计字段。

---

## 6. 第 5–15 页图示形式计划

| 页码 | 主题 | 图形形式 | 重点证据 |
| --- | --- | --- | --- |
| 5 | 整体实验问题与研究目标 | 单步 LLM 决策到模块化 Agent 的问题转化图 | baseline 单步 prompt、模块化目标 |
| 6 | 8 层模块化技术架构总览 | 纵向 8 层 pipeline stack | 数据、候选、记忆、Prompt、约束、归因 |
| 7 | 数据特征层的数据来源与清洗逻辑 | 数据源到 prompt-ready feature block | price、fundamental、quant、portfolio state |
| 8 | 选股层与候选股票池构建 | DJIA 20 股票池筛选漏斗 | `symbols_universe`、数据完整性、可交易性 |
| 9 | 买入候选排序层的评分与排序逻辑 | 候选排序与 Top-K 输入机制 | score/rank/top-k/priority 字段或实验规则 |
| 10 | 交易记忆层的股票级状态结构 | stock memory card + 更新循环 | last action、holding、days since、reason、cooldown |
| 11 | Prompt 决策层的输入输出结构 | prompt blocks + output JSON schema | prompt 文件与 parser |
| 12 | 订单约束层与 5 日冷却机制 | raw action → cooldown gate → final action | cooldown_days=5、反向交易拦截 |
| 13 | 风险控制层的实验尝试与保留策略 | hard override 到 soft warning 的对照图 | Q1 / risk guardrail / F10 负面结果 |
| 14 | 消融实验版本对比 | 版本账本矩阵 + 关键指标 | B0、FUND1、F5、F6、Q1、Risk、F10 |
| 15 | 最终系统结论与证据链 | F6 证据闭环图 | F6 模块、指标、日志、消融结论 |

---

## 7. 实施步骤

### Step 1：资料抽取

- 从代码、prompt、实验文档和日志中抽取真实名称、字段、指标；
- 整理到 `presentation/figures/src/data.ts`；
- 避免在页面组件中硬编码散落数据。

### Step 2：搭建生成环境

- 初始化 `presentation/figures`；
- 安装 React、Vite、TypeScript、Playwright；
- 编写统一 render 脚本，按页输出 PNG。

### Step 3：设计系统落地

- 编写 `styles.css`；
- 建立颜色、字体、spacing、card、label、evidence strip 等基础组件；
- 确保每张图在 1920×1080 下清晰可读。

### Step 4：先做两张样稿

优先制作：

```text
page-06.png  8 层模块化技术架构总览
page-14.png  消融实验版本对比
```

原因：

- 第 6 页检验整体架构表达能力；
- 第 14 页检验真实实验数据、表格密度和视觉风格；
- 两张图能最快判断方向是否适合最终 PPT。

### Step 5：批量制作第 5–15 页

在样稿风格确认后，批量完成剩余 9 张图。

### Step 6：质量检查

检查项：

- 输出尺寸是否一致；
- 字号在 PPT 中是否可读；
- 是否有网页交互痕迹；
- 是否存在过密文字；
- 指标是否与文档/代码一致；
- 页面风格是否统一但不重复；
- 每页是否有一个明确主论点。

---

## 8. 初始自我约束

- 不做泛化 AI dashboard 风格；
- 不用无意义大数字卡片堆砌；
- 不使用默认黑绿终端视觉；
- 不使用纯咨询风箭头流程模板；
- 不把风险、量化、记忆模块都画成同样的盒子；
- 不为了美观牺牲实验准确性；
- 不将尚未在代码或文档中确认的字段伪装成真实实现；
- 不把图做成“小字很多的说明文档”；
- 中文字体要足够粗、足够大，避免细字在 PPT 投影或截图压缩后不可读；
- 删除冗余总结卡、角标和重复结论，把重要信息放大；
- 每张图优先让观众在 5 秒内看懂主结构或主结论。

---

## 9. 下一步

下一步开始搭建 `presentation/figures` 生成环境，并制作两张样稿：

```text
presentation/figures/output/page-06.png
presentation/figures/output/page-14.png
```

样稿完成后再统一批量生成第 5–15 页。
