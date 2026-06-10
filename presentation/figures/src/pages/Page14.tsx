import { ablationRuns, moduleColumns } from '../data';

const rows = ablationRuns.filter((run) => ['B0', 'Q1', 'FUND1', 'C1', 'M1', 'F5', 'F6', '10D', 'RISK', 'F10'].includes(run.id));
const maxTrades = Math.max(...rows.map((run) => run.trades));
const returnMin = -8;
const returnMax = 4.5;

const shortVerdict: Record<string, string> = {
  B0: '收益为正，但交易过频。',
  Q1: '负面：量化风险混合后错过反弹。',
  FUND1: '有效：输入质量改善。',
  C1: '约束有效，但单独使用过强。',
  M1: '泛化反思过于保守。',
  F5: '收益继续提升，但回撤偏大。',
  F6: '综合最优：收益、回撤、交易次数均衡。',
  '10D': '过强冷却压制收益。',
  RISK: '负面：硬覆盖误伤机会。',
  F10: '未超过 F6，不升级主线。',
};

function formatPct(value: number, digits = 2) {
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(digits)}%`;
}

function ReturnBar({ value, status }: { value: number; status: string }) {
  const start = Math.min(value, 0);
  const end = Math.max(value, 0);
  const left = ((start - returnMin) / (returnMax - returnMin)) * 100;
  const width = ((end - start) / (returnMax - returnMin)) * 100;
  const zero = ((0 - returnMin) / (returnMax - returnMin)) * 100;
  return (
    <div className="return-bar-cell">
      <div className="return-axis">
        <span className="return-zero" style={{ left: `${zero}%` }} />
        <span
          className={`return-bar ${value >= 0 ? 'positive' : 'negative'} status-${status}`}
          style={{ left: `${left}%`, width: `${width}%` }}
        />
      </div>
      <b className={value >= 0 ? 'positive-text' : 'negative-text'}>{formatPct(value)}</b>
    </div>
  );
}

function ModuleMark({ active, status }: { active: boolean; status: string }) {
  return <span className={`matrix-dot ${active ? 'active' : ''} status-${status}`} />;
}

export function Page14() {
  return (
    <main className="figure diagram-only page-14-clean page-14-table-only">
      <div className="paper-grid" />

      <section className="ablation-table-clean single-table">
        <div className="clean-head">
          <div>版本</div>
          <div className="module-heads">
            {moduleColumns.map((mod) => <span key={mod.key}>{mod.label}</span>)}
          </div>
          <div>收益</div>
          <div>回撤</div>
          <div>交易</div>
          <div>结论</div>
        </div>

        {rows.map((run) => (
          <div key={run.id} className={`clean-row status-${run.status}`}>
            <div className="clean-run">
              <b>{run.id}</b>
              <span>{run.name}</span>
            </div>
            <div className="clean-modules">
              {moduleColumns.map((mod) => (
                <ModuleMark key={mod.key} active={run.modules.includes(mod.key)} status={run.status} />
              ))}
            </div>
            <ReturnBar value={run.returnPct} status={run.status} />
            <div className="clean-metric">{formatPct(run.maxDrawdown)}</div>
            <div className="clean-trades">
              <b>{run.trades}</b>
              <span style={{ width: `${(run.trades / maxTrades) * 100}%` }} />
            </div>
            <div className="clean-verdict">{shortVerdict[run.id] ?? run.verdict}</div>
          </div>
        ))}
      </section>
    </main>
  );
}
