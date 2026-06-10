const riskSignals = ['波动', '回撤', '集中度', '单股暴露'];

const strongRules = [
  '风险过高 → 阻止买入',
  '风险过高 → 强制持有',
  '风险过高 → 降低仓位',
];

const results = [
  { id: 'Q1', value: '-7.54%', note: '量化风险混合后错过反弹', bad: true },
  { id: 'RISK', value: '-2.60%', note: '硬覆盖可能误伤机会', bad: true },
  { id: 'F6', value: '+3.99%', note: '风险保留为提示，不主导订单', bad: false },
];

export function Page13() {
  return (
    <main className="figure diagram-only page-13-clean">
      <section className="risk-figure">
        <div className="risk-signal-card">
          {riskSignals.map((signal) => <span key={signal}>{signal}</span>)}
        </div>

        <div className="risk-mode-compare">
          <div className="risk-mode-card hard">
            <b>强覆盖</b>
            {strongRules.map((rule) => <span key={rule}>{rule}</span>)}
          </div>
          <div className="risk-mode-card soft">
            <b>软提示</b>
            <span>进入 Prompt</span>
            <span>提醒 LLM 但不直接改单</span>
            <span>只在极端情况考虑硬约束</span>
          </div>
        </div>

        <div className="risk-results">
          {results.map((item) => (
            <div className={`risk-result-card ${item.bad ? 'bad' : 'good'}`} key={item.id}>
              <b>{item.id}</b>
              <strong>{item.value}</strong>
              <span>{item.note}</span>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
