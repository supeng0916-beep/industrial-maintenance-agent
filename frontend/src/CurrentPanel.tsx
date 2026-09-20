import { localTime, type Snapshot } from './model'

export function CurrentPanel({ current, unverified }: { current?: Snapshot['current']; unverified: boolean }) {
  const sample = current?.measurement
  const status = current?.status
  const elapsed = current?.statusRequestedAt === undefined ? 0 : Math.max(0, performance.now() - current.statusRequestedAt) / 1000
  const stale = status?.is_stale || (status?.data_age_seconds != null && status.data_age_seconds + elapsed > status.stale_after_seconds)
  const uncertain = unverified || (!!sample && (status?.last_attempt_status === 'unknown' || (status?.data_age_seconds != null && status.data_age_seconds < 0)))
  const label = uncertain ? '当前电流未能核实' : !current ? '当前接口未提供电流' : !sample ? '暂无电流样本' : status?.last_attempt_status === 'failure' ? '最近采集失败，保留历史电流' : stale ? '电流数据已过期' : '电流数据未过期'
  return <section className="current-panel" aria-label="电流观测">
    <div><h2>最后有效电流 <span className="tag">仅观测，无电流告警</span></h2><p className="current-reading"><strong data-testid="current-value">{sample ? sample.value.toFixed(2) : '—'}</strong> A</p></div>
    <div className="current-detail"><strong data-testid="current-status">{label}</strong><p>电流原采集时间：<time data-testid="current-time" dateTime={sample?.collected_at}>{localTime(sample?.collected_at)}</time></p><p>电流最近尝试：{status?.last_attempt_status === 'failure' ? '失败' : status?.last_attempt_status === 'success' ? '成功' : '未知'} · {localTime(status?.last_attempt_at)}</p><p>温度与电流各用自己的采集记录判断新鲜度；“—”不是0A。</p></div>
  </section>
}
