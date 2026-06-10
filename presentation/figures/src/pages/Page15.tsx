const kept = ['清洗特征', '股票级记忆', '5 日冷却', '风险软提示', '归因日志'];
const rejected = ['强量化覆盖', '高权限风险否决', '过强冷却', '无筛选字段堆叠'];

const metrics = [
  { label: '收益', value: '+3.99%' },
  { label: '最大回撤', value: '-9.16%' },
  { label: '交易次数', value: '261' },
];

const evidence = [
  '消融实验确认模块贡献',
  '原始建议与最终订单可对比',
  '冷却触发原因可记录',
  '负贡献版本被排除',
];

export function Page15() {
  return (
    <main className="figure diagram-only page-15-clean page-15-v2">
      <section className="final-clean-board">
        <div className="final-metric-row">
          {metrics.map((item) => (
            <div className="final-metric-card" key={item.label}>
              <b>{item.value}</b>
              <span>{item.label}</span>
            </div>
          ))}
        </div>

        <div className="f6-formula-row">
          <span>F6</span>
          <i>=</i>
          {kept.map((item) => <b key={item}>{item}</b>)}
        </div>

        <div className="final-three-columns">
          <div className="final-column keep">
            <h3>保留</h3>
            {kept.map((item) => <p key={item}>{item}</p>)}
          </div>
          <div className="final-column avoid">
            <h3>不作为主线</h3>
            {rejected.map((item) => <p key={item}>{item}</p>)}
          </div>
          <div className="final-column evidence">
            <h3>证据链</h3>
            {evidence.map((item, index) => (
              <p key={item}><em>{String(index + 1).padStart(2, '0')}</em>{item}</p>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
