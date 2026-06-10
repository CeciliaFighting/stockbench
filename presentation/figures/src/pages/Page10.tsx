const memoryFields = [
  ['股票代码', 'symbol'],
  ['当前持仓', 'position_state'],
  ['上次动作', 'action'],
  ['目标金额', 'target_cash_amount'],
  ['决策理由', 'reasons'],
  ['置信度', 'confidence'],
];

const cycle = ['读取记忆', '写入 Prompt', '输出动作', '执行校验', '更新记录'];

const samples = [
  { symbol: 'AAPL', action: 'hold', days: '3 日', state: '冷却中' },
  { symbol: 'MSFT', action: 'increase', days: '8 日', state: '可调整' },
  { symbol: 'JNJ', action: 'decrease', days: '5 日', state: '可调整' },
];

export function Page10() {
  return (
    <main className="figure diagram-only page-10-clean">
      <section className="memory-figure">
        <div className="memory-record-card">
          <div className="memory-symbol">单股记忆</div>
          <div className="memory-fields">
            {memoryFields.map(([label, code]) => (
              <div key={code}>
                <b>{label}</b>
                <span>{code}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="memory-cycle">
          {cycle.map((step, index) => (
            <div className="cycle-step" key={step}>
              <em>{String(index + 1).padStart(2, '0')}</em>
              <span>{step}</span>
            </div>
          ))}
        </div>

        <div className="memory-samples">
          {samples.map((item) => (
            <div className="memory-sample-card" key={item.symbol}>
              <b>{item.symbol}</b>
              <div><span>上次动作</span><i>{item.action}</i></div>
              <div><span>距离交易</span><i>{item.days}</i></div>
              <div><span>当前状态</span><i>{item.state}</i></div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
