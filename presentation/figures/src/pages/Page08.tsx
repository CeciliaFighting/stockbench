const symbols = ['GS', 'MSFT', 'HD', 'V', 'SHW', 'CAT', 'MCD', 'UNH', 'AXP', 'AMGN', 'TRV', 'CRM', 'JPM', 'IBM', 'HON', 'BA', 'AMZN', 'AAPL', 'PG', 'JNJ'];

const gates = [
  { label: '配置范围', note: '固定股票池', code: 'symbols_universe' },
  { label: '行情可用', note: '当日开盘 + 历史收盘', code: 'open / close_7d' },
  { label: '新闻压缩', note: '近两日 Top-K 事件', code: 'top_k_events' },
  { label: '持仓补齐', note: '现金、股数、持有天数', code: 'position_state' },
  { label: '幻觉过滤', note: '只保留真实输入股票', code: 'valid_symbols' },
];

const outputs = [
  '每日可决策股票列表',
  '每只股票一份特征块',
  '只允许返回池内股票动作',
];

export function Page08() {
  return (
    <main className="figure diagram-only page-08-clean">
      <div className="paper-grid" />
      <section className="universe-flow">
        <div className="symbol-pool-card">
          <div className="pool-count"><b>20</b><span>只股票</span></div>
          <div className="symbol-grid">
            {symbols.map((symbol) => <span key={symbol}>{symbol}</span>)}
          </div>
        </div>

        <div className="gate-stack">
          {gates.map((gate, index) => (
            <div className="universe-gate" key={gate.label}>
              <em>{String(index + 1).padStart(2, '0')}</em>
              <div>
                <b>{gate.label}</b>
                <span>{gate.note}</span>
              </div>
              <i>{gate.code}</i>
            </div>
          ))}
        </div>

        <div className="tradable-result-card">
          <div className="result-icon">✓</div>
          <div className="result-lines">
            {outputs.map((item) => <span key={item}>{item}</span>)}
          </div>
          <div className="prompt-map-mini">
            <b>symbols</b>
            <p>GS</p><p>MSFT</p><p>AAPL</p><p>JNJ</p>
          </div>
        </div>
      </section>
    </main>
  );
}
