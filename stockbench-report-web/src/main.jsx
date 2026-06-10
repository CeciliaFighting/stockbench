import React, { useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  BookOpen,
  CheckCircle2,
  ClipboardList,
  Code2,
  Database,
  FileJson,
  FileText,
  GitBranch,
  HardDrive,
  Layers3,
  LineChart,
  MemoryStick,
  Network,
  Play,
  ShieldCheck,
  SlidersHorizontal,
  Target,
  TimerReset,
  TrendingDown,
  TrendingUp,
  XCircle,
} from 'lucide-react';
import frameworkImage from '../../main.png';
import datasetImage from '../../dataset.png';
import './styles.css';

const slides = [
  ['cover', '封面', '基于 StockBench 的金融 LLM Agent 研究', '不是再造一个交易规则库，而是把 LLM 决策放进可观测、可回测、可归因的工程系统。'],
  ['question', '研究问题', '我的切入点：LLM 到底输在哪里', '本次研究把问题拆成输入噪声、历史状态、订单行为、评估归因四个技术层面。'],
  ['architecture', '代码架构', 'StockBench 运行链路如何串起来', '从 CLI 到 BacktestEngine，再到 Strategy.on_bar、dual-agent、订单执行和报告落盘。'],
  ['data', '数据与缓存', '数据层：避免把 API 限速误判成策略问题', '价格、新闻、财务数据进入 data_hub；共享 data cache 与本地 LLM cache 分离。'],
  ['feature', '特征构造', '特征层：让 Prompt 输入更像结构化交易状态', 'features.py 负责市场、新闻、仓位、基本面；FUND1 的价值是降低基本面噪声。'],
  ['dual', '双 Agent', '决策层：fundamental filter + decision agent', '先判断哪些股票需要基本面，再按过滤结果重建 enhanced features，最后组合级输出目标仓位。'],
  ['memory', '记忆机制', '状态层：从 previous_decisions 到长期 decision_history', 'Strategy 按 symbol 保存历史动作，并在下一次 prompt 中提供最近记录，避免每天从零判断。'],
  ['execution', '执行层', '订单层：target_cash_amount 如何变成真实买卖', 'LLM 输出目标金额，策略计算 delta，执行器使用开盘价、滑点、手续费和现金保护生成交易记录。'],
  ['cooldown', 'F6 技术点', 'F6 为什么是综合最优：5D cooldown 的工程边界', '5D 约束减少短期反向 churn；10D 和强风控会压制纠错与反弹参与。'],
  ['attribution', '归因产物', '报告层：实验不是只看收益表', 'reports.py、detailed_trades.jsonl、portfolio_snapshots 和 attribution 脚本共同支撑解释。'],
  ['results', '实验矩阵', '结果：有效的是低权限行为约束，不是高权限接管', 'F6 保持主线；F10/F11 的重点转向单模块、低权限、强归因。'],
  ['f11', '后续设计', 'F11 应该怎么继续：共享 filter cache + 单模块矩阵', '下一步重点不是 full combo，而是每个模块证明自己确实改变了 prompt、size、budget 或 memory。'],
  ['closing', '总结', '最终汇报主张', '把 LLM 当成决策推理器，而不是交易系统本身；系统边界、记录和归因决定研究可信度。'],
];

const codeFlow = [
  ['CLI 参数', 'stockbench/apps/run_backtest.py', '解析 --data-mode、--llm-profile、--cooldown-days，注入 config'],
  ['回测主循环', 'stockbench/backtest/pipeline.py', '创建 Datasets、Slippage、BacktestEngine，并调用 write_outputs'],
  ['每日策略', 'stockbench/backtest/strategies/llm_decision.py', 'Strategy.on_bar(ctx) 构造 features、调用 unified_decide_batch'],
  ['双 Agent', 'stockbench/agents/dual_agent_llm.py', 'filter -> enhanced features -> decision_agent JSON'],
  ['订单执行', 'stockbench/backtest/engine.py', '以 open price 成交，记录 trade / portfolio snapshot / metrics'],
];

const experimentRows = [
  ['B&H20', '+0.73%', '0.018', '-14.95%', '-', '课题统一对照'],
  ['B0 DeepSeek baseline', '+2.56%', '0.034', '-10.47%', '564', '能盈利但换手高'],
  ['FUND1', '+3.35%', '0.038', '-11.61%', '351', '基本面清洗有边际贡献'],
  ['F5 memory', '+3.83%', '0.045', '-12.41%', '363', 'Sortino 高，但回撤偏大'],
  ['F6 / 5D cooldown', '+3.99%', '0.043', '-9.16%', '261', '综合最优主线'],
  ['F9A buy/add reduce', '+3.36%', '0.039', '-9.73%', '245', '低权限 sizing 有价值'],
  ['F10E defensive lagging', '+3.68%', '-', '-11.11%', '268', '接近但弱于 F6'],
  ['F10F NT band old', '+4.17%', '-', '-11.19%', '251', '收益高但风险变差'],
  ['F10G risk budget', '+0.96%', '-', '-10.84%', '164', '风控压制收益'],
];

const codeRefs = {
  cli: ['run_backtest.py', 'main()', '--data-mode / --llm-profile / --cooldown-days'],
  strategy: ['llm_decision.py', 'Strategy.on_bar(ctx)', 'features_list -> decisions_map -> orders'],
  dual: ['dual_agent_llm.py', 'decide_batch_dual_agent()', 'filter_result -> enhanced_features_list'],
  filter: ['fundamental_filter_agent.py', 'filter_stocks_needing_fundamental()', 'shared cache key ignores portfolio/history for reuse'],
  engine: ['engine.py', 'BacktestEngine.run()', 'open price fill + detailed trade records'],
  report: ['reports.py', 'write_outputs()', 'metrics.json / daily_nav.parquet / trades.parquet'],
};

function App() {
  const [index, setIndex] = useState(0);
  const [selectedFlow, setSelectedFlow] = useState(2);
  const [selectedExp, setSelectedExp] = useState('F6 / 5D cooldown');
  const slide = slides[index];

  const content = useMemo(() => {
    switch (slide[0]) {
      case 'cover':
        return <CoverSlide />;
      case 'question':
        return <QuestionSlide />;
      case 'architecture':
        return <ArchitectureSlide selected={selectedFlow} setSelected={setSelectedFlow} />;
      case 'data':
        return <DataSlide />;
      case 'feature':
        return <FeatureSlide />;
      case 'dual':
        return <DualAgentSlide />;
      case 'memory':
        return <MemorySlide />;
      case 'execution':
        return <ExecutionSlide />;
      case 'cooldown':
        return <CooldownSlide />;
      case 'attribution':
        return <AttributionSlide />;
      case 'results':
        return <ResultsSlide selected={selectedExp} setSelected={setSelectedExp} />;
      case 'f11':
        return <F11Slide />;
      case 'closing':
        return <ClosingSlide />;
      default:
        return null;
    }
  }, [slide, selectedFlow, selectedExp]);

  function go(delta) {
    setIndex((value) => Math.min(slides.length - 1, Math.max(0, value + delta)));
  }

  return (
    <div className="deck-shell">
      <aside className="slide-nav">
        <div className="brand">
          <span className="brand-mark">SB</span>
          <div>
            <strong>StockBench</strong>
            <span>技术汇报</span>
          </div>
        </div>
        <div className="nav-list">
          {slides.map((item, itemIndex) => (
            <button
              key={item[0]}
              className={itemIndex === index ? 'nav-dot active' : 'nav-dot'}
              onClick={() => setIndex(itemIndex)}
            >
              <span>{String(itemIndex + 1).padStart(2, '0')}</span>
              {item[1]}
            </button>
          ))}
        </div>
      </aside>
      <main className="slide-stage">
        <header className="slide-topbar">
          <div>
            <span className="page-count">{index + 1} / {slides.length}</span>
            <h1>{slide[2]}</h1>
            <p>{slide[3]}</p>
          </div>
          <div className="step-controls">
            <button onClick={() => go(-1)} disabled={index === 0} title="上一页">
              <ArrowLeft size={18} />
            </button>
            <button onClick={() => go(1)} disabled={index === slides.length - 1} title="下一页">
              <ArrowRight size={18} />
            </button>
          </div>
        </header>
        <section className="slide-card">{content}</section>
      </main>
    </div>
  );
}

function CoverSlide() {
  return (
    <div className="cover-grid">
      <div className="cover-copy">
        <span className="badge">最终主线：F6 = FUND1 + memory + 5D cooldown</span>
        <h2>少做一点，但要知道为什么少做</h2>
        <p>
          我把本次工作定义为“金融 LLM Agent 的工程化约束研究”：不是让 LLM 直接替代策略系统，
          而是在真实回测中给它输入清洗、历史状态、订单边界和归因日志。
        </p>
        <div className="hero-metrics">
          <Metric label="F6 Return" value="+3.99%" icon={TrendingUp} />
          <Metric label="F6 MDD" value="-9.16%" icon={TrendingDown} />
          <Metric label="Trades" value="261" icon={LineChart} />
        </div>
      </div>
      <img src={frameworkImage} alt="StockBench framework" />
    </div>
  );
}

function QuestionSlide() {
  const cards = [
    ['输入层', 'LLM 看到的不是“市场真相”，而是价格、新闻、财务字段拼出来的 prompt。基本面缺失、陈旧和极端值会变成错误叙事。', SlidersHorizontal],
    ['状态层', '原始 baseline 容易每天重新判断同一只股票，缺少“刚买过/刚卖过/上次为什么做”的股票级状态。', MemoryStick],
    ['行为层', 'LLM 可能给出合理解释但目标金额来回震荡，最终表现成短期反向交易和高 notional。', ShieldCheck],
    ['评估层', '只看最终 return 不够，必须知道模块触发了多少次、改了哪些订单、改动后未来收益如何。', FileJson],
  ];
  return <CardGrid cards={cards} />;
}

function ArchitectureSlide({ selected, setSelected }) {
  const active = codeFlow[selected];
  return (
    <div>
      <div className="ablation-line code-flow">
        {codeFlow.map((item, idx) => (
          <button
            key={item[0]}
            className={idx === selected ? 'ablation-node active' : 'ablation-node'}
            onClick={() => setSelected(idx)}
          >
            <strong>{item[0]}</strong>
            <span>{item[1]}</span>
          </button>
        ))}
      </div>
      <div className="detail-panel">
        <Code2 size={26} />
        <div>
          <strong>{active[1]}</strong>
          <p>{active[2]}</p>
        </div>
      </div>
      <CodePathList />
    </div>
  );
}

function DataSlide() {
  return (
    <div className="two-col">
      <div>
        <HorizontalPipeline
          items={[
            ['price/news/financials', Database],
            ['data_hub', HardDrive],
            ['features.py', FileText],
            ['prompt payload', FileJson],
          ]}
        />
        <img className="dataset-img" src={datasetImage} alt="StockBench dataset" />
      </div>
      <div className="future-card">
        <h3>我在汇报里要强调的工程点</h3>
        <ul>
          <li>`--data-mode offline_only` 把实验和实时 API 波动隔离开。</li>
          <li>`STOCKBENCH_DATA_CACHE_DIR` 只共享数据缓存，LLM cache 仍按 worktree/run 本地隔离。</li>
          <li>F11 另有 `STOCKBENCH_FUNDAMENTAL_FILTER_CACHE_DIR`，专门复用 fundamental filter 结果。</li>
          <li>缓存策略本质是实验控制变量：避免把 rate limit、网络波动误判成策略差异。</li>
        </ul>
      </div>
    </div>
  );
}

function FeatureSlide() {
  return (
    <div className="compare-grid">
      <SignalPanel
        tone="bad"
        title="原始输入风险"
        chips={['缺失财务字段', '陈旧 timestamp', '极端 PE/PB', '新闻稀疏', '价格窗口短', '仓位状态不连续']}
      />
      <div className="processor">
        <FileText size={30} />
        <strong>build_features_for_prompt()</strong>
        <span>market_data</span>
        <span>news_events</span>
        <span>position_state</span>
        <span>fundamental_data</span>
      </div>
      <SignalPanel
        tone="good"
        title="FUND1 的改进逻辑"
        chips={['cleaned fundamental', 'bucket 化表达', '只保留可解释字段', '降低噪声叙事', '交易数下降', 'Sortino 提升']}
      />
    </div>
  );
}

function DualAgentSlide() {
  return (
    <div>
      <HorizontalPipeline
        items={[
          ['features_list', FileJson],
          ['fundamental filter', Target],
          ['rebuild features', SlidersHorizontal],
          ['quant/f11 context', Layers3],
          ['decision agent', BookOpen],
          ['decisions_map', FileJson],
        ]}
      />
      <div className="checklist-grid">
        <TechCard refData={codeRefs.filter} title="基本面预筛" text="如果 features.fundamental.enabled=false，直接返回空列表；否则 LLM 判断哪些股票需要补基本面。" />
        <TechCard refData={codeRefs.dual} title="增强特征重建" text="对需要基本面的股票 include fundamental，对其他股票 exclude fundamental，减少 prompt 噪声。" />
        <TechCard refData={codeRefs.strategy} title="组合级决策" text="最终 prompt 包含 portfolio_info、symbols、history，可输出每只股票 target_cash_amount。" />
      </div>
    </div>
  );
}

function MemorySlide() {
  const items = [
    ['_add_decision_to_history()', '按 symbol 保存 date、decision、meta，新记录插到列表头部。'],
    ['_cleanup_old_history()', '按 max_history_days 清理旧记录，避免过期记忆污染当前市场。'],
    ['_get_decision_history_for_prompt()', '把历史记录转换成 prompt 需要的 action、cash_change、confidence。'],
    ['record_executed_decisions()', 'hold 全记录，buy/sell 只记录成功执行，防止被拒订单污染记忆。'],
  ];
  return (
    <div className="memory-layout">
      <div className="side-token">previous_decisions</div>
      <div className="memory-bank">
        <h3>Strategy 内部的长期历史状态</h3>
        <div className="memory-grid">
          {items.map(([name, desc]) => (
            <article className="memory-card" key={name}>
              <strong>{name}</strong>
              <span>llm_decision.py</span>
              <p>{desc}</p>
              <small>作用：让 LLM 看到股票级行为上下文</small>
            </article>
          ))}
        </div>
      </div>
      <div className="side-token good">decision_history in prompt</div>
    </div>
  );
}

function ExecutionSlide() {
  return (
    <div>
      <HorizontalPipeline
        items={[
          ['LLM action', BookOpen],
          ['target_cash_amount', FileJson],
          ['delta_value', BarChart3],
          ['qty = delta/open', SlidersHorizontal],
          ['BacktestEngine fill', Play],
          ['TradeRecord', ClipboardList],
        ]}
      />
      <div className="checklist-grid">
        <TechCard refData={codeRefs.strategy} title="策略侧" text="on_bar 对每只股票计算 current_value、target_value、delta_value，并修正 increase/decrease 但 delta≈0 的逻辑错误。" />
        <TechCard refData={codeRefs.engine} title="引擎侧" text="使用开盘价作为现金和估值口径，执行滑点、手续费、fill_ratio，并生成详细交易记录。" />
        <TechCard refData={codeRefs.report} title="产物侧" text="write_outputs 保存 trades.parquet、daily_nav.parquet、metrics.json、metrics_summary.csv 和图表。" />
      </div>
    </div>
  );
}

function CooldownSlide() {
  const days = [
    ['Day 1', '买入', 'buy'],
    ['Day 2', '继续持有', 'hold'],
    ['Day 3', '想反向卖出', 'blocked'],
    ['Day 4', '持有', 'hold'],
    ['Day 5', '持有', 'hold'],
    ['Day 6', '重新评估', 'open'],
  ];
  return (
    <div>
      <div className="callout">
        <TimerReset size={22} />
        <p>
          F6 的技术假设：LLM 对方向有一定判断力，但在短周期仓位表达上容易抖动。
          因此 cooldown 是行为层边界，不是 alpha 替代品。5D 有效，10D 过强。
        </p>
      </div>
      <div className="day-line">
        {days.map(([day, label, status]) => (
          <div className={`day-node ${status}`} key={day}>
            <strong>{day}</strong>
            <span />
            <p>{label}</p>
            {status === 'blocked' && <small>短期反向交易被降级</small>}
          </div>
        ))}
      </div>
    </div>
  );
}

function AttributionSlide() {
  const rows = [
    ['run-level', 'metrics.json', 'cum_return、max_drawdown、sortino、trades_count'],
    ['daily-level', 'daily_nav.parquet', '策略 NAV 与 benchmark NAV 可画收益/回撤曲线'],
    ['trade-level', 'detailed_trades.jsonl', '每笔交易的 open price、slippage、cash_before/after、realized_pnl'],
    ['state-level', 'detailed_portfolio_snapshots.jsonl', '每日现金、持仓、position_pct、unrealized_pnl'],
    ['attribution', 'analyze_experiment_attribution.py', '未来 5d/10d 收益、winner exposure、模块触发次数'],
  ];
  return <DataTable headers={['层级', '文件/脚本', '技术含义']} rows={rows} />;
}

function ResultsSlide({ selected, setSelected }) {
  const active = experimentRows.find((row) => row[0] === selected) || experimentRows[4];
  return (
    <div>
      <div className="result-summary">
        <Metric label="F6 Return" value="+3.99%" icon={TrendingUp} />
        <Metric label="F6 Sortino" value="0.043" icon={BarChart3} />
        <Metric label="F6 MDD" value="-9.16%" icon={TrendingDown} />
        <Metric label="F6 Trades" value="261" icon={LineChart} />
      </div>
      <div className="toolbar">
        {experimentRows.map((row) => (
          <button
            key={row[0]}
            className={selected === row[0] ? 'pill active' : 'pill'}
            onClick={() => setSelected(row[0])}
          >
            {row[0]}
          </button>
        ))}
      </div>
      <div className="detail-panel">
        <Target size={24} />
        <div>
          <strong>{active[0]}：{active[5]}</strong>
          <p>Return {active[1]}，Sortino {active[2]}，MDD {active[3]}，Trades {active[4]}。</p>
        </div>
      </div>
      <DataTable headers={['实验', 'Return', 'Sortino', 'MDD', 'Trades', '判断']} rows={experimentRows} highlight="F6 / 5D cooldown" />
    </div>
  );
}

function F11Slide() {
  return (
    <div className="compare-grid modules">
      <ModuleList
        title="F11 该保留的工程原则"
        tone="good"
        icon={CheckCircle2}
        items={[
          ['单模块', '每次只验证一个 prompt/context/size/budget 改动'],
          ['低权限', '不 hard sell blocking，不 regime hard-switch'],
          ['共享 filter cache', '同日同股票池的 fundamental filter 可跨实验复用'],
          ['dry-run / attribution', '先证明模块真的触发，再解释收益'],
        ]}
      />
      <div className="not-equal">≠</div>
      <ModuleList
        title="不该继续的方向"
        tone="bad"
        icon={XCircle}
        items={[
          ['full combo', '多个弱信号叠加后难归因'],
          ['generic reflection', '让模型保守但不精准'],
          ['rebound sizing boost', 'tag 可解释但未证明 future-return alpha'],
          ['强风险预算', '降低回撤容易同时压制反弹收益'],
        ]}
      />
    </div>
  );
}

function ClosingSlide() {
  return (
    <div className="closing-grid">
      <FlowBox items={['数据缓存隔离', '结构化特征', '双 Agent 决策', '历史记忆', '低权限执行约束', '归因评估']} emphasis={4} />
      <div className="future-card">
        <h3>最终汇报口径</h3>
        <ul>
          <li>F6 是当前综合最优，不是因为模块多，而是权限边界合适。</li>
          <li>有效模块集中在输入清洗和行为约束；高权限风险/卖出/组合优化多数会压制 alpha。</li>
          <li>后续必须补齐 5-run 均值 ± 标准差，避免把 LLM 随机性误读成稳定改进。</li>
          <li>所有新方向先回答“模块有没有真实触发、改了什么订单、改动后未来收益怎样”。</li>
        </ul>
        <strong>一句话：LLM 负责推理，系统负责边界、记忆、执行和证据。</strong>
      </div>
    </div>
  );
}

function CodePathList() {
  return (
    <div className="checklist-grid code-ref-grid">
      {Object.values(codeRefs).map((ref) => (
        <TechCard key={ref[0]} refData={ref} title={ref[1]} text={ref[2]} />
      ))}
    </div>
  );
}

function TechCard({ title, text, refData }) {
  return (
    <article className="info-card">
      <Code2 size={22} />
      <h3>{title}</h3>
      <p>{text}</p>
      <code>{refData[0]}</code>
    </article>
  );
}

function CardGrid({ cards }) {
  return (
    <div className="checklist-grid">
      {cards.map(([title, text, Icon]) => (
        <article className="info-card" key={title}>
          <Icon size={22} />
          <h3>{title}</h3>
          <p>{text}</p>
        </article>
      ))}
    </div>
  );
}

function Metric({ label, value, icon: Icon }) {
  return (
    <article className="metric">
      <Icon size={20} />
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function FlowBox({ items, emphasis }) {
  return (
    <div className="flow-vertical">
      {items.map((item, idx) => (
        <React.Fragment key={item}>
          <div className={idx === emphasis ? 'flow-item emphasis' : 'flow-item'}>{item}</div>
          {idx < items.length - 1 && <ArrowRight className="down-arrow" size={20} />}
        </React.Fragment>
      ))}
    </div>
  );
}

function HorizontalPipeline({ items }) {
  return (
    <div className="pipeline">
      {items.map(([label, Icon], idx) => (
        <React.Fragment key={label}>
          <div className="pipe-step">
            <Icon size={22} />
            <span>{label}</span>
          </div>
          {idx < items.length - 1 && <ArrowRight className="pipe-arrow" size={22} />}
        </React.Fragment>
      ))}
    </div>
  );
}

function SignalPanel({ title, chips, tone }) {
  return (
    <div className={`signal-panel ${tone}`}>
      <h3>{title}</h3>
      <div>
        {chips.map((chip) => (
          <span key={chip}>{chip}</span>
        ))}
      </div>
    </div>
  );
}

function ModuleList({ title, items, icon: Icon, tone }) {
  return (
    <div className={`module-list ${tone}`}>
      <h3><Icon size={22} />{title}</h3>
      {items.map(([name, text]) => (
        <article key={name}>
          <strong>{name}</strong>
          <span>{text}</span>
        </article>
      ))}
    </div>
  );
}

function DataTable({ headers, rows, highlight }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.join('-')} className={highlight && row[0] === highlight ? 'highlight' : ''}>
              {row.map((cell) => <td key={cell}>{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
