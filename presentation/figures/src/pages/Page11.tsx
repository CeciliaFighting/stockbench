const promptInputs = [
  { label: '组合信息', code: 'portfolio_info', items: ['total_assets', 'available_cash', 'position_value'] },
  { label: '股票特征', code: 'symbols', items: ['market_data', 'news_events', 'position_state'] },
  { label: '交易记忆', code: 'history', items: ['action', 'reasons', 'confidence'] },
  { label: '风险提示', code: 'risk note', items: ['volatility', 'drawdown', 'concentration'] },
];

const outputFields = ['action', 'target_cash_amount', 'cash_change', 'reasons', 'confidence'];
const checks = ['JSON 解析', '动作合法性', '资金校验', '保存原始建议'];

export function Page11() {
  return (
    <main className="figure diagram-only page-11-clean">
      <section className="prompt-schema-flow">
        <div className="prompt-inputs">
          {promptInputs.map((block) => (
            <div className="prompt-input-card" key={block.code}>
              <b>{block.label}</b>
              <i>{block.code}</i>
              <div>{block.items.map((item) => <span key={item}>{item}</span>)}</div>
            </div>
          ))}
        </div>

        <div className="llm-core-card">
          <div className="llm-core-circle">LLM</div>
          <span>decision_agent_v1</span>
          <p>输入是结构化任务，输出是交易建议</p>
        </div>

        <div className="json-output-card">
          <div className="json-brace">{`{`}</div>
          {outputFields.map((field) => (
            <div className="json-line" key={field}>
              <b>{field}</b>
              <span>{field === 'action' ? 'increase / decrease / hold / close' : 'value'}</span>
            </div>
          ))}
          <div className="json-brace">{`}`}</div>
        </div>

        <div className="parser-strip">
          {checks.map((item, index) => (
            <div key={item}><em>{String(index + 1).padStart(2, '0')}</em><span>{item}</span></div>
          ))}
        </div>
      </section>
    </main>
  );
}
