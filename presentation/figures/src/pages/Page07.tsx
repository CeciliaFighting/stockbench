const sources = [
  { label: '行情', fields: ['开盘价', '近 7 日收盘', '交易日期'] },
  { label: '新闻', fields: ['标题', '摘要', 'Top-K 事件'] },
  { label: '基本面', fields: ['市值', '市盈率', '股息率', '52 周区间'] },
  { label: '持仓', fields: ['持仓市值', '持有天数', '股数'] },
];

const cleaningSteps = [
  '按日期排序去重',
  '排除决策日收盘',
  '缺失值补默认',
  '新闻压缩为 Top-K',
  '基本面按需加载',
];

const outputs = [
  { key: 'market_data', name: '市场数据', fields: ['ticker', 'open', 'close_7d', 'date'] },
  { key: 'news_events', name: '新闻事件', fields: ['top_k_events'] },
  { key: 'position_state', name: '组合状态', fields: ['current_position_value', 'holding_days', 'shares'] },
  { key: 'fundamental_data', name: '基本面块', fields: ['market_cap', 'pe_ratio', 'dividend_yield'] },
];

export function Page07() {
  return (
    <main className="figure diagram-only page-07-clean">
      <div className="paper-grid" />
      <section className="feature-flow">
        <div className="feature-sources">
          {sources.map((source) => (
            <div className="source-card" key={source.label}>
              <b>{source.label}</b>
              <div>
                {source.fields.map((field) => <span key={field}>{field}</span>)}
              </div>
            </div>
          ))}
        </div>

        <div className="cleaning-pipeline">
          {cleaningSteps.map((step, index) => (
            <div className="clean-step" key={step}>
              <em>{String(index + 1).padStart(2, '0')}</em>
              <span>{step}</span>
            </div>
          ))}
        </div>

        <div className="prompt-output-blocks">
          {outputs.map((block) => (
            <div className="prompt-block" key={block.key}>
              <i>{block.key}</i>
              <b>{block.name}</b>
              <div>
                {block.fields.map((field) => <span key={field}>{field}</span>)}
              </div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
