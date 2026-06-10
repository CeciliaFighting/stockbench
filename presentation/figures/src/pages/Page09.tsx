const inputs = [
  { label: '近 7 日价格', code: 'close_7d' },
  { label: '当日开盘', code: 'open' },
  { label: '组合状态', code: 'position_state' },
];

const metrics = [
  { label: '短期收益', code: 'return_5d' },
  { label: '七日动量', code: 'momentum_7d' },
  { label: '低波动排名', code: 'low_volatility_rank_pct' },
  { label: '持仓权重', code: 'position_weight' },
];

const ranks = [
  { group: 'top', label: '优先关注', width: 92, color: 'blue' },
  { group: 'middle', label: '正常观察', width: 58, color: 'cyan' },
  { group: 'bottom', label: '降低权重', width: 24, color: 'red' },
];

const outputs = [
  { label: '横向排名', code: 'rank_pct' },
  { label: '强弱分桶', code: 'bucket' },
  { label: '现金约束', code: 'cash_ratio' },
];

export function Page09() {
  return (
    <main className="figure diagram-only page-09-clean">
      <div className="paper-grid" />
      <section className="ranking-flow">
        <div className="ranking-inputs">
          {inputs.map((item) => (
            <div className="rank-input-card" key={item.code}>
              <b>{item.label}</b>
              <span>{item.code}</span>
            </div>
          ))}
        </div>

        <div className="metric-board">
          {metrics.map((item, index) => (
            <div className="metric-row-clean" key={item.code}>
              <em>{String(index + 1).padStart(2, '0')}</em>
              <b>{item.label}</b>
              <span>{item.code}</span>
            </div>
          ))}
        </div>

        <div className="rank-output-panel">
          <div className="rank-bars">
            {ranks.map((rank) => (
              <div className="rank-bar-line" key={rank.group}>
                <b>{rank.group}</b>
                <span><i className={`rank-fill ${rank.color}`} style={{ width: `${rank.width}%` }} /></span>
                <em>{rank.label}</em>
              </div>
            ))}
          </div>
          <div className="rank-output-cards">
            {outputs.map((item) => (
              <div key={item.code}>
                <b>{item.label}</b>
                <span>{item.code}</span>
              </div>
            ))}
          </div>
          <div className="rank-note">排序只帮助聚焦，不直接替代 LLM 决策</div>
        </div>
      </section>
    </main>
  );
}
