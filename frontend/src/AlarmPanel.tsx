import { localTime } from './model'
import type { AlarmSnapshot } from './model'

export function AlarmPanel({ alarm, unverified }: { alarm?: AlarmSnapshot; unverified: boolean }) {
  const current = unverified || !alarm ? 'unknown' : alarm.current
  const title = current === 'not_enabled' ? '告警规则未启用' : current === 'unknown' ? '当前未知' : current === 'pending' ? '超限待确认' : current === 'active' ? '当前温度告警中' : '当前无未解除告警'
  const active = alarm?.active
  const confirmSeconds = alarm?.rule.confirm_seconds ?? 0
  const pending = alarm?.pending
  return <section className="alarm-panel" aria-labelledby="alarm-heading">
    <div className="chart-heading"><div><h2 id="alarm-heading">温度回差告警</h2><p>教学规则：新温度 &gt;{alarm?.rule.trigger_above ?? 80}℃{confirmSeconds > 0 ? `，观测连续至少${confirmSeconds}秒才触发；≤${alarm?.rule.trigger_above ?? 80}℃取消待确认。` : '即时触发。'} 已报警时 &lt;{alarm?.rule.recover_below ?? 78}℃ 恢复，等于恢复阈值保持。</p></div><span className="tag">教学配置</span></div>
    <div className={`alarm-status ${active ? 'warn' : ''}`}>
      <strong data-testid="alarm-status" role="status">{title}</strong>
      {current === 'pending' && pending && <p data-testid="alarm-pending">已观测累计 {pending.elapsed_seconds.toFixed(1)} 秒 / 需 {confirmSeconds} 秒。首次超限：{localTime(pending.first_exceeded_at)}。等待下一次有效样本，不按页面倒计时触发。</p>}
      {active && <p data-testid="alarm-active">{unverified ? '历史快照中有未解除告警' : '仍有未解除告警'} #{active.id} · {localTime(active.started_at)} 由 {active.trigger_value.toFixed(1)}℃ 触发。</p>}
      {current === 'unknown' && <p>当前温度无法确认。通信失败、数据校验失败、数据过期或接口查询失败都不能作为告警恢复证据；等待新的有效采集结果。</p>}
      {current === 'not_enabled' && <p>此数据库尚无可用的告警规则状态。使用新版采集器连接同一数据库，并等待新样本；旧测量不会补算成刚发生的告警。</p>}
      {current === 'clear' && <p>最近有效样本支持此规则判断，不表示设备健康。</p>}
    </div>
    <details className="alarm-history">
      <summary>告警历史 · {alarm ? `最近 ${alarm.history.length} 条 / 共 ${alarm.total} 条` : '待加载'}{unverified && alarm ? '（历史快照）' : ''}</summary>
      {alarm?.history.length ? <ol data-testid="alarm-history">{alarm.history.map(event => <li key={event.id}>
        <div><strong>#{event.id} · {event.recovered_at ? '已恢复' : '未解除'}</strong><span>本次规则：&gt;{event.trigger_above}℃ / &lt;{event.recover_below}℃</span></div>
        <p>本次确认要求：{event.confirm_seconds ? `观测连续至少${event.confirm_seconds}秒` : '即时触发（旧规则）'}</p>
        {event.observed_seconds != null && <p>触发时已观测 {event.observed_seconds.toFixed(1)} 秒 · 当次允许样本间隔 {event.max_gap_seconds} 秒</p>}
        {event.first_exceeded_at && <p>首次超限：{localTime(event.first_exceeded_at)} · {event.first_exceeded_value?.toFixed(1)}℃ · 样本 #{event.first_exceeded_measurement_id}</p>}
        <p>正式触发：{localTime(event.started_at)} · {event.trigger_value.toFixed(1)}℃ · 样本 #{event.trigger_measurement_id}</p>
        <p>恢复：{event.recovered_at ? `${localTime(event.recovered_at)} · ${event.recovery_value?.toFixed(1)}℃ · 样本 #${event.recovery_measurement_id}` : '尚无恢复证据'}</p>
      </li>)}</ol> : <p>{current === 'not_enabled' || !alarm ? '暂无可用的告警历史。' : '尚无告警记录；这里只统计规则启用后的新采集结果。'}</p>}
      {confirmSeconds > 0 && <p className="scope-note">相邻有效样本最多间隔 {alarm?.rule.max_gap_seconds ?? '—'} 秒；失败、长间隙或采集器重启都重新累计。连续观测不证明两个采样时刻之间的物理温度始终超限。</p>}
      <p className="scope-note">采集器独立执行规则，关闭或刷新页面不会创建告警。时间为本地时间；连续高温合并在同一次告警内。</p>
    </details>
  </section>
}
