const kept = ['清洗特征', '股票级记忆', '5 日冷却', '风险软提示', '归因日志'];
const rejected = ['强量化覆盖', '高权限风险否决', '过强冷却', '无筛选字段堆叠'];

const metrics = [
  { label: '收益', value: '+3.99%' },
  { label: '最大回撤', value: '-9.16%' },
  { label: '交易次数', value: '261' },
];

const evidence = [
  '消融实验确认模块贡献',
  'raw_action 与 final_action 可对比',
  '冷却触发原因可记录',
  '负贡献版本被排除',
];

export function Page15() {
  return (
    <main className="figure diagram-only page-15-clean">
      <section className="final-evidence-figure">
        <div className="final-system-card">
          <div className="f6-large">F6</div>
          <div className="f6-metrics">
            {metrics.map((item) => (
              <div key={item.label}><b>{item.value}</b><span>{item.label}</span></div>
            ))}
          </div>
        </div>

        <div className="final-lists">
          <div className="kept-list">
            <b>保留</b>
            {kept.map((item) => <span key={item}>{item}</span>)}
          </div>
          <div className="rejected-list">
            <b>不保留为主线</b>
            {rejected.map((item) => <span key={item}>{item}</span>)}
          </div>
        </div>

        <div className="evidence-chain">
          {evidence.map((item, index) => (
            <div className="evidence-node" key={item}>
              <em>{String(index + 1).padStart(2, '0')}</em>
              <span>{item}</span>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
