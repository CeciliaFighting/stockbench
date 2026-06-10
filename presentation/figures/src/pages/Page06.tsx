import { architectureLayers } from '../data';

const shortRoles = [
  '把行情、新闻、持仓、基本面整理成结构化输入',
  '固定二十只道指成分股，按当日数据可用性进入决策',
  '用相对强弱和动量排序，降低横向比较负担',
  '保留个股历史动作与理由，减少每天从零判断',
  '双 Agent 组织输入，输出结构化交易建议',
  '五日冷却拦截短期反向交易，抑制无效反转',
  '风险信息作为提示保留，避免高权限覆盖误伤机会',
  '记录指标、交易和干预，形成可复盘证据链',
];

const outputs = [
  '结构化特征',
  '可交易范围',
  '重点候选',
  '个股记忆',
  '原始建议',
  '最终订单',
  '风险提示',
  '归因证据',
];

const tags = [
  ['行情', '新闻', '持仓', '基本面'],
  ['道指二十只', '数据可用'],
  ['相对强弱', '动量排序'],
  ['历史动作', '交易理由'],
  ['Prompt', 'JSON'],
  ['冷却=5日', '反向交易'],
  ['波动', '回撤', '集中度'],
  ['指标', '交易', '干预'],
];

function CompactLayer({ layer, index }: { layer: typeof architectureLayers[number]; index: number }) {
  return (
    <div className={`wide-layer tone-${layer.tone}`}>
      <div className="wide-index">{String(index + 1).padStart(2, '0')}</div>
      <div className="wide-main">
        <div className="wide-title">
          <b>{layer.title}</b>
          <span>{outputs[index]}</span>
        </div>
        <p>{shortRoles[index]}</p>
      </div>
      <div className="wide-tags">
        {tags[index].map((item) => (
          <i key={item}>{item}</i>
        ))}
      </div>
    </div>
  );
}

export function Page06() {
  return (
    <main className="figure diagram-only page-06-clean page-06-list-only">
      <div className="paper-grid" />
      <section className="layers-wide">
        {architectureLayers.map((layer, index) => (
          <CompactLayer key={layer.id} layer={layer} index={index} />
        ))}
      </section>
    </main>
  );
}
