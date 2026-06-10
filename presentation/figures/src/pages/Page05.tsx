const problems = [
  { label: '输入噪声', note: '字段多、质量不均' },
  { label: '没有记忆', note: '每天重新判断' },
  { label: '频繁反转', note: '买卖动作来回切换' },
  { label: '难以归因', note: '不知道收益来自哪里' },
];

const modules = [
  { label: '清洗输入', note: '把数据压成结构化特征' },
  { label: '交易记忆', note: '记录个股动作与理由' },
  { label: '订单冷却', note: '拦截短期反向交易' },
  { label: '消融验证', note: '比较模块真实贡献' },
];

const outcomes = ['更稳定', '少交易', '可解释', '可复盘'];

export function Page05() {
  return (
    <main className="figure diagram-only page-05-clean">
      <div className="paper-grid" />
      <section className="problem-transform">
        <div className="single-agent-card">
          <div className="agent-orbit">
            <span>当日数据</span>
            <i>LLM</i>
            <span>交易动作</span>
          </div>
          <div className="problem-list">
            {problems.map((item) => (
              <div className="problem-pill" key={item.label}>
                <b>{item.label}</b>
                <small>{item.note}</small>
              </div>
            ))}
          </div>
        </div>

        <div className="transform-gate">
          <span />
          <b>工程化改造</b>
          <span />
        </div>

        <div className="modular-agent-card">
          <div className="module-grid-clean">
            {modules.map((item, index) => (
              <div className="module-tile-clean" key={item.label}>
                <em>{String(index + 1).padStart(2, '0')}</em>
                <b>{item.label}</b>
                <small>{item.note}</small>
              </div>
            ))}
          </div>
          <div className="outcome-strip">
            {outcomes.map((item) => <span key={item}>{item}</span>)}
          </div>
        </div>
      </section>
    </main>
  );
}
