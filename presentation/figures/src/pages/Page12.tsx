const conditions = [
  { label: '距离上次交易', value: '< 5 日' },
  { label: '动作方向', value: '与上次相反' },
  { label: '触发结果', value: '改为 hold' },
];

const examples = [
  { raw: 'increase', last: 'decrease', days: 3, final: 'hold', status: '拦截' },
  { raw: 'decrease', last: 'increase', days: 4, final: 'hold', status: '拦截' },
  { raw: 'increase', last: 'increase', days: 2, final: 'increase', status: '保留' },
  { raw: 'hold', last: 'increase', days: 1, final: 'hold', status: '保留' },
];

export function Page12() {
  return (
    <main className="figure diagram-only page-12-clean">
      <section className="cooldown-figure">
        <div className="raw-action-card">
          <b>LLM 原始建议</b>
          <div className="action-pair"><span>raw_action</span><i>increase / decrease</i></div>
          <div className="action-pair"><span>last_action</span><i>历史动作</i></div>
        </div>

        <div className="cooldown-gate-card">
          <div className="gate-number">5</div>
          <span>日冷却窗口</span>
          <div className="condition-list">
            {conditions.map((item) => (
              <div key={item.label}><b>{item.label}</b><i>{item.value}</i></div>
            ))}
          </div>
        </div>

        <div className="final-action-card">
          <b>最终订单</b>
          <div className="action-pair"><span>final_action</span><i>hold 或保留原动作</i></div>
          <div className="action-pair"><span>记录字段</span><i>trigger / reason</i></div>
        </div>

        <div className="cooldown-table">
          {examples.map((row) => (
            <div className={`cooldown-row ${row.status === '拦截' ? 'blocked' : ''}`} key={`${row.raw}-${row.last}-${row.days}`}>
              <span>{row.raw}</span>
              <span>{row.last}</span>
              <span>{row.days} 日</span>
              <span>{row.final}</span>
              <b>{row.status}</b>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
