import { localTime, type MetricSnapshot, type Snapshot } from './model'
import { replayRunningLabel } from './ReplayPanel'

export function runningLabel(value: number) {
  return value === 0 ? '停止' : value === 1 ? '运行' : `无法识别（原始值 ${value}）`
}

export function OperatingPanel({ metric, reading, unverified, replay = false }: {
  metric: 'speed' | 'running_state'; reading?: MetricSnapshot; unverified: boolean; replay?: boolean
}) {
  const title = metric === 'speed' ? '转速' : '运行状态'
  const sample = reading?.measurement
  const status = reading?.status
  const elapsed = reading?.statusRequestedAt === undefined ? 0 : Math.max(0, performance.now() - reading.statusRequestedAt) / 1000
  const stale = status?.is_stale || (status?.data_age_seconds != null && status.data_age_seconds + elapsed > status.stale_after_seconds)
  const invalid = status?.last_failure_type === 'data_validation_error'
  let label = '本次数据有效'
  if (unverified) label = '当前未知：查询未能核实'
  else if (!reading) label = `当前接口未提供${title}`
  else if (status?.last_attempt_status === 'failure') label = `当前未知：${invalid ? metric === 'running_state' ? '本次状态值未定义（数据校验失败）' : '数据校验失败' : '通信失败'}`
  else if (!sample) label = `暂无${title}样本`
  else if (stale) label = '当前未知：数据已过期'
  else if (status?.last_attempt_status !== 'success' || (status.data_age_seconds != null && status.data_age_seconds < 0)) label = '当前未知：时间或结果未能核实'
  else if (metric === 'running_state' && sample.value !== 0 && sample.value !== 1) label = '当前未知：运行状态无法识别'
  return <section className="operating-panel" aria-label={`${title}观测`}>
    <h2>最后有效{title}</h2>
    <p className="operating-value"><strong data-testid={`${metric}-value`}>{sample ? metric === 'speed' ? sample.value.toFixed(0) : replay ? replayRunningLabel(sample.value) : runningLabel(sample.value) : '—'}</strong>{metric === 'speed' && <span> rpm</span>}</p>
    <p data-testid={`${metric}-status`} className="operating-status">{label}</p>
    <p>{replay ? '该行回放时间' : '原采集时间'}：<time data-testid={`${metric}-time`} dateTime={sample?.collected_at}>{localTime(sample?.collected_at)}</time></p>
    {status?.last_attempt_status === 'failure' && status.last_failure_message && <p className="failure-evidence" data-testid={`${metric}-failure`}>{unverified ? '历史失败证据' : '最近失败证据'}：{status.last_failure_message}</p>}
    <p className="scope-note">{metric === 'speed' ? '0 rpm是有效零转速，未知时不补零。' : replay ? '1＝正常运转，0＝数据集标注故障（Machine failure 列）。' : '0＝停止，1＝运行；断线不等于停止。'} 本测点仅观测。</p>
  </section>
}

export function RunningHistory({ history, replay = false }: { history: Snapshot['history']; replay?: boolean }) {
  // 窗口仍最多1000点；用有界滚动列表保留全部实际记录，不把重复采样冒充状态变化。
  return <div className="running-history" tabIndex={0} role="region" aria-label="运行状态历史记录"><table><thead><tr><th>{replay ? '该行回放时间（本地）' : '原采集时间（本地）'}</th><th>状态</th><th>原始值</th></tr></thead><tbody>{[...history.points].reverse().map(point => <tr key={point.id}><td><time dateTime={point.collected_at}>{localTime(point.collected_at)}</time></td><td>{replay ? replayRunningLabel(point.value) : runningLabel(point.value)}</td><td>{point.value}</td></tr>)}</tbody></table></div>
}
