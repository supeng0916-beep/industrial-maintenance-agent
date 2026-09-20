// 回放设备（motor-c）专用面板：来源声明 + 数据集标注故障史；运行状态语义与仿真设备不同。
import { localTime, type ReplayStatus, type MetricSnapshot } from './model'

export function replayRunningLabel(value: number) {
  return value === 1 ? '正常运转' : value === 0 ? '数据集标注故障' : `无法识别（原始值 ${value}）`
}

function stale(reading: MetricSnapshot | undefined, unverified: boolean) {
  const status = reading?.status
  const elapsed = reading?.statusRequestedAt === undefined ? 0 : Math.max(0, performance.now() - reading.statusRequestedAt) / 1000
  if (unverified) return '当前未知：查询未能核实'
  if (!reading) return '当前接口未提供该指标'
  if (!reading.measurement) return '暂无样本'
  if (status?.last_attempt_status === 'failure') return '最近回放行写入失败'
  if (status?.is_stale || (status?.data_age_seconds != null && status?.data_age_seconds + elapsed > status.stale_after_seconds)) return '回放已停止：数据过期'
  return '回放进行中'
}

export function ReplayMetricsPanel({ torque, toolWear, airTemperature, unverified }: {
  torque?: MetricSnapshot; toolWear?: MetricSnapshot; airTemperature?: MetricSnapshot; unverified: boolean
}) {
  const cards = [
    { metric: 'torque', title: '扭矩', reading: torque, format: (v: number) => v.toFixed(1), unit: 'Nm' },
    { metric: 'tool_wear', title: '刀具磨损', reading: toolWear, format: (v: number) => v.toFixed(0), unit: 'min' },
    { metric: 'air_temperature', title: '空气温度', reading: airTemperature, format: (v: number) => v.toFixed(1), unit: '℃' },
  ] as const
  return <section className="current-panel replay-metrics" aria-label="回放附加指标观测">
    {cards.map(card => <div key={card.metric}>
      <h2>最后有效{card.title} <span className="tag">数据集原值</span></h2>
      <p className="current-reading"><strong data-testid={`${card.metric}-value`}>{card.reading?.measurement ? card.format(card.reading.measurement.value) : '—'}</strong> {card.unit}</p>
      <p><strong data-testid={`${card.metric}-status`}>{stale(card.reading, unverified)}</strong></p>
      <p>该行回放时间：<time dateTime={card.reading?.measurement?.collected_at}>{localTime(card.reading?.measurement?.collected_at)}</time></p>
    </div>)}
  </section>
}

export function ReplayFaultPanel({ replay, unverified }: { replay?: ReplayStatus | null; unverified: boolean }) {
  const dataset = replay?.dataset
  return <section className="alarm-panel replay-panel" aria-label="数据集标注故障史">
    <div className="alarm-heading">
      <h2>数据集标注故障 <span className="tag">历史回放</span></h2>
      <p>故障标签来自 AI4I 2020 数据集自身列，本系统不做再判定{unverified ? '；当前查询未能核实' : ''}</p>
    </div>
    {replay ? <>
      <p className="replay-note" data-testid="replay-note">{replay.note}</p>
      <dl className="replay-dataset">
        <div><dt>数据集</dt><dd>{dataset?.name}（{dataset?.rows_total} 行，合成数据）</dd></div>
        <div><dt>许可</dt><dd>{dataset?.license} · <a href={dataset?.source} target="_blank" rel="noreferrer noopener">UCI 来源</a></dd></div>
        <div><dt>窗口内故障行</dt><dd data-testid="replay-faults-total">{replay.faults_total} 行</dd></div>
      </dl>
      {replay.faults.length === 0 ? <div className="empty-chart"><strong>回放窗口内还没有数据集标注的故障行</strong><p>继续回放即可出现；AI4I 2020 全集共 339 个故障标注。</p></div>
        : <ol className="replay-faults">
          {replay.faults.map(fault => <li key={fault.occurred_at + fault.message}>
            <time dateTime={fault.occurred_at}>{localTime(fault.occurred_at)}</time>
            <span>{fault.message}</span>
          </li>)}
        </ol>}
    </> : <p className="empty-chart"><strong>回放信息待加载</strong></p>}
    <p className="scope-note">“数据集标注故障”是数据集对合成工况的标注，不是本系统对真实设备的诊断；停机/故障不由此推断设备健康。</p>
  </section>
}
